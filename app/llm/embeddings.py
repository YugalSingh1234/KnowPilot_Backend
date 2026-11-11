import logging
import time

import httpcore
import httpx

from app.config import get_settings
from app.errors import AppError
from app.llm.client import get_client

log = logging.getLogger("knowpilot.llm")

BATCH_SIZE = 50
RETRIES = 2  # retries after the first attempt
BACKOFF_SECONDS = 1.0


def llm_unavailable() -> AppError:
    return AppError(
        "llm_unavailable", "The AI service is temporarily unavailable. Please try again.", 503
    )


def _retryable(e: Exception) -> bool:
    from google.genai import errors

    if isinstance(e, errors.APIError):
        return e.code == 429 or (e.code or 0) >= 500
    # timeouts, connection resets (google-genai can surface raw httpcore errors too)
    return isinstance(e, (httpx.TransportError, httpcore.TimeoutException, httpcore.NetworkError))


def call_with_retry(fn):
    """Run fn(); retry twice on 429/5xx/timeouts, then raise llm_unavailable (503)."""
    for attempt in range(RETRIES + 1):
        try:
            return fn()
        except Exception as e:
            if not _retryable(e):
                log.error("Gemini call failed (not retryable): %s", type(e).__name__)
                raise llm_unavailable() from e
            if attempt == RETRIES:
                log.error("Gemini call failed after retries: %s", type(e).__name__)
                raise llm_unavailable() from e
            time.sleep(BACKOFF_SECONDS * 2**attempt)


def _embed(texts: list[str], task_type: str) -> list[list[float]]:
    s = get_settings()
    import numpy as np
    from google.genai import types

    cfg = types.EmbedContentConfig(task_type=task_type, output_dimensionality=s.EMBED_DIM)
    resp = call_with_retry(
        lambda: get_client().models.embed_content(model=s.GEMINI_EMBED_MODEL, contents=texts, config=cfg)
    )
    vecs = np.array([e.values for e in resp.embeddings], dtype=float)
    norms = np.linalg.norm(vecs, axis=1, keepdims=True)
    return (vecs / np.where(norms == 0, 1, norms)).tolist()


def embed_documents(texts: list[str]) -> list[list[float]]:
    out: list[list[float]] = []
    for i in range(0, len(texts), BATCH_SIZE):
        out.extend(_embed(texts[i : i + BATCH_SIZE], "RETRIEVAL_DOCUMENT"))
    return out


def embed_query(text: str) -> list[float]:
    return _embed([text], "RETRIEVAL_QUERY")[0]
