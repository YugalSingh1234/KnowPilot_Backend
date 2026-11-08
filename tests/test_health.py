from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health():
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "database": "ok"}


def test_unknown_route_uses_error_shape():
    r = client.get("/api/nope")
    assert r.status_code == 404
    assert set(r.json()["error"]) == {"code", "message"}


def test_cors_split():
    h = {"Origin": "http://evil.example", "Access-Control-Request-Method": "POST"}
    assert client.options("/api/ask", headers=h).headers["access-control-allow-origin"] == "*"
    assert "access-control-allow-origin" not in client.options("/api/health", headers=h).headers
