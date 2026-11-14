"""Routes that serve I's λ products and the overlays/exports (P's side of the I↔P and M↔P surfaces).

Everything here is behind a feature flag (main.require) and refuses to run without the locked
calibration where λ matters. Frames are re-read through the FrameSource, whose disk cache (frames are
cached forever, implementation.md §3.7) makes this cheap after the view job."""

from __future__ import annotations

import asyncio
import io
import json
from typing import Any

import numpy as np
from fastapi import HTTPException, Response

from spherex.access.failover import fetch_frames
from spherex.access.frames import snap_box
from spherex.render import FORMAT_F16
from spherex.targets import Target, pa_deg, sep_arcsec
from spherex.types import FrameRef, TimeBin

from .store import find


def _refs(m: dict[str, Any], band: int, bin_id: str) -> list[FrameRef]:
    ids = {f["id"] for f in m["frames"] if f["band"] == band and f["bin"] == bin_id and f["skipped"] is None}
    return [FrameRef(**r) for r in m.get("_refs", []) if r["s3_key"].rsplit("/", 1)[-1] in ids]


def _tbin(m: dict[str, Any], band: int, bin_id: str) -> TimeBin:
    b = next((x for x in m["bins"].get(str(band), []) if x["id"] == bin_id), None)
    if b is None:
        raise HTTPException(404, f"no bin {bin_id} in band {band}")
    return TimeBin(
        id=b["id"],
        band=band,
        idx=np.empty(0, np.int64),
        status=b["status"],
        mjd_mean=b["mjd_mean"],
        mjd_min=b["mjd_min"],
        mjd_max=b["mjd_max"],
        surveys=tuple(b["surveys"]),
        label=b["label"],
    )


async def _raws(svc: Any, m: dict[str, Any], refs: list[FrameRef]) -> list[Any]:
    if svc.source is None:
        raise HTTPException(409, "no FrameSource on this server (offline)")
    plan = m.get("_plan")
    if plan is None:
        raise HTTPException(409, "this view was built without its plan (snapshot or mock); recompute it live")
    ra, dec, fov, _ = plan["grid_args"]
    centres = plan.get("track_centres") or {}
    outs = await fetch_frames(
        svc.source,
        refs,
        lambda ref: (
            snap_box(centres[ref.id][0], centres[ref.id][1], fov) if ref.id in centres else snap_box(ra, dec, fov)
        ),
    )
    m.setdefault("_measurement_fetch_skipped", []).extend(
        [[o.ref.id, o.skipped_reason or "native frame fetch failed"] for o in outs if o.frame is None]
    )
    return [o.frame for o in outs if o.frame is not None]


def _grid_xy(m: dict[str, Any], ra: float, dec: float) -> tuple[float, float]:
    from astropy.wcs import WCS

    g = m["grid"]
    w = WCS(naxis=2)
    w.wcs.ctype, w.wcs.crval, w.wcs.crpix, w.wcs.cdelt = g["ctype"], g["crval"], g["crpix"], g["cdelt"]
    x, y = w.wcs_world2pix(ra, dec, 0)
    return float(x), float(y)


def _grid_sky(m: dict[str, Any], x: float, y: float) -> tuple[float, float]:
    from astropy.wcs import WCS

    g = m["grid"]
    w = WCS(naxis=2)
    w.wcs.ctype, w.wcs.crval, w.wcs.crpix, w.wcs.cdelt = g["ctype"], g["crval"], g["crpix"], g["cdelt"]
    ra, dec = w.wcs_pix2world(x, y, 0)
    return float(ra), float(dec)


DIFF_CACHE_VERSION = 2      # 2: the expected motion direction is B → A (it was A → B, never agreeing with the dipole)


async def diff_info(svc: Any, m: dict[str, Any], a: str, b: str, band: int) -> dict[str, Any]:
    key = m["key"]
    jp = find(svc, "diff_path", key, a, b, band, "json")
    url = f"/api/v1/views/{key}/diff/{a}/{b}/{band}.f16"
    if jp.exists():
        cached = json.loads(jp.read_text(encoding="utf-8"))
        # older caches predate decision 0008 or the B → A direction fix: rebuild them once
        if "photometric_match" in cached and cached.pop("cache_version", None) == DIFF_CACHE_VERSION:
            return {**cached, "url": url}
    ta, tb = _tbin(m, band, a), _tbin(m, band, b)
    ra_a = await _raws(svc, m, _refs(m, band, a))
    ra_b = await _raws(svc, m, _refs(m, band, b))
    plan = m["_plan"]
    positions, expected = [], None
    ny, nx = m["grid"]["shape"]
    exclude = [((nx - 1) / 2, (ny - 1) / 2)]      # the target is never a photometric reference (decision 0008)
    trk = {(p["bin"], p["band"]): p for p in m.get("track", [])}
    if (a, band) in trk and (b, band) in trk:
        pa_, pb_ = trk[(a, band)], trk[(b, band)]
        positions.append(_grid_xy(m, (pa_["ra"] + pb_["ra"]) / 2, (pa_["dec"] + pb_["dec"]) / 2))
        exclude += [_grid_xy(m, pa_["ra"], pa_["dec"]), _grid_xy(m, pb_["ra"], pb_["dec"])]
        if sep_arcsec(pa_["ra"], pa_["dec"], pb_["ra"], pb_["dec"]) > 0.3 * m["grid"]["pix_arcsec"]:
            # A − B puts −f at B's position and +f at A's, so fit_dipole/fit_shift measure the shift B → A
            expected = pa_deg(pb_["ra"], pb_["dec"], pa_["ra"], pa_["dec"])
    else:
        positions.append(((nx - 1) / 2, (ny - 1) / 2))
    from .worker import diff_task

    loop = asyncio.get_running_loop()
    try:
        out = await loop.run_in_executor(
            svc.executor,
            diff_task,
            ra_a,
            ra_b,
            ta,
            tb,
            band,
            tuple(plan["grid_args"]),
            plan["preset"],
            svc.calib_spec,
            positions,
            expected,
            exclude,
        )
    except ValueError as e:
        raise HTTPException(409, str(e)) from None
    from .settings import load_features

    accepted = load_features(svc.settings.features_path).flags["diff"].level == "on"
    anns = []
    for r in out["annotations"]:
        if r["kind"] == "dipole":
            ra1, de1 = _grid_sky(m, r["x1"], r["y1"])
            ra2, de2 = _grid_sky(m, r["x2"], r["y2"])
            anns.append(
                dict(
                    kind="dipole",
                    ra=ra1,
                    dec=de1,
                    to_ra=ra2,
                    to_dec=de2,
                    shift_px=r["shift_px"],
                    shift_arcsec=r["shift_px"] * m["grid"]["pix_arcsec"],
                    pa_deg=r.get("pa_deg"),
                    agrees_with_track=(expected is not None and r["label"].startswith("moved")),
                    label=r["label"],
                )
            )
        else:
            ra1, de1 = _grid_sky(m, r["x"], r["y"])
            anns.append(
                dict(
                    kind="monopole",
                    ra=ra1,
                    dec=de1,
                    # across releases (before F4) a monopole is a residual, not a brightness change (§11.2)
                    sign=("brightened" if r["flux"] > 0 else "faded") if r.get("comparable", True) else None,
                    label=r["label"],
                )
            )
    info = dict(
        a=a,
        b=b,
        band=band,
        format=FORMAT_F16,
        k=out["k"],
        clip_sigma=5.0,
        annotations=anns,
        validity="accepted" if accepted else "unvalidated",
        photometric_match=out.get("photometric_match"),
    )
    from .store import atomic_write

    atomic_write(svc.store.diff_path(key, a, b, band, "f16"), out["f16"])
    atomic_write(jp, json.dumps({**info, "cache_version": DIFF_CACHE_VERSION}).encode())
    return {**info, "url": url}


async def cube_payload(svc: Any, m: dict[str, Any], bin_id: str, band: int) -> bytes:
    from .store import atomic_write
    from .worker import cube_task

    try:
        cp = find(svc, "cube_path", m["key"], bin_id, band)
    except ValueError as e:
        raise HTTPException(400, str(e)) from None
    if cp.exists():
        return cp.read_bytes()

    raws = await _raws(svc, m, _refs(m, band, bin_id))
    loop = asyncio.get_running_loop()
    try:
        data = await loop.run_in_executor(
            svc.executor,
            cube_task,
            raws,
            _tbin(m, band, bin_id),
            band,
            tuple(m["_plan"]["grid_args"]),
            m["_plan"]["preset"],
            svc.calib_spec,
        )
    except ValueError as e:
        raise HTTPException(409, str(e)) from None
    if cp.is_relative_to(svc.store.root):
        atomic_write(cp, data)
    return data


async def flipbook(svc: Any, m: dict[str, Any], band: int, sort: str) -> dict[str, Any]:
    """Exposure flipbook (P2-2, expert mode, G5.flip; implementation.md §4.6, §5.1).

    Every QA-passing frame of the band, gridded like the visit stacks, with the λ that frame saw at the
    target (I's `worker.flipbook_task`), ordered by I's `cube.flipbook_order` and decimated to ≤ 64.
    `sort=lambda` (the default, workflow.md §11.2) drops frames whose λ at the target is unknown instead of
    placing them by a guess; `sort=time` keeps them and is labelled as mixing wavelength with time."""
    import hashlib

    from spherex.cube import SPECTRAL_LABEL, flipbook_order

    from .store import atomic_write

    key = m["key"]
    idx_path = find(svc, "frame_path", key, band, "index.json")
    if idx_path.exists():
        rows = json.loads(idx_path.read_text(encoding="utf-8"))
    else:
        ids = {f["id"] for f in m["frames"] if f["band"] == band and f["skipped"] is None}
        refs = [FrameRef(**r) for r in m.get("_refs", []) if r["s3_key"].rsplit("/", 1)[-1] in ids]
        if not refs:
            raise HTTPException(404, f"no usable frames in band {band}")
        raws = await _raws(svc, m, refs)
        plan = m["_plan"]
        mjd = {f["id"]: f["mjd"] for f in m["frames"]}
        centres = plan.get("track_centres") or {}
        tgt = plan.get("target")
        if tgt is not None:
            t = Target(**tgt)
            fids = [r.ref.id for r in raws if r.ref is not None]
            ra_t, de_t = t.pos([mjd[f] for f in fids]) if fids else ([], [])
            target_at = {f: (float(a), float(d)) for f, a, d in zip(fids, ra_t, de_t, strict=True)}
        else:
            ra0, de0 = plan["grid_args"][0], plan["grid_args"][1]
            target_at = {r.ref.id: (ra0, de0) for r in raws if r.ref is not None}
        from .worker import flipbook_task

        loop = asyncio.get_running_loop()
        out = await loop.run_in_executor(
            svc.executor,
            flipbook_task,
            raws,
            band,
            tuple(plan["grid_args"]),
            plan["preset"],
            svc.calib_spec,
            target_at,
            {k: tuple(v) for k, v in centres.items()} or None,
        )
        rows = []
        for o in out:
            dig = hashlib.sha256(o["id"].encode()).hexdigest()[:16]
            atomic_write(svc.store.frame_path(key, band, f"{dig}.f16"), o["f16"])
            rows.append(dict(id=o["id"], mjd=o["mjd"], lam_um=o["lam_um"], digest=dig))
        atomic_write(idx_path, json.dumps(rows).encode())
    if sort == "lambda":
        rows = [r for r in rows if r["lam_um"] is not None]
        if not rows:
            raise HTTPException(
                409, "no frame has a known wavelength at the target; the flipbook is not sorted by guess"
            )
        label = SPECTRAL_LABEL
    else:
        label = "exposure (time) order: the wavelength changes between exposures, so brightness changes are spectral, not variability"
    order = flipbook_order(
        [r["lam_um"] if r["lam_um"] is not None else np.nan for r in rows], [r["mjd"] for r in rows], sort=sort
    )
    frames = [
        dict(
            id=rows[i]["id"],
            mjd=rows[i]["mjd"],
            lam_um=rows[i]["lam_um"],
            url=f"/api/v1/views/{key}/frames/{band}/{rows[i]['digest']}.f16",
        )
        for i in order
    ]
    return dict(key=key, band=band, sort=sort, label=label, format=FORMAT_F16, frames=frames)


BLINK25_IMAGES_PER_EPOCH = {"2MASS": 3, "AllWISE": 1, "NEOWISE": 4}


def _ks_expected(t: Target) -> float | None:
    """Catalogue Ks of the target for the 2MASS brightness match: SIMBAD's K for any star, else the acceptance
    table matched by position (so aliases resolve too)."""
    from astropy.time import Time

    if t.extra.get("k_mag") is not None:
        return float(t.extra["k_mag"])

    from spherex.access.blink25 import KS_EXPECTED
    from spherex.constants import TEST_TARGETS

    for name, ks in KS_EXPECTED.items():
        ra, dec, ep = TEST_TARGETS[name][:3]
        a, d = t.pos([float(Time(ep, format="jyear").mjd)])
        if sep_arcsec(float(a[0]), float(d[0]), ra, dec) < 30:
            return ks
    return None


async def blink25(svc: Any, m: dict[str, Any]) -> dict[str, Any]:
    """25-year blink (P2-1, implementation.md §4.13): D's epoch plan (2MASS Ks, AllWISE W2, NEOWISE W2 thinned to
    ≈ one per two years), fetched as cutouts, put by I's `spherex.blink25` on one grid centred between the archival
    and current positions (≥ 1.5 × the jump), each epoch on its own sky σ; the view's latest full band-6 visit
    stack is the last epoch. Positions only. Cached per view."""
    key = m["key"]
    idx_path = find(svc, "blink25_path", key, "index.json")
    if idx_path.exists():
        return dict(json.loads(idx_path.read_text(encoding="utf-8")))
    lock = _BLINK25_LOCKS.setdefault(key, asyncio.Lock())
    async with lock:  # concurrent requests for one view share a single archive build
        if idx_path.exists():
            return dict(json.loads(idx_path.read_text(encoding="utf-8")))
        return await _build_blink25(svc, m, idx_path)


_BLINK25_LOCKS: dict[str, asyncio.Lock] = {}


async def _build_blink25(svc: Any, m: dict[str, Any], idx_path: Any) -> dict[str, Any]:
    from astropy.time import Time

    from spherex.access.blink25 import fetch_cutout, plan, sep_arcmin
    from spherex.blink25 import select_epochs
    from spherex.external.twomass import TwoMassClient
    from spherex.external.wise import WiseClient
    from spherex.render import BLINK25_LABEL

    from .pipeline import grid_info
    from .store import atomic_write

    key = m["key"]
    if not svc.settings.network or svc.client is None:
        raise HTTPException(409, "the 25-year blink needs the IRSA archives; this server is offline")
    plan_m = m.get("_plan")
    if plan_m is None or plan_m.get("target") is None:
        raise HTTPException(409, "this view has no resolved target; the 25-year blink follows a named moving star")
    t = Target(**plan_m["target"])
    if t.kind != "star" or not t.moving:
        raise HTTPException(409, "the 25-year blink is for stars with measured proper motion (positions only)")
    band = 6
    full = [b for b in m["bins"].get(str(band), []) if b["status"] == "full"]
    ready = {s["bin"] for s in m["stacks"] if s["band"] == band and s["ready"] and s["frame_ids"]}
    last = max((b for b in full if b["id"] in ready), key=lambda b: b["mjd_mean"], default=None)
    from spherex.targets import mjd_now

    any_bins = [b["mjd_mean"] for b in m["bins"].get(str(band), [])]
    now_mjd = last["mjd_mean"] if last else (max(any_bins) if any_bins else mjd_now())
    now_year = float(Time(now_mjd, format="mjd").jyear)

    def pos(year: float) -> tuple[float, float]:
        a, d = t.pos([float(Time(year, format="jyear").mjd)])
        return float(a[0]), float(d[0])

    try:
        p = await plan(
            t.name,
            pos,
            now_year,
            TwoMassClient(svc.client),
            WiseClient(svc.client),
            "spherex.targets.Target.pos (catalogue epoch, proper motion and parallax)",
            k_expected=_ks_expected(t),
        )
    except Exception as e:  # archive failures are reported, never replaced by a guess
        raise HTTPException(502, f"archival search failed: {type(e).__name__}: {e}"[:300]) from None
    d = p.as_dict()
    old = (d["twomass_source"]["ra"], d["twomass_source"]["dec"]) if d["twomass_source"] else pos(2010.5)
    now = tuple(d["now_pos"])
    # midpoint on the sphere's RA circle: a star straddling 0h must not centre the blink 180° away (audit K-38)
    d_ra = (now[0] - old[0] + 180.0) % 360.0 - 180.0
    centre = ((old[0] + d_ra / 2) % 360.0, (old[1] + now[1]) / 2)
    fov = float(d["fov_arcmin"])
    pix = float(m["grid"]["pix_arcsec"])
    from spherex.grid import pixel_scale_for

    grid_args = (centre[0], centre[1], fov, pixel_scale_for(fov, pix))
    size_deg = fov * 1.5 / 60  # √2 rotation margin plus slack
    epochs = select_epochs(d["epochs"])
    sem = asyncio.Semaphore(4)

    async def get(url: str) -> bytes | None:
        async with sem:
            try:
                return await fetch_cutout(
                    svc.client,
                    f"{url.split('?')[0]}?center={centre[0]:.6f},{centre[1]:.6f}&size={size_deg:.5f}",
                    getattr(svc, "limiter", None),
                )
            except Exception:  # one failed image is listed via n_images, not fatal
                return None

    archival: list[list[bytes]] = []
    for ep in epochs:
        lim = next(v for k, v in BLINK25_IMAGES_PER_EPOCH.items() if ep["label"].startswith(k))
        got = await asyncio.gather(*(get(im["url"]) for im in ep["images"][:lim]))
        archival.append([g for g in got if g is not None])
    stack = None
    if last is not None:
        from .main import _payload_path

        sp = _payload_path(svc, key, last["id"], band, "f32")
        if sp is not None:
            stack = np.frombuffer(sp.read_bytes(), "<f4").reshape(tuple(m["grid"]["shape"])).astype(float)
    from .worker import blink25_task

    loop = asyncio.get_running_loop()
    out = await loop.run_in_executor(svc.executor, blink25_task, archival, stack, m["grid"], grid_args)
    rows = []
    all_epochs = [
        *epochs,
        dict(label=f"SPHEREx band {band}", year=now_year, date=last["label"] if last else "", images=[]),
    ]
    for i, (ep, (payload, n)) in enumerate(zip(all_epochs, out, strict=True)):
        url = None
        if payload is not None:
            atomic_write(svc.store.blink25_path(key, f"{i}.f16"), payload)
            url = f"/api/v1/views/{key}/blink25/{i}.f16"
        is_sx = i == len(all_epochs) - 1
        ra_e, de_e = pos(float(ep["year"]))
        note = "; ".join(ep.get("notes", [])) or None
        if payload is None:
            note = (note + "; " if note else "") + (
                "no full band-6 visit stack in this view" if is_sx else "no image could be fetched or normalised"
            )
        rows.append(
            dict(
                label=ep["label"],
                year=float(ep["year"]),
                date=str(ep["date"]),
                pairs_with_band=band if is_sx else d["pairing"].get(ep["label"]),
                n_images=n if not is_sx else int(payload is not None),
                ra=ra_e,
                dec=de_e,
                url=url,
                note=note,
            )
        )
    view_fov = float(plan_m["grid_args"][2])
    vg = (float(m["grid"]["crval"][0]), float(m["grid"]["crval"][1]))
    info = dict(
        key=key,
        label=BLINK25_LABEL,
        format=FORMAT_F16,
        grid=grid_info(grid_args),
        view_fov_arcmin=view_fov,
        fov_needed_arcmin=fov,
        view_fov_for_full_coverage_arcmin=float(2 * sep_arcmin(vg, centre) + fov * 2**0.5),
        expected_jumps_arcmin={k: float(v) for k, v in d["expected_jumps_arcmin"].items()},
        twomass_match=(
            f"2MASS {d['twomass_source']['designation']} (Ks {d['twomass_source']['k_m']:.2f}, "
            f"{d['twomass_source']['date']})"
        )
        if d["twomass_source"]
        else None,
        pos_source=d["pos_source"],
        epochs=rows,
    )
    atomic_write(idx_path, json.dumps(info).encode())
    return info


RGB_RANGE_PRESETS = ("methane", "ice")


async def rgb_payload(svc: Any, m: dict[str, Any], bin_id: str, preset: str) -> bytes:
    """λ-range RGB composite of one time bin (implementation.md §7), computed once and cached."""
    from spherex.constants import BANDS
    from spherex.cube import RGB_PRESETS

    from .store import atomic_write

    if preset not in RGB_RANGE_PRESETS:
        raise HTTPException(404, f"RGB preset must be one of {', '.join(RGB_RANGE_PRESETS)}")
    try:
        p = find(svc, "rgb_path", m["key"], bin_id, preset)
    except ValueError as e:
        raise HTTPException(400, str(e)) from None
    if p.exists():
        return bytes(p.read_bytes())
    ranges: tuple[tuple[float, float], ...] = RGB_PRESETS[preset]  # type: ignore[assignment]  # λ-range presets only
    bands = sorted({b for b, (lo, hi, _) in BANDS.items() for (a, z) in ranges if lo <= z and hi >= a})
    raws, tbins = {}, {}
    missing = [b for b in bands if not any(x["id"] == bin_id for x in m["bins"].get(str(b), []))]
    if missing:
        # A channel without data would read as "no flux" (e.g. no red in rgb:methane): refuse instead.
        raise HTTPException(404, f"bin {bin_id} has no stack in band(s) {missing}, which preset {preset} needs")
    for b in bands:
        tbins[b] = _tbin(m, b, bin_id)
        raws[b] = await _raws(svc, m, _refs(m, b, bin_id))
    if not raws:
        raise HTTPException(404, f"no bin {bin_id} in the bands this preset needs ({bands})")
    from .worker import rgb_task

    loop = asyncio.get_running_loop()
    data = await loop.run_in_executor(
        svc.executor,
        rgb_task,
        raws,
        tbins,
        tuple(m["_plan"]["grid_args"]),
        m["_plan"]["preset"],
        svc.calib_spec,
        preset,
    )
    atomic_write(p, data)
    return bytes(data)


CATALOGUE_TTL_S = 7 * 86400
SSO_OVERLAY_VMAX = 19.0      # understanding.md §6.2: single frames reach V ≲ 18.5
SSO_OVERLAY_MAX = 20


async def cached_cone(svc: Any, name: str, cls: Any, fetch: Any, *key: Any) -> list[Any]:
    """Catalogue cone rows (dataclasses) cached on disk for CATALOGUE_TTL_S, keyed by the rounded query (audit K-34):
    overlays are asked once per time bin and each TAP cone costs 10–17 s. Propagation to the bin's epoch happens
    after the cache, so one cached cone serves every bin."""
    import dataclasses

    from spherex.external.tap import JsonCache

    cache = JsonCache(svc.settings.cache_dir / "catalogues", ttl_s=CATALOGUE_TTL_S)
    k = json.dumps([name, *[round(float(x), 4) if isinstance(x, float) else x for x in key]])
    hit = cache.get(k)
    if hit is not None:
        try:
            return [cls(**row) for row in hit]
        except TypeError:                     # a client's fields changed since the entry was written: refetch
            pass
    rows = await fetch()
    try:
        cache.put(k, [dataclasses.asdict(r) for r in rows])
    except OSError:
        pass
    return list(rows)


async def overlay(svc: Any, cat: str, ra: float, dec: float, r_deg: float, mjd: float) -> dict[str, Any]:
    """Catalogue markers propagated to the requested epoch (implementation.md §6.6), parallax included,
    through M's common pos(t), with exact SPHEREx-observer SSO ephemerides."""
    if not svc.settings.network or svc.client is None:
        raise HTTPException(409, "overlays need the catalogue services; this server is offline")
    out = []
    if cat == "gaia":
        from spherex.external.gaia import GaiaClient, GaiaSource

        rows = await cached_cone(svc, "gaia", GaiaSource, lambda: GaiaClient(svc.client).cone(ra, dec, r_deg, g_max=19.0),
                                 ra, dec, r_deg, 19.0)
        for s in rows[:2000]:
            t = Target(
                query="",
                kind="star",
                name=str(s.source_id),
                ra=s.ra,
                dec=s.dec,
                epoch=2016.0,
                pmra=s.pmra,
                pmdec=s.pmdec,
                plx=s.parallax if (s.parallax or 0) > 0 else None,
                rv=s.radial_velocity,
            )
            pra, pde = t.pos([mjd])
            out.append(dict(id=f"Gaia DR3 {s.source_id}", ra=float(pra[0]), dec=float(pde[0]), mag=s.phot_g_mean_mag))
    elif cat == "catwise":
        from spherex.external.catwise import CATWISE_EPOCH_MJD, CatwiseClient, CatwiseSource
        from spherex.targets import decimal_year

        crows = await cached_cone(svc, "catwise", CatwiseSource, lambda: CatwiseClient(svc.client).cone(ra, dec, r_deg),
                                  ra, dec, r_deg)
        for c in crows[:2000]:
            t = Target(
                query="",
                kind="star",
                name=c.source_name,
                ra=c.ra,
                dec=c.dec,
                epoch=decimal_year(CATWISE_EPOCH_MJD),
                pmra=c.pmra,
                pmdec=c.pmdec,
            )
            pra, pde = t.pos([mjd])
            out.append(dict(id=c.source_name, ra=float(pra[0]), dec=float(pde[0]), mag=c.w2mpro))
    elif cat == "allwise":
        # As WISE measured them around 2010.5, deliberately NOT moved to `mjd`: a mover sits away from its marker.
        from spherex.external.allwise import ALLWISE_EPOCH, ALLWISE_W2_MAX, AllwiseClient, AllwiseSource

        arows = await cached_cone(svc, "allwise", AllwiseSource, lambda: AllwiseClient(svc.client).cone(ra, dec, r_deg),
                                  ra, dec, r_deg)
        # Only sources a SPHEREx visit stack shows plainly: every AllWISE source buried the image (221 squares on
        # a 6' field, browser test 2026-11-14). W2 <= 14 keeps WISE 0855 itself (W2 13.70).
        shown = [a for a in arows if a.w2mpro is not None and a.w2mpro <= ALLWISE_W2_MAX]
        brightest = sorted(shown, key=lambda a: a.w2mpro if a.w2mpro is not None else 99.0)[:2000]
        out = [dict(id=f"WISEA {a.designation}", ra=a.ra, dec=a.dec, mag=a.w2mpro) for a in brightest]
        return dict(catalogue=cat, mjd=mjd, sources=out, epoch=ALLWISE_EPOCH)
    elif cat == "simbad":
        from spherex.external.simbad import SimbadClient, SimbadObject

        srows = await cached_cone(svc, "simbad", SimbadObject,
                                  lambda: SimbadClient(svc.client).high_pm_cone(ra, dec, r_deg, 0.0), ra, dec, r_deg)
        for o in srows:
            if o.ra is None or o.dec is None:
                continue
            t = Target(
                query="",
                kind="star",
                name=o.main_id,
                ra=o.ra,
                dec=o.dec,
                epoch=2000.0,
                pmra=o.pmra,
                pmdec=o.pmdec,
                plx=o.plx,
            )
            pra, pde = t.pos([mjd])
            out.append(dict(id=o.main_id, ra=float(pra[0]), dec=float(pde[0]), label=o.main_id))
    elif cat == "sso":
        from spherex.external.horizons import positions
        from spherex.external.skybot import SkybotClient

        skipped = []
        # SkyBoT geocentric search is identification only. Never draw its geocentre
        # direction as a SPHEREx position; refine each candidate with Horizons.
        objects = await SkybotClient(svc.client).cone(mjd + 2400000.5, ra, dec, min(r_deg + 0.5, 10))
        # Near the ecliptic SkyBoT returns hundreds of bodies, each needing its own Horizons call (audit K-35): keep
        # the ones a single SPHEREx frame could show, nearest first, and refine at most SSO_OVERLAY_MAX concurrently.
        keep = sorted((o for o in objects if o.mv is None or o.mv <= SSO_OVERLAY_VMAX),
                      key=lambda o: sep_arcsec(ra, dec, o.ra_deg, o.dec_deg))
        for o in objects:
            if o.mv is not None and o.mv > SSO_OVERLAY_VMAX:
                skipped.append([o.name, f"V = {o.mv:.1f} is fainter than a SPHEREx frame shows (V > {SSO_OVERLAY_VMAX:g})"])
        for o in keep[SSO_OVERLAY_MAX:]:
            skipped.append([o.name, f"not refined: more than {SSO_OVERLAY_MAX} candidate bodies in the field"])
        sem = asyncio.Semaphore(4)

        async def refine(obj: Any) -> None:
            command = f"{obj.number};" if obj.number else obj.name
            try:
                async with sem:
                    xy = await positions(svc.client, command, [mjd])
                a, d = xy[0]
                if sep_arcsec(ra, dec, a, d) <= r_deg * 3600:
                    out.append(dict(id=obj.name, ra=a, dec=d, mag=obj.mv, label=f"{obj.name} (SPHEREx observer)"))
            except Exception as ex:
                skipped.append([obj.name, f"exact SPHEREx ephemeris unavailable: {type(ex).__name__}: {ex}"])

        await asyncio.gather(*(refine(o) for o in keep[:SSO_OVERLAY_MAX]))
        out.sort(key=lambda x: str(x["id"]))
        return dict(catalogue=cat, mjd=mjd, sources=out, skipped=skipped)
    else:
        raise HTTPException(400, "unknown overlay catalogue")
    return dict(catalogue=cat, mjd=mjd, sources=out)


async def export_view(
    svc: Any, fmt: str, key: str, band: int, bins: str, stretch: str, cmap: str, fps: float
) -> Response:
    """P2-7: GIF/APNG blink with the shared stretch; FITS (stacks with the grid WCS) and CSV (frame list).
    MP4 needs ffmpeg in the image: refused with a clear message instead of a lower-quality substitute."""
    from .main import _manifest
    from .render_png import RenderError, animation_bytes, decode_f16

    m, _ = _manifest(svc, key)
    if m is None:
        raise HTTPException(404, "unknown view")
    order = [s for s in m["stacks"] if s["band"] == band and s["ready"]]
    want = [x for x in bins.split(",") if x] or [s["bin"] for s in order]
    shape = tuple(m["grid"]["shape"])
    from .main import _payload_path

    def arr(bin_id: str, ext: str) -> Any:
        p = _payload_path(svc, key, bin_id, band, ext)
        if p is None:
            raise HTTPException(404, f"stack {bin_id}/{band} not ready")
        return (
            decode_f16(p.read_bytes(), shape) if ext == "f16" else np.frombuffer(p.read_bytes(), "<f4").reshape(shape)
        )

    if fmt in ("gif", "apng"):
        lim = m["limits"].get(str(band))
        if not lim:
            raise HTTPException(409, "limits not ready")
        labels = {b["id"]: b["label"] for b in m["bins"].get(str(band), [])}
        try:
            data = animation_bytes(
                [arr(b, "f16") for b in want],
                lim["lo"],
                lim["hi"],
                stretch,
                cmap,
                fmt,
                fps,
                [labels.get(b, b) for b in want],
            )
        except RenderError as e:
            raise HTTPException(400, str(e)) from None
        return Response(
            data,
            media_type="image/gif" if fmt == "gif" else "image/apng",
            headers={
                "Content-Disposition": f'attachment; filename="parallax_{key}_b{band}.{"gif" if fmt == "gif" else "png"}"'
            },
        )
    if fmt == "fits":
        from astropy.io import fits
        from astropy.wcs import WCS

        g = m["grid"]
        w = WCS(naxis=2)
        w.wcs.ctype, w.wcs.crval, w.wcs.crpix, w.wcs.cdelt = g["ctype"], g["crval"], g["crpix"], g["cdelt"]
        hdr = w.to_header()
        hl = fits.HDUList([fits.PrimaryHDU()])
        hl[0].header["ORIGIN"] = "ParallaX"
        hl[0].header["VIEWKEY"] = key
        hl[0].header["PIN"] = m["pin"]
        hl[0].header["BUNIT"] = "MJy/sr"
        for b in want:
            h = hdr.copy()
            h["EXTNAME"] = f"B{band}_{b}"[:68]
            h["BUNIT"] = "MJy/sr"
            hl.append(fits.ImageHDU(arr(b, "f32").astype(np.float32), header=h))
            hv = hdr.copy()
            hv["EXTNAME"] = f"B{band}_{b}_VAR"[:68]
            hl.append(fits.ImageHDU(arr(b, "var.f32").astype(np.float32), header=hv))
        buf = io.BytesIO()
        hl.writeto(buf)
        return Response(
            buf.getvalue(),
            media_type="application/fits",
            headers={"Content-Disposition": f'attachment; filename="parallax_{key}_b{band}.fits"'},
        )
    if fmt == "csv":
        import csv

        s = io.StringIO()
        wr = csv.writer(s)
        wr.writerow(
            [
                "id",
                "band",
                "detector",
                "bin",
                "mjd",
                "survey",
                "release",
                "collection",
                "pipeline",
                "L1DQAFLG",
                "L2DQAFLG",
                "FINAST",
                "skipped",
            ]
        )
        for f in m["frames"]:
            if f["band"] != band:
                continue
            q = f.get("qa") or {}
            wr.writerow(
                [
                    f["id"],
                    f["band"],
                    f["detector"],
                    f["bin"],
                    f["mjd"],
                    f["survey"],
                    f["release"],
                    f["collection"],
                    f["pipeline"],
                    q.get("L1DQAFLG", ""),
                    q.get("L2DQAFLG", ""),
                    q.get("FINAST", ""),
                    f["skipped"] or "",
                ]
            )
        return Response(
            s.getvalue(),
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="parallax_{key}_b{band}.csv"'},
        )
    if fmt == "mp4":
        raise HTTPException(501, "MP4 export needs ffmpeg in the server image (not installed); use gif or apng")
    raise HTTPException(404, "export formats: gif, apng, fits, csv (mp4 needs ffmpeg)")
