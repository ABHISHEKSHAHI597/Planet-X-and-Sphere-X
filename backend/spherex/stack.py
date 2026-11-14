"""Transient rejection, stacking and bright-target display fill (implementation.md §4.3, §4.5)."""

from collections.abc import Iterable
from typing import TYPE_CHECKING, Any

from numpy.typing import ArrayLike, NDArray

if TYPE_CHECKING:
    from .types import Grid, GridFrame, PSFModel, Stack, TimeBin

import warnings

import numpy as np

A = NDArray[Any]


def frame_weight(var: A, sky: A) -> float:
    """One weight per frame, from its sky variance. Per-pixel inverse-variance weights include the
    source's own shot noise, so bright pixels would down-weight themselves and bias stacks low."""
    v = var[sky & (var > 0)]
    return 1.0 / np.median(v) if v.size else 0.0


def reject_transients(frames: A, var: A, k: float = 5.0) -> A:
    """Flag single-frame outliers on pixels whose stack median looks like empty sky.
    Pixels on real sources (median clearly positive) are never clipped. That keeps real
    channel-to-channel spectral changes: a T dwarf varies ×3–5 across band 4, often with one bright end,
    which a symmetric clip would cut. Asteroids, residual cosmic rays and glints on empty sky are caught.
    The flagged pixels feed the asteroid finder (P2-5)."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)          # all-NaN columns are fine
        med = np.nanmedian(frames, axis=0)
        n = np.isfinite(frames).sum(axis=0)
        sig_med = 1.2533 * np.sqrt(np.nanmedian(var, axis=0) / np.maximum(n, 1))
        skylike = np.abs(med) < 3.0 * sig_med
        with np.errstate(invalid="ignore"):
            return np.isfinite(frames) & skylike & (np.abs(frames - med) > k * np.sqrt(var))


def weighted_stack(frames: A, var: A, w_frame: ArrayLike, rej: A) -> tuple[A, A, A]:
    """frames/var: (n, ny, nx) on the common grid, NaN = masked; w_frame: (n,) from frame_weight."""
    ok = np.isfinite(frames) & (var > 0) & ~rej
    w = np.where(ok, np.asarray(w_frame, float)[:, None, None], 0.0)
    sw = w.sum(axis=0)
    with np.errstate(invalid="ignore", divide="ignore"):
        mean = (w * np.where(ok, frames, 0.0)).sum(axis=0) / sw
        v = (w ** 2 * np.where(ok, var, 0.0)).sum(axis=0) / sw ** 2
    return mean, v, ok.sum(axis=0)          # NaN where nothing contributed


def flag_or(flags: ArrayLike, info_mask: int) -> A:
    """Bitwise OR over frames of the informational planes (OVERFLOW, SOURCE, OUTLIER, STREAK).
    flags: (n, ny, nx) integer flags on the common grid (nearest-neighbour), -1/NaN-free."""
    return np.bitwise_or.reduce(np.asarray(flags, np.int64) & info_mask, axis=0)


def display_fill(mean: A, model: A, core: A | None = None) -> tuple[A, A]:
    """Bright-target display (P1-7): fill NaN core pixels with the fitted ePSF model, display stack
    only. model: model surface brightness on the same grid, from M's wing fit (§4.7). Returns
    (filled image, filled mask). The mask drives the dashed outline and "show raw"; measurements
    never read the filled image."""
    hole = ~np.isfinite(mean) & np.isfinite(model)
    if core is not None:
        hole &= core
    out = np.array(mean, float, copy=True)
    out[hole] = model[hole]
    return out, hole


def transient_candidates(rej: A, frame_ids: list[str] | None = None, min_pix: int = 2) -> list[dict[str, Any]]:
    """Per-exposure transients: positive connected components of ≥ min_pix pixels in each frame's
    rejected-pixel plane (§4.5). After artifact vetting they are the asteroid candidates (P2-5)."""
    from scipy.ndimage import center_of_mass, label
    out = []
    for i, r in enumerate(np.asarray(rej, bool)):
        lab, n = label(r)
        for k in range(1, n + 1):
            npix = int((lab == k).sum())
            if npix >= min_pix:
                y, x = center_of_mass(r, lab, k)
                out.append(dict(frame=frame_ids[i] if frame_ids else i, x=float(x), y=float(y), npix=npix))
    return out


def build_stack(gframes: "list[GridFrame]", tbin: "TimeBin", grid: "Grid",
                skipped: "Iterable[tuple[str, str]]" = (), k_reject: float = 5.0) -> "Stack":
    """Stack one (time-bin, band) from GridFrames (I -> P). Frames the caller rejected (QA, fetch
    failures) go in `skipped` with a reason and are listed in the manifest, never dropped silently."""
    from .flags import CANONICAL_INFO
    from .types import Stack
    ny, nx = grid.shape
    if not gframes:
        nan = np.full((ny, nx), np.nan)
        return Stack(bin=tbin, grid=grid, mean=nan, var=nan.copy(), nhits=np.zeros((ny, nx), np.int64),
                     flag_or=np.zeros((ny, nx), np.uint32), rej=np.zeros((0, ny, nx), bool), frame_ids=[],
                     skipped=list(skipped))
    F = np.array([g.sci for g in gframes])
    V = np.array([g.var for g in gframes])
    rej = reject_transients(F, V, k_reject)
    mean, var, nh = weighted_stack(F, V, [g.w_frame for g in gframes], rej)
    fo = flag_or(np.array([g.flags for g in gframes]), CANONICAL_INFO).astype(np.uint32)
    ids = [g.frame_id for g in gframes]
    return Stack(bin=tbin, grid=grid, mean=mean, var=var, nhits=nh.astype(np.int64), flag_or=fo, rej=rej,
                 frame_ids=ids, skipped=list(skipped), transients=transient_candidates(rej, ids))


def bright_display(stack: "Stack", psf_model: "PSFModel", x: float, y: float, r_px: float = 3.0) -> "Stack":
    """P1-7: fill the target's NaN core (pixels within r_px of grid position x, y) with M's fitted PSF
    model (types.PSFModel), display only. Sets stack.display and stack.filled (dashed outline and
    "show raw" in the viewer); stack.mean, the measurement array, is never touched."""
    yy, xx = np.indices(stack.grid.shape)
    core = np.hypot(xx - x, yy - y) <= r_px
    stack.display, stack.filled = display_fill(stack.mean, psf_model.render(stack.grid), core)
    return stack


def sky_pixels(stack: "Stack", clip: float = 3.0, min_pix: int = 50) -> A:
    """Sky mask on a grid for weights and significance: finite, not a known SOURCE, and the stack itself
    below clip σ. SOURCE can cover ≈all pixels of a crowded field, so fall back to the σ cut alone."""
    from .flags import CANONICAL_BITS
    with np.errstate(invalid="ignore", divide="ignore"):
        s = stack.mean / np.sqrt(stack.var)
    fin = np.isfinite(s)
    if fin.sum() < min_pix:
        return fin
    med = np.median(s[fin])
    mad = 1.4826 * np.median(np.abs(s[fin] - med))
    quiet = fin & (np.abs(s - med) < clip * max(mad, 1e-12))
    src = (stack.flag_or & np.uint32(1 << CANONICAL_BITS["SOURCE"])) != 0
    m = quiet & ~src
    return m if m.sum() >= min_pix else quiet
