"""Endpoints for gemte steder og anmeldelser: liste, "Send" og "Markér som besvaret".

Når en parameter er skrevet som `UUID`, afviser FastAPI selv alt der ikke er et gyldigt
id, med fejlen 400, før databasen bliver rørt.
"""

from uuid import UUID

from fastapi import APIRouter

from app.core.errors import ApiError
from app.models import replies, restaurants, reviews
from app.schemas.reviews import (
    OkResponse,
    RestaurantListResponse,
    RestaurantReviewsResponse,
    SendReplyRequest,
)

router = APIRouter()


@router.get("/restaurants", response_model=RestaurantListResponse)
async def list_restaurants():
    """GET /api/restaurants  Alle gemte steder. Siden kalder den når den åbnes, så den kan genoptage arbejdet."""
    rows = await restaurants.list_all()
    return {
        "restaurants": [
            {
                "id": row["id"],
                "name": row["name"],
                "business_type": row["business_type"] or "",
                "address": row["address"] or "",
                "default_tone": row["default_tone"] or "",
            }
            for row in rows
        ]
    }


@router.get("/restaurants/{restaurant_id}/reviews", response_model=RestaurantReviewsResponse)
async def restaurant_reviews(restaurant_id: UUID):
    """GET /api/restaurants/{id}/reviews  Ét sted med alle dets anmeldelser. 404 hvis stedet ikke findes."""
    restaurant = await restaurants.find_by_id(restaurant_id)
    if restaurant is None:
        raise ApiError(404, "Restauranten findes ikke.")

    rows = await reviews.list_by_restaurant(restaurant_id)
    return {
        "restaurant_id": restaurant["id"],
        "business_name": restaurant["name"],
        "business_type": restaurant["business_type"] or "",
        "default_tone": restaurant["default_tone"] or "",
        "reviews": [reviews.to_client_review(row) for row in rows],
    }


@router.post("/reviews/{review_id}/send", response_model=OkResponse)
async def send_reply(review_id: UUID, body: SendReplyRequest):
    """POST /api/reviews/{id}/send  Gemmer den tekst ejeren sendte, og flytter anmeldelsen til "Besvarede".

    Teksten kan være redigeret i forhold til Claudes udkast, og det er den redigerede
    tekst der gemmes.
    """
    if await reviews.find_by_id(review_id) is None:
        raise ApiError(404, "Anmeldelsen findes ikke.")

    await replies.mark_sent(review_id, body.final_text)
    return OkResponse()


@router.post("/reviews/{review_id}/answered", response_model=OkResponse)
async def mark_answered(review_id: UUID):
    """POST /api/reviews/{id}/answered  Markerer som besvaret uden svartekst (ejeren svarede selv på Google)."""
    if await reviews.mark_answered(review_id) is None:
        raise ApiError(404, "Anmeldelsen findes ikke.")
    return OkResponse()
