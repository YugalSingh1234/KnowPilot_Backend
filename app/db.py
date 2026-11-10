from sqlalchemy import create_engine
from sqlalchemy.exc import InterfaceError, OperationalError
from sqlalchemy.orm import sessionmaker

from app.config import get_settings

engine = create_engine(get_settings().DATABASE_URL, pool_pre_ping=True, pool_size=5)
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
