import uuid

import pymupdf
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select

from app.db import SessionLocal
from app.errors import AppError
from app.main import app
from app.models import Chunk, Document, Organization
from app.services import ingest, storage

client = TestClient(app)
PARA = (
    "Students with a CGPA of 8.0 or above are eligible for the merit scholarship. "
    "Family income must be below 8 lakh rupees per year. Applications close on 31 July. "
)


def make_pdf(pages: list[str]) -> bytes:
    doc = pymupdf.open()
    for text in pages:
        page = doc.new_page()
        if text:
            page.insert_textbox(pymupdf.Rect(50, 50, 550, 800), text, fontsize=9)
    return doc.tobytes()


@pytest.fixture(autouse=True)
def fakes(monkeypatch):
    files = {}
    monkeypatch.setattr(storage, "upload", lambda path, data: files.__setitem__(path, data))
    monkeypatch.setattr(storage, "delete", lambda path: files.pop(path, None))
    monkeypatch.setattr(ingest, "embed_documents", lambda texts: [[1.0] + [0.0] * 767 for _ in texts])
    monkeypatch.setattr(ingest, "suggest_questions", lambda text: ["Q1?", "Q2?", "Q3?"])
    return files


def _register():
    email = f"doc-{uuid.uuid4().hex[:10]}@example.com"
    r = client.post("/api/auth/register", json={"org_name": "Doc Org", "email": email, "password": "password123"})
    body = r.json()
    return {"id": uuid.UUID(body["org"]["id"]), "h": {"Authorization": f"Bearer {body['access_token']}"}}


@pytest.fixture
def org():
    o = _register()
    yield o
    with SessionLocal() as db:
        db.execute(delete(Organization).where(Organization.id == o["id"]))
        db.commit()


@pytest.fixture
def other_org():
    o = _register()
    yield o
    with SessionLocal() as db:
        db.execute(delete(Organization).where(Organization.id == o["id"]))
        db.commit()


def upload(org, data: bytes, name="Scholarship_Policy.pdf"):
    return client.post("/api/documents", headers=org["h"], files={"file": (name, data, "application/pdf")})


def err(r):
    return r.json()["error"]["code"], r.json()["error"]["message"]


def test_valid_upload_indexes_pages(org, fakes):
    r = upload(org, make_pdf([PARA * 8, PARA * 3]))
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["status"] == "ready" and body["page_count"] == 2 and body["chunk_count"] >= 2
    assert f"{org['id']}/{body['id']}.pdf" in fakes
    with SessionLocal() as db:
        chunks = db.scalars(select(Chunk).where(Chunk.org_id == org["id"]).order_by(Chunk.chunk_index)).all()
    assert {c.page_number for c in chunks} == {1, 2}
    assert [c.chunk_index for c in chunks] == list(range(len(chunks)))
    listing = client.get("/api/documents", headers=org["h"]).json()
    assert listing["limits"] == {"max_documents": 10, "max_pages": 20, "max_mb": 10, "used_documents": 1}
    assert listing["documents"][0]["chunk_count"] == body["chunk_count"]


def test_fake_pdf_rejected(org):
    assert err(upload(org, b"hello, not a pdf"))[0] == "invalid_pdf"
    assert err(upload(org, make_pdf([PARA]), name="notes.txt"))[0] == "invalid_pdf"


def test_too_many_pages(org):
    r = upload(org, make_pdf([PARA] * 21))
    assert r.status_code == 400
    assert err(r) == ("page_limit", "This PDF has 21 pages; the limit is 20.")


def test_textless_pdf(org):
    assert err(upload(org, make_pdf(["", ""])))[0] == "no_text"


def test_too_large(org, monkeypatch):
    monkeypatch.setattr(ingest, "MAX_BYTES", 100)
    code, message = err(upload(org, make_pdf([PARA])))
    assert code == "file_too_large" and message.endswith("the limit is 10 MB.")


def test_too_much_text(org, monkeypatch):
    monkeypatch.setattr(ingest, "MAX_TEXT_CHARS", 500)
    assert err(upload(org, make_pdf([PARA * 8])))[0] == "text_limit"


def test_limit_rechecked_under_lock(org, monkeypatch):
    """Simulates a concurrent upload landing between validation and insert."""
    real_validate = ingest.validate_pdf

    def validate_then_race(db, org_id, filename, data):
        pages = real_validate(db, org_id, filename, data)
        with SessionLocal() as other:
            other.add_all(
                Document(org_id=org_id, filename=f"r{i}.pdf", storage_path="x", page_count=1, size_bytes=1)
                for i in range(10)
            )
            other.commit()
        return pages

    monkeypatch.setattr(ingest, "validate_pdf", validate_then_race)
    assert err(upload(org, make_pdf([PARA])))[0] == "document_limit"
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(Document).where(Document.org_id == org["id"])) == 10


def test_duplicate_filename(org):
    assert upload(org, make_pdf([PARA])).status_code == 201
    assert err(upload(org, make_pdf([PARA])))[0] == "duplicate_filename"


def test_eleventh_document_refused(org):
    with SessionLocal() as db:
        db.add_all(
            Document(org_id=org["id"], filename=f"f{i}.pdf", storage_path="x", page_count=1, size_bytes=1, status="ready")
            for i in range(10)
        )
        db.commit()
    r = upload(org, make_pdf([PARA]))
    assert r.status_code == 409
    assert err(r) == ("document_limit", "You already have 10 of 10 documents. Delete one first.")


def test_processing_failure_cleans_up(org, fakes, monkeypatch):
    def boom(texts):
        raise AppError("llm_unavailable", "down", 503)

    monkeypatch.setattr(ingest, "embed_documents", boom)
    r = upload(org, make_pdf([PARA]))
    assert r.status_code == 500 and err(r)[0] == "document_processing_failed"
    assert fakes == {}
    with SessionLocal() as db:
        doc = db.scalar(select(Document).where(Document.org_id == org["id"]))
        n = db.scalar(select(func.count()).select_from(Chunk).where(Chunk.org_id == org["id"]))
    assert doc.status == "failed" and doc.error_message == "down" and n == 0


def test_delete(org, fakes):
    doc_id = upload(org, make_pdf([PARA])).json()["id"]
    assert client.delete(f"/api/documents/{doc_id}", headers=org["h"]).status_code == 204
    assert fakes == {}
    assert client.get("/api/documents", headers=org["h"]).json()["documents"] == []
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(Chunk).where(Chunk.org_id == org["id"])) == 0


def test_delete_other_orgs_document_is_404(org, other_org):
    doc_id = upload(org, make_pdf([PARA])).json()["id"]
    r = client.delete(f"/api/documents/{doc_id}", headers=other_org["h"])
    missing = client.delete(f"/api/documents/{uuid.uuid4()}", headers=other_org["h"])
    assert r.status_code == 404 and r.json() == missing.json()
    assert len(client.get("/api/documents", headers=org["h"]).json()["documents"]) == 1


def test_requires_login():
    assert client.get("/api/documents").status_code == 401


def _pdf_with_chrome(bodies: list[str]) -> pymupdf.Document:
    """Each page: a running header and footer in the margins, a unique body line and a repeated body line."""
    doc = pymupdf.open()
    for i, body in enumerate(bodies, 1):
        page = doc.new_page()  # 842pt tall: the 7% margins are the top/bottom ~59pt
        page.insert_text((50, 30), "Acme College | Fee Rules", fontsize=9)
        page.insert_text((50, 300), body, fontsize=11)
        page.insert_text((50, 400), "Repeated rule on every page.", fontsize=11)
        page.insert_text((50, 825), f"Illustrative footer   Page {i}", fontsize=8)
    return doc


def test_running_headers_and_footers_stripped():
    bodies = ["Hostel fee is due in July.", "Refunds follow the schedule.", "Late fee is charged weekly."]
    pages = ingest.extract_pages(_pdf_with_chrome(bodies))
    for page, body in zip(pages, bodies):
        assert body in page and "Repeated rule on every page." in page  # body kept, even when repeated
        assert "Acme College" not in page and "Illustrative footer" not in page
    single = ingest.extract_pages(_pdf_with_chrome(["Only page."]))[0]
    assert "Acme College" in single  # nothing "repeats" in a one-page PDF


def test_chunk_page_sizes_and_overlap():
    chunks = ingest.chunk_page((PARA * 30) + "\n\nShort.")
    assert len(chunks) > 1
    assert all(len(c) <= ingest.CHUNK_SIZE for c in chunks)
    assert chunks[0][-60:] in chunks[1]  # trailing sentence carried over
    assert ingest.chunk_page("Too short.") == []
