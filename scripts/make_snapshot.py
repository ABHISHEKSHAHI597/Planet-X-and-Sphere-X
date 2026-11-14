"""Package built views into an offline snapshot (workflow.md §8.5 "snapshot mode", §12.4; implementation.md §9).

  python scripts/make_snapshot.py --cache .cache/parallax --out dist/snapshot            all complete views
  python scripts/make_snapshot.py --cache ... --out ... --keys KEY1,KEY2                  only these

The snapshot directory has the ViewStore layout plus `index.json` (canonical request → key; pin → key) and the
cache's `release_state.json`, so `OFFLINE=1 SNAPSHOT_DIR=<out>` serves exactly the packaged views with no
network. Build the views first with scripts/prewarm.py. Only complete views (every stack written) are packaged:
a half-built view never reaches a demo laptop."""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "backend"))

from app.store import ViewStore, atomic_write  # noqa: E402


def package(cache_dir: Path, out: Path, keys: list[str] | None = None) -> dict:
    src = ViewStore(Path(cache_dir))
    dst = ViewStore(Path(out))
    chosen = keys if keys else src.keys()
    index: dict = {"schema": "parallax-snapshot@1", "views": {}, "pins": {}, "keys": [],
                   "created": datetime.datetime.now(datetime.UTC).isoformat(timespec="seconds")}
    old = Path(out) / "index.json"
    if old.exists():                                         # incremental: keep previously packaged views
        prev = json.loads(old.read_text(encoding="utf-8"))
        for k in ("views", "pins"):
            index[k].update(prev.get(k, {}))
        index["keys"] = list(prev.get("keys", []))
    for key in chosen:
        if not src.complete(key):
            raise SystemExit(f"view {key} is not complete in {cache_dir}; build it first (scripts/prewarm.py)")
        src.copy_view(key, dst)
        m = src.manifest(key) or {}
        if m.get("_request"):
            index["views"][m["_request"]] = key
        if m.get("pin"):
            index["pins"][m["pin"]] = key
        if key not in index["keys"]:
            index["keys"].append(key)
    rs = Path(cache_dir) / "release_state.json"
    if rs.exists():
        shutil.copy2(rs, Path(out) / "release_state.json")
    digest = hashlib.sha256()
    for p in sorted((Path(out) / "views").rglob("*")):
        if p.is_file():
            digest.update(p.relative_to(out).as_posix().encode())
            digest.update(p.read_bytes())
    index["content_sha256"] = digest.hexdigest()
    atomic_write(Path(out) / "index.json", json.dumps(index, indent=1, sort_keys=True).encode())
    return index


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cache", type=Path, default=REPO / ".cache" / "parallax")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--keys", default="")
    a = ap.parse_args()
    idx = package(a.cache, a.out, [k for k in a.keys.split(",") if k] or None)
    print(f"snapshot {a.out}: {len(idx['keys'])} views, sha256 {idx['content_sha256'][:16]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
