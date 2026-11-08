"""Private 'documents' bucket. Never creates public or signed URLs."""
from functools import lru_cache

from supabase import create_client

from app.config import get_settings


@lru_cache
def _bucket():
    s = get_settings()
    return create_client(s.SUPABASE_URL, s.SUPABASE_SECRET_KEY).storage.from_(s.SUPABASE_BUCKET)


def upload(path: str, data: bytes) -> None:
    _bucket().upload(path, data, {"content-type": "application/pdf", "upsert": "true"})


def delete(path: str) -> None:
    _bucket().remove([path])


def exists(path: str) -> bool:
    return _bucket().exists(path)
