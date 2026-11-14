"""Pinned frame lists for the 5 acceptance targets (owner D; workflow.md §8.3, G1).

Replays the SIA2 responses recorded by `scripts/verify/f11_coverage.py` (so the pins are reproducible
offline from committed bytes), deduplicates with config/releases.yaml, and writes
config/pins/<pin>.json plus config/pins/index.json (target → pin, params). Existing pins are never
rewritten; a changed frame list yields a new candidate pin and a diff against the current one
(workflow.md §12.4). Usage: python scripts/make_pins.py [--live]
"""
import argparse
import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "scripts/verify"))

from f11_coverage import REC, TARGETS  # noqa: E402

from spherex.access import pins  # noqa: E402
from spherex.access.coverage import TARGET_RADIUS_DEG, CoverageClient  # noqa: E402
from spherex.access.dedup import dedup  # noqa: E402
from spherex.access.http import make_client  # noqa: E402
from spherex.access.releases import load as load_registry  # noqa: E402
from spherex.access.replay import ReplayTransport  # noqa: E402

DEFAULT_FOV = {"barnard": 6, "epsindb": 6, "wise0855": 6, "rwaur": 6, "rdra": 6}   # URL default (impl. §5.3); WISE 0855 ≥ 6′
INDEX = pins.PIN_DIR / "index.json"


async def main(live):
    reg = load_registry()
    idx = json.loads(INDEX.read_text()) if INDEX.exists() else {}
    rec_idx = json.loads((REC / "index.json").read_text())
    async with make_client(None if live else ReplayTransport(REC)) as c:
        cov = CoverageClient(c, reg)
        for name, (ra, dec) in TARGETS.items():
            rows = await cov.sia2(ra, dec, TARGET_RADIUS_DEG, reg.collections())
            res = dedup(rows, reg)
            sia_keys = [k for k in rec_idx if k.startswith("GET https://irsa.ipac.caltech.edu/SIA") and
                        f"CIRCLE+{ra:.7f}+{dec:.7f}" in k.replace("%20", "+")]
            prov = dict(coverage="SIA2 (spherex.access.coverage), " + ("live" if live else "replayed from "
                        + str(REC.relative_to(ROOT))), retrieved=rec_idx[sia_keys[0]]["retrieved"] if sia_keys else None,
                        sia2_rows=len(rows), superseded=len(res.superseded), skipped=res.skipped,
                        registry=str(Path("config/releases.yaml")))
            params = dict(target=name, ra=ra, dec=dec, radius_deg=TARGET_RADIUS_DEG, fov=DEFAULT_FOV[name],
                          center="fixed", collections=reg.collections(), position_note="≈2026.0 position (fixture provenance)")
            p = pins.make_pin(res.frames, reg, params, prov)
            old = idx.get(name)
            if old and old["pin"] != p.pin:
                d = pins.diff(pins.load(old["pin"]).frames, p.frames)
                print(f"{name}: CANDIDATE pin {p.pin} differs from current {old['pin']}: +{len(d['added'])} "
                      f"-{len(d['removed'])} ~{len(d['replaced'])}. Current pin kept (adopt via §12.4).")
                pins.save(p)
                idx[name].setdefault("candidates", [])
                if p.pin not in idx[name]["candidates"]:
                    idx[name]["candidates"].append(p.pin)
                continue
            path = pins.save(p)
            idx[name] = dict(pin=p.pin, frames=len(res.frames), file=str(path.relative_to(ROOT)), params=params,
                             counts=p.doc["counts"])
            print(name, p.pin, len(res.frames), p.doc["counts"]["by_release"])
    INDEX.write_text(json.dumps(idx, indent=1) + "\n")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true")
    asyncio.run(main(ap.parse_args().live))
