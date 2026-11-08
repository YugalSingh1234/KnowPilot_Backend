"""In-memory sliding-window rate limit for public routes.

Call order on a public route: check_ip -> resolve the token in the DB -> check_token.
Unknown tokens never get a counter, and a request blocked by IP never counts against the token.
"""
import ipaddress
import threading
import time
from collections import OrderedDict, deque

from fastapi import Request

from app.errors import AppError

IP_LIMIT = 20
TOKEN_LIMIT = 20
WINDOW_SECONDS = 60.0
MAX_KEYS = 50_000  # hard memory cap; least recently used keys are evicted

# ponytail: per-process memory; resets on restart and isn't shared across workers.
# Move to Redis/Postgres if we run more than one instance.
_hits: "OrderedDict[str, deque]" = OrderedDict()
_lock = threading.Lock()


def _limited() -> AppError:
    return AppError("rate_limited", "Too many questions. Please wait a minute.", 429)


def _allow(key: str, limit: int) -> bool:
    now = time.monotonic()
    with _lock:
        q = _hits.get(key)
        if q is None:
            q = _hits[key] = deque()
            if len(_hits) > MAX_KEYS:
                _hits.popitem(last=False)
        else:
            _hits.move_to_end(key)
        while q and q[0] <= now - WINDOW_SECONDS:
            q.popleft()
        if len(q) >= limit:
            return False
        q.append(now)
        return True


def client_ip(request: Request) -> str:
    """Rightmost X-Forwarded-For entry: the one appended by our own proxy (Render), which the
    visitor can't forge. Falls back to the socket peer when absent or not a valid IP."""
    forwarded = request.headers.get("x-forwarded-for", "")
    candidate = forwarded.rsplit(",", 1)[-1].strip()
    try:
        return str(ipaddress.ip_address(candidate))
    except ValueError:
        return request.client.host if request.client else "unknown"


def check_ip(ip: str) -> None:
    if not _allow(f"ip:{ip}", IP_LIMIT):
        raise _limited()


def check_token(token: str) -> None:
    """Only call with a token that resolved to a real, active assistant."""
    if not _allow(f"t:{token}", TOKEN_LIMIT):
        raise _limited()


def reset() -> None:
    with _lock:
        _hits.clear()
