"""Common north-up grid, reprojection and significance (implementation.md §4.4)."""

from collections.abc import Callable, Sequence
from typing import Any

import numpy as np
from astropy.wcs import WCS
from numpy.typing import ArrayLike, NDArray
from reproject import reproject_interp

from .constants import PIXEL_ARCSEC
from .flags import canonical
from .types import CalFrame, Grid, GridFrame

A = NDArray[Any]

MAX_SIDE_PX = 301            # ≤ 30′ stays native; larger FOVs are binned (P0-4, 60′ → ≈12″ pixels)


def pixel_scale_for(fov_arcmin: float, px_arcsec: float | None = None) -> float:
    """Display pixel scale: the requested one (native 6.15″ default, e.g. 3″ upsampled), coarsened so
    the grid side stays ≤ MAX_SIDE_PX. Larger FOVs degrade gracefully instead of exploding payloads."""
    px = PIXEL_ARCSEC if px_arcsec is None else float(px_arcsec)
    return max(px, fov_arcmin * 60.0 / MAX_SIDE_PX)


def make_grid(ra: float, dec: float, fov_arcmin: float, pix_arcsec: float = PIXEL_ARCSEC) -> Grid:
    n = int(fov_arcmin * 60 / pix_arcsec) | 1                    # odd → centre on a pixel
    w = WCS(naxis=2)
    w.wcs.ctype = ["RA---TAN", "DEC--TAN"]
    w.wcs.crval = [ra, dec]
    w.wcs.crpix = [(n + 1) / 2, (n + 1) / 2]
    w.wcs.cdelt = [-pix_arcsec / 3600, pix_arcsec / 3600]        # north up, east left
    return Grid(wcs=w, shape=(n, n), pix_arcsec=float(pix_arcsec), ra=float(ra), dec=float(dec))


def grid_centres(pos: Callable[[A], tuple[A, A]], mjd: ArrayLike, mode: str = "fixed") -> tuple[A, A]:
    """Grid centre per frame (implementation.md §4.1). pos: M's pos(t) -> (ra, dec) arrays.
    fixed: one centre, pos at the median frame time, so a mover stays near the centre in every visit.
    track: each frame centred on pos(MJD-AVG); the only useful mode for Solar System bodies."""
    mjd = np.asarray(mjd, float)
    if mode == "fixed":
        ra, dec = pos(np.array([np.median(mjd)]))
        return np.repeat(np.atleast_1d(ra), mjd.size), np.repeat(np.atleast_1d(dec), mjd.size)
    if mode == "track":
        ra, dec = pos(mjd)
        return np.atleast_1d(ra), np.atleast_1d(dec)
    raise ValueError(f"unknown centring mode {mode!r}")


def to_grid(sci: A, var: A, frame_wcs: WCS, grid_wcs: WCS, shape: tuple[int, int],
            order: str = "bilinear") -> tuple[A, A]:
    """Surface brightness (MJy/sr) is intensive, so interpolation conserves it with no flux rescaling.
    frame_wcs = WCS(IMAGE header) picks up RA---TAN-SIP; the PA 0/180 rotation is handled here.
    order="bicubic" (difference path) is NaN-safe: spline prefiltering would spread one NaN over the
    whole frame, so holes are filled with 0 for the interpolation and re-masked, dilated by two pixels (spline ringing)."""
    bad = ~np.isfinite(sci)
    if order == "bicubic" and bad.any():
        from scipy.ndimage import binary_dilation
        a, foot = reproject_interp((np.where(bad, 0.0, sci), frame_wcs), grid_wcs, shape_out=shape, order=order)
        hole, _ = reproject_interp((binary_dilation(bad, iterations=2).astype(float), frame_wcs), grid_wcs, shape_out=shape,
                                   order="bilinear")
        a[~(hole == 0)] = np.nan
    else:
        a, foot = reproject_interp((sci, frame_wcs), grid_wcs, shape_out=shape, order=order)
    v, _ = reproject_interp((var, frame_wcs), grid_wcs, shape_out=shape, order="nearest-neighbor")
    a[foot == 0] = np.nan
    return a, v


def map_to_grid(m: ArrayLike, frame_wcs: WCS, grid_wcs: WCS, shape: tuple[int, int]) -> A:
    """Per-pixel maps that must not be blended (λ from CWAVE, flags): nearest-neighbour, NaN outside."""
    a, foot = reproject_interp((np.asarray(m, float), frame_wcs), grid_wcs, shape_out=shape,
                               order="nearest-neighbor")
    a[foot == 0] = np.nan
    return a


def frame_to_grid(cf: CalFrame, grid: Grid, order: str = "bilinear") -> GridFrame:
    """One calibrated frame onto the common grid: sci bilinear, var/λ/flags nearest-neighbour.
    Flags are re-packed to the canonical layout first, so stacks of mixed releases OR correctly."""
    sci, var = to_grid(cf.sci, cf.var, cf.wcs, grid.wcs, grid.shape, order)
    lam = map_to_grid(cf.lam, cf.wcs, grid.wcs, grid.shape)
    fl = map_to_grid(canonical(cf.flags, cf.bits).astype(float), cf.wcs, grid.wcs, grid.shape)
    return GridFrame(sci=sci, var=var, lam=lam, flags=np.nan_to_num(fl).astype(np.uint32),
                     w_frame=cf.w_frame, mjd=cf.mjd, detector=cf.detector, survey=cf.survey,
                     frame_id=cf.ref.id if cf.ref else cf.obsid,
                     psf_fwhm_arcsec=float(cf.header.get("PSF_FWHM", np.nan)),
                     photometric_scale=cf.photometric_scale)


def significance(img: A, var: A, sky: A) -> tuple[A, float]:
    """img/√var, rescaled so that sky pixels have unit robust σ. Resampling correlates noise, and a
    nearest-neighbour variance map is only approximate. Without this step, '5σ' is not 5σ."""
    with np.errstate(invalid="ignore", divide="ignore"):
        s = img / np.sqrt(var)
    ss = s[sky & np.isfinite(s)]
    k = 1.4826 * np.median(np.abs(ss - np.median(ss))) if ss.size > 50 else 1.0
    return s / k, k          # report k as a QA number; ≈1 at native sampling


def centroids(img: A, xy: Sequence[tuple[float, float]] | A, half: int = 3) -> A:
    """Background-subtracted, first-moment centroids in (2·half+1)² boxes; NaN where the box is
    off the image or has non-finite pixels. Grid pixel coordinates, 0-based."""
    out = np.full((len(xy), 2), np.nan)
    ny, nx = img.shape
    for k, (x, y) in enumerate(xy):
        ix, iy = int(round(x)), int(round(y))
        if ix - half - 1 < 0 or iy - half - 1 < 0 or ix + half + 1 >= nx or iy + half + 1 >= ny:
            continue
        big = img[iy - half - 1:iy + half + 2, ix - half - 1:ix + half + 2]
        if not np.isfinite(big).all():
            continue
        ring = np.concatenate([big[0], big[-1], big[1:-1, 0], big[1:-1, -1]])
        box = np.clip(big[1:-1, 1:-1] - np.median(ring), 0, None)
        if box.sum() <= 0:
            continue
        g = np.arange(-half, half + 1)
        out[k] = ix + (box.sum(0) * g).sum() / box.sum(), iy + (box.sum(1) * g).sum() / box.sum()
    return out


def registration_offsets(img_a: A, img_b: A, xy: Sequence[tuple[float, float]], half: int = 3,
                         iterate: int = 2) -> A:
    """Positional offsets (b − a, grid px) of static stars between two stacks on the same grid, for the
    G2 registration check (workflow.md §6: median < 0.1 px). xy: predicted star positions (e.g. Gaia,
    propagated to each epoch by M's pos(t)). The box is re-centred `iterate` times on each image."""
    pa = np.asarray(xy, float)
    pb = pa.copy()
    for _ in range(iterate):
        ca, cb = centroids(img_a, np.nan_to_num(pa), half), centroids(img_b, np.nan_to_num(pb), half)
        pa, pb = np.where(np.isfinite(ca), ca, pa), np.where(np.isfinite(cb), cb, pb)
    d = cb - ca
    return d[np.isfinite(d).all(axis=1)]
