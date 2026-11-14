"""Display limits, stretch and float16 encoding (implementation.md §5.2, §6.3, §6.4, §4.13)."""

import warnings
from collections.abc import Sequence
from typing import Any

import numpy as np
from astropy.visualization import ZScaleInterval
from numpy.typing import ArrayLike, NDArray

from .constants import NODATA_F16

A = NDArray[Any]


def shared_limits(stacks: ArrayLike, lim: str = "zscale") -> tuple[float, float]:
    """One (lo, hi) for every frame of a blink, from the median stack (understanding.md §5.4).
    lim: 'zscale' | 'p99.5' | 'manual:lo,hi'. Per-frame limits are an expert toggle, never default."""
    if lim.startswith("manual:"):
        lo, hi = (float(v) for v in lim[7:].split(","))
        return lo, hi
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        med = np.nanmedian(np.asarray(stacks, float), axis=0)
    good = med[np.isfinite(med)]
    if good.size == 0:
        return 0.0, 1.0
    if lim == "zscale":
        lo, hi = ZScaleInterval().get_limits(good)
    elif lim.startswith("p"):
        p = float(lim[1:])
        lo, hi = np.percentile(good, [100 - p, p])
    else:
        raise ValueError(f"unknown lim {lim!r}")
    if not hi > lo:
        hi = lo + 1.0
    return float(lo), float(hi)


def stretch(x: ArrayLike, lo: float, hi: float, mode: str = "asinh", beta: float = 8.0) -> A:
    """CPU twin of the WebGL shader (§6.3): returns t in [0, 1], NaN where no data.
    mode: lin | asinh | log | sqrt | diverging (symmetric, uses hi as the clip)."""
    x = np.asarray(x, float)
    with np.errstate(invalid="ignore"):
        if mode == "diverging":
            return np.clip(0.5 + 0.5 * x / hi, 0.0, 1.0)
        t = np.clip((x - lo) / (hi - lo), 0.0, 1.0)
        if mode == "asinh":
            return np.arcsinh(t * beta) / np.arcsinh(beta)
        if mode == "log":
            return np.log1p(t * beta) / np.log1p(beta)
        if mode == "sqrt":
            return np.sqrt(t)
        if mode == "lin":
            return t
    raise ValueError(f"unknown stretch {mode!r}")


def to_u8(t: A) -> A:
    """[0,1] → 8-bit LUT index for the PNG renderer. No data → 0; the renderer tints it."""
    return np.where(np.isfinite(t), np.round(np.nan_to_num(t) * 255), 0).astype(np.uint8)


def to_f16(a: ArrayLike) -> bytes:
    """Display payload: float16 LE, real values clipped to [−5e4, 6.5e4], no data = −65504."""
    a = np.asarray(a)
    out = np.clip(a, -5.0e4, 6.5e4).astype("<f2")
    out[~np.isfinite(a)] = NODATA_F16
    return out.tobytes()


def cube_to_f16(cube: ArrayLike) -> bytes:
    """λ-scrubber payload (P2-2): (17, ny, nx) planes in bin order, same encoding as stacks."""
    return to_f16(np.asarray(cube))


def normalise_epoch(img: A, sky: A) -> A:
    """25-year blink (P2-1): put an epoch from any telescope on its own sky σ, so one common asinh
    stretch fits all. Positions only: fluxes are not comparable across telescopes and bands."""
    s = np.asarray(img, float)[sky & np.isfinite(img)]
    if s.size < 10:
        return np.full(np.shape(img), np.nan)
    med = np.median(s)
    sig = 1.4826 * np.median(np.abs(s - med))
    return (np.asarray(img, float) - med) / (sig if sig > 0 else 1.0)


# Manifest `format` ids (workflow.md §7.1–7.2). A layout change means a new id; viewers refuse unknown ids.
FORMAT_F16 = "f16le-row0south-nodata-65504@1"
FORMAT_F32 = "f32le-row0south-nodata-nan@1"
FORMAT_U32_FLAGS = "u32le-row0south-flags-canonical@1"     # bit meanings: flags.CANONICAL_BITS


def to_f32(a: ArrayLike) -> bytes:
    """Science payload (.f32, .var.f32): float32 LE, NaN = no data (implementation.md §5.2)."""
    return np.asarray(a, "<f4").tobytes()


def to_u32_flags(flags: ArrayLike) -> bytes:
    """Flag payload (.flags.u32): canonical bit layout, uint32 LE."""
    return np.asarray(flags, "<u4").tobytes()


def golden_F(n: int = 121) -> A:
    """Contract golden (workflow.md §7.3): an 'F' in the north-east corner of a north-up, east-left
    grid, row 0 = south. North-east = high rows, low columns. Sentinel (no-data) pixels: the south-west
    corner 3×3 and the centre pixel. Values: background 0, the F 100, a ramp 0..50 along the bottom row."""
    a = np.zeros((n, n))
    a[0, :] = np.linspace(0.0, 50.0, n)          # south edge ramp: west (right) is brighter
    top, left = n - 6, 5                          # F drawn upright: its stem on the east (left) side
    a[top - 30:top + 1, left:left + 4] = 100.0    # stem
    a[top - 3:top + 1, left:left + 20] = 100.0    # top bar
    a[top - 17:top - 13, left:left + 14] = 100.0  # middle bar
    a[:3, n - 3:] = np.nan                        # south-west corner
    a[n // 2, n // 2] = np.nan
    return a


def rgb(r: A, g: A, b: A, limits: Sequence[tuple[float, float]], mode: str = "asinh", beta: float = 8.0) -> A:
    """RGB composite (presets in cube.RGB_PRESETS): each channel stretched with its own shared limits.
    Returns (ny, nx, 3) in [0, 1], NaN where a channel has no data."""
    return np.stack([stretch(x, lo, hi, mode, beta) for x, (lo, hi) in zip((r, g, b), limits, strict=False)], axis=-1)


BLINK25_LABEL = "different telescopes, positions only"


def blink25_plan(expected_jump_arcmin: float, other_pix_arcsec: float, fov_arcmin: float = 6.0) -> tuple[float, float]:
    """25-year blink (P2-1, implementation.md §4.13): FOV ≥ 1.5 × the expected jump, on a common grid at
    6.15″ or the coarser of the two telescopes' pixels. Returns (fov_arcmin, pix_arcsec)."""
    from .constants import PIXEL_ARCSEC
    return max(fov_arcmin, 1.5 * expected_jump_arcmin), max(PIXEL_ARCSEC, other_pix_arcsec)
