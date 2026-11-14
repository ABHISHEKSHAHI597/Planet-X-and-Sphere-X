"""Per-IP sliding-window rate limits (implementation.md §8 "Rate-limit reports per IP", §9 "per-IP job rate
limit"). In memory, like the job registry: one API process (§9)."""
from __future__ import annotations

import time
from collections import deque
from collections.abc import Callable

from fastapi import HTTPException, Request


class RateLimiter:
    def __init__(self, limit: int, window_s: float, clock: Callable[[], float] = time.monotonic) -> None:
        self.limit, self.window, self.clock = limit, window_s, clock
        self.hits: dict[str, deque[float]] = {}

    def allow(self, who: str) -> bool:
        now = self.clock()
        q = self.hits.setdefault(who, deque())
        while q and now - q[0] > self.window:
            q.popleft()
        if len(q) >= self.limit:
            return False
        q.append(now)
        if len(self.hits) > 1024:                 # forget quiet addresses (audit K-04): memory stays bounded
            for k in [k for k, v in self.hits.items() if not v or now - v[-1] > self.window]:
                del self.hits[k]
        return True

    def check(self, request: Request, what: str) -> None:
        ip = client_ip(request)
        if not self.allow(ip):
            raise HTTPException(429, f"Too many {what} from this address; please wait a minute and try again.")


def client_ip(request: Request) -> str:
    """The peer address as uvicorn reports it. Behind Caddy, `--proxy-headers` already replaces it with the address
    Caddy saw, so a client cannot choose its own rate-limit identity with a forged X-Forwarded-For (audit K-05)."""
    return request.client.host if request.client else "?"
