"""Disk budget for the cache (audit O-13). Frames are cached "forever" and every view's payloads stay on disk, so a
public server that accepts any coordinates fills its volume. With CACHE_MAX_GB set, the least recently used frames
and views are deleted until the cache is back under 90 % of the budget.

Never deleted: views whose frame list is a committed demo pin (config/pins), views listed in the offline snapshot's
index, views being built right now, and everything outside `frames/` and `views/` (coverage, resolver, catalogue,
pins, release state, candidates). A deleted view or frame is simply rebuilt or re-fetched on its next request: the
cache is content-addressed, so deletion can cost time but never change a result.

"Recently used": a frame's file time is refreshed on each cache hit, a view's `.used` marker on each warm request
(`touch_view`), so eviction follows use, not creation, even on file systems mounted with noatime."""
from __future__ import annotations

import json
import logging
import os
import shutil
import time
from pathlib import Path
from typing import Any

log = logging.getLogger("parallax.cachegc")
TARGET_FRACTION = 0.9
MIN_FREE_BYTES = 1 << 30          # refuse new builds below 1 GiB free (HTTP 507) rather than fail half-way


def _tree_size(p: Path) -> int:
    n = 0
    for root, _, files in os.walk(p):
        for f in files:
            try:
                n += os.stat(os.path.join(root, f)).st_size
            except OSError:
                pass
    return n


def touch_view(store_root: Path, key: str) -> None:
    try:
        m = store_root / "views" / key / ".used"
        m.parent.mkdir(parents=True, exist_ok=True)
        m.touch()
    except OSError:
        pass


def _view_used(d: Path) -> float:
    for name in (".used", "manifest.json"):
        try:
            return (d / name).stat().st_mtime
        except OSError:
            continue
    return 0.0


def protected_keys(svc: Any) -> set[str]:
    """Views that must survive any budget: demo pins, the snapshot index, running jobs."""
    keep: set[str] = {j.key for j in svc.jobs.jobs.values() if j.status == "running"}
    pins = {p.stem for p in Path(svc.settings.pins_dir).glob("*.json") if p.stem != "index"}
    vroot = svc.store.root / "views"
    if vroot.exists():
        for d in vroot.iterdir():
            try:
                m = json.loads((d / "manifest.json").read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            if m.get("pin") in pins:
                keep.add(d.name)
    if svc.snapshot is not None:
        try:
            idx = json.loads((svc.snapshot.root / "index.json").read_text(encoding="utf-8"))
            keep.update(idx.get("keys", []))
        except (OSError, ValueError):
            pass
    return keep


def prune(svc: Any, budget_bytes: int, now: float | None = None) -> dict[str, int]:
    """Delete least recently used frames and unprotected views until the cache is under TARGET_FRACTION of the
    budget. Returns counts and bytes. Safe to run while serving: a view being built is protected, and a frame read
    that races a deletion is a cache miss (FrameCache.get treats a vanished or corrupt file as a miss)."""
    root = Path(svc.settings.cache_dir)
    items: list[tuple[float, int, Path, str]] = []          # (last use, bytes, path, kind)
    frames = root / "frames"
    if frames.exists():
        for f in frames.rglob("*.fits"):
            try:
                st = f.stat()
            except OSError:
                continue
            meta = f.with_suffix(".json")
            items.append((st.st_mtime, st.st_size + (meta.stat().st_size if meta.exists() else 0), f, "frame"))
    keep = protected_keys(svc)
    vroot = svc.store.root / "views"
    if vroot.exists():
        for d in vroot.iterdir():
            if d.is_dir() and d.name not in keep:
                items.append((_view_used(d), _tree_size(d), d, "view"))
    protected = sum(_tree_size(vroot / k) for k in keep if (vroot / k).is_dir()) if vroot.exists() else 0
    total = sum(b for _, b, _, _ in items) + protected
    out = dict(total_bytes=total, deleted_frames=0, deleted_views=0, freed_bytes=0)
    target = int(budget_bytes * TARGET_FRACTION)
    if total <= budget_bytes:
        return out
    for _, size, path, kind in sorted(items, key=lambda x: x[0]):
        if total <= target:
            break
        try:
            if kind == "frame":
                path.unlink(missing_ok=True)
                path.with_suffix(".json").unlink(missing_ok=True)
                out["deleted_frames"] += 1
            else:
                shutil.rmtree(path, ignore_errors=True)
                out["deleted_views"] += 1
        except OSError:
            continue
        total -= size
        out["freed_bytes"] += size
    out["total_bytes"] = total
    log.info(json.dumps({"event": "cache_prune", **out, "budget_bytes": budget_bytes, "t": now or time.time()}))
    return out


def free_bytes(path: Path) -> int:
    try:
        return shutil.disk_usage(path).free
    except OSError:
        return MIN_FREE_BYTES
