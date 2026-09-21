"""Skemaer for søgning efter steder (GET /api/places/search)."""

from app.schemas.common import CamelModel


class PlaceSummary(CamelModel):
    """Ét søgeresultat: id, navn og adresse."""

    place_id: str
    name: str
    address: str


class PlaceSearchResponse(CamelModel):
    """Svar på GET /api/places/search."""

    places: list[PlaceSummary]
