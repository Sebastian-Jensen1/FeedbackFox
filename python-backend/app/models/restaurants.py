"""Databasen: tabellen `restaurants` (steder).

Al SQL for restauranter står her og kun her. Hver funktion kører én forespørgsel.
"""

from uuid import UUID

from app.db.pool import fetch_all, fetch_one, fetch_one_required


async def upsert_by_place_id(
    *,
    google_place_id: str,
    name: str,
    business_type: str | None,
    address: str | None,
    google_rating: float | None,
    google_rating_count: int | None,
) -> dict:
    """Opretter stedet, eller opdaterer det hvis vi kender det i forvejen. Returnerer rækken.

    "Upsert" = update + insert. Vi henter samme sted igen og igen, og navn, adresse
    og Google-score kan have ændret sig, så vi må ikke lave et nyt sted hver gang.
    """
    return await fetch_one_required(
        """
        INSERT INTO restaurants
          (google_place_id, name, business_type, address, google_rating, google_rating_count)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT (google_place_id) DO UPDATE SET
          name                = EXCLUDED.name,
          address             = EXCLUDED.address,
          google_rating       = EXCLUDED.google_rating,
          google_rating_count = EXCLUDED.google_rating_count,
          -- COALESCE = "brug den nye værdi, men behold den gamle hvis den nye er tom".
          -- Branchen skriver ejeren selv, og Google sender den ikke med.
          business_type       = COALESCE(EXCLUDED.business_type, restaurants.business_type)
        RETURNING *
        """,
        (
            google_place_id,
            name,
            business_type or None,
            address or None,
            google_rating,
            google_rating_count,
        ),
    )


async def list_all() -> list[dict]:
    """Henter alle steder, det senest brugte først."""
    return await fetch_all("SELECT * FROM restaurants ORDER BY updated_at DESC")


async def find_by_id(restaurant_id: UUID) -> dict | None:
    """Henter ét sted ud fra dets id, eller None hvis det ikke findes."""
    return await fetch_one("SELECT * FROM restaurants WHERE id = %s", (restaurant_id,))


async def update_default_tone(restaurant_id: UUID, tone: str | None) -> dict | None:
    """Gemmer den tone ejeren har valgt, så den huskes til næste gang."""
    return await fetch_one(
        "UPDATE restaurants SET default_tone = %s WHERE id = %s RETURNING *",
        (tone or None, restaurant_id),
    )
