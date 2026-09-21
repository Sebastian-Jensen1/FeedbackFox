"""Endpoint der får Claude til at skrive udkast: POST /api/generate."""

import anthropic
from fastapi import APIRouter, Depends

from app.core.config import Settings
from app.core.deps import get_claude, get_settings
from app.core.errors import ApiError
from app.models import replies, restaurants, reviews
from app.schemas.generate import GenerateRequest, GenerateResponse
from app.services import claude_service

router = APIRouter()


@router.post("/generate", response_model=GenerateResponse)
async def generate(
    body: GenerateRequest,
    claude: anthropic.AsyncAnthropic = Depends(get_claude),
    settings: Settings = Depends(get_settings),
):
    """POST /api/generate  Skriver et udkast til hver af de valgte anmeldelser og gemmer dem."""
    # Samme anmeldelse to gange ville give to betalte udkast, så dubletter fjernes
    # (rækkefølgen bevares).
    review_ids = list(dict.fromkeys(item.id for item in body.reviews))

    # Slå ALLE anmeldelser op FØR vi kalder Claude. Ellers kunne vi nå at betale
    # for udkast der bagefter ikke kan gemmes, fordi anmeldelsen ikke findes.
    found = await reviews.find_many(review_ids)
    if len(found) != len(review_ids):
        raise ApiError(404, "En eller flere anmeldelser findes ikke.")

    # Husk den valgte tone til næste gang.
    if body.restaurant_id and body.tone:
        await restaurants.update_default_tone(body.restaurant_id, body.tone)

    results = []
    for review_id in review_ids:
        # Anmeldelsens indhold kommer fra databasen, ikke fra det browseren sendte.
        review = found[review_id]
        reviewer_name = review["reviewer_name"] or ""
        review_text = review["review_text"] or ""

        draft = await claude_service.draft_review_reply(
            claude,
            model=settings.claude_model,
            business_name=body.business_name,
            business_type=body.business_type,
            reviewer_name=reviewer_name,
            rating=review["rating"],
            review_text=review_text,
            tone=body.tone,
        )

        # Udkastet gemmes med det samme, ét ad gangen. Fejler nummer 4 af 5, er de
        # første tre stadig gemt (og betalt for), så de går ikke tabt.
        await replies.insert_draft(
            review_id=review_id,
            draft_text=draft.text,
            tone=body.tone,
            model=draft.model,
        )

        results.append(
            {
                "id": review_id,
                "reviewer_name": reviewer_name,
                "rating": review["rating"],
                "review_text": review_text,
                "draft": draft.text,
                "model": draft.model,
            }
        )

    return {"results": results}
