import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select

from app.db import SessionLocal
from app.main import app
from app.models import AssistantToken, Organization
from app.services import ratelimit

client = TestClient(app)


@pytest.fixture(autouse=True)
def _reset_rate_limit():
    ratelimit.reset()
    yield
    ratelimit.reset()


@pytest.fixture
def org():
    email = f"asst-{uuid.uuid4().hex[:10]}@example.com"
    r = client.post("/api/auth/register", json={"org_name": 'Sunrise "College" <A>', "email": email, "password": "password123"})
    body = r.json()
    o = {"id": uuid.UUID(body["org"]["id"]), "h": {"Authorization": f"Bearer {body['access_token']}"}}
    yield o
    with SessionLocal() as db:
        db.execute(delete(Organization).where(Organization.id == o["id"]))
        db.commit()


def test_get_assistant_shape(org):
    r = client.get("/api/assistant", headers=org["h"])
    assert r.status_code == 200
    body = r.json()
    assert set(body) == {"assistant_url", "token", "created_at", "embed_code"}
    assert body["assistant_url"].endswith(f"/a/{body['token']}")
    assert f'src="{body["assistant_url"]}"' in body["embed_code"]
    assert 'title="Sunrise &quot;College&quot; &lt;A&gt; Assistant"' in body["embed_code"]  # escaped


def test_info_without_login(org):
    token = client.get("/api/assistant", headers=org["h"]).json()["token"]
    r = client.get(f"/api/assistant/{token}/info")
    assert r.status_code == 200
    assert r.json() == {"org_name": 'Sunrise "College" <A>', "suggested_questions": []}


def test_unknown_and_oversized_tokens_404():
    for token in ("nope", "x" * 101):
        r = client.get(f"/api/assistant/{token}/info")
        assert r.status_code == 404
        assert r.json()["error"] == {"code": "invalid_token", "message": "This assistant link is not active."}


def test_regenerate_kills_old_token(org):
    old = client.get("/api/assistant", headers=org["h"]).json()["token"]
    new = client.post("/api/assistant/regenerate", headers=org["h"]).json()["token"]
    assert new != old
    assert client.get(f"/api/assistant/{old}/info").status_code == 404
    assert client.get(f"/api/assistant/{new}/info").status_code == 200
    with SessionLocal() as db:
        active = db.scalar(select(func.count()).select_from(AssistantToken).where(AssistantToken.org_id == org["id"], AssistantToken.is_active))
        revoked = db.scalar(select(AssistantToken.revoked_at).where(AssistantToken.token == old))
    assert active == 1 and revoked is not None


def test_assistant_token_as_bearer_rejected(org):
    token = client.get("/api/assistant", headers=org["h"]).json()["token"]
    r = client.get("/api/assistant", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 401


def test_admin_routes_need_login():
    assert client.get("/api/assistant").status_code == 401
    assert client.post("/api/assistant/regenerate").status_code == 401


def test_rate_limit(org):
    token = client.get("/api/assistant", headers=org["h"]).json()["token"]
    codes = [client.get(f"/api/assistant/{token}/info").status_code for _ in range(21)]
    assert codes[:20] == [200] * 20
    r = client.get(f"/api/assistant/{token}/info")
    assert r.status_code == 429
    assert r.json()["error"] == {"code": "rate_limited", "message": "Too many questions. Please wait a minute."}


def test_cors_public_info_but_not_regenerate():
    h = {"Origin": "http://school.example", "Access-Control-Request-Method": "GET"}
    assert client.options("/api/assistant/abc/info", headers=h).headers.get("access-control-allow-origin") == "*"
    assert "access-control-allow-origin" not in client.options("/api/assistant/regenerate", headers=h).headers
