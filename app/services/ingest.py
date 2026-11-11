"""PDF validation, page-wise chunking and indexing."""
import logging
import re
import uuid

from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.errors import AppError
from app.llm.embeddings import embed_documents
from app.llm.generate import suggest_questions
from app.models import Chunk, Document, Organization
from app.services import storage

log = logging.getLogger("knowpilot.ingest")

MAX_DOCUMENTS = 10
MAX_PAGES = 20
MAX_MB = 10
MAX_BYTES = MAX_MB * 1024 * 1024
MIN_TEXT_CHARS = 50
MAX_TEXT_CHARS = 300_000  # ~15k chars/page; caps chunk count and embedding cost
CHUNK_SIZE = 900
CHUNK_OVERLAP = 150
MIN_CHUNK_CHARS = 40

_SENTENCE_END = re.compile(r"(?<=[.!?।])\s+")


def storage_path(org_id, document_id) -> str:
    return f"{org_id}/{document_id}.pdf"


# ---------- chunking ----------

def _units(text: str) -> list[str]:
    """Paragraphs split into sentences; anything still longer than CHUNK_SIZE is hard-split."""
    out = []
    for para in re.split(r"\n\s*\n", text):
        para = " ".join(para.split())
        for sent in _SENTENCE_END.split(para):
            step = CHUNK_SIZE - CHUNK_OVERLAP
            out.extend(sent[i : i + CHUNK_SIZE] for i in range(0, len(sent), step) if sent[i : i + CHUNK_SIZE])
    return out


def chunk_page(text: str) -> list[str]:
    """~CHUNK_SIZE chars per chunk, ~CHUNK_OVERLAP chars of trailing sentences repeated, one page only."""
    chunks, cur = [], []
    for unit in _units(text):
        if cur and len(" ".join(cur + [unit])) > CHUNK_SIZE:
            chunks.append(" ".join(cur))
            tail = []  # carry whole trailing sentences up to CHUNK_OVERLAP chars
            for s in reversed(cur):
                if len(" ".join([s] + tail)) > CHUNK_OVERLAP:
                    break
                tail.insert(0, s)
            cur = tail
        cur.append(unit)
    if cur:
        chunks.append(" ".join(cur))
    return [c for c in chunks if len(c) >= MIN_CHUNK_CHARS]


MARGIN = 0.07  # top/bottom 7% of the page height is where running headers and footers sit


def extract_pages(pdf) -> list[str]:
    """Page texts without running headers/footers: text blocks lying in the top or bottom MARGIN that
    repeat (digits ignored) on at least 60% of pages. Body text is never touched, even if it repeats.
    ponytail: geometric heuristic; a header placed lower than 7% of the page height survives."""
    key = lambda t: re.sub(r"\d+", "#", " ".join(t.split()).lower())  # noqa: E731
    pages = []
    for page in pdf:
        top, bottom = page.rect.height * MARGIN, page.rect.height * (1 - MARGIN)
        pages.append([(b[4], b[3] <= top or b[1] >= bottom)
                      for b in page.get_text("blocks", sort=True) if b[6] == 0 and b[4].strip()])
    seen: dict[str, int] = {}
    for blocks in pages:
        for k in {key(t) for t, in_margin in blocks if in_margin}:
            seen[k] = seen.get(k, 0) + 1
    threshold = max(2, -(-len(pages) * 6 // 10))  # ceil(60%), and never for a 1-page PDF
    repeated = {k for k, n in seen.items() if n >= threshold}
    return ["\n".join(t for t, in_margin in blocks if not (in_margin and key(t) in repeated)) for blocks in pages]


# ---------- validation ----------

def check_file(filename: str, head: bytes, size: int) -> None:
    """Checks 1-2: cheap, done before the whole file is read into memory."""
    if not filename.lower().endswith(".pdf") or not head.startswith(b"%PDF"):
        raise AppError("invalid_pdf", "Only PDF files are allowed.", 400)
    if size > MAX_BYTES:
        raise AppError("file_too_large", f"File is {size / 1024 / 1024:.1f} MB; the limit is {MAX_MB} MB.", 413)


def validate_pdf(db: Session, org_id, filename: str, data: bytes) -> list[str]:
    """Run checks 1-7 in order; return the text of each page."""
    check_file(filename, data[:5], len(data))
    _check_document_limit(db, org_id)
    import pymupdf  # lazy: PyMuPDF only loads on upload

    try:
        pdf = pymupdf.open(stream=data, filetype="pdf")
    except Exception:
        raise AppError("invalid_pdf", "This file could not be opened as a PDF.", 400)
    with pdf:
        if pdf.needs_pass or pdf.is_encrypted:
            raise AppError("encrypted_pdf", "This PDF is password-protected. Please upload an unlocked copy.", 400)
        if pdf.page_count > MAX_PAGES:
            raise AppError("page_limit", f"This PDF has {pdf.page_count} pages; the limit is {MAX_PAGES}.", 400)
        total = 0
        for page in pdf:  # stop extracting as soon as the cap is exceeded
            total += len(page.get_text())
            if total > MAX_TEXT_CHARS:
                raise AppError(
                    "text_limit",
                    f"This PDF contains too much text; the limit is {MAX_TEXT_CHARS:,} characters.", 400,
                )
        pages = extract_pages(pdf)
    if sum(len("".join(p.split())) for p in pages) < MIN_TEXT_CHARS:
        raise AppError("no_text", "This looks like a scanned image. Please upload a text-based PDF.", 400)
    if db.scalar(select(Document.id).where(Document.org_id == org_id, Document.filename == filename)):
        raise AppError("duplicate_filename", f'A document named "{filename}" already exists.', 409)
    return pages


def _check_document_limit(db: Session, org_id) -> None:
    used = db.scalar(select(func.count()).select_from(Document).where(Document.org_id == org_id))
    if used >= MAX_DOCUMENTS:
        raise AppError(
            "document_limit",
            f"You already have {used} of {MAX_DOCUMENTS} documents. Delete one first.", 409,
        )


# ---------- ingestion ----------

def ingest(db: Session, org_id, filename: str, data: bytes) -> Document:
    pages = validate_pdf(db, org_id, filename, data)
    doc = Document(
        id=uuid.uuid4(), org_id=org_id, filename=filename, storage_path="",
        page_count=len(pages), size_bytes=len(data), status="processing",
    )
    doc.storage_path = storage_path(org_id, doc.id)
    try:
        # Serialize uploads per org: lock the org row, re-count, insert, commit (one transaction).
        db.execute(select(Organization.id).where(Organization.id == org_id).with_for_update())
        _check_document_limit(db, org_id)
        db.add(doc)
        db.commit()
    except AppError:
        db.rollback()
        raise
    except IntegrityError:  # concurrent upload with the same name
        db.rollback()
        raise AppError("duplicate_filename", f'A document named "{filename}" already exists.', 409)

    try:
        storage.upload(doc.storage_path, data)
        rows = [
            (page_no, text)
            for page_no, page_text in enumerate(pages, start=1)
            for text in chunk_page(page_text)
        ]
        vectors = embed_documents([t for _, t in rows]) if rows else []
        db.add_all(
            Chunk(org_id=org_id, document_id=doc.id, page_number=p, chunk_index=i, content=t, embedding=v)
            for i, ((p, t), v) in enumerate(zip(rows, vectors))
        )
        doc.status = "ready"
        db.commit()
    except Exception as e:
        log.error("Processing failed for document %s", doc.id, exc_info=e)
        db.rollback()
        _cleanup_failed(db, doc, e)
        raise AppError(
            "document_processing_failed", "We couldn't process this PDF. Please try again.", 500
        ) from e
    # After the document is ready, so a Gemini failure never fails the upload (it stores []).
    doc.suggested_questions = suggest_questions("\n\n".join(pages))
    db.commit()
    return doc


def _cleanup_failed(db: Session, doc: Document, error: Exception) -> None:
    db.execute(delete(Chunk).where(Chunk.org_id == doc.org_id, Chunk.document_id == doc.id))
    try:
        storage.delete(doc.storage_path)
    except Exception:
        log.warning("Could not remove storage file for failed document %s", doc.id)
    doc.status = "failed"
    doc.error_message = (getattr(error, "message", None) or type(error).__name__)[:500]
    db.commit()
