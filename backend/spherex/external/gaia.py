"""Gaia DR3 at IRSA (TAP table `gaia_dr3_source`, ✅ 11-06). Owner D.

Astrometry is J2016.0 (Gaia DR3's reference epoch); pass `radial_velocity` to M's propagation only with
these Gaia epochs. Used for target astrometry (resolver step 3), re-registration reference stars (F15)
and mover identification."""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

import httpx

from .tap import adql_number, opt_float, tap_query

GAIA_EPOCH = 2016.0
COLUMNS = ("source_id, ra, dec, ra_error, dec_error, parallax, parallax_error, pmra, pmra_error, pmdec, "
           "pmdec_error, radial_velocity, radial_velocity_error, ruwe, phot_g_mean_mag, phot_bp_mean_mag, "
           "phot_rp_mean_mag")


@dataclass(frozen=True)
class GaiaSource:
    source_id: int
    ra: float
    dec: float
    ra_error: float | None
    dec_error: float | None
    parallax: float | None
    parallax_error: float | None
    pmra: float | None
    pmra_error: float | None
    pmdec: float | None
    pmdec_error: float | None
    radial_velocity: float | None
    radial_velocity_error: float | None
    ruwe: float | None
    phot_g_mean_mag: float | None
    phot_bp_mean_mag: float | None
    phot_rp_mean_mag: float | None
    epoch: float = GAIA_EPOCH

    @classmethod
    def from_row(cls, r: dict[str, Any]) -> GaiaSource:
        def f(k: str) -> float | None:
            return opt_float(r, k)
        return cls(int(r["source_id"]), float(r["ra"]), float(r["dec"]), f("ra_error"), f("dec_error"),
                   f("parallax"), f("parallax_error"), f("pmra"), f("pmra_error"), f("pmdec"), f("pmdec_error"),
                   f("radial_velocity"), f("radial_velocity_error"), f("ruwe"), f("phot_g_mean_mag"),
                   f("phot_bp_mean_mag"), f("phot_rp_mean_mag"))


def by_id_sql(ids: Sequence[int]) -> str:
    return f"SELECT {COLUMNS} FROM gaia_dr3_source WHERE source_id IN ({', '.join(str(int(i)) for i in ids)})"


def cone_sql(ra: float, dec: float, radius_deg: float, g_max: float | None = None) -> str:
    q = (f"SELECT {COLUMNS} FROM gaia_dr3_source WHERE 1 = CONTAINS(POINT('ICRS', ra, dec), "
         f"CIRCLE('ICRS', {adql_number(ra)}, {adql_number(dec)}, {adql_number(radius_deg)}))")
    if g_max is not None:
        q += f" AND phot_g_mean_mag < {adql_number(g_max)}"
    return q


class GaiaClient:
    def __init__(self, client: httpx.AsyncClient) -> None:
        self.client = client

    async def by_id(self, ids: Sequence[int]) -> list[GaiaSource]:
        if not ids:
            return []
        return [GaiaSource.from_row(r) for r in await tap_query(self.client, by_id_sql(ids))]

    async def cone(self, ra: float, dec: float, radius_deg: float, g_max: float | None = None) -> list[GaiaSource]:
        """A 12′ region around a target (F15) is ≈0.1°; the result must not be truncated (QueryOverflow)."""
        return [GaiaSource.from_row(r) for r in await tap_query(self.client, cone_sql(ra, dec, radius_deg, g_max))]
