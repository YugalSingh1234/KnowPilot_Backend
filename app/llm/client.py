from functools import lru_cache

from google import genai
from google.genai import types

from app.config import get_settings

TIMEOUT_MS = 30_000


@lru_cache
def get_client() -> genai.Client:
    """One shared client; 30-second request timeout."""
    return genai.Client(
        api_key=get_settings().GEMINI_API_KEY,
        http_options=types.HttpOptions(timeout=TIMEOUT_MS),
    )
