"""Record the pinned demo views as static files: ParallaX Lite (optimisation.md item 0.3; advanced_research.md A1).

  python scripts/make_lite.py --api http://localhost:8000                    every view in config/demo_views.yaml
  python scripts/make_lite.py --api ... --out frontend/dist-lite/lite --environment staging

Run it against an API that has the views built (scripts/prewarm.py first; live or OFFLINE=1 with a snapshot).
For each view it stores the API's own answers: the manifest, every ready stack (.f16) and its flags (.flags.u32),
the resolver's answer for the name, and the derived products that a static copy can serve and whose capability
is shown in `--environment` (25-year blink, exposure flipbook, λ-range RGB). The frontend built with VITE_LITE=1
(`npm run build:lite`) reads these files through `frontend/src/api/lite.ts` and needs no server.

A view that is not built is skipped and reported; the exit code is 1 if any view is missing. File names follow
`lite_file`, the same rule as `liteFile` in lite.ts (backend/tests/unit/test_lite_export.py holds both to it)."""
from __future__ import annotations

import argparse
import datetime
import json
import re
import shutil
import sys
from pathlib import Path
from typing import Any
from urllib.parse import unquote

import httpx
import yaml

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "backend"))

from app.settings import effective_features, load_features  # noqa: E402

API = "/api/v1"
MATCH_KEYS = ("q", "ra", "dec", "fov", "px", "axis", "center", "mask", "rel", "pin", "lim")
# Capabilities a static copy can serve: they need only the manifest, recorded payloads, or a third-party service the
# browser calls itself (Aladin). Everything else (measurements on demand, exports, reports) needs the server.
STATIC_CAPABLE = ("blink", "coverage", "resolve", "pins", "flags_overlay", "freshness", "embed", "aladin",
                  "rgb", "blink25", "flip")
RGB_PRESETS = ("methane", "ice", "thermal")
_UNSAFE = re.compile(r"[^A-Za-z0-9._-]")


def lite_file(path_and_query: str) -> str:
    """Static file of a GET (mirror of `liteFile`, frontend/src/api/lite.ts)."""
    path, _, query = path_and_query.partition("?")
    segs = [_UNSAFE.sub("_", unquote(s)) for s in path.split("/") if s]
    name = "api/" + "/".join(segs)
    if segs and re.search(r"\.[A-Za-z0-9]+$", segs[-1]):
        return name
    q = _UNSAFE.sub("_", "&".join(sorted(unquote(p) for p in query.split("&") if p)))
    return f"{name}{'@' + q if q else ''}.json"


class Recorder:
    def __init__(self, client: httpx.Client, out: Path) -> None:
        self.client, self.out = client, out
        self.files = 0
        self.bytes = 0

    def write(self, name: str, data: bytes) -> None:
        p = self.out / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
        self.files += 1
        self.bytes += len(data)

    def get(self, path: str, timeout: float = 600.0) -> httpx.Response | None:
        """Record one GET under its static name. None when the API does not have it."""
        r = self.client.get(API + path, timeout=timeout)
        if r.status_code != 200:
            return None
        self.write(lite_file(path), r.content)
        return r

    def get_json_with_payloads(self, path: str) -> Any | None:
        """A JSON answer plus every server-relative payload URL it names."""
        r = self.get(path)
        if r is None:
            return None
        body = r.json()
        for url in sorted(set(_payload_urls(body))):
            self.get(url[len(API):])
        return body


def _payload_urls(node: Any) -> list[str]:
    if isinstance(node, str):
        return [node] if node.startswith(API + "/") else []
    if isinstance(node, dict):
        return [u for v in node.values() for u in _payload_urls(v)]
    if isinstance(node, list):
        return [u for v in node for u in _payload_urls(v)]
    return []


def record_view(rec: Recorder, body: dict[str, Any], features: dict[str, str]) -> dict[str, Any] | None:
    r = rec.client.post(API + "/views", json=body)
    if r.status_code != 200 or r.json().get("status") != "ready":
        return None
    m = r.json()["manifest"]
    key = m["key"]
    if any(st.get("filled") for st in m["stacks"]) and features.get("bright_fill", "off") == "off":
        # Model-filled cores are display-only and unvalidated: never freeze them into a copy that does not show the
        # capability (an API whose view keys predate the `fill` key component could hand them over).
        print(f"REFUSED {key}: its stacks carry model-filled cores, and bright_fill is off in this copy")
        return None
    rec.write(lite_file(f"/views/{key}/manifest"), json.dumps(m, separators=(",", ":")).encode())
    for st in m["stacks"]:
        if st["ready"] and st["frame_ids"]:
            for ext in ("f16", "flags.u32"):
                rec.get(f"/views/{key}/stack/{st['bin']}/{st['band']}.{ext}")
    shown = lambda cap: features.get(cap, "off") != "off"       # noqa: E731
    if shown("blink25") and (m.get("target") or {}).get("kind") == "star":
        rec.get_json_with_payloads(f"/views/{key}/blink25")
    bands = str(body.get("bands", "6"))
    band = int(bands[0]) if bands[:1].isdigit() else 6
    if shown("flip"):
        for sort in ("lambda", "time"):
            rec.get_json_with_payloads(f"/views/{key}/frames?band={band}&sort={sort}")
    if shown("rgb"):
        for b in m["bins"].get("4", []):
            for preset in RGB_PRESETS:
                rec.get(f"/views/{key}/rgb/{b['id']}/{preset}.f16")
    return m


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--api", default="http://localhost:8000")
    ap.add_argument("--views", type=Path, default=REPO / "config" / "demo_views.yaml")
    ap.add_argument("--out", type=Path, default=REPO / "frontend" / "dist-lite" / "lite")
    ap.add_argument("--environment", default="staging", choices=("staging", "production", "local"),
                    help="whose flag levels the copy shows (config/features.yaml); a public copy is `staging` or `production`")
    a = ap.parse_args()

    cfg = load_features(REPO / "config" / "features.yaml")
    features = {name: (level if name in STATIC_CAPABLE else "off")
                for name, level in effective_features(cfg, a.environment).items()}
    if a.out.exists():
        shutil.rmtree(a.out)
    views = yaml.safe_load(a.views.read_text(encoding="utf-8"))["views"]
    index: dict[str, Any] = {"schema": "parallax-lite@1", "views": [], "resolve": {},
                             "created": datetime.datetime.now(datetime.UTC).isoformat(timespec="seconds")}
    missing: list[str] = []
    with httpx.Client(base_url=a.api, timeout=120.0) as c:
        rec = Recorder(c, a.out)
        rel = c.get(API + "/releases").raise_for_status().json()
        # `snapshot` stays false: the frontend keeps the chosen environment's flag levels and shows its own
        # "frozen copy" banner for the Lite transport (components/Badges.tsx).
        rel.update(features=features, environment=a.environment, snapshot=False)
        rec.write("releases.json", json.dumps(rel, separators=(",", ":")).encode())
        for v in views:
            body = v["body"]
            m = record_view(rec, body, features)
            if m is None:
                missing.append(v["name"])
                print(f"MISSING {v['name']}: not built on {a.api}; the request has queued its build "
                      f"(run scripts/prewarm.py and wait for it, then run this again)")
                continue
            index["views"].append({"key": m["key"], "name": v["name"], "match": {k: str(body[k]) for k in MATCH_KEYS if k in body}})
            if body.get("q") and body["q"] not in index["resolve"]:
                r = c.get(API + "/resolve", params={"q": body["q"]})
                if r.status_code == 200:
                    index["resolve"][body["q"]] = r.json()
            print(f"ok      {v['name']:<60} key={m['key']}")
        rec.write("index.json", json.dumps(index, indent=1, sort_keys=True).encode())
    page = a.out.parent / "index.html"
    if page.exists():
        # The app's routes as real pages, so a static host answers them with 200 (a 404 answer, even with the app
        # in it, reads as a dead link to link checkers and web filters); 404.html catches anything else. Asset
        # paths are absolute (vite `base`), so the same file works one directory down.
        for route in ("embed", "about", "proof"):
            (a.out.parent / route).mkdir(exist_ok=True)
            shutil.copy2(page, a.out.parent / route / "index.html")
        shutil.copy2(page, a.out.parent / "404.html")
    print(f"lite {a.out}: {len(index['views'])} views, {rec.files} files, {rec.bytes / 1e6:.1f} MB"
          f" · features shown: {', '.join(k for k, lv in sorted(features.items()) if lv != 'off')}")
    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main())
