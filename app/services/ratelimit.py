"""In-memory sliding-window rate limit for public routes.

Call order on a public route: check_ip -> resolve the token in the DB -> check_token.
Unknown tokens never get a counter, and a request blocked by IP never counts against the token.
IP and token counters live in separate stores, so flooding one can't evict the other.
When a store is full of live counters, new keys are refused (fail closed), never evicted.
"""
import ipaddress
import threading
import time
from collections import OrderedDict, deque

from fastapi import Request

from app.errors import AppError

IP_LIMIT = 20
TOKEN_LIMIT = 200  # whole-tenant abuse ceiling; well above IP_LIMIT so one abuser can't lock out a college
WINDOW_SECONDS = 60.0
MAX_KEYS = 50_000  # per store

# ponytail: per-process memory; resets on restart and isn't shared across workers.
# Move to Redis/Postgres if we run more than one instance.
_ip_hits: "OrderedDict[str, deque]" = OrderedDict()  # ordered by last counted hit
_token_hits: "OrderedDict[str, deque]" = OrderedDict()
_lock = threading.Lock()


def _limited() -> AppError:
    return AppError("rate_limited", "Too many questions. Please wait a minute.", 429)


def _allow(store: OrderedDict, key: str, limit: int) -> bool:
    now = time.monotonic()
    cutoff = now - WINDOW_SECONDS
    with _lock:
        q = store.get(key)
        if q is None:
            # Front of the store = oldest last hit; drop entries whose window has passed.
            while store and next(iter(store.values()))[-1] <= cutoff:
                store.popitem(last=False)
            if len(store) >= MAX_KEYS:
                return False  # every counter is live: refuse rather than evict
            q = store[key] = deque()
        while q and q[0] <= cutoff:
            q.popleft()
        if len(q) >= limit:
            return False
        q.append(now)
        store.move_to_end(key)
        return True


def client_ip(request: Request) -> str:
    """Rightmost X-Forwarded-For entry: the one appended by our own proxy (Render), which the
    visitor can't forge. Falls back to the socket peer when absent or not a valid IP.
    IPv6 is grouped by /64, the block one subscriber typically controls."""
    forwarded = request.headers.get("x-forwarded-for", "")
    candidate = forwarded.rsplit(",", 1)[-1].strip()
    try:
        ip = ipaddress.ip_address(candidate)
    except ValueError:
        return request.client.host if request.client else "unknown"
    if ip.version == 6:
        return str(ipaddress.ip_network(f"{ip}/64", strict=False))
    return str(ip)


def check_ip(ip: str) -> None:
    if not _allow(_ip_hits, ip, IP_LIMIT):
        raise _limited()


def check_token(token: str) -> None:
    """Only call with a token that resolved to a real, active assistant."""
    if not _allow(_token_hits, token, TOKEN_LIMIT):
        raise _limited()


def reset() -> None:
    with _lock:
        _ip_hits.clear()
        _token_hits.clear()
