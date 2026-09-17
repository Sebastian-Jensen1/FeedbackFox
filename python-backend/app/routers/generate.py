from app.core.config import ANTHROPIC_API_KEY, GOOGLE_PLACES_API_KEY
from fastapi import FastAPI

routes = FastAPI

antrophic = ANTHROPIC_API_KEY

@routes.post("/generate")
    

