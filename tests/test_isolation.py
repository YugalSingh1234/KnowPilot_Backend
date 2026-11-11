"""Tenant isolation: one org's assistant can never see or answer from another org's documents."""
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete

from app.db import SessionLocal
from app.llm import generate
from app.main import app
from app.models import Chunk, Document, Organization
from app.services import orchestrator, ratelimit, retrieval
from app.system1 import classifier

client = TestClient(app)
UNIT = [1.0] + [0.0] * 767


@pytest.fixture(autouse=True)
def mocks(monkeypatch):
    ratelimit.reset()
    monkeypatch.setattr(retrieval, "embed_query", lambda q: UNIT)
    monkeypatch.setattr(orchestrator.classifier, "classify", lambda q: {"label": "direct", "confidence": 0.9})

    def echo_answer(question, chunks, language, question_type, decision=None):  # answer = what it was given
        return {"covered": True, "answer_text": " | ".join(c["content"] for c in chunks),
                "used_sources": [{"filename": c["filename"], "page": c["page_number"]} for c in chunks]}

    monkeypatch.setattr(generate, "generate_answer", echo_answer)
    yield
    ratelimit.reset()


def _make_org(secret: str) -> dict:
    email = f"iso-{uuid.uuid4().hex[:10]}@example.com"
    body = client.post("/api/auth/register", json={"org_name": "Iso Org", "email": email, "password": "password123"}).json()
    h = {"Authorization": f"Bearer {body['access_token']}"}
    org_id = uuid.UUID(body["org"]["id"])
    with SessionLocal() as db:
        doc = Document(org_id=org_id, filename=f"{secret}.pdf", storage_path="x", page_count=1, size_bytes=1, status="ready")
        db.add(doc)
        db.flush()
        db.add(Chunk(org_id=org_id, document_id=doc.id, page_number=1, chunk_index=0,
                     content=f"The secret code phrase of this organization is {secret}.", embedding=UNIT))
        db.commit()
        doc_id = doc.id
    token = client.get("/api/assistant", headers=h).json()["token"]
    return {"id": org_id, "h": h, "token": token, "doc_id": doc_id, "secret": secret}


@pytest.fixture
def orgs():
    a, b = _make_org("PURPLE-ELEPHANT-42"), _make_org("GOLDEN-TIGER-77")
    yield a, b
    with SessionLocal() as db:
        db.execute(delete(Organization).where(Organization.id.in_([a["id"], b["id"]])))
        db.commit()


def ask(token, question="What is the secret code phrase?"):
    return client.post("/api/ask", json={"assistant_token": token, "question": question})


def test_retrieval_is_isolated(orgs):
    a, b = orgs
    with SessionLocal() as db:
        for me, other in ((a, b), (b, a)):
            text = " ".join(c["content"] for c in retrieval.retrieve(db, me["id"], f"secret code {other['secret']}"))
            assert me["secret"] in text and other["secret"] not in text


def test_answers_are_isolated(orgs):
    a, b = orgs
    for me, other in ((a, b), (b, a)):
        r = ask(me["token"], f"Is the secret code phrase {other['secret']}?")
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["status"] == "answered"
        assert me["secret"] in body["answer"] and other["secret"] not in body["answer"]
        assert [ref["filename"] for ref in body["references"]] == [f"{me['secret']}.pdf"]


def test_foreign_document_id_is_404(orgs):
    a, b = orgs
    assert client.delete(f"/api/documents/{b['doc_id']}", headers=a["h"]).status_code == 404


def test_assistant_token_rejected_on_every_admin_route(orgs):
    a, _ = orgs
    h = {"Authorization": f"Bearer {a['token']}"}
    routes = [
        ("get", "/api/auth/me", {}), ("get", "/api/documents", {}),
        ("post", "/api/documents", {"files": {"file": ("x.pdf", b"%PDF-1.4", "application/pdf")}}),
        ("delete", f"/api/documents/{a['doc_id']}", {}), ("get", "/api/assistant", {}),
        ("post", "/api/assistant/regenerate", {}), ("get", "/api/usage", {}),
    ]
    for method, path, kw in routes:
        assert getattr(client, method)(path, headers=h, **kw).status_code == 401, path


def test_regenerated_token_is_404_on_ask(orgs):
    a, _ = orgs
    old = a["token"]
    client.post("/api/assistant/regenerate", headers=a["h"])
    r = ask(old)
    assert r.status_code == 404 and r.json()["error"]["code"] == "invalid_token"


def test_usage_counts_own_org_only(orgs):
    a, b = orgs
    ask(a["token"])
    ask(a["token"])
    ua = client.get("/api/usage", headers=a["h"]).json()
    ub = client.get("/api/usage", headers=b["h"]).json()
    assert ua["total_questions"] == 2 and ua["by_status"] == {"answered": 2} and ua["by_language"] == {"en": 2}
    assert ub["total_questions"] == 0


def test_out_of_scope_skips_llm(orgs, monkeypatch):
    a, _ = orgs
    monkeypatch.setattr(orchestrator.classifier, "classify", lambda q: {"label": "out_of_scope", "confidence": 0.9})
    monkeypatch.setattr(generate, "generate_answer", lambda *a, **k: pytest.fail("LLM must not be called"))
    body = ask(a["token"], "Who won the IPL?").json()
    assert body["status"] == "no_answer" and body["references"] == [] and body["decision"] is None


def test_llm_failure_returns_passages(orgs, monkeypatch):
    from app.errors import AppError

    a, _ = orgs

    def busy(*args, **kwargs):
        raise AppError("llm_unavailable", "busy", 503)

    monkeypatch.setattr(generate, "generate_answer", busy)
    body = ask(a["token"]).json()
    assert body["status"] == "passages_only" and body["answer"].startswith("The AI service is busy")
    assert body["references"][0]["filename"] == f"{a['secret']}.pdf"


def test_question_length_validated(orgs):
    a, _ = orgs
    assert ask(a["token"], "hi").status_code == 422
    assert ask(a["token"], "x" * 1001).status_code == 422


assert classifier  # imported module patched via orchestrator.classifier


def test_not_covered_is_no_answer(orgs, monkeypatch):
    a, _ = orgs
    monkeypatch.setattr(generate, "generate_answer",
                        lambda *a, **k: {"covered": False, "answer_text": "Not covered.", "used_sources": []})
    body = ask(a["token"]).json()
    assert body["status"] == "no_answer" and body["references"] == []
    assert client.get("/api/usage", headers=a["h"]).json()["by_status"] == {"no_answer": 1}


def test_db_drop_retried_once_then_503(orgs, monkeypatch):
    from sqlalchemy.exc import OperationalError

    a, _ = orgs
    real, calls = orchestrator.retrieval.retrieve, {"n": 0}

    def flaky(*args, **kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            raise OperationalError("select", {}, Exception("server closed the connection"))
        return real(*args, **kwargs)

    monkeypatch.setattr(orchestrator.retrieval, "retrieve", flaky)
    assert ask(a["token"]).json()["status"] == "answered" and calls["n"] == 2  # retried once

    def down(*args, **kwargs):
        raise OperationalError("select", {}, Exception("server closed the connection"))

    monkeypatch.setattr(orchestrator.retrieval, "retrieve", down)
    r = ask(a["token"])
    assert r.status_code == 503
    assert r.json()["error"] == {"code": "service_busy", "message": "Please try again in a moment."}


def test_no_answer_trace_hides_filenames(orgs, monkeypatch):
    a, _ = orgs
    monkeypatch.setattr(orchestrator.classifier, "classify", lambda q: {"label": "out_of_scope", "confidence": 0.9})
    body = ask(a["token"], "Who won the IPL?").json()
    summary = next(t["summary"] for t in body["trace"] if t["step"] == "retrieval")
    assert ".pdf" not in summary and "not enough" in summary
