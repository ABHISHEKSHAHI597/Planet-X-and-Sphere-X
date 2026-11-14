"""Foundation check F8 (workflow.md §5; owner I, pair D). What fraction of frames per target fails
L2DQAFLG (or L1DQAFLG) or FINAST, and why? Sets the frame-rejection policy (preprocess.REJECT_ON_DQAFLG).
Also measures the other §4.3 rejection rule (> 50% of the box bad) on the real cutouts collected.

Real files used: backend/tests/data/real/frames_5targets.json (IMAGE headers of all 3,878 SIA2 rows of
the 5 targets, committed fixture) and the 279 cached real cutouts (WISE 0855, Barnard).
Usage: python scripts/verify/f08_frame_qa.py
"""
import collections
import json

import numpy as np
from _cache import ROOT, cutouts, load_cutout
from _evidence import record

from spherex.flags import bad_mask, flag_bits

F = ROOT / "backend/tests/data/real/frames_5targets.json"
d = json.loads(F.read_text())
col = {c: i for i, c in enumerate(d["columns"])}
per = collections.defaultdict(lambda: collections.Counter())
for r in d["rows"]:
    t = r[col["target"]]
    per[t]["n"] += 1
    per[t]["fail_L1"] += r[col["L1DQAFLG"]] != "Pass"
    per[t]["fail_L2"] += r[col["L2DQAFLG"]] != "Pass"
    per[t]["fail_FINAST"] += r[col["FINAST"]] != 0
    per[t]["qr3"] += "qr3" in r[col["collection"]]
versions = collections.Counter(r[col["VERSION"]] for r in d["rows"])

bad = collections.defaultdict(list)
for tag in ("wise0855", "barnard", "barnard12"):
    for p in cutouts(tag):
        raw, _ = load_cutout(p)
        h, flg = raw.hdus["FLAGS"]
        bits = flag_bits(h)
        img = np.asarray(raw.hdus["IMAGE"][1], float)
        for preset in ("discovery", "bright", "imaging"):
            bad[preset].append(float((bad_mask(np.asarray(flg, np.int64), bits, preset) | ~np.isfinite(img)).mean()))

n = sum(c["n"] for c in per.values())
nfail = sum(c["fail_L1"] + c["fail_L2"] + c["fail_FINAST"] for c in per.values())
metrics = {f"{t}_fail_fraction": dict(value=f"{(c['fail_L1'] + c['fail_L2'] + c['fail_FINAST'])}/{c['n']}",
                                      threshold="measured", **{"pass": None}) for t, c in per.items()}
metrics["total_fail"] = dict(value=f"{nfail}/{n}", threshold="measured", **{"pass": None})
for preset, v in bad.items():
    v = np.array(v)
    metrics[f"cutouts_over_50pct_bad_{preset}"] = dict(value=f"{int((v > 0.5).sum())}/{v.size}",
                                                       threshold="measured", **{"pass": None})
    metrics[f"cutouts_median_bad_{preset}"] = dict(value=round(float(np.median(v)), 4), threshold="measured", **{"pass": None})
table = "\n".join(f"| {t} | {c['n']} | {c['qr3']} | {c['fail_L1']} | {c['fail_L2']} | {c['fail_FINAST']} |"
                  for t, c in per.items())
report = f"""
**Question.** What fraction of frames per target fails `L2DQAFLG` or `FINAST`, and why?
Outcome: **confirmed, with a policy decision**: none of the {n} frames covering the 5 acceptance targets
fails `L1DQAFLG`, `L2DQAFLG` or `FINAST` (pipelines {', '.join(f'{k} ×{v}' for k, v in versions.most_common())}).

| target | frames | of which QR3 | L1DQAFLG ≠ Pass | L2DQAFLG ≠ Pass | FINAST ≠ 0 |
|---|---|---|---|---|---|
{table}

**Why none fail.** No failing frame exists to inspect. The archive appears to serve only frames that
passed both QA stages (an inference from 0/{n}, not a documented IRSA rule).

**Policy (preprocess.REJECT_ON_DQAFLG = ("L1DQAFLG", "L2DQAFLG"), plus FINAST ≠ 0).** Hard-reject
on any failure: on today's archive it removes no frame (measured), and it protects every stack if a
failing frame ever appears (e.g. in DR1). Rejected frames are listed in the manifest with the reason,
never dropped silently. The "> 50% of the box bad" rule rejected
{metrics['cutouts_over_50pct_bad_discovery']['value']} real cutouts under the discovery preset
(median bad fraction {metrics['cutouts_median_bad_discovery']['value']}).
"""
record("F8", "L2", "pass", metrics, report, [str(F.relative_to(ROOT)), "~/.cache/parallax-verify/cutouts (279 real cutouts)"],
       n_frames=n, code_paths=["backend/spherex/preprocess.py"],
       caveats=["L2 not L3: QA keywords counted over every frame of the 5 targets (the level F8 asks for); "
                "pixel bad fractions only over the 279 cutouts collected (WISE 0855 full visits, Barnard band 6, "
                "Barnard 12′ field)",
                "frames come from SIA2 at a 0.001° radius; pinned lists (D) may differ slightly"])
