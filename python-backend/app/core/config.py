import os
from dotenv import load_dotenv

load_dotenv()
os.getenv("PORT")

PORT = int(os.getenv("PORT", 3000))
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
GOOGLE_PLACES_API_KEY = os.getenv("GOOGLE_PLACES_API_KEY")
