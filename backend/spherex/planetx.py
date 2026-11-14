"""Distance-parametrized parallax linking on per-day orphans (§4.12).

Distances are a first-order parallax inference, not an orbital solution.
Pluto linking is validated against Horizons, never by its distance fit.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from .astrometry import gls, parallax_factors

DISTANCES_AU = (50.0, 100.0, 150.0, 200.0, 300.0, 500.0, 800.0, 1200.0)


def orphan_rows(epochs: list[list[dict[str, Any]]]) -> list[dict[str, Any]]:
    """Unmatched detections with no position-consistent counterpart on another day.

    Experimental three-sigma covariance ellipse; missing/invalid uncertainty
    cannot establish an orphan. Completeness requires empirical calibration.
    """
    rows = [r for epoch in epochs for r in epoch if not r.get("known")]
    out = []
    for row in rows:
        try:
            if row["s_xi"] <= 0 or row["s_eta"] <= 0:
                continue
            cov = np.array(
                [[row["s_xi"] ** 2, row.get("cov_xi_eta", 0)], [row.get("cov_xi_eta", 0), row["s_eta"] ** 2]]
            )
            np.linalg.cholesky(cov)
            if not np.all(np.isfinite(cov)):
                continue
            static = False
            for epoch in epochs:
                for other in epoch:
                    if int(other["mjd"]) == int(row["mjd"]):
                        continue
                    ocov = np.array(
                        [
                            [other["s_xi"] ** 2, other.get("cov_xi_eta", 0)],
                            [other.get("cov_xi_eta", 0), other["s_eta"] ** 2],
                        ]
                    )
                    np.linalg.cholesky(ocov)
                    delta = np.array([row["xi"] - other["xi"], row["eta"] - other["eta"]])
                    if not np.all(np.isfinite(delta)) or not np.all(np.isfinite(ocov)):
                        raise ValueError("uncertain counterpart")
                    if delta @ np.linalg.solve(cov + ocov, delta) <= 9:
                        static = True
                        break
                if static:
                    break
            if not static:
                out.append(row)
        except (KeyError, ValueError, np.linalg.LinAlgError):
            continue
    return out


def shift_and_stack(
    images: Any, variances: Any, mjd: Any, ra: float, dec: float, distance_au: float, pixel_arcsec: float = 6.15
) -> tuple[Any, Any]:
    """Digital tracking on north-up native-scale daily images; bilinear variance weights squared.

    Pixel covariances remain correlated. Detection must renormalize significance on sky,
    and flux/centroid measurements must return to the original native frames.
    """
    f, v = np.asarray(images, float), np.asarray(variances, float)
    if f.shape != v.shape or f.ndim != 3 or len(mjd) != len(f) or pixel_arcsec < 6.15:
        raise ValueError("equal native daily images, variances and epochs required")
    dx, dy = distant_body_offset(mjd, float(np.median(mjd)), ra, dec, distance_au)
    yy, xx = np.indices(f.shape[1:])
    num = np.zeros(f.shape[1:])
    den = np.zeros_like(num)
    varnum = np.zeros_like(num)
    for image, var, a, d in zip(f, v, dx, dy, strict=True):
        # Positive east is negative grid x. Sample original mover location to align it at reference.
        sx = xx - a / pixel_arcsec
        sy = yy + d / pixel_arcsec
        x0 = np.floor(sx).astype(int)
        y0 = np.floor(sy).astype(int)
        tx = sx - x0
        ty = sy - y0
        total = np.zeros_like(num)
        vv = np.zeros_like(num)
        support = np.zeros_like(num)
        for ox, oy, w in [(0, 0, (1 - tx) * (1 - ty)), (1, 0, tx * (1 - ty)), (0, 1, (1 - tx) * ty), (1, 1, tx * ty)]:
            x = x0 + ox
            y = y0 + oy
            inside = (x >= 0) & (y >= 0) & (x < f.shape[2]) & (y < f.shape[1])
            xi = np.clip(x, 0, f.shape[2] - 1)
            yi = np.clip(y, 0, f.shape[1] - 1)
            ok = inside & np.isfinite(image[yi, xi]) & np.isfinite(var[yi, xi]) & (var[yi, xi] > 0)
            weight = np.where(ok, w, 0.0)
            total += np.nan_to_num(image[yi, xi]) * weight
            vv += np.nan_to_num(var[yi, xi]) * weight**2
            support += weight
        ok = (support > 0.999999) & (vv > 0)
        # Frame-only sky weight prevents source shot noise biasing bright-source sums.
        noise = var[np.isfinite(var) & (var > 0)]
        fw = 1 / np.median(noise) if noise.size else 0.0
        num += np.where(ok, total * fw, 0.0)
        den += np.where(ok, fw, 0.0)
        varnum += np.where(ok, vv * fw**2, 0.0)
    with np.errstate(divide="ignore", invalid="ignore"):
        return num / den, varnum / den**2


def distant_body_offset(mjd: Any, mjd0: float, ra: float, dec: float, dist_au: float) -> tuple[Any, Any]:
    if not np.isfinite(dist_au) or dist_au <= 0:
        raise ValueError("positive distance required")
    pa, pd = parallax_factors(mjd, ra, dec)
    a0, d0 = parallax_factors(mjd0, ra, dec)
    return 206264.806 / dist_au * (pa - a0), 206264.806 / dist_au * (pd - d0)


def infer_distance(mjd: Any, xi: Any, eta: Any, errors: Any, ra: float, dec: float) -> dict[str, Any]:
    """Fit parallax + linear orbital nuisance; reject degenerate time geometry."""
    t, x, y, e = [np.asarray(v, float) for v in (mjd, xi, eta, errors)]
    if len(t) < 4 or np.any(e <= 0):
        raise ValueError("at least four days and positive errors required")
    pa, pd = parallax_factors(t, ra, dec)
    n = len(t)
    dt = t - t.mean()
    a = np.zeros((2 * n, 5))
    a[:n, 0], a[n:, 1], a[:n, 2], a[n:, 3], a[:n, 4], a[n:, 4] = 1, 1, dt, dt, pa, pd
    p, c, chi, dof = gls(a, np.r_[x, y], np.diag(np.tile(e, 2) ** 2))
    if p[4] <= 0:
        raise ValueError("nonpositive fitted parallax; no physical distance")
    d = 206264.806 / p[4]
    ed = d * np.sqrt(c[4, 4]) / p[4]
    # Circular speed projected into angular speed; linear approximation is checked as a bound.
    bound = 3548.0 / d**1.5  # arcsec/day, 2*pi AU/yr at 1 AU scaled by d^(-3/2)
    if np.linalg.norm(p[2:4]) > np.sqrt(2) * bound:
        raise ValueError("orbital nuisance exceeds escape-speed bound")
    return dict(
        distance_au=float(d),
        error_au=float(ed),
        chi2=chi,
        dof=dof,
        orbital_arcsec_day=p[2:4].tolist(),
        covariance=c.tolist(),
    )


def link_orphans(
    rows: list[dict[str, Any]],
    ra: float,
    dec: float,
    distances: Any = DISTANCES_AU,
    tolerance_arcsec: float = 9.225,
    max_chains: int = 100000,
) -> list[dict[str, Any]]:
    """Retain ambiguous daily branches at each common distance, never choose by input order.

    A bounded branch budget fails explicitly rather than silently dropping paths.
    Distance inference requires at least four days; shorter chains remain absent.
    """
    if tolerance_arcsec <= 0 or max_chains < 1:
        raise ValueError("positive spatial tolerance and chain budget required")
    out = []
    for d in distances:
        if not np.isfinite(d) or d <= 0:
            raise ValueError("positive finite distance hypotheses required")
        for seed in rows:
            eligible: dict[int, list[dict[str, Any]]] = {}
            for r in sorted(rows, key=lambda r: (r["mjd"], str(r.get("id", "")))):
                if r["mjd"] <= seed["mjd"] or r["day"] == seed["day"]:
                    continue
                dx, dy = distant_body_offset(r["mjd"], seed["mjd"], ra, dec, d)
                dt = abs(r["mjd"] - seed["mjd"])
                orbital = np.sqrt(2) * 3548.0 / d**1.5 * dt
                residual = np.hypot(r["xi"] - seed["xi"] - dx, r["eta"] - seed["eta"] - dy)
                sf = np.asarray(seed["spectrum"])
                rf = np.asarray(r["spectrum"])
                se = np.asarray(seed["spectrum_err"])
                re = np.asarray(r["spectrum_err"])
                if not (sf.shape == rf.shape == se.shape == re.shape):
                    continue
                common = np.isfinite(sf) & np.isfinite(rf) & np.isfinite(se) & np.isfinite(re) & (se > 0) & (re > 0)
                compatible = (
                    sf.shape == rf.shape
                    and common.sum() >= 3
                    and np.all(abs(sf[common] - rf[common]) <= 3 * np.hypot(se[common], re[common]))
                )
                if residual <= tolerance_arcsec + orbital and compatible:
                    eligible.setdefault(r["day"], []).append(r)
            chains = [[seed]]
            for options in eligible.values():
                if len(chains) * len(options) + len(out) > max_chains:
                    raise ValueError("ambiguous orphan field exceeds chain budget")
                chains = [chain + [option] for chain in chains for option in options]
            for chain in chains:
                if len(chain) >= 4 and len({v["visit"] for v in chain}) >= 2:
                    out.append(dict(distance_grid_au=float(d), chain=chain, label="parallax-linked orphan candidate"))
    return out
