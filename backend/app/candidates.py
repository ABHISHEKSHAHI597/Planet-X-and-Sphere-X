"""Citizen-science candidate reports (implementation.md §8, P2-9; gate G5.eng).

SQLite, one file, schema of §8 plus a `pin` column (additive). Notes are stored and returned as plain
text and never rendered as HTML by us (the frontend renders them as text too). Reports are rate-limited
per IP (ratelimit.py). The public gallery is behind a moderation flag (PUBLIC_GALLERY, off during judging)
and always carries the honesty banner."""

from __future__ import annotations

import asyncio
import contextlib
import json
import sqlite3
import unicodedata
import uuid
from pathlib import Path
from typing import Any

import numpy as np

HONESTY = "Candidates are not discoveries until confirmed by follow-up."
MEASUREMENT_CHECK_S = 20.0   # the PM/colour check reuses cached view-bound measurements; never minutes (audit K-39)
SCHEMA = """
CREATE TABLE IF NOT EXISTS candidate (
  id TEXT PRIMARY KEY,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP,
  ra REAL NOT NULL, dec REAL NOT NULL, view_key TEXT NOT NULL, visits TEXT,
  kind TEXT CHECK (kind IN ('mover','variable','transient','artifact','other')),
  note TEXT CHECK (length(note) <= 1000), auto_checks TEXT,
  votes INTEGER DEFAULT 0, status TEXT DEFAULT 'new',
  pin TEXT DEFAULT '');
"""


def clean_note(s: str) -> str:
    """Plain text only: strip control characters (keep newlines/tabs), normalise, cap at 1000."""
    s = unicodedata.normalize("NFC", s)
    return "".join(c for c in s if c in "\n\t" or unicodedata.category(c)[0] != "C")[:1000]


class CandidateStore:
    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        with contextlib.closing(self._db()) as db, db:
            db.executescript(SCHEMA)

    def _db(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.path)
        db.row_factory = sqlite3.Row
        return db

    def add(self, req: dict[str, Any], checks: list[dict[str, Any]]) -> str:
        cid = str(uuid.uuid4())
        with contextlib.closing(self._db()) as db, db:
            db.execute(
                "INSERT INTO candidate (id, ra, dec, view_key, visits, kind, note, auto_checks, pin) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    cid,
                    req["ra"],
                    req["dec"],
                    req["view_key"],
                    json.dumps(req["visits"]),
                    req["kind"],
                    clean_note(req["note"]),
                    json.dumps(checks),
                    req.get("pin", ""),
                ),
            )
        return cid

    def list(self, limit: int = 200) -> list[dict[str, Any]]:
        with contextlib.closing(self._db()) as db:
            rows = db.execute("SELECT * FROM candidate ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
        return [
            dict(
                id=r["id"],
                created_at=r["created_at"],
                ra=r["ra"],
                dec=r["dec"],
                view_key=r["view_key"],
                pin=r["pin"] or "",
                visits=json.loads(r["visits"] or "[]"),
                kind=r["kind"],
                note=r["note"] or "",
                auto_checks=json.loads(r["auto_checks"] or "[]"),
                votes=r["votes"],
                status=r["status"],
            )
            for r in rows
        ]


async def auto_checks(svc: Any, req: dict[str, Any]) -> list[dict[str, Any]]:
    """implementation.md §8 step 2. A check that can't run says why (passed = None); none is faked."""
    ra, dec = float(req["ra"]), float(req["dec"])
    out: list[dict[str, Any]] = []
    client = svc.client if svc.settings.network else None
    m = svc.store.manifest(req["view_key"])

    async def known() -> dict[str, Any]:
        name = "Known in SIMBAD/Gaia/CatWISE?"
        if client is None:
            return dict(name=name, passed=None, detail="not checked: this server is offline")
        from spherex.external.catwise import CatwiseClient
        from spherex.external.gaia import GaiaClient
        from spherex.external.simbad import SimbadClient

        found = []
        r = 5.0 / 3600
        for label, coro in (
            ("Gaia DR3", GaiaClient(client).cone(ra, dec, r)),
            ("CatWISE2020", CatwiseClient(client).cone(ra, dec, r)),
            ("SIMBAD", SimbadClient(client).high_pm_cone(ra, dec, r, 0.0)),
        ):
            try:
                rows: Any = await asyncio.wait_for(coro, 30)
                if rows is not None and len(rows):
                    found.append(f"{label}: {len(rows)} within 5″")
            except Exception as e:
                found.append(f"{label}: not checked ({type(e).__name__})")
        hit = any("within" in f for f in found)
        incomplete = any("not checked" in f for f in found)
        return dict(
            name=name,
            passed=False if hit else None if incomplete else True,
            detail="; ".join(found) or "no catalogue source within 5″",
        )

    async def asteroid() -> dict[str, Any]:
        name = "Known asteroid (SkyBoT)?"
        if client is None or m is None:
            return dict(name=name, passed=None, detail="not checked: offline or unknown view")
        from spherex.external.skybot import SkybotClient

        mjds = sorted({b["mjd_mean"] for bins in m["bins"].values() for b in bins if b["id"] in req["visits"]})
        if not mjds:
            return dict(name=name, passed=None, detail="no visit epochs attached")
        try:
            hits = []
            for t in mjds[:4]:
                objs = await asyncio.wait_for(SkybotClient(client).cone(t + 2400000.5, ra, dec, 30 / 3600), 60)
                hits += [o.name for o in objs]
            return dict(
                name=name, passed=not hits, detail=", ".join(sorted(set(hits))) or "none within 30″ (geocentric)"
            )
        except Exception as e:
            return dict(name=name, passed=None, detail=f"not checked ({type(e).__name__})")

    out += list(await asyncio.gather(known(), asteroid()))
    n = len(req["visits"])
    out.append(dict(name="Seen in ≥ 2 visits?", passed=n >= 2, detail=f"{n} visit(s) attached"))
    out.append(_artifact_check(svc, req, m))
    if svc.enabled("astrometry") and svc.enabled("spectrum"):
        try:
            if m is None:
                raise LookupError("unknown view")
            # Always bound to the reported view (its frame list and cache); never a fresh 12′ build (K-39).
            # Through the API's view-bound result cache, with the arguments the viewer uses for a clicked position,
            # so a measurement the reporter already ran answers at once and a new one is cached for next time.
            from . import measurement
            from .main import _call

            astro, spectrum = await asyncio.wait_for(asyncio.gather(
                _call(measurement, "astrometry_api", svc, ra=ra, dec=dec, name="", key=req["view_key"]),
                _call(measurement, "spectrum_api", svc, ra=ra, dec=dec, track=False, visits="all",
                      key=req["view_key"])), MEASUREMENT_CHECK_S)
            fit = astro["fit"]
            red = [r for r in spectrum["rows"] if r["detector"] in (5, 6) and not r["contaminated"]]
            blue = [r for r in spectrum["rows"] if r["detector"] in (1, 2, 3) and not r["contaminated"]]
            moving = bool(fit and fit["delta_chi2"] > 25 and fit["mu"] > 3 * fit["e_mu"])
            cold = bool(
                red
                and blue
                and any(r["flux"] > 5 * r["err"] for r in red)
                and all(r["flux"] < 3 * r["err"] for r in blue)
            )
            out.append(
                dict(
                    name="PM significance and colour",
                    passed=moving and cold,
                    detail=f"native fits: moving={moving}, red detected and blue undetected={cold}; candidate only",
                )
            )
        except TimeoutError:
            out.append(dict(name="PM significance and colour", passed=None,
                            detail=f"not checked: the native-frame measurement did not finish within {MEASUREMENT_CHECK_S:.0f} s "
                            "(run Spectrum and Astrometry on this position first, then report again)"))
        except Exception as ex:
            out.append(dict(name="PM significance and colour", passed=None,
                            detail=f"measurement unavailable: {type(ex).__name__}: {ex}"[:300]))
    else:
        out.append(
            dict(
                name="PM significance and colour",
                passed=None,
                detail="not checked: measurement gates G3/G4b unaccepted; science flags off",
            )
        )
    return out


def _artifact_check(svc: Any, req: dict[str, Any], m: dict[str, Any] | None) -> dict[str, Any]:
    name = "Inside an artifact footprint?"
    if m is None:
        return dict(name=name, passed=None, detail="unknown view")
    from astropy.wcs import WCS

    g = m["grid"]
    w = WCS(naxis=2)
    w.wcs.ctype, w.wcs.crval, w.wcs.crpix, w.wcs.cdelt = g["ctype"], g["crval"], g["crpix"], g["cdelt"]
    x, y = (float(v) for v in w.wcs_world2pix(req["ra"], req["dec"], 0))
    ny, nx = g["shape"]
    ix, iy = int(round(x)), int(round(y))
    if not (0 <= ix < nx and 0 <= iy < ny):
        return dict(name=name, passed=None, detail="position outside the view")
    masked, total = 0, 0
    for s in m["stacks"]:
        if s["bin"] not in req["visits"] or not s["ready"]:
            continue
        p = svc.store.stack_path(m["key"], s["bin"], s["band"], "f32")
        if not p.exists():
            continue
        a = np.frombuffer(p.read_bytes(), "<f4").reshape(ny, nx)
        total += 1
        masked += int(not np.isfinite(a[iy, ix]))
    if not total:
        return dict(name=name, passed=None, detail="no stacks of the attached visits")
    return dict(
        name=name,
        passed=masked == 0,
        detail=f"pixel masked (artifact or bad-pixel flags) in {masked} of {total} attached stacks",
    )
