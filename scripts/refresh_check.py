"""Data-refresh check (owner D; workflow.md §12.4, docs/data-refresh.md). Run hourly by the watcher job,
and by hand on the event Saturday morning.

  1. Release watcher: list S3, compare with the stored release state, report new planning periods and
     any new top-level release prefix (DR1). Nothing is adopted.
  2. Candidate pins: live SIA2 coverage for the 5 acceptance targets → dedup → diff against the current
     pins (config/pins/index.json). Current pins are never changed; `--write-candidates` stores candidate
     pins next to them and lists them under "candidates" for the §12.4 review.
  3. Writes a JSON report (default: stdout).

Never edits config/releases.yaml: a new collection (DR1) reaches dedup only after a reviewed PR adds it.
Usage: python scripts/refresh_check.py [--state PATH] [--write-candidates] [--out report.json]
"""
import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from spherex.access import pins  # noqa: E402
from spherex.access.coverage import TARGET_RADIUS_DEG, CoverageClient  # noqa: E402
from spherex.access.dedup import dedup  # noqa: E402
from spherex.access.http import make_client  # noqa: E402
from spherex.access.releases import load as load_registry  # noqa: E402
from spherex.access.watcher import check  # noqa: E402

DEFAULT_STATE = Path(os.environ.get("PARALLAX_CACHE", Path.home() / ".cache/parallax")) / "release_state.json"


async def main(a):
    reg = load_registry()
    idx = json.loads((pins.PIN_DIR / "index.json").read_text())
    report = {"registry_releases": [r.id for r in reg.releases]}
    async with make_client(timeout=300) as c:
        report["watcher"] = await check(c, reg, Path(a.state))
        cov = CoverageClient(c, reg)
        report["targets"] = {}
        for name, e in idx.items():
            p = e["params"]
            rows = await cov.sia2(p["ra"], p["dec"], p.get("radius_deg", TARGET_RADIUS_DEG), reg.collections())
            res = dedup(rows, reg)
            cur = pins.load(e["pin"])
            d = pins.diff(cur.frames, res.frames)
            unknown = sorted({r for _, r in res.skipped if "not in config" in r})
            entry = dict(current_pin=e["pin"], candidate_pin=pins.pin_of(res.frames) if res.frames else None,
                         same=d["same"], added=len(d["added"]), removed=len(d["removed"]), replaced=len(d["replaced"]),
                         added_examples=d["added"][:5], removed_examples=d["removed"][:5],
                         unknown_collections=unknown)
            if not d["same"] and a.write_candidates:
                cp = pins.make_pin(res.frames, reg, p, dict(coverage="SIA2 live (refresh_check)", candidate_for=e["pin"]))
                pins.save(cp)
                if cp.pin not in e.setdefault("candidates", []):
                    e["candidates"].append(cp.pin)
            report["targets"][name] = entry
    if a.write_candidates:
        (pins.PIN_DIR / "index.json").write_text(json.dumps(idx, indent=1) + "\n")
    report["action"] = ("no change: demo pins stay; nothing to review" if not report["watcher"]["changed"] and
                        all(t["same"] for t in report["targets"].values()) else
                        "review per docs/data-refresh.md: staging only; re-run L3 checks on candidate pins; "
                        "adopt only through a normal RC (workflow.md §12.4)")
    out = json.dumps(report, indent=1, default=str)
    if a.out:
        Path(a.out).write_text(out)
    print(out)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--state", default=str(DEFAULT_STATE))
    ap.add_argument("--write-candidates", action="store_true")
    ap.add_argument("--out")
    asyncio.run(main(ap.parse_args()))
