import uuid

import pytest
from sqlalchemy import delete

from app.db import SessionLocal
from app.models import Chunk, Document, Organization
from app.services import retrieval

DIM = 768


def unit(i: int) -> list[float]:
    v = [0.0] * DIM
    v[i] = 1.0
    return v


@pytest.fixture
def two_orgs(monkeypatch):
    monkeypatch.setattr(retrieval, "embed_query", lambda q: unit(0))
    ids = []
    with SessionLocal() as db:
        for name in ("Org A", "Org B"):
            org = Organization(name=name, email=f"ret-{uuid.uuid4().hex[:10]}@example.com", password_hash="x")
            db.add(org)
            db.flush()
            ids.append(org.id)
            for status in ("ready", "processing"):
                doc = Document(org_id=org.id, filename=f"{name}-{status}.pdf", storage_path="x", page_count=1,
                               size_bytes=1, status=status)
                db.add(doc)
                db.flush()
                db.add_all([
                    Chunk(org_id=org.id, document_id=doc.id, page_number=1, chunk_index=i,
                          content=f"{name} scholarship rule number {i} for {status} document", embedding=unit(i % 3))
                    for i in range(4)
                ])
        db.commit()
    yield ids
    with SessionLocal() as db:
        db.execute(delete(Organization).where(Organization.id.in_(ids)))
        db.commit()


def test_only_own_org_and_ready_documents(two_orgs):
    org_a, org_b = two_orgs
    with SessionLocal() as db:
        results = retrieval.retrieve(db, org_a, "scholarship rule", k=10)
    assert results, "expected chunks from org A"
    assert all(r["filename"] == "Org A-ready.pdf" for r in results)
    assert all(set(r) >= {"filename", "page_number", "content", "vector_score", "keyword_score"} for r in results)
    assert results[0]["vector_score"] == pytest.approx(1.0, abs=1e-4)
    assert any(r["keyword_score"] > 0 for r in results)


def test_unknown_org_gets_nothing(two_orgs):
    with SessionLocal() as db:
        assert retrieval.retrieve(db, uuid.uuid4(), "scholarship rule") == []


def test_keyword_terms_drop_stopwords():
    assert retrieval.keyword_terms("kya mujhe merit scholarship milegi?") == "merit scholarship milegi?"
