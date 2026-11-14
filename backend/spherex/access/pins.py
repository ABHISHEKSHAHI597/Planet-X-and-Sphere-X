"""Pinned frame lists (implementation.md §2.3, workflow.md §8.3).

A pin is the frame list F of a view: `pin = first 12 hex of sha256(F)`, F = the deduplicated frame
access URLs, sorted, joined with "\n" (versions are in the names, so F is immutable). Pins live in
config/pins/<pin>.json. New archive data never changes an existing pin; it produces a *candidate* pin
that is diffed against the current one and adopted only through the §12.4 procedure.

P's view key (`sha256(canonical params + F)`) must hash F the same way: use `frame_list_digest`."""
from __future__ import annotations

import datetime
import hashlib
import json
from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..types import FrameRef
from .dedup import FileInfo
from .releases import REPO, Registry

PIN_DIR = REPO / "config" / "pins"
SCHEMA = "parallax-pin@1"


class PinError(ValueError):
    pass


def frame_list_digest(urls: Iterable[str]) -> str:
    return hashlib.sha256("\n".join(sorted(urls)).encode()).hexdigest()


def pin_of(frames: Sequence[FrameRef]) -> str:
    urls = [f.access_url for f in frames]
    if len(set(urls)) != len(urls):
        raise PinError("frame list has duplicate URLs; dedup first")
    return frame_list_digest(urls)[:12]


def frame_entry(f: FrameRef, registry: Registry) -> dict[str, Any]:
    fi = FileInfo.parse(f.access_url)
    rel = registry.release_for_collection(f.collection)
    return dict(access_url=f.access_url, s3_key=f.s3_key, collection=f.collection, obs_id=f.obs_id,
                detector=f.detector, t_min=f.t_min, release=rel.id if rel else None,
                file_version=f"v{fi.version}" if fi else None, proc_date=fi.proc_date if fi else None,
                psffix=bool(fi and fi.psffix), retry=bool(fi and fi.retry))


@dataclass
class Pin:
    pin: str
    doc: dict[str, Any]

    @property
    def frames(self) -> list[FrameRef]:
        return [FrameRef(e["access_url"], e["s3_key"], e["collection"], e["obs_id"], int(e["detector"]),
                         float(e["t_min"])) for e in self.doc["frames"]]


def make_pin(frames: Sequence[FrameRef], registry: Registry, params: dict[str, Any], provenance: dict[str, Any]) -> Pin:
    p = pin_of(frames)
    by_det = Counter(f.detector for f in frames)
    by_rel = Counter(frame_entry(f, registry)["release"] for f in frames)
    by_coll = Counter(f.collection for f in frames)
    doc = dict(schema=SCHEMA, pin=p, created=datetime.date.today().isoformat(), params=params,
               counts=dict(frames=len(frames), by_detector={str(k): v for k, v in sorted(by_det.items())},
                           by_release=dict(sorted(by_rel.items())), by_collection=dict(sorted(by_coll.items()))),
               mjd_range=[min(f.t_min for f in frames), max(f.t_min for f in frames)] if frames else None,
               provenance=provenance, frames=[frame_entry(f, registry) for f in frames])
    return Pin(p, doc)


def save(pin: Pin, root: Path = PIN_DIR) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"{pin.pin}.json"
    if path.exists():
        old = json.loads(path.read_text())
        if [e["access_url"] for e in old["frames"]] != [e["access_url"] for e in pin.doc["frames"]]:
            raise PinError(f"pin {pin.pin} exists with a different frame list")   # impossible unless corrupted
        return path                                       # pins are immutable: never rewritten
    path.write_text(json.dumps(pin.doc, indent=1) + "\n")
    return path


def load(pin_id: str, root: Path = PIN_DIR) -> Pin:
    path = root / f"{pin_id}.json"
    if not path.exists():
        raise PinError(f"unknown pin {pin_id}")
    doc = json.loads(path.read_text())
    if doc.get("schema") != SCHEMA or doc.get("pin") != pin_id:
        raise PinError(f"pin file {path.name} has a bad schema or id")
    if frame_list_digest(e["access_url"] for e in doc["frames"])[:12] != pin_id:
        raise PinError(f"pin {pin_id}: frame list does not hash to its id")
    return Pin(pin_id, doc)


def diff(old: Sequence[FrameRef], new: Sequence[FrameRef]) -> dict[str, Any]:
    """Candidate-pin diff for the §12.4 review: frames added, removed, and replaced by a newer version
    of the same (obs id, detector)."""
    ko = {(f.obs_id, f.detector): f.access_url for f in old}
    kn = {(f.obs_id, f.detector): f.access_url for f in new}
    added = sorted(kn[k] for k in kn.keys() - ko.keys())
    removed = sorted(ko[k] for k in ko.keys() - kn.keys())
    replaced = sorted((ko[k], kn[k]) for k in ko.keys() & kn.keys() if ko[k] != kn[k])
    return dict(same=not (added or removed or replaced), added=added, removed=removed, replaced=replaced,
                n_old=len(old), n_new=len(new))
