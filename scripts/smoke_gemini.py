"""Smoke test: one embedding and one tiny chat call."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import get_settings  # noqa: E402
from app.llm.client import get_client  # noqa: E402
from app.llm.embeddings import call_with_retry, embed_query  # noqa: E402

vec = embed_query("merit scholarship eligibility")
print("embedding length:", len(vec))
reply = call_with_retry(
    lambda: get_client().models.generate_content(
        model=get_settings().GEMINI_CHAT_MODEL, contents="Reply with OK"
    )
)
print("chat reply:", reply.text)
