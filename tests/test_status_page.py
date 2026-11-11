from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app.config import get_settings
from app.db import get_db
from app.main import APP_VERSION, app

client = TestClient(app)


def test_status_page_running():
    r = client.get("/")
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/html")
    body = r.text
    assert "KnowPilot API" in body and "Running" in body and APP_VERSION in body
    assert 'href="/docs"' in body and f'href="{get_settings().frontend_origins[0]}"' in body
    assert "@example.com" not in body  # counts only, no org details


def test_status_page_database_issue():
    class DownSession:
        def execute(self, *a, **k):
            raise OperationalError("select 1", {}, Exception("down"))

    app.dependency_overrides[get_db] = lambda: DownSession()
    try:
        r = client.get("/")
    finally:
        app.dependency_overrides.pop(get_db, None)
    assert r.status_code == 200 and "Database issue" in r.text and "Running" not in r.text
