import os

from sqlalchemy import create_engine
from sqlalchemy.exc import InterfaceError, OperationalError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

from app.config import get_settings


def _engine_kwargs(url: str, serverless: bool) -> dict:
    """Serverless (Vercel): no pool, every invocation is short-lived. Supabase transaction pooler
    (port 6543) cannot track psycopg's server-side prepared statements, so disable them."""
    kw: dict = {"pool_pre_ping": True}
    kw.update({"poolclass": NullPool} if serverless else {"pool_size": 5})
    if ":6543" in url:
        kw["connect_args"] = {"prepare_threshold": None}
    return kw


engine = create_engine(get_settings().DATABASE_URL, **_engine_kwargs(get_settings().DATABASE_URL, bool(os.environ.get("VERCEL"))))
SessionLocal = sessionmaker(bind=engine, autoflush=False)


def get_db():
    with SessionLocal() as db:
        yield db


DB_CONNECTION_ERRORS = (OperationalError, InterfaceError)


def db_retry(db, fn):
    """Run fn() once more on a dropped connection; the pool hands out a fresh one after rollback.
    A second failure propagates and becomes 503 service_busy (see app/errors.py)."""
    try:
        return fn()
    except DB_CONNECTION_ERRORS:
        db.rollback()
        return fn()
