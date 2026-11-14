"""Per-frame preprocessing (implementation.md §4.3)."""

from typing import Any

import numpy as np
from astropy.stats import sigma_clipped_stats
from numpy.typing import NDArray

from .calib import parent_slice
from .constants import PIXEL_ARCSEC
from .epochs import survey_number
from .flags import bad_mask, flag_bits
from .stack import frame_weight
from .types import CalFrame, Calib, RawFrame

A = NDArray[Any]

SMOOTH_BKG_ARCMIN = 10.0     # larger boxes get a 2-D background: atmospheric lines vary along the LVF axis
SMOOTH_BKG_BOX_PX = 16


def _background(sci: A, sky: A, smooth: bool) -> Any:
    """Scalar sigma-clipped median of sky pixels, or a smooth 2-D background (photutils
    Background2D, box ≈ 16 px) for large boxes. Falls back to the scalar if the 2-D fit can't run."""
    med = sigma_clipped_stats(sci[sky], sigma=3.0)[1] if sky.any() else 0.0
    if not smooth:
        return med
    from photutils.background import Background2D
    try:
        bk = Background2D(np.where(sky, sci, med), SMOOTH_BKG_BOX_PX, mask=~sky, filter_size=3,
                          exclude_percentile=50.0)
        return bk.background
    except ValueError:                               # too few unmasked pixels per box
        return med


def calibrate_frame(hdus: Any, origin: tuple[int, int], calib: Any, preset: str = "discovery",
                    release_scale: str = "qr3", min_sky_pix: int = 50, fluxcorr_op: str | None = None,
                    smooth_bkg: bool | None = None) -> tuple[Any, ...]:
    """Array-level core of `calibrate`. hdus: {"IMAGE"|"FLAGS"|"VARIANCE"|"ZODI": (header, data)};
    origin from the FrameSource. calib: anything with .cwave[det] (and .fluxcorr[det] for QR2).
    fluxcorr_op: None | "multiply" | "divide". It is foundation check F4 (owner M): until F4 is resolved
    callers pass None, QR2 frames stay on the QR2 scale and are labelled so (no mixed photometry)."""
    (hi, img), (hf, flg), (_, var), (_, zodi) = (hdus[k] for k in ("IMAGE", "FLAGS", "VARIANCE", "ZODI"))
    img, var, zodi = (np.asarray(a, float) for a in (img, var, zodi))
    flg = np.asarray(flg, np.int64)
    bits = flag_bits(hf)
    ps = parent_slice(origin, img.shape)              # origin from the FrameSource (§3.4), never guessed
    bad = bad_mask(flg, bits, preset) | ~np.isfinite(img) | ~(var > 0)
    sci = img - zodi                                  # 1) model zodi (not subtracted in L2)
    scale = release_scale
    if fluxcorr_op not in (None, "multiply", "divide"):
        raise ValueError("fluxcorr_op must be multiply, divide or None (F4)")
    if release_scale == "qr2" and fluxcorr_op is not None:   # 2) QR2 → QR3 photometric scale (F4)
        fc = np.asarray(calib.fluxcorr[int(hi["DETECTOR"])][ps], float)
        if fc.shape != img.shape or not np.all(np.isfinite(fc) & (fc > 0)):
            raise ValueError("invalid flux-correction map: finite positive factors at every native pixel required")
        fc = fc if fluxcorr_op == "multiply" else 1.0 / fc
        sci, var = sci * fc, var * fc ** 2
        scale = "qr3"
    src = (flg & bits.get("SOURCE", 0)) != 0          # 3) local residual background: He 1.083 µm,
    sky = ~bad & ~src                                 #    aurora, shuttle glow, zodi error
    if sky.sum() < min_sky_pix:                       #    SOURCE can cover ≈all pixels of a small,
        sky = ~bad                                    #    crowded box (81% at Barnard)
    if smooth_bkg is None:
        smooth_bkg = min(img.shape) * PIXEL_ARCSEC / 60 > SMOOTH_BKG_ARCMIN
    sci = sci - _background(sci, sky, smooth_bkg)
    sci[bad] = np.nan
    w_frame = frame_weight(var, sky)                  # 4) one weight per frame (§4.5)
    lam = np.asarray(calib.cwave[int(hi["DETECTOR"])][ps], float)   # per-pixel λ (µm)
    return sci, var, bad, lam, flg, bits, sky, w_frame, scale


# F8 decides whether L1/L2DQAFLG hard-reject a frame (see scripts/verify/f08_frame_qa.py).
REJECT_ON_DQAFLG: tuple[str, ...] = ("L1DQAFLG", "L2DQAFLG")   # F8 (2026-11-06): 0 of 3,878 frames fail


def frame_qa(img_hdr: Any, bad: A, max_bad_frac: float = 0.5,
             reject_on: tuple[str, ...] = REJECT_ON_DQAFLG) -> dict[str, Any]:
    """Frame-level QA (§4.3). Reject on FINAST != 0, > 50% bad pixels, or a 'Fail' in the DQA keywords
    listed in reject_on (policy set by foundation check F8). All DQA values are reported as badges."""
    finast = img_hdr.get("FINAST", 0)
    bad_frac = float(np.mean(bad)) if np.size(bad) else 1.0
    badges = {k: str(img_hdr.get(k, "")).strip() for k in ("L1DQAFLG", "L2DQAFLG")}
    reasons = []
    if finast != 0:
        reasons.append(f"FINAST={finast}")
    if bad_frac > max_bad_frac:
        reasons.append(f"bad={bad_frac:.0%}")
    reasons += [f"{k}={badges[k]}" for k in reject_on if badges.get(k, "").lower().startswith("fail")]
    return dict(ok=not reasons, reasons=reasons, bad_frac=bad_frac, badges=badges)


def calibrate(raw: RawFrame, calib: Calib, preset: str = "discovery", fluxcorr_op: str | None = None,
              smooth_bkg: bool | None = None, reject_on: tuple[str, ...] = REJECT_ON_DQAFLG) -> CalFrame:
    """RawFrame (D) -> CalFrame (I -> M). Never raises on a bad frame: QA lands in .qa and the caller
    lists rejected frames in the manifest (workflow.md §11.2: no silent drops)."""
    sci, var, bad, lam, flg, bits, sky, w, scale = calibrate_frame(
        raw.hdus, raw.origin, calib, preset, raw.release,
        fluxcorr_op=fluxcorr_op, smooth_bkg=smooth_bkg)
    hi = raw.hdus["IMAGE"][0]
    det = int(hi["DETECTOR"])
    ps = parent_slice(raw.origin, sci.shape)
    bad_phot = bad_mask(flg, bits, "photometry") | ~np.isfinite(np.asarray(raw.hdus["IMAGE"][1], float)) \
        | ~(var > 0)
    mjd = float(hi.get("MJD-AVG", raw.ref.t_min if raw.ref else np.nan))
    epa = hi.get("SPS_EPA")
    return CalFrame(sci=sci, var=var, bad=bad, bad_phot=bad_phot, lam=lam,
                    dlam=np.asarray(calib.cband[det][ps], float), flags=flg, bits=bits, sky=sky,
                    w_frame=float(w), wcs=raw.wcs, origin=raw.origin, detector=det, mjd=mjd,
                    obsid=str(hi.get("OBSID", raw.ref.obs_id if raw.ref else "")),
                    survey=survey_number(mjd, float(epa)) if epa is not None else None,
                    header=hi, qa=frame_qa(hi, bad, reject_on=reject_on), photometric_scale=scale,
                    preset=preset, ref=raw.ref)


def sky_noise_scale(sci: A, var: A, sky: A, tile: int = 16, min_px: int = 50, min_tiles: int = 3) -> float:
    """Empirical noise calibration of one native frame (F5 diagnosis, decision 0007).

    The ratio of the measured pixel scatter to the `VARIANCE` plane, from blank sky only: in each tile×tile
    block, the pulls (sci − weighted mean)/√var of `sky` pixels (background pixels, SOURCE-flagged pixels
    excluded) give a robust σ (1.4826·MAD); the frame's scale is the median over blocks. It never looks at a
    star or a PSF model, so using it in a star fit cannot tune the fit to a PSF. Returns NaN when fewer than
    `min_tiles` blocks have `min_px` sky pixels. 1.0 means VARIANCE describes the sky noise exactly."""
    sci, var = np.asarray(sci, float), np.asarray(var, float)
    ok = np.asarray(sky, bool) & np.isfinite(sci) & np.isfinite(var) & (var > 0)
    scales = []
    ny, nx = sci.shape
    for iy in range(0, ny - tile + 1, tile):
        for ix in range(0, nx - tile + 1, tile):
            sl = np.s_[iy : iy + tile, ix : ix + tile]
            m = ok[sl]
            if m.sum() < min_px:
                continue
            w = 1.0 / var[sl][m]
            z = (sci[sl][m] - np.sum(sci[sl][m] * w) / w.sum()) * np.sqrt(w)
            scales.append(1.4826 * np.median(np.abs(z - np.median(z))))
    return float(np.median(scales)) if len(scales) >= min_tiles else float("nan")
