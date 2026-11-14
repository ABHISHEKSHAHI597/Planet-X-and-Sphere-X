"""P-platform-L2 (owner P; engineering record, not a gate criterion). End-to-end plumbing on committed real
fixtures, offline: POST /views for the pinned Barnard view → SSE (planned → fetched → stack_ready band 6 first →
done) → manifest → payloads (sizes match the grid) → server PNG → warm 200 → snapshot package → offline serve.

Fixture mode stacks the ONE committed Barnard frame (the other 358 pinned frames are skipped with a stated
reason), so this record proves format handling and plumbing at L2 only. It is not real-target evidence and does
not count toward G2 (workflow.md §4.1). G2-repro (p_repro.py) is the L3 counterpart on the full pin.

Usage: python scripts/verify/p_platform.py"""
from __future__ import annotations

import importlib.util
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _evidence import record  # noqa: E402
from _p_build import ROOT, build, fixture_services  # noqa: E402

BARNARD = "21a7689afc4b"
BODY = {"q": "Barnard's Star", "pin": BARNARD, "px": "6.15"}


def main() -> int:
    t0 = time.time()
    with tempfile.TemporaryDirectory() as tmp:
        a = build(fixture_services(Path(tmp) / "a"), BODY)
        b = build(fixture_services(Path(tmp) / "b"), BODY)
        m = a["manifest"]
        types = [e["type"] for e in a["events"]]
        first_sr = next((e for e in a["events"] if e["type"] == "stack_ready"), {})
        planned = next((e["n"] for e in a["events"] if e["type"] == "planned"), 0)
        stacked = sorted({f for s in m["stacks"] for f in s["frame_ids"]})
        skipped = [x for s in m["stacks"] for x in s["skipped"]]
        ny, nx = m["grid"]["shape"]
        sizes_ok = all(len(v) == ny * nx * (2 if k.endswith(".f16") else 4) for k, v in a["payloads"].items())

        spec = importlib.util.spec_from_file_location("ms", ROOT / "scripts" / "make_snapshot.py")
        ms = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(ms)
        cache = Path(tmp) / "a"
        idx = ms.package(cache, Path(tmp) / "snap", [m["key"]])

    metrics = {
        "events_order": {"value": f"{types[0]} … {types[-1]} ({len(types)} events)",
                         "threshold": "planned first, done last", "pass": types[0] == "planned" and types[-1] == "done"},
        "planned_frames": {"value": planned, "threshold": "= pin size 359", "pass": planned == 359},
        "first_stack_band": {"value": first_sr.get("band"), "threshold": "selected band (6) first",
                             "pass": first_sr.get("band") == 6},
        "stacked_frames": {"value": len(stacked), "threshold": "= committed fixture frames (1)", "pass": len(stacked) == 1},
        "skipped_with_reason": {"value": len(skipped), "threshold": "every other frame listed with a reason",
                                "pass": all(r for _, r in skipped) and len(skipped) + len(stacked) >= planned},
        "payload_sizes": {"value": f"{len(a['payloads'])} payloads, grid {ny}×{nx}", "threshold": "bytes = ny·nx·itemsize",
                          "pass": sizes_ok},
        "png": {"value": f"HTTP {a.get('png_status')} {a.get('png_bytes')} B", "threshold": "200", "pass": a.get("png_status") == 200},
        "warm_second_request": {"value": f"{b['warm_status']} in {b['warm_s'] * 1000:.0f} ms", "threshold": "ready, ≤ 300 ms (in-process)",
                                "pass": b["warm_status"] == "ready" and b["warm_s"] <= 0.3},
        "repro_fixture": {"value": "identical" if a["payloads"] == b["payloads"] else "DIFFERENT",
                          "threshold": "two cold builds byte-identical (fixture frames only)",
                          "pass": a["payloads"] == b["payloads"]},
        "snapshot_index": {"value": f"{len(idx['keys'])} view(s), pin→key {idx['pins'].get(BARNARD) == m['key']}",
                           "threshold": "packaged and addressable by pin", "pass": idx["pins"].get(BARNARD) == m["key"]},
    }
    ok = all(v["pass"] for v in metrics.values())
    report = (f"**Scope.** Fixture-backed end-to-end run of the API (workflow.md §8.5) at git HEAD; pinned Barnard view "
              f"({BARNARD}), key `{m['key']}`, cold build {a['cold_s']:.1f} s in-process.\n\n"
              "**What this establishes (L2).** The API, job runner, SSE, manifest, payload encodings, PNG renderer, warm "
              "cache and snapshot packaging work on real SPHEREx bytes and real recorded archive answers.\n\n"
              "**What it does not.** Anything about stacks of the science targets: only one real frame is stacked. "
              "G2-repro (scripts/verify/p_repro.py) and the staging perf probe are the L3 evidence.")
    record("P-platform-L2", "L2", "pass" if ok else "fail", metrics, report,
           ["backend/tests/data/real/f2 (committed fixture frames)", "backend/tests/data/real/recorded/coverage",
            f"config/pins/{BARNARD}"], n_frames=len(stacked), pins=[BARNARD],
           code_paths=["backend/app", "scripts/make_snapshot.py"],
           caveats=["fixture-backed: 1 real frame stacked, 358 skipped by design; not real-target evidence",
                    f"runtime {time.time() - t0:.1f} s"], author="P")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
