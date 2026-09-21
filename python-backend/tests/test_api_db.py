"""Tester hele flowet gennem API'et mod en rigtig database (et midlertidigt testschema).

Google og Claude er falske. Alt andet er ægte: routes, validering, SQL, transaktioner
og migrationer. Se conftest.py for hvordan testdatabasen laves og ryddes op.
"""

import httpx
import psycopg
import pytest

from app.db import pool as db_pool
from tests.conftest import PLACE, FakeClaude, google_ok, use_claude, use_google

PLACE_ID = "ChIJtest"


def fetch_places(client, business_type=""):
    return client.get("/api/places/reviews", params={"placeId": PLACE_ID, "businessType": business_type})


def by_external_id(data):
    return {r["externalId"].rsplit("/", 1)[-1]: r for r in data["reviews"]}


# ---- migrationer -----------------------------------------------------------------


def test_migrations_apply_once_and_are_idempotent(migration_result):
    first, second = migration_result
    assert first == 1  # 001_init.sql
    assert second == 0  # næste kørsel gør ingenting


# ---- hent fra Google og gem ------------------------------------------------------


def test_empty_database_gives_empty_restaurant_list(client):
    assert client.get("/api/restaurants").json() == {"restaurants": []}


def test_fetching_from_google_saves_restaurant_and_reviews(client):
    calls = use_google(client, google_ok())

    response = fetch_places(client, "Café")
    assert response.status_code == 200
    data = response.json()

    assert data["businessName"] == "Test Café"
    assert data["businessType"] == "Café"
    assert data["address"] == "Testvej 1, 2200 København"
    assert data["rating"] == 4.4
    assert data["userRatingCount"] == 120
    assert {r["status"] for r in data["reviews"]} == {"new"}
    assert by_external_id(data)["r1"]["reviewerName"] == "Ida"
    assert by_external_id(data)["r1"]["publishedAt"].startswith("2026-09-01T10:00:00")

    # Nøglen sendes i header, ikke i URL'en, og stien er præcis det vi forventer.
    (call,) = calls
    assert call.headers["X-Goog-Api-Key"] == "test-google-key"
    assert "test-google-key" not in str(call.url)
    assert call.url.path == "/v1/places/ChIJtest"

    # ...og det er blevet gemt: en ny hentning fra databasen giver det samme.
    (restaurant,) = client.get("/api/restaurants").json()["restaurants"]
    saved = client.get(f"/api/restaurants/{restaurant['id']}/reviews").json()
    assert saved["reviews"] == data["reviews"]


def test_fetching_twice_creates_no_duplicates(client):
    use_google(client, google_ok())
    first = fetch_places(client).json()
    second = fetch_places(client).json()
    assert len(second["reviews"]) == 2
    assert first["restaurantId"] == second["restaurantId"]
    assert len(client.get("/api/restaurants").json()["restaurants"]) == 1


def test_refetching_does_not_reset_answered_reviews(client):
    # Den vigtigste regel i hele databasedesignet.
    use_google(client, google_ok())
    data = fetch_places(client).json()
    review = by_external_id(data)["r1"]

    assert client.post(f"/api/reviews/{review['id']}/send", json={"finalText": "Tak!"}).json() == {"ok": True}

    again = by_external_id(fetch_places(client).json())["r1"]
    assert again["status"] == "sent"
    assert again["draft"] == "Tak!"


def test_business_type_typed_by_owner_survives_refetch_without_one(client):
    use_google(client, google_ok())
    fetch_places(client, "Café")
    assert fetch_places(client, "").json()["businessType"] == "Café"  # COALESCE, ikke overskrivning


def test_google_review_text_is_stored_verbatim_and_escaping_is_left_to_the_frontend(client):
    use_google(client, google_ok())
    data = fetch_places(client).json()
    assert by_external_id(data)["r2"]["reviewerName"] == "<img src=x onerror=alert(1)>"


def test_old_reviews_google_no_longer_sends_are_kept(client):
    use_google(client, google_ok())
    fetch_places(client)
    fewer = {**PLACE, "reviews": PLACE["reviews"][:1]}
    use_google(client, google_ok(fewer))
    assert len(fetch_places(client).json()["reviews"]) == 2


def test_restaurant_without_reviews(client):
    use_google(client, google_ok({**PLACE, "reviews": []}))
    assert fetch_places(client).json()["reviews"] == []


# ---- fejl fra Google -------------------------------------------------------------


@pytest.mark.parametrize("status, expected_status", [(403, 502), (404, 502), (429, 503), (500, 502)])
def test_google_errors_are_reported_without_leaking_details(client, status, expected_status):
    use_google(client, lambda request: httpx.Response(status, text="INTERN-DETALJE test-google-key"))
    response = fetch_places(client)
    assert response.status_code == expected_status
    assert "INTERN-DETALJE" not in response.text
    assert "test-google-key" not in response.text
    assert client.get("/api/restaurants").json() == {"restaurants": []}  # intet halvt gemt


def test_google_timeout_becomes_502(client):
    def boom(request):
        raise httpx.ConnectTimeout("langsom")

    use_google(client, boom)
    assert fetch_places(client).status_code == 502


def test_google_returning_garbage_becomes_502(client):
    use_google(client, lambda request: httpx.Response(200, text="<html>ikke json</html>"))
    assert fetch_places(client).status_code == 502


def test_search_maps_google_results(client):
    calls = use_google(
        client,
        lambda request: httpx.Response(
            200, json={"places": [{"id": "p1", "displayName": {"text": "Café A"}, "formattedAddress": "Vej 1"}]}
        ),
    )
    response = client.get("/api/places/search", params={"query": "  café  "})
    assert response.json() == {"places": [{"placeId": "p1", "name": "Café A", "address": "Vej 1"}]}
    assert b'"textQuery":"caf' in calls[0].content.replace(b" ", b"")


def test_search_with_no_results(client):
    use_google(client, lambda request: httpx.Response(200, json={}))
    assert client.get("/api/places/search", params={"query": "x"}).json() == {"places": []}


# ---- generér udkast --------------------------------------------------------------


def seed(client):
    use_google(client, google_ok())
    data = fetch_places(client).json()
    return data["restaurantId"], by_external_id(data)


def test_generate_saves_drafts_and_marks_reviews_ready(client):
    restaurant_id, reviews = seed(client)
    claude = use_claude(client, FakeClaude())

    response = client.post(
        "/api/generate",
        json={
            "businessName": "Test Café",
            "businessType": "Café",
            "tone": "varmt",
            "restaurantId": restaurant_id,
            "reviews": [{"id": reviews["r1"]["id"]}, {"id": reviews["r2"]["id"]}],
        },
    )
    assert response.status_code == 200
    results = response.json()["results"]
    assert [r["draft"] for r in results] == ["Udkast nr. 1", "Udkast nr. 2"]  # trimmet
    assert {r["model"] for r in results} == {"test-model"}
    assert results[0]["reviewerName"] == "Ida"

    saved = client.get(f"/api/restaurants/{restaurant_id}/reviews").json()
    assert saved["defaultTone"] == "varmt"  # tonen huskes
    saved_reviews = by_external_id(saved)
    assert saved_reviews["r1"]["status"] == "ready"
    assert saved_reviews["r1"]["draft"] == "Udkast nr. 1"

    # Prompten bygges af det der ligger i databasen.
    assert "Fantastisk kaffe!" in claude.calls[0]["messages"][0]["content"]
    assert claude.calls[0]["model"] == "test-model"


def test_generate_uses_database_text_not_text_sent_by_the_client(client):
    _, reviews = seed(client)
    claude = use_claude(client, FakeClaude())
    client.post(
        "/api/generate",
        json={
            "businessName": "Test Café",
            "reviews": [{"id": reviews["r1"]["id"], "reviewText": "SNYDETEKST", "reviewerName": "SNYD", "rating": 1}],
        },
    )
    prompt = claude.calls[0]["messages"][0]["content"]
    assert "SNYDETEKST" not in prompt and "SNYD<" not in prompt
    assert "Fantastisk kaffe!" in prompt


def test_generate_for_unknown_review_costs_nothing(client):
    seed(client)
    claude = use_claude(client, FakeClaude())
    response = client.post(
        "/api/generate",
        json={"businessName": "x", "reviews": [{"id": "00000000-0000-0000-0000-000000000000"}]},
    )
    assert response.status_code == 404
    assert claude.calls == []  # ingen betalte kald


def test_generate_same_review_twice_only_drafts_once(client):
    _, reviews = seed(client)
    claude = use_claude(client, FakeClaude())
    rid = reviews["r1"]["id"]
    client.post("/api/generate", json={"businessName": "x", "reviews": [{"id": rid}, {"id": rid}]})
    assert len(claude.calls) == 1


def test_generate_keeps_drafts_made_before_a_failure(client):
    restaurant_id, reviews = seed(client)
    use_claude(client, FakeClaude(fail_on_call=2))
    response = client.post(
        "/api/generate",
        json={"businessName": "x", "reviews": [{"id": reviews["r1"]["id"]}, {"id": reviews["r2"]["id"]}]},
    )
    assert response.status_code == 502
    assert response.json() == {"error": "Claude fejlede (test)."}

    saved = by_external_id(client.get(f"/api/restaurants/{restaurant_id}/reviews").json())
    statuses = {saved["r1"]["status"], saved["r2"]["status"]}
    assert statuses == {"ready", "new"}  # første er gemt og betalt for


def test_regenerating_keeps_history_and_shows_newest(client):
    restaurant_id, reviews = seed(client)
    use_claude(client, FakeClaude())
    payload = {"businessName": "x", "reviews": [{"id": reviews["r1"]["id"]}]}
    client.post("/api/generate", json=payload)
    use_claude(client, FakeClaude())
    client.post("/api/generate", json=payload)

    saved = by_external_id(client.get(f"/api/restaurants/{restaurant_id}/reviews").json())
    assert saved["r1"]["draft"] == "Udkast nr. 1"  # nyt FakeClaude tæller forfra
    with psycopg.connect(db_pool.build_conninfo(client.app.state.settings.database_url)) as conn:
        assert conn.execute("SELECT count(*) FROM replies").fetchone()[0] == 2


# ---- send og markér besvaret -----------------------------------------------------


def db_rows(client, query):
    with psycopg.connect(db_pool.build_conninfo(client.app.state.settings.database_url)) as conn:
        return conn.execute(query).fetchall()


def test_send_stores_edited_text_next_to_the_draft(client):
    restaurant_id, reviews = seed(client)
    use_claude(client, FakeClaude())
    rid = reviews["r1"]["id"]
    client.post("/api/generate", json={"businessName": "x", "reviews": [{"id": rid}]})

    assert client.post(f"/api/reviews/{rid}/send", json={"finalText": "  Redigeret svar  "}).status_code == 200

    saved = by_external_id(client.get(f"/api/restaurants/{restaurant_id}/reviews").json())["r1"]
    assert saved["status"] == "sent"
    assert saved["draft"] == "Redigeret svar"  # det sendte vinder over modellens udkast
    ((draft, final, status, model),) = db_rows(client, "SELECT draft_text, final_text, status, model FROM replies")
    assert (draft, final, status, model) == ("Udkast nr. 1", "Redigeret svar", "sent", "test-model")


def test_send_without_a_draft_stores_it_as_handwritten(client):
    _, reviews = seed(client)
    rid = reviews["r2"]["id"]
    client.post(f"/api/reviews/{rid}/send", json={"finalText": "Skrevet i hånden"})
    ((final, status, model),) = db_rows(client, "SELECT final_text, status, model FROM replies")
    assert (final, status, model) == ("Skrevet i hånden", "sent", None)  # model NULL = ikke AI


def test_send_touches_only_the_newest_draft(client):
    _, reviews = seed(client)
    rid = reviews["r1"]["id"]
    payload = {"businessName": "x", "reviews": [{"id": rid}]}
    use_claude(client, FakeClaude())
    client.post("/api/generate", json=payload)
    client.post("/api/generate", json=payload)
    client.post(f"/api/reviews/{rid}/send", json={"finalText": "endeligt"})
    rows = db_rows(client, "SELECT status FROM replies ORDER BY created_at")
    assert rows == [("draft",), ("sent",)]


def test_send_validation(client):
    _, reviews = seed(client)
    rid = reviews["r1"]["id"]
    assert client.post(f"/api/reviews/{rid}/send", json={"finalText": ""}).status_code == 400
    assert client.post(f"/api/reviews/{rid}/send", json={"finalText": "   "}).status_code == 400
    assert client.post(f"/api/reviews/{rid}/send", json={}).status_code == 400
    assert client.post(f"/api/reviews/{rid}/send", json={"finalText": "x" * 4097}).status_code == 400
    assert client.post(f"/api/reviews/{rid}/send", json={"finalText": "x" * 4096}).status_code == 200
    unknown = "00000000-0000-0000-0000-000000000000"
    assert client.post(f"/api/reviews/{unknown}/send", json={"finalText": "x"}).status_code == 404


def test_mark_answered_without_text(client):
    restaurant_id, reviews = seed(client)
    rid = reviews["r1"]["id"]
    assert client.post(f"/api/reviews/{rid}/answered", json={}).json() == {"ok": True}
    saved = by_external_id(client.get(f"/api/restaurants/{restaurant_id}/reviews").json())["r1"]
    assert saved["status"] == "sent" and saved["draft"] == ""
    assert db_rows(client, "SELECT count(*) FROM replies") == [(0,)]  # ingen svartekst gemt


def test_mark_answered_unknown_review(client):
    assert client.post("/api/reviews/00000000-0000-0000-0000-000000000000/answered", json={}).status_code == 404


def test_unknown_restaurant_is_404(client):
    assert client.get("/api/restaurants/00000000-0000-0000-0000-000000000000/reviews").status_code == 404


def test_restaurant_list_newest_first(client):
    use_google(client, google_ok())
    fetch_places(client)
    use_google(client, google_ok({**PLACE, "id": "ChIJother", "displayName": {"text": "Andet sted"}}))
    client.get("/api/places/reviews", params={"placeId": "ChIJother"})
    names = [r["name"] for r in client.get("/api/restaurants").json()["restaurants"]]
    assert names == ["Andet sted", "Test Café"]


def test_sql_injection_attempts_are_inert(client):
    seed(client)
    evil = "'; DROP TABLE reviews; --"
    use_google(client, google_ok({**PLACE, "id": "ChIJevil", "displayName": {"text": evil}, "reviews": []}))
    client.get("/api/places/reviews", params={"placeId": "ChIJevil", "businessType": evil})
    names = [r["name"] for r in client.get("/api/restaurants").json()["restaurants"]]
    assert evil in names  # gemt som ren tekst
    assert db_rows(client, "SELECT count(*) FROM reviews") == [(2,)]  # tabellen findes stadig


def test_transaction_rolls_back_the_whole_google_fetch_on_failure(client):
    # Anden anmeldelse bryder CHECK (rating BETWEEN 1 AND 5). Parsing i places_service
    # filtrerer sådan noget fra, så fejlen tvinges ind direkte i model-laget.
    from types import SimpleNamespace

    from app.models import restaurants, reviews

    async def run():
        restaurant = await restaurants.upsert_by_place_id(
            google_place_id="ChIJrollback", name="R", business_type=None, address=None,
            google_rating=None, google_rating_count=None,
        )
        good = SimpleNamespace(external_id="ok", reviewer_name="A", rating=5, review_text="t", published_at=None)
        bad = SimpleNamespace(external_id="bad", reviewer_name="B", rating=99, review_text="t", published_at=None)
        with pytest.raises(psycopg.errors.CheckViolation):
            await reviews.upsert_many(restaurant["id"], [good, bad])
        return await reviews.list_by_restaurant(restaurant["id"])

    # Køres i appens egen event loop, hvor databasepoolen lever.
    assert client.portal.call(run) == []  # den gode blev ikke gemt alene
