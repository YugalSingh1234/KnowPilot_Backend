"""In-memory sliding-window rate limit for public routes."""
import threading
import time
from collections import deque

from app.errors import AppError

LIMIT = 20
WINDOW_SECONDS = 60.0

# ponytail: per-process memory; resets on restart and isn't shared across workers.
# Move to Redis/Postgres if we run more than one instance.
_hits: dict[str, deque] = {}
_lock = threading.Lock()


def _allow(key: str, now: float) -> bool:
    q = _hits.setdefault(key, deque())
    while q and q[0] <= now - WINDOW_SECONDS:
        q.popleft()
    if len(q) >= LIMIT:
        return False
    q.append(now)
    return True


def _sweep(now: float) -> None:
    for key in [k for k, q in _hits.items() if not q or q[-1] <= now - WINDOW_SECONDS]:
        del _hits[key]


def check(token: str, ip: str) -> None:
    """Raise 429 if this token or this IP made LIMIT requests in the last minute."""
    now = time.monotonic()
    with _lock:
        if len(_hits) > 10_000:
            _sweep(now)
        ok_token = _allow(f"t:{token[:100]}", now)
        ok_ip = _allow(f"ip:{ip}", now)
    if not (ok_token and ok_ip):
        raise AppError("rate_limited", "Too many questions. Please wait a minute.", 429)


def reset() -> None:
    with _lock:
        _hits.clear()
