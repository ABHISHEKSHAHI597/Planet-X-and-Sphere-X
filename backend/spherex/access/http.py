"""HTTP plumbing for spherex/access (implementation.md §3.7): one User-Agent, per-host concurrency limits
behind global semaphores, and transfer accounting so benchmarks and the bytes-per-view metric see every
byte. `spherex/access` is the only package that performs network I/O for SPHEREx pixels (workflow.md §3)."""
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from urllib.parse import urlsplit

import httpx

USER_AGENT = "ParallaX/0.1 (+https://github.com/ABHISHEKSHAHI597/Nasa-Space-Apps-2026; NASA Space Apps 2026)"
IRSA_HOST = "irsa.ipac.caltech.edu"
S3_HOST = "nasa-irsa-spherex.s3.amazonaws.com"
S3_HTTPS = f"https://{S3_HOST}/"
IBE_PREFIX = f"https://{IRSA_HOST}/ibe/data/spherex/"

# ✅ 11-06: 4 parallel IRSA requests drew a 503 from our network. Start at 4 and raise only after the
# F12 soak passes from the deployment VM. In-region S3 range reads tolerate 32+.
DEFAULT_LIMITS = {IRSA_HOST: 4, S3_HOST: 32}
FALLBACK_LIMIT = 4


@dataclass
class TransferStats:
    requests: int = 0
    bytes: int = 0
    failures: int = 0
    by_host: dict[str, int] = field(default_factory=dict)

    def add(self, url: str, nbytes: int) -> None:
        self.requests += 1
        self.bytes += nbytes
        host = urlsplit(url).hostname or ""
        self.by_host[host] = self.by_host.get(host, 0) + nbytes


class HostLimiter:
    """Global per-host semaphores. Shared by every FrameSource and client in a process."""

    def __init__(self, limits: dict[str, int] | None = None) -> None:
        self.limits = dict(DEFAULT_LIMITS if limits is None else limits)
        self._sems: dict[str, asyncio.Semaphore] = {}
        self.in_flight: dict[str, int] = {}
        self.peak: dict[str, int] = {}

    def _sem(self, host: str) -> asyncio.Semaphore:
        if host not in self._sems:
            self._sems[host] = asyncio.Semaphore(self.limits.get(host, FALLBACK_LIMIT))
        return self._sems[host]

    def slot(self, url: str) -> _Slot:
        return _Slot(self, urlsplit(url).hostname or "")


class _Slot:
    def __init__(self, lim: HostLimiter, host: str) -> None:
        self.lim, self.host = lim, host

    async def __aenter__(self) -> None:
        await self.lim._sem(self.host).acquire()
        n = self.lim.in_flight.get(self.host, 0) + 1
        self.lim.in_flight[self.host] = n
        self.lim.peak[self.host] = max(self.lim.peak.get(self.host, 0), n)

    async def __aexit__(self, *exc: object) -> None:
        self.lim.in_flight[self.host] -= 1
        self.lim._sem(self.host).release()


def make_client(transport: httpx.AsyncBaseTransport | None = None, timeout: float = 90.0) -> httpx.AsyncClient:
    return httpx.AsyncClient(headers={"User-Agent": USER_AGENT}, timeout=timeout, transport=transport,
                             follow_redirects=True, http2=False)


class Timer:
    def __init__(self) -> None:
        self.t0 = time.perf_counter()
        self.ttfb: float | None = None

    def first_byte(self) -> None:
        if self.ttfb is None:
            self.ttfb = time.perf_counter() - self.t0

    @property
    def elapsed(self) -> float:
        return time.perf_counter() - self.t0
