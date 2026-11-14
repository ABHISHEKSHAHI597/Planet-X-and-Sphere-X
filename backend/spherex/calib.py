"""Calibration: discovery, lock, bootstrap, verified loading and parent-pixel lookups
(implementation.md §3.5, workflow.md §8.4). Owner D.

* Discovery lists the bucket, because the documented directory names are wrong (`cal-wcs` is really
  `cal-swcs-v5-2026-191`). Per product and detector the newest version directory wins
  (`cal-<code>-v<N>-<yyyy>-<ddd>`, compared numerically), so D3's extra ePSF `v2` is picked for D3 only.
* config/calibration.lock freezes the result: S3 key, version directory, size, S3 ETag (the MD5 of these
  single-part uploads) and sha256. Changing it is a reviewed PR (D; reviewers I and M) and re-runs F1,
  F3, F4, F5, F13. Its `lock_hash` is what every evidence record cites.
* Bootstrap downloads each locked file once (resumable), checks MD5 against the ETag and sha256 against
  the lock; a mismatch is fatal. `Calib` then memory-maps the verified files.

`parent_origin` / `parent_slice` keep their signatures (the pixel pipeline imports them)."""

from __future__ import annotations

import asyncio
import datetime
import hashlib
import json
import os
import re
from collections.abc import Iterator, Mapping
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

REPO = Path(__file__).resolve().parents[2]
LOCK_PATH = REPO / "config" / "calibration.lock"
LOCK_SCHEMA = "parallax-calibration-lock@1"
# product → (per-detector?, what it is for). These are the products the science code reads.
PRODUCTS: dict[str, tuple[bool, str]] = {
    "spectral_wcs": (True, "CWAVE/CBAND per-pixel λ, Δλ (F1)"),
    "spectral_channels": (False, "CHANNEL_MAP (HDU 1, all detectors) + SPECTRAL_CHANNELS table (F3)"),
    "epsf": (True, "ePSF zones (F5, owner M)"),
    "l3_flux_corrections": (True, "QR2 → QR3 gain factors (F4, owner M)"),
    "solid_angle_pixel_map": (True, "pixel solid angle (F13, owner M)"),
}
_VDIR = re.compile(r"(?:cal-[a-z]+-v(?P<v>\d+)|base)-(?P<y>\d{4})-(?P<d>\d{3})")
_DET = re.compile(r"_D(?P<det>[1-6])_")


# --------------------------------------------------------------------------- parent-pixel helpers
def parent_origin(img_hdr: Any) -> tuple[int, int]:
    """IRSA cutouts only: 0-based parent-detector pixel of cutout pixel (0,0).
    IRSA: x_orig = 1 + x_cut - CRPIX1A (x_cut 0-based). Example: CRPIX1A=-642 → x0=643.
    S3 sections already know their origin, and a full-file header must NOT be read this way
    (full files have CRPIXnA = 1, i.e. origin (0, 0), which is only right for the whole detector).
    Section headers written by access/s3sections.py shift CRPIXnA, so they follow this rule too (F2)."""
    return int(round(1 - img_hdr["CRPIX1A"])), int(round(1 - img_hdr["CRPIX2A"]))


def parent_slice(origin: tuple[int, int], shape: tuple[int, ...]) -> tuple[slice, slice]:
    (x0, y0), (ny, nx) = origin, shape
    return np.s_[y0 : y0 + ny, x0 : x0 + nx]


# --------------------------------------------------------------------------- lock
@dataclass
class LockEntry:
    product: str
    detector: int | None
    s3_key: str
    version_dir: str
    size: int
    etag_md5: str
    sha256: str | None = None

    @property
    def filename(self) -> str:
        return self.s3_key.rsplit("/", 1)[-1]


@dataclass
class CalibrationLock:
    release: str
    entries: list[LockEntry]
    listed: str = ""
    notes: list[str] = field(default_factory=list)

    @property
    def complete(self) -> bool:
        return all(e.sha256 for e in self.entries)

    def lock_hash(self) -> str:
        """sha256 over the canonical (key, size, md5, sha256) list: cite it in evidence records."""
        canon = json.dumps(
            [[e.s3_key, e.size, e.etag_md5, e.sha256] for e in sorted(self.entries, key=lambda e: e.s3_key)],
            separators=(",", ":"),
        )
        return hashlib.sha256(canon.encode()).hexdigest()[:16]

    def get(self, product: str, detector: int | None = None) -> LockEntry:
        for e in self.entries:
            if e.product == product and e.detector == detector:
                return e
        raise KeyError((product, detector))

    def to_json(self) -> str:
        return (
            json.dumps(
                dict(
                    schema=LOCK_SCHEMA,
                    release=self.release,
                    listed=self.listed,
                    lock_hash=self.lock_hash(),
                    complete=self.complete,
                    notes=self.notes,
                    files=[asdict(e) for e in sorted(self.entries, key=lambda e: (e.product, e.detector or 0))],
                ),
                indent=1,
            )
            + "\n"
        )

    @classmethod
    def from_json(cls, text: str) -> CalibrationLock:
        d = json.loads(text)
        if d.get("schema") != LOCK_SCHEMA:
            raise ValueError(f"not a calibration lock: {d.get('schema')!r}")
        lock = cls(d["release"], [LockEntry(**e) for e in d["files"]], d.get("listed", ""), d.get("notes", []))
        if d.get("lock_hash") and d["lock_hash"] != lock.lock_hash():
            raise ValueError("calibration.lock: lock_hash does not match its entries (edited by hand?)")
        return lock

    def save(self, path: Path = LOCK_PATH) -> None:
        path.write_text(self.to_json())

    @classmethod
    def load(cls, path: Path = LOCK_PATH) -> CalibrationLock:
        return cls.from_json(path.read_text())


def version_key(vdir: str) -> tuple[int, int, int]:
    m = _VDIR.search(vdir)
    if m is None:
        raise ValueError(f"unrecognised calibration version directory {vdir!r}")
    return int(m["v"] or 0), int(m["y"]), int(m["d"])


def select_files(product: str, objects: list[tuple[str, int, str]], release: str) -> list[LockEntry]:
    """objects: (key, size, etag) under <release>/<product>/. Newest version directory per detector
    (or overall for single-file products); FITS only."""
    per_det, _ = PRODUCTS[product]
    best: dict[int | None, tuple[tuple[int, int, int], LockEntry]] = {}
    for key, size, etag in objects:
        if not key.endswith(".fits"):
            continue
        parts = key.split("/")
        if len(parts) < 4 or parts[0] != release.rstrip("/") or parts[1] != product:
            continue
        vdir = parts[2]
        det: int | None = None
        if per_det:
            m = _DET.search(parts[-1])
            if m is None:
                continue
            det = int(m["det"])
        e = LockEntry(product, det, key, vdir, int(size), etag.strip('"'))
        k = version_key(vdir)
        if det not in best or k > best[det][0]:
            best[det] = (k, e)
    if per_det and sorted(d for d in best if d is not None) != [1, 2, 3, 4, 5, 6]:
        raise ValueError(f"{product}: detectors found {sorted(d for d in best if d is not None)}; expected 1–6")
    if not best:
        raise ValueError(f"{product}: no FITS files found")
    return [v[1] for _, v in sorted(best.items(), key=lambda kv: kv[0] or 0)]


async def discover(client: Any, release: str = "qr3", products: Mapping[str, Any] = PRODUCTS) -> CalibrationLock:
    """List the bucket and select the calibration files (no data download)."""
    from .access.s3list import list_s3

    entries: list[LockEntry] = []
    notes = []
    for prod in products:
        lst = await list_s3(client, f"{release}/{prod}/", None)
        objs = [(o.key, o.size, o.etag) for o in lst.objects]
        sel = select_files(prod, objs, release)
        vdirs = sorted({o[0].split("/")[2] for o in objs})
        if len(vdirs) > 1:
            notes.append(
                f"{prod}: version dirs {vdirs}; newest per detector selected "
                f"({', '.join(f'D{e.detector}={e.version_dir}' for e in sel if e.detector)})"
            )
        entries += sel
    return CalibrationLock(release, entries, datetime.datetime.now(datetime.UTC).isoformat(timespec="seconds"), notes)


# --------------------------------------------------------------------------- bootstrap
def file_digests(path: Path) -> tuple[str, str]:
    md5, sha = hashlib.md5(), hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            md5.update(chunk)
            sha.update(chunk)
    return md5.hexdigest(), sha.hexdigest()


class CalibIntegrityError(RuntimeError):
    pass


async def download(client: Any, key: str, dest: Path, size: int, chunk: int = 4 << 20) -> None:
    """Resumable ranged download into dest (via dest.part)."""
    from .access.http import S3_HTTPS
    from .access.retry import with_retry

    part = dest.with_name(dest.name + ".part")
    dest.parent.mkdir(parents=True, exist_ok=True)
    have = part.stat().st_size if part.exists() else 0
    with open(part, "ab") as f:
        while have < size:
            stop = min(have + chunk, size)

            async def once(a: int = have, b: int = stop) -> bytes:
                r = await client.get(S3_HTTPS + key, headers={"Range": f"bytes={a}-{b - 1}"}, timeout=300)
                r.raise_for_status()
                if r.status_code != 206 or len(r.content) != b - a:
                    raise EOFError(f"short range {len(r.content)} != {b - a}")
                return bytes(r.content)

            f.write(await with_retry(once, tries=6))
            f.flush()
            have = stop
    part.replace(dest)


async def bootstrap(
    client: Any, lock: CalibrationLock, root: Path, freeze: bool = False, progress: Any = None
) -> CalibrationLock:
    """Download and verify every locked file. MD5 must equal the S3 ETag. If the lock already has a
    sha256 it must match; with freeze=True a missing sha256 is filled in (creating the lock)."""
    for e in lock.entries:
        dest = root / e.s3_key
        if not dest.exists() or dest.stat().st_size != e.size:
            await download(client, e.s3_key, dest, e.size)
        md5, sha = await asyncio.to_thread(file_digests, dest)
        if md5 != e.etag_md5:
            dest.unlink()
            raise CalibIntegrityError(f"{e.s3_key}: md5 {md5} != ETag {e.etag_md5}")
        if e.sha256 and e.sha256 != sha:
            raise CalibIntegrityError(f"{e.s3_key}: sha256 {sha} != lock {e.sha256}")
        if not e.sha256:
            if not freeze:
                raise CalibIntegrityError(f"{e.s3_key}: lock has no sha256 (run bootstrap --freeze in a lock PR)")
            e.sha256 = sha
        if progress:
            progress(e)
    return lock


# --------------------------------------------------------------------------- loader
class _LazyMaps(Mapping[int, Any]):
    def __init__(self, loader: Any) -> None:
        self._load = loader
        self._cache: dict[int, Any] = {}

    def __getitem__(self, det: int) -> Any:
        if det not in self._cache:
            self._cache[det] = self._load(int(det))
        return self._cache[det]

    def __iter__(self) -> Iterator[int]:
        return iter(range(1, 7))

    def __len__(self) -> int:
        return 6


class Calib:
    """types.Calib, backed by the locked, verified files under `root` (memory-mapped, loaded lazily per
    detector). cwave/cband: spectral_wcs CWAVE/CBAND (µm, DETCOORD='sky' like IMAGE, F1). channel:
    CHANNEL_MAP (F3). fluxcorr: the l3_flux_corrections `IMAGE` HDU (HDU names of every locked file are in
    tests/data/real/calib_headers.json); whether it multiplies or divides QR2 fluxes
    is F4 (owner M), so it is exposed raw. solid_angle: the pixel solid-angle map (F13, owner M)."""

    def __init__(self, root: Path | str, lock: CalibrationLock | None = None, verify: bool = True) -> None:
        self.root = Path(root)
        self.lock = lock or CalibrationLock.load()
        if verify:
            self.verify()
        self.cwave = _LazyMaps(lambda d: self._img("spectral_wcs", d, "CWAVE"))
        self.cband = _LazyMaps(lambda d: self._img("spectral_wcs", d, "CBAND"))
        self.fluxcorr = _LazyMaps(lambda d: self._img("l3_flux_corrections", d, "IMAGE"))
        self.solid_angle = _LazyMaps(lambda d: self._img("solid_angle_pixel_map", d, "IMAGE"))
        self._channel: Any = None

    def path(self, product: str, detector: int | None = None) -> Path:
        return self.root / self.lock.get(product, detector).s3_key

    def verify(self) -> None:
        missing = [e.s3_key for e in self.lock.entries if not (self.root / e.s3_key).exists()]
        if missing:
            raise CalibIntegrityError(f"calibration files not bootstrapped: {missing[:3]}… ({len(missing)})")
        for e in self.lock.entries:
            _, sha = file_digests(self.root / e.s3_key)
            if e.sha256 is None or sha != e.sha256:
                raise CalibIntegrityError(f"{e.s3_key}: sha256 does not match calibration.lock")

    def _img(self, product: str, det: int | None, extname: str | None) -> Any:
        from astropy.io import fits

        p = self.path(product, det)
        with fits.open(p, memmap=os.name != "nt") as hl:
            if extname is not None:
                return np.asarray(hl[extname].data)
            for h in hl:  # first HDU that holds a 2-D image
                if getattr(h, "is_image", False) and h.data is not None and np.ndim(h.data) == 2:
                    return np.asarray(h.data)
        raise CalibIntegrityError(f"no image HDU in {p.name}")

    @property
    def channel(self) -> Any:
        if self._channel is None:
            self._channel = self._img("spectral_channels", None, "CHANNEL_MAP")
        return self._channel


class SlicedCalib:
    """types.Calib for fixtures: maps known only on a parent-pixel window [y0:y0+ny, x0:x0+nx], embedded in
    full-size NaN (or 0) arrays so `parent_slice` lookups work unchanged. Lookups outside the window
    return NaN, which the pipeline treats as unknown λ, never as a valid value."""

    def __init__(
        self,
        origin: tuple[int, int],
        cwave: Mapping[int, Any],
        channel: Any = None,
        cband: Mapping[int, Any] | None = None,
        fluxcorr: Mapping[int, Any] | None = None,
        shape: tuple[int, int] = (2040, 2040),
    ) -> None:
        def embed(a: Any, fill: float) -> Any:
            out = np.full(shape, fill, dtype=np.asarray(a).dtype if fill == 0 else float)
            out[parent_slice(origin, np.shape(a))] = a
            return out

        self.cwave = {d: embed(a, np.nan) for d, a in cwave.items()}
        self.cband = {d: embed(a, np.nan) for d, a in (cband or {}).items()}
        self.fluxcorr = {d: embed(a, np.nan) for d, a in (fluxcorr or {}).items()}
        self.channel = embed(channel, 0) if channel is not None else np.zeros(shape, np.uint8)
