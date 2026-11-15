"""Pre-warm the demo views against a running API (workflow.md §12.4, §10.2 Phase C). Owner P.

  python scripts/prewarm.py --api http://localhost:8000              every view in config/demo_views.yaml
  python scripts/prewarm.py --api https://staging.example --json out.json
  python scripts/prewarm.py --api http://localhost:8010 --stars "Proxima Centauri,Wolf 359"
  python scripts/prewarm.py --api http://localhost:8010 --stars-file config/prewarm_stars.txt --coverage-only

--stars / --stars-file build a view for each named star instead of the demo views, so it keeps working while IRSA is
down: its name lookup, frame list and frames are then on disk, and the API falls back to them (a frame list of any
age, marked "coverage_stale"). --coverage-only saves just the lookup and frame list (seconds per star, no frame
downloads; the frames then come from S3 or IRSA cutouts when the star is opened).

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


def star_names(a: argparse.Namespace) -> list[str]:
    names = [n.strip() for n in (a.stars or "").split(",") if n.strip()]
    if a.stars_file:
        for line in a.stars_file.read_text(encoding="utf-8").splitlines():
            line = line.split("#", 1)[0].strip()
            if line:
                names.append(line)
    return list(dict.fromkeys(names))


def warm_star(client: httpx.Client, name: str, coverage_only: bool, timeout_s: float) -> dict:
    t0 = time.monotonic()
    r = client.get("/api/v1/resolve", params={"q": name}, timeout=120.0)
    if r.status_code != 200:
        raise RuntimeError(f"resolve HTTP {r.status_code}: {r.text[:200]}")
    pos = r.json()["propagated_now"]
    if coverage_only:
        c = client.get("/api/v1/coverage", params={"ra": pos["ra"], "dec": pos["dec"]}, timeout=180.0)
        if c.status_code != 200:
            raise RuntimeError(f"coverage HTTP {c.status_code}: {c.text[:200]}")
        n = c.json()["n_frames"]
        if not n:
            raise RuntimeError("SPHEREx has no frames there in the configured releases")
        return dict(frames=n, seconds=round(time.monotonic() - t0, 1))
    res = build(client, {"q": name, "bands": "6"}, timeout_s)
    res.pop("manifest")
    return res


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--api", default="http://localhost:8000")
    ap.add_argument("--views", type=Path, default=REPO / "config" / "demo_views.yaml")
    ap.add_argument("--json", type=Path)
    ap.add_argument("--stars", help="comma-separated star names to pre-load instead of the demo views")
    ap.add_argument("--stars-file", type=Path, help="one star name per line (# comments allowed)")
    ap.add_argument("--coverage-only", action="store_true", help="with --stars: save lookup + frame list only")
    ap.add_argument("--timeout", type=float, default=900.0, help="seconds per view build (default 900)")
    a = ap.parse_args()
    out, bad = [], 0
    names = star_names(a)
    if names:
        with httpx.Client(base_url=a.api, timeout=60.0) as c:
            for name in names:
                try:
                    res = dict(name=name, **warm_star(c, name, a.coverage_only, a.timeout))
                    print(f"ok   {name:<32} {res}")
                except Exception as e:  # noqa: BLE001 — report every star, then fail
                    bad += 1
                    res = dict(name=name, error=repr(e)[:300])
                    print(f"FAIL {name:<32} {res['error']}")
                out.append(res)
        if a.json:
            a.json.write_text(json.dumps(out, indent=1), encoding="utf-8")
        print(f"{len(names) - bad}/{len(names)} stars pre-loaded")
        return 1 if bad else 0
    views = yaml.safe_load(a.views.read_text(encoding="utf-8"))["views"]
    with httpx.Client(base_url=a.api, timeout=60.0) as c:
        features = c.get("/api/v1/releases").raise_for_status().json().get("features", {})
        for v in views:
            try:
                res = build(c, v["body"], a.timeout)
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
