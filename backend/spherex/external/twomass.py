"""2MASS at IRSA (owner D): Point Source Catalog epochs and Atlas images for the 25-year blink.

* Epochs: `fp_psc.jdate` is each source's own 2MASS observation date (✅ 11-06: Barnard 2000-05-28 =
  2000.41, ε Ind B 1999.85, RW Aur 1999.90). Every target has its own epoch; never assume "≈1998".
* Images: IBE search `ibe/search/twomass/allsky/allsky?POS=ra,dec` lists every overlapping Atlas image
  (8.5′ × 17′); the data URL is `ibe/data/twomass/allsky/allsky/{ordate}{hemisphere}/s{scanno:03d}/image/
  {fname}` plus `?center=…&size=…` for a cutout. 2MASS is not in IRSA's SIA2 ObsCore."""
from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from typing import Any

import httpx
from astropy.time import Time

from ..access.retry import with_retry
from .tap import adql_number, opt_float, tap_query

IBE_SEARCH = "https://irsa.ipac.caltech.edu/ibe/search/twomass/allsky/allsky"
IBE_DATA = "https://irsa.ipac.caltech.edu/ibe/data/twomass/allsky/allsky/"


@dataclass(frozen=True)
class TwoMassSource:
    designation: str
    ra: float
    dec: float
    j_m: float | None
    h_m: float | None
    k_m: float | None
    jdate: float
    ph_qual: str | None

    @property
    def epoch(self) -> float:
        """Decimal year of this source's 2MASS observation."""
        return float(Time(self.jdate, format="jd", scale="utc").decimalyear)

    @property
    def date(self) -> str:
        return str(Time(self.jdate, format="jd", scale="utc").to_value("iso", subfmt="date"))


def psc_cone_sql(ra: float, dec: float, radius_deg: float) -> str:
    return ("SELECT designation, ra, dec, j_m, h_m, k_m, jdate, ph_qual FROM fp_psc WHERE "
            f"1 = CONTAINS(POINT('ICRS', ra, dec), CIRCLE('ICRS', {adql_number(ra)}, {adql_number(dec)}, "
            f"{adql_number(radius_deg)}))")


def _src(r: dict[str, Any]) -> TwoMassSource:
    def f(k: str) -> float | None:
        return opt_float(r, k)
    return TwoMassSource(str(r["designation"]).strip(), float(r["ra"]), float(r["dec"]), f("j_m"), f("h_m"),
                         f("k_m"), float(r["jdate"]), None if r.get("ph_qual") is None else str(r["ph_qual"]))


@dataclass(frozen=True)
class AtlasImage:
    band: str              # j, h, k
    ordate: str
    hemisphere: str
    scanno: int
    fname: str
    row: dict[str, Any]

    def url(self) -> str:
        return f"{IBE_DATA}{self.ordate}{self.hemisphere}/s{self.scanno:03d}/image/{self.fname}"

    def cutout_url(self, ra: float, dec: float, size_deg: float) -> str:
        return f"{self.url()}?center={ra:.6f},{dec:.6f}&size={size_deg:.5f}"


def parse_image_search(text: str) -> list[AtlasImage]:
    rows = list(csv.DictReader(io.StringIO(text)))
    out = []
    for r in rows:
        fname = r.get("fname", "").strip()
        if not fname:
            continue
        band = (r.get("filter") or fname[0]).strip().lower()
        out.append(AtlasImage(band, r["ordate"].strip(), r["hemisphere"].strip(), int(r["scanno"]), fname, r))
    return out


def nearest_match(rows: list[TwoMassSource], ra: float, dec: float, match_arcsec: float) -> TwoMassSource | None:
    import math
    best, dbest = None, match_arcsec
    for s in rows:
        d = 3600 * math.hypot((s.ra - ra) * math.cos(math.radians(dec)), s.dec - dec)
        if d <= dbest:
            best, dbest = s, d
    return best


class TwoMassClient:
    def __init__(self, client: httpx.AsyncClient) -> None:
        self.client = client

    async def cone(self, ra: float, dec: float, radius_deg: float = 0.01) -> list[TwoMassSource]:
        return [_src(r) for r in await tap_query(self.client, psc_cone_sql(ra, dec, radius_deg))]

    async def epoch_of(self, ra: float, dec: float, radius_deg: float = 0.01, match_arcsec: float = 10.0,
                       k_expected: float | None = None, k_tol: float = 1.5) -> TwoMassSource | None:
        """The 2MASS source that is the target, or None if 2MASS did not detect it.
        (ra, dec) must be the target's position *at its 2MASS epoch* (≈2000 for a fast mover, not now).
        Nearest source within `match_arcsec` whose Ks agrees with `k_expected` (when given) within `k_tol`.
        Position alone is not enough: 2MASS 08551654-0714457 (K = 15.8) lies 3.6″ from WISE 0855's J2000
        position and ≈9″ from its 1999 position, but WISE 0855 has J ≈ 25 (recorded response, 2026-11-07)."""
        rows = await self.cone(ra, dec, radius_deg)
        if k_expected is not None:
            rows = [s for s in rows if s.k_m is not None and abs(s.k_m - k_expected) <= k_tol]
        return nearest_match(rows, ra, dec, match_arcsec)

    async def images(self, ra: float, dec: float, band: str | None = "k") -> list[AtlasImage]:
        async def once() -> str:
            r = await self.client.get(IBE_SEARCH, params={"POS": f"{ra:.6f},{dec:.6f}", "ct": "csv"}, timeout=120)
            r.raise_for_status()
            return r.text
        imgs = parse_image_search(await with_retry(once))
        return [i for i in imgs if band is None or i.band == band]

    async def cutout(self, img: AtlasImage, ra: float, dec: float, size_deg: float) -> bytes:
        """Raw (possibly gzipped) FITS bytes of an Atlas cutout; validated as FITS by the caller."""
        async def once() -> bytes:
            r = await self.client.get(img.cutout_url(ra, dec, size_deg), timeout=180)
            r.raise_for_status()
            return r.content
        return await with_retry(once)
