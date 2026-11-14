"""G2-repro (owner P; workflow.md §6 G2 "Reproducibility: two cold builds of the same pinned view produce
byte-identical .f16 payloads", L3).

Builds the pinned view twice, each with its own empty cache (frames, views and coverage all cold), through the
real API in-process against the live archive, then compares every stack payload byte for byte.

  python scripts/verify/p_repro.py                         Barnard's Star pin 21a7689afc4b, all bands
  python scripts/verify/p_repro.py --pin 325c57328320 --q "WISE 0855-0714"
  CALIB_ROOT=<bootstrapped calibration> python scripts/verify/p_repro.py     (λ maps from the locked set)

Needs network (IRSA). Region does not matter for reproducibility, but the record states where it ran.
A missing CALIB_ROOT does not change stack bytes (λ maps are used by cubes/diffs, not stacks) and is recorded."""
from __future__ import annotations

import argparse
import hashlib
import os
import platform
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _evidence import record  # noqa: E402
from _p_build import build, live_services  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pin", default="21a7689afc4b")
    ap.add_argument("--q", default="Barnard's Star")
    ap.add_argument("--where", default=f"{platform.node()} ({platform.system()})")
    a = ap.parse_args()
    calib = Path(os.environ["CALIB_ROOT"]) if os.environ.get("CALIB_ROOT") else None
    body = {"q": a.q, "pin": a.pin}
    runs = []
    t0 = time.time()
    with tempfile.TemporaryDirectory() as tmp:
        for i in range(2):
            svc = live_services(Path(tmp) / f"run{i}", calib)
            r = build(svc, body)
            # which source served each frame: the pool mixes IRSA cutouts and S3 sections differently on every
            # cold build, which is exactly what the canonical frame window must make irrelevant (decision 0009)
            r["by_source"] = next((j.stats.get("frames_by_source") for j in svc.jobs.jobs.values()
                                   if j.stats.get("frames_by_source")), {})
            runs.append(r)
            print(f"build {i + 1}: key {r['manifest']['key']} cold {r['cold_s']:.1f} s, {len(r['payloads'])} payloads, "
                  f"frames by source {r['by_source']}")
    a0, a1 = runs
    f16 = sorted(k for k in a0["payloads"] if k.endswith(".f16"))
    diff = [k for k in sorted(set(a0["payloads"]) | set(a1["payloads"])) if a0["payloads"].get(k) != a1["payloads"].get(k)]
    stacked = sorted({f for s in a0["manifest"]["stacks"] for f in s["frame_ids"]})
    skipped = sum(len(s["skipped"]) for s in a0["manifest"]["stacks"])
    digest = hashlib.sha256(b"".join(a0["payloads"][k] for k in f16)).hexdigest()[:16]
    errors = [e for r in runs for e in r["events"] if e["type"] == "error"]
    metrics = {
        "same_key": {"value": f"{a0['manifest']['key']} / {a1['manifest']['key']}", "threshold": "equal",
                     "pass": a0["manifest"]["key"] == a1["manifest"]["key"]},
        "f16_payloads": {"value": len(f16), "threshold": "> 0 (every ready stack)", "pass": len(f16) > 0},
        "byte_identical_f16_f32": {"value": "all identical" if not diff else f"{len(diff)} differ: {diff[:5]}",
                                   "threshold": "byte-identical", "pass": not diff},
        "f16_digest": {"value": digest, "threshold": "reported", "pass": None},
        "frames_stacked": {"value": len(stacked), "threshold": "reported", "pass": None},
        "frames_skipped": {"value": skipped, "threshold": "reported (each with a reason)", "pass": None},
        "job_errors": {"value": len(errors), "threshold": "0", "pass": not errors},
        "cold_s": {"value": [round(r["cold_s"], 1) for r in runs], "threshold": "reported (budgets are G2-perf)", "pass": None},
        "frames_by_source": {"value": [r["by_source"] for r in runs], "threshold": "reported", "pass": None},
    }
    ok = all(m["pass"] is not False for m in metrics.values())
    report = (f"**Method.** Two cold in-process builds of pin `{a.pin}` ({a.q}), each with an empty cache, through "
              f"POST /views → SSE → payload GETs, from {a.where}. Compared every `.f16` and `.f32` stack payload.\n\n"
              f"**Result.** {'Byte-identical' if not diff else 'NOT identical'}: {len(f16)} f16 payloads, "
              f"{len(stacked)} frames stacked, {skipped} skipped with reasons.")
    record("G2-repro", "L3", "pass" if ok else "fail", metrics, report,
           [f"config/pins/{a.pin}", "live IRSA archive"], n_frames=len(stacked), pins=[a.pin],
           code_paths=["backend/app/pipeline.py", "backend/app/worker.py", "backend/spherex/stack.py",
                       "backend/spherex/grid.py", "backend/spherex/preprocess.py", "backend/spherex/render.py",
                       "backend/spherex/access/window.py", "backend/spherex/access/failover.py"],
           caveats=([] if calib else ["CALIB_ROOT not set: stacks do not use λ maps, so bytes are unaffected"]) +
                   [f"runtime {time.time() - t0:.0f} s"], author="P", environment=a.where)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
