from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import get_settings

engine = create_engine(get_settings().DATABASE_URL, pool_pre_ping=True, pool_size=5)
SessionLocal = sessionmaker(bind=engine, autoflush=False)


def get_db():
    with SessionLocal() as db:
        yield db
