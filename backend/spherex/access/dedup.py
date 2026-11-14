"""Deduplication and version policy (implementation.md §3.3).

One frame per (observation id, detector). Prefer the higher-priority release (registry), then the newer
pipeline version, then the newer processing date, then a `+psffix1` file, then a `_retry` file.
* `_retry`: 11 of the 3,878 files covering the 5 targets are `…_spx_l2b_retry-v27-…` (QR3 reprocessing
  retries, ✅ 11-06); the regex accepts them.
* Co-aligned detector pairs (D1/D4, D2/D5, D3/D6) from one exposure share an obs id and are NOT
  duplicates: the key includes the detector.
* Unknown file names, unknown collections and never_use collections are skipped and reported, never
  fatal and never silently used (so a new DR1 collection stays out until the registry lists it)."""
from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any

from ..types import FrameRef
from .releases import Registry

FNAME = re.compile(r"level2_(?P<obsid>\w+?)D(?P<det>\d)_spx_l2b(?P<retry>_retry)?-v(?P<ver>\d+)-(?P<y>\d{4})-"
                   r"(?P<doy>\d{3})(?P<fix>\+psffix1)?\.fits")


@dataclass(frozen=True)
class FileInfo:
    obsid: str
    detector: int
    version: int
    proc_date: int                    # yyyy*1000 + day of year
    psffix: bool
    retry: bool

    @classmethod
    def parse(cls, url: str) -> FileInfo | None:
        m = FNAME.search(url)
        if m is None:
            return None
        return cls(m["obsid"], int(m["det"]), int(m["ver"]), int(m["y"]) * 1000 + int(m["doy"]),
                   bool(m["fix"]), bool(m["retry"]))


def rank(prio: int, fi: FileInfo) -> tuple[int, int, int, int, int]:
    return prio, fi.version, fi.proc_date, int(fi.psffix), int(fi.retry)


@dataclass
class DedupResult:
    frames: list[FrameRef]
    superseded: list[tuple[str, str]] = field(default_factory=list)    # (dropped url, kept url)
    skipped: list[tuple[str, str]] = field(default_factory=list)       # (url, reason)

    @property
    def n_in(self) -> int:
        return len(self.frames) + len(self.superseded) + len(self.skipped)


def _get(r: Any, k: str) -> Any:
    return r[k] if isinstance(r, Mapping) else getattr(r, k)


def dedup(rows: Iterable[Any], registry: Registry) -> DedupResult:
    """rows: coverage rows (dicts or objects with access_url, s3_key, collection, obs_id, t_min).
    Output is sorted by (t_min, obs id, detector) so frame lists and pins are deterministic."""
    prio = registry.collection_priority()
    best: dict[tuple[str, int], tuple[tuple[int, ...], Any, FileInfo]] = {}
    res = DedupResult([])
    for r in rows:
        url, coll = str(_get(r, "access_url")), str(_get(r, "collection"))
        if registry.is_forbidden(coll):
            res.skipped.append((url, f"collection {coll} is never_use"))
            continue
        if coll not in prio:
            res.skipped.append((url, f"collection {coll} not in config/releases.yaml"))
            continue
        fi = FileInfo.parse(url)
        if fi is None:
            res.skipped.append((url, "unrecognised file name"))
            continue
        key = (fi.obsid, fi.detector)
        rk = rank(prio[coll], fi)
        if key not in best:
            best[key] = (rk, r, fi)
        elif rk > best[key][0]:
            res.superseded.append((str(_get(best[key][1], "access_url")), url))
            best[key] = (rk, r, fi)
        else:
            res.superseded.append((url, str(_get(best[key][1], "access_url"))))
    refs = [FrameRef(access_url=str(_get(r, "access_url")), s3_key=str(_get(r, "s3_key")),
                     collection=str(_get(r, "collection")), obs_id=fi.obsid, detector=fi.detector,
                     t_min=float(_get(r, "t_min"))) for _, r, fi in best.values()]
    res.frames = sorted(refs, key=lambda f: (f.t_min, f.obs_id, f.detector))
    return res
