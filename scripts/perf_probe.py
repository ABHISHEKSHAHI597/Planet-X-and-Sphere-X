"""Performance probe (workflow.md §6 G2 "Cold and warm performance measured from staging", §9.5 nightly;
implementation.md §6.7, §10.3). Owner P (with D for the IRSA side).

  python scripts/perf_probe.py --api https://staging.example --where "us-east-1 VM (t3.xlarge)" [--record]

For each pinned demo view (config/demo_views.yaml): first stack time, full view time, warm manifest latency,
warm all-stacks latency and payload bytes, compared with the budgets below. "Cold" is only cold when the
server's view cache does not hold the view yet: run right after a deploy with an empty cache volume, or pass
--cold-cache-confirmed when you emptied it. The record is G2-perf (L3) — `inconclusive` unless it ran from
the deployment region against a confirmed cold cache (§10.3 budgets are defined for a us-east-1 VM)."""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import httpx
import yaml

ROOT = Path(__file__).resolve().parents[1]
BUDGET = {"first_stack_cold_p50_s": 30.0, "full_cold_p50_s": 90.0, "full_cold_p95_s": 180.0,
          "warm_manifest_s": 0.3, "warm_all_stacks_s": 1.0, "payload_mb": 3.0}


def probe(c: httpx.Client, body: dict) -> dict:
    t0 = time.monotonic()
    d = c.post("/api/v1/views", json=body).raise_for_status().json()
    first = None
    if d["status"] == "queued":
        with c.stream("GET", f"/api/v1/jobs/{d['job_id']}/events", timeout=900) as s:
            for line in s.iter_lines():
                if line.startswith("event: stack_ready") and first is None:
                    first = time.monotonic() - t0
                if line.startswith("event: error"):
                    raise RuntimeError("job error")
                if line.startswith("event: done"):
                    break
        key, cold = d["key"], True
    else:
        key, cold = d["manifest"]["key"], False
    full = time.monotonic() - t0
    t1 = time.monotonic()
    m = c.get(f"/api/v1/views/{key}/manifest").raise_for_status().json()
    warm_manifest = time.monotonic() - t1
    t2 = time.monotonic()
    nbytes = 0
    for st in m["stacks"]:
        if st["ready"] and st["frame_ids"]:
            nbytes += len(c.get(f"/api/v1/views/{key}/stack/{st['bin']}/{st['band']}.f16").raise_for_status().content)
    warm_stacks = time.monotonic() - t2
    return dict(key=key, cold=cold, first_stack_s=first, full_s=full, warm_manifest_s=warm_manifest,
                warm_all_stacks_s=warm_stacks, payload_mb=nbytes / 1e6)


def pct(xs: list[float], q: float) -> float | None:
    xs = sorted(x for x in xs if x is not None)
    if not xs:
        return None
    return xs[min(len(xs) - 1, int(round(q * (len(xs) - 1))))]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--api", required=True)
    ap.add_argument("--where", required=True, help="where the probe ran, e.g. 'us-east-1 VM'")
    ap.add_argument("--views", type=Path, default=ROOT / "config" / "demo_views.yaml")
    ap.add_argument("--cold-cache-confirmed", action="store_true")
    ap.add_argument("--record", action="store_true", help="write a G2-perf evidence record")
    ap.add_argument("--json", type=Path)
    a = ap.parse_args()
    views = yaml.safe_load(a.views.read_text(encoding="utf-8"))["views"]
    rows = []
    with httpx.Client(base_url=a.api, timeout=120) as c:
        for v in views:
            try:
                r = probe(c, v["body"])
            except Exception as e:  # noqa: BLE001
                r = dict(error=repr(e)[:200])
            r["name"] = v["name"]
            rows.append(r)
            print(json.dumps(r))
    ok_rows = [r for r in rows if "error" not in r]
    cold_rows = [r for r in ok_rows if r["cold"]]
    stats = {
        "first_stack_cold_p50_s": pct([r["first_stack_s"] for r in cold_rows], 0.5),
        "full_cold_p50_s": pct([r["full_s"] for r in cold_rows], 0.5),
        "full_cold_p95_s": pct([r["full_s"] for r in cold_rows], 0.95),
        "warm_manifest_s": max((r["warm_manifest_s"] for r in ok_rows), default=None),
        "warm_all_stacks_s": max((r["warm_all_stacks_s"] for r in ok_rows), default=None),
        "payload_mb": max((r["payload_mb"] for r in ok_rows), default=None),
    }
    metrics = {k: {"value": None if v is None else round(v, 3), "threshold": f"≤ {BUDGET[k]}",
                   "pass": None if v is None else v <= BUDGET[k]} for k, v in stats.items()}
    metrics["errors"] = {"value": len(rows) - len(ok_rows), "threshold": "0", "pass": len(ok_rows) == len(rows)}
    metrics["cold_views"] = {"value": len(cold_rows), "threshold": "all views cold (confirmed empty cache)",
                             "pass": a.cold_cache_confirmed and len(cold_rows) == len(rows)}
    in_region = "us-east-1" in a.where.lower()
    if a.json:
        a.json.write_text(json.dumps(dict(rows=rows, stats=stats), indent=1), encoding="utf-8")
    if a.record:
        sys.path.insert(0, str(ROOT / "scripts"))
        from validate import record
        if not in_region or not a.cold_cache_confirmed:
            verdict = "inconclusive"
        else:
            verdict = "pass" if all(m["pass"] is not False for m in metrics.values()) else "fail"
        record("G2-perf", "L3", verdict, metrics,
               f"**Method.** {len(rows)} pinned demo views against {a.api} from {a.where}. Budgets: implementation.md "
               f"§6.7 and §10.3. Recorded even if missed (G2).",
               [a.api, str(a.views.relative_to(ROOT))], pins=[v["body"].get("pin", "") for v in views],
               code_paths=["backend/app", "backend/spherex/access"], author="P", environment=a.where,
               caveats=([] if in_region else ["not run from the deployment region (us-east-1): budgets not assessable"]) +
                       ([] if a.cold_cache_confirmed else ["server cache not confirmed empty: cold numbers unreliable"]))
    bad = [k for k, m in metrics.items() if m["pass"] is False]
    print("budget misses:", bad or "none")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
