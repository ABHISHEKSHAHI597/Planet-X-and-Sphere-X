"""IMCCE SkyBoT cone search (owner D): known Solar System objects in a field at an epoch.

✅ 11-06: the observer parameter is `-loc` (500 = geocentre); `-observer` is silently ignored, which
would quietly return the wrong observer. The geocentric → SPHEREx shift is M's (parallax_factors with
the spacecraft position). Results are immutable per (epoch, field, observer), so they are cached forever."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

from ..access.retry import with_retry
from .tap import JsonCache

SKYBOT = "https://ssp.imcce.fr/webservices/skybot/api/conesearch.php"


@dataclass(frozen=True)
class SkybotObject:
    number: str | None
    name: str
    ra_deg: float
    dec_deg: float
    cls: str
    mv: float | None
    err_arcsec: float | None
    dist_arcsec: float | None
    dra_arcsec_h: float | None
    ddec_arcsec_h: float | None
    dg_au: float | None
    dh_au: float | None


def params(jd: float, ra: float, dec: float, radius_deg: float, loc: str = "500") -> dict[str, str]:
    p = {"-ep": f"{jd:.6f}", "-ra": f"{ra:.6f}", "-dec": f"{dec:.6f}", "-rd": f"{radius_deg:.6f}",
         "-mime": "text", "-output": "basic", "-loc": str(loc), "-filter": "0", "-objFilter": "111",
         "-from": "ParallaX"}
    assert "-observer" not in p
    return p


def _hms_to_deg(s: str) -> float:
    h, m, sec = (float(x) for x in s.split())
    return 15.0 * (h + m / 60 + sec / 3600)


def _dms_to_deg(s: str) -> float:
    s = s.strip()
    sign = -1.0 if s.startswith("-") else 1.0
    d, m, sec = (abs(float(x)) for x in s.lstrip("+-").split())
    return sign * (d + m / 60 + sec / 3600)


def parse_text(text: str) -> list[SkybotObject]:
    """`-mime=text` output: comment lines start with '#', fields are '|'-separated: Num | Name | RA(h) |
    DE(deg) | Class | Mv | Err(arcsec) | d(arcsec) | dRA(arcsec/h) | dDEC(arcsec/h) | Dg(ua) | Dh(ua)."""
    out = []
    flag = None
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith("# Flag:"):
            flag = line
            continue
        if line.startswith("#"):
            continue
        f = [x.strip() for x in line.split("|")]
        if len(f) < 12:
            raise ValueError(f"unexpected SkyBoT line ({flag}): {line[:120]}")
        def num(x: str) -> float | None:
            return None if x in ("", "-") else float(x)
        out.append(SkybotObject(f[0] if f[0] not in ("", "-") else None, f[1], _hms_to_deg(f[2]), _dms_to_deg(f[3]),
                                f[4], num(f[5]), num(f[6]), num(f[7]), num(f[8]), num(f[9]), num(f[10]), num(f[11])))
    return out


class SkybotClient:
    def __init__(self, client: httpx.AsyncClient, cache: JsonCache | None = None) -> None:
        self.client, self.cache = client, cache

    async def cone(self, jd: float, ra: float, dec: float, radius_deg: float, loc: str = "500") -> list[SkybotObject]:
        p = params(jd, ra, dec, radius_deg, loc)
        key = "skybot?" + "&".join(f"{k}={v}" for k, v in sorted(p.items()))
        text: Any = self.cache.get(key) if self.cache else None
        if text is None:
            async def once() -> str:
                r = await self.client.get(SKYBOT, params=p, timeout=120)
                r.raise_for_status()
                return r.text
            text = await with_retry(once)
            if self.cache:
                self.cache.put(key, text)
        return parse_text(str(text))
