"""FrameSource A: S3 row sections of full L2 files (implementation.md §3.4 A).

Anonymous HTTPS byte ranges against the public bucket (no s3fs, no credentials). Per frame:
  1. walk the headers (PRIMARY, IMAGE, FLAGS, VARIANCE, ZODI) with small range requests; header maps are
     immutable per key (the file name carries the pipeline version), so they are cached;
  2. map the requested sky square through the full-file WCS (SIP included) to a parent-pixel box;
  3. read whole rows y0..y1 of IMAGE, VARIANCE, ZODI (plain images, 8,160 B per row) and slice columns;
  4. FLAGS is a RICE_1 tile-compressed BINTABLE with one-row tiles in full files (✅ 11-06, F1): read
     the row descriptors, then those rows' heap bytes, and decode with astropy's RICE codec.
The origin (x0, y0) is known directly. Section headers get NAXISn and every CRPIXn<alt> shifted, so the
section follows the cutout convention (parent_origin(header) == origin) and the WCS stays exact (F2).
A full-file header is never read for CRPIXnA as if it were a cutout (implementation.md §15)."""
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import Any

import httpx
import numpy as np
from astropy.io import fits
from astropy.wcs import WCS

from ..types import FrameRef, RawFrame
from .fitsio import (WANTED, CorruptResponse, data_bytes, decode_image, extname, header_end,
                     image_header_from_compressed, is_rice_tiled, padded, parse_header, rice_decode_rows,
                     rice_rows_layout, shift_wcs_header)
from .frames import FrameBox, FrameUnavailable, SourceFailure, world_to_pixel
from .http import S3_HTTPS, HostLimiter, Timer, TransferStats
from .releases import Registry
from .retry import GaveUp, with_retry

HEADER_CHUNK = 32 * 1024


@dataclass(frozen=True)
class HDUInfo:
    name: str
    header: fits.Header
    data_offset: int
    nbytes: int


class RangeReader:
    """Validated S3 byte ranges: status 206, Content-Range and length must match the request. A 200 (the
    server ignoring Range) is refused instead of pulling a 70 MB file; a short body is truncation."""

    def __init__(self, client: httpx.AsyncClient, limiter: HostLimiter, stats: TransferStats,
                 base: str = S3_HTTPS, tries: int = 4, timeout: float = 60.0) -> None:
        self.client, self.limiter, self.stats, self.base = client, limiter, stats, base
        self.tries, self.timeout = tries, timeout

    async def _once(self, url: str, start: int, stop: int) -> bytes:
        async with self.limiter.slot(url):
            r = await self.client.get(url, headers={"Range": f"bytes={start}-{stop - 1}"}, timeout=self.timeout)
        self.stats.add(url, len(r.content))
        if r.status_code == 416:
            raise FrameUnavailable(f"range {start}-{stop} beyond end of {url}")
        if r.status_code >= 400:
            r.raise_for_status()
        if r.status_code != 206:
            raise CorruptResponse(f"expected 206 Partial Content, got {r.status_code}")
        cr = r.headers.get("Content-Range", "")
        if not cr.startswith(f"bytes {start}-"):
            raise CorruptResponse(f"Content-Range {cr!r} does not match {start}-{stop - 1}")
        total = int(cr.rsplit("/", 1)[-1]) if "/" in cr and cr.rsplit("/", 1)[-1].isdigit() else None
        want = stop - start if total is None else min(stop, total) - start
        if len(r.content) != want:
            raise EOFError(f"range body {len(r.content)} B, expected {want} B")
        return r.content

    async def get(self, key: str, start: int, stop: int) -> bytes:
        url = self.base + key
        try:
            return await with_retry(lambda: self._once(url, start, stop), tries=self.tries)
        except httpx.HTTPStatusError as e:
            if e.response.status_code in (403, 404):
                raise FrameUnavailable(f"HTTP {e.response.status_code} for {key}") from e
            raise


async def hdu_map(rr: RangeReader, key: str, wanted: tuple[str, ...] = ("PRIMARY",) + WANTED) -> dict[str, HDUInfo]:
    """Walk headers from byte 0 until every wanted HDU header is known (data is never read)."""
    out: dict[str, HDUInfo] = {}
    off = 0
    while len(out) < len(wanted):
        raw = b""
        end = None
        while end is None:
            raw += await rr.get(key, off + len(raw), off + len(raw) + HEADER_CHUNK)
            end = header_end(raw)
            if end is None and len(raw) > 100 * HEADER_CHUNK:
                raise CorruptResponse(f"no END card in {key} at {off}")
        h = parse_header(raw[:end])
        nb = data_bytes(h)
        name = extname(h)
        if name in wanted:
            out[name] = HDUInfo(name, h, off + end, nb)
        off += end + padded(nb)
    return out


def irsa_bounds(full_hdr: fits.Header, box: FrameBox, pad: int = 0) -> tuple[int, int, int, int] | None:
    """The parent-pixel box IRSA's cutout service returns for `box`: every frame pixel whose centre lies
    within c ± h on both axes, h = size / 2 / pixel scale, c the 0-based pixel of the sky centre, i.e.
    x0 = ⌈cx − h⌉ … x1 = ⌊cx + h⌋ (inclusive), clipped to the detector. Fits all 7 live cutouts seen (4
    Barnard boxes 0.031–0.1°, and the three F2 frames at 0.155°, where ⌊size/scale⌋ alone was 1 px short)
    and is re-tested by F2. IRSA's exact sizing is not public: on 3 of the F2 frames this rule was 1 px short
    on one axis (validation/F2), so `S3SectionSource` pads it by 1 px to stay a superset of the cutout box.
    The √2 rotation margin is already in `cutout_size_deg`."""
    from astropy.wcs.utils import proj_plane_pixel_scales
    w = WCS(full_hdr)
    nx, ny = int(full_hdr["NAXIS1"]), int(full_hdr["NAXIS2"])
    c = world_to_pixel(w, box.ra, box.dec, nx, ny, slack=box.size_deg * 3600 / 6.0 + 10)
    if c is None:
        return None
    cx, cy = c
    scale = float(np.mean(proj_plane_pixel_scales(w.celestial)))       # deg / pixel
    h = box.size_deg / 2 / scale
    x0, y0 = int(np.ceil(cx - h)) - pad, int(np.ceil(cy - h)) - pad
    x1, y1 = int(np.floor(cx + h)) + 1 + pad, int(np.floor(cy + h)) + 1 + pad
    x0c, y0c, x1c, y1c = max(x0, 0), max(y0, 0), min(x1, nx), min(y1, ny)
    if x0c >= x1c or y0c >= y1c:
        return None
    return x0c, x1c, y0c, y1c


def pixel_bounds(full_hdr: fits.Header, box: FrameBox, margin: int = 0) -> tuple[int, int, int, int] | None:
    """Covering parent-pixel box [x0, x1) × [y0, y1) covering the sky square, through the full-file WCS (SIP
    included). The square's edges are sampled densely (rotation and distortion at any angle; safe across
    RA = 0 and near the poles because it works in a tangent plane at the box centre)."""
    nx, ny = int(full_hdr["NAXIS1"]), int(full_hdr["NAXIS2"])
    t = WCS(naxis=2)
    t.wcs.ctype = ["RA---TAN", "DEC--TAN"]
    t.wcs.crval = [box.ra, box.dec]
    t.wcs.crpix = [1.0, 1.0]                       # FITS 1-based: 0-based (0, 0) is the box centre
    t.wcs.cdelt = [-box.size_deg / 2, box.size_deg / 2]
    s = np.linspace(-1, 1, 17)
    ex = np.r_[s, s, -np.ones_like(s), np.ones_like(s)]
    ey = np.r_[-np.ones_like(s), np.ones_like(s), s, s]
    ra, dec = t.wcs_pix2world(ex, ey, 0)
    w = WCS(full_hdr)
    if world_to_pixel(w, box.ra, box.dec, nx, ny, slack=box.size_deg * 3600 / 6.0 + 10) is None:
        return None
    with np.errstate(invalid="ignore"):
        px, py = w.all_world2pix(ra, dec, 0, quiet=True)
    if not (np.isfinite(px).all() and np.isfinite(py).all()):
        return None
    x0 = max(int(np.floor(px.min() + 0.5)) - margin, 0)
    x1 = min(int(np.floor(px.max() + 0.5)) + margin + 1, nx)
    y0 = max(int(np.floor(py.min() + 0.5)) - margin, 0)
    y1 = min(int(np.floor(py.max() + 0.5)) + margin + 1, ny)
    if x0 >= x1 or y0 >= y1:
        return None
    return x0, x1, y0, y1


class S3SectionSource:
    name = "s3-section"

    def __init__(self, client: httpx.AsyncClient, limiter: HostLimiter | None = None,
                 registry: Registry | None = None, stats: TransferStats | None = None, tries: int = 4,
                 margin: int = 0, bounds: str = "irsa") -> None:
        """bounds="irsa": IRSA's cutout box rule padded by 1 px, a superset of what the cutout service
        returns (validation/F2), so failover never loses pixels; "cover": every pixel touching the
        rotated square, plus `margin`."""
        self.stats = stats or TransferStats()
        self.rr = RangeReader(client, limiter or HostLimiter(), self.stats, tries=tries)
        self.registry, self.margin, self.bounds = registry, margin, bounds
        self._maps: dict[str, dict[str, HDUInfo]] = {}
        self.last_timing: dict[str, float] = {}

    async def headers(self, key: str) -> dict[str, HDUInfo]:
        if key not in self._maps:
            self._maps[key] = await hdu_map(self.rr, key)
        return self._maps[key]

    async def _rows(self, key: str, info: HDUInfo, y0: int, y1: int, x0: int, x1: int) -> tuple[fits.Header, Any]:
        h = info.header
        if is_rice_tiled(h):
            nx, heap = rice_rows_layout(h)
            desc = np.frombuffer(await self.rr.get(key, info.data_offset + 8 * y0, info.data_offset + 8 * y1),
                                 ">i4").reshape(-1, 2).astype(np.int64)
            lo, hi = int(desc[:, 1].min()), int((desc[:, 1] + desc[:, 0]).max())
            blob = await self.rr.get(key, info.data_offset + heap + lo, info.data_offset + heap + hi)
            rows = rice_decode_rows(h, desc, blob, lo)
            return image_header_from_compressed(h), rows[:, x0:x1]
        nx = int(h["NAXIS1"])
        bpp = abs(int(h["BITPIX"])) // 8
        raw = await self.rr.get(key, info.data_offset + y0 * nx * bpp, info.data_offset + y1 * nx * bpp)
        sub = h.copy()
        sub["NAXIS2"] = y1 - y0
        return h, decode_image(sub, raw)[:, x0:x1]

    async def fetch_pixels(self, ref: FrameRef, x0: int, x1: int, y0: int, y1: int) -> RawFrame:
        """Parent pixels [x0, x1) × [y0, y1) of one full file (used by F2 to read exactly a cutout's box)."""
        t = Timer()
        b0 = self.stats.bytes
        try:
            m = await self.headers(ref.s3_key)
            parts = await asyncio.gather(*(self._rows(ref.s3_key, m[n], y0, y1, x0, x1) for n in WANTED))
        except GaveUp as e:
            raise SourceFailure(f"{self.name}: {e}") from e
        hdus: dict[str, tuple[fits.Header, Any]] = {}
        for n, (h, a) in zip(WANTED, parts):
            hdus[n] = (shift_wcs_header(h, x0, y0, x1 - x0, y1 - y0), a)
        hdus["PRIMARY"] = (m["PRIMARY"].header, np.zeros(0))
        hi = hdus["IMAGE"][0]
        rel = self.registry.release_for_collection(ref.collection) if self.registry else None
        self.last_timing = {"total_s": t.elapsed, "bytes": self.stats.bytes - b0}
        return RawFrame(hdus=hdus, wcs=WCS(hi), origin=(x0, y0), ref=ref,
                        release=rel.id if rel else ref.collection.removeprefix("spherex_").removesuffix("_deep"))

    async def fetch(self, ref: FrameRef, box: FrameBox) -> RawFrame:
        t0 = time.perf_counter()
        try:
            m = await self.headers(ref.s3_key)
        except GaveUp as e:
            raise SourceFailure(f"{self.name}: {e}") from e
        hi = m["IMAGE"].header
        b = irsa_bounds(hi, box, pad=1) if self.bounds == "irsa" else pixel_bounds(hi, box, self.margin)
        if b is None:
            raise FrameUnavailable(f"box {box.key()} misses {ref.id}")
        x0, x1, y0, y1 = b
        frame = await self.fetch_pixels(ref, x0, x1, y0, y1)
        self.last_timing["wall_s"] = time.perf_counter() - t0
        return frame
