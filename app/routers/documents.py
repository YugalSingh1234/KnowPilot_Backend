import logging
import uuid

from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.db import get_db
from app.errors import AppError
from app.models import Chunk, Document, Organization
from app.security import get_current_org
from app.services import ingest, storage

log = logging.getLogger("knowpilot.documents")
router = APIRouter(prefix="/api/documents", tags=["documents"])


def _out(doc: Document, chunk_count: int) -> dict:
    return {
        "id": str(doc.id), "filename": doc.filename, "page_count": doc.page_count,
        "size_bytes": doc.size_bytes, "status": doc.status, "chunk_count": chunk_count,
        "created_at": doc.created_at.isoformat(),
    }


@router.post("", status_code=201)
async def upload_document(
    file: UploadFile = File(...),
    org: Organization = Depends(get_current_org),
    db: Session = Depends(get_db),
):
    filename = (file.filename or "").strip()
    # Starlette has already spooled the upload; check type and size before loading it into memory.
    head = await file.read(5)
    size = file.size if file.size is not None else len(head + await file.read())
    ingest.check_file(filename, head, size)
    await file.seek(0)
    data = await file.read()
    # ingest blocks (DB, storage, Gemini); keep it off the event loop
    doc = await run_in_threadpool(ingest.ingest, db, org.id, filename, data)
    count = db.scalar(select(func.count()).select_from(Chunk).where(Chunk.org_id == org.id, Chunk.document_id == doc.id))
    return _out(doc, count)


@router.get("")
def list_documents(org: Organization = Depends(get_current_org), db: Session = Depends(get_db)):
    counts = (
        select(Chunk.document_id, func.count().label("n"))
        .where(Chunk.org_id == org.id)
        .group_by(Chunk.document_id)
        .subquery()
    )
    rows = db.execute(
        select(Document, func.coalesce(counts.c.n, 0))
        .outerjoin(counts, counts.c.document_id == Document.id)
        .where(Document.org_id == org.id)
        .order_by(Document.created_at)
    ).all()
    return {
        "documents": [_out(d, n) for d, n in rows],
        "limits": {
            "max_documents": ingest.MAX_DOCUMENTS, "max_pages": ingest.MAX_PAGES,
            "max_mb": ingest.MAX_MB, "used_documents": len(rows),
        },
    }


@router.delete("/{document_id}", status_code=204)
def delete_document(
    document_id: uuid.UUID,
    org: Organization = Depends(get_current_org),
    db: Session = Depends(get_db),
):
    doc = db.scalar(select(Document).where(Document.id == document_id, Document.org_id == org.id))
    if doc is None:  # same answer whether it doesn't exist or belongs to another org
        raise AppError("not_found", "Document not found.", 404)
    path = doc.storage_path
    db.delete(doc)  # chunks go with it (on delete cascade)
    db.commit()
    try:
        storage.delete(path)
    except Exception:
        log.warning("Could not remove storage file %s", path)
