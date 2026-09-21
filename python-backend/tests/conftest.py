"""Fælles opsætning til alle tests (pytest finder denne fil automatisk).

Database-testene kører i et MIDLERTIDIGT schema med tilfældigt navn i Neon. Det
oprettes før testene og slettes bagefter, så de rigtige tabeller aldrig røres.
Google og Claude er falske, så testene er gratis.
"""

import asyncio
import uuid
from types import SimpleNamespace

import httpx
import psycopg
import pytest
from fastapi.testclient import TestClient
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict, make_conninfo

from app.core.config import REPO_DIR, Settings, load_settings
from app.db import migrate as migrate_module
from app.db import pool as db_pool
from app.main import create_app

PUBLIC_DIR = REPO_DIR / "public"


def make_settings(**overrides) -> Settings:
    """Laver testindstillinger med falske nøgler. Enkelte værdier kan overskrives."""
    values = dict(
        port=3000,
        database_url=None,
        anthropic_api_key="test-anthropic-key",
        google_places_api_key="test-google-key",
        claude_model="test-model",
        allowed_hosts=("localhost",),
        enable_docs=False,
        public_dir=PUBLIC_DIR,
    )
    values.update(overrides)
    return Settings(**values)


@pytest.fixture
def unit_client() -> TestClient:
    """En testklient UDEN database. Bruges kun til at teste det der sker før databasen rammes."""
    app = create_app(make_settings())
    # Uden database starter lifespan ikke, så klienterne sættes her i hånden.
    # Ingen af disse tests kalder dem.
    app.state.http = httpx.AsyncClient()
    app.state.anthropic = FakeClaude()
    return TestClient(app, base_url="http://localhost")


@pytest.fixture(scope="module")
def isolated_db_url():
    """Opretter et midlertidigt schema og giver en forbindelsesstreng der KUN peger på det.

    Schemaet slettes igen når testene er færdige. Springer testene over, hvis
    DATABASE_URL ikke er sat.
    """
    real_url = load_settings().database_url
    if not real_url:
        pytest.skip("DATABASE_URL er ikke sat — springer databasetestene over.")

    schema = "test_" + uuid.uuid4().hex[:12]
    params = conninfo_to_dict(real_url)
    # Neons "pooler"-adresse understøtter ikke search_path. Den direkte adresse gør,
    # og det er den samme database.
    params["host"] = params["host"].replace("-pooler", "")

    admin_conninfo = db_pool.build_conninfo(make_conninfo(**params))
    with psycopg.connect(admin_conninfo, autocommit=True) as admin:
        admin.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))

    params["options"] = f"-c search_path={schema}"
    test_url = make_conninfo(**params)

    # SIKKERHEDSTJEK: er forbindelsen virkelig rettet mod testschemaet? Hvis ikke,
    # ville testene skrive i de rigtige tabeller, så vi stopper med det samme.
    with psycopg.connect(db_pool.build_conninfo(test_url)) as check:
        current = check.execute("SELECT current_schema()").fetchone()[0]
    if current != schema:
        with psycopg.connect(admin_conninfo, autocommit=True) as admin:
            admin.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema)))
        pytest.fail(f"Testforbindelsen peger på {current!r}, ikke {schema!r}. Afbryder.")

    yield test_url

    with psycopg.connect(admin_conninfo, autocommit=True) as admin:
        admin.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema)))


async def _run_migrations(test_url: str) -> tuple[int, int]:
    """Kører migrationerne to gange mod testschemaet. Returnerer hvor mange der kørte hver gang."""
    await db_pool.init_pool(db_pool.build_conninfo(test_url))
    try:
        first = await migrate_module.migrate()
        second = await migrate_module.migrate()
        return first, second
    finally:
        await db_pool.close_pool()


@pytest.fixture(scope="module")
def migration_result(isolated_db_url):
    """Opretter tabellerne i testschemaet og giver (første kørsel, anden kørsel)."""
    return asyncio.run(_run_migrations(isolated_db_url))


@pytest.fixture(scope="module")
def client(isolated_db_url, migration_result):
    """En testklient koblet til den rigtige app og testdatabasen."""
    app = create_app(make_settings(database_url=isolated_db_url))
    with TestClient(app, base_url="http://localhost") as test_client:
        yield test_client


@pytest.fixture(autouse=True)
def clean_tables(request):
    """Tømmer tabellerne før hver databasetest, så testene ikke påvirker hinanden."""
    if "client" not in request.fixturenames:
        yield
        return
    url = request.getfixturevalue("isolated_db_url")
    request.getfixturevalue("migration_result")  # tabellerne skal findes før de tømmes
    with psycopg.connect(db_pool.build_conninfo(url), autocommit=True) as conn:
        conn.execute("TRUNCATE restaurants, reviews, replies CASCADE")
    yield


# ---- Falske eksterne tjenester ------------------------------------------------

# Et eksempel på hvad Google svarer for et sted med to anmeldelser. Den ene
# anmelder har bevidst et ondsindet navn, så vi kan se det behandles som ren tekst.
PLACE = {
    "id": "ChIJtest",
    "displayName": {"text": "Test Café"},
    "formattedAddress": "Testvej 1, 2200 København",
    "rating": 4.4,
    "userRatingCount": 120,
    "reviews": [
        {
            "name": "places/ChIJtest/reviews/r1",
            "authorAttribution": {"displayName": "Ida"},
            "rating": 5,
            "text": {"text": "Fantastisk kaffe!"},
            "publishTime": "2026-09-01T10:00:00.123456789Z",
        },
        {
            "name": "places/ChIJtest/reviews/r2",
            "authorAttribution": {"displayName": "<img src=x onerror=alert(1)>"},
            "rating": 1,
            "text": {"text": "Elendig service."},
            "publishTime": "2026-08-01T10:00:00Z",
        },
    ],
}


def use_google(client: TestClient, handler) -> list[httpx.Request]:
    """Lader appen kalde en falsk Google, som svarer med `handler`. Returnerer listen af kald der blev lavet."""
    calls: list[httpx.Request] = []

    def recording(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return handler(request)

    client.app.state.http = httpx.AsyncClient(transport=httpx.MockTransport(recording))
    return calls


def google_ok(place: dict = PLACE):
    """Giver en falsk Google der altid svarer OK med det givne sted."""
    return lambda request: httpx.Response(200, json=place)


class FakeClaude:
    """En falsk Claude. Gemmer hvilke kald den fik, og svarer med "Udkast nr. 1", "Udkast nr. 2" osv."""

    def __init__(self, fail_on_call: int | None = None):
        self.calls: list[dict] = []
        self.fail_on_call = fail_on_call  # fx 2 = lad kald nummer 2 fejle
        self.messages = self  # så koden kan skrive client.messages.create(...)

    async def create(self, **kwargs):
        """Ligner Claudes messages.create(), men svarer med et fast udkast (eller fejler)."""
        from app.core.errors import UpstreamError

        self.calls.append(kwargs)
        if self.fail_on_call == len(self.calls):
            raise UpstreamError("Claude fejlede (test).")
        n = len(self.calls)
        return SimpleNamespace(
            content=[SimpleNamespace(type="text", text=f"  Udkast nr. {n}  ")],
            stop_reason="end_turn",
        )

    async def close(self):
        """Gør ingenting (den rigtige klient skal lukkes, så den falske skal kunne det også)."""


def use_claude(client: TestClient, fake: FakeClaude) -> FakeClaude:
    """Lader appen bruge den givne falske Claude i stedet for den rigtige."""
    client.app.state.anthropic = fake
    return fake
