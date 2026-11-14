"""Release registry (implementation.md §3.1, config/releases.yaml).

The registry is the only place that decides which collections exist and how they rank. It is edited by
a human in a reviewed PR (workflow.md §12.4); nothing in the code writes it. In particular DR1 is never
adopted automatically: the release watcher only reports a new prefix, and coverage rows from a
collection the registry doesn't list are skipped by dedup, not used."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

REPO = Path(__file__).resolve().parents[3]
DEFAULT_PATH = REPO / "config" / "releases.yaml"
_ID = re.compile(r"^[a-z][a-z0-9_]*$")


class RegistryError(ValueError):
    pass


@dataclass(frozen=True)
class Release:
    id: str
    collections: tuple[str, ...]
    s3_prefix: str
    pipeline_family: str
    photometric_scale: str
    priority: int

    @property
    def deep_collections(self) -> tuple[str, ...]:
        return tuple(c for c in self.collections if c.endswith("_deep"))


@dataclass(frozen=True)
class Registry:
    releases: tuple[Release, ...]
    never_use: tuple[str, ...] = ()
    calibration_release: str = "qr3"
    discover_by_listing: bool = True
    include_deep: str = "auto"
    raw: dict[str, Any] = field(default_factory=dict, compare=False)

    def collection_priority(self) -> dict[str, int]:
        return {c: r.priority for r in self.releases for c in r.collections}

    def release_for_collection(self, collection: str) -> Release | None:
        for r in self.releases:
            if collection in r.collections:
                return r
        return None

    def release(self, rid: str) -> Release:
        for r in self.releases:
            if r.id == rid:
                return r
        raise KeyError(rid)

    def collections(self, include_deep: bool | None = None) -> list[str]:
        """Collections to query, highest priority first. `include_deep: auto` includes the *_deep
        collections everywhere: outside the deep fields they return no rows, and inside them (R Dra,
        ≈1,950 of its ≈2,480 frames) leaving them out would silently drop most of the data."""
        deep = self.include_deep != "never" if include_deep is None else include_deep
        out: list[str] = []
        for r in sorted(self.releases, key=lambda r: -r.priority):
            out += [c for c in r.collections if deep or not c.endswith("_deep")]
        return out

    def is_forbidden(self, collection: str) -> bool:
        return any(collection == f"spherex_{n}" or collection.startswith(f"spherex_{n}_")
                   for n in self.never_use)

    def s3_prefixes(self) -> dict[str, str]:
        return {r.id: r.s3_prefix for r in self.releases}


def parse(doc: dict[str, Any]) -> Registry:
    if not isinstance(doc, dict) or not isinstance(doc.get("releases"), list) or not doc["releases"]:
        raise RegistryError("releases.yaml needs a non-empty 'releases' list")
    rels: list[Release] = []
    seen_ids: set[str] = set()
    seen_colls: set[str] = set()
    prios: set[int] = set()
    never = tuple(str(x) for x in doc.get("never_use", []))
    for d in doc["releases"]:
        for k in ("id", "collections", "s3_prefix", "pipeline_family", "photometric_scale", "priority"):
            if k not in d:
                raise RegistryError(f"release entry missing '{k}': {d}")
        rid = str(d["id"])
        if not _ID.match(rid) or rid in seen_ids:
            raise RegistryError(f"bad or duplicate release id {rid!r}")
        if rid in never:
            raise RegistryError(f"release {rid!r} is listed in never_use")
        colls = tuple(str(c) for c in d["collections"])
        if not colls or seen_colls & set(colls):
            raise RegistryError(f"release {rid!r}: empty or duplicated collections")
        prio = int(d["priority"])
        if prio in prios:
            raise RegistryError(f"duplicate priority {prio}: release order must be total")
        if not str(d["s3_prefix"]).endswith("/"):
            raise RegistryError(f"s3_prefix of {rid!r} must end with '/'")
        if d["photometric_scale"] not in ("qr2", "qr3"):
            raise RegistryError(f"unknown photometric_scale {d['photometric_scale']!r}")
        seen_ids.add(rid)
        seen_colls |= set(colls)
        prios.add(prio)
        rels.append(Release(rid, colls, str(d["s3_prefix"]), str(d["pipeline_family"]),
                            str(d["photometric_scale"]), prio))
    cal = doc.get("calibration", {}) or {}
    reg = Registry(tuple(rels), never, str(cal.get("release", "qr3")), bool(cal.get("discover_by_listing", True)),
                   str(doc.get("include_deep", "auto")), raw=doc)
    if reg.include_deep not in ("auto", "always", "never"):
        raise RegistryError(f"include_deep must be auto|always|never, not {reg.include_deep!r}")
    if reg.calibration_release not in seen_ids:
        raise RegistryError(f"calibration release {reg.calibration_release!r} is not a listed release")
    for c in seen_colls:
        if reg.is_forbidden(c):
            raise RegistryError(f"collection {c} belongs to a never_use release")
    return reg


def load(path: Path | str = DEFAULT_PATH) -> Registry:
    return parse(yaml.safe_load(Path(path).read_text()))
