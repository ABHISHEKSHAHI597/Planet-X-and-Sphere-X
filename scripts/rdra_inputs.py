"""R Draconis: deep-field volume and per-frame light-curve inputs for M (owner D; workflow.md §6 target
steward, §10.2). Reads R Dra's pin (config/pins/index.json), fetches each frame's headers from S3 (one
small range walk per frame, no pixels), computes R Dra's parent pixel per frame, and — when the locked
calibration is bootstrapped ($PARALLAX_CALIB) — the CHANNEL_MAP channel and CWAVE λ there.

Output: backend/tests/data/real/rdra_frame_inputs.json.gz (+ provenance): one row per frame with
collection (deep/wide), detector, MJD, x/y, channel, λ, QA and timing keywords. M groups by (detector,
channel, detector region) for the annulus method (implementation.md §4.9); D does not bin or normalise.
"""
import asyncio
import datetime
import gzip
import hashlib
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from spherex.access import pins  # noqa: E402
from spherex.access.deepfield import frame_inputs, inputs_table, volume  # noqa: E402
from spherex.access.http import HostLimiter, make_client  # noqa: E402
from spherex.access.releases import load as load_registry  # noqa: E402
from spherex.access.s3sections import S3SectionSource  # noqa: E402
from spherex.constants import TEST_TARGETS  # noqa: E402

OUT = ROOT / "backend/tests/data/real/rdra_frame_inputs.json.gz"


async def main():
    reg = load_registry()
    idx = json.loads((pins.PIN_DIR / "index.json").read_text())
    pin = pins.load(idx["rdra"]["pin"])
    frames = pin.frames
    ra, dec = TEST_TARGETS["R Dra"][:2]          # Gaia DR3 J2016; R Dra moves 0.2″ over the mission
    calib = None
    cal_root = Path(os.environ.get("PARALLAX_CALIB", Path.home() / ".cache/parallax/calib"))
    try:
        from spherex.calib import Calib
        calib = Calib(cal_root, verify=False)
        calib.channel
    except Exception as e:  # noqa: BLE001
        print("calibration not available, channel/λ left empty:", e)
        calib = None
    vol = volume(frames, lambda c: (reg.release_for_collection(c).id if reg.release_for_collection(c) else c))
    print(json.dumps({k: vol[k] for k in ("frames", "deep", "wide", "by_collection", "by_detector")}))
    async with make_client(timeout=120) as c:
        src = S3SectionSource(c, limiter=HostLimiter({"nasa-irsa-spherex.s3.amazonaws.com": 16}), registry=reg)
        rows = await frame_inputs(src, frames, ra, dec, calib, concurrency=16,
                                  progress=lambda i, n: print(i, n, flush=True) if i % 200 == 0 else None)
    tab = inputs_table(rows)
    tab["volume"] = vol
    tab["pin"] = pin.pin
    tab["target"] = dict(name="R Dra", ra=ra, dec=dec, source="constants.TEST_TARGETS (Gaia DR3 1648328016354496384)")
    tab["errors"] = sum(r.error is not None for r in rows)
    tab["off_detector"] = sum(not r.on_detector for r in rows)
    OUT.write_bytes(gzip.compress(json.dumps(tab, default=str).encode(), 9, mtime=0))
    (OUT.parent / "rdra_frame_inputs.provenance.json").write_text(json.dumps(dict(
        source="S3 header byte ranges of every frame in pin " + pin.pin, retrieved=datetime.date.today().isoformat(),
        calibration=(f"config/calibration.lock {calib.lock.lock_hash()}" if calib else "not used (channel/λ empty)"),
        content="per-frame R Dra parent pixel, channel, λ, header QA/timing; deep vs wide", bytes=OUT.stat().st_size,
        sha256=hashlib.sha256(OUT.read_bytes()).hexdigest(), collected_by="D (scripts/rdra_inputs.py)",
        needed_by="M: lightcurve.py annulus method (G5.lc); I: R Dra fixed-bin axis"), indent=1))
    print("frames", len(rows), "errors", tab["errors"], "off-detector", tab["off_detector"])


def record_evidence():
    """Evidence record from the committed output (no network): volume, coverage of the target pixel,
    channel groups available to M's same-channel annulus method."""
    sys.path.insert(0, str(ROOT / "scripts/verify"))
    from collections import Counter
    from _evidence import record
    d = json.loads(gzip.decompress(OUT.read_bytes()))
    rows = [dict(zip(d["columns"], r)) for r in d["rows"]]
    on = [r for r in rows if r["on_detector"]]
    groups = Counter((r["detector"], r["channel"]) for r in on if r["channel"] not in (0, 18, None))
    v = d["volume"]
    metrics = {
        "frames": {"value": v["frames"], "threshold": "≈2,480 (understanding.md §3.4)", "pass": abs(v["frames"] - 2480) < 50},
        "deep_frames": {"value": v["deep"], "threshold": "≈1,950", "pass": abs(v["deep"] - 1950) < 50},
        "header_errors": {"value": d["errors"], "threshold": "0", "pass": d["errors"] == 0},
        "target_off_detector": {"value": d["off_detector"], "threshold": "reported (circle overlaps, pixel centre outside)", "pass": None},
        "outside_band_ch0_or_18": {"value": sum(r["channel"] in (0, 18) for r in on), "threshold": "reported", "pass": None},
        "qa_pass_frames": {"value": sum(r["hdr_L2DQAFLG"] == "Pass" and r["hdr_FINAST"] == 0 for r in rows),
                           "threshold": "reported (F8)", "pass": None},
        "channel_groups": {"value": len(groups), "threshold": "reported; ≤ 102", "pass": len(groups) <= 102},
        "frames_per_group_min_median": {"value": [min(groups.values()), sorted(groups.values())[len(groups) // 2]],
                                        "threshold": "reported (annulus method needs ≥ 2 per group)", "pass": min(groups.values()) >= 2},
        "by_collection": {"value": v["by_collection"], "threshold": "reported", "pass": None},
    }
    report = f"""
**Scope.** R Draconis data volume and per-frame inputs for M's light curve (workflow.md §6, R Dra steward D;
§10.2 "light-curve input plumbing for M"). Data only: binning, normalisation and the periodogram are M's.

**Method.** The frames of pin {d['pin']} (config/pins). For each, the full-file IMAGE header via S3 byte ranges
(no pixels); R Dra's 0-based parent pixel through that WCS (SIP included); CHANNEL_MAP and CWAVE at that
pixel from the locked calibration (config/calibration.lock); header QA and timing keywords. Output:
`backend/tests/data/real/rdra_frame_inputs.json.gz`.
"""
    record("RDra-inputs", "L3", "pass" if all(m["pass"] in (True, None) for m in metrics.values()) else "fail",
           metrics, report, inputs={"output": str(OUT.relative_to(ROOT)), "pin": d["pin"]}, n_frames=v["frames"],
           calibration=json.loads((ROOT / "config/calibration.lock").read_text())["lock_hash"], pins=[d["pin"]],
           code_paths=["backend/spherex/access/deepfield.py", "scripts/rdra_inputs.py"], author="D")


if __name__ == "__main__":
    if sys.argv[1:] == ["--record"]:
        record_evidence()
    else:
        asyncio.run(main())
