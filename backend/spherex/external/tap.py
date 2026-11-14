"""Shared helpers for the catalogue clients (owner D): ADQL literal escaping, TAP sync queries returning
VOTables (with overflow detection), and a small persistent JSON cache for recorded responses.

All services here are called server-side only: IRSA, SIMBAD and SkyBoT send no CORS headers, and the
frontend never calls external services directly (workflow.md §3)."""
from __future__ import annotations

import hashlib
import io
import json
import math
import os
import threading
import time
import warnings
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import httpx

from ..access.retry import with_retry

IRSA_TAP = "https://irsa.ipac.caltech.edu/TAP/sync"


class QueryOverflow(RuntimeError):
    """The service truncated the result (VOTable QUERY_STATUS = OVERFLOW). Never use a truncated list:
    it would silently drop frames or stars."""


class ServiceError(RuntimeError):
    pass


def opt_float(r: dict[str, Any], k: str) -> float | None:
    """r[k] as a float, or None when the column is null (catalogue row parsers)."""
    v = r.get(k)
    return None if v is None else float(v)


def opt_str(r: dict[str, Any], k: str) -> str | None:
    v = r.get(k)
    return None if v in (None, "") else str(v).strip()


def adql_literal(s: str) -> str:
    """'…' with embedded quotes doubled. `Barnard's Star` broke an unescaped query, and unescaped
    input allows injection (✅ 11-06)."""
    return "'" + str(s).replace("'", "''") + "'"


def adql_number(x: float) -> str:
    v = float(x)
    if not math.isfinite(v):
        raise ValueError(f"non-finite number in ADQL: {x!r}")
    return repr(v)


def parse_votable(raw: bytes) -> list[dict[str, Any]]:
    """VOTable → rows keyed by field *name* (IRSA SIA2 fields carry names, not ids). Raises
    QueryOverflow on QUERY_STATUS=OVERFLOW and ServiceError on QUERY_STATUS=ERROR."""
    from astropy.io.votable import parse
    from astropy.io.votable.exceptions import VOWarning
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", VOWarning)
        vt = parse(io.BytesIO(raw), verify="ignore")
    infos = list(vt.infos) + [i for r in vt.resources for i in r.infos]
    for info in infos:
        if info.name == "QUERY_STATUS":
            if info.value == "OVERFLOW":
                raise QueryOverflow("result truncated by the service (QUERY_STATUS=OVERFLOW)")
            if info.value == "ERROR":
                raise ServiceError(f"service error: {info.content or info.value}")
    tables = list(vt.iter_tables())
    if not tables:
        return []
    import numpy as np
    t = tables[0]
    names = [f.name for f in t.fields]
    tab = t.to_table()
    tab.rename_columns(tab.colnames, names)
    out = []
    for rec in tab:
        row: dict[str, Any] = {}
        for n in names:
            v = rec[n]
            if v is np.ma.masked or (np.ma.isMaskedArray(v) and np.ma.getmaskarray(v).all()):
                row[n] = None
                continue
            if isinstance(v, bytes):
                v = v.decode()
            if hasattr(v, "item") and getattr(v, "ndim", 0) == 0:
                v = v.item()
            if isinstance(v, float) and math.isnan(v):
                v = None
            row[n] = v
        out.append(row)
    return out


async def tap_query(client: httpx.AsyncClient, query: str, url: str = IRSA_TAP, maxrec: int = 1_000_000,
                    timeout: float = 300.0, tries: int = 3) -> list[dict[str, Any]]:
    """Synchronous TAP (ADQL) → rows. IRSA TAP costs 10–17 s even for trivial queries (✅ 11-06), so keep
    it off interactive paths."""
    data = {"REQUEST": "doQuery", "LANG": "ADQL", "FORMAT": "votable", "QUERY": query, "MAXREC": str(maxrec)}

    async def once() -> bytes:
        r = await client.post(url, data=data, timeout=timeout)
        r.raise_for_status()
        return r.content
    return parse_votable(await with_retry(once, tries=tries))


async def tap_first(client: httpx.AsyncClient, query: str, urls: Sequence[str], **kw: Any) -> tuple[list[dict[str, Any]], str]:
    """Try mirrors in order (SIMBAD: CfA first, the CDS host timed out from our network twice)."""
    last: Exception | None = None
    for u in urls:
        try:
            return await tap_query(client, query, url=u, **kw), u
        except (httpx.HTTPError, ServiceError, RuntimeError) as e:
            if isinstance(e, QueryOverflow):
                raise
            last = e
    raise ServiceError(f"all mirrors failed: {last!r}")


class JsonCache:
    """Forever-cache for immutable answers (SkyBoT and catalogue responses keyed by the exact request),
    optionally with a TTL. One file per key under `root`."""

    def __init__(self, root: Path | str, ttl_s: float | None = None) -> None:
        self.root, self.ttl = Path(root), ttl_s
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        return self.root / (hashlib.sha256(key.encode()).hexdigest()[:32] + ".json")

    def get(self, key: str) -> Any | None:
        p = self._path(key)
        if not p.exists():
            return None
        try:
            d = json.loads(p.read_text())
        except (OSError, ValueError):          # corrupt entry: a miss (audit K-37)
            return None
        if self.ttl is not None and time.time() - d["t"] > self.ttl:
            return None
        return d["v"]

    def put(self, key: str, value: Any) -> None:
        p = self._path(key)
        tmp = p.with_suffix(f".tmp{os.getpid()}.{threading.get_ident()}")
        tmp.write_text(json.dumps({"k": key, "t": time.time(), "v": value}, default=str))
        tmp.replace(p)
