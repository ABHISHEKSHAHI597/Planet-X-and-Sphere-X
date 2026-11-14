"""The common, typed FrameSource interface (implementation.md §3.4).

Every source returns `types.RawFrame(hdus, wcs, origin, ref, release)`: `hdus` holds IMAGE, FLAGS,
VARIANCE and ZODI as (header, data), `origin` is the 0-based parent-detector pixel of the frame's pixel
(0, 0), supplied by the source itself (cutout: CRPIXnA; S3 section: known directly). Requests are sized
for rotation and snapped so nearby views reuse cached frames."""
from __future__ import annotations

import math
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from ..types import FrameRef, RawFrame

PIX_ARCSEC = 6.15
# 32′ (audit B-06): a 25–30′ view used to fetch the 48′ box, 3.7× the pixels it needs.
SIZE_PRESETS_ARCMIN = (3.0, 6.0, 12.0, 24.0, 32.0, 48.0)
SNAP_ARCSEC = 30.0


# Which source served the frame fetched in *this* task. Task-local (asyncio copies the context per task), so
# concurrent fetches never see each other's value, unlike an attribute on a shared source object.
SERVED_BY: ContextVar[str | None] = ContextVar("served_by", default=None)


class FrameUnavailable(Exception):
    """The request can't be served by this frame (off the detector, HTTP 4xx). Not retryable and not a
    source failure: it doesn't count toward failover."""


class SourceFailure(Exception):
    """A source failed after its retries (5xx, throttling, truncation, transport). Counts toward
    failover; the frame is reported as skipped if every source fails."""


@dataclass(frozen=True)
class FrameBox:
    """A square sky region: centre (deg, ICRS) and full side length (deg). Cutout semantics: the source
    returns every frame pixel it can within the square, at the frame's own orientation."""
    ra: float
    dec: float
    size_deg: float

    def key(self) -> str:
        return f"{self.ra:.5f},{self.dec:.5f},{self.size_deg:.5f}"


def cutout_size_deg(fov_arcmin: float, margin_px: float = 4, pix_arcsec: float = PIX_ARCSEC) -> float:
    """Square cutout that covers a north-up display square at any rotation, plus a few pixels for
    interpolation and PSF wings: FOV × √2 + 2 × margin."""
    return (fov_arcmin * 2 ** 0.5 + 2 * margin_px * pix_arcsec / 60) / 60


def snap_box(ra: float, dec: float, fov_arcmin: float) -> FrameBox:
    """Centre snapped to a 30″ grid (RA steps scaled by cos δ), size rounded up to the next preset
    (3′, 6′, 12′, 24′, 32′, 48′) plus 30″ for the snapping, then grown for rotation. Small pans and nearby
    views then hit the same cached frames (implementation.md §3.4)."""
    step = SNAP_ARCSEC / 3600
    dec_s = round(dec / step) * step
    cosd = max(math.cos(math.radians(dec_s)), 1e-6)
    ra_step = step / cosd
    ra_s = (round(ra / ra_step) * ra_step) % 360.0
    preset = next((p for p in SIZE_PRESETS_ARCMIN if p >= fov_arcmin), fov_arcmin)
    return FrameBox(ra_s, dec_s, cutout_size_deg(preset + SNAP_ARCSEC / 60))


@runtime_checkable
class FrameSource(Protocol):
    name: str

    async def fetch(self, ref: FrameRef, box: FrameBox) -> RawFrame:
        """Raise FrameUnavailable when the box misses the frame, SourceFailure after retries."""
        ...


@dataclass
class FetchOutcome:
    """One frame's fate, for the manifest: never drop failed frames silently (workflow.md §11.2)."""
    ref: FrameRef
    frame: RawFrame | None
    source: str | None
    skipped_reason: str | None = None
    bytes: int = 0
    seconds: float = 0.0


def world_to_pixel(wcs: object, ra: float, dec: float, nx: int, ny: int, slack: float = 200.0) -> tuple[float, float] | None:
    """0-based frame pixel of (ra, dec), or None when it is far off the frame. The linear (no-SIP) TAN
    solution screens first, because the iterative SIP inverse diverges for points far outside the
    detector (seen for a box 100° away); points near the frame then get the exact SIP solution."""
    import numpy as np
    with np.errstate(all="ignore"):
        lx, ly = (float(v) for v in wcs.wcs_world2pix(ra, dec, 0))      # type: ignore[attr-defined]
        if not (np.isfinite(lx) and np.isfinite(ly)) or not (-slack <= lx < nx + slack and -slack <= ly < ny + slack):
            return None
        x, y = (float(v) for v in wcs.all_world2pix(ra, dec, 0, quiet=True))   # type: ignore[attr-defined]
    if not (np.isfinite(x) and np.isfinite(y)):
        return None
    return x, y
