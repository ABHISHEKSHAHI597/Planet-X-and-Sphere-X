"""Horizons HTTP transport. Science code consumes parsed astrometric ICRF positions.

UTC JD for observer tables; vectors explicitly request ICRF equatorial km/s,
geocentre and TDB epochs. Cache by complete query, not by approximate epoch.
"""

from __future__ import annotations

import csv
import io
from typing import Any

import numpy as np
from astropy.time import Time

from ..access.retry import with_retry

# Ephemerides are immutable per (object, observer, epoch): cached forever in-process (implementation.md §3.7).
_CACHE: dict[tuple[str, str, float], tuple[float, float]] = {}

URL = "https://ssd.jpl.nasa.gov/api/horizons.api"
CENTER = "500@-163182"
COMMANDS = {"pluto": "999", "makemake": "136472;", "haumea": "136108;", "eris": "136199;"}


def command(name: str) -> str:
    cmd = COMMANDS.get(name.strip().lower(), name.strip())
    if not cmd or any(c in cmd for c in "'\"\n\r"):
        raise ValueError("invalid Horizons object name")
    return cmd


def parse_table(result: str) -> list[list[str]]:
    if "$$SOE" not in result or "$$EOE" not in result:
        raise ValueError("Horizons returned no ephemeris; object or observer interval unavailable")
    block = result.split("$$SOE", 1)[1].split("$$EOE", 1)[0].strip()
    return [[v.strip() for v in r] for r in csv.reader(io.StringIO(block)) if r and any(v.strip() for v in r)]


async def positions(client: Any, name: str, mjd: list[float], center: str = CENTER) -> list[tuple[float, float]]:
    times = np.asarray(mjd, float)
    if not np.all(np.isfinite(times)):
        raise ValueError("finite MJD UTC required")
    cmd = command(name)
    missing = sorted({float(t) for t in times if (cmd, center, float(t)) not in _CACHE})
    for start in range(0, len(missing), 50):
        ordered = missing[start : start + 50]
        params = dict(
            format="json",
            COMMAND=f"'{cmd}'",
            OBJ_DATA="'NO'",
            MAKE_EPHEM="'YES'",
            EPHEM_TYPE="'OBSERVER'",
            CENTER=f"'{center}'",
            QUANTITIES="'1'",
            ANG_FORMAT="'DEG'",
            CSV_FORMAT="'YES'",
            TIME_TYPE="'UT'",
            TLIST=",".join(f"{t + 2400000.5:.9f}" for t in ordered),
        )
        async def once(params: dict[str, str] = params) -> Any:
            r = await client.get(URL, params=params, timeout=90)
            r.raise_for_status()
            return r

        doc = (await with_retry(once)).json()
        if "error" in doc:
            raise ValueError(str(doc["error"]))
        rows = parse_table(doc.get("result", ""))
        if len(rows) != len(ordered):
            raise ValueError("Horizons response count mismatch")
        # Observer CSV: date, solar-presence, lunar-presence, RA, Dec.
        vals = [(float(row[3]), float(row[4])) for row in rows]
        if any(not (0 <= a < 360 and -90 <= d <= 90) for a, d in vals):
            raise ValueError("Horizons angle out of range")
        _CACHE.update({(cmd, center, t): v for t, v in zip(ordered, vals, strict=True)})
    return [_CACHE[(cmd, center, float(t))] for t in times]


async def spacecraft_vectors(client: Any, mjd: list[float]) -> Any:
    ordered = sorted(set(mjd))
    td = Time(ordered, format="mjd", scale="utc").tdb.jd
    params = dict(
        format="json",
        COMMAND="'-163182'",
        OBJ_DATA="'NO'",
        MAKE_EPHEM="'YES'",
        EPHEM_TYPE="'VECTORS'",
        CENTER="'500@399'",
        REF_PLANE="'FRAME'",
        REF_SYSTEM="'ICRF'",
        OUT_UNITS="'KM-S'",
        VEC_TABLE="'2'",
        CSV_FORMAT="'YES'",
        TLIST=",".join(f"{t:.10f}" for t in td),
    )
    r = await client.get(URL, params=params, timeout=90)
    r.raise_for_status()
    rows = parse_table(r.json().get("result", ""))
    if len(rows) != len(ordered):
        raise ValueError("Horizons vector count mismatch")
    by_time = dict(zip(ordered, [[float(v) for v in row[2:5]] for row in rows], strict=True))
    return np.asarray([by_time[t] for t in mjd])
