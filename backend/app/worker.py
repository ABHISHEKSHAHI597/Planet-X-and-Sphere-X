"""CPU work of a view, run in the API's process pool (implementation.md §2.2 "Jobs"): one call per
(time-bin, band). Pure function of its arguments, so results are reproducible byte for byte (G2
"Reproducibility" criterion): frames are processed in frame-id order and nothing reads the clock.

I's chain: RawFrame → preprocess.calibrate (QA in .qa) → grid.frame_to_grid → stack.build_stack."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np

from spherex.grid import frame_to_grid, make_grid
from spherex.preprocess import calibrate
from spherex.render import to_f16, to_f32, to_u32_flags
from spherex.stack import build_stack
from spherex.types import RawFrame, TimeBin

from . import calibration


@dataclass
class FrameReport:
    id: str
    detector: int
    mjd: float
    survey: int | None
    obsid: str
    qa: dict[str, Any]
    skipped: str | None
    photometric_scale: str


@dataclass
class StackResult:
    bin: str
    band: int
    payloads: dict[str, bytes]
    nhits_max: int
    frame_ids: list[str]
    skipped: list[tuple[str, str]]
    frames: list[FrameReport]
    median_sample: Any  # the stack's mean (float64) for shared limits; dropped after use
    filled: bool = False
    scales: list[str] = field(default_factory=list)
    transients: list[dict[str, Any]] = field(default_factory=list)


def stack_task(
    raws: list[RawFrame],
    tbin: TimeBin,
    grid_args: tuple[float, float, float, float],
    preset: str,
    calib_spec: tuple[str, str],
    pre_skipped: list[tuple[str, str]],
    track_centres: dict[str, tuple[float, float]] | None = None,
    fill_position: tuple[float, float] | None = None,
) -> StackResult:
    """grid_args = (ra, dec, fov_arcmin, pix_arcsec). pre_skipped: frames that never arrived (fetch
    failures, caps) with their reasons, listed in the manifest beside QA rejections.
    track_centres: track mode (implementation.md §4.1): each frame is reprojected onto a grid of the same
    shape centred on pos(MJD) of that frame, so the target stays still and the stars stream past."""
    cal = calibration.load(calib_spec)
    grid = make_grid(*grid_args)
    fov, pix = grid_args[2], grid_args[3]
    gframes, skipped, reports = [], list(pre_skipped), []
    models = []
    scales: set[str] = set()
    for raw in sorted(raws, key=lambda r: r.ref.id if r.ref else ""):
        fid = raw.ref.id if raw.ref else "?"
        try:
            cf = calibrate(raw, cal, preset=preset)
        except Exception as e:  # malformed frame: listed, never fatal
            skipped.append((fid, f"calibration failed: {type(e).__name__}: {e}"[:200]))
            reports.append(
                FrameReport(
                    fid,
                    raw.ref.detector if raw.ref else 0,
                    raw.ref.t_min if raw.ref else 0.0,
                    None,
                    raw.ref.obs_id if raw.ref else "",
                    {},
                    skipped[-1][1],
                    raw.release,
                )
            )
            continue
        qa = {
            **{k: v for k, v in cf.qa["badges"].items()},
            "FINAST": int(cf.header.get("FINAST", 0)),
            "bad_frac": round(float(cf.qa["bad_frac"]), 4),
            "PSF_FWHM": _f(cf.header.get("PSF_FWHM")),
        }
        if not cf.qa["ok"]:
            reason = "QA: " + ", ".join(cf.qa["reasons"])
            skipped.append((fid, reason))
            reports.append(FrameReport(fid, cf.detector, cf.mjd, cf.survey, cf.obsid, qa, reason, cf.photometric_scale))
            continue
        g = grid if not track_centres or fid not in track_centres else make_grid(*track_centres[fid], fov, pix)
        try:
            gframes.append(frame_to_grid(cf, g))
        except Exception as e:  # e.g. a WCS that does not converge: listed, never fatal (audit K-17)
            reason = f"reprojection failed: {type(e).__name__}: {e}"[:200]
            skipped.append((fid, reason))
            reports.append(FrameReport(fid, cf.detector, cf.mjd, cf.survey, cf.obsid, qa, reason, cf.photometric_scale))
            continue
        if fill_position is not None and calib_spec[0] == "locked":
            from spherex.epsf import FittedPSF, fit_native, load_table

            a, d = track_centres[fid] if track_centres and fid in track_centres else fill_position
            x, y = map(float, cf.wcs.world_to_pixel_values(a, d))
            try:
                psf = load_table(str(cal.path("epsf", cf.detector)))
                zone = psf.zone(x + cf.origin[0], y + cf.origin[1])
                bad = cf.bad_phot | ((cf.flags & cf.bits.get("OVERFLOW", 0)) != 0)
                fit = fit_native(cf.sci, cf.var, bad, psf, zone, x, y)
                if fit is not None and fit.params[2] > 5 * fit.errors[2]:
                    model = FittedPSF(psf, zone, cf.wcs, *fit.params[:3]).render(g)
                    models.append((model, cf.w_frame))
            except Exception:  # noqa: BLE001 — no model is safer than extrapolating the finite ePSF wings
                pass
        scales.add(cf.photometric_scale)
        reports.append(FrameReport(fid, cf.detector, cf.mjd, cf.survey, cf.obsid, qa, None, cf.photometric_scale))
    st = build_stack(gframes, tbin, grid, skipped=skipped)
    if models and fill_position is not None:
        from spherex.stack import display_fill

        sw = sum(w for _, w in models)
        if sw > 0:
            model = sum(a * w for a, w in models) / sw
            x, y = grid.wcs.world_to_pixel_values(*fill_position)
            yy, xx = np.indices(grid.shape)
            st.display, st.filled = display_fill(st.mean, model, np.hypot(xx - x, yy - y) < 3)
    shown = st.display if st.display is not None else st.mean
    payloads = {
        "f16": to_f16(shown),
        "f32": to_f32(st.mean),
        "var.f32": to_f32(st.var),
        "flags.u32": to_u32_flags(st.flag_or),
    }
    if st.filled is not None:
        payloads["filled.u8"] = np.asarray(st.filled, np.uint8).tobytes()
    return StackResult(
        bin=tbin.id,
        band=tbin.band,
        payloads=payloads,
        nhits_max=int(st.nhits.max(initial=0)),
        frame_ids=st.frame_ids,
        skipped=st.skipped,
        frames=reports,
        median_sample=st.mean,
        filled=st.filled is not None,
        scales=sorted(scales),
        transients=_transients(st.transients, grid),
    )


MAX_TRANSIENTS = 200


def _transients(found: list[dict[str, Any]], grid: Any) -> list[dict[str, Any]]:
    """Asteroid-candidate transients (stack.transient_candidates) with sky positions; capped per stack.
    Track-mode grids differ per frame, so their positions are only approximate on the base grid."""
    out = []
    for t in found[:MAX_TRANSIENTS]:
        ra, dec = grid.wcs.wcs_pix2world(t["x"], t["y"], 0)
        out.append(dict(frame=str(t["frame"]), x=float(t["x"]), y=float(t["y"]), ra=float(ra), dec=float(dec),
                        npix=int(t["npix"])))
    return out


def _f(v: Any) -> float | None:
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    return x if np.isfinite(x) else None


# ------------------------------------------------------------------------------- λ products (G4a, G5.flip)


def _calibrated(raws: list[RawFrame], preset: str, cal: Any) -> list[Any]:
    """QA-passing CalFrames in frame-id order (the order every λ product stacks them in)."""
    out = []
    for raw in sorted(raws, key=lambda r: r.ref.id if r.ref else ""):
        try:
            cf = calibrate(raw, cal, preset=preset)
        except Exception:
            continue
        if cf.qa["ok"]:
            out.append(cf)
    return out


def _gridded(cfs: list[Any], grid: Any, order: str) -> list[Any]:
    out = []
    for cf in cfs:
        try:
            out.append(frame_to_grid(cf, grid, order))
        except Exception:  # noqa: BLE001 — listed as skipped in the view's own stack already
            continue
    return out


def _calibrated_grid_frames(raws: list[RawFrame], grid: Any, preset: str, cal: Any, order: str) -> list[Any]:
    return _gridded(_calibrated(raws, preset, cal), grid, order)


def diff_task(
    raws_a: list[RawFrame],
    raws_b: list[RawFrame],
    bin_a: TimeBin,
    bin_b: TimeBin,
    band: int,
    grid_args: tuple[float, float, float, float],
    preset: str,
    calib_spec: tuple[str, str],
    positions: list[tuple[float, float]],
    expected_pa: float | None,
    exclude_xy: list[tuple[float, float]] | None = None,
) -> dict[str, Any]:
    """I's λ-matched difference (implementation.md §4.6, decision 0003): bicubic resampling, PSF
    homogenisation to 1.5× the largest PSF_FWHM, per-pixel λ matching, renormalised significance, and
    auto-annotations at the given grid positions. A QR2/QR3 pair is matched in situ on the static sources
    outside PHOTMATCH_EXCLUDE_FWHM common-PSF FWHM of exclude_xy (the target in both visits; decision 0008);
    raises ValueError when that match cannot be made."""
    from spherex.cube import (
        DIFF_ORDER,
        PHOTMATCH_EXCLUDE_FWHM,
        annotate,
        build_cube,
        diff,
        diff_fwhm_arcsec,
        matched_pair,
    )
    from spherex.stack import sky_pixels

    cal = calibration.load(calib_spec)
    grid = make_grid(*grid_args)
    # Calibrate each frame once and grid it twice (bilinear for the sky masks, DIFF_ORDER for the cubes): calibrate
    # is deterministic, so this is the same result as calibrating twice, at half the cost (audit K-28).
    ca_, cb_ = _calibrated(raws_a, preset, cal), _calibrated(raws_b, preset, cal)
    sa = build_stack(_gridded(ca_, grid, "bilinear"), bin_a, grid)
    sb = build_stack(_gridded(cb_, grid, "bilinear"), bin_b, grid)
    ga = _gridded(ca_, grid, DIFF_ORDER)
    gb = _gridded(cb_, grid, DIFF_ORDER)
    if not ga or not gb:
        raise ValueError("one of the two visits has no usable frames in this band")
    fw = diff_fwhm_arcsec(ga, gb)
    ca = build_cube(ga, bin_a, band, grid, homog_fwhm_arcsec=fw)
    cb = build_cube(gb, bin_b, band, grid, homog_fwhm_arcsec=fw)
    df = diff(ca, cb, sky_pixels(sa) & sky_pixels(sb), exclude_xy=list(exclude_xy or positions),
              exclude_r_px=PHOTMATCH_EXCLUDE_FWHM * fw / grid.pix_arcsec)
    # pair: dipole shifts from the data's own PSF (fit_shift), as validated in G4a, not the Gaussian two-PSF model
    ann = annotate(df, positions, fw / grid.pix_arcsec, grid.pix_arcsec, expected_pa=expected_pa,
                   pair=matched_pair(ca, cb))
    return dict(f16=to_f16(df.sig), k=float(df.k), annotations=ann, fwhm_arcsec=fw,
                photometric_match=df.photometric_match)


def cube_task(
    raws: list[RawFrame],
    tbin: TimeBin,
    band: int,
    grid_args: tuple[float, float, float, float],
    preset: str,
    calib_spec: tuple[str, str],
) -> bytes:
    """λ-scrubber payload (P2-2): the (17, ny, nx) per-pixel spectral cube, f16, planes in bin order."""
    from spherex.cube import build_cube
    from spherex.render import cube_to_f16

    cal = calibration.load(calib_spec)
    grid = make_grid(*grid_args)
    gs = _calibrated_grid_frames(raws, grid, preset, cal, "bilinear")
    if not gs:
        raise ValueError("no usable frames in this bin")
    return cube_to_f16(build_cube(gs, tbin, band, grid).cube)


def flipbook_task(
    raws: list[RawFrame],
    band: int,
    grid_args: tuple[float, float, float, float],
    preset: str,
    calib_spec: tuple[str, str],
    target_at: dict[str, tuple[float, float]],
    track_centres: dict[str, tuple[float, float]] | None = None,
) -> list[dict[str, Any]]:
    """Exposure flipbook (P2-2, G5.flip): every QA-passing frame of one band on the view's grid, with the
    wavelength that frame actually saw at the target (the reprojected CWAVE map read at the target's
    grid pixel, nearest neighbour, like every λ lookup of the cube path). `target_at[frame_id]` is pos(t)
    at that frame's MJD. A frame whose λ at the target is not finite (target off the frame, or no locked
    calibration) gets lam_um=None; the caller never sorts it by a guessed wavelength."""
    cal = calibration.load(calib_spec)
    fov, pix = grid_args[2], grid_args[3]
    base = make_grid(*grid_args)
    out: list[dict[str, Any]] = []
    for raw in sorted(raws, key=lambda r: r.ref.id if r.ref else ""):
        fid = raw.ref.id if raw.ref else "?"
        try:
            cf = calibrate(raw, cal, preset=preset)
        except Exception:  # listed as skipped in the manifest already
            continue
        if not cf.qa["ok"] or cf.detector != band:
            continue
        g = base if not track_centres or fid not in track_centres else make_grid(*track_centres[fid], fov, pix)
        gf = frame_to_grid(cf, g)
        lam_um: float | None = None
        if fid in target_at:
            x, y = g.wcs.world_to_pixel_values(*target_at[fid])
            ix, iy = int(round(float(x))), int(round(float(y)))
            ny, nx = g.shape
            if 0 <= ix < nx and 0 <= iy < ny and np.isfinite(gf.lam[iy, ix]):
                lam_um = float(gf.lam[iy, ix])
        out.append(dict(id=fid, mjd=float(cf.mjd), lam_um=lam_um, f16=to_f16(gf.sci)))
    return out


def rgb_task(
    raws_by_band: dict[int, list[RawFrame]],
    bins_by_band: dict[int, TimeBin],
    grid_args: tuple[float, float, float, float],
    preset: str,
    calib_spec: tuple[str, str],
    name: str,
) -> bytes:
    """RGB preset composite (implementation.md §7: `rgb:methane`, `rgb:ice`): each channel is I's
    `cube.lambda_slice` — the inverse-variance mean of the cube bins whose *per-pixel measured* λ lies in
    the preset range — over the cubes of every band that covers the range. Returns (3, ny, nx) f16 in
    R, G, B order. A channel no pixel sampled is all no-data; nothing is filled from a neighbouring λ."""
    from spherex.constants import BANDS
    from spherex.cube import RGB_PRESETS, build_cube, lambda_slice

    ranges: tuple[tuple[float, float], ...] = RGB_PRESETS[name]  # type: ignore[assignment]  # λ-range presets only
    cal = calibration.load(calib_spec)
    grid = make_grid(*grid_args)
    cubes: dict[int, Any] = {}
    for band, raws in raws_by_band.items():
        gs = _calibrated_grid_frames(raws, grid, preset, cal, "bilinear")
        if gs:
            cubes[band] = build_cube(gs, bins_by_band[band], band, grid)
    planes = []
    for lo, hi in ranges:
        use = [c for b, c in cubes.items() if BANDS[b][0] <= hi and BANDS[b][1] >= lo]
        planes.append(lambda_slice(use, lo, hi)[0] if use else np.full(grid.shape, np.nan))
    return to_f16(np.stack(planes))


def blink25_task(
    archival: list[list[bytes]],
    spherex_stack: Any,
    view_grid: dict[str, Any],
    grid_args: tuple[float, float, float, float],
) -> list[tuple[bytes | None, int]]:
    """25-year blink (P2-1): every archival epoch, then the SPHEREx visit stack, on one blink grid and each on its
    own sky σ (I's `spherex.blink25`). Returns one (f16 payload or None, images used) per epoch, SPHEREx last."""
    from astropy.wcs import WCS

    from spherex.blink25 import epoch_on_grid, spherex_epoch

    grid = make_grid(*grid_args)
    out: list[tuple[bytes | None, int]] = []
    for images in archival:
        img, n = epoch_on_grid(images, grid)
        out.append((to_f16(img) if n else None, n))
    if spherex_stack is None:
        out.append((None, 0))
        return out
    from spherex.grid import to_grid

    w = WCS(naxis=2)
    w.wcs.ctype, w.wcs.crval = view_grid["ctype"], view_grid["crval"]
    w.wcs.crpix, w.wcs.cdelt = view_grid["crpix"], view_grid["cdelt"]
    st = np.asarray(spherex_stack, float)
    on, _ = to_grid(spherex_epoch(st), np.ones_like(st), w, grid.wcs, grid.shape)
    out.append((to_f16(on) if np.isfinite(on).any() else None, 1))
    return out
