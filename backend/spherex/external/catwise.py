"""CatWISE2020 at IRSA (TAP table `catwise_2020`; owner D). Proper motions of faint red sources from
unWISE, used to identify mover candidates (implementation.md §4.10) and as a WISE-era cross-check.
CatWISE PMs are relative to a reference epoch of MJD 57170 (2015.4); positions are given at that epoch."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

from .tap import adql_number, opt_float, tap_query

CATWISE_EPOCH_MJD = 57170.0
COLUMNS = "source_name, ra, dec, sigra, sigdec, pmra, pmdec, sigpmra, sigpmdec, w1mpro, w2mpro, w1sigmpro, w2sigmpro"


@dataclass(frozen=True)
class CatwiseSource:
    source_name: str
    ra: float
    dec: float
    sigra: float | None
    sigdec: float | None
    pmra: float | None      # arcsec/yr in the catalogue → converted to mas/yr here
    pmdec: float | None
    sigpmra: float | None
    sigpmdec: float | None
    w1mpro: float | None
    w2mpro: float | None
    w1sigmpro: float | None
    w2sigmpro: float | None

    @classmethod
    def from_row(cls, r: dict[str, Any]) -> CatwiseSource:
        def f(k: str) -> float | None:
            return opt_float(r, k)
        def mas(k: str) -> float | None:
            v = f(k)
            return None if v is None else v * 1000.0
        return cls(str(r["source_name"]).strip(), float(r["ra"]), float(r["dec"]), f("sigra"), f("sigdec"),
                   mas("pmra"), mas("pmdec"), mas("sigpmra"), mas("sigpmdec"), f("w1mpro"), f("w2mpro"),
                   f("w1sigmpro"), f("w2sigmpro"))


def cone_sql(ra: float, dec: float, radius_deg: float) -> str:
    return (f"SELECT {COLUMNS} FROM catwise_2020 WHERE 1 = CONTAINS(POINT('ICRS', ra, dec), "
            f"CIRCLE('ICRS', {adql_number(ra)}, {adql_number(dec)}, {adql_number(radius_deg)}))")


class CatwiseClient:
    def __init__(self, client: httpx.AsyncClient) -> None:
        self.client = client

    async def cone(self, ra: float, dec: float, radius_deg: float) -> list[CatwiseSource]:
        return [CatwiseSource.from_row(r) for r in await tap_query(self.client, cone_sql(ra, dec, radius_deg))]
