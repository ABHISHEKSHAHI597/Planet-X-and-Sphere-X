"""The view job (implementation.md §2.3): resolve → coverage → dedup → plan (band first) → fetch → calibrate →
reproject → stack per (time-bin, band) → payloads + manifest, emitting SSE events as stacks finish.

Rules this module enforces (workflow.md §11.2):
  * every frame ends as stacked or as skipped *with a reason* in the manifest (fetch failures, QA, caps);
  * one shared stretch per band, from the median stack, computed after every bin of the band is stacked;
  * partial visits are labelled (and off by default in the viewer);
  * QR2 and QR3 are never mixed photometrically: a `qr_mix` warning tells the viewer to compare positions;
  * no λ is invented: without calibration, λ-dependent products refuse to run.
The manifest is written as soon as the plan exists (stacks `ready: false`) and updated as stacks land."""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any

import httpx
import numpy as np

from spherex.access.coverage import TARGET_RADIUS_DEG, half_diagonal_deg
from spherex.access.dedup import FileInfo, dedup
from spherex.access.deepfield import cap_frames
from spherex.access.failover import fetch_frames
from spherex.access.frames import FrameBox, snap_box
from spherex.access.pins import Pin, frame_list_digest, load as load_pin
from spherex.access.retry import GaveUp
from spherex.epochs import time_bins
from spherex.flags import CANONICAL_BITS, FLAG_INFO
from spherex.grid import make_grid, pixel_scale_for
from spherex.render import FORMAT_F16, FORMAT_F32, FORMAT_U32_FLAGS, shared_limits
from spherex.types import FrameRef, TimeBin

from spherex.targets import (
    is_bright,
    NeedsUpstream,
    ResolveError,
    Target,
    UpstreamError,
    coords_target,
    epoch_guard,
    parse_coord_pair,
    parse_coords,
    resolve_name,
    to_result,
)
from .jobs import Job
from .viewkey import PIPELINE_VERSION, ParamError, canonical, normalize, round_deg, selected_band, view_key
from .worker import StackResult, stack_task

log = logging.getLogger("parallax.pipeline")
_BACKGROUND: set[asyncio.Future[Any]] = set()


def _settle(f: asyncio.Future[Any]) -> None:
    """Done-callback of a background task: drop the strong reference and retrieve any exception (a failed
    informational check is not an error, and an unretrieved one would be logged as one)."""
    _BACKGROUND.discard(f)
    if not f.cancelled():
        f.exception()


NEWER_CHECK_S = 2.0          # pinned views: longest the "newer data?" hint may delay a view (frame_list)
API_FIELDS_ONLY = ("_complete", "_request", "_plan", "_refs")


class PlanError(ValueError):
    """The request is valid but can't be planned (no coverage, offline without a snapshot, …): HTTP 409/404."""

    def __init__(self, msg: str, status: int = 409) -> None:
        super().__init__(msg)
        self.status = status


@dataclass
class Plan:
    key: str
    pin: str
    params: dict[str, str]
    compute: dict[str, str]
    request_canon: str
    target: Target
    centre: tuple[float, float]
    grid_args: tuple[float, float, float, float]
    refs: list[FrameRef]
    plan_skipped: dict[str, str]
    bins: dict[int, list[TimeBin]]
    axis: str
    preset: str
    band_first: int
    track_centres: dict[str, tuple[float, float]] | None
    warnings: list[dict[str, str]] = field(default_factory=list)
    newer_pin: str | None = None
    pinned: bool = False
    coverage_query: dict[str, Any] | None = None   # where an un-pinned frame list came from (runtime pins)


def request_canonical(params: dict[str, str]) -> str:
    """The request without its frame list: used by snapshot indexes (offline laptops can't run coverage)."""
    keep = {
        k: params[k]
        for k in ("q", "ra", "dec", "fov", "px", "axis", "center", "mask", "rel", "lim", "pin")
        if k in params
    }
    if "q" in keep:
        keep["q"] = keep["q"].strip().lower()
    return canonical(keep)


RESOLVE_TTL_S = 7 * 86400
UPSTREAM_FAILURES = (UpstreamError, GaveUp, httpx.HTTPError)


async def cached_resolve(svc: Any, query: str, client: Any) -> Target:
    """Name -> Target, cached on disk for RESOLVE_TTL_S (SIMBAD + Gaia via IRSA TAP cost 10-30 s per call,
    which would make every warm view cold; implementation.md §2.3, §10.3). Degraded answers (offline-table
    fallback) and Solar-System bodies are never cached."""
    import hashlib
    import json

    from spherex.targets import normalize_query

    from .store import atomic_write

    norm = normalize_query(query).lower()
    path = svc.settings.cache_dir / "resolve" / (hashlib.sha256(norm.encode()).hexdigest()[:24] + ".json")
    if client is not None and path.exists():
        try:
            d = json.loads(path.read_text(encoding="utf-8"))
            if time.time() - d["t"] < RESOLVE_TTL_S:
                t = Target(**d["target"])
                t.query = query
                return t
        except (OSError, ValueError, KeyError, TypeError):   # corrupt or older entry: resolve again (K-37)
            pass
    last = path.with_suffix(".last.json")   # the newest answer of any quality: used only while SIMBAD is down
    try:
        t = await resolve_name(query, client)
    except UPSTREAM_FAILURES:
        for p in (path, last):
            try:
                d = json.loads(p.read_text(encoding="utf-8"))
                t = Target(**d["target"])
            except (OSError, ValueError, KeyError, TypeError):
                continue
            t.query = query
            t.extra["warning"] = ("SIMBAD is not answering: position and motion from the lookup saved on "
                                  f"{time.strftime('%Y-%m-%d', time.gmtime(d['t']))}")
            return t
        raise
    if client is not None and t.kind == "star":
        doc = json.dumps(dict(t=time.time(), target=t.__dict__)).encode()
        atomic_write(last, doc)
        if not t.extra.get("warning"):
            atomic_write(path, doc)
    return t


EPOCH_GUARD_TTL_S = 86400
EPOCH_GUARD_DEADLINE_S = 8.0


async def cached_epoch_guard(svc: Any, ra: float, dec: float, client: Any) -> tuple[Any, Any]:
    """(hint, label) of `epoch_guard` for typed coordinates, cached on disk for a day by position (1e-4°), and
    never waiting more than EPOCH_GUARD_DEADLINE_S for SIMBAD: past that the offline table answers (audit K-19;
    the cone was repeated on every coordinate view and band switch, up to 4 minutes when SIMBAD hung)."""
    import hashlib
    import json

    from .store import atomic_write

    path = svc.settings.cache_dir / "epoch_guard" / (
        hashlib.sha256(f"{ra:.4f},{dec:.4f}".encode()).hexdigest()[:24] + ".json")
    if client is not None:
        try:
            d = json.loads(path.read_text(encoding="utf-8"))
            if time.time() - d["t"] < EPOCH_GUARD_TTL_S:
                return d["hint"], d["label"]
        except (OSError, ValueError, KeyError):
            pass
    degraded = False
    try:
        _, hint, label = await asyncio.wait_for(epoch_guard(ra, dec, client), EPOCH_GUARD_DEADLINE_S)
    except TimeoutError:
        _, hint, label = await epoch_guard(ra, dec, None)
        degraded = True
    if client is not None and not degraded:
        try:
            atomic_write(path, json.dumps(dict(t=time.time(), hint=hint, label=label)).encode())
        except OSError:
            pass
    return hint, label


FROZEN_TARGETS = "targets.json"


def frozen_target(svc: Any, pin_id: str, query: str) -> Target | None:
    """The target a committed pin was reviewed with (config/pins/targets.json, written by scripts/freeze_targets.py).
    A pin freezes the frame list, but the view key also depends on the resolved position; with the target frozen
    too, a pinned demo link gives the same key whatever SIMBAD or Gaia answer today, and when they do not answer at
    all (advanced_research.md A2: Gaia DR4 lands on 2026-12-02, inside the judging window)."""
    import json

    from spherex.targets import identifier

    try:
        doc = json.loads((svc.settings.pins_dir / FROZEN_TARGETS).read_text(encoding="utf-8"))
        hit = doc["targets"][pin_id][identifier(query).lower()]
        t = Target(**hit)
    except (OSError, ValueError, KeyError, TypeError, AttributeError):   # no file, no entry, or an older layout
        return None
    t.query = query
    return t


async def resolve_target(svc: Any, params: dict[str, str]) -> Target:
    client = svc.client if svc.settings.network else None
    try:
        if "q" in params:
            xy = parse_coords(params["q"])
            if xy is None:
                frozen = frozen_target(svc, params["pin"], params["q"]) if params.get("pin") else None
                return frozen or await cached_resolve(svc, params["q"], client)
            t = coords_target(params["q"], *xy)
        else:
            xy = parse_coord_pair(params["ra"], params["dec"])
            t = coords_target(f"{params['ra']} {params['dec']}", *xy)
        # P0-1: typed coordinates of a high-PM object at another epoch get the banner hint in the manifest
        # (display only: never part of the view key).
        hint, label = await cached_epoch_guard(svc, xy[0], xy[1], client)
        t.extra.update(epoch_hint=hint, label_hint=label)
        return t
    except NeedsUpstream as e:
        raise PlanError(str(e), 501) from None
    except ResolveError as e:
        raise PlanError(str(e), 404) from None
    except UpstreamError as e:
        raise PlanError(str(e), 503) from None


def calibration_tag(svc: Any) -> str:
    from .calibration import tag

    return tag(getattr(svc, "calib_spec", ("missing", "")))


def collections_for(svc: Any, rel: str) -> list[str]:
    if rel == "auto":
        return list(svc.registry.collections())
    try:
        return list(svc.registry.release(rel).collections)
    except KeyError:
        raise PlanError(
            f"unknown release {rel!r}; config/releases.yaml lists {[r.id for r in svc.registry.releases]}", 400
        ) from None


async def frame_list(
    svc: Any, params: dict[str, str], target: Target
) -> tuple[list[FrameRef], Pin | None, str | None, list[dict[str, str]]]:
    """(frames, pin, newer_pin, warnings). Pinned views read config/pins/<pin>.json and never change."""
    warnings: list[dict[str, str]] = []
    if "pin" in params:
        pin = find_pin(svc, params["pin"])
        refs = pin.frames
        _check_pin_field(pin, target)
        newer = None
        pp = pin.doc.get("params", {})
        if svc.coverage is not None and not svc.settings.offline and "ra" in pp and "dec" in pp:
            # Informational only ("newer data exists"), so it must never hold the view up: a cold IRSA SIA2
            # answer takes 4-30 s. Bounded at NEWER_CHECK_S; past that the query finishes in the background,
            # fills the 24 h coverage cache, and the next open of this pin shows the hint.
            check = asyncio.ensure_future(svc.coverage.coverage(
                float(pp["ra"]),
                float(pp["dec"]),
                float(pp.get("radius_deg", TARGET_RADIUS_DEG)),
                list(pp.get("collections") or svc.registry.collections()),
                release_state=svc.release_state().token(),
            ))
            try:
                rows = await asyncio.wait_for(asyncio.shield(check), NEWER_CHECK_S)
                cur = dedup(rows, svc.registry).frames
                if cur and frame_list_digest(f.access_url for f in cur)[:12] != pin.pin:
                    newer = frame_list_digest(f.access_url for f in cur)[:12]
                    warnings.append(
                        dict(
                            code="newer_data",
                            severity="info",
                            message=f"Newer data is available for this view (pin {newer}); this "
                            "pinned link keeps showing its frozen frame list.",
                        )
                    )
            except TimeoutError:      # still running: let it finish (and cache) on its own
                _BACKGROUND.add(check)                     # asyncio keeps only weak references to tasks
                check.add_done_callback(_settle)
            except Exception as e:  # coverage down: the pinned view still works
                warnings.append(
                    dict(
                        code="newer_check_failed",
                        severity="info",
                        message=f"Could not check for newer data ({type(e).__name__}).",
                    )
                )
        return refs, pin, newer, warnings
    if svc.coverage is None:
        raise PlanError(
            "this server has no coverage service (offline or fixture mode): open a pinned link "
            "or a view from the offline snapshot",
            409,
        )
    if target.kind == "sso":
        from spherex.external.horizons import positions

        times = np.arange(60796.0, _mjd_now() + 1, 14.0).tolist()
        xy = await positions(svc.client, target.extra["command"], times)
        radius, colls = half_diagonal_deg(float(params["fov"])), collections_for(svc, params["rel"])

        async def near(t: float, a: float, d: float) -> list[Any]:
            found = await svc.coverage.coverage(a, d, radius, colls, release_state=svc.release_state().token())
            return [r for r in found if abs(float(r.t_min) - t) <= 14]

        # Concurrent (the host limiter still caps IRSA at 4 in flight); each answer is cached 24 h.
        rows = [r for part in await asyncio.gather(*(near(t, a, d) for t, (a, d) in zip(times, xy, strict=True)))
                for r in part]
        frames = dedup(rows, svc.registry).frames
        if not frames:
            raise PlanError("No moving-path coverage in configured releases", 404)
        return frames, None, None, warnings
    now_ra, now_dec = (float(v[0]) for v in target.pos([_mjd_now()]))
    radius = TARGET_RADIUS_DEG if target.kind == "star" else half_diagonal_deg(float(params["fov"]))
    target.extra["_coverage_query"] = dict(ra=now_ra, dec=now_dec, radius_deg=radius)
    rows = await svc.coverage.coverage(
        now_ra, now_dec, radius, collections_for(svc, params["rel"]), release_state=svc.release_state().token()
    )
    if svc.coverage.last.get("warning"):
        code = "coverage_stale" if svc.coverage.last.get("service") == "stale-cache" else "coverage_fallback"
        warnings.append(dict(code=code, severity="warn", message=svc.coverage.last["warning"]))
    res = dedup(rows, svc.registry)
    if not res.frames:
        raise PlanError("SPHEREx has no frames covering this position in the configured releases yet. The quick "
                        "releases do not cover the whole sky; try a nearby position or one of the five targets.", 404)
    return res.frames, None, None, warnings


PIN_FIELD_TOLERANCE_DEG = 0.5


def runtime_pins_dir(svc: Any) -> Any:
    """Pins of views planned on this server (audit B-05): config/pins holds only the reviewed demo pins, so a shared
    pinned link to any other view used to answer 404. Same immutable format, kept with the cache."""
    return svc.settings.cache_dir / "pins"


def find_pin(svc: Any, pin_id: str) -> Pin:
    """config/pins (reviewed, committed) first, then this server's runtime pins."""
    errors = []
    for root in (svc.settings.pins_dir, runtime_pins_dir(svc)):
        try:
            return load_pin(pin_id, root)
        except Exception as e:  # PinError (unknown or bad file) or an unreadable file
            errors.append(str(e))
    raise PlanError(f"unknown pin {pin_id}: it is neither a committed demo pin nor a view built on this server", 404)


def save_runtime_pin(svc: Any, plan: Plan) -> None:
    """Freeze an un-pinned view's frame list as a pin, so its Share link works (the manifest's `pin`). Never fails a
    request. Solar System views are frozen without a position: their frames follow an ephemeris, not one field."""
    if plan.pinned or not plan.refs:
        return
    from spherex.access.pins import make_pin, save

    try:
        params: dict[str, Any] = dict(target=plan.target.main_id or plan.target.name, fov=float(plan.params["fov"]),
                                      center=plan.params["center"], rel=plan.params["rel"],
                                      collections=collections_for(svc, plan.params["rel"]))
        if plan.coverage_query is not None:
            params.update(plan.coverage_query)
        pin = make_pin(plan.refs, svc.registry, params, dict(coverage="live SIA2 at view planning (runtime pin)",
                                                              view_key=plan.key))
        if pin.pin == plan.pin:
            save(pin, runtime_pins_dir(svc))
    except Exception as e:  # noqa: BLE001 — a missing pin costs the Share link, never the view
        log.warning("runtime pin for %s not saved: %r", plan.key, e)


def _check_pin_field(pin: Pin, target: Target) -> None:
    """A pin is a frame list for one field. Combined with a target elsewhere it would build an empty view of
    hundreds of skipped frames (audit B-08), so refuse it. Pins without a recorded position are accepted."""
    pp = pin.doc.get("params") or {}
    try:
        pra, pdec = float(pp["ra"]), float(pp["dec"])
    except (KeyError, TypeError, ValueError):
        return
    if target.kind == "sso":
        return
    mjd = pin.doc.get("mjd_range") or [_mjd_now()]
    ra, dec = (float(v[0]) for v in target.pos([float(np.mean(mjd))]))
    from spherex.targets import sep_arcsec

    sep = sep_arcsec(ra, dec, pra, pdec) / 3600
    if sep > PIN_FIELD_TOLERANCE_DEG:
        raise PlanError(f"pin {pin.pin} is the frame list of another field ({sep:.1f}° from this target); "
                        "open the target without the pin", 409)


def _mjd_now() -> float:
    from spherex.targets import mjd_now

    return mjd_now()


def apply_cap(refs: list[FrameRef], axis: str, cap_total: int) -> tuple[list[FrameRef], dict[str, str]]:
    """implementation.md §9: ≤ 600 frames per view. D's `deepfield.cap_frames` keeps at most c frames per
    (time-bin, detector), evenly spaced in time; c is the largest value that fits the total. Dropped
    frames are listed as skipped with the cap reason (never silent)."""
    if len(refs) <= cap_total:
        return refs, {}
    tb = time_bins([f.t_min for f in refs], [f.detector for f in refs], axis)
    bin_of = {}
    for band, bins in tb.items():
        for b in bins:
            for i in b.idx:
                bin_of[refs[int(i)].access_url] = b.id
    lo, hi = 1, max(len(refs), 1)
    best: tuple[list[FrameRef], list[tuple[str, str]]] = cap_frames(refs, lambda f: bin_of[f.access_url], 1)
    while lo <= hi:  # largest per-group cap within the total
        mid = (lo + hi) // 2
        kept, dropped = cap_frames(refs, lambda f: bin_of[f.access_url], mid)
        if len(kept) <= cap_total:
            best, lo = (kept, dropped), mid + 1
        else:
            hi = mid - 1
    return best[0], dict(best[1])


async def plan_view(svc: Any, raw: dict[str, Any]) -> Plan:
    try:
        params = normalize(raw, svc.settings.max_fov_arcmin)
    except ParamError as e:
        raise PlanError(str(e), 400) from None
    target = await resolve_target(svc, params)
    track_note = None
    if target.kind == "sso" and params["center"] != "track":
        # A Solar System body is only meaningful centred on its ephemeris; typing "Pluto" must just work (K-20).
        params = dict(params, center="track")
        track_note = dict(code="sso_track", severity="info",
                          message="Solar System body: every frame is centred on its JPL Horizons position as seen "
                          "from SPHEREx (track mode), so it stays still while the stars stream past.")
    refs, pin, newer, warnings = await frame_list(svc, params, target)
    if track_note:
        warnings.insert(0, track_note)
    if target.kind == "sso":
        from spherex.external.horizons import positions

        times = sorted({f.t_min for f in refs} | {_mjd_now()})
        xy = await positions(svc.client, target.extra["command"], times)
        target.extra["ephemeris"].update({str(t): v for t, v in zip(times, xy, strict=True)})
    axis = params["axis"]
    if axis == "multi":
        warnings.append(dict(code="axis_multi", severity="info", message="axis=multi is not built yet; showing visits"))
        axis = "visit"
    if axis == "auto":
        from spherex.epochs import choose_axis, cluster_visits

        mj = np.array([f.t_min for f in refs])
        axis = choose_axis(mj, cluster_visits(mj))
    dropped: dict[str, str] = {}
    if len(refs) > svc.settings.max_frames_per_view:
        all_refs = refs
        refs, dropped = apply_cap(refs, axis, svc.settings.max_frames_per_view)
        warnings.append(
            dict(
                code="frames_capped",
                severity="warn",
                message=f"{len(dropped)} of {len(all_refs)} frames were left out to respect the "
                f"{svc.settings.max_frames_per_view}-frame limit per view; each is listed "
                "with its reason.",
            )
        )
        refs = sorted(refs + [f for f in all_refs if f.id in dropped], key=lambda f: (f.t_min, f.obs_id, f.detector))
    bins = time_bins([f.t_min for f in refs], [f.detector for f in refs], axis)
    mjd = np.array([f.t_min for f in refs])
    if target.kind == "sso":
        from spherex.external.horizons import positions

        times = sorted({float(np.median(mjd))} | {b.mjd_mean for bs in bins.values() for b in bs})
        xy = await positions(svc.client, target.extra["command"], times)
        target.extra["ephemeris"].update({str(t): v for t, v in zip(times, xy, strict=True)})
    fov = float(params["fov"])
    pix = pixel_scale_for(fov, float(params["px"]))
    track = params["center"] == "track"
    ra_c, dec_c = (float(v[0]) for v in target.pos([float(np.median(mjd))]))
    track_centres = None
    if track:
        if not target.moving:
            warnings.append(
                dict(
                    code="track_static",
                    severity="info",
                    message="Track mode on a fixed position is the same as fixed sky.",
                )
            )
        else:
            ra_t, dec_t = target.pos(mjd)
            track_centres = {f.id: (float(a), float(b)) for f, a, b in zip(refs, ra_t, dec_t)}
    preset = params["mask"]
    if preset == "auto":
        preset = "bright" if is_bright(target) else "discovery"
    compute = dict(
        target=target.main_id or "coords",
        ra=round_deg(ra_c),
        dec=round_deg(dec_c),
        fov=params["fov"],
        px=f"{pix:g}",
        axis=axis,
        center=params["center"],
        mask=preset,
        rel=params["rel"],
        lim=params["lim"],
        pv=PIPELINE_VERSION,
        cal=str(getattr(svc, "calib_tag", "") or calibration_tag(svc)),
        fill="1" if svc.enabled("bright_fill") else "0",
    )
    canon = canonical(compute)
    key = view_key(canon, [f.access_url for f in refs])
    if target.extra.get("warning"):
        warnings.append(dict(code="resolver_degraded", severity="warn", message=target.extra["warning"]))
    if target.extra.get("quality_warning"):
        warnings.append(dict(code="astrometry_quality", severity="warn", message=target.extra["quality_warning"]))
    return Plan(
        key=key,
        pin=frame_list_digest(f.access_url for f in refs)[:12],
        params=params,
        compute=compute,
        request_canon=request_canonical(params),
        target=target,
        centre=(ra_c, dec_c),
        grid_args=(ra_c, dec_c, fov, pix),
        refs=refs,
        plan_skipped=dropped,
        bins=bins,
        axis=axis,
        preset=preset,
        band_first=selected_band(params["bands"]),
        track_centres=track_centres,
        warnings=warnings,
        newer_pin=newer,
        pinned=pin is not None,
        coverage_query=target.extra.pop("_coverage_query", None),
    )


# ------------------------------------------------------------------------------------------- manifest


def grid_info(grid_args: tuple[float, float, float, float]) -> dict[str, Any]:
    g = make_grid(*grid_args)
    w = g.wcs.wcs
    return dict(
        ctype=[str(w.ctype[0]), str(w.ctype[1])],
        crval=[float(w.crval[0]), float(w.crval[1])],
        crpix=[float(w.crpix[0]), float(w.crpix[1])],
        cdelt=[float(w.cdelt[0]), float(w.cdelt[1])],
        shape=[int(g.shape[0]), int(g.shape[1])],
        pix_arcsec=float(g.pix_arcsec),
        native=bool(g.native),
    )


def bin_info(b: TimeBin) -> dict[str, Any]:
    return dict(
        id=b.id,
        band=int(b.band),
        status=b.status,
        mjd_mean=b.mjd_mean,
        mjd_min=b.mjd_min,
        mjd_max=b.mjd_max,
        surveys=list(b.surveys),
        label=b.label,
        n_frames=int(len(b.idx)),
        n_visit_frames=int(b.n_visit_frames),
    )


def skeleton(svc: Any, plan: Plan, data_source: str = "live") -> dict[str, Any]:
    bands = sorted(plan.bins)
    stacks = []
    for band in bands:
        for b in plan.bins[band]:
            ids = [plan.refs[int(i)].id for i in b.idx]
            stacks.append(
                dict(
                    bin=b.id,
                    band=band,
                    ready=False,
                    format=FORMAT_F16,
                    nhits_max=0,
                    filled=False,
                    skipped=[[i, plan.plan_skipped[i]] for i in ids if i in plan.plan_skipped],
                    frame_ids=[],
                )
            )
    frames = []
    bin_of = {plan.refs[int(i)].id: b.id for band in bands for b in plan.bins[band] for i in b.idx}
    for f in plan.refs:
        fi = FileInfo.parse(f.access_url)
        rel = svc.registry.release_for_collection(f.collection)
        frames.append(
            dict(
                id=f.id,
                band=f.detector,
                detector=f.detector,
                bin=bin_of.get(f.id, "?"),
                mjd=f.t_min,
                survey=None,
                obsid=f.obs_id,
                release=rel.id if rel else "?",
                collection=f.collection,
                pipeline=f"v{fi.version}" if fi else "?",
                qa={},
                skipped=plan.plan_skipped.get(f.id),
            )
        )
    track = []
    if plan.target.moving:
        for band in bands:
            for b in plan.bins[band]:
                ra, dec = plan.target.pos([b.mjd_mean])
                track.append(dict(bin=b.id, band=band, mjd=b.mjd_mean, ra=float(ra[0]), dec=float(dec[0])))
    warnings = list(plan.warnings)
    if svc.calib_spec[0] == "missing":
        warnings.append(
            dict(
                code="calibration_missing",
                severity="info",
                message="Wavelength calibration is not loaded on this server: visit stacks are exact, "
                "but cubes, differences and spectra are unavailable.",
            )
        )
    for band in bands:
        if plan.bins[band] and all(b.status == "partial" for b in plan.bins[band]):
            warnings.append(
                dict(
                    code="partial_only",
                    severity="warn",
                    message=f"Band {band} has only partial visits here: shallower than a full visit.",
                )
            )
    return dict(
        schema_version=svc_api_version(),
        key=plan.key,
        pin=plan.pin,
        newer_pin=plan.newer_pin,
        params=dict(plan.params, mask_resolved=plan.preset),   # `mask=auto` resolved for this target (display)
        target=to_result(plan.target, plan.target.extra.get("epoch_hint"), plan.target.extra.get("label_hint")),
        grid=grid_info(plan.grid_args),
        axis=plan.axis,
        bands=bands,
        bins={str(b): [bin_info(x) for x in plan.bins[b]] for b in bands},
        stacks=stacks,
        limits={},
        frames=frames,
        track=track,
        flags=dict(bits=dict(CANONICAL_BITS), info=dict(FLAG_INFO), format=FORMAT_U32_FLAGS),
        formats=dict(stack=FORMAT_F16, science=FORMAT_F32, flags=FORMAT_U32_FLAGS),
        release=svc.release_info(),
        warnings=warnings,
        data_source=data_source,
        _complete=False,
        _request=plan.request_canon,
        _plan=dict(
            grid_args=list(plan.grid_args),
            preset=plan.preset,
            compute=plan.compute,
            track_centres=plan.track_centres,
            target=plan.target.__dict__,
        ),
        _refs=[
            dict(
                access_url=f.access_url,
                s3_key=f.s3_key,
                collection=f.collection,
                obs_id=f.obs_id,
                detector=f.detector,
                t_min=f.t_min,
            )
            for f in plan.refs
        ],
    )


def svc_api_version() -> str:
    from .settings import API_VERSION

    return API_VERSION


def public(m: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in m.items() if k not in API_FIELDS_ONLY}


# ------------------------------------------------------------------------------------------------ run


async def run_view(svc: Any, plan: Plan, job: Job) -> None:
    store = svc.store
    m = skeleton(svc, plan)
    _carry_over_ready(store, plan.key, m)
    store.put_manifest(plan.key, m)
    if svc.source is None:
        raise PlanError("no FrameSource on this server (offline): only snapshot views can be shown", 409)
    t0 = time.perf_counter()
    job.emit({"type": "planned", "n": len(plan.refs)})
    order = [plan.band_first] + [b for b in sorted(plan.bins) if b != plan.band_first]
    order = [b for b in order if b in plan.bins]
    centre_box = snap_box(plan.centre[0], plan.centre[1], plan.grid_args[2])
    fov = plan.grid_args[2]

    def box(ref: FrameRef) -> FrameBox:
        if plan.track_centres and ref.id in plan.track_centres:
            return snap_box(*plan.track_centres[ref.id], fov)
        return centre_box

    n_total = len(plan.refs) - len(plan.plan_skipped)
    fetched = 0
    bytes_by_source: dict[str, int] = {}
    loop = asyncio.get_running_loop()
    first_stack_s: float | None = None
    frame_meta = {f["id"]: f for f in m["frames"]}
    all_skipped = 0
    scales_seen: set[str] = set()
    frames_by_source: dict[str, int] = {}

    def on_done(i: int, n: int, o: Any) -> None:
        nonlocal fetched
        fetched += 1
        if o.source:
            bytes_by_source[o.source] = bytes_by_source.get(o.source, 0) + int(o.bytes or 0)
            frames_by_source[o.source] = frames_by_source.get(o.source, 0) + 1
        job.emit({"type": "fetched", "i": fetched, "n": n_total})

    # One fetch stream for the whole view, in band order (selected band first) and bin order within a band.
    # Each time bin is stacked the moment its last frame arrives and shown at once (stack_ready), instead of
    # waiting for its whole band to download and every other bin of the band to stack. Display limits are
    # shared per band (one blink, one stretch): they are recomputed from the bins stacked so far and written
    # with each, so the first visit is drawn with real limits; the last update equals the band's final limits
    # (pixelwise median over its bins, then ZScale: independent of completion order). Solar-System targets
    # stack per band, because their frame centres come from one Horizons call per band.
    # The selected band is stacked first: stacking is CPU work shared under one GIL, so other bands' bins wait
    # until its bins are done (frames keep arriving meanwhile). From the frame cache that brings the first image
    # from ~20 s to ~4 s (Barnard, 359 frames); on a cold build fetching is the bottleneck and the gate rarely waits.
    bins_in_order = [(band, b) for band in order for b in plan.bins[band]]
    ref_bin: dict[str, tuple[int, str]] = {}
    want: list[FrameRef] = []
    remaining: dict[tuple[int, str], int] = {}
    band_left: dict[int, int] = {band: 0 for band in order}
    for band, b in bins_in_order:
        n = 0
        for i in b.idx:
            ref = plan.refs[int(i)]
            if ref.id in plan.plan_skipped:
                continue
            ref_bin[ref.id] = (band, b.id)
            want.append(ref)
            n += 1
        remaining[(band, b.id)] = n
        band_left[band] += n
    by_id = {(band, b.id): b for band, b in bins_in_order}
    got: dict[str, Any] = {}
    results_by_band: dict[int, dict[str, StackResult]] = {band: {} for band in order}
    stack_tasks: list[asyncio.Future[None]] = []
    is_sso = plan.target.kind == "sso"
    timing = {"fetch_s": 0.0, "stack_s": 0.0}
    first_band = order[0] if order else None
    first_left = len(plan.bins[first_band]) if first_band is not None else 0
    first_done = asyncio.Event()
    if first_left == 0:
        first_done.set()

    async def stack_bin(band: int, b: TimeBin) -> None:
        nonlocal first_left
        if band != first_band:
            await first_done.wait()
        try:
            await _stack_bin(band, b)
        finally:
            if band == first_band:
                first_left -= 1
                if first_left <= 0:
                    first_done.set()

    async def _stack_bin(band: int, b: TimeBin) -> None:
        nonlocal first_stack_s, all_skipped
        ids = [plan.refs[int(i)].id for i in b.idx]
        raws = [got[i].frame for i in ids if i in got and got[i].frame is not None]
        pre = [(i, plan.plan_skipped[i]) for i in ids if i in plan.plan_skipped]
        pre += [(i, got[i].skipped_reason or "not fetched") for i in ids if i in got and got[i].frame is None]
        tc = {i: plan.track_centres[i] for i in ids if plan.track_centres and i in plan.track_centres} or None
        try:
            r: StackResult = await loop.run_in_executor(
                svc.executor, stack_task, raws, b, plan.grid_args, plan.preset, svc.calib_spec, pre, tc,
                plan.centre if svc.enabled("bright_fill") else None,
            )
        except Exception as e:  # one bin must not fail the view (K-17): an empty stack, every frame listed
            log.exception("stack of %s/%s failed", b.id, band)
            why = f"stack failed: {type(e).__name__}: {e}"[:200]
            fetched_ids = [i for i in ids if i in got and got[i].frame is not None]
            r = await loop.run_in_executor(
                svc.executor, stack_task, [], b, plan.grid_args, plan.preset, svc.calib_spec,
                pre + [(i, why) for i in fetched_ids], None, None,
            )
        for i in ids:                # the raw frames of this bin are no longer needed: free them (audit B-06)
            got.pop(i, None)
        del raws
        done = results_by_band[band]
        done[r.bin] = r
        bin_rank = {x.id: k for k, x in enumerate(plan.bins[band])}
        ordered = [done[k] for k in sorted(done, key=lambda k: bin_rank.get(k, 0))]
        lim = plan.params["lim"]
        lo, hi = shared_limits([x.median_sample for x in ordered], lim)
        m["limits"][str(band)] = dict(lo=lo, hi=hi, lim=lim)
        store.put_stack(plan.key, r.bin, r.band, r.payloads)
        r.payloads = {}              # written; keep only what the shared limits need (median_sample)
        st = next(x for x in m["stacks"] if x["bin"] == r.bin and x["band"] == r.band)
        st.update(ready=True, nhits_max=r.nhits_max, filled=r.filled, frame_ids=r.frame_ids,
                  skipped=[[a, c] for a, c in r.skipped], transients=r.transients)
        scales_seen.update(r.scales)
        for fr in r.frames:
            fm = frame_meta.get(fr.id)
            if fm is not None:
                fm.update(mjd=fr.mjd, survey=fr.survey, obsid=fr.obsid or fm["obsid"], qa=fr.qa, skipped=fr.skipped)
        for fid, why in r.skipped:
            if frame_meta.get(fid) is not None and frame_meta[fid]["skipped"] is None:
                frame_meta[fid]["skipped"] = why
        all_skipped += len(r.skipped)
        store.put_manifest(plan.key, m)
        job.emit({"type": "stack_ready", "bin": r.bin, "band": r.band})
        if first_stack_s is None:
            first_stack_s = time.perf_counter() - t0

    async def stack_band_sso(band: int) -> None:
        from spherex.external.horizons import positions

        outs = [got[f.id] for f in want if ref_bin[f.id][0] == band and f.id in got]
        times = sorted({float(o.frame.hdus["IMAGE"][0]["MJD-AVG"]) for o in outs if o.frame is not None})
        if times:
            xy = await positions(svc.client, plan.target.extra["command"], times)
            plan.target.extra["ephemeris"].update({str(t): v for t, v in zip(times, xy, strict=True)})
        for o in outs:
            if o.frame is not None and plan.track_centres is not None:
                t = float(o.frame.hdus["IMAGE"][0]["MJD-AVG"])
                a, d = plan.target.pos([t])
                plan.track_centres[o.ref.id] = (float(a[0]), float(d[0]))
        await asyncio.gather(*(stack_bin(band, b) for b in plan.bins[band]))

    def dispatch(band: int, bin_id: str) -> None:
        if not is_sso:
            stack_tasks.append(asyncio.ensure_future(stack_bin(band, by_id[(band, bin_id)])))

    def on_frame(i: int, n: int, o: Any) -> None:
        on_done(i, n, o)
        got[o.ref.id] = o
        band, bin_id = ref_bin[o.ref.id]
        remaining[(band, bin_id)] -= 1
        band_left[band] -= 1
        if remaining[(band, bin_id)] == 0:
            dispatch(band, bin_id)
        if is_sso and band_left[band] == 0:
            stack_tasks.append(asyncio.ensure_future(stack_band_sso(band)))

    for band, b in bins_in_order:                      # bins with nothing to fetch (all capped) stack at once
        if remaining[(band, b.id)] == 0:
            dispatch(band, b.id)
    for band in order:
        if is_sso and band_left[band] == 0:
            stack_tasks.append(asyncio.ensure_future(stack_band_sso(band)))
    t_f = time.perf_counter()
    cache = getattr(svc.source, "cache", None)

    class FirstBandFirst:
        """Frames of later bands that are already in the frame cache wait until the selected band is stacked.
        Reading a cached frame is ~35 ms of GIL-holding Python (FITS headers, WCS); run beside the stacks it
        starves them (each short numpy step waits a switch interval for the GIL), measured as a first image at
        15-20 s instead of ~3 s. Network fetches are never held: they wait on the network, not the GIL."""

        name = svc.source.name
        concurrency = int(getattr(svc.source, "concurrency", 8))

        async def fetch(self, ref: FrameRef, b: FrameBox) -> Any:
            if (not first_done.is_set() and ref_bin[ref.id][0] != first_band and cache is not None
                    and cache.contains(ref, b)):
                await first_done.wait()
            return await svc.source.fetch(ref, b)

    try:
        if want:
            await fetch_frames(FirstBandFirst(), want, box, on_done=on_frame)
    except BaseException:                               # failed or timed out: leave no stack task pending
        for task in stack_tasks:
            task.cancel()
        raise
    timing["fetch_s"] = time.perf_counter() - t_f
    t_s = time.perf_counter()
    await asyncio.gather(*stack_tasks)
    timing["stack_s"] = time.perf_counter() - t_s       # stacking left after the last frame arrived
    _finalise(svc, plan, m, all_skipped, scales_seen)
    store.put_manifest(plan.key, m)
    if all_skipped:
        job.emit(
            {
                "type": "warning",
                "code": "frames_skipped",
                "message": f"{all_skipped} frame(s) were skipped; each is listed with its reason",
            }
        )
    pool = getattr(getattr(svc.source, "inner", svc.source), "stats", None)
    job.stats.update(
        frames=len(plan.refs),
        fetched=fetched,
        skipped=all_skipped,
        bytes_by_source=bytes_by_source,
        frames_by_source=frames_by_source,
        first_stack_s=round(first_stack_s or 0.0, 3),
        fetch_s=round(timing["fetch_s"], 3),
        stack_tail_s=round(timing["stack_s"], 3),
        total_s=round(time.perf_counter() - t0, 3),
        pool=pool() if callable(pool) else None,
        key=plan.key,
        pin=plan.pin,
    )
    svc.counters.inc("views_built")
    svc.counters.inc("frames_fetched", fetched)
    svc.counters.inc("frames_skipped", all_skipped)


def _carry_over_ready(store: Any, key: str, m: dict[str, Any]) -> None:
    """A view that timed out or was interrupted resumes on the next request (jobs.py). Its finished stacks stay
    visible while it rebuilds, instead of the viewer going blank until every bin is stacked again (audit K-22).
    The rebuild rewrites them with identical bytes (the stack is a pure function of the frames)."""
    old = store.manifest(key)
    if not old:
        return
    done = {(x["bin"], x["band"]): x for x in old.get("stacks", []) if x.get("ready")}
    kept = 0
    for st in m["stacks"]:
        prev = done.get((st["bin"], st["band"]))
        if prev and store.stack_path(key, st["bin"], st["band"], "f16").exists():
            st.update({k: prev[k] for k in ("ready", "nhits_max", "filled", "frame_ids", "skipped", "transients") if k in prev})
            kept += 1
    if kept:
        m["limits"] = dict(old.get("limits") or {})


def _finalise(svc: Any, plan: Plan, m: dict[str, Any], n_skipped: int, scales: set[str]) -> None:
    """Re-label bins with the survey numbers read from the frames' own headers (epochs.time_bins with
    surveys; the same MJDs, so the same bins), and add view-level warnings."""
    surveys: list[int | None] = []
    by_id = {x["id"]: x for x in m["frames"]}
    for f in plan.refs:
        s = by_id[f.id].get("survey")
        surveys.append(s if (s is not None or f.t_min < 60796.0) else 0)
    tb = time_bins([f.t_min for f in plan.refs], [f.detector for f in plan.refs], plan.axis, surveys=surveys)
    m["bins"] = {str(b): [bin_info(x) for x in tb[b]] for b in sorted(tb)}
    if n_skipped:
        m["warnings"].append(
            dict(
                code="frames_skipped",
                severity="warn",
                message=f"{n_skipped} frame(s) were skipped; the frame inspector lists each reason.",
            )
        )
    if len(scales) > 1:
        m["warnings"].append(
            dict(
                code="qr_mix",
                severity="warn",
                message="These visits come from QR2 and QR3, whose absolute calibration differs until "
                "foundation check F4 is resolved: compare positions, not brightness.",
            )
        )
    m["_complete"] = True
