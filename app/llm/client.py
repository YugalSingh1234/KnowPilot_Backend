from functools import lru_cache

from app.config import get_settings

TIMEOUT_MS = 30_000


@lru_cache
def get_client():
    """One shared genai.Client; 30-second request timeout. Imported lazily: serverless cold starts
    for login/health must not pay for google-genai."""
    from google import genai
    from google.genai import types

    return genai.Client(
        api_key=get_settings().GEMINI_API_KEY,
        http_options=types.HttpOptions(timeout=TIMEOUT_MS),
    )
