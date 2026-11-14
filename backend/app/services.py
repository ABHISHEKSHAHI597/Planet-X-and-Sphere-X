"""Process-wide services, built once at start-up from Settings (FastAPI lifespan). Every network client,
cache and pool lives here, so routes stay thin and tests can build a Services with a fixture FrameSource
and recorded HTTP responses (workflow.md §8.5 fixture-backed mode)."""
from __future__ import annotations

import asyncio
import datetime
import json
import logging
import os
import time
from concurrent.futures import Executor, ProcessPoolExecutor, ThreadPoolExecutor
from pathlib import Path
from typing import Any

import httpx

from spherex.access import releases as releases_mod
from spherex.access.cache import CoverageCache
from spherex.access.coverage import CoverageClient
from spherex.access.frames import FrameSource
from spherex.access.http import HostLimiter, make_client
from spherex.access.sources import build_source
from spherex.access.watcher import ReleaseState, check, period_week_start

from . import calibration
from .jobs import JobRegistry
from .settings import Settings, effective_features, load_features
from .store import ViewStore

log = logging.getLogger("parallax")


class Counters:
    """Simple counters (implementation.md §9 "Observability"), exposed at /metrics."""

    def __init__(self) -> None:
        self.c: dict[str, float] = {}

    def inc(self, name: str, by: float = 1.0) -> None:
        self.c[name] = self.c.get(name, 0.0) + by

    def snapshot(self) -> dict[str, float]:
        return dict(sorted(self.c.items()))


class Services:
    def __init__(self, settings: Settings, transport: httpx.AsyncBaseTransport | None = None,
                 source: FrameSource | None = None) -> None:
        self.settings = settings
        self.registry = releases_mod.load(settings.releases_path)
        self.features_cfg = load_features(settings.features_path)
        self.limiter = HostLimiter()
        self.client: httpx.AsyncClient | None = None
        if settings.network or transport is not None:
            self.client = make_client(transport)
        cache = settings.cache_dir
        self.store = ViewStore(cache)
        self.snapshot = ViewStore(settings.snapshot_dir) if settings.snapshot_dir else None
        self.coverage_cache = CoverageCache(cache / "coverage")
        self.coverage = CoverageClient(self.client, self.registry, self.limiter, cache=self.coverage_cache) \
            if self.client is not None else None
        if source is not None:
            self.source: FrameSource | None = source
        elif settings.framesource == "fixture":
            self.source = build_source("fixture", fixture_root=settings.fixture_root)
        elif self.client is not None:
            self.source = build_source(settings.framesource, client=self.client, registry=self.registry,
                                       in_aws_us_east_1=settings.in_aws_us_east_1, cache_root=cache / "frames",
                                       limiter=self.limiter)
        else:
            self.source = None                                  # offline: snapshot only
        self.calib_spec = calibration.spec_for(settings.framesource, settings.calib_root)
        self.calib_tag = calibration.tag(self.calib_spec)
        self.jobs = JobRegistry(timeout_s=settings.job_timeout_s)
        self.counters = Counters()
        self.release_state_path = cache / "release_state.json"
        # Threads when CPU_WORKERS=0 (Windows default: spawn-started process pools cost seconds per worker and
        # pickle every frame). numpy, scipy.ndimage and astropy's WCS release the GIL for most of a stack, so
        # more than the former 2 threads do help; sized to the machine, at most 8.
        # forkserver, not fork: workers are started after the frame-cache and stacking threads exist, and forking a
        # multi-threaded process can copy a held lock into the child (audit K-24). Windows/macOS already spawn.
        self.executor: Executor = (ProcessPoolExecutor(settings.cpu_workers, mp_context=_mp_context())
                                   if settings.cpu_workers > 0
                                   else ThreadPoolExecutor(max(2, min(8, (os.cpu_count() or 3) - 1)),
                                                           thread_name_prefix="stack"))
        self.health_cache: tuple[float, list[dict[str, Any]]] | None = None
        self.health_fails = 0
        self.irsa_down = False
        # request (without frame list) → view key of views planned live, so they stay reachable while IRSA is down
        self.live_index_path = cache / "live_index.json"
        self.live_index: dict[str, str] = _read_json(self.live_index_path)
        self._watcher: asyncio.Task[None] | None = None
        self._pruning = False
        self._prober: asyncio.Task[None] | None = None

    # ------------------------------------------------------------------------------------ lifecycle
    async def start(self) -> None:
        if self.settings.calib_root is not None:
            calibration.load(self.calib_spec, verify=True)     # verify once, here; workers load unverified
        if self.settings.run_watcher and self.client is not None:
            self._watcher = asyncio.create_task(self._watch())
        elif self.client is not None and self.settings.network:
            # Laptops: one listing at start-up so the freshness badge is not "unknown" in a local demo (K-33).
            self._watcher = asyncio.create_task(self._watch_once())
        if self.snapshot is not None and self.client is not None and not self.settings.offline:
            self._prober = asyncio.create_task(self._probe())
        self.schedule_prune()

    async def close(self) -> None:
        for task in (self._watcher, self._prober):
            if task:
                task.cancel()
        if self.client is not None:
            await self.client.aclose()
        self.executor.shutdown(wait=False, cancel_futures=True)

    async def _watch(self) -> None:
        """Hourly release watcher (implementation.md §3.6). It refreshes coverage caches (via the
        release-state token) and the freshness badge; it never touches pins or config/releases.yaml."""
        assert self.client is not None
        while True:
            try:
                rep = await check(self.client, self.registry, self.release_state_path)
                for e in rep["events"]:
                    log.info(json.dumps({"event": "release_watcher", "message": e}))
            except Exception as e:                              # a failed listing is logged, never fatal
                log.warning(json.dumps({"event": "release_watcher_error", "error": repr(e)[:200]}))
            await asyncio.sleep(self.settings.watcher_interval_s)

    async def _watch_once(self) -> None:
        assert self.client is not None
        try:
            rep = await check(self.client, self.registry, self.release_state_path)
            for e in rep["events"]:
                log.info(json.dumps({"event": "release_watcher", "message": e}))
        except Exception as e:                                  # offline or S3 slow: the badge says "unknown"
            log.warning(json.dumps({"event": "release_watcher_error", "error": repr(e)[:200]}))

    async def _probe(self) -> None:
        """implementation.md §9: when the IRSA health checks fail, serve the snapshot. /healthz updates
        `irsa_down`, so poll it here instead of relying on an outside monitor (cached 60 s)."""
        from .main import health

        while True:
            try:
                await health(self)
            except Exception as e:                              # never fatal
                log.warning(json.dumps({"event": "health_probe_error", "error": repr(e)[:200]}))
            await asyncio.sleep(60)

    # --------------------------------------------------------------------------------- cache budget
    def schedule_prune(self) -> None:
        """Run the cache budget (app/cachegc.py) in a thread, at most one at a time. A no-op without CACHE_MAX_GB."""
        if self.settings.cache_max_gb <= 0 or self._pruning:
            return
        from . import cachegc

        self._pruning = True

        async def run() -> None:
            try:
                await asyncio.to_thread(cachegc.prune, self, int(self.settings.cache_max_gb * (1 << 30)))
            except Exception as e:                       # a failed prune never affects a request
                log.warning(json.dumps({"event": "cache_prune_error", "error": repr(e)[:200]}))
            finally:
                self._pruning = False

        task = asyncio.ensure_future(run())
        task.add_done_callback(lambda t: None)

    # ------------------------------------------------------------------------------------- state
    def remember_view(self, request_canon: str, key: str) -> None:
        if self.live_index.get(request_canon) == key:
            return
        self.live_index[request_canon] = key
        from .store import atomic_write

        try:
            atomic_write(self.live_index_path, json.dumps(self.live_index, sort_keys=True).encode())
        except OSError:                                   # an index write never fails a request
            pass

    def release_state(self) -> ReleaseState:
        st = ReleaseState.load(self.release_state_path)
        if not st.latest and self.snapshot is not None:
            snap = self.snapshot.root / "release_state.json"
            if snap.exists():
                st = ReleaseState.load(snap)
        return st

    def release_info(self) -> dict[str, Any]:
        st = self.release_state()
        newest = ""
        if st.latest:
            from spherex.access.watcher import pp_key
            newest = max(st.latest.values(), key=pp_key)
        return dict(release_state=dict(st.latest), newest_period=newest, checked_at=st.checked or "never")

    def freshness_text(self) -> str:
        info = self.release_info()
        if not info["newest_period"]:
            return "release watcher has not run yet"
        week = period_week_start(info["newest_period"])
        return f"Latest SPHEREx data: planning period {info['newest_period']} (≈{week:%b %Y})"

    def features(self) -> dict[str, str]:
        return dict(effective_features(self.features_cfg, self.settings.environment))

    def enabled(self, cap: str) -> bool:
        return self.features().get(cap, "off") != "off"

    @property
    def mode(self) -> str:
        s = self.settings
        if s.mock:
            return "mock"
        if s.offline:
            return "snapshot"
        if s.framesource == "fixture":
            return "fixture"
        return "live"

    def now_iso(self) -> str:
        return datetime.datetime.now(datetime.UTC).isoformat(timespec="seconds")

    def uptime_probe(self) -> float:
        return time.monotonic()


def _mp_context() -> Any:
    import multiprocessing as mp

    return mp.get_context("forkserver" if "forkserver" in mp.get_all_start_methods() else "spawn")


def _read_json(p: Path) -> dict[str, Any]:
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def snapshot_index(root: Path | None) -> dict[str, Any]:
    if root is None:
        return {}
    p = root / "index.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
