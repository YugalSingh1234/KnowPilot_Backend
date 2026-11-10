import pytest
from pydantic import ValidationError

from app.config import Settings


@pytest.mark.parametrize("secret", [None, "", "short"])
def test_weak_or_missing_jwt_secret_refuses_to_start(monkeypatch, secret):
    monkeypatch.delenv("JWT_SECRET", raising=False)
    kwargs = {} if secret is None else {"JWT_SECRET": secret}
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **kwargs)


def test_strong_jwt_secret_ok():
    assert Settings(_env_file=None, JWT_SECRET="x" * 32).JWT_SECRET


def test_frontend_origins_comma_separated():
    s = Settings(_env_file=None, JWT_SECRET="x" * 32,
                 FRONTEND_ORIGIN=" https://knowpilot.vercel.app/ , http://localhost:5173 ,")
    assert s.frontend_origins == ["https://knowpilot.vercel.app", "http://localhost:5173"]
