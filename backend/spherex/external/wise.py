"""AllWISE and NEOWISE images at IRSA via SIA2 (owner D; ✅ 11-06).

* AllWISE Atlas coadds: `COLLECTION=wise_allwise` (W1/W2 ≈ SPHEREx bands 4 and 6; epoch ≈2010.5).
* NEOWISE single exposures: `COLLECTION=neowiser`, grouped here into ≈6-month epochs (visits) for
  stacking. The stacking and normalisation are I's (25-year-blink normalisation, workflow.md §2.1).
Cutouts come from the `access_url` with `?center=…&size=…`."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx
import numpy as np

from ..access.retry import with_retry
from .tap import parse_votable

SIA = "https://irsa.ipac.caltech.edu/SIA"


@dataclass(frozen=True)
class WiseImage:
    collection: str
    obs_id: str
    band: str             # W1..W4
    t_min: float          # MJD
    t_max: float | None
    access_url: str
    subtype: str | None

    def cutout_url(self, ra: float, dec: float, size_deg: float) -> str:
        sep = "&" if "?" in self.access_url else "?"
        return f"{self.access_url}{sep}center={ra:.6f},{dec:.6f}&size={size_deg:.5f}"


def parse_sia(raw: bytes) -> list[WiseImage]:
    out = []
    for r in parse_votable(raw):
        band = str(r.get("energy_bandpassname") or "").strip()
        out.append(WiseImage(str(r["obs_collection"]), str(r["obs_id"]), band, float(r["t_min"]),
                             None if r.get("t_max") is None else float(r["t_max"]), str(r["access_url"]),
                             None if r.get("dataproduct_subtype") is None else str(r["dataproduct_subtype"])))
    return out


def group_epochs(images: list[WiseImage], gap_days: float = 60.0) -> list[list[WiseImage]]:
    """NEOWISE visits a sky point every ≈6 months for a few days; split on gaps > gap_days."""
    if not images:
        return []
    ims = sorted(images, key=lambda i: i.t_min)
    t = np.array([i.t_min for i in ims])
    cut = np.r_[0, np.nonzero(np.diff(t) > gap_days)[0] + 1, len(ims)]
    return [ims[a:b] for a, b in zip(cut[:-1], cut[1:], strict=False)]


class WiseClient:
    def __init__(self, client: httpx.AsyncClient) -> None:
        self.client = client

    async def search(self, ra: float, dec: float, collection: str, radius_deg: float = 0.0005,
                     bands: tuple[str, ...] | None = ("W1", "W2"),
                     subtypes: tuple[str, ...] | None = ("science",)) -> list[WiseImage]:
        """SIA2 rows include every product of a tile or frame (science `-int-` image, `noise`, `weight`,
        artefact `.tbl`s); by default only `science` images are returned."""
        params: list[tuple[str, Any]] = [("POS", f"CIRCLE {ra:.7f} {dec:.7f} {radius_deg:.6f}"),
                                         ("COLLECTION", collection), ("RESPONSEFORMAT", "VOTABLE")]

        async def once() -> bytes:
            r = await self.client.get(SIA, params=params, timeout=180)
            r.raise_for_status()
            return r.content
        ims = parse_sia(await with_retry(once))
        return [i for i in ims if (bands is None or i.band in bands) and (subtypes is None or i.subtype in subtypes)]

    async def allwise(self, ra: float, dec: float, **kw: Any) -> list[WiseImage]:
        return await self.search(ra, dec, "wise_allwise", **kw)

    async def neowise(self, ra: float, dec: float, **kw: Any) -> list[WiseImage]:
        return await self.search(ra, dec, "neowiser", **kw)

    async def cutout(self, img: WiseImage, ra: float, dec: float, size_deg: float) -> bytes:
        async def once() -> bytes:
            r = await self.client.get(img.cutout_url(ra, dec, size_deg), timeout=180)
            r.raise_for_status()
            return r.content
        return await with_retry(once)
