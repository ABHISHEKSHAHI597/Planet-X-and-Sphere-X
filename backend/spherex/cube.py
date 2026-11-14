"""Spectral cubes, λ-matched differences, flipbook ordering (implementation.md §4.6, §7)."""

from collections.abc import Iterable, Sequence
from typing import TYPE_CHECKING, Any

from numpy.typing import ArrayLike, NDArray

if TYPE_CHECKING:
    from .types import Cube, Diff, Grid, GridFrame, TimeBin

import numpy as np
from scipy.optimize import linear_sum_assignment

from .constants import BANDS
from .constants import CHANNELS_PER_DETECTOR as NCH

A = NDArray[Any]

CH_LN = {d: np.log(hi / lo) / NCH for d, (lo, hi, _) in BANDS.items()}   # one channel, in ln λ


def spectral_cube(frames: A, var: A, lam: A, w_frame: ArrayLike, band: int, rej: A | None = None,
                  oversample: int = 1) -> tuple[A, A, A]:
    """Bin one (time-bin, band) frame set by the wavelength each pixel saw.
    frames/var/lam: (n, ny, nx) on the common grid (lam = reprojected CWAVE, µm).
    Returns cube, cube_var, cube_lam: (17·oversample, ny, nx). cube_lam is the mean λ each bin actually
    sampled at each pixel. NaN where no frame sampled that bin at that pixel."""
    lo, hi, _ = BANDS[band]
    nb = NCH * oversample
    ok = np.isfinite(frames) & np.isfinite(lam) & (var > 0)
    if rej is not None:
        ok &= ~rej
    idx = np.floor(nb * np.log(np.where(ok, lam, lo) / lo) / np.log(hi / lo)).astype(int).clip(0, nb - 1)
    w = np.where(ok, np.asarray(w_frame, float)[:, None, None], 0.0)
    f, v, lm = np.where(ok, frames, 0.0), np.where(ok, var, 0.0), np.where(ok, lam, 0.0)
    cube = np.full((nb,) + frames.shape[1:], np.nan)
    cvar, clam = np.full_like(cube, np.nan), np.full_like(cube, np.nan)
    for k in range(nb):
        wk = np.where(idx == k, w, 0.0)
        sw = wk.sum(axis=0)
        with np.errstate(invalid="ignore", divide="ignore"):
            cube[k] = (wk * f).sum(axis=0) / sw
            cvar[k] = (wk ** 2 * v).sum(axis=0) / sw ** 2
            clam[k] = (wk * lm).sum(axis=0) / sw
    return cube, cvar, clam


def at_wavelengths(lam_t: A, cube: A, cvar: A, clam: A, band: int, max_gap_ch: float = 0.75,
                   max_interp_ch: float = 2.0) -> tuple[A, A]:
    """Evaluate a cube's per-pixel spectrum at wavelengths lam_t (nb, ny, nx): linear in ln λ between
    the nearest sampled bins below and above. This removes the half-channel S1/S2 ↔ S3/S4 offset, which
    no pairing can. Where no bracketing pair lies within max_interp_ch channels, fall back to the
    nearest sampled bin if it lies within max_gap_ch channels; otherwise NaN.
    Deviation note (implementation.md §4.6): the documented version brackets with *adjacent* bin
    indices only. With max_interp_ch = 2 this gives the same values wherever that version returns one
    (adjacent bins' measured λ are < 2 channels apart); a larger max_interp_ch bridges missing bins
    (used by the null test, where each half-visit samples every other channel)."""
    nb = len(cube)
    with np.errstate(invalid="ignore", divide="ignore"):
        lt, ls = np.log(lam_t), np.log(clam)
    fin = np.isfinite(cube) & np.isfinite(ls)
    ar = np.arange(nb)[:, None, None]
    def take(a: A, j: A) -> A:
        return np.take_along_axis(a, j[None], axis=0)[0]
    f = np.full(np.shape(lam_t), np.nan)
    v = np.full(np.shape(lam_t), np.nan)
    ch = CH_LN[band]
    for k in range(len(lt)):
        with np.errstate(invalid="ignore"):
            below, above = fin & (ls <= lt[k]), fin & (ls > lt[k])
        j0 = np.where(below, ar, -1).max(axis=0)
        j1 = np.where(above, ar, nb).min(axis=0)
        has0, has1 = j0 >= 0, j1 < nb
        j0c, j1c = j0.clip(0, nb - 1), j1.clip(0, nb - 1)
        l0, l1 = take(ls, j0c), take(ls, j1c)
        f0, f1, v0, v1 = take(cube, j0c), take(cube, j1c), take(cvar, j0c), take(cvar, j1c)
        with np.errstate(invalid="ignore", divide="ignore"):
            t = (lt[k] - l0) / (l1 - l0)
            good = has0 & has1 & (l1 - l0 <= max_interp_ch * ch)
            d0 = np.where(has0, lt[k] - l0, np.inf)
            d1 = np.where(has1, l1 - lt[k], np.inf)
            near = ~good & (np.minimum(d0, d1) < max_gap_ch * ch)
            use0 = d0 <= d1
            f[k] = np.where(good, f0 * (1 - t) + f1 * t, np.where(near, np.where(use0, f0, f1), np.nan))
            v[k] = np.where(good, v0 * (1 - t) ** 2 + v1 * t ** 2, np.where(near, np.where(use0, v0, v1), np.nan))
        f[k][~np.isfinite(lt[k])] = np.nan
        v[k][~np.isfinite(lt[k])] = np.nan
    return f, v


def matched_difference(a: tuple[A, A, A], b: tuple[A, A, A], band: int, sky: A, max_interp_ch: float = 2.0,
                       sys_frac: float = 0.0, sys_shift_px: float = 0.0, b_at: tuple[A, A] | None = None,
                       scale: A | None = None, scale_err: A | None = None, offset: A | None = None,
                       offset_err: A | None = None) -> tuple[A, A]:
    """Visit A − visit B, matched in wavelength pixel by pixel. a, b: (cube, var, lam) from spectral_cube
    (same band, same grid). B's spectrum is interpolated to the wavelengths A sampled, so both the PA-flip
    gradient reversal and the half-channel survey offset drop out. Bin weights come from sky pixels, so
    bright sources don't down-weight themselves.
    sys_frac: fractional systematic per bin, added in quadrature to the variance as (sys_frac·flux)² for
    both visits; sys_shift_px a positional jitter (px) added as (sys_shift_px·|∇flux|)², the
    astrometric-noise term of ZOGY-style differencing. Both carry the resampling error of an undersampled
    PSF (see `diff`).
    b_at: B already evaluated at A's wavelengths (skips the interpolation). scale/offset (nb,): a per-bin
    photometric match B → scale·B + offset (fit_relative_scale); its uncertainty enters the variance as
    scale_err²·B² + offset_err², so a poorly determined gain widens the significance instead of hiding."""
    ca, va, la = a
    fb, vb = b_at if b_at is not None else at_wavelengths(la, *b, band, max_interp_ch=max_interp_ch)
    if scale is not None:
        s = np.asarray(scale, float)[:, None, None]
        es = np.zeros_like(s) if scale_err is None else np.asarray(scale_err, float)[:, None, None]
        c = np.zeros_like(s) if offset is None else np.asarray(offset, float)[:, None, None]
        ec = np.zeros_like(s) if offset_err is None else np.asarray(offset_err, float)[:, None, None]
        fb, vb = s * fb + c, s * s * vb + es * es * fb * fb + ec * ec
    ok = np.isfinite(ca) & np.isfinite(fb) & (va > 0) & (vb > 0)
    wk = np.zeros(len(ca))
    for k in range(len(ca)):
        s = ok[k] & sky
        if s.any():
            wk[k] = 1.0 / np.median(va[k][s] + vb[k][s])
    w = np.where(ok, wk[:, None, None], 0.0)
    sw = w.sum(axis=0)
    with np.errstate(invalid="ignore", divide="ignore"):
        d = (w * np.where(ok, ca - fb, 0.0)).sum(axis=0) / sw
        vs = va + vb + sys_frac ** 2 * (ca ** 2 + fb ** 2)
        if sys_shift_px:
            def g2(c: A) -> A:
                gy, gx = np.gradient(c, axis=(1, 2))
                return np.nan_to_num(gy) ** 2 + np.nan_to_num(gx) ** 2
            vs = vs + sys_shift_px ** 2 * (g2(ca) + g2(fb))
        v = (w ** 2 * np.where(ok, vs, 0.0)).sum(axis=0) / sw ** 2
    return d, v               # display significance(d, v, sky) (§4.4) with a diverging map


def pair_frames(lam_a: ArrayLike, lam_b: ArrayLike, band: int, tol_channels: float = 0.75) -> tuple[A, A]:
    """Fast path for target-only spectra: pair frames of two visits by λ *at the target*. 0.75 channel
    lets the half-channel S3/S4 offset pair, but the 0.5-channel mismatch then stays in the difference.
    Never use it for a whole field (workflow.md §11.2)."""
    cost = np.abs(np.log(lam_a)[:, None] - np.log(lam_b)[None, :])
    cost = np.where(np.isfinite(cost), cost, 1e9)        # a frame that missed the target never pairs
    ia, ib = linear_sum_assignment(cost)
    ok = cost[ia, ib] < tol_channels * CH_LN[band]
    return ia[ok], ib[ok]


def occupancy(frames: A, lam: A, var: A, band: int, oversample: int = 1) -> A:
    """Foundation check F16: samples per (bin, pixel) of one visit's cube. Returns (nb, ny, nx) counts."""
    lo, hi, _ = BANDS[band]
    nb = NCH * oversample
    ok = np.isfinite(frames) & np.isfinite(lam) & (var > 0)
    idx = np.floor(nb * np.log(np.where(ok, lam, lo) / lo) / np.log(hi / lo)).astype(int).clip(0, nb - 1)
    return np.stack([((idx == k) & ok).sum(axis=0) for k in range(nb)])


def flipbook_order(lam_at_target: ArrayLike, mjd: ArrayLike, sort: str = "lambda", max_frames: int = 64) -> A:
    """Exposure flipbook (P2-2, expert mode). Sorted by λ by default, because exposure order reads
    spectral change as variability (understanding.md §5.2). Decimated evenly to ≤ max_frames."""
    key = np.asarray(lam_at_target if sort == "lambda" else mjd, float)
    order = np.argsort(key, kind="stable")
    if order.size > max_frames:
        order = order[np.linspace(0, order.size - 1, max_frames).round().astype(int)]
    return order


# Difference path (decision record 0002, PROPOSED until the G4a real-data null test confirms them).
# Resampling an undersampled PSF (FWHM ≈ 1.46 native px) changes its shape with sub-pixel phase; with
# one frame per cube bin that leaves flux-proportional residuals at static stars (26σ at peak S/N 90 per
# frame in the native synthetic scene). Bicubic resampling, homogenising every frame to 1.5× the PSF
# FWHM and a small systematic term keep static stars < 3σ from S/N 6 to 370 per frame.
DIFF_ORDER = "bicubic"
DIFF_FWHM_FACTOR = 1.5          # common PSF = 1.5 × the largest frame PSF_FWHM of the pair
DIFF_SYS_FRAC = 0.02            # fractional flux systematic per bin and visit
DIFF_SYS_SHIFT_PX = 0.05        # positional jitter (native px) → (σ_r·|∇F|)²

PHOTMATCH_SNR = 10.0                  # calibration pixels: broadband S/N above this in both visits
PHOTMATCH_MIN_SOURCES = 5             # refuse below this many independent static sources
PHOTMATCH_EXCLUDE_FWHM = 3.0          # mask this many common-PSF FWHM around each target position
PHOTMATCH_SCALE_RANGE = (0.5, 2.0)    # a "gain" outside this is a failed match, not a calibration
PHOTMATCH_TUKEY_C = 4.685             # Tukey biweight tuning constant (95 % Gaussian efficiency)
PHOTMATCH_BOOT = 200                  # source-island bootstrap replicates (global fit; half per bin)
PHOTMATCH_SYS = 0.02                  # fractional per-pixel systematic in the fit weights (≈ DIFF_SYS_FRAC)
PHOTMATCH_SCALE_FLOOR = 0.002         # systematic floor on each scale error (λ-interpolation curvature and PSF
                                      # homogenisation shift the effective gain by ≈ 0.17 % on the L1 chain)
PHOTMATCH_METHOD = ("in-situ relative photometry: Tukey-biweight IRLS, errors in both visits, "
                    "source-island bootstrap, empirical-Bayes shrinkage per λ bin")


def homogenise(gframes: "list[GridFrame]", fwhm_target_arcsec: float, pix_arcsec: float) -> "list[GridFrame]":
    """Convolve every GridFrame to a common Gaussian-equivalent PSF (PSF_FWHM headers)."""
    from dataclasses import replace
    out = []
    for g in gframes:
        f0 = g.psf_fwhm_arcsec if np.isfinite(g.psf_fwhm_arcsec) else fwhm_target_arcsec / DIFF_FWHM_FACTOR
        s, v = psf_match(g.sci, g.var, f0 / pix_arcsec, fwhm_target_arcsec / pix_arcsec)
        out.append(replace(g, sci=s, var=v))
    return out


def build_cube(gframes: "list[GridFrame]", tbin: "TimeBin", band: int, grid: "Grid", rej: A | None = None,
               homog_fwhm_arcsec: float | None = None) -> "Cube":
    """types.Cube for one (time-bin, band) from GridFrames (lam = reprojected CWAVE).
    homog_fwhm_arcsec: convolve the frames to this common PSF first (difference path)."""
    from .types import Cube
    if homog_fwhm_arcsec:
        gframes = homogenise(gframes, homog_fwhm_arcsec, grid.pix_arcsec)
    F = np.array([g.sci for g in gframes])
    V = np.array([g.var for g in gframes])
    L = np.array([g.lam for g in gframes])
    c, cv, cl = spectral_cube(F, V, L, [g.w_frame for g in gframes], band, rej)
    ok = np.isfinite(F) & (V > 0) & (rej is None or ~rej)
    return Cube(bin=tbin, band=band, grid=grid, cube=c, var=cv, lam=cl, nhits=occupancy(np.where(ok, F, np.nan), L, V, band),
                photometric_scales=tuple(sorted({g.photometric_scale for g in gframes})))


def diff_fwhm_arcsec(gframes_a: "Iterable[GridFrame]", gframes_b: "Iterable[GridFrame]") -> float:
    """Common PSF for a difference: 1.5 × the largest PSF_FWHM of either visit (9.0″ → 13.6″ in band 6)."""
    f = [g.psf_fwhm_arcsec for g in list(gframes_a) + list(gframes_b) if np.isfinite(g.psf_fwhm_arcsec)]
    return DIFF_FWHM_FACTOR * (max(f) if f else 1.46 * 6.15)


def diff(cube_a: "Cube", cube_b: "Cube", sky: A, max_interp_ch: float = 2.0, sys_frac: float = DIFF_SYS_FRAC,
         sys_shift_px: float = DIFF_SYS_SHIFT_PX, allow_mixed_scales: bool = False,
         photometric_match: str = "auto", exclude_xy: Sequence[tuple[float, float]] = (),
         exclude_r_px: float = 6.0, n_boot: int = PHOTMATCH_BOOT) -> "Diff":
    """types.Diff: λ-matched A − B with its renormalised significance (workflow.md G4a). Build both cubes
    from GridFrames reprojected with order=DIFF_ORDER and homog_fwhm_arcsec=diff_fwhm_arcsec(...).

    Photometric scales (workflow.md §11.2, decision record 0008). Uncorrected QR2 and QR3 differ by a
    gain (≈ 0.93, validation/F4) that leaves flux-proportional residuals at every static star, and F4 is
    unresolved. A mixed-scale pair is therefore matched in situ (fit_relative_scale on the static sources
    both visits share, outside exclude_r_px of exclude_xy, the target positions) and the match is applied;
    if it cannot be made, the difference is refused. Brightness changes across releases stay
    uninterpretable (photometric_match["cross_release"]); positions and motions are valid.
    photometric_match: "auto" (apply on mixed scales, report as a diagnostic otherwise), "off", or "force"
    (apply always). allow_mixed_scales=True: raw mixed difference, no match — validation runs that
    measure the F4 effect, never for display."""
    from .grid import significance
    from .types import Diff
    if cube_a.band != cube_b.band or cube_a.grid.shape != cube_b.grid.shape:
        raise ValueError("difference needs the same band and grid")
    if photometric_match not in ("auto", "off", "force"):
        raise ValueError(f"photometric_match must be auto, off or force, not {photometric_match!r}")
    sa, sb = tuple(cube_a.photometric_scales), tuple(cube_b.photometric_scales)
    mixed = len(set(sa) | set(sb)) > 1
    must = (mixed and not allow_mixed_scales) or photometric_match == "force"
    if must and photometric_match == "off":
        raise ValueError(f"mixed photometric scales {sa} vs {sb}: F4 is unresolved, so a QR2 − QR3 difference "
                         "needs the in-situ photometric match (photometric_match='auto')")
    b_at = at_wavelengths(cube_a.lam, cube_b.cube, cube_b.var, cube_b.lam, cube_a.band, max_interp_ch=max_interp_ch)
    fit, why = None, ""
    if photometric_match != "off":
        try:
            fit = fit_relative_scale(cube_a.cube, cube_a.var, b_at[0], b_at[1], cube_a.lam, sky, exclude_xy,
                                     exclude_r_px, n_boot=n_boot if must else max(n_boot // 4, 20))
        except ValueError as e:
            if must:
                raise ValueError(f"cannot difference {'/'.join(sa)} against {'/'.join(sb)}: F4 is unresolved and "
                                 f"the in-situ photometric match failed — {e}") from None
            why = str(e)
    apply = must and fit is not None
    arr = fit.pop("arrays") if fit is not None else None
    d, v = matched_difference((cube_a.cube, cube_a.var, cube_a.lam), (cube_b.cube, cube_b.var, cube_b.lam),
                              cube_a.band, sky, max_interp_ch, sys_frac,
                              sys_shift_px * 6.15 / cube_a.grid.pix_arcsec, b_at=b_at,
                              **(dict(scale=arr["scale"], scale_err=arr["err"], offset=arr["offset"],
                                      offset_err=arr["offset_err"]) if apply and arr is not None else {}))
    sig, k = significance(d, v, sky)
    pm = None
    if photometric_match != "off":
        pm = dict(applied=apply, cross_release=mixed, scales_a=list(sa), scales_b=list(sb), method=PHOTMATCH_METHOD,
                  **(fit or {}), note=photometric_note(mixed, apply, fit, sa, sb, why))
    return Diff(a=cube_a.bin.id, b=cube_b.bin.id, band=cube_a.band, d=d, var=v, sig=sig, k=float(k),
                photometric_match=pm)


def photometric_note(mixed: bool, applied: bool, fit: dict[str, Any] | None, sa: Sequence[str], sb: Sequence[str],
                     why: str = "") -> str:
    """One plain sentence for the viewer: what was matched, how well, and what may be read from it."""
    if fit is None:
        return f"No photometric check: {why}" if why else "No photometric check."
    s, e, n = fit["scale"], fit["scale_err"], fit["n_sources"]
    if applied and mixed:
        return (f"{'/'.join(sb).upper()} visit matched to {'/'.join(sa).upper()} in situ on {n} static sources "
                f"(scale {s:.3f} ± {e:.3f}). Positions and motions are valid; brightness changes across releases "
                "are not interpreted until F4 is resolved.")
    if applied:
        return f"Photometric match applied on {n} static sources (scale {s:.3f} ± {e:.3f})."
    z = abs(s - 1) / e if e > 0 else np.inf
    verdict = "consistent with 1" if z < 3 else f"{z:.1f}σ from 1 — check the calibration of these visits"
    return f"Same photometric scale ({'/'.join(sa).upper()}); in-situ check {s:.3f} ± {e:.3f} on {n} sources, {verdict}."


def _gauss(xx: A, yy: A, x: float, y: float, s: float) -> A:
    return np.exp(-((xx - x) ** 2 + (yy - y) ** 2) / (2 * s * s)) / (2 * np.pi * s * s)


def fit_dipole(d: A, var: A, x0: float, y0: float, fwhm_px: float, half: int = 6) -> dict[str, Any] | None:
    """Fit a difference image near (x0, y0) with a dipole (+f at r2, −f at r1, plus a constant) and with
    a monopole (f at r, plus a constant). Gaussian PSF of the given FWHM (grid px; PSF_FWHM / pixel).
    Returns dict(kind, x1, y1, x2, y2, dx, dy, shift_px, flux, chi2_dipole, chi2_monopole) or None."""
    from scipy.optimize import least_squares
    ix, iy = int(round(x0)), int(round(y0))
    ny, nx = d.shape
    if ix - half < 0 or iy - half < 0 or ix + half >= nx or iy + half >= ny:
        return None
    sl = np.s_[iy - half:iy + half + 1, ix - half:ix + half + 1]
    D, Vv = d[sl], var[sl]
    m = np.isfinite(D) & (Vv > 0)
    if m.sum() < 12:
        return None
    yy, xx = np.mgrid[iy - half:iy + half + 1, ix - half:ix + half + 1].astype(float)
    s = fwhm_px / 2.3548
    w = 1 / np.sqrt(np.where(m, Vv, 1.0))
    Dz = np.where(m, D, 0.0)
    jmax, jmin = np.unravel_index(np.argmax(np.where(m, D, -np.inf)), D.shape), \
        np.unravel_index(np.argmin(np.where(m, D, np.inf)), D.shape)
    p_amp = float(np.nanmax(np.abs(D))) * 2 * np.pi * s * s
    lo, hi = [ix - half, iy - half], [ix + half, iy + half]

    def rd(p: A) -> A:
        x1, y1, x2, y2, f, c = p
        return ((Dz - f * (_gauss(xx, yy, x2, y2, s) - _gauss(xx, yy, x1, y1, s)) - c) * w)[m]

    def rm(p: A) -> A:
        x, y, f, c = p
        return ((Dz - f * _gauss(xx, yy, x, y, s) - c) * w)[m]

    p0 = [xx[jmin], yy[jmin], xx[jmax], yy[jmax], p_amp, 0.0]
    rdp = least_squares(rd, p0, bounds=(lo + lo + [0, -np.inf], hi + hi + [np.inf, np.inf]))
    jm = jmax if abs(D[jmax]) >= abs(D[jmin]) else jmin
    rmp = least_squares(rm, [xx[jm], yy[jm], float(np.sign(D[jm])) * p_amp, 0.0],
                        bounds=(lo + [-np.inf, -np.inf], hi + [np.inf, np.inf]))
    x1, y1, x2, y2, f, _ = rdp.x
    cd, cm = float((rdp.fun ** 2).sum()), float((rmp.fun ** 2).sum())
    kind = "dipole" if cm - cd > 25.0 else "monopole"
    return dict(kind=kind, x1=x1, y1=y1, x2=x2, y2=y2, dx=x2 - x1, dy=y2 - y1, shift_px=float(np.hypot(x2 - x1, y2 - y1)),
                flux=float(f if kind == "dipole" else rmp.x[2]), x=float(rmp.x[0]), y=float(rmp.x[1]),
                chi2_dipole=cd, chi2_monopole=cm)


def shift_pa(dx: float, dy: float) -> float:
    """Position angle (deg, east of north) of a shift on the north-up, east-left grid (+x = west)."""
    return float(np.degrees(np.arctan2(-dx, dy)) % 360.0)


def annotate(df: "Diff", positions: Sequence[tuple[float, float]], fwhm_px: float, pix_arcsec: float,
             expected_pa: float | None = None, pa_tol: float = 30.0, min_shift_px: float = 0.3,
             pair: tuple[A, A, A] | None = None, photometry_comparable: bool | None = None) -> list[dict[str, Any]]:
    """Auto-annotations of a types.Diff (implementation.md §4.6). positions: grid (x, y) to examine
    (target from pos(t), detected peaks). A dipole is labelled 'moved ≈X″' when its shift exceeds
    0.3 px and, if a prediction is given, its direction agrees with it within pa_tol degrees.
    pair: (A, B, var) from matched_pair. When given, the shift comes from fit_shift (the data's own PSF,
    valid with masked cores); the Gaussian two-PSF model still decides dipole vs monopole.
    photometry_comparable: False labels monopoles as residuals, not brightened/faded (a cross-release pair
    before F4, workflow.md §11.2); None takes it from df.photometric_match."""
    if photometry_comparable is None:
        photometry_comparable = not (df.photometric_match or {}).get("cross_release", False)
    out = []
    for x, y in positions:
        r = fit_dipole(df.d, df.var / df.k ** 2, x, y, fwhm_px)
        if r is None:
            continue
        if pair is not None and r["kind"] == "dipole":
            t = fit_shift(*pair, x, y)
            if t is not None:
                mx, my = (r["x1"] + r["x2"]) / 2, (r["y1"] + r["y2"]) / 2     # the drawn arrow follows the template shift
                r.update(dx=t["dx"], dy=t["dy"], shift_px=t["shift_px"], shift_method="template", template=t,
                         x1=mx - t["dx"] / 2, y1=my - t["dy"] / 2, x2=mx + t["dx"] / 2, y2=my + t["dy"] / 2)
        if r["kind"] == "dipole":
            pa = shift_pa(r["dx"], r["dy"])
            r["pa_deg"] = pa
            agree = expected_pa is None or abs((pa - expected_pa + 180) % 360 - 180) <= pa_tol
            if r["shift_px"] > min_shift_px and agree:
                r["label"] = f"moved ≈{r['shift_px'] * pix_arcsec:.1f}″"
            else:
                r["label"] = "dipole (not consistent with the predicted motion)"
        else:
            r["comparable"] = photometry_comparable
            r["label"] = (("brightened" if r["flux"] > 0 else "faded") if photometry_comparable else
                          "residual (brightness not comparable across releases before F4)")
        out.append(r)
    df.annotations = out
    return out


def psf_match(img: A, var: A, fwhm_from_px: float, fwhm_to_px: float) -> tuple[A, A]:
    """Convolve the sharper image to a broader PSF (Gaussian kernel, σ² = σ_to² − σ_from²; FWHMs from
    the PSF_FWHM headers). Only for PA 0°/180° pairs whose asymmetric PSFs leave rotated residuals."""
    from scipy.ndimage import gaussian_filter
    if fwhm_to_px <= fwhm_from_px:
        return img, var
    s = np.sqrt(fwhm_to_px ** 2 - fwhm_from_px ** 2) / 2.3548
    z = np.isfinite(img)
    num = gaussian_filter(np.where(z, img, 0.0), s)
    den = gaussian_filter(z.astype(float), s)
    vv = gaussian_filter(np.where(z, var, 0.0), s / np.sqrt(2)) / (4 * np.pi * s * s)
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.where(den > 0.5, num / den, np.nan), np.where(den > 0.5, vv / den, np.nan)


def scrubber(cubes: "Iterable[Cube]") -> tuple[A, A, A]:
    """λ-scrubber product (P2-2, G5.flip): every cube plane of the given bands, sorted by the median
    wavelength it actually sampled. Returns (planes (N, ny, nx), lam (N,), band (N,)). Labelled as
    spectral, never temporal."""
    planes, lam, band = [], [], []
    for c in cubes:
        for k in range(len(c.cube)):
            lk = c.lam[k][np.isfinite(c.lam[k])]
            if lk.size:
                planes.append(c.cube[k])
                lam.append(float(np.median(lk)))
                band.append(c.band)
    o = np.argsort(lam, kind="stable")
    return np.array(planes)[o], np.array(lam)[o], np.array(band)[o]


SPECTRAL_LABEL = "spectral sequence (sorted by wavelength), not a time sequence"

# implementation.md §7 RGB presets: (R, G, B) wavelength ranges in µm, or detector bands.
RGB_PRESETS = {
    "methane": ((4.0, 4.2), (3.55, 3.65), (3.25, 3.40)),   # T/Y dwarfs glow red
    "ice": ((2.55, 2.65), (3.0, 3.1), (3.55, 3.65)),       # ice band in G: ice-rich sightlines go magenta
    "thermal": (4, 5, 6),
}


def lambda_slice(cubes: "Iterable[Cube]", lam_lo: float, lam_hi: float) -> tuple[A, A]:
    """Inverse-variance mean of every cube bin whose per-pixel measured λ lies in [lam_lo, lam_hi].
    Returns (img, var); NaN where no bin sampled the range at that pixel."""
    cubes = list(cubes)
    num = np.zeros(cubes[0].cube.shape[1:])
    den = np.zeros_like(num)
    for c in cubes:
        with np.errstate(invalid="ignore", divide="ignore"):
            inr = (c.lam >= lam_lo) & (c.lam <= lam_hi) & np.isfinite(c.cube) & (c.var > 0)
            w = np.where(inr, 1.0 / np.where(c.var > 0, c.var, 1.0), 0.0)
        num = num + (w * np.where(inr, c.cube, 0.0)).sum(0)
        den = den + w.sum(0)
    with np.errstate(invalid="ignore", divide="ignore"):
        return num / den, 1.0 / den


def null_halves(lam_at_target: ArrayLike) -> tuple[A, A]:
    """Split one visit's frames into two disjoint halves for the G4a null test: alternate in order of
    the wavelength each frame sampled at the target, so both halves span the band (every other channel)."""
    o = np.argsort(np.asarray(lam_at_target, float), kind="stable")
    return np.sort(o[0::2]), np.sort(o[1::2])


def matched_pair(cube_a: "Cube", cube_b: "Cube", max_interp_ch: float = 2.0) -> tuple[A, A, A]:
    """λ-matched broadband pair: A summed over its bins, and B interpolated to A's wavelengths and summed
    over the same bins (only bins finite in both). Returns (A, B, var_A + var_B)."""
    fb, vb = at_wavelengths(cube_a.lam, cube_b.cube, cube_b.var, cube_b.lam, cube_a.band,
                            max_interp_ch=max_interp_ch)
    ok = np.isfinite(cube_a.cube) & np.isfinite(fb)
    n = ok.sum(0)
    with np.errstate(invalid="ignore", divide="ignore"):
        Aa = np.where(ok, cube_a.cube, 0).sum(0) / n
        Bm = np.where(ok, fb, 0).sum(0) / n
        V = (np.where(ok, cube_a.var, 0).sum(0) + np.where(ok, vb, 0).sum(0)) / n ** 2
    return np.where(n > 0, Aa, np.nan), np.where(n > 0, Bm, np.nan), np.where(n > 0, V, np.nan)


def fit_shift(a: A, b: A, var: A, x0: float, y0: float, half: int = 8,
              max_shift: float = 4.0) -> dict[str, Any] | None:
    """Shift (dx, dy) in grid px that moves image b onto image a near (x0, y0): least squares of
    a ≈ s·b(x − dx, y − dy) + c on pixels finite in both. Uses the data's own PSF, so it works on bright
    targets whose cores are masked (Barnard: TRANSIENT+SUR_ERROR early events), where a Gaussian dipole
    fit only sees non-Gaussian wings. Returns dict(dx, dy, shift_px, scale, chi2r) or None."""
    from scipy.ndimage import shift as nd_shift
    from scipy.optimize import least_squares
    ix, iy = int(round(x0)), int(round(y0))
    ny, nx = a.shape
    pad = int(np.ceil(max_shift)) + 2
    if ix - half - pad < 0 or iy - half - pad < 0 or ix + half + pad >= nx or iy + half + pad >= ny:
        return None
    big = np.s_[iy - half - pad:iy + half + pad + 1, ix - half - pad:ix + half + pad + 1]
    B = b[big]
    hole = ~np.isfinite(B)
    Bz = np.where(hole, 0.0, B)
    inner = np.s_[pad:-pad, pad:-pad]
    Ab, V = a[big][inner], var[big][inner]

    def model(p: A) -> A:
        dx, dy, s, c = p
        sh = nd_shift(Bz, (dy, dx), order=3, mode="nearest")
        hz = nd_shift(hole.astype(float), (dy, dx), order=1, mode="nearest") > 0.01
        return np.where(hz, np.nan, s * sh + c)[inner]

    def res(p: A) -> A:
        m = model(p)
        ok = np.isfinite(m) & np.isfinite(Ab) & (V > 0)
        r = np.zeros(Ab.shape)
        r[ok] = (Ab[ok] - m[ok]) / np.sqrt(V[ok])
        return r.ravel()

    best = None
    for dx0, dy0 in [(0, 0), (1, 0), (-1, 0), (0, 1), (0, -1)]:
        r = least_squares(res, [dx0, dy0, 1.0, 0.0], bounds=([-max_shift, -max_shift, 0.2, -np.inf],
                                                              [max_shift, max_shift, 5.0, np.inf]))
        if best is None or r.cost < best.cost:
            best = r
    assert best is not None
    dx, dy, s, _ = best.x
    nfit = int((best.fun != 0).sum())
    return dict(dx=float(dx), dy=float(dy), shift_px=float(np.hypot(dx, dy)), scale=float(s),
                chi2r=float(2 * best.cost / max(nfit - 4, 1)), npix=nfit)


# ------------------------------------------------------------------ cross-release photometric matching
# F4 is inconclusive (validation/F4/2026-11-08-d6d2e45): l3_flux_corrections, multiplied or divided,
# does not bring QR2 onto QR3. A QR2 − QR3 difference therefore matches the two visits *in situ*, as
# image-subtraction codes do (Alard & Lupton 1998; HOTPANTS, Becker 2015; ZOGY, Zackay et al. 2016): fit
# B onto A on the static sources both visits share. Decision record 0008. Constants: PHOTMATCH_* above.


def _robust_sigma(r: A) -> float:
    r = r[np.isfinite(r)]
    if r.size < 3:
        return 1.0
    return float(max(1.4826 * np.median(np.abs(r - np.median(r))), 1e-12))


def _irls_scale(a: A, va: A, b: A, vb: A, w0: A, s0: float, c0: float, fref: A | None = None,
                n_iter: int = 40, sys_frac: float = PHOTMATCH_SYS) -> tuple[float, float]:
    """a ≈ s·b + c with errors in both a and b: York et al. (2004, Am. J. Phys. 72, 367) regression —
    unbiased under noise in b, unlike an ordinary weighted slope, which is diluted by var(b) — made robust
    by a Tukey biweight on the residual r = (a − s·b − c)/√(va + s²·vb + 2·sys²·fref²). The residual scale
    is re-estimated (MAD) every pass, so underestimated variances (correlated, resampled noise) do not turn
    every pixel into an outlier. fref: a noise-suppressed flux for the systematic term (weights computed
    from the noisy pixel itself would correlate with its noise and bias s low). w0: prior weights
    (bootstrap multiplicities; 0 drops a pixel)."""
    s, c = s0, c0
    use = w0 > 0
    va_e = va + 2 * sys_frac ** 2 * (np.zeros_like(a) if fref is None else fref * fref)
    for _ in range(n_iter):
        W = 1.0 / (va_e + s * s * vb)
        r = (a - s * b - c) * np.sqrt(W)
        u = r / (PHOTMATCH_TUKEY_C * _robust_sigma(r[use]))
        Wt = w0 * np.where(np.abs(u) < 1, (1 - u * u) ** 2, 0.0) * W
        sw = Wt.sum()
        if not sw > 0 or (Wt > 0).sum() < 3:
            return np.nan, np.nan
        mb, ma = (Wt * b).sum() / sw, (Wt * a).sum() / sw
        U, V = b - mb, a - ma
        beta = W * (U * va_e + s * V * vb)
        den = (Wt * beta * U).sum()
        if not den != 0:
            return np.nan, np.nan
        s_new = float((Wt * beta * V).sum() / den)
        c_new = float(ma - s_new * mb)
        conv = abs(s_new - s) < 1e-7 * max(abs(s), 1.0) and abs(c_new - c) < 1e-7 * float(np.sqrt(np.median(va_e)))
        s, c = s_new, c_new
        if not np.isfinite(s):
            return np.nan, np.nan
        if conv:
            break
    return s, c


def _broadband(a: A, va: A, b: A, vb: A) -> tuple[A, A, A, A, A]:
    """Mean over the λ bins finite in *both* cubes (so neither side sees a bin the other lacks)."""
    ok = np.isfinite(a) & np.isfinite(b) & (va > 0) & (vb > 0)
    n = ok.sum(0)
    with np.errstate(invalid="ignore", divide="ignore"):
        out = [np.where(ok, x, 0).sum(0) / n for x in (a, b)] + [np.where(ok, x, 0).sum(0) / n ** 2 for x in (va, vb)]
    return out[0], out[2], out[1], out[3], n


def static_islands(a: A, va: A, b: A, vb: A, sky: A, exclude_xy: Sequence[tuple[float, float]] = (),
                   exclude_r_px: float = 6.0, snr_min: float = PHOTMATCH_SNR, min_pix: int = 3) -> tuple[A, int]:
    """Calibration pixels for the photometric match, labelled by source island (0 = not used).
    A pixel qualifies when its broadband S/N exceeds snr_min in *both* visits, it is not a sky pixel, and it
    lies outside exclude_r_px of every target position (a mover's pixels say nothing about the gain). Islands
    are 8-connected components of ≥ min_pix pixels (drops cosmic-ray and hot-pixel singletons): one per
    source, the independent unit of the bootstrap, since the pixels of one PSF are correlated."""
    from scipy.ndimage import label
    A_, VA, B_, VB, n = _broadband(a, va, b, vb)
    with np.errstate(invalid="ignore", divide="ignore"):
        good = (n >= max(2, len(a) // 4)) & (A_ / np.sqrt(VA) > snr_min) & (B_ / np.sqrt(VB) > snr_min) & ~sky
    ny, nx = good.shape
    yy, xx = np.mgrid[:ny, :nx]
    for x, y in exclude_xy:
        if np.isfinite(x) and np.isfinite(y):
            good &= (xx - x) ** 2 + (yy - y) ** 2 > exclude_r_px ** 2
    lab, nlab = label(good, structure=np.ones((3, 3)))
    if not nlab:
        return lab, 0
    sizes = np.bincount(lab.ravel(), minlength=nlab + 1)
    keep = np.nonzero(sizes >= min_pix)[0]
    keep = keep[keep > 0]
    remap = np.zeros(nlab + 1, int)
    remap[keep] = np.arange(1, len(keep) + 1)
    return remap[lab], int(len(keep))


def fit_relative_scale(a: A, va: A, b: A, vb: A, lam: A, sky: A,
                       exclude_xy: Sequence[tuple[float, float]] = (), exclude_r_px: float = 6.0,
                       snr_min: float = PHOTMATCH_SNR, min_sources: int = PHOTMATCH_MIN_SOURCES,
                       n_boot: int = PHOTMATCH_BOOT, seed: int = 0,
                       scale_floor: float = PHOTMATCH_SCALE_FLOOR) -> dict[str, Any]:
    """Relative photometric scale of visit B onto visit A per wavelength bin: a_k ≈ s_k·b_k + c_k.

    a, va, b, vb: (nb, ny, nx), B already evaluated at A's wavelengths (at_wavelengths), both on the common
    PSF. lam: A's cube_lam (µm). sky: sky mask (anchors the offsets c_k; never resampled).

    What each step guards against:
      * the moving target — masked within exclude_r_px of every position given;
      * variable stars, cosmic rays, PSF-mismatch cores — Tukey-biweight IRLS started from the median of
        per-source flux ratios (breakdown ≈ 50 % of sources), residual scale re-estimated by MAD;
      * flux-proportional systematics — 2·sys²·fref² in the weights (fref a 3×3-smoothed flux, so the
        weights do not correlate with the noise), so bright cores do not dominate;
      * noise in both visits — York (2004) errors-in-variables regression, not a diluted weighted slope;
      * correlated pixels — 1σ errors from a bootstrap over source islands (block bootstrap), not from
        the formal covariance, which would count each PSF's pixels as independent; PHOTMATCH_SCALE_FLOOR is
        added in quadrature for what the bootstrap cannot see (interpolation and homogenisation systematics);
      * noisy single bins — each s_k is shrunk toward the broadband scale with the empirical-Bayes weight
        σ_k²/(σ_k² + τ²), τ² the DerSimonian–Laird between-bin variance; a bin with too little data is
        pooled to the broadband scale and flagged.
    Raises ValueError when fewer than min_sources static sources qualify or the broadband scale is
    unphysical. Deterministic for a given seed."""
    nb = len(a)
    lab, nsrc = static_islands(a, va, b, vb, sky, exclude_xy, exclude_r_px, snr_min)
    if nsrc < min_sources:
        raise ValueError(f"cross-release photometric match needs ≥ {min_sources} static sources with S/N > "
                         f"{snr_min:g} in both visits; found {nsrc} (field too sparse or the visits barely overlap)")
    cal = lab > 0
    rng = np.random.default_rng(seed)
    ys, xs = np.nonzero(sky & ~cal)
    cap = min(2 * int(cal.sum()), 5000)
    if ys.size > cap:                                              # sky anchors c; it must not swamp s
        pick = np.sort(rng.choice(ys.size, cap, replace=False))
        ys, xs = ys[pick], xs[pick]
    cy, cx = np.nonzero(cal)
    PY, PX_ = np.r_[cy, ys], np.r_[cx, xs]
    blk = np.r_[lab[cy, cx] - 1, np.full(ys.size, -1)]            # island index; −1 = sky

    def fit(fa: A, fva: A, fb: A, fvb: A, fr: A, nboot: int) -> dict[str, Any]:
        fin = np.isfinite(fa) & np.isfinite(fb) & (fva > 0) & (fvb > 0)
        fa, fva, fb, fvb, fr, bk = fa[fin], fva[fin], fb[fin], fvb[fin], fr[fin], blk[fin]
        src = bk >= 0
        ns = int(len(np.unique(bk[src])))
        res: dict[str, Any] = dict(s=np.nan, c=np.nan, es=np.nan, ec=np.nan, n_pix=int(src.sum()), n_sources=ns,
                                   z_before=np.nan, z_after=np.nan, rsig=np.nan)
        if ns < 3 or src.sum() < 10:
            return res
        num = np.bincount(bk[src], fa[src], minlength=nsrc)
        den = np.bincount(bk[src], fb[src], minlength=nsrc)
        with np.errstate(invalid="ignore", divide="ignore"):
            rr = num / den
        rr = rr[np.isfinite(rr) & (den > 0) & (rr > 0)]
        s0 = float(np.median(rr)) if rr.size else 1.0
        c0 = float(np.median(fa[~src] - s0 * fb[~src])) if (~src).any() else 0.0
        s, c = _irls_scale(fa, fva, fb, fvb, np.ones(fa.size), s0, c0, fr)
        if not np.isfinite(s):
            return res
        bs, bc = [], []
        for _ in range(nboot):
            mult = np.bincount(rng.integers(0, nsrc, nsrc), minlength=nsrc).astype(float)
            w0 = np.where(src, mult[np.clip(bk, 0, None)], 1.0)
            sb_, cb_ = _irls_scale(fa, fva, fb, fvb, w0, s, c, fr, n_iter=20)
            if np.isfinite(sb_):
                bs.append(sb_)
                bc.append(cb_)

        def zmed(ss: float, cc: float) -> float:                  # median |island-integrated residual| in σ
            ev = fva + ss * ss * fvb
            r = np.bincount(bk[src], (fa - ss * fb - cc)[src], minlength=nsrc)
            e = np.bincount(bk[src], ev[src], minlength=nsrc)
            with np.errstate(invalid="ignore", divide="ignore"):
                z = np.abs(r / np.sqrt(e))
            z = z[np.isfinite(z) & (e > 0)]
            return float(np.median(z)) if z.size else np.nan

        ev = fva + s * s * fvb + 2 * PHOTMATCH_SYS ** 2 * fr * fr
        res.update(s=s, c=c, rsig=_robust_sigma(((fa - s * fb - c) / np.sqrt(ev))[src]),
                   z_before=zmed(1.0, 0.0), z_after=zmed(s, c))
        if len(bs) >= max(10, nboot // 4):
            q, qc = np.percentile(bs, [15.865, 84.135]), np.percentile(bc, [15.865, 84.135])
            res.update(es=float(max(np.hypot((q[1] - q[0]) / 2, scale_floor), 1e-6)), ec=float((qc[1] - qc[0]) / 2))
        return res

    from scipy.ndimage import uniform_filter

    def ref(x: A, y: A) -> A:                                      # 3×3-smoothed mean flux, for weights only
        return uniform_filter(np.nan_to_num((x + y) / 2), 3)[PY, PX_]

    A_, VA, B_, VB, _ = _broadband(a, va, b, vb)
    g = fit(A_[PY, PX_], VA[PY, PX_], B_[PY, PX_], VB[PY, PX_], ref(A_, B_), n_boot)
    S, eS, C = g["s"], g["es"], g["c"]
    lo, hi = PHOTMATCH_SCALE_RANGE
    if not (np.isfinite(S) and np.isfinite(eS) and lo < S < hi):
        raise ValueError(f"cross-release photometric match failed: broadband scale {S:.3g} ± {eS:.2g} is not a "
                         f"plausible gain ({lo}–{hi}); the visits do not share enough static flux")
    per = [fit(a[k][PY, PX_], va[k][PY, PX_], b[k][PY, PX_], vb[k][PY, PX_], ref(a[k], b[k]), max(n_boot // 2, 20))
           for k in range(nb)]
    sk = np.array([p["s"] for p in per])
    ek = np.array([p["es"] for p in per])
    with np.errstate(invalid="ignore"):
        ok = np.isfinite(sk) & np.isfinite(ek) & (sk > lo) & (sk < hi)
    tau2, Q = 0.0, 0.0
    if ok.sum() >= 2:                                              # DerSimonian–Laird between-bin variance
        w = 1 / ek[ok] ** 2
        mu = float((w * sk[ok]).sum() / w.sum())
        Q = float((w * (sk[ok] - mu) ** 2).sum())
        tau2 = max(0.0, (Q - (ok.sum() - 1)) / float(w.sum() - (w ** 2).sum() / w.sum()))
    scale, err = np.full(nb, S), np.full(nb, eS)
    offset, shrink = np.full(nb, C), np.ones(nb)
    for k in np.nonzero(ok)[0]:
        bk_ = ek[k] ** 2 / (ek[k] ** 2 + tau2) if tau2 > 0 else 1.0   # 1 → fully pooled to S
        scale[k] = bk_ * S + (1 - bk_) * sk[k]
        err[k] = float(np.sqrt((1 - bk_) * ek[k] ** 2 + bk_ ** 2 * eS ** 2))
        if np.isfinite(per[k]["c"]):
            offset[k] = per[k]["c"]
        shrink[k] = bk_
    oerr = np.array([p["ec"] if np.isfinite(p["ec"]) else g["ec"] for p in per])
    lam_k = [np.nanmedian(lam[k][cal]) if np.isfinite(lam[k][cal]).any() else np.nan for k in range(nb)]

    def fl(x: Any) -> float | None:
        return float(x) if x is not None and np.isfinite(x) else None

    bins = [dict(lam=fl(lam_k[k]), scale=float(scale[k]), err=float(err[k]), raw=fl(sk[k]), raw_err=fl(ek[k]),
                 shrink=float(shrink[k]), offset=float(offset[k]), n_pix=int(per[k]["n_pix"]),
                 n_sources=int(per[k]["n_sources"]), pooled=bool(not ok[k])) for k in range(nb)]
    return dict(scale=float(S), scale_err=float(eS), offset=float(C), offset_err=fl(g["ec"]),
                n_sources=int(nsrc), n_pix=int(g["n_pix"]), residual_scale=fl(g["rsig"]), tau=float(np.sqrt(tau2)),
                q_flat=float(Q), dof_flat=max(int(ok.sum()) - 1, 0), static_z_before=fl(g["z_before"]),
                static_z_after=fl(g["z_after"]), bins=bins,
                arrays=dict(scale=scale, err=err, offset=offset, offset_err=np.nan_to_num(oerr), calib=cal))
