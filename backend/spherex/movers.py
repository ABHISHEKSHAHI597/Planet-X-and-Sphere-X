"""Mover finder, detection half (implementation.md §4.10 step 1). Linking and scoring: M."""

from typing import Any

import numpy as np
from numpy.typing import ArrayLike, NDArray
from photutils.segmentation import SourceCatalog, detect_sources

from .constants import PIXEL_ARCSEC

A = NDArray[Any]


def detect(sig: ArrayLike, threshold: float = 5.0, npixels: int = 3, mask: A | None = None,
           pix_arcsec: float = PIXEL_ARCSEC) -> A:
    """Sources on a renormalised significance image (grid.significance) at native 6.15″ sampling.
    Returns a structured array: x, y (grid pixels, 0-based), peak σ, npix. Refuses upsampled grids:
    detection and measurement run at native scale only (implementation.md §4.4, workflow.md §11.2)."""
    if pix_arcsec < PIXEL_ARCSEC * 0.999:
        raise ValueError(f"detection needs a native-scale grid, got {pix_arcsec}″ pixels")
    sig = np.asarray(sig, float)
    bad = ~np.isfinite(sig) if mask is None else (mask | ~np.isfinite(sig))
    data = np.where(bad, 0.0, sig)
    seg = detect_sources(data, threshold, n_pixels=npixels, mask=bad)
    dt = [("x", float), ("y", float), ("peak", float), ("npix", int)]
    if seg is None:
        return np.zeros(0, dt)
    cat = SourceCatalog(data, seg, mask=bad)
    return np.array(list(zip(cat.x_centroid, cat.y_centroid, cat.max_value, cat.area.value.astype(int), strict=False)), dt)


def red_sum(m5: A, v5: A, m6: A, v6: A) -> tuple[A, A]:
    """Band 5 + 6 visit stacks, inverse-variance combined: catches cold brown dwarfs that are
    invisible blueward of ≈3.5 µm. Returns (mean, var)."""
    with np.errstate(invalid="ignore", divide="ignore"):
        w5, w6 = np.where(v5 > 0, 1 / v5, 0.0), np.where(v6 > 0, 1 / v6, 0.0)
        a5, a6 = np.nan_to_num(m5), np.nan_to_num(m6)
        w5, w6 = np.where(np.isfinite(m5), w5, 0.0), np.where(np.isfinite(m6), w6, 0.0)
        sw = w5 + w6
        return (w5 * a5 + w6 * a6) / sw, 1.0 / sw
