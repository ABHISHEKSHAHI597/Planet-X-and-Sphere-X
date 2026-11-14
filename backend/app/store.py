"""Content-addressed view store (implementation.md §2.3 "Cache by content"; §9 snapshot mode).

Layout, identical for the live cache and for a snapshot directory (so make_snapshot.py is a copy):
  <root>/views/<key>/manifest.json
  <root>/views/<key>/stack/<bin>/<band>.{f16,f32,var.f32,flags.u32,filled.u8}
  <root>/views/<key>/diff/<a>/<b>/<band>.{f16,json}
  <root>/views/<key>/frames/<band>/<frame-digest>.f16   exposure flipbook (one gridded frame each)
  <root>/views/<key>/rgb/<bin>/<preset>.f16             λ-range RGB composites (3 planes)
  <root>/views/<key>/blink25/{index.json,<i>.f16}           25-year blink epochs on the blink grid
  <root>/views/<key>/frames/<band>/index.json          frame id, MJD, λ at target, digest
  <root>/index.json      (snapshot only) canonical request → key, resolve answers, coverage answers
Writes are atomic (temp file + rename), so a crash never leaves a half payload that a reader trusts."""

from __future__ import annotations

import json
import os
import re
import shutil
import threading
from pathlib import Path
from typing import Any

_SAFE = re.compile(r"^[A-Za-z0-9_.:+-]{1,64}$")
STACK_EXTS = ("f16", "f32", "var.f32", "flags.u32", "filled.u8")


class UnsafePath(ValueError):
    """A key, bin id or payload name from a request that cannot name a store path: HTTP 400 (audit B-07)."""


def _safe(*parts: str) -> None:
    for p in parts:
        if not isinstance(p, str) or not _SAFE.match(p) or p in (".", ".."):
            raise UnsafePath(f"invalid view key, bin or payload name {str(p)[:80]!r}")


def atomic_write(p: Path, data: bytes) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    # pid + thread id: two threads writing one path must not share a temporary file (audit K-11)
    tmp = p.with_name(f"{p.name}.tmp{os.getpid()}.{threading.get_ident()}")
    tmp.write_bytes(data)
    tmp.replace(p)


class ViewStore:
    def __init__(self, root: Path) -> None:
        self.root = Path(root)

    def vdir(self, key: str) -> Path:
        _safe(key)
        return self.root / "views" / key

    def manifest(self, key: str) -> dict[str, Any] | None:
        p = self.vdir(key) / "manifest.json"
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None

    def put_manifest(self, key: str, m: dict[str, Any]) -> None:
        atomic_write(self.vdir(key) / "manifest.json", json.dumps(m, indent=None, sort_keys=True).encode())

    def complete(self, key: str) -> bool:
        m = self.manifest(key)
        if not m:
            return False
        return all(s["ready"] for s in m["stacks"]) and bool(m.get("_complete"))

    def stack_path(self, key: str, bin_id: str, band: int, ext: str) -> Path:
        if ext not in STACK_EXTS:
            raise UnsafePath(f"unknown stack payload {ext!r}")
        _safe(bin_id)
        return self.vdir(key) / "stack" / bin_id / f"{int(band)}.{ext}"

    def put_stack(self, key: str, bin_id: str, band: int, payloads: dict[str, bytes]) -> None:
        for ext, data in payloads.items():
            atomic_write(self.stack_path(key, bin_id, band, ext), data)

    def diff_path(self, key: str, a: str, b: str, band: int, ext: str) -> Path:
        _safe(a, b)
        if ext not in ("f16", "json"):
            raise UnsafePath(f"unknown difference payload {ext!r}")
        return self.vdir(key) / "diff" / a / b / f"{int(band)}.{ext}"

    def frame_path(self, key: str, band: int, name: str) -> Path:
        """Flipbook payloads: `<digest>.f16` (16 hex) or `index.json`."""
        if name != "index.json" and not re.fullmatch(r"[0-9a-f]{16}\.f16", name):
            raise UnsafePath(f"unknown flipbook payload {name!r}")
        return self.vdir(key) / "frames" / str(int(band)) / name

    def rgb_path(self, key: str, bin_id: str, preset: str) -> Path:
        _safe(bin_id, preset)
        return self.vdir(key) / "rgb" / bin_id / f"{preset}.f16"

    def cube_path(self, key: str, bin_id: str, band: int) -> Path:
        _safe(bin_id)
        return self.vdir(key) / "cube" / bin_id / f"{int(band)}.f16"

    def blink25_path(self, key: str, name: str) -> Path:
        """25-year blink payloads: `<i>.f16` (epoch index) or `index.json`."""
        if name != "index.json" and not re.fullmatch(r"[0-9]{1,2}\.f16", name):
            raise UnsafePath(f"unknown 25-year blink payload {name!r}")
        return self.vdir(key) / "blink25" / name

    def copy_view(self, key: str, dest: ViewStore) -> None:
        src = self.vdir(key)
        if not src.exists():
            raise FileNotFoundError(key)
        shutil.copytree(src, dest.vdir(key), dirs_exist_ok=True)

    def keys(self) -> list[str]:
        d = self.root / "views"
        return sorted(p.name for p in d.iterdir()) if d.exists() else []


def find(svc: Any, method: str, *args: Any) -> Path:
    """Path of a derived product (diff, flipbook, RGB, 25-year blink, cube): the live store's copy, else the
    offline snapshot's (implementation.md §9 snapshot mode), else the live path for a new build."""
    p: Path = getattr(svc.store, method)(*args)
    if not p.exists() and getattr(svc, "snapshot", None) is not None:
        q: Path = getattr(svc.snapshot, method)(*args)
        if q.exists():
            return q
    return p
