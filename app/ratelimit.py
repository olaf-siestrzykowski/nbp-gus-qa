"""In-memory rate limiting for the LLM endpoints.

Each question costs Groq tokens, so limits apply per client IP (stops one user from
spamming) and globally per day (caps the bill even if requests come from many IPs).
State lives in the process: fine for the single Render instance, it resets on restart.
"""
import threading
import time
from collections import deque

from fastapi import HTTPException, Request

from app.config import settings

MINUTE = 60
DAY = 24 * 60 * 60

MINUTE_MESSAGE = "Zbyt wiele pytań w krótkim czasie. Spróbuj ponownie za minutę."
DAILY_MESSAGE = "Dzienny limit pytań z tego adresu został wykorzystany. Wróć jutro."
GLOBAL_MESSAGE = "Demo wykorzystało dzisiejszy limit pytań. Wróć jutro."


class RateLimiter:
    def __init__(self, per_minute: int, per_day: int, global_per_day: int, clock=time.monotonic):
        self.per_minute = per_minute
        self.per_day = per_day
        self.global_per_day = global_per_day
        self._clock = clock
        self._lock = threading.Lock()
        self._by_client: dict[str, deque[float]] = {}
        self._all: deque[float] = deque()

    def check(self, client: str) -> tuple[int, str] | None:
        """Record a request and return None, or (seconds to wait, message) if over a limit."""
        now = self._clock()
        with self._lock:
            # .get: a blocked request must not add a client entry
            hits = self._by_client.get(client, deque())
            for timestamps in (hits, self._all):
                while timestamps and timestamps[0] <= now - DAY:
                    timestamps.popleft()
            last_minute = [t for t in hits if t > now - MINUTE]
            if len(self._all) >= self.global_per_day:
                return int(self._all[0] + DAY - now) + 1, GLOBAL_MESSAGE
            if len(hits) >= self.per_day:
                return int(hits[0] + DAY - now) + 1, DAILY_MESSAGE
            if len(last_minute) >= self.per_minute:
                return int(last_minute[0] + MINUTE - now) + 1, MINUTE_MESSAGE
            hits.append(now)
            self._by_client[client] = hits
            self._all.append(now)
            # Clients idle for a day would otherwise stay in the dict forever
            if len(self._by_client) > 10_000:
                for key, client_hits in list(self._by_client.items()):
                    if not client_hits or client_hits[-1] <= now - DAY:
                        del self._by_client[key]
            return None


limiter = RateLimiter(
    per_minute=settings.rate_limit_per_minute,
    per_day=settings.rate_limit_per_day,
    global_per_day=settings.rate_limit_global_per_day,
)


def client_ip(request: Request) -> str:
    # Render's proxy appends the real client address as the last X-Forwarded-For entry;
    # earlier entries come from the client and can be spoofed
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[-1].strip()
    return request.client.host if request.client else "unknown"


def rate_limit(request: Request):
    """FastAPI dependency for endpoints that call the LLM."""
    blocked = limiter.check(client_ip(request))
    if blocked is not None:
        retry_after, message = blocked
        raise HTTPException(status_code=429, detail=message, headers={"Retry-After": str(retry_after)})
