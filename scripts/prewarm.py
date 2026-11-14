"""Pre-warm the demo views against a running API (workflow.md §12.4, §10.2 Phase C). Owner P.

  python scripts/prewarm.py --api http://localhost:8000              every view in config/demo_views.yaml
  python scripts/prewarm.py --api https://staging.example --json out.json

For each pinned demo view: POST /api/v1/views, follow the SSE stream to `done`, then fetch the manifest and
every ready stack once (so Caddy/CDN and the browser cache are warm too). Prints cold/warm timings; exits 1 if
any view fails. Its JSON output feeds the G6 checklist (scripts/go_no_go.py)."""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import httpx
import yaml

REPO = Path(__file__).resolve().parents[1]


def build(client: httpx.Client, body: dict, timeout_s: float = 600.0) -> dict:
    t0 = time.monotonic()
    r = client.post("/api/v1/views", json=body)
    r.raise_for_status()
    d = r.json()
    events: list[str] = []
    first_stack = None
    if d["status"] == "queued":
        with client.stream("GET", f"/api/v1/jobs/{d['job_id']}/events", timeout=timeout_s) as s:
            name = None
            for line in s.iter_lines():
                if line.startswith("event: "):
                    name = line[7:]
                    events.append(name)
                    if name == "stack_ready" and first_stack is None:
                        first_stack = time.monotonic() - t0
                    if name == "error":
                        raise RuntimeError(f"job failed: {line}")
                    if name == "done":
                        break
        key = d["key"]
        m = client.get(f"/api/v1/views/{key}/manifest").raise_for_status().json()
    else:
        m = d["manifest"]
        key = m["key"]
    cold = time.monotonic() - t0
    t1 = time.monotonic()
    again = client.post("/api/v1/views", json=body).raise_for_status().json()
    warm = time.monotonic() - t1
    for st in m["stacks"]:
        if st["ready"] and st["frame_ids"]:
            client.get(f"/api/v1/views/{key}/stack/{st['bin']}/{st['band']}.f16").raise_for_status()
    return dict(key=key, status_first=d["status"], status_again=again["status"], cold_s=round(cold, 2),
                warm_s=round(warm, 3), first_stack_s=None if first_stack is None else round(first_stack, 2),
                n_events=len(events), warnings=[w["code"] for w in m["warnings"]], manifest=m)


def extras(client: httpx.Client, m: dict, wanted: list[str], features: dict[str, str]) -> dict[str, str]:
    """Build the derived products the demo script uses (implementation.md §9 pre-warm list), so they are cached
    with the view and packaged by make_snapshot.py. A product whose capability is off here is skipped."""
    key, t = m["key"], m["target"]
    band = int(str(m["params"].get("bands", "6")).split(",")[0]) if str(m["params"].get("bands", "6"))[:1].isdigit() else 6
    full = [b["id"] for b in m["bins"].get(str(band), []) if b["status"] == "full"]
    pos = t["propagated_now"]
    urls = {
        "diff": f"/api/v1/views/{key}/diff?a={full[0]}&b={full[-1]}&band={band}" if len(full) >= 2 else None,
        "blink25": f"/api/v1/views/{key}/blink25",
        "flip": f"/api/v1/views/{key}/frames?band={band}&sort=lambda",
        "spectrum": f"/api/v1/spectrum?ra={pos['ra']}&dec={pos['dec']}&track=1&key={key}",
        "astrometry": f"/api/v1/astrometry?ra={pos['ra']}&dec={pos['dec']}&name={t['name']}&key={key}",
        "lightcurve": f"/api/v1/lightcurve?ra={pos['ra']}&dec={pos['dec']}&key={key}"
                      f"&method={'annulus' if m['params'].get('mask_resolved') == 'bright' else 'psf'}&release=qr2",
    }
    out = {}
    for name in wanted:
        if features.get(name, "off") == "off" or urls.get(name) is None:
            out[name] = "skipped (capability off here, or fewer than two full visits)"
            continue
        r = client.get(urls[name], timeout=1800.0)
        out[name] = f"HTTP {r.status_code}" + ("" if r.status_code == 200 else f": {r.text[:160]}")
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--api", default="http://localhost:8000")
    ap.add_argument("--views", type=Path, default=REPO / "config" / "demo_views.yaml")
    ap.add_argument("--json", type=Path)
    a = ap.parse_args()
    views = yaml.safe_load(a.views.read_text(encoding="utf-8"))["views"]
    out, bad = [], 0
    with httpx.Client(base_url=a.api, timeout=60.0) as c:
        features = c.get("/api/v1/releases").raise_for_status().json().get("features", {})
        for v in views:
            try:
                res = build(c, v["body"])
                res["name"] = v["name"]
                res["extras"] = extras(c, res.pop("manifest"), v.get("extras", []), features)
                print(f"ok   {v['name']:<42} key={res['key']} cold={res['cold_s']}s warm={res['warm_s']}s "
                      f"extras={res['extras']}")
            except Exception as e:  # noqa: BLE001 — report every view, then fail
                bad += 1
                res = dict(name=v["name"], error=repr(e)[:300])
                print(f"FAIL {v['name']:<42} {res['error']}")
            out.append(res)
    if a.json:
        a.json.write_text(json.dumps(out, indent=1), encoding="utf-8")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
