"""Retries with exponential backoff and jitter (implementation.md §3.4 "Retries", §3.7).

Retry on 429/5xx, transport errors, truncated bodies (EOFError: ✅ 11-06 IRSA ended transfers early
after HTTP 200) and corrupt bodies. Never retry other 4xx (e.g. the point is off this frame). A frame
that still fails is reported by the caller as skipped; a view never fails as a whole."""
from __future__ import annotations

import asyncio
import random
from collections.abc import Awaitable, Callable
from typing import TypeVar

import httpx

from .fitsio import CorruptResponse

T = TypeVar("T")
RETRYABLE = (httpx.TransportError, EOFError, CorruptResponse)


class GaveUp(RuntimeError):
    def __init__(self, tries: int, last: BaseException | None) -> None:
        super().__init__(f"gave up after {tries} tries: {last!r}")
        self.tries, self.last = tries, last


def is_retryable(e: BaseException) -> bool:
    if isinstance(e, httpx.HTTPStatusError):
        code = e.response.status_code
        return code >= 500 or code == 429
    return isinstance(e, RETRYABLE)


def backoff(k: int, cap: float = 30.0, rng: random.Random | None = None) -> float:
    r = (rng or random).random()
    return min(cap, 2.0 ** k) * (0.5 + r)


async def with_retry(fetch: Callable[[], Awaitable[T]], tries: int = 4,
                     sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
                     on_error: Callable[[int, BaseException], None] | None = None) -> T:
    last: BaseException | None = None
    for k in range(tries):
        try:
            return await fetch()
        except Exception as e:  # noqa: BLE001 — classified below
            if not is_retryable(e):
                raise
            last = e
            if on_error:
                on_error(k, e)
        if k < tries - 1:
            await sleep(backoff(k))
    raise GaveUp(tries, last)
