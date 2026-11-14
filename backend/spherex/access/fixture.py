"""FrameSource over committed real-file fixtures (FRAMESOURCE=fixture, workflow.md §8.5): the real pipeline
on real SPHEREx bytes with no network.

A fixture directory holds FITS files (stream-aborted cutouts, HDUs 0–4, or S3 sections written by
`write_fixture`) and `index.json`, mapping each file to its s3_key, its parent-pixel origin and how that
origin was established ("crpixa" for cutouts, "section" for S3 sections). Only frames whose bytes are in
the directory can be served; anything else is FrameUnavailable, so a test can never pass on made-up data."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
from astropy.io import fits
from astropy.wcs import WCS

from ..calib import parent_origin
from ..types import FrameRef, RawFrame
from .fitsio import WANTED
from .frames import FrameBox, FrameUnavailable, world_to_pixel


class FixtureSource:
    name = "fixture"

    def __init__(self, root: Path | str) -> None:
        self.root = Path(root)
        idx = self.root / "index.json"
        self.index: dict[str, dict[str, Any]] = json.loads(idx.read_text()) if idx.exists() else {}
        self.last_source = self.name

    def keys(self) -> list[str]:
        return sorted(self.index)

    def load(self, s3_key: str, ref: FrameRef | None = None) -> RawFrame:
        meta = self.index.get(s3_key)
        if meta is None:
            raise FrameUnavailable(f"no fixture for {s3_key}")
        p = self.root / meta["file"]
        if "sha256" in meta and hashlib.sha256(p.read_bytes()).hexdigest() != meta["sha256"]:
            raise FrameUnavailable(f"fixture {p.name} fails its sha256")
        with fits.open(p, memmap=False) as hl:
            hdus: dict[str, tuple[fits.Header, Any]] = {n: (hl[n].header.copy(), np.array(hl[n].data)) for n in WANTED}
            hdus["PRIMARY"] = (hl[0].header.copy(), np.zeros(0))
        for n in ("FLAGS",):
            a = hdus[n][1]
            if a.dtype.kind in "iu":
                hdus[n] = (hdus[n][0], a.astype(np.int64))
        hi = hdus["IMAGE"][0]
        origin = parent_origin(hi) if meta["origin_from"] == "crpixa" else tuple(meta["origin"])
        if "origin" in meta and tuple(meta["origin"]) != tuple(origin):
            raise FrameUnavailable(f"fixture {p.name}: origin {origin} disagrees with index {meta['origin']}")
        return RawFrame(hdus=hdus, wcs=WCS(hi), origin=origin, ref=ref, release=meta["release"])

    async def fetch(self, ref: FrameRef, box: FrameBox) -> RawFrame:
        f = self.load(ref.s3_key, ref)
        ny, nx = f.hdus["IMAGE"][1].shape
        xy = world_to_pixel(f.wcs, box.ra, box.dec, nx, ny)
        if xy is None or not (-0.5 <= xy[0] < nx - 0.5 and -0.5 <= xy[1] < ny - 0.5):
            raise FrameUnavailable(f"box centre is outside fixture {ref.id}")
        return f


def write_fixture(root: Path | str, frame: RawFrame, fname: str, origin_from: str, provenance: dict[str, Any]) -> Path:
    """Write one RawFrame (HDUs 0–4) and register it in index.json with its sha256 and provenance."""
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    prim = frame.hdus.get("PRIMARY", (fits.Header(), None))[0]
    hl = fits.HDUList([fits.PrimaryHDU(header=prim)])
    for n in WANTED:
        h, a = frame.hdus[n]
        a = np.asarray(a)
        if n == "FLAGS":
            a = a.astype(np.int32)                       # the on-disk type; int64 is our decoded form
        keep = fits.Header([c for c in h.cards if c.keyword not in
                            ("XTENSION", "BITPIX", "NAXIS", "NAXIS1", "NAXIS2", "PCOUNT", "GCOUNT", "EXTEND",
                             "ZIMAGE", "ZBITPIX", "ZNAXIS", "ZNAXIS1", "ZNAXIS2", "ZTILE1", "ZTILE2",
                             "ZCMPTYPE", "ZNAME1", "ZVAL1", "ZNAME2", "ZVAL2", "TFIELDS", "TTYPE1", "TFORM1",
                             "THEAP", "ZQUANTIZ", "ZDITHER0", "BSCALE", "BZERO")])
        hl.append(fits.ImageHDU(data=a, header=keep, name=n))
    p = root / fname
    hl.writeto(p, overwrite=True, output_verify="silentfix")
    idxp = root / "index.json"
    idx = json.loads(idxp.read_text()) if idxp.exists() else {}
    assert frame.ref is not None
    idx[frame.ref.s3_key] = dict(file=fname, origin=list(frame.origin), origin_from=origin_from,
                                 release=frame.release, sha256=hashlib.sha256(p.read_bytes()).hexdigest(),
                                 bytes=p.stat().st_size, **provenance)
    idxp.write_text(json.dumps(idx, indent=1, sort_keys=True))
    return p
