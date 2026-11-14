"""QR3 table ePSFs on zero-based parent pixels; native-pixel fits (impl. §4.7).

Table orientation is preserved. F5 must validate it against stars before release.
The finite table supports ±3.2 px, and must not be extrapolated into far wings.
"""

from __future__ import annotations

import functools
from dataclasses import dataclass
from typing import Any

import numpy as np
from scipy.ndimage import map_coordinates
from scipy.optimize import least_squares

from .types import Grid


class EPSF:
    def __init__(self, table: Any, oversample: int = 5) -> None:
        self.xc, self.yc = np.asarray(table["XCENTER"], float), np.asarray(table["YCENTER"], float)
        psf = np.asarray(table["EPSF"], float)
        if psf.ndim != 3 or psf.shape[1] != psf.shape[2] or not np.all(np.isfinite(psf)):
            raise ValueError("EPSF must contain finite square zone arrays")
        sums = psf.sum(axis=(1, 2), keepdims=True)
        if np.any(sums <= 0) or oversample <= 0:
            raise ValueError("invalid EPSF integral or oversampling")
        self.os = oversample
        self.psf = psf / sums * self.os**2
        self.c = (psf.shape[-1] - 1) / 2

    def zone(self, xp: float, yp: float) -> int:
        if not (np.isfinite(xp) and np.isfinite(yp) and 0 <= xp < 2040 and 0 <= yp < 2040):
            raise ValueError("ePSF zone requires parent-detector pixels in [0,2040)")
        return int(np.argmin((self.xc - xp) ** 2 + (self.yc - yp) ** 2))

    def sample(self, iz: int, dx: Any, dy: Any) -> Any:
        return map_coordinates(
            self.psf[iz],
            [self.c + self.os * np.asarray(dy), self.c + self.os * np.asarray(dx)],
            order=3,
            mode="grid-constant",
            cval=0.0,
        )

    def stamp(self, iz: int, dx: float, dy: float, half: int = 3) -> Any:
        yy, xx = np.mgrid[-half : half + 1, -half : half + 1]
        return self.sample(iz, xx - dx, yy - dy)


@dataclass
class StarFit:
    params: Any
    covariance: Any
    rchi2: float
    dof: int
    wing_fit: bool
    model: Any

    @property
    def errors(self) -> Any:
        return np.sqrt(np.diag(self.covariance))


def fit_native(
    img: Any,
    var: Any,
    bad: Any,
    epsf: EPSF,
    iz: int,
    x0: float,
    y0: float,
    half: int = 3,
    fixed_xy: bool = False,
    max_shift: float = 1.5,
    background_order: int = 0,
) -> StarFit | None:
    if background_order not in (0, 1):
        raise ValueError("background order must be constant or plane")
    ix, iy = int(round(x0)), int(round(y0))
    ny, nx = img.shape
    if ix - half < 0 or iy - half < 0 or ix + half >= nx or iy + half >= ny:
        return None
    sl = np.s_[iy - half : iy + half + 1, ix - half : ix + half + 1]
    d, v = np.asarray(img[sl], float), np.asarray(var[sl], float)
    mask = bad[sl] | ~np.isfinite(d) | ~np.isfinite(v) | (v <= 0)
    npar = (2 if fixed_xy else 4) + 2 * background_order
    if (~mask).sum() < npar + 3:
        return None

    def model(p: Any) -> Any:
        x, y, f, b = (x0, y0, *p[:2]) if fixed_xy else p[:4]
        result = f * epsf.stamp(iz, x - ix, y - iy, half) + b
        if background_order:
            yy, xx = np.mgrid[-half : half + 1, -half : half + 1]
            result = result + p[-2] * xx + p[-1] * yy
        return result

    def resid(p: Any) -> Any:
        return (d - model(p))[~mask] / np.sqrt(v[~mask])

    f0 = float(np.sum(d[~mask] - np.median(d[~mask])))
    p0 = [f0, float(np.median(d[~mask]))] if fixed_xy else [x0, y0, f0, float(np.median(d[~mask]))]
    if background_order:
        p0 += [0.0, 0.0]
    bounds: Any = (
        (-np.inf, np.inf)
        if fixed_xy
        else ([x0 - max_shift, y0 - max_shift, -np.inf, -np.inf], [x0 + max_shift, y0 + max_shift, np.inf, np.inf])
    )
    if background_order and not fixed_xy:
        bounds = (list(bounds[0]) + [-np.inf, -np.inf], list(bounds[1]) + [np.inf, np.inf])
    r = least_squares(resid, p0, bounds=bounds, xtol=1e-11, ftol=1e-11, gtol=1e-11)
    if not r.success or (not fixed_xy and np.any(r.active_mask[:2])):
        return None
    _, s, vt = np.linalg.svd(r.jac, full_matrices=False)
    if s[-1] <= s[0] * 1e-10:
        return None
    dof = r.fun.size - npar
    chi = float(r.fun @ r.fun / dof)
    cov = ((vt.T / s**2) @ vt) * max(1.0, chi)
    return StarFit(r.x, cov, chi, dof, bool(mask[half - 1 : half + 2, half - 1 : half + 2].any()), model(r.x))


def fit_star(
    img: Any,
    var: Any,
    bad: Any,
    epsf: EPSF,
    iz: int,
    x0: float,
    y0: float,
    half: int = 3,
    fixed_xy: bool = False,
    max_shift: float = 1.5,
) -> Any:
    r = fit_native(img, var, bad, epsf, iz, x0, y0, half, fixed_xy, max_shift)
    return None if r is None else (r.params, r.errors, r.rchi2)


def fit_sources(img: Any, var: Any, bad: Any, epsf: EPSF, positions: Any, zones: Any, half: int = 4) -> dict[str, Any]:
    """Simultaneous fixed-position signed amplitudes + sky, retaining blend covariance.

    Negative flux is valid for a non-detection. A nearly unresolved pair is rejected.
    """
    pos = np.asarray(positions, float)
    x0, y0 = np.mean(pos, axis=0)
    ix, iy = int(round(x0)), int(round(y0))
    if ix - half < 0 or iy - half < 0 or ix + half >= img.shape[1] or iy + half >= img.shape[0]:
        raise ValueError("blend stamp off image")
    yy, xx = np.mgrid[iy - half : iy + half + 1, ix - half : ix + half + 1]
    sl = np.s_[iy - half : iy + half + 1, ix - half : ix + half + 1]
    d, v = img[sl], var[sl]
    ok = ~bad[sl] & np.isfinite(d) & np.isfinite(v) & (v > 0)
    a = np.stack(
        [epsf.sample(z, xx - x, yy - y) for (x, y), z in zip(pos, zones, strict=True)] + [np.ones(d.shape)], axis=-1
    )
    from .astrometry import gls

    p, c, chi, dof = gls(a[ok], d[ok], np.diag(v[ok]))
    return dict(flux=p[:-1], covariance=c[:-1, :-1], background=p[-1], rchi2=chi / dof, dof=dof)


def fit_blend(
    img: Any,
    var: Any,
    bad: Any,
    epsf: EPSF,
    positions: Any,
    zones: Any,
    max_shift: float = 1.5,
    half: int = 4,
    shared_shift: bool = False,
) -> StarFit | None:
    """Joint signed flux covariance with a free centroid or shared WCS translation.

    shared_shift preserves catalogue separations and lets a bright neighbour constrain
    the local WCS translation even when the forced target flux is consistent with zero.
    The translation is a fitted nuisance parameter, never an exact registration.
    """
    pos = np.asarray(positions, float)
    ix, iy = np.rint(pos.mean(axis=0)).astype(int)
    if ix - half < 0 or iy - half < 0 or ix + half >= img.shape[1] or iy + half >= img.shape[0]:
        return None
    sl = np.s_[iy - half : iy + half + 1, ix - half : ix + half + 1]
    yy, xx = np.mgrid[iy - half : iy + half + 1, ix - half : ix + half + 1]
    d, v = img[sl], var[sl]
    ok = ~bad[sl] & np.isfinite(d) & np.isfinite(v) & (v > 0)
    npar = 3 + len(pos)
    if ok.sum() < npar + 3:
        return None
    try:
        seed = fit_sources(img, var, bad, epsf, pos, zones, half)
    except (ValueError, np.linalg.LinAlgError):
        return None

    def model(p: Any) -> Any:
        xy = pos + (p[:2] - pos[0]) if shared_shift else np.vstack([p[:2], pos[1:]])
        return sum(f * epsf.sample(z, xx - x, yy - y) for (x, y), f, z in zip(xy, p[2:-1], zones, strict=True)) + p[-1]

    p0 = np.r_[pos[0], seed["flux"], seed["background"]]
    lb = np.r_[pos[0] - max_shift, np.full(len(pos) + 1, -np.inf)]
    ub = np.r_[pos[0] + max_shift, np.full(len(pos) + 1, np.inf)]
    r = least_squares(lambda p: (d - model(p))[ok] / np.sqrt(v[ok]), p0, bounds=(lb, ub))
    _, s, vt = np.linalg.svd(r.jac, full_matrices=False)
    if not r.success or np.any(r.active_mask[:2]) or s[-1] <= s[0] * 1e-10:
        return None
    dof = len(r.fun) - npar
    chi = float(r.fun @ r.fun / dof)
    return StarFit(
        r.x,
        ((vt.T / s**2) @ vt) * max(1.0, chi),
        chi,
        dof,
        bool((~ok)[half - 1 : half + 2, half - 1 : half + 2].any()),
        model(r.x),
    )


@dataclass
class FittedPSF:
    """M→I display model preserving the native PSF orientation through its WCS."""

    epsf: EPSF
    zone_id: int
    wcs: Any
    x: float
    y: float
    flux: float

    def render(self, grid: Grid) -> Any:
        yy, xx = np.indices(grid.shape)
        nx, ny = self.wcs.world_to_pixel(grid.wcs.pixel_to_world(xx, yy))
        return self.flux * self.epsf.sample(self.zone_id, nx - self.x, ny - self.y)


@functools.lru_cache(maxsize=12)
def load_table(path: str) -> EPSF:
    """The EPSF HDU of one calibration file, read once per process (≈8 MB per detector)."""
    from astropy.io import fits

    return EPSF(fits.getdata(path, extname="EPSF"))
