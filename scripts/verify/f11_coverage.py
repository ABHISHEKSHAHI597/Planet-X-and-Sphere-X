"""F11 (owner D): does the SIA2 response contain the columns coverage needs, and does it return the same
frame set as TAP after dedup? For all 5 acceptance targets; counts reconciled with understanding.md §3.4
and with the 2026-11-06 coverage fixture (frames_5targets.json), so every difference is explained.

Live mode records every SIA2/TAP response under backend/tests/data/real/recorded/coverage/ (the
"saved SIA2 and TAP responses" fixture of workflow.md §8.2); --replay reruns the check offline on them.

Usage: python scripts/verify/f11_coverage.py [--replay]
"""
import argparse
import asyncio
import json
import sys
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).parents[2]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(Path(__file__).parent))

from spherex.access.coverage import REQUIRED_SIA_COLUMNS, SIA, CoverageClient, sia2_params  # noqa: E402
from spherex.access.dedup import FileInfo, dedup  # noqa: E402
from spherex.access.http import make_client  # noqa: E402
from spherex.access.releases import load as load_registry  # noqa: E402
from spherex.access.replay import RecordingTransport, ReplayTransport  # noqa: E402
from spherex.external.tap import parse_votable  # noqa: E402

REC = ROOT / "backend/tests/data/real/recorded/coverage"
FIX = ROOT / "backend/tests/data/real/frames_5targets.json"
# The 2026.0 positions of the committed coverage fixture (its provenance), so counts are comparable.
TARGETS = {"barnard": (269.4461, 4.7707), "epsindb": (331.0918, -56.7966), "wise0855": (133.7578, -7.2420),
           "rwaur": (76.95654, 30.40130), "rdra": (248.16733, 66.75502)}
# understanding.md §3.4 (✅ 11-05/11-06), as stated there
DOC = {"barnard": (359, "359"), "epsindb": (447, "449 (✅ 11-06: 447 SIA2 rows)"), "wise0855": (256, "256, all QR2"),
       "rwaur": (333, "333"), "rdra": (2480, "≈2,480 (≈1,950 deep)")}
PAIRS = {frozenset((1, 4)), frozenset((2, 5)), frozenset((3, 6))}
IOC_MJD = 60796.0


def fixture_rows():
    d = json.loads(FIX.read_text())
    out = {}
    for r in d["rows"]:
        r = dict(zip(d["columns"], r))
        out.setdefault(r["target"], set()).add(r["s3_key"])
    return out


async def main(replay):
    from _evidence import record
    reg = load_registry()
    colls = reg.collections()
    transport = ReplayTransport(REC) if replay else RecordingTransport(REC)
    old = fixture_rows()
    per, metrics, all_ok = {}, {}, True
    async with make_client(transport, timeout=300) as c:
        cov = CoverageClient(c, reg)
        for name, (ra, dec) in TARGETS.items():
            raw = (await c.get(SIA, params=sia2_params(ra, dec, 0.001, colls))).content
            cols = list(parse_votable(raw)[0].keys())
            t0 = time.perf_counter()
            sia = await cov.sia2(ra, dec, 0.001, colls)
            ts = time.perf_counter() - t0
            t0 = time.perf_counter()
            tap = await cov.tap(ra, dec, colls)
            tt = time.perf_counter() - t0
            ds, dt = dedup(sia, reg), dedup(tap, reg)
            ks, kt = {f.access_url for f in ds.frames}, {f.access_url for f in dt.frames}
            only_s, only_t = sorted(ks - kt), sorted(kt - ks)
            fr = ds.frames
            by_obs = {}
            for f in fr:
                by_obs.setdefault(f.obs_id, set()).add(f.detector)
            pair_frac = sum(frozenset(v) in PAIRS for v in by_obs.values()) / max(len(by_obs), 1)
            keys_now = {f.s3_key for f in fr}
            keys_old = old.get(name, set())
            new_since = sorted(keys_now - keys_old)
            gone = sorted(keys_old - keys_now)
            periods_new = Counter(k.split("/")[2] for k in new_since)
            per[name] = dict(
                sia2_rows=len(sia), tap_rows=len(tap), sia2_frames=len(ds.frames), tap_frames=len(dt.frames),
                sia2_superseded=len(ds.superseded), tap_superseded=len(dt.superseded),
                sia2_skipped=ds.skipped[:5], tap_skipped=dt.skipped[:5], only_sia2=only_s[:20], only_tap=only_t[:20],
                n_only_sia2=len(only_s), n_only_tap=len(only_t), identical=not only_s and not only_t,
                missing_columns=[x for x in REQUIRED_SIA_COLUMNS if x not in cols],
                by_collection=dict(Counter(f.collection for f in fr)), by_detector=dict(sorted(Counter(f.detector for f in fr).items())),
                ioc_frames=sum(f.t_min < IOC_MJD for f in fr), retry_files=sum(bool(FileInfo.parse(f.access_url).retry) for f in fr),
                psffix_files=sum(bool(FileInfo.parse(f.access_url).psffix) for f in fr),
                coaligned_pair_fraction=round(pair_frac, 4), seconds_sia2=round(ts, 1), seconds_tap=round(tt, 1),
                fixture_2026_11_06=len(keys_old), new_since_fixture=len(new_since), new_periods=dict(periods_new),
                gone_since_fixture=len(gone), gone_examples=gone[:5], doc_count=DOC[name][1])
            ok = per[name]["identical"] and not per[name]["missing_columns"]
            all_ok &= ok
            metrics[f"{name}_sia2_eq_tap"] = {"value": f"{len(ks)} vs {len(kt)}; only SIA2 {len(only_s)}, only TAP {len(only_t)}",
                                              "threshold": "identical deduplicated sets", "pass": ok}
            metrics[f"{name}_vs_doc"] = {"value": f"{len(fr)} now; {len(keys_old)} on 2026-11-06; doc {DOC[name][1]}; "
                                                  f"+{len(new_since)} new ({dict(periods_new)}), -{len(gone)} gone",
                                         "threshold": "every difference explained", "pass": None}
            print(name, json.dumps({k: per[name][k] for k in ("sia2_rows", "tap_rows", "sia2_frames", "tap_frames",
                                                                "identical", "new_since_fixture", "gone_since_fixture",
                                                                "by_collection")}), flush=True)
    metrics["sia2_required_columns"] = {"value": "present" if all(not p["missing_columns"] for p in per.values()) else
                                        {n: p["missing_columns"] for n, p in per.items()},
                                        "threshold": ", ".join(REQUIRED_SIA_COLUMNS), "pass": all(not p["missing_columns"] for p in per.values())}
    rows = "\n".join(f"| {n} | {p['sia2_rows']} / {p['tap_rows']} | {p['sia2_frames']} / {p['tap_frames']} | "
                     f"{'yes' if p['identical'] else 'NO'} | {p['by_collection']} | {p['ioc_frames']} | {p['retry_files']} | "
                     f"{p['coaligned_pair_fraction']} | {p['fixture_2026_11_06']} → {p['sia2_frames']} "
                     f"(+{p['new_since_fixture']} {p['new_periods']}, −{p['gone_since_fixture']}) | {p['doc_count']} |"
                     for n, p in per.items())
    report = f"""
**Question (F11).** Does the SIA2 response carry the columns coverage needs, and does it return the same
frame set as TAP after dedup? Outcome: see verdict and per-target table.

**Method.** For each target, one SIA2 call with all four registry collections (radius 0.001°, the
target-centred default) and one TAP call (`CONTAINS(POINT, p.poly)` over plane ⋈ artifact ⋈ observation,
the same collections), both through `spherex.access.coverage`, then `spherex.access.dedup` with
`config/releases.yaml`. Deduplicated access URLs are compared as sets. Counts are reconciled against
understanding.md §3.4 and against the committed 2026-11-06 coverage fixture (`frames_5targets.json`,
same positions): frames added since then are attributed to their planning periods. Responses are
recorded in `backend/tests/data/real/recorded/coverage/` ({'replayed' if replay else 'recorded live'}).

| target | rows SIA2 / TAP | frames after dedup SIA2 / TAP | identical | collections | IOC | `_retry` | pair fraction | vs 2026-11-06 fixture | understanding.md §3.4 |
|---|---|---|---|---|---|---|---|---|---|
{rows}

"pair fraction" = obs ids whose frames are exactly one co-aligned pair (D1+D4, D2+D5, D3+D6); the rest
are single-detector edge cases (understanding.md §3.3: 178 of 181 for Barnard).
"""
    d = record("F11", "L3", "pass" if all_ok else "fail", metrics, report,
               inputs={"positions": TARGETS, "collections": colls, "recorded": str(REC.relative_to(ROOT))},
               n_frames=sum(p["sia2_frames"] for p in per.values()),
               code_paths=["backend/spherex/access/coverage.py", "backend/spherex/access/dedup.py",
                           "config/releases.yaml"], author="D")
    (d / "per_target.json").write_text(json.dumps(per, indent=1))


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--replay", action="store_true")
    asyncio.run(main(p.parse_args().replay))
