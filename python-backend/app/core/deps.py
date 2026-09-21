"""Afhængigheder: ting som routerne får leveret, i stedet for selv at skulle finde dem.

En route skriver fx `claude = Depends(get_claude)`, og FastAPI kalder så
`get_claude` og giver den resultatet.
"""

import anthropic
import httpx
from fastapi import Depends, Request

from app.core.config import Settings
from app.core.errors import ApiError


def get_settings(request: Request) -> Settings:
    """Giver indstillingerne (dem der blev lavet da appen startede)."""
    return request.app.state.settings


def get_http(request: Request) -> httpx.AsyncClient:
    """Giver den delte HTTP-klient, som bruges til at kalde Google."""
    return request.app.state.http


def get_claude(request: Request) -> anthropic.AsyncAnthropic:
    """Giver klienten til Claude. Fejler med en tydelig besked hvis ANTHROPIC_API_KEY mangler."""
    client = request.app.state.anthropic
    if client is None:
        raise ApiError(500, "Mangler ANTHROPIC_API_KEY. Opret en .env-fil ud fra .env.example.")
    return client


def get_places_key(settings: Settings = Depends(get_settings)) -> str:
    """Giver Google-nøglen. Fejler med en tydelig besked hvis GOOGLE_PLACES_API_KEY mangler."""
    if not settings.google_places_api_key:
        raise ApiError(500, "Mangler GOOGLE_PLACES_API_KEY i .env.")
    return settings.google_places_api_key
