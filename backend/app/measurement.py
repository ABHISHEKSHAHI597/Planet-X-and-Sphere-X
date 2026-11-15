"""M↔P integration: archive acquisition stays outside pure measurement functions.

No measurements on display stacks. Results retain native frames, scales and reasons
for every failed fit. Release flags remain off until the corresponding gates pass.
"""

from __future__ import annotations

import asyncio
from typing import Any

import numpy as np
from astropy.coordinates import SkyCoord
from astropy.time import Time
from fastapi import HTTPException

from spherex.astrometry import isolated, motion_fit, parallax_factors, registration
from spherex.epsf import EPSF, fit_native, load_table
from spherex.external.gaia import GaiaClient, GaiaSource
from spherex.external.horizons import CENTER, positions
from spherex.photometry import spectrum_point
from spherex.preprocess import calibrate
from spherex.targets import Target, sep_arcsec

from . import calibration
from .science import _raws, cached_cone


def _exact(*xs: float) -> list[str]:
    """Cache key parts at full precision: cached_cone rounds floats to 4 decimals, which suits overlays but would let a
    measurement reuse the rows of a slightly different cone."""
    return [repr(float(x)) for x in xs]


def validity(svc: Any, flag: str) -> str:
    return "accepted" if svc.features().get(flag) == "on" else "unvalidated"


async def inputs(
    svc: Any,
    ra: float,
    dec: float,
    key: str | None = None,
    name: str = "",
    release: str = "",
    min_fov: float = 0,
    detectors: tuple[int, ...] | None = None,
    include_capped: bool = False,
) -> tuple[Any, Any, Any]:
    if svc.calib_spec[0] != "locked":
        raise HTTPException(
            409, "Measurement requires locked CWAVE, CBAND, ePSF and solid-angle maps; fixture slices are insufficient"
        )
    # Bound to a view (audit K-40): without one, every request planned a fresh 12′ view and fetched all its frames,
    # uncached and unlimited. The view's immutable frame list also makes the result cacheable (main._call).
    if not key:
        raise HTTPException(400, "measurements need the view key (key=…): open the position in a view first")
    m = svc.store.manifest(key)
    if m is None and svc.snapshot is not None:
        m = svc.snapshot.manifest(key)
    if m is None:
        raise HTTPException(404, "unknown view")
    if min_fov and float(m["_plan"]["grid_args"][2]) < min_fov:
        import copy

        m = copy.deepcopy(m)
        grid_args = list(m["_plan"]["grid_args"])
        grid_args[2] = min_fov
        m["_plan"]["grid_args"] = grid_args
    m.setdefault("_measurement_fetch_skipped", []).extend(
        [[f["id"], f["skipped"]] for f in m.get("frames", []) if f.get("skipped") is not None
         and not (include_capped and str(f["skipped"]).startswith("cap:"))]
    )
    from spherex.types import FrameRef

    # The 600-frame cap (implementation.md §9) limits display stacks. Light curves need every same-channel repeat
    # (§4.9 annulus groups), so they may also read the frames the cap left out.
    usable = {f["id"] for f in m.get("frames", [])
              if f.get("skipped") is None or (include_capped and str(f.get("skipped")).startswith("cap:"))}
    refs = [FrameRef(**r) for r in m.get("_refs", [])]
    raws = await _raws(
        svc,
        m,
        [
            r
            for r in refs
            if r.id in usable
            and (not release or release in r.collection)
            and (detectors is None or r.detector in detectors)
        ],
    )
    if not raws:
        raise HTTPException(409, "No native frames available for this measurement")
    planned_target = m.get("_plan", {}).get("target") or {}
    if planned_target.get("kind") == "sso":
        if svc.client is None:
            raise HTTPException(409, "Tracked SSO measurement requires exact midpoint Horizons positions")
        times = sorted({float(r.hdus["IMAGE"][0]["MJD-AVG"]) for r in raws})
        extra = planned_target.setdefault("extra", {})
        xy = await positions(svc.client, extra.get("command", planned_target["name"]), times)
        extra.setdefault("ephemeris", {}).update({str(t): p for t, p in zip(times, xy, strict=True)})
    cal = calibration.load(svc.calib_spec)
    return m, raws, cal


def epsfs(cal: Any, detectors: Any) -> dict[int, EPSF]:
    return {d: load_table(str(cal.path("epsf", d))) for d in set(detectors)}


def target_from_manifest(m: Any, ra: float, dec: float, track: bool) -> Target:
    t = m.get("target") or {}
    if track and t.get("kind") == "sso":
        planned = m.get("_plan", {}).get("target")
        if planned is None:
            raise HTTPException(409, "Tracked SSO measurement is missing its ephemeris provenance")
        return Target(**planned)
    pm = t.get("pm") or [None, None]
    if track and t.get("kind") == "star":
        from spherex.targets import sep_arcsec

        if (
            sep_arcsec(
                ra,
                dec,
                t.get("propagated_now", {}).get("ra", t["ra"]),
                t.get("propagated_now", {}).get("dec", t["dec"]),
            )
            < 30
        ):
            return Target(
                "",
                "star",
                t["name"],
                t["ra"],
                t["dec"],
                t["epoch"],
                pm[0],
                pm[1],
                t.get("plx"),
                t.get("rv"),
                astrometry_source=t.get("astrometry_source"),
            )
    return Target("", "coords", "selected sky", ra, dec)


NEIGHBOUR_ARCSEC = 15.0   # ≈ 2.4 native px: a Gaia source this close blends with the target (WISE 0855's G = 16.3 star)


def red_only(t: dict[str, Any] | None) -> bool:
    """Brown dwarf with no Gaia astrometry (Gaia-invisible, e.g. Y dwarfs): too faint below ≈3.5 µm, so motion is
    measured in band 6 only with a joint target + neighbour fit (decision 0006). Was hard-coded to WISE 0855."""
    if not t or t.get("kind") != "star":
        return False
    cold = (t.get("otype") or "").startswith("BD") or (t.get("spt") or "")[:1] in ("L", "T", "Y")
    return cold and "Gaia" not in str(t.get("astrometry_source") or "")


def blend_neighbours(target: Target, gaia: list[Any], mjd: float) -> list[Any]:
    """Gaia sources within NEIGHBOUR_ARCSEC of the target at the observation epoch `mjd` (both propagated, so a
    fast mover meets the stars it is crossing now), nearest first, excluding the target's own Gaia counterpart
    (≤ 2″). Generalises the WISE 0855 contaminant to every target."""
    a, d = target.pos([mjd])
    near = []
    for g in gaia:
        ga, gd = Target("", "star", str(g.source_id), g.ra, g.dec, 2016.0, g.pmra, g.pmdec,
                        g.parallax if (g.parallax or 0) > 0 else None).pos([mjd])
        sep = sep_arcsec(float(a[0]), float(d[0]), float(ga[0]), float(gd[0]))
        if 2.0 < sep < NEIGHBOUR_ARCSEC:
            near.append((sep, g))
    return [g for _, g in sorted(near, key=lambda x: x[0])]


def isolated_field_stars(candidates: list[Any], ra: float, dec: float, n_max: int = 8) -> list[Any]:
    """Field stars for the methane-index reference, in catalogue order: Gaia RUWE ≤ 1.5, ≥ 20″ from the target, no
    other candidate within 18″. One vectorised pair search instead of a Python double loop on the event loop
    (audit K-41: seconds of a blocked API in dense fields); the selection is unchanged."""
    from astropy import units as u

    if not candidates:
        return []
    cat = SkyCoord([g.ra for g in candidates] * u.deg, [g.dec for g in candidates] * u.deg)
    to_target = cat.separation(SkyCoord(ra * u.deg, dec * u.deg)).arcsec
    i1, i2, _, _ = cat.search_around_sky(cat, 18 * u.arcsec)
    ids = np.array([g.source_id for g in candidates], dtype=object)
    crowded = np.zeros(len(candidates), bool)
    other = ids[i1] != ids[i2]
    crowded[i1[other]] = True
    out = []
    for k, g in enumerate(candidates):
        if g.ruwe is None or g.ruwe > 1.5 or to_target[k] < 20 or crowded[k]:
            continue
        out.append(g)
        if len(out) >= n_max:
            break
    return out


def frame_mjd(raw: Any) -> float:
    """The time calibrate() gives a frame (CalFrame.mjd), read before calibrating."""
    return float(raw.hdus["IMAGE"][0].get("MJD-AVG", raw.ref.t_min if raw.ref else np.nan))


class FramePositions:
    """Target.pos for every frame time at once: Target.pos is elementwise in time, so one astropy call per source
    replaces one call per (source, frame). A time that was not precomputed falls back to a direct call."""

    def __init__(self, targets: list[Target], mjds: list[float]) -> None:
        self.targets = targets
        self.index = {t: k for k, t in enumerate(mjds)}
        self.pos = [t.pos(mjds) for t in targets] if mjds else []

    def __call__(self, i: int, mjd: float) -> tuple[Any, Any]:
        k = self.index.get(mjd)
        if k is None:
            return self.targets[i].pos([mjd])
        a, d = self.pos[i]
        return a[k : k + 1], d[k : k + 1]


async def spectrum_api(
    svc: Any, ra: float, dec: float, track: bool = True, visits: str = "all", key: str | None = None
) -> dict[str, Any]:
    m, raws, cal = await inputs(svc, ra, dec, key)
    target = target_from_manifest(m, ra, dec, track)
    psfs = epsfs(cal, [int(r.hdus["IMAGE"][0]["DETECTOR"]) for r in raws])
    fid_to_bin = {f["id"]: f["bin"] for f in m["frames"]}
    rows = []
    skipped = list(m.get("_measurement_fetch_skipped", []))
    scales = set()
    neighbours: list[Any] = []
    field = []
    if svc.client is not None:
        candidates = await cached_cone(svc, "gaia", GaiaSource, lambda: GaiaClient(svc.client).cone(ra, dec, 0.1, g_max=17.0),
                                       *_exact(ra, dec, 0.1, 17.0))
        # Any Gaia source blended with the target is fitted simultaneously (two-source photometry).
        mjd_obs = float(np.median([float(r.hdus['IMAGE'][0]['MJD-AVG']) for r in raws]))
        neighbours = blend_neighbours(target, candidates, mjd_obs)[:1]
        field = await asyncio.to_thread(isolated_field_stars, candidates, ra, dec)
    field_points: dict[Any, list[Any]] = {}
    index_points: dict[Any, list[Any]] = {}
    mjds = [frame_mjd(r) for r in raws]
    target_at = FramePositions([target], mjds)
    neighbour_targets = [
        Target("", "star", str(g.source_id), g.ra, g.dec, 2016.0, g.pmra, g.pmdec, g.parallax, g.radial_velocity)
        for g in neighbours
    ]
    neighbour_at = FramePositions(neighbour_targets, mjds)
    field_targets = [
        Target("", "star", str(g.source_id), g.ra, g.dec, 2016.0, g.pmra, g.pmdec, g.parallax, g.radial_velocity)
        for g in field
    ]
    # field stars are measured on D4/D5 frames only
    field_at = FramePositions(field_targets, [t for t, r in zip(mjds, raws, strict=True)
                                              if int(r.hdus["IMAGE"][0]["DETECTOR"]) in (4, 5)])
    for raw in raws:
        fid = raw.ref.id if raw.ref else "?"
        visit = fid_to_bin.get(fid, "?")
        if visits != "all" and visit not in visits.split(","):
            continue
        cf = await asyncio.to_thread(calibrate, raw, cal, preset="photometry")
        a, d = target_at(0, cf.mjd)
        x, y = map(float, cf.wcs.world_to_pixel_values(a[0], d[0]))
        xp, yp = int(round(x + cf.origin[0])), int(round(y + cf.origin[1]))
        if not (0 <= xp < 2040 and 0 <= yp < 2040):
            skipped.append([fid, "target outside parent detector"])
            continue
        neigh = []
        for j in range(len(neighbour_targets)):
            na, nd = neighbour_at(j, cf.mjd)
            neigh.append((na[0], nd[0]))
        point = await asyncio.to_thread(spectrum_point, cf, psfs[cf.detector], a[0], d[0], float(cal.solid_angle[cf.detector][yp, xp]), neigh)
        if point is None:
            skipped.append([fid, "QA, off-edge, missing calibration or degenerate native ePSF fit"])
            continue
        scales.add(point["photometric_scale"])
        index_points.setdefault((visit, point["photometric_scale"]), []).append(point)
        if cf.detector in (4, 5):
            for j, g in enumerate(field):
                fa, fd = field_at(j, cf.mjd)
                fx, fy = map(float, cf.wcs.world_to_pixel_values(fa[0], fd[0]))
                fpx, fpy = int(round(fx + cf.origin[0])), int(round(fy + cf.origin[1]))
                if not (0 <= fpx < 2040 and 0 <= fpy < 2040):
                    continue
                fp = await asyncio.to_thread(spectrum_point, cf, psfs[cf.detector], fa[0], fd[0], float(cal.solid_angle[cf.detector][fpy, fpx]))
                if fp is not None and not fp["contaminated"]:
                    field_points.setdefault((visit, point["photometric_scale"], g.source_id), []).append(fp)
        rows.append(
            dict(
                lam=point["lam"],
                dlam=point["dlam"],
                flux=point["flux_uJy"],
                err=point["err_uJy"],
                mjd=cf.mjd,
                visit=visit,
                detector=cf.detector,
                flags=point["flags_near"],
                rchi2=point["rchi2"],
                contaminated=point["contaminated"],
                release=raw.release,
                quality=point,
                frame_id=fid,
            )
        )
    from spherex.photometry import methane_index, wise_colour

    by_visit = {}
    for (visit, scale), points in index_points.items():
        ratios = []
        for (v, s, _gid), field_spectrum in field_points.items():
            if v != visit or s != scale:
                continue
            try:
                ratios.append(methane_index(field_spectrum, [1.0])["methane_rel"])
            except ValueError:
                continue
        if len(ratios) >= 3:
            try:
                by_visit[f"{visit}:{scale}"] = methane_index(points, ratios)
            except ValueError:
                pass
        try:
            colour = wise_colour(points)
            by_visit.setdefault(f"{visit}:{scale}", {})["w1w2_syn"] = colour
        except (ValueError, FileNotFoundError):
            pass
    latest = next(reversed(by_visit.values()), None) if by_visit else None
    from spherex.templates import template_overlays

    return dict(
        ra=ra,
        dec=dec,
        rows=rows,
        indices=dict(methane_rel=latest.get("methane_rel"), w1w2_syn=latest.get("w1w2_syn")) if latest else None,
        indices_by_visit=by_visit,
        templates=template_overlays(rows),
        validity=validity(svc, "spectrum"),
        notes=[
            "Signed native-frame flux; 3% calibration floor retained separately. Methane indices require at least three field-star spectra in the same visit and release scale.",
            "QR2 and QR3 rows are separate scales; cross-release indices and light curves prohibited until F4.",
            "Synthetic W1-W2 uses official WISE responses and Vega offsets; W2 is approximate because SPHEREx ends at 5 microns.",
        ],
        skipped=skipped,
        photometric_scales=sorted(scales),
        pin=m.get("pin"),
        native_frames=[r.ref.id for r in raws if r.ref is not None],
    )


async def astrometry_api(svc: Any, ra: float, dec: float, name: str = "", key: str | None = None) -> dict[str, Any]:
    planned = svc.store.manifest(key) if key else None
    tinfo = (planned or {}).get("target")
    if tinfo is None and name and svc.client is not None:
        from spherex.targets import to_result

        from .pipeline import cached_resolve

        try:
            tinfo = to_result(await cached_resolve(svc, name, svc.client))
        except Exception:  # unresolvable name: measure as a plain position
            tinfo = None
    wise = red_only(tinfo)
    m, raws, cal = await inputs(
        svc, ra, dec, key=key, name=name, min_fov=30 if wise else 12, detectors=(6,) if wise else None
    )
    target = target_from_manifest(m, ra, dec, True)
    if svc.client is None:
        raise HTTPException(409, "Differential astrometry needs Gaia stars in a >=12 arcmin registration region")
    r_reg = 0.25 if wise else 0.1
    stars = await cached_cone(svc, "gaia", GaiaSource, lambda: GaiaClient(svc.client).cone(ra, dec, r_reg, g_max=18.0),
                              *_exact(ra, dec, r_reg, 18.0))
    all_stars = list(stars)
    keep = isolated([s.ra for s in stars], [s.dec for s in stars])
    stars = [s for s, k in zip(stars, keep, strict=True) if k]
    psfs = epsfs(cal, [int(r.hdus["IMAGE"][0]["DETECTOR"]) for r in raws])
    points = []
    skipped = list(m.get("_measurement_fetch_skipped", []))
    reg = []
    joint_groups: dict[str, list[Any]] = {}
    joint_results = []
    from astropy import units as u

    ref = SkyCoord(ra * u.deg, dec * u.deg)
    fbin = {f["id"]: f["bin"] for f in m["frames"]}
    full_bins = {(int(band), b["id"]) for band, bs in m["bins"].items() for b in bs if b["status"] == "full"}
    times = [float(r.hdus["IMAGE"][0]["MJD-AVG"]) for r in raws]
    predictions = {}
    for s in stars:
        if s.ruwe is None or s.ruwe > 1.5 or s.pmra is None:
            continue
        if SkyCoord(s.ra * u.deg, s.dec * u.deg).separation(ref).arcsec < 15:
            continue
        t = Target("", "star", str(s.source_id), s.ra, s.dec, 2016.0, s.pmra, s.pmdec, s.parallax, s.radial_velocity)
        predictions[s.source_id] = t.pos(times)
    target_ra, target_dec = target.pos(times)
    neighbours = blend_neighbours(target, all_stars, float(np.median(times)))[:1] if wise else []
    neighbour_pos = None
    if neighbours:
        g = neighbours[0]
        neighbour_pos = Target(
            "", "star", str(g.source_id), g.ra, g.dec, 2016.0, g.pmra, g.pmdec, g.parallax, g.radial_velocity
        ).pos(times)
    for frame_index, raw in enumerate(raws):
        cf = await asyncio.to_thread(calibrate, raw, cal, preset="photometry")
        fid = raw.ref.id if raw.ref else "?"
        if not cf.qa["ok"]:
            skipped.append([fid, "frame QA"])
            continue
        residuals = []
        errors = []
        reference_ids = []
        for s in stars:
            if s.source_id not in predictions:
                continue
            a, d = (p[frame_index] for p in predictions[s.source_id])
            # The target (or an unresolved neighbour of a Gaia-invisible
            # target) must not anchor its own astrometric registration.
            if sep_arcsec(float(a), float(d), target_ra[frame_index], target_dec[frame_index]) < 18:
                continue
            x, y = map(float, cf.wcs.world_to_pixel_values(a, d))
            # OVERFLOW retained for photometry, excluded for astrometric reference stars.
            bad = cf.bad_phot | ((cf.flags & cf.bits.get("OVERFLOW", 0)) != 0)
            try:
                fit = await asyncio.to_thread(fit_native,
                    cf.sci,
                    cf.var,
                    bad,
                    psfs[cf.detector],
                    psfs[cf.detector].zone(x + cf.origin[0], y + cf.origin[1]),
                    x,
                    y,
                )
            except ValueError:
                continue
            if fit is None or fit.params[2] < 10 * fit.errors[2] or fit.wing_fit:
                continue
            a1, d1 = cf.wcs.pixel_to_world_values(*fit.params[:2])
            dx, dy = SkyCoord(a * u.deg, d * u.deg).spherical_offsets_to(SkyCoord(a1 * u.deg, d1 * u.deg))
            residuals.append([dx.arcsec, dy.arcsec])
            reference_ids.append(s.source_id)
            from spherex.astrometry import sky_covariance

            errors.append(
                np.sqrt(
                    np.diag(sky_covariance(cf.wcs, float(fit.params[0]), float(fit.params[1]), fit.covariance[:2, :2]))
                )
            )
        try:
            rr = registration(residuals, errors)
        except (ValueError, IndexError):
            skipped.append([fid, "fewer than five isolated unsaturated registration stars"])
            continue
        reg.append(
            dict(
                frame=fid,
                before=rr["before_rms"].tolist(),
                after=rr["after_rms"].tolist(),
                offset_arcsec=rr["offset"].tolist(),
                error_arcsec=rr["error"].tolist(),
                reference_source_ids=[int(s) for s, used in zip(reference_ids, rr["used"], strict=True) if used],
            )
        )
        if wise:
            visit = fbin.get(fid, "?")
            if (6, visit) not in full_bins:
                skipped.append([fid, "partial visit excluded from the joint red-band motion fit"])
                continue
            if neighbour_pos is None:
                skipped.append([fid, "no Gaia neighbour within 15 arcsec for the joint fit"])
                continue
            from spherex.joint_astrometry import prepare_frame

            try:
                frame = prepare_frame(
                    cf,
                    psfs[6],
                    (float(target_ra[frame_index]), float(target_dec[frame_index])),
                    (float(neighbour_pos[0][frame_index]), float(neighbour_pos[1][frame_index])),
                    rr,
                )
                joint_groups.setdefault(visit, []).append((frame, cf.mjd, fid))
            except ValueError as ex:
                skipped.append([fid, str(ex)])
            continue
        x, y = map(float, cf.wcs.world_to_pixel_values(target_ra[frame_index], target_dec[frame_index]))
        try:
            iz = psfs[cf.detector].zone(x + cf.origin[0], y + cf.origin[1])
            fit = await asyncio.to_thread(fit_native,
                cf.sci,
                cf.var,
                cf.bad_phot | ((cf.flags & cf.bits.get("OVERFLOW", 0)) != 0),
                psfs[cf.detector],
                iz,
                x,
                y,
            )
        except ValueError:
            fit = None
        if fit is None:
            skipped.append([fid, "target native centroid unconstrained"])
            continue
        a1, d1 = cf.wcs.pixel_to_world_values(*fit.params[:2])
        xi, eta = ref.spherical_offsets_to(SkyCoord(a1 * u.deg, d1 * u.deg))
        from spherex.astrometry import sky_covariance

        centroid_cov = sky_covariance(cf.wcs, float(fit.params[0]), float(fit.params[1]), fit.covariance[:2, :2])
        err = np.sqrt(np.diag(centroid_cov) + rr["error"] ** 2)
        points.append(
            dict(
                visit=fbin.get(fid, "?"),
                mjd=cf.mjd,
                xi=float(xi.arcsec - rr["offset"][0]),
                eta=float(eta.arcsec - rr["offset"][1]),
                s_xi=float(err[0]),
                s_eta=float(err[1]),
                band=cf.detector,
                frame_id=fid,
                native_xy=fit.params[:2].tolist(),
                flux_snr=float(fit.params[2] / fit.errors[2]),
                rchi2=fit.rchi2,
                cov_xi_eta=float(centroid_cov[0, 1]),
                fit_included=(cf.detector, fbin.get(fid, "?")) in full_bins
                and (not wise or cf.detector == 6),
            )
        )
    for visit, entries in joint_groups.items():
        from spherex.joint_astrometry import fit_visit

        try:
            result = fit_visit([e[0] for e in entries])
            epoch = float(np.mean([e[1] for e in entries]))
            a, d = target.pos([epoch])
            xi, eta = ref.spherical_offsets_to(SkyCoord(a[0] * u.deg, d[0] * u.deg))
            position = np.array([xi.arcsec, eta.arcsec]) + result["offset_arcsec"]
            covariance = result["covariance"]
            points.append(
                dict(
                    visit=visit,
                    mjd=epoch,
                    xi=float(position[0]),
                    eta=float(position[1]),
                    s_xi=float(np.sqrt(covariance[0, 0])),
                    s_eta=float(np.sqrt(covariance[1, 1])),
                    cov_xi_eta=float(covariance[0, 1]),
                    band=6,
                    fit_included=True,
                    rchi2=result["chi2"] / result["dof"],
                    method="joint-native-visit",
                )
            )
            joint_results.append(
                dict(
                    visit=visit,
                    frame_ids=[e[2] for e in entries],
                    **{
                        k: v.tolist() if isinstance(v, np.ndarray) else v
                        for k, v in result.items()
                        if k != "start_solutions"
                    },
                    start_solutions=[
                        dict(offset_arcsec=s["offset_arcsec"].tolist(), chi2=s["chi2"])
                        for s in result["start_solutions"]
                    ],
                )
            )
        except (ValueError, np.linalg.LinAlgError) as ex:
            skipped.append(["joint:" + visit, str(ex)])
    fitout = None
    fit_points = [p for p in points if p["fit_included"]]
    if len(fit_points) >= 2:
        ts = Time([p["mjd"] for p in fit_points], format="mjd").jyear
        pa, pd = parallax_factors([p["mjd"] for p in fit_points], ra, dec)
        try:
            r = await asyncio.to_thread(motion_fit,
                ts,
                [p["xi"] for p in fit_points],
                [p["eta"] for p in fit_points],
                [p["s_xi"] for p in fit_points],
                [p["s_eta"] for p in fit_points],
                pa,
                pd,
                float(np.mean(ts)),
                (target.plx or 0) / 1000.0,
                xy_covariance=[p["cov_xi_eta"] for p in fit_points],
            )
            mu = r["params"][2:4]
            cov = r["covariance"][2:4, 2:4]
            amp = float(np.linalg.norm(mu))
            fitout = dict(
                pmra=mu[0],
                pmdec=mu[1],
                e_pmra=r["errors"][2],
                e_pmdec=r["errors"][3],
                mu=amp,
                e_mu=float(np.sqrt(mu @ cov @ mu) / amp) if amp else float(np.sqrt(np.trace(cov))),
                pa_deg=float(np.degrees(np.arctan2(mu[0], mu[1])) % 360),
                plx_fixed=None if r["plx_fixed"] is None else r["plx_fixed"] * 1000.0,
                chi2=r["chi2"],
                dof=r["dof"],
                delta_chi2=r["delta_chi2"],
            )
        except (ValueError, np.linalg.LinAlgError) as e:
            skipped.append(["motion-fit", str(e)])
    catalogue = None
    if target.pmra is not None and target.pmdec is not None:
        catalogue = dict(
            source=target.astrometry_source or "manifest catalogue",
            pmra=target.pmra / 1000.0,
            pmdec=target.pmdec / 1000.0,
            mu=float(np.hypot(target.pmra, target.pmdec) / 1000.0),
            pa_deg=float(np.degrees(np.arctan2(target.pmra, target.pmdec)) % 360),
        )
    return dict(
        name=target.name,
        points=points,
        fit=fitout,
        catalogue=catalogue,
        validity=validity(svc, "astrometry"),
        skipped=skipped,
        registration=reg,
        joint_fits=joint_results,
        notes=[
            "Gaia-invisible brown dwarfs (e.g. WISE 0855) use a band-6 joint native-pixel fit with their nearest Gaia neighbour per full visit, with independent nonnegative source fluxes per frame and registration nuisances. Catalogue motion/parallax is used within each visit, not to fix the independent visit offsets. Covariance remains conditional on the ePSF and registration model.",
            "A two-epoch motion fit has zero residual model-test degrees of freedom.",
        ]
        if wise
        else [],
        tangent_origin=[ra, dec],
        pin=m.get("pin"),
        native_frames=[r.ref.id for r in raws if r.ref is not None],
    )


async def sso_api(svc: Any, name: str, mjd: list[float]) -> dict[str, Any]:
    if svc.client is None:
        raise HTTPException(409, "Horizons client unavailable offline")
    try:
        rows = await positions(svc.client, name, mjd)
    except ValueError as e:
        raise HTTPException(422, str(e)) from e
    return dict(
        name=name, observer=CENTER, points=[dict(mjd=t, ra=a, dec=d) for t, (a, d) in zip(mjd, rows, strict=True)]
    )


async def lightcurve_api(
    svc: Any,
    ra: float,
    dec: float,
    bin: str = "14d",
    bands: str = "",
    method: str = "psf",
    release: str = "",
    key: str | None = None,
) -> dict[str, Any]:
    from spherex.lightcurve import annulus_measure, correlated_periodogram, normalized_curve

    if method not in ("psf", "annulus"):
        raise HTTPException(400, "method must be psf or annulus")
    try:
        width = float(bin.removesuffix("d"))
    except ValueError:
        raise HTTPException(400, "bin must be a number of days, e.g. 14d") from None
    if not np.isfinite(width) or width <= 0:
        raise HTTPException(400, "bin width must be finite and positive")
    if release not in ("", "qr2", "qr3"):
        raise HTTPException(400, "release must be qr2 or qr3")
    m, raws, cal = await inputs(svc, ra, dec, key=key, release=release, include_capped=True)
    target = target_from_manifest(m, ra, dec, True)
    psfs = epsfs(cal, [int(r.hdus["IMAGE"][0]["DETECTOR"]) for r in raws]) if method == "psf" else {}
    data = []
    skipped = list(m.get("_measurement_fetch_skipped", []))
    target_at = FramePositions([target], [frame_mjd(r) for r in raws])
    for raw in raws:
        cf = await asyncio.to_thread(calibrate, raw, cal, preset="photometry")
        if bands and str(cf.detector) not in bands.split(","):
            continue
        a, d = target_at(0, cf.mjd)
        x, y = map(float, cf.wcs.world_to_pixel_values(a[0], d[0]))
        xp, yp = int(round(x + cf.origin[0])), int(round(y + cf.origin[1]))
        try:
            if not cf.qa["ok"] or not (0 <= xp < 2040 and 0 <= yp < 2040):
                raise ValueError("QA or outside detector")
            if method == "annulus":
                f, e = await asyncio.to_thread(annulus_measure, cf.sci, cf.var, cf.bad_phot, x, y)
            else:
                p = await asyncio.to_thread(spectrum_point, cf, psfs[cf.detector], a[0], d[0], float(cal.solid_angle[cf.detector][yp, xp]))
                if p is None or p["contaminated"]:
                    raise ValueError("invalid or contaminated ePSF fit")
                # A shared multiplicative calibration cancels in F/Sref;
                # do not count that common floor as independent sample noise.
                f, e = p["flux_uJy"], p["stat_err_uJy"]
            data.append(
                dict(
                    detector=cf.detector,
                    channel=int(cal.channel[yp, xp]),
                    region=(xp // 100, yp // 100),
                    mjd=cf.mjd,
                    flux=f,
                    err=e,
                    scale=cf.photometric_scale,
                )
            )
        except (ValueError, IndexError) as ex:
            skipped.append([raw.ref.id if raw.ref else cf.obsid, str(ex)])   # frame ids, like every other list
    if not data:
        # Say why instead of the science module's generic "observations required" (e.g. a saturated star in PSF mode)
        raise HTTPException(
            409,
            f"No usable {method.upper() if method == 'psf' else method} measurement at this position in "
            f"{release.upper() or 'any release'}: all {len(raws)} frames were rejected (saturated, flagged or failed fits). "
            "A saturated star needs the annulus method (open the view with mask=bright), or try the other release.",
        )
    try:
        normalized = normalized_curve(data, width, method)
        curves = normalized["bands"]
    except ValueError as ex:
        raise HTTPException(409, str(ex)) from ex
    # Six detector measurements in one time bin are one epoch, not six bins.
    grouped: dict[str, list[Any]] = {}
    for band, values in curves.items():
        for point in values:
            if point["err"] > 0:
                grouped.setdefault(point["bin"], []).append(dict(point, detector=band))
    allpoints: list[dict[str, Any]] = []
    merge = np.zeros((len(grouped), len(normalized["covariance_order"])))
    for binid, points in grouped.items():
        weight = np.array([1 / p["err"] ** 2 for p in points])
        for p, w in zip(points, weight / weight.sum(), strict=True):
            merge[len(allpoints), normalized["covariance_order"].index([p["detector"], binid])] = w
        allpoints.append(
            dict(
                mjd=float(weight @ np.array([p["mjd"] for p in points]) / weight.sum()),
                rel=float(weight @ np.array([p["rel"] for p in points]) / weight.sum()),
                err=float(1 / np.sqrt(weight.sum())),
                bin=binid,
            )
        )
    pg = None
    if allpoints:
        try:
            pg = correlated_periodogram(
                [p["mjd"] for p in allpoints],
                [p["rel"] for p in allpoints],
                merge @ np.asarray(normalized["covariance"]) @ merge.T,
            )
        except ValueError:
            pass
    return dict(
        bands=curves,
        covariance=normalized["covariance"],
        covariance_order=normalized["covariance_order"],
        reference_spectrum=normalized["reference"],
        uncertainty=normalized.get("uncertainty", "No usable repeated channels")
        + " Periodogram uses propagated covariance; simulated FAP is conditional on that estimated Gaussian noise model, not PSF or temporal-template systematics.",
        periodogram=pg,
        method=method,
        label="relative, qualitative" if method == "annulus" else "relative, spectrally normalized",
        validity=validity(svc, "lightcurve"),
        photometric_scales=sorted({r["scale"] for r in data}),
        pin=m.get("pin"),
        native_frames=[r.ref.id for r in raws if r.ref is not None],
        skipped=skipped,
    )


async def movers_api(svc: Any, key: str, mode: str = "stellar", mu_max: float = 10.0) -> dict[str, Any]:
    from spherex.linking import link_detections, score_chain

    # Detection products are persisted with native-frame vetting by the mover job.
    m = svc.store.manifest(key)
    if m is None:
        raise HTTPException(404, "unknown view")
    if mode == "planetx" and (not m.get("axis", "").startswith("bin:1d") or float(m["params"]["fov"]) < 30):
        raise HTTPException(409, "Planet X linking requires per-day bins and FOV >=30 arcmin")
    detections = m.get("_native_detections")
    if detections is None:
        detections = await view_native_detections(svc, key, m)
    if mode == "planetx":
        from spherex.epochs import cluster_visits
        from spherex.planetx import infer_distance, link_orphans, orphan_rows

        rows = orphan_rows(detections)
        from spherex.linking import vet_detection

        rows = [d for d in rows if not d.get("known") and not vet_detection(d, 3.0)]
        if not rows:
            return dict(key=key, candidates=[], tracked=tracked_planetx(svc, m), validity=validity(svc, "planetx"))
        labels = cluster_visits(np.array([d["mjd"] for d in rows]))
        for row, label in zip(rows, labels, strict=True):
            row["day"] = int(row["mjd"])
            row["visit"] = f"V{label}"
        out = []
        for i, planet_chain in enumerate(link_orphans(rows, *m["grid"]["crval"])):
            data = planet_chain["chain"]
            try:
                r = infer_distance(
                    [p["mjd"] for p in data],
                    [p["xi"] for p in data],
                    [p["eta"] for p in data],
                    [max(p["s_xi"], p["s_eta"]) for p in data],
                    *m["grid"]["crval"],
                )
            except (ValueError, np.linalg.LinAlgError):
                continue
            if r["dof"] <= 0 or r["chi2"] / r["dof"] > 3.0:
                continue
            out.append(
                dict(
                    id=f"planetx-{i}",
                    ra=data[0]["ra"],
                    dec=data[0]["dec"],
                    visits=sorted({p["visit"] for p in data}),
                    distance_au=r["distance_au"],
                    distance_error_au=r["error_au"],
                    why=[
                        planet_chain["label"],
                        f"grid hypothesis {planet_chain['distance_grid_au']} AU; bounded orbital nuisance",
                    ],
                    score=None,
                    known=None,
                    pm_arcsec_yr=None,
                    pa_deg=None,
                )
            )
        return dict(key=key, candidates=out, tracked=tracked_planetx(svc, m), validity=validity(svc, "planetx"))
    out = []
    skipped = []
    orphan_queue = []
    for chain in link_detections(detections, mu_max=mu_max):
        if len(chain) == 1:
            from spherex.linking import vet_detection

            row = chain[0]
            if not row.get("known") and not vet_detection(row, 3.0):
                orphan_queue.append(
                    dict(
                        id=str(row["id"]),
                        ra=row["ra"],
                        dec=row["dec"],
                        mjd=row["mjd"],
                        visit=row["visit"],
                        queues=["asteroid", "planetx"],
                        status="unvalidated; exposure-level ephemeris vetting required",
                    )
                )
        if len(chain) < 3:
            continue
        try:
            result = score_chain(chain, chain[0].get("catalogue_parallax"), max_rchi2=3.0)
        except (ValueError, np.linalg.LinAlgError) as ex:
            skipped.append([str(chain[0]["id"]), str(ex)])
            continue
        if result["candidate"]:
            out.append(
                dict(
                    id=str(chain[0]["id"]),
                    ra=chain[0]["ra"],
                    dec=chain[0]["dec"],
                    pm_arcsec_yr=result["mu"],
                    pa_deg=result["pa_deg"],
                    visits=[d["visit"] for d in chain],
                    known=result["known"],
                    score=result["score"],
                )
            )
        elif (result["vetoes"] and result["score"] > 25 and result["mu"] > 3 * result["e_mu"]
              and result["shift_px"] > 0.3):
            # Significant motion that fails vetting (a saturated star such as Barnard's: PSF residuals, BLOOM) is
            # reported as excluded with its reasons, never dropped silently. It is still not a candidate.
            why = (f"{result['known'] or 'unmatched source'}: moves {result['mu']:.2f} ± {result['e_mu']:.2f}″/yr over "
                   f"{len(chain)} visits, vetoed ({', '.join(result['vetoes'])})")
            if all(w != why for _, w in skipped):
                skipped.append([str(chain[0]["id"]), why])
    return dict(key=key, candidates=out, orphans=orphan_queue, validity=validity(svc, "movers"), skipped=skipped)


def stars_pos(targets: list[Target], mjd: Any) -> list[tuple[Any, Any]]:
    """[t.pos(mjd) for t in targets] for catalogue stars, batched: one astropy space-motion call per epoch for each
    group of stars that share a catalogue epoch and the same distance / radial-velocity terms, instead of one call per
    star (a 6′ field has thousands of Gaia stars). Same steps as targets.seen_by_spherex, elementwise over stars;
    the mover detections it feeds were checked identical on a real Barnard's Star visit."""
    import astropy.units as u
    from astropy.coordinates import Distance, SkyCoord
    from astropy.time import Time

    mjd = np.atleast_1d(np.asarray(mjd, float))
    out: list[Any] = [None] * len(targets)
    groups: dict[tuple[float, bool, bool], list[int]] = {}
    for i, t in enumerate(targets):
        if t.kind != "star" or not t.moving:
            out[i] = t.pos(mjd)
            continue
        has_d = t.plx is not None and t.plx > 0
        groups.setdefault((float(t.epoch), has_d, has_d and t.rv is not None), []).append(i)
    for (epoch, has_d, has_rv), idx in groups.items():
        ts = [targets[i] for i in idx]
        kw: dict[str, Any] = {}
        if has_d:
            kw["distance"] = Distance(parallax=np.array([t.plx for t in ts], float) * u.mas)
            if has_rv:
                kw["radial_velocity"] = np.array([t.rv for t in ts], float) * u.km / u.s
        c = SkyCoord(
            ra=np.array([t.ra for t in ts], float) * u.deg,
            dec=np.array([t.dec for t in ts], float) * u.deg,
            pm_ra_cosdec=np.array([t.pmra or 0 for t in ts], float) * u.mas / u.yr,
            pm_dec=np.array([t.pmdec or 0 for t in ts], float) * u.mas / u.yr,
            obstime=Time(epoch, format="jyear"),
            **kw,
        )
        p = np.array([max(t.plx or 0.0, 0.0) / 1000.0 for t in ts])
        ra = np.empty((len(ts), len(mjd)))
        dec = np.empty((len(ts), len(mjd)))
        for k, when in enumerate(mjd):
            moved = c.apply_space_motion(new_obstime=Time(when, format="mjd"))
            pa, pd = parallax_factors(when, moved.ra.deg, moved.dec.deg)
            shifted = SkyCoord(moved.ra, moved.dec).spherical_offsets_by(p * pa * u.arcsec, p * pd * u.arcsec)
            ra[:, k], dec[:, k] = shifted.ra.deg, shifted.dec.deg
        for j, i in enumerate(idx):
            out[i] = (ra[j], dec[j])
    return out


# A healthy 6′ Gaia cone takes ≈46 s; past this IRSA is hanging (seen 2026-11-15: 3 × ReadTimeout, ≈7 min).
GAIA_REFERENCE_DEADLINE_S = 150.0
DETECTIONS_VERSION = 1  # bump when native_detections changes what it returns
_detection_runs: dict[str, asyncio.Future[list[list[dict[str, Any]]]]] = {}


async def view_native_detections(svc: Any, key: str, m: dict[str, Any]) -> list[list[dict[str, Any]]]:
    """native_detections once per view. They depend on the view only (pinned frame list, locked calibration), never on
    the motion limit or the search mode, so a second search with another `mu_max` reuses them instead of re-measuring
    every native frame (minutes). A run in progress is shared; a result with incomplete catalogue checks is not kept,
    so a later search can retry those catalogues."""
    import json

    from .store import atomic_write

    paths = []
    for st in [svc.store] + ([svc.snapshot] if getattr(svc, "snapshot", None) is not None else []):
        try:
            paths.append(st.vdir(key) / "science" / f"native_detections-v{DETECTIONS_VERSION}.json")
        except ValueError:
            pass
    for p in paths:
        if p.exists():
            try:
                cached: list[list[dict[str, Any]]] = json.loads(p.read_text(encoding="utf-8"))
                return cached
            except (OSError, ValueError):
                pass
    run = _detection_runs.get(key)
    if run is None:
        run = asyncio.ensure_future(native_detections(svc, m))
        _detection_runs[key] = run
        run.add_done_callback(lambda _f: _detection_runs.pop(key, None))
    detections = await asyncio.shield(run)
    if paths and all(d.get("catalogue_complete", True) for epoch in detections for d in epoch):
        try:
            atomic_write(paths[0], json.dumps(detections, default=float).encode())
        except (TypeError, ValueError, OSError):
            pass
    return detections


async def native_detections(svc: Any, m: dict[str, Any], progress: Any = None) -> list[list[dict[str, Any]]]:
    """I detection → M native fits, labels and artifact vetting. Never centroid a display image."""
    from astropy import units as u

    from spherex.grid import frame_to_grid, make_grid, significance
    from spherex.movers import detect, red_sum
    from spherex.stack import build_stack, sky_pixels

    from .science import _refs, _tbin

    cal = calibration.load(svc.calib_spec)
    if svc.calib_spec[0] != "locked" or svc.client is None:
        raise HTTPException(409, "Mover vetting needs locked calibration and catalogue clients")
    a, d = m["grid"]["crval"]
    grid = make_grid(a, d, float(m["params"]["fov"]), 6.15)
    ref = SkyCoord(a * u.deg, d * u.deg)
    radius = float(m["params"]["fov"]) / 60 / np.sqrt(2)
    import asyncio

    from spherex.external.catwise import CATWISE_EPOCH_MJD, CatwiseClient, CatwiseSource
    from spherex.external.simbad import SimbadClient, SimbadObject

    # Gaia (≈46 s for a 6′ field) runs at the same time as CatWISE and SIMBAD instead of before them; all three are
    # cached on disk by their exact query, so a repeated search does not ask TAP again.
    gaia_query = asyncio.ensure_future(cached_cone(
        svc, "gaia", GaiaSource, lambda: GaiaClient(svc.client).cone(a, d, radius + 0.1, g_max=20), *_exact(a, d, radius + 0.1, 20)))
    catalogue_rows = await asyncio.gather(
        cached_cone(svc, "catwise", CatwiseSource, lambda: CatwiseClient(svc.client).cone(a, d, radius + 0.1),
                    *_exact(a, d, radius + 0.1)),
        cached_cone(svc, "simbad-hpm", SimbadObject, lambda: SimbadClient(svc.client).high_pm_cone(a, d, radius + 0.15, 0),
                    *_exact(a, d, radius + 0.15)),
        return_exceptions=True,
    )
    try:
        stars = await asyncio.wait_for(gaia_query, GAIA_REFERENCE_DEADLINE_S)
    except TimeoutError:
        raise HTTPException(503, f"Gaia DR3 (queried through IRSA) did not answer within {GAIA_REFERENCE_DEADLINE_S:.0f} s. "
                                 "The moving-object search needs it as its reference star list; IRSA is probably slow "
                                 "or recovering from an outage, so try again in a few minutes.") from None
    catalogue_complete = not any(isinstance(rows, BaseException) for rows in catalogue_rows)
    other_targets = []
    if isinstance(catalogue_rows[0], list):
        for c in catalogue_rows[0]:
            other_targets.append(
                Target(
                    "",
                    "star",
                    "CatWISE2020 " + c.source_name,
                    c.ra,
                    c.dec,
                    float(Time(CATWISE_EPOCH_MJD, format="mjd").jyear),
                    c.pmra,
                    c.pmdec,
                )
            )
    if isinstance(catalogue_rows[1], list):
        for s in catalogue_rows[1]:
            if s.ra is not None and s.dec is not None:
                other_targets.append(
                    Target("", "star", "SIMBAD " + s.main_id, s.ra, s.dec, 2000.0, s.pmra, s.pmdec, s.plx)
                )
    epochs = []
    gaia_targets = [
        Target("", "star", str(s.source_id), s.ra, s.dec, 2016.0, s.pmra, s.pmdec, s.parallax, s.radial_velocity)
        for s in stars
    ]
    bright_targets = [t for s, t in zip(stars, gaia_targets, strict=True) if (s.phot_g_mean_mag or 99) <= 12]
    bin_lookup = {b["id"]: b for bs in m["bins"].values() for b in bs}
    bins_sorted = sorted(bin_lookup.values(), key=lambda b: b["mjd_mean"])
    # Target.pos is elementwise in time: propagate each catalogue source once for every bin epoch, instead of one
    # astropy space-motion call per (source, bin). Those calls were most of the run time (≈175 s of 305 s per visit).
    bin_mjds = [b["mjd_mean"] for b in bins_sorted]
    gaia_pos = stars_pos(gaia_targets, bin_mjds)
    other_pos = stars_pos(other_targets, bin_mjds)
    for bi, b in enumerate(bins_sorted):
        binid = b["id"]
        groups = {}
        stacked = {}
        for band in range(1, 7):
            if not any(x["id"] == binid for x in m["bins"].get(str(band), [])):
                continue
            raws = await _raws(svc, m, _refs(m, band, binid))
            frames = []
            for r in raws:
                frames.append(await asyncio.to_thread(calibrate, r, cal, preset="discovery"))
            frames = [f for f in frames if f.qa["ok"]]
            if len({f.photometric_scale for f in frames}) > 1:
                raise HTTPException(409, "F4 unresolved: mover detection stack mixes release scales")
            if frames:
                groups[band] = frames
                stacked[band] = build_stack([frame_to_grid(f, grid) for f in frames], _tbin(m, band, binid), grid)
        if not stacked:
            continue
        peaks: list[Any] = []
        for st in stacked.values():
            sig, _ = significance(st.mean, st.var, sky_pixels(st))
            peaks.extend(detect(sig, pix_arcsec=grid.pix_arcsec))
        if 5 in stacked and 6 in stacked:
            mean, var = red_sum(stacked[5].mean, stacked[5].var, stacked[6].mean, stacked[6].var)
            sig, _ = significance(mean, var, sky_pixels(stacked[6]))
            peaks.extend(detect(sig, pix_arcsec=grid.pix_arcsec))
        det: list[Any] = []
        for peak in sorted(peaks, key=lambda p: -p["peak"]):
            if all(np.hypot(peak["x"] - other["x"], peak["y"] - other["y"]) > 1 for other in det):
                det.append(peak)
        psfs = epsfs(cal, groups.keys())
        # These predictions depend on exposure/epoch, never on a candidate.
        # Reusing them avoids thousands of repeated ERFA propagations per field; each bright star is propagated
        # once for all exposures of the bin (elementwise in time, same values as one call per exposure).
        all_frames = [cf for frames in groups.values() for cf in frames]
        frame_mjds = [cf.mjd for cf in all_frames]
        bright_at = [t.pos(frame_mjds) for t in bright_targets] if all_frames else []
        bright_pixels = {}
        for k, cf in enumerate(all_frames):
            bright_pixels[id(cf)] = [
                tuple(float(v) for v in cf.wcs.world_to_pixel_values(pa[k], pd[k])) for pa, pd in bright_at
            ]
        gaia_sky = SkyCoord([p[0][bi] for p in gaia_pos] * u.deg, [p[1][bi] for p in gaia_pos] * u.deg)
        other_sky = SkyCoord([p[0][bi] for p in other_pos] * u.deg, [p[1][bi] for p in other_pos] * u.deg)
        epoch = []
        for i, candidate in enumerate(det):
            cra, cdec = map(float, grid.wcs.pixel_to_world_values(candidate["x"], candidate["y"]))
            measurements = []
            spectral_samples: dict[int, list[Any]] = {}
            flags = set()
            chi = []
            echo = []
            for band, frames in groups.items():
                for cf in frames:
                    x, y = map(float, cf.wcs.world_to_pixel_values(cra, cdec))
                    try:
                        iz = psfs[band].zone(x + cf.origin[0], y + cf.origin[1])
                        fit = await asyncio.to_thread(fit_native, cf.sci, cf.var, cf.bad_phot, psfs[band], iz, x, y)
                    except ValueError:
                        continue
                    if fit is None or fit.params[2] <= 3 * fit.errors[2]:
                        continue
                    ra1, dec1 = cf.wcs.pixel_to_world_values(*fit.params[:2])
                    dx, dy = ref.spherical_offsets_to(SkyCoord(ra1 * u.deg, dec1 * u.deg))
                    from spherex.astrometry import sky_covariance

                    sky_error = np.sqrt(
                        np.diag(
                            sky_covariance(cf.wcs, float(fit.params[0]), float(fit.params[1]), fit.covariance[:2, :2])
                        )
                    )
                    measurements.append([dx.arcsec, dy.arcsec, *sky_error])
                    from spherex.photometry import to_uJy

                    px, py = int(round(x + cf.origin[0])), int(round(y + cf.origin[1]))
                    ch = int(cal.channel[py, px])
                    if 1 <= ch <= 17:
                        area = float(cal.solid_angle[band][py, px])
                        spectral_samples.setdefault((band - 1) * 17 + ch - 1, []).append(
                            [float(to_uJy(fit.params[2], area)), float(to_uJy(fit.errors[2], area))]
                        )
                    flags.update(cf.flags_near(*fit.params[:2]))
                    chi.append(fit.rchi2)
                    for sx, sy in bright_pixels[id(cf)]:
                        echo.append((float(sx - x), float(sy - y)))
            if not measurements:
                continue
            vals = np.asarray(measurements)
            wx = 1 / vals[:, 2] ** 2
            wy = 1 / vals[:, 3] ** 2
            xi = float(wx @ vals[:, 0] / wx.sum())
            eta = float(wy @ vals[:, 1] / wy.sum())
            measured = ref.spherical_offsets_by(xi * u.arcsec, eta * u.arcsec)
            cra, cdec = float(measured.ra.deg), float(measured.dec.deg)
            pa, pd = parallax_factors(b["mjd_mean"], cra, cdec)
            known = None
            plx = None
            matches = np.flatnonzero(measured.separation(gaia_sky).arcsec < 6.15)
            if len(matches):
                star = stars[int(matches[0])]
                known = f"Gaia DR3 {star.source_id}"
                plx = max(star.parallax or 0, 0) / 1000
            if known is None:
                matches = np.flatnonzero(measured.separation(other_sky).arcsec < 6.15)
                if len(matches):
                    source = other_targets[int(matches[0])]
                    known = source.name
                    plx = max(source.plx or 0, 0) / 1000
            spectrum = np.full(102, np.nan)
            spectrum_error = np.full(102, np.nan)
            for ch, values in spectral_samples.items():
                flux, err = np.asarray(values).T
                weight = 1 / err**2
                spectrum[ch] = weight @ flux / weight.sum()
                spectrum_error[ch] = np.hypot(1 / np.sqrt(weight.sum()), 0.03 * abs(spectrum[ch]))
            epoch.append(
                dict(
                    id=f"{binid}-{i}",
                    xi=xi,
                    eta=eta,
                    mjd=b["mjd_mean"],
                    s_xi=float(1 / np.sqrt(wx.sum())),
                    s_eta=float(1 / np.sqrt(wy.sum())),
                    p_a=float(pa),
                    p_d=float(pd),
                    flags=sorted(flags),
                    rchi2=float(max(chi)),
                    bright_neighbours=echo,
                    visit=binid,
                    ra=cra,
                    dec=cdec,
                    known=known,
                    catalogue_parallax=plx,
                    catalogue_complete=catalogue_complete,
                    spectrum=spectrum.tolist(),
                    spectrum_err=spectrum_error.tolist(),
                )
            )
        epochs.append(epoch)
        if progress is not None:
            progress(epochs)
    return epochs


def tracked_planetx(svc: Any, m: dict[str, Any], bands: tuple[int, ...] = (5, 6), threshold: float = 5.0) -> list[dict[str, Any]]:
    """Shift-and-stack variant of Planet X mode (implementation.md §4.12): for each distance hypothesis, shift
    every per-day band 5/6 stack by the predicted parallactic offset and coadd, then detect on the renormalised
    significance. Candidates only: their flux and position must be re-measured on native frames."""
    from spherex.grid import significance
    from spherex.movers import detect
    from spherex.planetx import DISTANCES_AU, shift_and_stack

    from .main import _payload_path

    ny, nx = m["grid"]["shape"]
    ra, dec = m["grid"]["crval"]
    out: list[dict[str, Any]] = []
    for band in bands:
        imgs, vars_, mjds = [], [], []
        for b in m["bins"].get(str(band), []):
            fp, vp = _payload_path(svc, m["key"], b["id"], band, "f32"), _payload_path(svc, m["key"], b["id"], band, "var.f32")
            if fp is None or vp is None:
                continue
            imgs.append(np.frombuffer(fp.read_bytes(), "<f4").reshape(ny, nx))
            vars_.append(np.frombuffer(vp.read_bytes(), "<f4").reshape(ny, nx))
            mjds.append(b["mjd_mean"])
        if len(imgs) < 4:
            continue
        # Static sources would survive every hypothesis: remove the per-pixel median over days first.
        with np.errstate(all="ignore"):
            res = np.asarray(imgs, float) - np.nanmedian(np.asarray(imgs, float), axis=0)
        for d in DISTANCES_AU:
            img, var = shift_and_stack(res, vars_, mjds, ra, dec, d, m["grid"]["pix_arcsec"])
            sig, _ = significance(img, var, np.isfinite(img))
            for s in detect(sig, threshold, pix_arcsec=m["grid"]["pix_arcsec"]):
                out.append(dict(band=band, distance_au=d, x=float(s["x"]), y=float(s["y"]), peak_sigma=float(s["peak"]),
                                n_days=len(imgs), status="unvalidated; shift-and-stack candidate"))
    return out[:500]
