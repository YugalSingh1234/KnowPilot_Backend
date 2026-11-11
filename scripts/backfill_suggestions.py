"""Fill suggested_questions for ready documents that don't have any yet.

    python scripts/backfill_suggestions.py

Rebuilds each document's text from its stored chunks (in page order) and asks Gemini once per
document. Safe to re-run: documents that already have suggestions are skipped.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select  # noqa: E402

from app.db import SessionLocal  # noqa: E402
from app.llm.generate import suggest_questions  # noqa: E402
from app.models import Chunk, Document  # noqa: E402

with SessionLocal() as db:
    docs = db.scalars(select(Document).where(Document.status == "ready").order_by(Document.created_at)).all()
    for doc in docs:
        if doc.suggested_questions:
            print(f"skip  {doc.filename} (has {len(doc.suggested_questions)})")
            continue
        text = "\n\n".join(db.scalars(
            select(Chunk.content)
            .where(Chunk.org_id == doc.org_id, Chunk.document_id == doc.id)
            .order_by(Chunk.page_number, Chunk.chunk_index)
        ))
        doc.suggested_questions = suggest_questions(text)
        db.commit()
        print(f"done  {doc.filename}: {doc.suggested_questions}")
