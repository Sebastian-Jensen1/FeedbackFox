"""Skemaer for restauranter og anmeldelser: hvad API'et svarer med, og hvad "Send" modtager.

Svarskemaerne bestemmer præcis hvilke felter der forlader serveren. Et felt der ikke
står her, bliver aldrig sendt til browseren.
"""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field

from app.schemas.common import CamelModel

# Googles egen grænse for længden af et svar på en anmeldelse.
MAX_REPLY_LENGTH = 4096


class ClientReview(CamelModel):
    """Én anmeldelse, som frontenden viser den. status: new = ingen udkast, ready = udkast, sent = besvaret."""

    id: UUID
    external_id: str
    reviewer_name: str
    rating: int | None
    review_text: str
    published_at: datetime | None
    status: Literal["new", "ready", "sent"]
    draft: str


class RestaurantSummary(CamelModel):
    """Et sted i listen over gemte steder."""

    id: UUID
    name: str
    business_type: str
    address: str
    default_tone: str


class RestaurantListResponse(CamelModel):
    """Svar på GET /api/restaurants."""

    restaurants: list[RestaurantSummary]


class RestaurantReviewsResponse(CamelModel):
    """Svar på GET /api/restaurants/{id}/reviews: stedet og alle dets anmeldelser."""

    restaurant_id: UUID
    business_name: str
    business_type: str
    default_tone: str
    reviews: list[ClientReview]


class PlaceReviewsResponse(RestaurantReviewsResponse):
    """Svar på GET /api/places/reviews: som ovenfor, plus Googles score og adresse."""

    address: str
    rating: float | None
    user_rating_count: int | None


class SendReplyRequest(CamelModel):
    """Det browseren sender til "Send": den tekst ejeren endte med (må ikke være tom)."""

    final_text: str = Field(min_length=1, max_length=MAX_REPLY_LENGTH)


class OkResponse(CamelModel):
    """Svaret {"ok": true}, når en handling er lykkedes."""

    ok: bool = True
