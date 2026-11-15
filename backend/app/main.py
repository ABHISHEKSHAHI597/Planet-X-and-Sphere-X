"""ParallaX API (implementation.md §5.1, `/api/v1`). Owner P.

Run:  uvicorn app.main:app --workers 1         (one worker: the job registry is in memory, implementation.md §9)
Modes (app/settings.py): live (default) · FRAMESOURCE=fixture (real pipeline on committed fixtures, no
network) · MOCK=1 (golden payloads, frontend work) · OFFLINE=1 + SNAPSHOT_DIR (demo laptop).

Capabilities behind feature flags (config/features.yaml, workflow.md §9.6) answer 404 "capability off"
when the flag is off for this environment, so a client can never reach an unaccepted science product in a
release. Routes whose science module belongs to another role answer 501 with the owner's name until it lands."""

from __future__ import annotations

import asyncio
import importlib
import json
import logging
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import httpx
import numpy as np
from fastapi import APIRouter, FastAPI, HTTPException, Query, Request, Response
from fastapi.responses import JSONResponse, PlainTextResponse, StreamingResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.gzip import GZipMiddleware

from spherex.access.retry import GaveUp
from spherex.external.tap import QueryOverflow, ServiceError
from spherex.targets import (
    NeedsUpstream,
    ResolveError,
    UpstreamError,
    coords_target,
    parse_coords,
    resolve_name,
    to_result,
)

from . import mock as mockmod
from . import schemas as S
from .candidates import HONESTY, CandidateStore, auto_checks
from .jobs import sse
from .pipeline import PlanError, plan_view, public, request_canonical, run_view
from .ratelimit import RateLimiter
from .render_png import RenderError, decode_f16, png_bytes
from .services import Services, snapshot_index
from .settings import API_VERSION, Settings
from .store import UnsafePath, find
from .upstream import describe_upstream
from .viewkey import ParamError, normalize

log = logging.getLogger("parallax")


def create_app(settings: Settings | None = None, services: Services | None = None) -> FastAPI:
    settings = settings or (services.settings if services else Settings.from_env())

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        svc = services or Services(settings)
        app.state.svc = svc
        app.state.view_limiter = RateLimiter(settings.jobs_per_minute_per_ip, 60.0)
        app.state.cand_limiter = RateLimiter(settings.candidates_per_hour_per_ip, 3600.0)
        app.state.lookup_limiter = RateLimiter(settings.lookups_per_minute_per_ip, 60.0)
        app.state.measure_limiter = RateLimiter(settings.measurements_per_minute_per_ip, 60.0)
        app.state.candidates = CandidateStore(settings.cache_dir / "candidates.sqlite")
        await svc.start()
        try:
            yield
        finally:
            await svc.close()

    app = FastAPI(
        title="ParallaX API",
        version=API_VERSION,
        lifespan=lifespan,
        description="SPHEREx blink tool API (implementation.md §5). HTTP contract: CONTRACTS.md.",
    )
    app.add_middleware(GZipMiddleware, minimum_size=1024)
    app.add_middleware(SecurityHeaders)
    app.add_middleware(AccessLog)
    r = APIRouter(prefix="/api/v1")
    _routes(r)
    app.include_router(r)

    @app.get("/healthz", response_model=S.Health, tags=["ops"])
    async def healthz(request: Request) -> Any:
        return await health(request.app.state.svc)

    @app.get("/metrics", response_class=PlainTextResponse, tags=["ops"])
    async def metrics(request: Request) -> str:
        svc: Services = request.app.state.svc
        lines = [f"parallax_{k} {v:g}" for k, v in svc.counters.snapshot().items()]
        lines += [f"parallax_jobs_{k} {v}" for k, v in svc.jobs.counters.items()]
        lines.append(f"parallax_jobs_running {svc.jobs.running()}")
        return "\n".join(lines) + "\n"

    @app.exception_handler(PlanError)
    async def plan_error(_: Request, e: PlanError) -> JSONResponse:
        return JSONResponse({"detail": str(e)}, status_code=e.status)

    @app.exception_handler(UnsafePath)
    async def unsafe_path(_: Request, e: UnsafePath) -> JSONResponse:
        return JSONResponse({"detail": str(e)}, status_code=400)

    for exc in UPSTREAM_ERRORS:
        app.add_exception_handler(exc, upstream_error)  # type: ignore[arg-type]

    return app


# An archive or catalogue service failed after its retries. A clear 503 instead of a bare 500 (audit B-09).
UPSTREAM_ERRORS: tuple[type[BaseException], ...] = (UpstreamError, GaveUp, ServiceError, QueryOverflow, httpx.HTTPError)
UPSTREAM_MESSAGE = ("An archive service this request needs (IRSA, SIMBAD, Gaia or JPL Horizons) is not answering "
                    "right now. Try again in a minute; the pinned demo targets still work.")


async def upstream_error(request: Request, e: Exception) -> JSONResponse:
    log.warning(json.dumps({"event": "upstream_error", "path": request.url.path, "error": repr(e)[:300]}))
    if isinstance(e, UpstreamError):
        detail = str(e)
    elif (what := describe_upstream(e)) is not None:
        detail = (f"{what}, so this cannot be loaded right now. That is an outage on their side; try again in a few "
                  "minutes. Pinned targets, and stars this server has opened before, still work.")
    else:
        detail = f"{UPSTREAM_MESSAGE} ({type(e).__name__})"
    return JSONResponse({"detail": detail}, status_code=503)


OVERLAY_DEADLINE_S = 45.0    # one catalogue overlay (a TAP cone is 10-17 s when the archive is healthy)
PLAN_DEADLINE_S = 60.0       # planning (resolve + coverage) never holds a request longer than this
HEALTH_FAILS_TO_DOWN = 3     # consecutive failed probes before the API serves the snapshot (audit K-01)


class SecurityHeaders(BaseHTTPMiddleware):
    """implementation.md §5.3: `frame-ancestors *` on /embed only; everything else SAMEORIGIN. Caddy serves the
    frontend with the same rule (Caddyfile); the API repeats it so a direct hit is covered too."""

    async def dispatch(self, request: Request, call_next: Any) -> Response:
        resp: Response = await call_next(request)
        if request.url.path.startswith("/embed"):
            resp.headers["Content-Security-Policy"] = "frame-ancestors *"
        else:
            resp.headers["X-Frame-Options"] = "SAMEORIGIN"
            resp.headers.setdefault("Content-Security-Policy", "frame-ancestors 'self'")
        resp.headers["X-Content-Type-Options"] = "nosniff"
        return resp


class AccessLog(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Any) -> Response:
        t0 = time.perf_counter()
        resp: Response = await call_next(request)
        svc = getattr(request.app.state, "svc", None)
        if svc is not None:
            svc.counters.inc(f"http_{resp.status_code // 100}xx")
        log.info(
            json.dumps(
                {
                    "event": "http",
                    "method": request.method,
                    "path": request.url.path,
                    "status": resp.status_code,
                    "ms": round(1000 * (time.perf_counter() - t0), 1),
                }
            )
        )
        return resp


def _svc(request: Request) -> Services:
    return request.app.state.svc  # type: ignore[no-any-return]


def limit(request: Request, kind: str) -> None:
    """Per-IP limit on every route that reaches an archive or the executor (audit K-03): `lookup` (resolve,
    coverage, overlays, ephemerides, view planning) or `measure` (native-frame fits, λ products, exports)."""
    lim = getattr(request.app.state, f"{kind}_limiter", None)
    if lim is not None:
        lim.check(request, "requests" if kind == "lookup" else "measurement requests")


def require(svc: Services, cap: str) -> None:
    if not svc.enabled(cap):
        raise HTTPException(
            404, f"capability '{cap}' is off in this environment (config/features.yaml, workflow.md §9.6)"
        )


def _science(module: str, owner: str, what: str) -> Any:
    try:
        return importlib.import_module(f"spherex.{module}")
    except ImportError:
        raise HTTPException(501, f"{what} needs spherex/{module}.py (owner {owner}); not merged yet") from None


async def health(svc: Services) -> dict[str, Any]:
    """implementation.md §3.7/§9: probe SIA2 and S3, never TAP (10–17 s even when trivial). Cached 60 s."""
    probes: list[dict[str, Any]] = []
    if svc.mode == "live" and svc.client is not None:
        now = time.monotonic()
        if svc.health_cache and now - svc.health_cache[0] < 60:
            probes = svc.health_cache[1]
        else:
            from spherex.access.coverage import SIA
            from spherex.access.http import S3_HTTPS

            checks = (
                (
                    "sia2",
                    SIA,
                    {
                        "POS": "CIRCLE 269.4461 4.7707 0.0001",
                        "COLLECTION": "spherex_qr3",
                        "RESPONSEFORMAT": "VOTABLE",
                        "MAXREC": "1",
                    },
                ),
                ("s3", S3_HTTPS, {"list-type": "2", "max-keys": "1", "prefix": "qr3/"}),
            )

            async def one(name: str, url: str, params: dict[str, str]) -> dict[str, Any]:
                t0 = time.perf_counter()
                try:
                    assert svc.client is not None
                    rr = await svc.client.get(url, params=params, timeout=10)
                    return dict(
                        name=name,
                        ok=rr.status_code < 400,
                        seconds=round(time.perf_counter() - t0, 3),
                        detail=f"HTTP {rr.status_code}",
                    )
                except Exception as e:
                    return dict(
                        name=name, ok=False, seconds=round(time.perf_counter() - t0, 3), detail=type(e).__name__
                    )

            probes = list(await asyncio.gather(*(one(*c) for c in checks)))
            svc.health_cache = (now, probes)
            # One slow answer must not switch every user to the snapshot: require consecutive failures.
            svc.health_fails = 0 if all(p["ok"] for p in probes) else getattr(svc, "health_fails", 0) + 1
        svc.irsa_down = getattr(svc, "health_fails", 0) >= HEALTH_FAILS_TO_DOWN
    from .calibration import describe

    snap_ok = svc.snapshot is not None and bool(svc.snapshot.keys())
    # A new list: the cached archive probes must not collect a snapshot and a jobs row on every call.
    probes = [
        *probes,
        dict(
            name="snapshot",
            ok=snap_ok or svc.snapshot is None,
            detail=f"{len(svc.snapshot.keys())} views" if svc.snapshot else "not configured",
        ),
        dict(name="jobs", ok=True, detail=f"{svc.jobs.running()} running"),
    ]
    ok = all(p["ok"] for p in probes) or (svc.irsa_down and snap_ok)
    mode = "snapshot" if (svc.settings.offline or (svc.irsa_down and snap_ok)) else svc.mode
    return dict(
        ok=ok,
        mode=mode,
        environment=svc.settings.environment,
        api_version=API_VERSION,
        git_sha=svc.settings.git_sha,
        calibration=describe(svc.calib_spec),
        probes=probes,
    )


def _use_snapshot(svc: Services) -> bool:
    return svc.snapshot is not None and (svc.settings.offline or svc.irsa_down)


def _manifest(svc: Services, key: str) -> tuple[dict[str, Any] | None, str]:
    m = svc.store.manifest(key)
    if m is not None:
        return m, "live"
    if svc.snapshot is not None:
        m = svc.snapshot.manifest(key)
        if m is not None:
            return m, "snapshot"
    return None, ""


def _payload_path(svc: Services, key: str, bin_id: str, band: int, ext: str) -> Any:
    try:
        p = svc.store.stack_path(key, bin_id, band, ext)
        if p.exists():
            return p
        if svc.snapshot is not None:
            p = svc.snapshot.stack_path(key, bin_id, band, ext)
            if p.exists():
                return p
    except ValueError as e:
        raise HTTPException(400, str(e)) from None
    return None


def _band_of(name: str, suffix: str) -> int:
    """`<band><suffix>` → band 1–6, else HTTP 400 (audit B-07: `abc.f16` was a 500)."""
    stem = name[: -len(suffix)] if name.endswith(suffix) else ""
    if not stem.isdigit() or not 1 <= int(stem) <= 6:
        raise HTTPException(400, f"expected <band>{suffix} with band 1–6")
    return int(stem)


def _band_limits(m: dict[str, Any], band: int) -> tuple[float, float]:
    lim = m["limits"].get(str(band))
    if not lim:
        raise HTTPException(409, "this band's shared limits are not ready yet")
    return float(lim["lo"]), float(lim["hi"])


def _routes(r: APIRouter) -> None:  # noqa: C901 — one place lists every endpoint of implementation.md §5.1

    # ------------------------------------------------------------------------------------- releases
    @r.get("/releases", response_model=S.ReleasesResponse, tags=["core"])
    async def releases(request: Request) -> Any:
        svc = _svc(request)
        info = mockmod.MOCK_RELEASE if svc.settings.mock else svc.release_info()
        env = svc.settings.environment
        snap = _use_snapshot(svc)
        return dict(
            **info,
            features=svc.features(),
            environment="snapshot" if snap and env != "mock" else env,
            snapshot=snap,
            api_version=API_VERSION,
        )

    # -------------------------------------------------------------------------------------- resolve
    @r.get("/resolve", response_model=S.ResolveResult, tags=["core"])
    async def resolve(request: Request, q: str = Query(min_length=1, max_length=200)) -> Any:
        svc = _svc(request)
        limit(request, "lookup")
        client = svc.client if (svc.settings.network and not _use_snapshot(svc)) else None
        try:
            xy = parse_coords(q)
            if xy is not None:
                from .pipeline import cached_epoch_guard

                t = coords_target(q, *xy)
                hint, label = await cached_epoch_guard(svc, xy[0], xy[1], client)
                return to_result(t, hint, label)
            from .pipeline import cached_resolve

            return to_result(await cached_resolve(svc, q, client))
        except NeedsUpstream as e:
            raise HTTPException(501, str(e)) from None
        except ResolveError as e:
            raise HTTPException(404, str(e)) from None

    # ------------------------------------------------------------------------------------- coverage
    @r.get("/coverage", response_model=S.Coverage, tags=["core"])
    async def coverage(
        request: Request,
        ra: float = Query(ge=0, lt=360),
        dec: float = Query(ge=-90, le=90),
        fov: float = Query(6.0, ge=2, le=60),
    ) -> Any:
        svc = _svc(request)
        limit(request, "lookup")
        fresh = mockmod.MOCK_RELEASE if svc.settings.mock else svc.release_info()
        if svc.settings.mock:
            return dict(
                ra=ra, dec=dec, fov=fov, n_frames=0, axis="visit", visits=[], releases=["qr2", "qr3"], freshness=fresh
            )
        if svc.coverage is None or _use_snapshot(svc):
            raise HTTPException(409, "coverage needs the archive; this server is offline")
        from spherex.access.coverage import TARGET_RADIUS_DEG
        from spherex.access.dedup import dedup
        from spherex.epochs import choose_axis, cluster_visits, time_bins

        t0 = time.perf_counter()
        try:
            rows = await asyncio.wait_for(
                svc.coverage.coverage(ra, dec, TARGET_RADIUS_DEG, release_state=svc.release_state().token()),
                PLAN_DEADLINE_S,
            )
        except TimeoutError:
            raise HTTPException(503, f"{UPSTREAM_MESSAGE} (coverage took longer than {PLAN_DEADLINE_S:.0f} s)") from None
        frames = dedup(rows, svc.registry).frames
        svc.counters.inc("coverage_seconds", time.perf_counter() - t0)
        if not frames:
            return dict(ra=ra, dec=dec, fov=fov, n_frames=0, axis="visit", visits=[], releases=[], freshness=fresh)
        mj = np.array([f.t_min for f in frames])
        axis = choose_axis(mj, cluster_visits(mj))
        tb = time_bins(mj, [f.detector for f in frames], axis)
        rel_of = {c: rr.id for rr in svc.registry.releases for c in rr.collections}
        visits: dict[str, dict[str, Any]] = {}
        for band, bins in tb.items():
            for b in bins:
                v = visits.setdefault(
                    b.id,
                    dict(
                        id=b.id,
                        status=b.status,
                        mjd_min=b.mjd_min,
                        mjd_max=b.mjd_max,
                        surveys=[],
                        frames_per_band={},
                        releases=set(),
                    ),
                )
                v["mjd_min"], v["mjd_max"] = min(v["mjd_min"], b.mjd_min), max(v["mjd_max"], b.mjd_max)
                if b.status == "full":
                    v["status"] = "full"
                v["frames_per_band"][str(band)] = len(b.idx)
                v["releases"].update(rel_of.get(frames[int(i)].collection, "?") for i in b.idx)
        out = []
        for v in sorted(visits.values(), key=lambda v: v["mjd_min"]):
            v["releases"] = sorted(v["releases"])
            out.append(v)
        return dict(
            ra=ra,
            dec=dec,
            fov=fov,
            n_frames=len(frames),
            axis=axis,
            visits=out,
            releases=sorted({rel_of.get(f.collection, "?") for f in frames}),
            freshness=fresh,
        )

    # ---------------------------------------------------------------------------------------- views
    @r.post(
        "/views", response_model=S.ViewReady | S.ViewQueued, tags=["views"], responses={202: {"model": S.ViewQueued}}
    )
    async def create_view(request: Request, response: Response) -> Any:
        svc = _svc(request)
        try:
            body = await request.json()
        except Exception:
            raise HTTPException(400, "body must be a JSON object of view parameters") from None
        if not isinstance(body, dict):
            raise HTTPException(400, "body must be a JSON object of view parameters")
        if svc.settings.mock:
            return await _mock_view(svc, body, response, request)
        if _use_snapshot(svc):
            return _snapshot_view(svc, body)
        limit(request, "lookup")
        try:
            plan = await asyncio.wait_for(plan_view(svc, body), PLAN_DEADLINE_S)
        except TimeoutError:
            raise HTTPException(503, f"{UPSTREAM_MESSAGE} (planning took longer than {PLAN_DEADLINE_S:.0f} s)") from None
        svc.remember_view(plan.request_canon, plan.key)
        from .pipeline import save_runtime_pin

        save_runtime_pin(svc, plan)
        if svc.store.complete(plan.key):
            m = svc.store.manifest(plan.key)
            assert m is not None
            m["newer_pin"] = plan.newer_pin
            m["release"] = svc.release_info()
            from .cachegc import touch_view

            touch_view(svc.store.root, plan.key)
            svc.counters.inc("views_warm")
            return dict(status="ready", manifest=public(m))
        running = svc.jobs.active(plan.key)
        if running is not None:          # already being built: share it, never count it against the limit (B-03)
            svc.jobs.counters["deduplicated"] += 1
            response.status_code = 202
            return dict(status="queued", job_id=running.id, key=plan.key)
        request.app.state.view_limiter.check(request, "new views")
        from . import cachegc

        if cachegc.free_bytes(svc.settings.cache_dir) < cachegc.MIN_FREE_BYTES:
            svc.schedule_prune()
            raise HTTPException(507, "The server's cache disk is full, so new views cannot be built right now. "
                                "Views already built, and the pinned demo targets, still open.")
        svc.counters.inc("views_cold")
        # A cold view costs ≈1 s per frame on IRSA cutouts from a laptop (G2-repro: 313-369 s for Barnard's 359
        # frames), so the time limit grows with the frame list instead of cutting big views (R Dra) off at 5 min.
        # Larger boxes take longer per frame on the cutout path (bytes ∝ area): scale past the 12′ preset's box.
        from spherex.access.frames import snap_box

        box_arcmin = snap_box(plan.centre[0], plan.centre[1], plan.grid_args[2]).size_deg * 60
        time_limit = max(svc.settings.job_timeout_s, 1.5 * len(plan.refs) * max(1.0, (box_arcmin / 18.5) ** 2))
        job = svc.jobs.start(plan.key, lambda job: run_view(svc, plan, job), timeout_s=time_limit)
        if job.task is not None:
            job.task.add_done_callback(lambda _t: svc.schedule_prune())
        response.status_code = 202
        return dict(status="queued", job_id=job.id, key=plan.key)

    @r.get("/views/{key}/manifest", response_model=S.ViewManifest, tags=["views"])
    async def get_manifest(request: Request, key: str) -> Any:
        svc = _svc(request)
        try:
            m, src = _manifest(svc, key)
        except ValueError:
            raise HTTPException(400, "bad view key") from None
        if m is None:
            raise HTTPException(404, "unknown view")
        if src == "snapshot":
            m["data_source"] = "snapshot"
        else:
            m["release"] = svc.release_info()
        return public(m)

    @r.get(
        "/jobs/{job_id}/events",
        tags=["views"],
        responses={
            200: {
                "model": S.JobEventDoc,
                "content": {"text/event-stream": {}},
                "description": "SSE: event name = type; data = the event without `type`",
            }
        },
    )
    async def job_events(request: Request, job_id: str) -> StreamingResponse:
        job = _svc(request).jobs.get(job_id)
        if job is None:
            raise HTTPException(404, "unknown or expired job")

        async def gen() -> AsyncIterator[str]:
            async for ev in job.stream():
                if await request.is_disconnected():
                    return
                yield sse(ev)

        return StreamingResponse(
            gen(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
        )

    @r.get(
        "/views/{key}/stack/{bin_id}/{name}",
        tags=["views"],
        responses={200: {"content": {"application/octet-stream": {}}}},
    )
    async def stack_payload(request: Request, key: str, bin_id: str, name: str, raw: bool = False) -> Response:
        svc = _svc(request)
        band_s, _, ext = name.partition(".")
        if not band_s.isdigit() or not 1 <= int(band_s) <= 6:
            raise HTTPException(400, "band must be 1–6")
        if ext == "filled.u8":
            require(svc, "bright_fill")
        p = _payload_path(svc, key, bin_id, int(band_s), ext)
        if p is None:
            raise HTTPException(404, "stack not ready (or unknown view, bin or payload)")
        if raw and ext == "f16":
            from spherex.render import to_f16

            raw_path = _payload_path(svc, key, bin_id, int(band_s), "f32")
            if raw_path is None:
                raise HTTPException(404, "native science stack unavailable")
            return Response(to_f16(np.frombuffer(raw_path.read_bytes(), "<f4")), media_type="application/octet-stream")
        return Response(
            p.read_bytes(),
            media_type="application/octet-stream",
            headers={"Cache-Control": "public, max-age=31536000, immutable"},
        )

    @r.get("/views/{key}/png/{bin_id}/{name}", tags=["views"], responses={200: {"content": {"image/png": {}}}})
    async def png(
        request: Request,
        key: str,
        bin_id: str,
        name: str,
        stretch: str = "asinh:8",
        lim: str = "",
        cmap: str = "gray",
        raw: bool = False,
    ) -> Response:
        """P0-8 fallback viewer. `lim=manual:lo,hi` (the client sends the manifest's shared limits); any
        other value uses the manifest's shared limits for the band. Never per-frame limits."""
        svc = _svc(request)
        band = _band_of(name, ".png")
        m, _ = _manifest(svc, key)
        if m is None:
            raise HTTPException(404, "unknown view")
        p = _payload_path(svc, key, bin_id, band, "f16")
        if p is None:
            raise HTTPException(404, "stack not ready")
        from .render_png import parse_manual

        try:
            lohi = parse_manual(lim) or _band_limits(m, band)
            image = decode_f16(p.read_bytes(), tuple(m["grid"]["shape"]))
            if raw:
                rp = _payload_path(svc, key, bin_id, band, "f32")
                if rp is None:
                    raise HTTPException(404, "science stack unavailable")
                image = np.frombuffer(rp.read_bytes(), "<f4").reshape(m["grid"]["shape"])
            data = png_bytes(image, *lohi, stretch, cmap)
        except RenderError as e:
            raise HTTPException(400, str(e)) from None
        svc.counters.inc("png_rendered")
        return Response(data, media_type="image/png", headers={"Cache-Control": "public, max-age=86400"})

    # -------------------------------------------------------------------- λ products (I → P, gated)
    @r.get("/views/{key}/diff", response_model=S.DiffInfo, tags=["science"])
    async def diff(request: Request, key: str, a: str, b: str, band: int = Query(ge=1, le=6)) -> Any:
        """G4a: off in every release until accepted (workflow.md §11.2). Never a naive visit subtraction."""
        svc = _svc(request)
        require(svc, "diff")
        limit(request, "measure")
        m, _ = _manifest(svc, key)
        if m is None:
            raise HTTPException(404, "unknown view")
        if svc.calib_spec[0] == "missing" and not find(svc, "diff_path", key, a, b, band, "json").exists():
            raise HTTPException(409, "the λ-matched difference needs the locked calibration (CALIB_ROOT)")
        from .science import diff_info

        return await diff_info(svc, m, a, b, band)

    @r.get(
        "/views/{key}/diff/{a}/{b}/{name}",
        tags=["science"],
        responses={200: {"content": {"application/octet-stream": {}}}},
    )
    async def diff_payload(request: Request, key: str, a: str, b: str, name: str) -> Response:
        svc = _svc(request)
        require(svc, "diff")
        p = find(svc, "diff_path", key, a, b, _band_of(name, ".f16"), "f16")
        if not p.exists():
            raise HTTPException(404, "difference not computed; request /diff first")
        return Response(p.read_bytes(), media_type="application/octet-stream")

    @r.get(
        "/views/{key}/cube/{bin_id}/{name}",
        tags=["science"],
        responses={200: {"content": {"application/octet-stream": {}}}},
    )
    async def cube(request: Request, key: str, bin_id: str, name: str) -> Response:
        svc = _svc(request)
        require(svc, "scrubber")
        limit(request, "measure")
        band = _band_of(name, ".f16")
        if svc.calib_spec[0] == "missing" and not find(svc, "cube_path", key, bin_id, band).exists():
            raise HTTPException(409, "cubes need the locked calibration (CALIB_ROOT)")
        from .science import cube_payload

        m, _ = _manifest(svc, key)
        if m is None:
            raise HTTPException(404, "unknown view")
        return Response(await cube_payload(svc, m, bin_id, band), media_type="application/octet-stream")

    @r.get(
        "/views/{key}/rgb/{bin_id}/{name}",
        tags=["science"],
        responses={200: {"content": {"application/octet-stream": {}}}},
    )
    async def rgb(request: Request, key: str, bin_id: str, name: str) -> Response:
        """RGB preset composite (implementation.md §7): 3 × ny × nx f16, R, G, B planes from per-pixel λ."""
        svc = _svc(request)
        require(svc, "rgb")
        if not name.endswith(".f16"):
            raise HTTPException(400, "expected <preset>.f16")
        cached = find(svc, "rgb_path", key, bin_id, name[:-4]).exists()
        if not cached:                  # a cached composite is a file read: only computing one counts as a measurement
            limit(request, "measure")
        if svc.calib_spec[0] == "missing" and not cached:
            raise HTTPException(409, "λ-range composites need the locked calibration (CALIB_ROOT)")
        from .science import rgb_payload

        m, _ = _manifest(svc, key)
        if m is None:
            raise HTTPException(404, "unknown view")
        return Response(await rgb_payload(svc, m, bin_id, name[:-4]), media_type="application/octet-stream")

    @r.get("/views/{key}/blink25", response_model=S.Blink25Response, tags=["science"])
    async def blink25(request: Request, key: str) -> Any:
        """25-year blink (P2-1, G5.25yr): 2MASS → AllWISE → NEOWISE → SPHEREx, positions only."""
        svc = _svc(request)
        require(svc, "blink25")
        from .science import blink25 as build

        m, _ = _manifest(svc, key)
        if m is None:
            raise HTTPException(404, "unknown view")
        if not find(svc, "blink25_path", key, "index.json").exists():
            # a cold build fetches dozens of archival images: it counts against the per-IP job limit like a new view
            request.app.state.view_limiter.check(request, "new 25-year blinks")
        return await build(svc, m)

    @r.get(
        "/views/{key}/blink25/{name}",
        tags=["science"],
        responses={200: {"content": {"application/octet-stream": {}}}},
    )
    async def blink25_payload(request: Request, key: str, name: str) -> Response:
        svc = _svc(request)
        require(svc, "blink25")
        try:
            p = find(svc, "blink25_path", key, name)
        except ValueError as e:
            raise HTTPException(400, str(e)) from None
        if name == "index.json" or not p.exists():
            raise HTTPException(404, "epoch not computed; request /blink25 first")
        return Response(p.read_bytes(), media_type="application/octet-stream")

    @r.get("/views/{key}/frames", response_model=S.FramesResponse, tags=["science"])
    async def frames(
        request: Request,
        key: str,
        band: int = Query(ge=1, le=6),
        sort: str = Query("lambda", pattern="^(time|lambda)$"),
    ) -> Any:
        svc = _svc(request)
        require(svc, "flip")
        limit(request, "measure")
        if svc.calib_spec[0] == "missing" and sort == "lambda" and not find(svc, "frame_path", key, band, "index.json").exists():
            raise HTTPException(409, "sorting by λ needs the locked calibration (CALIB_ROOT)")
        from .science import flipbook

        m, _ = _manifest(svc, key)
        if m is None:
            raise HTTPException(404, "unknown view")
        return await flipbook(svc, m, band, sort)

    @r.get(
        "/views/{key}/frames/{band}/{name}",
        tags=["science"],
        responses={200: {"content": {"application/octet-stream": {}}}},
    )
    async def frame_payload(request: Request, key: str, band: int, name: str) -> Response:
        """One gridded exposure of the flipbook (f16, same format and grid as the visit stacks)."""
        svc = _svc(request)
        require(svc, "flip")
        if not 1 <= band <= 6:
            raise HTTPException(400, "band must be 1-6")
        try:
            p = find(svc, "frame_path", key, band, name)
        except ValueError as e:
            raise HTTPException(400, str(e)) from None
        if name == "index.json" or not p.exists():
            raise HTTPException(404, "frame not computed; request /frames first")
        return Response(p.read_bytes(), media_type="application/octet-stream")

    # -------------------------------------------------------------------- M's science (P serves it)
    @r.get("/spectrum", response_model=S.SpectrumResponse, tags=["science"])
    async def spectrum(
        request: Request,
        ra: float = Query(ge=0, lt=360),
        dec: float = Query(ge=-90, le=90),
        track: int = 1,
        visits: str = "all",
        key: str | None = None,
    ) -> Any:
        svc = _svc(request)
        require(svc, "spectrum")
        limit(request, "measure")
        if svc.settings.mock:
            return dict(ra=ra, dec=dec, **mockmod.MOCK_SCIENCE["spectrum"])
        from . import measurement as mod

        return await _call(mod, "spectrum_api", svc, ra=ra, dec=dec, track=bool(track), visits=visits, key=key)

    @r.get("/astrometry", response_model=S.AstrometryResponse, tags=["science"])
    async def astrometry(
        request: Request,
        ra: float = Query(ge=0, lt=360),
        dec: float = Query(ge=-90, le=90),
        name: str = "",
        key: str | None = None,
    ) -> Any:
        svc = _svc(request)
        require(svc, "astrometry")
        limit(request, "measure")
        if svc.settings.mock:
            return dict(name=name or "mock", **mockmod.MOCK_SCIENCE["astrometry"])
        from . import measurement as mod

        return await _call(mod, "astrometry_api", svc, ra=ra, dec=dec, name=name, key=key)

    @r.get("/lightcurve", response_model=S.LightCurveResponse, tags=["science"])
    async def lightcurve(
        request: Request,
        ra: float = Query(ge=0, lt=360),
        dec: float = Query(ge=-90, le=90),
        bin: str = "14d",
        bands: str = "",
        method: str = Query("psf", pattern="^(psf|annulus)$"),
        release: str = Query("", pattern="^(|qr2|qr3)$"),
        key: str | None = None,
    ) -> Any:
        svc = _svc(request)
        require(svc, "lightcurve")
        limit(request, "measure")
        if svc.settings.mock:
            return mockmod.MOCK_SCIENCE["lightcurve"]
        from . import measurement as mod

        return await _call(
            mod, "lightcurve_api", svc, ra=ra, dec=dec, bin=bin, bands=bands, method=method, release=release, key=key
        )

    @r.get("/sso", response_model=S.SsoResponse, tags=["science"])
    async def sso(request: Request, name: str, mjd: str) -> Any:
        svc = _svc(request)
        require(svc, "sso")
        limit(request, "lookup")
        from . import measurement as mod

        try:
            times = [float(x) for x in mjd.split(",") if x]
        except ValueError:
            raise HTTPException(400, "mjd must contain comma-separated finite MJD numbers") from None
        if not times or len(times) > 2000 or not np.all(np.isfinite(times)):
            raise HTTPException(400, "one to 2000 finite MJD epochs required")
        return await _call(mod, "sso_api", svc, name=name, mjd=times)

    @r.get("/movers", response_model=S.MoversResponse, tags=["science"])
    async def movers(
        request: Request,
        key: str,
        mode: str = Query("stellar", pattern="^(stellar|planetx)$"),
        mu_max: float = Query(10.0, gt=0, le=1000),
    ) -> Any:
        svc = _svc(request)
        require(svc, "movers")
        limit(request, "measure")
        if mode == "planetx":
            require(svc, "planetx")
        from . import measurement as mod

        return await _call(mod, "movers_api", svc, key=key, mode=mode, mu_max=mu_max)

    @r.get("/overlays/{cat}", response_model=S.OverlayResponse, tags=["science"])
    async def overlays(
        request: Request,
        cat: str,
        ra: float = Query(ge=0, lt=360),
        dec: float = Query(ge=-90, le=90),
        r_deg: float = Query(0.1, alias="r", gt=0, le=0.5),
        mjd: float = Query(...),
    ) -> Any:
        svc = _svc(request)
        # AllWISE is drawn at its own epoch, never propagated, so it has its own capability (optimisation.md REL-5).
        require(svc, "wise_layer" if cat == "allwise" else "overlays")
        limit(request, "lookup")
        if cat not in ("gaia", "catwise", "allwise", "simbad", "sso"):
            raise HTTPException(404, "catalogue must be gaia|catwise|allwise|simbad|sso")
        from .science import overlay

        try:
            return await asyncio.wait_for(overlay(svc, cat, ra, dec, r_deg, mjd), OVERLAY_DEADLINE_S)
        except TimeoutError:
            # A catalogue cone that hangs (IRSA TAP recovering from an outage held Gaia for 300 s) must not keep the
            # checkbox spinning for minutes; the cone keeps no partial state, so the next tick simply asks again.
            src = "IRSA" if cat in ("gaia", "catwise", "allwise") else {"simbad": "SIMBAD", "sso": "SkyBoT"}[cat]
            raise HTTPException(503, f"The {cat} catalogue (via {src}) did not answer within {OVERLAY_DEADLINE_S:.0f} s. "
                                     "Untick and tick the overlay again in a few minutes.") from None

    # ------------------------------------------------------------------------------------- exports
    @r.get(
        "/export/{fmt}",
        tags=["export"],
        responses={200: {"content": {"image/gif": {}, "image/apng": {}, "application/fits": {}, "text/csv": {}}}},
    )
    async def export(
        request: Request,
        fmt: str,
        key: str,
        band: int = Query(ge=1, le=6),
        bins: str = "",
        stretch: str = "asinh:8",
        cmap: str = "gray",
        fps: float = Query(2.0, gt=0, le=30),
    ) -> Response:
        svc = _svc(request)
        require(svc, "export")
        limit(request, "measure")
        from .science import export_view

        return await export_view(svc, fmt, key, band, bins, stretch, cmap, fps)

    # ---------------------------------------------------------------------------------- candidates
    @r.post("/candidates", response_model=S.CandidateResponse, tags=["candidates"])
    async def candidates(request: Request, body: S.CandidateRequest) -> Any:
        svc = _svc(request)
        require(svc, "candidates")
        request.app.state.cand_limiter.check(request, "candidate reports")
        req = body.model_dump()
        checks = await auto_checks(svc, req)
        cid = request.app.state.candidates.add(req, checks)
        svc.counters.inc("candidates")
        return dict(id=cid, auto_checks=checks)

    @r.get("/candidates", response_model=S.CandidateGallery, tags=["candidates"])
    async def gallery(request: Request) -> Any:
        svc = _svc(request)
        require(svc, "candidates")
        if not svc.settings.public_gallery:
            raise HTTPException(403, "the public gallery is behind a moderation flag during judging")
        return dict(banner=HONESTY, candidates=request.app.state.candidates.list())


async def _call(mod: Any, fn: str, svc: Services, **kw: Any) -> Any:
    f = getattr(mod, fn, None)
    if f is None:
        raise HTTPException(
            501, f"{mod.__name__}.{fn}(svc, …) is the API entry point P calls; not provided yet (CONTRACTS.md 'M → P')"
        )
    paths = _science_cache_paths(svc, fn, kw)
    for p in paths:
        if p.exists():
            return json.loads(p.read_text(encoding="utf-8"))
    out = f(svc, **kw)
    out = _plain(await out if asyncio.iscoroutine(out) else out)
    if paths:
        # View-bound results are immutable (pinned frame list + locked calibration): cache them with the view,
        # so warm requests and offline snapshots answer without re-fitting hundreds of native frames.
        from fastapi.encoders import jsonable_encoder

        from .store import atomic_write

        try:
            atomic_write(paths[0], json.dumps(jsonable_encoder(out)).encode())
        except (TypeError, ValueError, OSError):
            pass
    return out


def _plain(x: Any) -> Any:
    """Science modules return numpy scalars and arrays (np.bool_, np.float64…), which the response models can't
    serialise; convert them to plain Python once, here, for every M route."""
    if isinstance(x, dict):
        return {k: _plain(v) for k, v in x.items()}
    if isinstance(x, list | tuple):
        return [_plain(v) for v in x]
    if isinstance(x, np.ndarray):
        return _plain(x.tolist())
    if isinstance(x, np.generic):
        return x.item()
    return x


SCIENCE_CACHE_VERSION = 2  # 2: light curves read cap-dropped frames
# Per-route bumps, so one route's change does not discard every other route's cached measurements.
SCIENCE_CACHE_ROUTE_VERSION = {"movers_api": 3}  # 3: vetoed significant movers are listed in `skipped`


def _science_cache_paths(svc: Services, fn: str, kw: dict[str, Any]) -> list[Any]:
    key = kw.get("key")
    if not key:
        return []
    import hashlib

    # Bump SCIENCE_CACHE_VERSION when a route's inputs or method change, so stale results are not served.
    version = SCIENCE_CACHE_ROUTE_VERSION.get(fn, SCIENCE_CACHE_VERSION)
    h = hashlib.sha256(json.dumps([fn, kw, version], sort_keys=True, default=str).encode()).hexdigest()[:20]
    try:
        stores = [svc.store] + ([svc.snapshot] if svc.snapshot is not None else [])
        return [s.vdir(key) / "science" / f"{fn}-{h}.json" for s in stores]
    except ValueError:
        return []


async def _mock_view(svc: Services, body: dict[str, Any], response: Response, request: Request) -> Any:
    try:
        params = normalize(body, svc.settings.max_fov_arcmin)
    except ParamError as e:
        raise HTTPException(400, str(e)) from None
    canon = request_canonical(params)
    key = mockmod.mock_key(canon)
    if svc.store.complete(key):
        m = svc.store.manifest(key)
        assert m is not None
        return dict(status="ready", manifest=public(m))
    target = None
    ra, dec = 269.4461, 4.7707
    if "q" in params:
        try:
            xy = parse_coords(params["q"])
            t = coords_target(params["q"], *xy) if xy else await resolve_name(params["q"], None)
            target, ra, dec = to_result(t), t.ra, t.dec
        except (ResolveError, NeedsUpstream) as e:
            raise HTTPException(404, str(e)) from None
    m = mockmod.manifest(key, params, target, ra, dec)
    svc.store.put_manifest(key, m)
    job = svc.jobs.start(key, lambda job: mockmod.run(svc, m, job))
    response.status_code = 202
    return dict(status="queued", job_id=job.id, key=key)


def _snapshot_view(svc: Services, body: dict[str, Any]) -> Any:
    """Offline laptop or IRSA down: serve only what the snapshot holds (implementation.md §9)."""
    try:
        params = normalize(body, svc.settings.max_fov_arcmin)
    except ParamError as e:
        raise HTTPException(400, str(e)) from None
    idx = snapshot_index(svc.snapshot.root if svc.snapshot else None)
    canon = request_canonical(params)
    key = idx.get("views", {}).get(canon) or svc.live_index.get(canon)
    if key is None and "pin" in params:
        key = idx.get("pins", {}).get(params["pin"])
    # IRSA down: a view already complete in the live cache is still served from it (audit K-01).
    if key and svc.store.complete(key):
        m = svc.store.manifest(key)
        if m is not None:
            svc.counters.inc("views_live_while_down")
            return dict(status="ready", manifest=public(m))
    m = svc.snapshot.manifest(key) if (key and svc.snapshot) else None
    if m is None:
        raise HTTPException(
            404, "This view is not in the offline snapshot (cached demo data). The pinned demo views are available."
        )
    m["data_source"] = "snapshot"
    svc.counters.inc("views_snapshot")
    return dict(status="ready", manifest=public(m))


def __getattr__(name: str) -> Any:
    """`uvicorn app.main:app` builds the app from the environment on first access (tests use create_app)."""
    if name == "app":
        globals()["app"] = create_app()
        return globals()["app"]
    raise AttributeError(name)
