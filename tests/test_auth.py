import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from app.db import SessionLocal
from app.main import app
from app.models import AssistantToken, Organization

client = TestClient(app)
PASSWORD = "correct-horse"


@pytest.fixture
def org():
    email = f"test-{uuid.uuid4().hex[:10]}@Example.com"
    r = client.post("/api/auth/register", json={"org_name": "Test Org", "email": email, "password": PASSWORD})
    assert r.status_code == 201, r.text
    yield {"email": email.lower(), **r.json()}
    with SessionLocal() as db:  # cascades to assistant_tokens
        db.execute(delete(Organization).where(Organization.id == uuid.UUID(r.json()["org"]["id"])))
        db.commit()


def test_register_ok(org):
    assert org["org"]["email"] == org["email"]  # stored lowercase
    assert org["access_token"]
    with SessionLocal() as db:
        tokens = db.scalars(select(AssistantToken).where(AssistantToken.org_id == uuid.UUID(org["org"]["id"]))).all()
    assert len(tokens) == 1 and tokens[0].is_active


def test_register_duplicate_email(org):
    r = client.post("/api/auth/register", json={"org_name": "Other", "email": org["email"].upper(), "password": PASSWORD})
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "email_exists"


def test_register_validation():
    bad = {"org_name": "X", "email": "nope", "password": "short"}
    r = client.post("/api/auth/register", json=bad)
    assert r.status_code == 422 and "error" in r.json()


def test_test_tld_email_accepted():
    email = f"demo-{uuid.uuid4().hex[:8]}@navodaya.test"
    r = client.post("/api/auth/register", json={"org_name": "Demo", "email": email, "password": PASSWORD})
    assert r.status_code == 201, r.text
    with SessionLocal() as db:
        db.execute(delete(Organization).where(Organization.id == uuid.UUID(r.json()["org"]["id"])))
        db.commit()


def test_login_ok(org):
    r = client.post("/api/auth/login", json={"email": org["email"], "password": PASSWORD})
    assert r.status_code == 200 and r.json()["org"]["id"] == org["org"]["id"]


def test_login_wrong_password_and_email(org):
    wrong_pw = client.post("/api/auth/login", json={"email": org["email"], "password": "wrong-password"})
    wrong_email = client.post("/api/auth/login", json={"email": "nobody@example.com", "password": PASSWORD})
    assert wrong_pw.status_code == wrong_email.status_code == 401
    assert wrong_pw.json() == wrong_email.json()
    assert wrong_pw.json()["error"]["code"] == "invalid_credentials"


def test_me_ok(org):
    r = client.get("/api/auth/me", headers={"Authorization": f"Bearer {org['access_token']}"})
    assert r.status_code == 200 and r.json() == org["org"]


def test_me_without_token():
    r = client.get("/api/auth/me")
    assert r.status_code == 401 and r.json()["error"]["code"] == "unauthorized"


def test_me_with_assistant_token_rejected(org):
    with SessionLocal() as db:
        tok = db.scalar(select(AssistantToken.token).where(AssistantToken.org_id == uuid.UUID(org["org"]["id"])))
    r = client.get("/api/auth/me", headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 401
