"""One pixel window per (frame, box), whichever source served the frame (decision record 0009).

IRSA cutouts and S3 sections of the same frame and box differ by a ring of up to 1 px: S3 reads IRSA's box rule
padded by 1 px (s3sections.irsa_bounds, because IRSA's exact sizing is not public and is sometimes 1 px short), and
frame-level statistics in the stack (the sky level) see that ring. Measured on Barnard D6: every stack pixel moved,
p99 |Δ| ≈ 1 % of the median level. So a stack's bytes depended on which source served each frame. With the pooled
source, which mixes them on every build, or after a failover, two cold builds of a pinned view then disagree (G2-repro).

`canonical_crop` cuts every frame to IRSA's rule shrunk by 1 px: inside what IRSA returns (at most 1 px short of the
rule) and inside the S3 section (the rule plus 1 px). The size includes the rotation margin and 4 px more on each
side (frames.cutout_size_deg), so the stack grid stays covered."""
from __future__ import annotations

import math
from dataclasses import replace
from typing import Any

import numpy as np

from ..types import RawFrame
from .fitsio import shift_wcs_header
from .frames import FrameBox, world_to_pixel

DETECTOR_PX = 2040


def canonical_bounds(frame: RawFrame, box: FrameBox) -> tuple[int, int, int, int] | None:
    """Parent-pixel window [x0, x1) × [y0, y1): IRSA's rule for `box` shrunk by 1 px, clipped to the detector and to
    the pixels the frame has. None if the box centre is far off the frame."""
    from astropy.wcs.utils import proj_plane_pixel_scales

    ox, oy = frame.origin
    ny, nx = np.shape(frame.hdus["IMAGE"][1])
    c = world_to_pixel(frame.wcs, box.ra, box.dec, nx, ny, slack=box.size_deg * 3600 / 6.0 + 10)
    if c is None:
        return None
    cx, cy = c[0] + ox, c[1] + oy
    h = box.size_deg / 2 / float(np.mean(proj_plane_pixel_scales(frame.wcs.celestial)))
    x0 = max(math.ceil(cx - h) + 1, 0, ox)
    y0 = max(math.ceil(cy - h) + 1, 0, oy)
    x1 = min(math.floor(cx + h), DETECTOR_PX, ox + nx)
    y1 = min(math.floor(cy + h), DETECTOR_PX, oy + ny)
    if x0 >= x1 or y0 >= y1:
        return None
    return x0, x1, y0, y1


def _shift_in_place(h: Any, dx: int, dy: int, nx: int, ny: int) -> Any:
    """fitsio.shift_wcs_header without the copy: a header copy is ≈ 3 ms of Python per HDU, 4 HDUs per frame."""
    h["NAXIS1"], h["NAXIS2"] = nx, ny
    for key in [k for k in h.keys() if k.startswith("CRPIX")]:
        if key.startswith("CRPIX1"):
            h[key] = float(h[key]) - dx
        elif key.startswith("CRPIX2"):
            h[key] = float(h[key]) - dy
    return h


def canonical_crop(frame: RawFrame, box: FrameBox, in_place: bool = False) -> RawFrame:
    """The frame cut to canonical_bounds (every 2-D HDU, its headers' CRPIX and the WCS shifted alike); the frame
    itself when it already has that window or the box misses it. in_place=True edits the frame's headers instead of
    copying them, for a caller that owns the frame (fetch_frames: every source returns a newly built frame)."""
    b = canonical_bounds(frame, box)
    if b is None:
        return frame
    x0, x1, y0, y1 = b
    ox, oy = frame.origin
    ny, nx = np.shape(frame.hdus["IMAGE"][1])
    if (x0, x1, y0, y1) == (ox, ox + nx, oy, oy + ny):
        return frame
    dx, dy = x0 - ox, y0 - oy
    sl = np.s_[dy : dy + (y1 - y0), dx : dx + (x1 - x0)]
    hdus: dict[str, tuple[Any, Any]] = {}
    for name, (hdr, a) in frame.hdus.items():
        if np.ndim(a) == 2 and np.shape(a) == (ny, nx):
            h2 = (_shift_in_place if in_place else shift_wcs_header)(hdr, dx, dy, x1 - x0, y1 - y0)
            hdus[name] = (h2, np.ascontiguousarray(a[sl]))
        else:
            hdus[name] = (hdr, a)
    return replace(frame, hdus=hdus, wcs=frame.wcs[sl], origin=(x0, y0))
