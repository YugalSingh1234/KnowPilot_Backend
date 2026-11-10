"""Answerability gate: decide from retrieval scores alone whether the LLM should be called."""
from app.config import get_settings

KEYWORD_ASSISTED_MIN = 0.45


def is_answerable(chunks: list[dict]) -> dict:
    if not chunks:
        return {"answerable": False, "confidence": 0.0}
    top = max(chunks, key=lambda c: c["vector_score"])
    score = top["vector_score"]
    has_keyword = any(c["keyword_score"] > 0 for c in chunks)
    answerable = score >= get_settings().GATE_MIN_SIMILARITY or (score >= KEYWORD_ASSISTED_MIN and has_keyword)
    return {"answerable": answerable, "confidence": round(max(0.0, min(1.0, score)), 3)}
