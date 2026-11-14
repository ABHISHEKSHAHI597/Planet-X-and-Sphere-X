"""Native forced photometry, blend covariance, spectra and indices (impl. §4.8)."""

from __future__ import annotations

from typing import Any

import numpy as np

from .epsf import EPSF, fit_blend, fit_native
from .types import CalFrame

SR_PER_ARCSEC2 = (np.pi / 648000.0) ** 2


def scale_template(wavelength: Any, flux: Any, errors: Any, template_wave: Any, template_flux: Any) -> dict[str, Any]:
    """Least-squares signed scale on common coverage; never extrapolate a library template."""
    wave, f, e, tl, tf = map(lambda v: np.asarray(v, float), (wavelength, flux, errors, template_wave, template_flux))
    if np.any(np.diff(tl) <= 0):
        raise ValueError("template wavelengths must increase")
    ok = np.isfinite(wave) & np.isfinite(f) & np.isfinite(e) & (e > 0) & (wave >= tl[0]) & (wave <= tl[-1])
    if ok.sum() < 3:
        raise ValueError("at least three common template samples required")
    model = np.interp(wave[ok], tl, tf)
    w = 1 / e[ok] ** 2
    normal = float(w @ (model * model))
    if normal <= 0:
        raise ValueError("template has no support")
    scale = float(w @ (f[ok] * model) / normal)
    chi = float(np.sum(w * (f[ok] - scale * model) ** 2))
    dof = int(ok.sum() - 1)
    return dict(scale=scale, error=float(np.sqrt(max(1.0, chi / dof) / normal)), chi2=chi, dof=dof, used=ok)


def to_uJy(f_pix_sum_mjysr: Any, omega_arcsec2: Any) -> Any:
    return f_pix_sum_mjysr * np.asarray(omega_arcsec2) * SR_PER_ARCSEC2 * 1e12


def ab_mag(uJy: Any) -> Any:
    f = np.asarray(uJy, float)
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where(f > 0, 23.9 - 2.5 * np.log10(f), np.nan)


def wise_colour(points: list[dict[str, Any]]) -> float:
    """Approximate Vega W1-W2 using official photon RSRs; W2 >5um is absent.

    RSR integrated in dln(lambda), as appropriate for photon counting and Fnu.
    AB-to-Vega offsets 2.699/3.339: WISE All-Sky Supplement IV.4.h Table 3.
    """
    from pathlib import Path

    require_common_scale(points)
    rows = [p for p in points if not p.get("contaminated", False)]
    wave = np.array([p["lam"] for p in rows])
    f = np.array([p["flux_uJy"] for p in rows])
    errors = np.array([p.get("stat_err_uJy", p["err_uJy"]) for p in rows])
    order = np.argsort(wave)
    wave, f, errors = wave[order], f[order], errors[order]
    unique, inverse = np.unique(wave, return_inverse=True)
    weights = 1 / errors**2
    f = np.bincount(inverse, weights=weights * f) / np.bincount(inverse, weights=weights)
    wave = unique
    if len(wave) < 20 or wave[0] > 2.8 or wave[-1] < 4.95:
        raise ValueError("insufficient W1/W2 spectral coverage")
    flux = []
    for band in ["W1", "W2"]:
        table = np.loadtxt(Path(__file__).parent / "data" / f"wise_{band}.txt")
        flux.append(synthetic_wise(wave, f, table[:, 0], table[:, 1]))
    if min(flux) <= 0:
        raise ValueError("positive integrated flux required for colour")
    return float(-2.5 * np.log10(flux[0] / flux[1]) + 0.640)


def spectrum_point(
    frame: CalFrame, epsf: Any, ra: float, dec: float, omega_arcsec2: float, neighbours: Any = ()
) -> dict[str, Any] | None:
    """A signed flux and total error; forced positions and wavelength are native.

    Neighbours are sky coordinates, jointly fitted, never subtracted without uncertainty.
    The 3% floor is carried separately and must not average down as independent noise.
    """
    if not frame.qa["ok"]:
        return None
    x, y = map(float, frame.wcs.world_to_pixel_values(ra, dec))
    ix, iy = int(round(x)), int(round(y))
    if not (0 <= ix < frame.sci.shape[1] and 0 <= iy < frame.sci.shape[0]):
        return None
    lam, dlam = frame.lam[iy, ix], frame.dlam[iy, ix]
    if not (np.isfinite(lam) and np.isfinite(dlam) and lam > 0 and dlam > 0 and omega_arcsec2 > 0):
        return None
    psf: EPSF = epsf[frame.detector] if isinstance(epsf, dict) else epsf
    zone = psf.zone(frame.origin[0] + x, frame.origin[1] + y)
    if len(neighbours):
        positions = [(x, y)] + [tuple(map(float, frame.wcs.world_to_pixel_values(*p))) for p in neighbours]
        zones = [psf.zone(frame.origin[0] + a, frame.origin[1] + b) for a, b in positions]
        r = fit_blend(frame.sci, frame.var, frame.bad_phot, psf, positions, zones, shared_shift=True)
        if r is None:
            return None
        f, ef, chi = r.params[2], r.errors[2], r.rchi2
        wing = bool(frame.bad_phot[max(0, iy - 1) : iy + 2, max(0, ix - 1) : ix + 2].any())
    else:
        fit = fit_native(frame.sci, frame.var, frame.bad_phot, psf, zone, x, y, fixed_xy=True)
        if fit is None:
            return None
        f, ef, chi, wing = fit.params[0], fit.errors[0], fit.rchi2, fit.wing_fit
    F, eF = map(float, (to_uJy(f, omega_arcsec2), to_uJy(ef, omega_arcsec2)))
    flags = frame.flags_near(x, y)
    contamination = set(flags) - {"SOURCE", "FULLSAMPLE", "OUTLIER", "STREAK"}
    return dict(
        lam=float(lam),
        dlam=float(dlam),
        flux_uJy=F,
        err_uJy=float(np.hypot(eF, 0.03 * abs(F))),
        stat_err_uJy=eF,
        cal_err_uJy=0.03 * abs(F),
        mjd=frame.mjd,
        detector=frame.detector,
        obsid=frame.obsid,
        rchi2=float(chi),
        flags_near=flags,
        wing_fit=wing,
        contaminated=bool(contamination) or abs(lam - 1.083) <= max(dlam / 2, 0.01),
        photometric_scale=frame.photometric_scale,
        blend_fit=bool(len(neighbours)),
        blend_registration="joint shared translation" if len(neighbours) else None,
        omega_arcsec2=omega_arcsec2,
        zone=zone,
    )


def require_common_scale(points: list[dict[str, Any]]) -> None:
    if len({p["photometric_scale"] for p in points}) > 1:
        raise ValueError("F4 unresolved: cross-release photometric aggregation prohibited")


def methane_index(points: list[dict[str, Any]], field_ratios: Any) -> dict[str, Any]:
    require_common_scale(points)

    def band(lo: float, hi: float) -> tuple[float, float]:
        rows = [p for p in points if lo <= p["lam"] <= hi and not p.get("contaminated", False)]
        if not rows:
            raise ValueError("index wavelength coverage missing")
        f = np.array([p["flux_uJy"] for p in rows])
        e = np.array([p.get("stat_err_uJy", p["err_uJy"]) for p in rows])
        w = 1 / e**2
        return float(w @ f / w.sum()), float(np.hypot(1 / np.sqrt(w.sum()), 0.03 * abs(w @ f / w.sum())))

    a, ea = band(3.25, 3.40)
    b, eb = band(3.95, 4.20)
    field = np.asarray(field_ratios, float)
    field = field[np.isfinite(field) & (field > 0)]
    if not field.size or b <= 3 * eb:
        raise ValueError("field calibration and a significant denominator required")
    med = float(np.median(field))
    emed = 1.2533 * 1.4826 * float(np.median(abs(field - med))) / np.sqrt(len(field))
    ratio = a / b / med
    err = np.sqrt((ea / b / med) ** 2 + (a * eb / b**2 / med) ** 2 + (a * emed / b / med**2) ** 2)
    return dict(methane_rel=ratio, error=float(err), field_median=med, n_field=len(field))


def synthetic_wise(lam: Any, flux: Any, response_lam: Any, response: Any) -> float:
    """Response-weighted Fnu, no extrapolation over missing wavelength coverage.

    Caller provides a documented photon response converted to dln(lambda) weights.
    SPHEREx W2 truncation must be labelled approximate.
    """
    wavelength, f, r, w = map(lambda x: np.asarray(x, float), (lam, flux, response_lam, response))
    order = np.argsort(wavelength)
    wavelength, f = wavelength[order], f[order]
    if len(wavelength) < 2 or np.any(np.diff(wavelength) <= 0) or np.any(w < 0) or not np.all(np.isfinite(f)):
        raise ValueError("finite increasing spectral sampling and nonnegative response required")
    keep = (r >= wavelength[0]) & (r <= wavelength[-1]) & (w > 0)
    if keep.sum() < 2:
        raise ValueError("no response coverage")
    return float(
        np.trapezoid(np.interp(r[keep], wavelength, f) * w[keep], np.log(r[keep]))
        / np.trapezoid(w[keep], np.log(r[keep]))
    )
