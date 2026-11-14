"""25-year blink: normalisation and gridding of archival epochs (P2-1; implementation.md §4.13, gate G5.25yr).

D's `access/blink25.py` finds and fetches the epochs; this module (pixel domain, owner I) puts each epoch on the
*view's* grid and on its own sky σ so one common asinh stretch fits 2MASS, AllWISE, NEOWISE and SPHEREx alike.
Positions only: fluxes are not comparable across telescopes and bands (`render.BLINK25_LABEL`).

Assumptions (stated per workflow.md §4.2):
- each archival cutout carries a celestial WCS in its primary HDU (2MASS Atlas, AllWISE `-int-` coadds and NEOWISE
  `-int-1b` frames do);
- the sky dominates the cutout, so an iterative 3σ clip of the image itself isolates sky pixels;
- several images of one epoch (a 2MASS mosaic, NEOWISE single exposures) are each normalised first and then
  combined with a per-pixel median, so different zero points and backgrounds never mix.
No network I/O here (workflow.md §3)."""

from __future__ import annotations

import gzip
import io
import warnings
from typing import Any

import numpy as np
from astropy.io import fits
from astropy.wcs import WCS
from numpy.typing import NDArray

from .grid import to_grid
from .render import normalise_epoch
from .types import Grid

A = NDArray[Any]


def sky_mask(img: A, nsigma: float = 3.0, iters: int = 5) -> A:
    """Pixels consistent with sky: iterative median/MAD clip (sources and their wings excluded)."""
    a = np.asarray(img, float)
    ok = np.isfinite(a)
    for _ in range(iters):
        s = a[ok]
        if s.size < 10:
            break
        med = np.median(s)
        sig = 1.4826 * np.median(np.abs(s - med))
        if not sig > 0:
            break
        new = np.isfinite(a) & (np.abs(a - med) < nsigma * sig)
        if (new == ok).all():
            break
        ok = new
    return ok


def read_image(raw: bytes) -> tuple[A, WCS]:
    """(image, celestial WCS) of the first HDU holding a 2-D image. Gzipped bytes are accepted."""
    data = gzip.decompress(raw) if raw[:2] == b"\x1f\x8b" else raw
    with fits.open(io.BytesIO(data)) as hl:
        for h in hl:
            if h.data is not None and np.ndim(h.data) == 2:
                w = WCS(h.header).celestial
                if not w.has_celestial:
                    raise ValueError("archival image has no celestial WCS")
                return np.asarray(h.data, float), w
    raise ValueError("no 2-D image in the archival file")


def epoch_on_grid(images: list[bytes], grid: Grid) -> tuple[A, int]:
    """One archival epoch on the view grid, in units of its own sky σ.

    Each image is reprojected (bilinear; surface brightness, no flux rescaling), normalised on its *own* sky
    (median 0, robust σ 1) and the images are combined with a per-pixel median. Returns (image, n_used); the
    image is NaN where no input covers the grid or where an input had too little sky to normalise."""
    planes = []
    for raw in images:
        try:
            img, w = read_image(raw)
        except (ValueError, OSError):
            continue
        on, _ = to_grid(img, np.ones_like(img), w, grid.wcs, grid.shape)
        if np.isfinite(on).sum() < 10:
            continue
        n = normalise_epoch(on, sky_mask(on))
        if np.isfinite(n).any():
            planes.append(n)
    if not planes:
        return np.full(grid.shape, np.nan), 0
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)  # all-NaN pixels stay NaN
        return np.nanmedian(np.stack(planes), axis=0), len(planes)


def spherex_epoch(stack: A) -> A:
    """The SPHEREx visit stack on the same σ scale as the archival epochs."""
    return normalise_epoch(stack, sky_mask(stack))


def select_epochs(epochs: list[dict[str, Any]], max_neowise: int = 6) -> list[dict[str, Any]]:
    """Every 2MASS and AllWISE W2 epoch, plus NEOWISE W2 epochs thinned evenly in time to `max_neowise`
    (≈ one per two years over 2014–2024), in time order. AllWISE W1 is dropped: W2 pairs with band 6, the band
    the view blinks by default, and showing both adds no positional information."""
    keep = [e for e in epochs if e["label"].startswith("2MASS") or e["label"] == "AllWISE W2"]
    neo = sorted((e for e in epochs if e["label"].startswith("NEOWISE")), key=lambda e: e["year"])
    if len(neo) > max_neowise:
        idx = np.linspace(0, len(neo) - 1, max_neowise).round().astype(int)
        neo = [neo[i] for i in sorted(set(idx.tolist()))]
    return sorted(keep + neo, key=lambda e: e["year"])
