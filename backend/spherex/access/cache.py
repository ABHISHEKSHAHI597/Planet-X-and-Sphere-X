"""Caches (implementation.md §3.7, §2.3).

* Frames: forever, content-addressed by sha1(access url) + snapped box. Frames are immutable because the
  file name carries the pipeline version, so a cached frame never goes stale.
* Coverage: 24 h, or until `release_state` (release watcher) moves, whichever comes first.
* Pins are never cached here and never invalidated: a pinned view reads its frame list from
  config/pins/<pin>.json (pins.py), so coverage invalidation can't change it (workflow.md §8.3)."""
from __future__ import annotations

import hashlib
import json
import os
import threading
import time
from pathlib import Path
from typing import Any

import numpy as np
from astropy.io import fits
from astropy.wcs import WCS

from ..types import FrameRef, RawFrame
from .frames import FrameBox

COVERAGE_TTL_S = 24 * 3600
STALE_NEAR_DEG = 1.0 / 60     # a stale coverage entry this close stands in for the query when IRSA is down
_HDUS = ("IMAGE", "FLAGS", "VARIANCE", "ZODI")


def frame_key(access_url: str, box: FrameBox) -> str:
    return hashlib.sha1(access_url.encode()).hexdigest() + "_" + hashlib.sha1(box.key().encode()).hexdigest()[:12]


def _atomic_write(p: Path, data: bytes) -> None:
    tmp = p.with_name(p.name + f".tmp{os.getpid()}.{threading.get_ident()}")
    tmp.write_bytes(data)
    tmp.replace(p)


def _parse_key(key: str) -> tuple[float, float, str, str] | None:
    """A coverage key "ra,dec,radius,coll|coll" (CoverageClient.coverage) → (ra, dec, radius text, collections)."""
    try:
        ra, dec, rad, colls = key.split(",", 3)
        return float(ra), float(dec), rad, colls
    except ValueError:
        return None


def _sep_deg(ra1: float, dec1: float, ra2: float, dec2: float) -> float:
    r1, d1, r2, d2 = map(np.radians, (ra1, dec1, ra2, dec2))
    c = np.sin(d1) * np.sin(d2) + np.cos(d1) * np.cos(d2) * np.cos(r1 - r2)
    return float(np.degrees(np.arccos(np.clip(c, -1.0, 1.0))))


class FrameCache:
    def __init__(self, root: Path | str) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.hits = self.misses = 0

    def _paths(self, key: str) -> tuple[Path, Path]:
        d = self.root / key[:2]
        d.mkdir(exist_ok=True)
        return d / f"{key}.fits", d / f"{key}.json"

    def contains(self, ref: FrameRef, box: FrameBox) -> bool:
        """Whether get() would hit: two stat calls, no parsing."""
        key = frame_key(ref.access_url, box)
        d = self.root / key[:2]
        return (d / f"{key}.fits").exists() and (d / f"{key}.json").exists()

    def get(self, ref: FrameRef, box: FrameBox) -> RawFrame | None:
        fp, mp = self._paths(frame_key(ref.access_url, box))
        if not (fp.exists() and mp.exists()):
            self.misses += 1
            return None
        try:
            meta = json.loads(mp.read_text())
            with fits.open(fp, memmap=False) as hl:
                hdus: dict[str, tuple[fits.Header, Any]] = {
                    n: (hl[n].header.copy(), np.array(hl[n].data)) for n in _HDUS}
                hdus["PRIMARY"] = (hl[0].header.copy(), np.zeros(0))
            frame = RawFrame(hdus=hdus, wcs=WCS(hdus["IMAGE"][0]), origin=tuple(meta["origin"]),
                             ref=ref, release=meta["release"])
        except Exception:               # truncated or corrupt entry (crash mid-write, full disk): re-fetch it
            self.misses += 1
            return None
        try:
            os.utime(fp)                # "recently used" for the cache budget (app/cachegc.py)
        except OSError:
            pass
        self.hits += 1
        return frame

    def put(self, ref: FrameRef, box: FrameBox, frame: RawFrame, source: str = "") -> None:
        fp, mp = self._paths(frame_key(ref.access_url, box))
        prim = frame.hdus.get("PRIMARY", (fits.Header(), None))[0]
        hl = fits.HDUList([fits.PrimaryHDU(header=prim)])
        for n in _HDUS:
            h, a = frame.hdus[n]
            hdr = fits.Header([c for c in h.cards if c.keyword not in
                               ("XTENSION", "BITPIX", "NAXIS", "NAXIS1", "NAXIS2", "PCOUNT", "GCOUNT", "EXTEND")])
            hl.append(fits.ImageHDU(data=np.asarray(a), header=hdr, name=n))
        import io
        buf = io.BytesIO()
        hl.writeto(buf, output_verify="silentfix")
        _atomic_write(fp, buf.getvalue())
        _atomic_write(mp, json.dumps({"origin": list(frame.origin), "release": frame.release, "source": source,
                                      "access_url": ref.access_url, "box": box.key(), "t": time.time()}).encode())


class CoverageCache:
    def __init__(self, root: Path | str, ttl_s: float = COVERAGE_TTL_S, clock: Any = time.time) -> None:
        self.root, self.ttl, self.clock = Path(root), ttl_s, clock
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        return self.root / (hashlib.sha256(key.encode()).hexdigest()[:32] + ".json")

    def get(self, key: str, release_state: str) -> list[dict[str, Any]] | None:
        p = self._path(key)
        if not p.exists():
            return None
        try:
            d = json.loads(p.read_text())
        except (OSError, ValueError):          # truncated or corrupt entry: a miss, never an error (audit K-37)
            return None
        if d.get("release_state") != release_state or self.clock() - d["t"] > self.ttl:
            return None
        return d["rows"]  # type: ignore[no-any-return]

    def get_stale(self, key: str, near_deg: float = STALE_NEAR_DEG) -> tuple[list[dict[str, Any]], float] | None:
        """(rows, saved_at) of the newest entry for this query, or for the same radius and collections within
        `near_deg` of it, whatever its age or release state. Only for when the archive is not answering: a
        moving star's position (and so its key) shifts a little every day, and a SPHEREx detector is ≈3.5° wide,
        so last week's frame list for a point a few arcseconds away is the same list minus the newest frames."""
        p = self._path(key)
        try:
            d = json.loads(p.read_text())
            return d["rows"], float(d["t"])
        except (OSError, ValueError, KeyError, TypeError):
            pass
        want = _parse_key(key)
        if want is None:
            return None
        ra0, dec0, rad0, colls0 = want
        best: tuple[float, list[dict[str, Any]], float] | None = None
        for q in self.root.glob("*.json"):
            try:
                d = json.loads(q.read_text())
                got = _parse_key(d["key"])
                if got is None or got[2] != rad0 or got[3] != colls0:
                    continue
                sep = _sep_deg(ra0, dec0, got[0], got[1])
                if sep <= near_deg and (best is None or sep < best[0]):
                    best = (sep, d["rows"], float(d["t"]))
            except (OSError, ValueError, KeyError, TypeError):
                continue
        return None if best is None else (best[1], best[2])

    def put(self, key: str, rows: list[dict[str, Any]], release_state: str) -> None:
        _atomic_write(self._path(key), json.dumps({"key": key, "t": self.clock(), "release_state": release_state,
                                                   "rows": rows}).encode())

    def invalidate_all(self) -> int:
        n = 0
        for p in self.root.glob("*.json"):
            p.unlink()
            n += 1
        return n
