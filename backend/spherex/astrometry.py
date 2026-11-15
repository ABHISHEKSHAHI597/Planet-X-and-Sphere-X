"""Native-frame astrometry and conditioned GLS motion fits (impl. §4.7).

Offsets and parallax are arcseconds; time is Julian years. No image resampling.
"""

from __future__ import annotations

from typing import Any

import numpy as np
from astropy.coordinates import get_body_barycentric
from astropy.time import Time

AU_KM = 149597870.7


def visit_centroid(points: list[dict[str, Any]]) -> dict[str, Any]:
    """GLS constant visit position; retain xy covariance and excess scatter.

    This does not estimate inter-frame correlated systematics or model the
    source's within-visit motion. The contributing epochs remain explicit.
    """
    if not points:
        raise ValueError("visit has no native positions")
    values = np.array([[p["xi"], p["eta"]] for p in points], float)
    covariances = np.array(
        [[[p["s_xi"] ** 2, p.get("cov_xi_eta", 0)], [p.get("cov_xi_eta", 0), p["s_eta"] ** 2]] for p in points]
    )
    if not np.all(np.isfinite(covariances)) or not np.all(np.isfinite(values)):
        raise ValueError("finite visit positions/covariance required")
    for covariance in covariances:
        np.linalg.cholesky(covariance)
    precision = np.linalg.inv(covariances)
    covariance = np.linalg.inv(precision.sum(axis=0))
    mean = covariance @ np.einsum("nij,nj->i", precision, values)
    residual = values - mean
    chi2 = float(np.einsum("ni,nij,nj", residual, precision, residual))
    dof = 2 * len(points) - 2
    if dof:
        covariance *= max(1.0, chi2 / dof)
    return dict(
        mean=mean,
        covariance=covariance,
        chi2=chi2,
        dof=dof,
        n=len(points),
        mjd=float(np.mean([p["mjd"] for p in points])),
    )


def sky_covariance(wcs: Any, x: float, y: float, covariance_px: Any) -> Any:
    """Local WCS Jacobian into (RA*cosDec,Dec), including detector rotation and SIP."""
    import astropy.units as u
    from astropy.coordinates import SkyCoord

    ra, dec = wcs.pixel_to_world_values(x, y)
    origin = SkyCoord(ra * u.deg, dec * u.deg)
    jac = np.empty((2, 2))
    for col, (dx, dy) in enumerate(((1e-3, 0), (0, 1e-3))):
        a, d = wcs.pixel_to_world_values(x + dx, y + dy)
        da, dd = origin.spherical_offsets_to(SkyCoord(a * u.deg, d * u.deg))
        jac[:, col] = [da.arcsec / 1e-3, dd.arcsec / 1e-3]
    return jac @ np.asarray(covariance_px) @ jac.T


def isolated(ra: Any, dec: Any, min_sep_arcsec: float = 18.0) -> Any:
    """Nearest other catalogue member, vectorized; no quadratic SkyCoord loop."""
    import astropy.units as u
    from astropy.coordinates import SkyCoord

    if len(ra) < 2:
        return np.ones(len(ra), bool)
    coords = SkyCoord(np.asarray(ra) * u.deg, np.asarray(dec) * u.deg)
    _, sep, _ = coords.match_to_catalog_sky(coords, nthneighbor=2)
    return sep.arcsec >= min_sep_arcsec


def parallax_factors(mjd: Any, ra_deg: Any, dec_deg: Any, sc_geo_km: Any = None) -> tuple[Any, Any]:
    """ICRS observer barycentric position; spacecraft offsets must be ICRS km.

    An unverified header coordinate frame must never be passed as sc_geo_km.
    Earth-only factors are adequate for stellar parallax, not nearby SSO work.
    """
    xyz = get_body_barycentric("earth", Time(mjd, format="mjd", scale="utc")).xyz.to_value("au")
    if sc_geo_km is not None:
        sc = np.asarray(sc_geo_km, float)
        if sc.shape[0] != 3 or not np.all(np.isfinite(sc)):
            raise ValueError("observer position must be finite (3, ...) ICRS kilometres")
        xyz = xyz + sc / AU_KM
    x, y, z = xyz
    a, d = np.radians(ra_deg), np.radians(dec_deg)
    return (x * np.sin(a) - y * np.cos(a), x * np.cos(a) * np.sin(d) + y * np.sin(a) * np.sin(d) - z * np.cos(d))


def gls(design: Any, values: Any, covariance: Any, allow_exact: bool = False) -> tuple[Any, Any, float, int]:
    """Whiten then SVD; reject deficient designs instead of returning false precision."""
    a, b, c = np.asarray(design, float), np.asarray(values, float), np.asarray(covariance, float)
    if (
        not all(np.all(np.isfinite(v)) for v in (a, b, c))
        or len(b) < a.shape[1]
        or (len(b) == a.shape[1] and not allow_exact)
    ):
        raise ValueError("finite data and positive residual degrees of freedom required")
    chol = np.linalg.cholesky(c)
    aw, bw = np.linalg.solve(chol, a), np.linalg.solve(chol, b)
    scale = np.linalg.norm(aw, axis=0)
    if np.any(scale == 0):
        raise ValueError("unconstrained parameter")
    u, s, vt = np.linalg.svd(aw / scale, full_matrices=False)
    if s[-1] <= s[0] * 1e-10:
        raise ValueError("rank deficient or ill-conditioned motion geometry")
    p = (vt.T @ ((u.T @ bw) / s)) / scale
    cov = ((vt.T / s**2) @ vt) / np.outer(scale, scale)
    chi2 = float(np.sum((aw @ p - bw) ** 2))
    dof = len(b) - len(p)
    return p, cov * (max(1.0, chi2 / dof) if dof else 1.0), chi2, dof


def motion_fit(
    t_yr: Any,
    xi: Any,
    eta: Any,
    s_xi: Any,
    s_eta: Any,
    p_a: Any,
    p_d: Any,
    t0: float,
    plx_fixed: float | None = None,
    visit_ids: Any = None,
    visit_floor: float = 0.0,
    xy_covariance: Any = None,
) -> dict[str, Any]:
    """Visit-shared error enters covariance blocks, so repeated frames cannot erase it."""
    t, x, y, sx, sy, pa, pd = [np.asarray(v, float) for v in (t_yr, xi, eta, s_xi, s_eta, p_a, p_d)]
    if len({v.shape for v in (t, x, y, sx, sy, pa, pd)}) != 1 or t.ndim != 1:
        raise ValueError("motion arrays must have equal one-dimensional shape")
    if np.any(sx <= 0) or np.any(sy <= 0) or visit_floor < 0:
        raise ValueError("positive errors required")
    n = len(t)
    a = np.zeros((2 * n, 5))
    a[:n, 0], a[n:, 1], a[:n, 2], a[n:, 3], a[:n, 4], a[n:, 4] = 1, 1, t - t0, t - t0, pa, pd
    b = np.r_[x, y]
    if plx_fixed is not None:
        b = b - a[:, 4] * plx_fixed
        a = a[:, :4]
    c = np.diag(np.r_[sx * sx, sy * sy])
    if xy_covariance is not None:
        xy = np.asarray(xy_covariance, float)
        if xy.shape != (n,) or not np.all(np.isfinite(xy)) or np.any(abs(xy) >= sx * sy):
            raise ValueError("finite positive-definite per-point sky covariance required")
        c[np.arange(n), n + np.arange(n)] = xy
        c[n + np.arange(n), np.arange(n)] = xy
    if visit_ids is not None:
        ids = np.asarray(visit_ids)
        shared = (ids[:, None] == ids[None, :]) * visit_floor**2
        c[:n, :n] += shared
        c[n:, n:] += shared
    # Two full WISE epochs constrain four linear parameters with externally
    # estimated measurement covariance, but leave zero model-test degrees of
    # freedom. Do not divide by zero or claim an estimated residual variance.
    p, cov, chi, dof = gls(a, b, c, allow_exact=plx_fixed is not None and n == 2)
    stationary = a[:, [0, 1] + ([4] if plx_fixed is None else [])]
    _, _, chi0, _ = gls(stationary, b, c)
    return dict(
        params=p,
        covariance=cov,
        errors=np.sqrt(np.diag(cov)),
        chi2=chi,
        dof=dof,
        delta_chi2=max(0.0, chi0 - chi),
        t0=t0,
        plx_fixed=plx_fixed,
    )


def fit_pm(
    t_yr: Any, xi: Any, eta: Any, s_xi: Any, s_eta: Any, p_a: Any, p_d: Any, t0: float, plx_fixed: float | None = None
) -> tuple[Any, Any, float]:
    r = motion_fit(t_yr, xi, eta, s_xi, s_eta, p_a, p_d, t0, plx_fixed)
    return r["params"], r["errors"], r["chi2"]


def registration(residuals_arcsec: Any, errors_arcsec: Any, min_stars: int = 5) -> dict[str, Any]:
    """Robust translation from isolated Gaia stars; uncertainty includes their scatter."""
    r, e = np.asarray(residuals_arcsec, float), np.asarray(errors_arcsec, float)
    ok = np.all(np.isfinite(r) & np.isfinite(e) & (e > 0), axis=1)
    for _ in range(3):
        if ok.sum() < min_stars:
            raise ValueError("registration needs at least five isolated unsaturated Gaia stars")
        med = np.median(r[ok], axis=0)
        sig = np.maximum(1.4826 * np.median(abs(r[ok] - med), axis=0), np.median(e[ok], axis=0))
        ok &= np.all(abs(r - med) <= 4 * sig, axis=1)
    # Offset and scatter from the set the last clip kept, the same set `used`, `error` and the RMS describe.
    if ok.sum() < min_stars:
        raise ValueError("registration needs at least five isolated unsaturated Gaia stars")
    med = np.median(r[ok], axis=0)
    sig = np.maximum(1.4826 * np.median(abs(r[ok] - med), axis=0), np.median(e[ok], axis=0))
    return dict(
        offset=med,
        error=1.2533 * sig / np.sqrt(ok.sum()),
        used=ok,
        before_rms=np.sqrt(np.mean(r[ok] ** 2, axis=0)),
        after_rms=np.sqrt(np.mean((r[ok] - med) ** 2, axis=0)),
    )
