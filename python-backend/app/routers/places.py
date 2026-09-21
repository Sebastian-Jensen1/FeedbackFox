"""Endpoints der handler om Google: søg efter et sted, og hent dets anmeldelser.

Et endpoint er en adresse browseren kan kalde, fx GET /api/places/search.
Routerne gør selv meget lidt. De tjekker input og kalder services og models.
"""

import re
from dataclasses import asdict

import httpx
from fastapi import APIRouter, Depends, Query

from app.core.deps import get_http, get_places_key
from app.core.errors import ApiError
from app.models import restaurants, reviews
from app.schemas.places import PlaceSearchResponse
from app.schemas.reviews import PlaceReviewsResponse
from app.services import places_service

router = APIRouter()

# Et Google place_id består kun af bogstaver, tal, "_" og "-". Alt andet afvises,
# før det kommer i nærheden af en adresse vi bygger til Google.
PLACE_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,300}$")


@router.get("/places/search", response_model=PlaceSearchResponse)
async def search_places(
    query: str = Query("", max_length=200),
    api_key: str = Depends(get_places_key),
    http: httpx.AsyncClient = Depends(get_http),
):
    """GET /api/places/search?query=...  Søger efter steder hos Google. Gemmer ikke noget."""
    query = query.strip()
    if not query:
        raise ApiError(400, "Mangler søgeord (query).")

    places = await places_service.search_places(http, query, api_key)
    return {"places": [asdict(place) for place in places]}


@router.get("/places/reviews", response_model=PlaceReviewsResponse)
async def place_reviews(
    place_id: str = Query("", alias="placeId", max_length=300),
    business_type: str = Query("", alias="businessType", max_length=100),
    api_key: str = Depends(get_places_key),
    http: httpx.AsyncClient = Depends(get_http),
):
    """GET /api/places/reviews?placeId=...  Henter fra Google, gemmer i databasen og svarer.

    Svaret kommer fra databasen og ikke direkte fra Google. Kun sådan får frontenden
    de rigtige id'er og den status og de udkast der allerede findes på anmeldelserne.
    """
    place_id = place_id.strip()
    if not place_id:
        raise ApiError(400, "Mangler placeId.")
    if not PLACE_ID_PATTERN.fullmatch(place_id):
        raise ApiError(400, "Ugyldigt placeId.")

    # 1. Hent stedet og anmeldelserne fra Google.
    details = await places_service.get_place_details(http, place_id, api_key)

    # 2. Gem (eller opdater) stedet og anmeldelserne i databasen.
    restaurant = await restaurants.upsert_by_place_id(
        google_place_id=place_id,
        name=details.business_name,
        business_type=business_type.strip(),
        address=details.address,
        google_rating=details.rating,
        google_rating_count=details.user_rating_count,
    )
    await reviews.upsert_many(restaurant["id"], details.reviews)

    # 3. Læs ALT tilbage fra databasen, også ældre anmeldelser som Google ikke
    #    længere sender med i sine fem.
    rows = await reviews.list_by_restaurant(restaurant["id"])

    return {
        "restaurant_id": restaurant["id"],
        "business_name": restaurant["name"],
        "business_type": restaurant["business_type"] or "",
        "address": restaurant["address"] or "",
        "rating": restaurant["google_rating"],
        "user_rating_count": restaurant["google_rating_count"],
        "default_tone": restaurant["default_tone"] or "",
        "reviews": [reviews.to_client_review(row) for row in rows],
    }
