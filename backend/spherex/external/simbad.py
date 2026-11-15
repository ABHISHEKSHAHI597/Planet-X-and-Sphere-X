"""SIMBAD TAP client (owner D; M's resolver in targets.py decides aliases, normalisation and which
astrometry to trust).

* CfA mirror first: the CDS host timed out from our network twice (✅ 11-06).
* Identifiers are always sent as escaped ADQL literals (`Barnard's Star` broke an unescaped query, and
  unescaped input allows injection). SIMBAD normalises identifier spacing itself.
* Returned positions are SIMBAD's J2000 (linear back-propagations of Gaia for Gaia stars, ✅ 11-06);
  `plx_bibcode` is returned so callers can spot the Hipparcos-2007 RW Aur trap."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

from .tap import adql_literal, adql_number, opt_float, opt_str, tap_first

SIMBAD_TAPS = ("https://simbad.harvard.edu/simbad/sim-tap/sync",
               "https://simbad.cds.unistra.fr/simbad/sim-tap/sync")
COLUMNS = ("b.oid, b.main_id, b.ra, b.dec, b.pmra, b.pmdec, b.plx_value, b.plx_err, b.plx_bibcode, "
           "b.rvz_radvel, b.sp_type, b.otype, b.coo_bibcode, b.pm_bibcode")


@dataclass(frozen=True)
class SimbadObject:
    oid: int
    main_id: str
    ra: float | None
    dec: float | None
    pmra: float | None
    pmdec: float | None
    plx: float | None
    plx_err: float | None
    plx_bibcode: str | None
    rv: float | None
    sp_type: str | None
    otype: str | None
    coo_bibcode: str | None
    pm_bibcode: str | None
    epoch: float = 2000.0           # SIMBAD basic.ra/dec are ICRS J2000

    @classmethod
    def from_row(cls, r: dict[str, Any]) -> SimbadObject:
        def f(k: str) -> float | None:
            return opt_float(r, k)

        def s(k: str) -> str | None:
            return opt_str(r, k)
        return cls(int(r["oid"]), str(r["main_id"]).strip(), f("ra"), f("dec"), f("pmra"), f("pmdec"),
                   f("plx_value"), f("plx_err"), s("plx_bibcode"), f("rvz_radvel"), s("sp_type"), s("otype"),
                   s("coo_bibcode"), s("pm_bibcode"))


def by_identifier_sql(*identifiers: str) -> str:
    where = " OR ".join(f"i.id = {adql_literal(x)}" for x in identifiers)
    return f"SELECT {COLUMNS} FROM basic AS b JOIN ident AS i ON i.oidref = b.oid WHERE {where}"


def name_variants(identifier: str) -> list[str]:
    """Spellings to retry after an exact miss. SIMBAD's ident match is case-sensitive and maps `Polaris` to
    `NAME Polaris` itself, but IAU-approved star names are stored as `NAME-IAU Xamidimura` and are not mapped."""
    cap = " ".join(w[:1].upper() + w[1:] for w in identifier.split(" "))
    out = [cap, f"NAME-IAU {identifier}", f"NAME-IAU {cap}"]
    return [x for i, x in enumerate(out) if x != identifier and x not in out[:i]]


def gaia_id_sql(oid: int) -> str:
    return f"SELECT id FROM ident WHERE oidref = {int(oid)} AND id LIKE 'Gaia DR3 %'"


def high_pm_cone_sql(ra: float, dec: float, radius_deg: float = 0.1, min_pm_masyr: float = 500.0) -> str:
    """Epoch-guard candidates (implementation.md §4.1): high-PM objects within 6′ by default."""
    pm2 = float(min_pm_masyr) ** 2
    return (f"SELECT {COLUMNS} FROM basic AS b WHERE 1 = CONTAINS(POINT('ICRS', b.ra, b.dec), "
            f"CIRCLE('ICRS', {adql_number(ra)}, {adql_number(dec)}, {adql_number(radius_deg)})) "
            f"AND b.pmra * b.pmra + b.pmdec * b.pmdec > {adql_number(pm2)}")


class SimbadClient:
    def __init__(self, client: httpx.AsyncClient, mirrors: tuple[str, ...] = SIMBAD_TAPS) -> None:
        self.client, self.mirrors = client, mirrors
        self.last_mirror: str | None = None

    async def _q(self, sql: str) -> list[dict[str, Any]]:
        rows, self.last_mirror = await tap_first(self.client, sql, self.mirrors, timeout=60, tries=2)
        return rows

    async def by_identifier(self, identifier: str) -> SimbadObject | None:
        rows = await self._q(by_identifier_sql(identifier))
        if not rows and (alts := name_variants(identifier)):  # one more query, only on a miss
            rows = await self._q(by_identifier_sql(*alts))
        return SimbadObject.from_row(rows[0]) if rows else None

    async def gaia_dr3_id(self, oid: int) -> int | None:
        rows = await self._q(gaia_id_sql(oid))
        for r in rows:
            s = str(r["id"]).strip()
            if s.startswith("Gaia DR3 "):
                return int(s.removeprefix("Gaia DR3 "))
        return None

    async def k_mag(self, oid: int) -> float | None:
        """2MASS-like K magnitude (Vega) from SIMBAD's flux table, or None. Used to decide whether a target
        overflows the detectors (bright mask preset) and to match its 2MASS counterpart by brightness."""
        rows = await self._q(f"SELECT flux FROM flux WHERE oidref = {int(oid)} AND filter = 'K'")
        for r in rows:
            if r.get("flux") is not None:
                return float(r["flux"])
        return None

    async def high_pm_cone(self, ra: float, dec: float, radius_deg: float = 0.1,
                           min_pm_masyr: float = 500.0) -> list[SimbadObject]:
        return [SimbadObject.from_row(r) for r in await self._q(high_pm_cone_sql(ra, dec, radius_deg, min_pm_masyr))]
