"""AllWISE Source Catalog at IRSA (TAP table `allwise_p3as_psd`; owner D). Used for the WISE overlay layer:
positions as WISE measured them around 2010.5, drawn where they were, never moved to another epoch. A source
that has moved since then sits away from its marker, which is the point of the layer (optimisation.md REL-5).
For WISE-era proper motions use CatWISE2020 (`catwise.py`)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

from .tap import adql_number, opt_float, tap_query

ALLWISE_EPOCH = 2010.5            # mean epoch of the cryogenic and post-cryogenic survey phases AllWISE combines
ALLWISE_W2_MAX = 14.0             # the overlay's brightness cut (app/science.py): readable, and keeps WISE 0855 (13.70)
COLUMNS = "designation, ra, dec, w1mpro, w2mpro"


@dataclass(frozen=True)
class AllwiseSource:
    designation: str
    ra: float
    dec: float
    w1mpro: float | None
    w2mpro: float | None

    @classmethod
    def from_row(cls, r: dict[str, Any]) -> AllwiseSource:
        return cls(str(r["designation"]).strip(), float(r["ra"]), float(r["dec"]), opt_float(r, "w1mpro"), opt_float(r, "w2mpro"))


def cone_sql(ra: float, dec: float, radius_deg: float) -> str:
    return (f"SELECT {COLUMNS} FROM allwise_p3as_psd WHERE 1 = CONTAINS(POINT('ICRS', ra, dec), "
            f"CIRCLE('ICRS', {adql_number(ra)}, {adql_number(dec)}, {adql_number(radius_deg)}))")


class AllwiseClient:
    def __init__(self, client: httpx.AsyncClient) -> None:
        self.client = client

    async def cone(self, ra: float, dec: float, radius_deg: float) -> list[AllwiseSource]:
        return [AllwiseSource.from_row(r) for r in await tap_query(self.client, cone_sql(ra, dec, radius_deg))]
