"""Coverage: SIA2 first, TAP as fallback (implementation.md §3.2).

SIA2 accepts repeated COLLECTION and answers in ≈6 s (✅ 11-06); TAP returns the same frames but costs
10–17 s per query even when trivial, so it is the fallback, the release watcher's confirmation path and
the F11 cross-check. Both produce `CoverageRow`s with the same fields; dedup then picks one file per
(obs id, detector). A truncated answer (QUERY_STATUS=OVERFLOW) is an error, never a short frame list.
SIA2 lags ingest by about a day; TAP gets new data first."""
from __future__ import annotations

import time
from dataclasses import asdict, dataclass
from typing import Any

import httpx

from ..external.tap import IRSA_TAP, QueryOverflow, ServiceError, adql_literal, adql_number, parse_votable, tap_query
from .http import IBE_PREFIX, IRSA_HOST, HostLimiter
from .releases import Registry
from .retry import with_retry

SIA = f"https://{IRSA_HOST}/SIA"
TARGET_RADIUS_DEG = 0.001           # target-centred views (default); discovery views use the half-diagonal
REQUIRED_SIA_COLUMNS = ("obs_collection", "obs_id", "access_url", "t_min", "energy_bandpassname", "cloud_access")


@dataclass(frozen=True)
class CoverageRow:
    collection: str
    obs_id: str
    band: str
    t_min: float                    # MJD
    access_url: str
    s3_key: str
    service: str                    # "sia2" | "tap"

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def s3_key_of(access_url: str) -> str:
    if not access_url.startswith(IBE_PREFIX):
        raise ValueError(f"unexpected access_url {access_url!r}")
    return access_url.removeprefix(IBE_PREFIX)


def half_diagonal_deg(fov_arcmin: float) -> float:
    """Discovery views: SIA2 POS=CIRCLE matches every image that overlaps the circle."""
    return fov_arcmin * 2 ** 0.5 / 2 / 60


def sia2_params(ra: float, dec: float, radius_deg: float,
                collections: list[str]) -> list[tuple[str, str | int | float | bool | None]]:
    p: list[tuple[str, str | int | float | bool | None]] = [
        ("POS", f"CIRCLE {ra:.7f} {dec:.7f} {radius_deg:.6f}"), ("RESPONSEFORMAT", "VOTABLE")]
    return p + [("COLLECTION", c) for c in collections]


def parse_sia2(raw: bytes, check_columns: bool = True) -> list[CoverageRow]:
    rows = parse_votable(raw)
    if rows and check_columns:
        missing = [c for c in REQUIRED_SIA_COLUMNS if c not in rows[0]]
        if missing:
            raise ServiceError(f"SIA2 response lacks columns {missing}")
    out = []
    for r in rows:
        url = str(r["access_url"])
        out.append(CoverageRow(str(r["obs_collection"]), str(r["obs_id"]), str(r["energy_bandpassname"]),
                               float(r["t_min"]), url, s3_key_of(url), "sia2"))
    return out


def tap_sql(ra: float, dec: float, collections: list[str]) -> str:
    colls = ", ".join(adql_literal(c) for c in collections)
    return ("SELECT o.collection, o.observationid, p.energy_bandpassname, p.energy_bounds_lower, "
            "p.energy_bounds_upper, p.time_bounds_lower, p.time_bounds_upper, p.time_exposure, a.uri, "
            "a.contentlength FROM spherex.plane AS p JOIN spherex.artifact AS a ON a.planeid = p.planeid "
            "JOIN spherex.observation AS o ON o.obsid = p.obsid "
            f"WHERE 1 = CONTAINS(POINT('ICRS', {adql_number(ra)}, {adql_number(dec)}), p.poly) "
            f"AND o.collection IN ({colls}) ORDER BY p.time_bounds_lower")


def parse_tap(rows: list[dict[str, Any]]) -> list[CoverageRow]:
    """✅ 11-06: one artifact per plane; a.uri → HTTP "https://irsa.ipac.caltech.edu/" + uri."""
    out = []
    for r in rows:
        url = f"https://{IRSA_HOST}/" + str(r["uri"]).lstrip("/")
        out.append(CoverageRow(str(r["collection"]), str(r["observationid"]), str(r["energy_bandpassname"]),
                               float(r["time_bounds_lower"]), url, s3_key_of(url), "tap"))
    return out


class CoverageClient:
    def __init__(self, client: httpx.AsyncClient, registry: Registry, limiter: HostLimiter | None = None,
                 cache: Any | None = None, tries: int = 3) -> None:
        self.client, self.registry, self.limiter = client, registry, limiter or HostLimiter()
        self.cache, self.tries = cache, tries
        self.last: dict[str, Any] = {}

    async def sia2(self, ra: float, dec: float, radius_deg: float = TARGET_RADIUS_DEG,
                   collections: list[str] | None = None) -> list[CoverageRow]:
        colls = collections or self.registry.collections()

        async def once() -> bytes:
            async with self.limiter.slot(SIA):
                r = await self.client.get(SIA, params=sia2_params(ra, dec, radius_deg, colls), timeout=120)
            r.raise_for_status()
            return r.content
        t0 = time.perf_counter()
        rows = parse_sia2(await with_retry(once, tries=self.tries))
        self.last = {"service": "sia2", "seconds": time.perf_counter() - t0, "rows": len(rows)}
        return rows

    async def tap(self, ra: float, dec: float, collections: list[str] | None = None) -> list[CoverageRow]:
        """Point containment only: INTERSECTS with the joins timed out (>200 s, ✅ 11-06)."""
        colls = collections or self.registry.collections()
        t0 = time.perf_counter()
        async with self.limiter.slot(IRSA_TAP):
            rows = parse_tap(await tap_query(self.client, tap_sql(ra, dec, colls), tries=self.tries))
        self.last = {"service": "tap", "seconds": time.perf_counter() - t0, "rows": len(rows)}
        return rows

    async def coverage(self, ra: float, dec: float, radius_deg: float = TARGET_RADIUS_DEG,
                       collections: list[str] | None = None, release_state: str = "") -> list[CoverageRow]:
        """SIA2, falling back to TAP if SIA2 fails or overflows. TAP can only answer point queries, so
        a discovery-radius fallback queries the centre point and says so in `last`."""
        colls = collections or self.registry.collections()
        ckey = f"{ra:.5f},{dec:.5f},{radius_deg:.6f},{'|'.join(colls)}"
        if self.cache is not None:
            hit = self.cache.get(ckey, release_state)
            if hit is not None:
                self.last = {"service": "cache", "rows": len(hit)}
                return [CoverageRow(**r) for r in hit]
        try:
            try:
                rows = await self.sia2(ra, dec, radius_deg, colls)
            except (httpx.HTTPError, ServiceError, QueryOverflow, RuntimeError) as e:
                rows = await self.tap(ra, dec, colls)
                self.last["fallback_reason"] = repr(e)[:200]
                if radius_deg > TARGET_RADIUS_DEG:
                    self.last["warning"] = "TAP fallback answered for the centre point only"
        except QueryOverflow:
            raise
        except (httpx.HTTPError, ServiceError, RuntimeError) as e:   # SIA2 and TAP both down: last known list
            stale = self.cache.get_stale(ckey) if self.cache is not None else None
            if stale is None:
                raise
            hit, saved = stale
            day = time.strftime("%Y-%m-%d", time.gmtime(saved))
            self.last = {"service": "stale-cache", "rows": len(hit), "saved": saved, "fallback_reason": repr(e)[:200],
                         "warning": f"IRSA is not answering, so this view uses the frame list saved on {day}. "
                                    "Frames IRSA added after that are missing until it is back."}
            return [CoverageRow(**r) for r in hit]
        if self.cache is not None:
            self.cache.put(ckey, [r.as_dict() for r in rows], release_state)
        return rows
