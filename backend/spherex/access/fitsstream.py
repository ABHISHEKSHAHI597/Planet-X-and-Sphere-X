"""FrameSource B: IRSA cutouts, streamed and aborted after ZODI (implementation.md §3.4 B).

Every cutout carries the ≈3.9 MB ePSF extension even when it is 29×29 pixels; everything we need ends
at byte 89,280 of that cutout (✅ 11-06), so the stream is closed as soon as ZODI has arrived. QR3's
`EPSF` and QR2's `PSF` sit after ZODI, so the abort is release-independent. Truncation (a stream that
ends early after HTTP 200, ✅ 11-06) raises EOFError and is retried; a non-FITS body raises
CorruptResponse and is retried; HTTP 4xx means the box is off this frame."""
from __future__ import annotations

import time
from collections.abc import AsyncIterator
from typing import Any

import httpx
import numpy as np
from astropy.io import fits
from astropy.wcs import WCS

from ..calib import parent_origin
from ..types import FrameRef, RawFrame
from .fitsio import BLOCK, WANTED, CorruptResponse, data_bytes, decode_hdu, extname, padded, parse_header
from .frames import FrameBox, FrameUnavailable, SourceFailure
from .http import HostLimiter, Timer, TransferStats
from .releases import Registry
from .retry import GaveUp, with_retry


class _Reader:
    def __init__(self, chunks: AsyncIterator[bytes], timer: Timer | None = None) -> None:
        self._it, self._buf, self.nread, self._timer = chunks, bytearray(), 0, timer

    async def take(self, n: int) -> bytes:
        while len(self._buf) < n:
            chunk = await anext(self._it, None)
            if chunk is None:
                raise EOFError(f"stream ended early after {self.nread + len(self._buf)} bytes")
            if self._timer:
                self._timer.first_byte()
            self._buf += chunk
        out = bytes(self._buf[:n])
        del self._buf[:n]
        self.nread += n
        return out


async def _read_header(rd: _Reader) -> fits.Header:
    raw = b""
    while True:
        blk = await rd.take(BLOCK)
        if not raw and not (blk.startswith(b"SIMPLE  =") or blk.startswith(b"XTENSION=")):
            raise CorruptResponse(f"not FITS: {blk[:60]!r}")
        raw += blk
        if any(blk[i:i + 8] == b"END     " for i in range(0, BLOCK, 80)):
            return parse_header(raw)
        if len(raw) > 200 * BLOCK:
            raise CorruptResponse("FITS header without END")


async def read_hdus(chunks: AsyncIterator[bytes], wanted: tuple[str, ...] = WANTED,
                    timer: Timer | None = None) -> tuple[dict[str, tuple[fits.Header, np.ndarray[Any, Any]]],
                                                         fits.Header, int]:
    """Parse a FITS byte stream until every wanted HDU has arrived. Returns (hdus, primary, bytes read)."""
    rd = _Reader(chunks, timer)
    out: dict[str, tuple[fits.Header, np.ndarray[Any, Any]]] = {}
    primary: fits.Header | None = None
    while len(out) < len(wanted):
        h = await _read_header(rd)
        nbytes = data_bytes(h)
        raw = await rd.take(padded(nbytes)) if nbytes else b""
        name = extname(h)
        if primary is None:
            primary = h
        if name in wanted:
            out[name] = decode_hdu(h, raw[:nbytes])
    assert primary is not None
    return out, primary, rd.nread


def cutout_url(access_url: str, box: FrameBox) -> str:
    return f"{access_url}?center={box.ra:.7f},{box.dec:.7f}deg&size={box.size_deg:.5f}"   # size in deg ✅


class IrsaCutoutSource:
    name = "irsa-cutout"

    def __init__(self, client: httpx.AsyncClient, limiter: HostLimiter | None = None,
                 registry: Registry | None = None, tries: int = 4, stats: TransferStats | None = None,
                 timeout: float = 90.0) -> None:
        self.client, self.limiter, self.registry = client, limiter or HostLimiter(), registry
        self.tries, self.stats, self.timeout = tries, stats or TransferStats(), timeout
        self.last_timing: dict[str, float] = {}

    async def _once(self, url: str) -> tuple[dict[str, tuple[fits.Header, np.ndarray[Any, Any]]], fits.Header, int]:
        timer = Timer()
        async with self.limiter.slot(url):
            async with self.client.stream("GET", url, timeout=self.timeout) as resp:
                if resp.status_code >= 400:
                    resp.raise_for_status()
                try:
                    hdus, primary, n = await read_hdus(resp.aiter_bytes(), timer=timer)
                finally:
                    self.stats.add(url, getattr(resp, "num_bytes_downloaded", 0))
        self.last_timing = {"ttfb_s": timer.ttfb or timer.elapsed, "total_s": timer.elapsed, "bytes": n}
        return hdus, primary, n
        # leaving the context closes the connection before EPSF is transferred

    async def fetch(self, ref: FrameRef, box: FrameBox) -> RawFrame:
        url = cutout_url(ref.access_url, box)
        t0 = time.perf_counter()
        try:
            hdus, primary, _ = await with_retry(lambda: self._once(url), tries=self.tries,
                                                on_error=lambda k, e: setattr(self.stats, "failures",
                                                                              self.stats.failures + 1))
        except httpx.HTTPStatusError as e:
            raise FrameUnavailable(f"HTTP {e.response.status_code} for {ref.id}") from e
        except GaveUp as e:
            raise SourceFailure(f"{self.name}: {e}") from e
        hi = hdus["IMAGE"][0]
        rel = self.registry.release_for_collection(ref.collection) if self.registry else None
        frame = RawFrame(hdus=hdus, wcs=WCS(hi), origin=parent_origin(hi), ref=ref,
                         release=rel.id if rel else _release_guess(ref.collection))
        frame.hdus = dict(hdus, PRIMARY=(primary, np.zeros(0)))   # VERSION lives in PRIMARY
        self.last_timing["wall_s"] = time.perf_counter() - t0
        return frame


def _release_guess(collection: str) -> str:
    return collection.removeprefix("spherex_").removesuffix("_deep")
