"""Automatic failover, pooling, caching and bounded-concurrency fetching (implementation.md §3.4, §3.7, §2.3).

FailoverSource: use the preferred source; after 3 consecutive SourceFailures switch to the other; while
switched, re-probe the preferred source every 5 minutes (one real request) and switch back if it works.
FrameUnavailable (off the frame, 4xx) is not a source failure and does not count.
PooledSource: several sources work the same queue at once (outside AWS: IRSA cutouts *and* S3 sections), each
frame routed to the source expected to finish it first, from each source's measured seconds per frame; a
source that fails is rested and its frame retried on another. Decision record 0009.
fetch_frames: the selected band's detector first, then the rest, behind the per-host semaphores; every
frame ends as fetched or as skipped with a reason, never dropped silently (workflow.md §11.2)."""
from __future__ import annotations

import asyncio
import time
from collections.abc import Callable, Sequence
from concurrent.futures import ThreadPoolExecutor

from ..types import FrameRef, RawFrame
from .cache import FrameCache
from .frames import SERVED_BY, FetchOutcome, FrameBox, FrameSource, FrameUnavailable, SourceFailure
from .window import canonical_crop

FAILOVER_AFTER = 3
REPROBE_S = 300.0


class FailoverSource:
    name = "failover"

    def __init__(self, preferred: FrameSource, fallback: FrameSource, threshold: int = FAILOVER_AFTER,
                 reprobe_s: float = REPROBE_S, clock: Callable[[], float] = time.monotonic) -> None:
        self.preferred, self.fallback = preferred, fallback
        self.threshold, self.reprobe_s, self.clock = threshold, reprobe_s, clock
        self.active: FrameSource = preferred
        self.consecutive = 0
        self.switched_at: float | None = None
        self.events: list[tuple[float, str]] = []
        self.last_source: str | None = None

    def _other(self, s: FrameSource) -> FrameSource:
        return self.fallback if s is self.preferred else self.preferred

    def _switch(self, to: FrameSource, why: str) -> None:
        self.events.append((self.clock(), f"switch {self.active.name} → {to.name}: {why}"))
        self.active = to
        self.consecutive = 0
        self.switched_at = self.clock() if to is not self.preferred else None

    async def fetch(self, ref: FrameRef, box: FrameBox) -> RawFrame:
        if self.active is not self.preferred and self.switched_at is not None \
                and self.clock() - self.switched_at >= self.reprobe_s:
            try:
                f = await self.preferred.fetch(ref, box)
                self._switch(self.preferred, "re-probe succeeded")
                self.last_source = self.preferred.name
                SERVED_BY.set(SERVED_BY.get() or self.preferred.name)
                return f
            except SourceFailure:
                self.switched_at = self.clock()           # stay; probe again in reprobe_s
        src = self.active
        try:
            f = await src.fetch(ref, box)
            self.consecutive = 0
            self.last_source = src.name
            SERVED_BY.set(SERVED_BY.get() or src.name)
            return f
        except SourceFailure as e:
            self.consecutive += 1
            if self.consecutive >= self.threshold:
                self._switch(self._other(src), f"{self.consecutive} consecutive failures ({e})")
            # This frame still gets one try on the other source before it is skipped.
            other = self._other(src)
            f = await other.fetch(ref, box)
            self.last_source = other.name
            SERVED_BY.set(SERVED_BY.get() or other.name)
            return f


class PooledSource:
    """Several FrameSources working one queue at once.

    Why: from a home connection the two sources are limited by different things. IRSA cutouts return only the
    box (≈ 0.2 MB a frame) but IRSA asks for ≤ 4 requests in flight; S3 sections have no such limit but read
    whole detector rows (≈ 3 MB a frame for a 6′ box). Measured from a laptop in India: ≈ 1.1 frames/s each.
    Used together their throughputs add, instead of one idling while the other works.

    Scheduling: each source has `capacity` frames in flight and an EWMA of its seconds per frame. A frame goes to
    the source with the earliest expected finish, L if a slot is free, else L·(1 + queued/capacity); so a fast
    source is worth queueing for, and a slow one never holds the last frames of a band. Failures: a SourceFailure
    counts toward resting that source for `rest_s` after `threshold` in a row, and the frame is retried once on
    each other source. FrameUnavailable (off the frame, 4xx) passes straight through, as in FailoverSource.
    `concurrency` (the sum of capacities) tells fetch_frames how many frames to start."""

    def __init__(self, sources: Sequence[FrameSource], capacity: Sequence[int], prior_s: Sequence[float],
                 alpha: float = 0.3, threshold: int = FAILOVER_AFTER, rest_s: float = 60.0,
                 clock: Callable[[], float] = time.monotonic) -> None:
        if not sources or not (len(sources) == len(capacity) == len(prior_s)):
            raise ValueError("PooledSource needs one capacity and one prior per source")
        self.sources = list(sources)
        self.capacity = [max(1, int(c)) for c in capacity]
        self.ewma = [float(p) for p in prior_s]
        self.alpha, self.threshold, self.rest_s, self.clock = alpha, threshold, rest_s, clock
        self.in_flight = [0] * len(self.sources)
        self.waiting = [0] * len(self.sources)
        self.fails = [0] * len(self.sources)
        self.rest_until = [0.0] * len(self.sources)
        self.served = [0] * len(self.sources)
        self._sems = [asyncio.Semaphore(c) for c in self.capacity]
        self.name = "pool(" + "+".join(x.name for x in self.sources) + ")"
        self.concurrency = sum(self.capacity)
        self.last_source: str | None = None
        self.events: list[tuple[float, str]] = []

    def expected_s(self, i: int) -> float:
        """Expected seconds until source i would finish one more frame."""
        queued = self.in_flight[i] + self.waiting[i] - self.capacity[i] + 1
        return self.ewma[i] * (1.0 + max(0, queued) / self.capacity[i])

    def _healthy(self, exclude: set[int]) -> list[int]:
        now = self.clock()
        left = [i for i in range(len(self.sources)) if i not in exclude]
        ok = [i for i in left if self.rest_until[i] <= now]
        # every remaining source is resting: use the one whose rest ends first rather than fail the frame
        return ok or ([min(left, key=lambda i: self.rest_until[i])] if left else [])

    async def _run(self, i: int, ref: FrameRef, box: FrameBox) -> RawFrame:
        self.waiting[i] += 1
        try:
            await self._sems[i].acquire()
        finally:
            self.waiting[i] -= 1
        self.in_flight[i] += 1
        t0 = self.clock()
        try:
            f = await self.sources[i].fetch(ref, box)
        finally:
            self.in_flight[i] -= 1
            self._sems[i].release()
        self.ewma[i] = (1 - self.alpha) * self.ewma[i] + self.alpha * max(self.clock() - t0, 1e-3)
        return f

    async def fetch(self, ref: FrameRef, box: FrameBox) -> RawFrame:
        tried: set[int] = set()
        last: SourceFailure | None = None
        while True:
            cand = self._healthy(tried)
            if not cand:
                raise last or SourceFailure(f"{self.name}: no source available")
            i = min(cand, key=self.expected_s)
            tried.add(i)
            try:
                f = await self._run(i, ref, box)
            except SourceFailure as e:
                last = e
                self.fails[i] += 1
                if self.fails[i] >= self.threshold:
                    self.rest_until[i] = self.clock() + self.rest_s
                    self.fails[i] = 0
                    self.events.append((self.clock(), f"rest {self.sources[i].name} {self.rest_s:.0f} s: {e}"))
                continue
            self.fails[i] = 0
            self.served[i] += 1
            name = SERVED_BY.get() or self.sources[i].name
            self.last_source = name
            SERVED_BY.set(name)
            return f

    def stats(self) -> dict[str, dict[str, float]]:
        return {x.name: {"served": self.served[i], "s_per_frame": round(self.ewma[i], 2),
                         "capacity": self.capacity[i]} for i, x in enumerate(self.sources)}


CACHE_IO_THREADS = 2


class CachedSource:
    """A FrameSource in front of the forever frame cache. Reads and writes run off the event loop: a cached
    frame costs 35-70 ms of FITS header parsing and WCS construction, which on the loop would stall every other
    request (and the progress stream) for ≈ 25 s while a 359-frame view reloads from the cache. That work is
    pure Python and holds the GIL, so it gets its own CACHE_IO_THREADS threads: more would not read faster,
    they would only take the GIL from the stacking threads and delay the first image until every frame is
    read (measured: first stack at 20.7 s of a 40 s warm rebuild with 16 readers)."""

    def __init__(self, inner: FrameSource, cache: FrameCache) -> None:
        self.inner, self.cache = inner, cache
        self.name = f"cached({inner.name})"
        self.concurrency = max(8, int(getattr(inner, "concurrency", 8)))
        self._io = ThreadPoolExecutor(CACHE_IO_THREADS, thread_name_prefix="frame-cache")

    async def fetch(self, ref: FrameRef, box: FrameBox) -> RawFrame:
        loop = asyncio.get_running_loop()
        hit = await loop.run_in_executor(self._io, self.cache.get, ref, box)
        if hit is not None:
            SERVED_BY.set("cache")
            return hit
        f = await self.inner.fetch(ref, box)
        src = SERVED_BY.get() or getattr(self.inner, "last_source", None) or self.inner.name
        try:
            await loop.run_in_executor(self._io, self.cache.put, ref, box, f, src)
        except OSError:                       # a full or read-only disk costs the cache, never the frame
            pass
        return f


def band_first(refs: Sequence[FrameRef], band: int | None) -> list[FrameRef]:
    """The selected band's frames first, so the first blink appears long before all frames are in."""
    if band is None:
        return list(refs)
    return [r for r in refs if r.detector == band] + [r for r in refs if r.detector != band]


async def fetch_frames(source: FrameSource, refs: Sequence[FrameRef], box: FrameBox | Callable[[FrameRef], FrameBox],
                       band: int | None = None, concurrency: int | None = None,
                       on_done: Callable[[int, int, FetchOutcome], None] | None = None) -> list[FetchOutcome]:
    """Fetch every frame; `box` may depend on the frame (track mode centres each frame on pos(t)).
    Outcomes are returned in the band-first order. Frames start in that order, so with on_done the caller
    sees each time bin complete roughly in turn. concurrency: by default the source's own (PooledSource sums
    its sources' capacities), else 8. Every frame is cut to its canonical window (window.py), so what is stacked
    does not depend on which source served it."""
    order = band_first(refs, band)
    sem = asyncio.Semaphore(concurrency or int(getattr(source, "concurrency", 8)))
    done = 0
    out: list[FetchOutcome | None] = [None] * len(order)

    async def one(i: int, ref: FrameRef) -> None:
        nonlocal done
        b = box(ref) if callable(box) else box
        t0 = time.perf_counter()
        async with sem:
            SERVED_BY.set(None)
            try:
                f = await source.fetch(ref, b)
                if isinstance(f, RawFrame):
                    f = canonical_crop(f, b, in_place=True)
                o = FetchOutcome(ref, f, SERVED_BY.get() or getattr(source, "last_source", None) or source.name,
                                 seconds=time.perf_counter() - t0)
            except FrameUnavailable as e:
                o = FetchOutcome(ref, None, None, f"unavailable: {e}", seconds=time.perf_counter() - t0)
            except SourceFailure as e:
                o = FetchOutcome(ref, None, None, f"fetch failed: {e}", seconds=time.perf_counter() - t0)
            except Exception as e:  # noqa: BLE001 — any other fault (odd FITS, crop): this frame only (audit K-17)
                o = FetchOutcome(ref, None, None, f"fetch failed: {type(e).__name__}: {e}"[:200],
                                 seconds=time.perf_counter() - t0)
        out[i] = o
        done += 1
        if on_done:
            on_done(done, len(order), o)

    await asyncio.gather(*(one(i, r) for i, r in enumerate(order)))
    return [o for o in out if o is not None]
