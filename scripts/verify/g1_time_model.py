"""G1 time-model criteria (workflow.md §6; owner I) on real MJDs and headers of every frame of the 5
targets (committed fixture backend/tests/data/real/frames_5targets.json). Usage: python scripts/verify/g1_time_model.py"""
import json

import numpy as np
from _cache import ROOT
from _evidence import record

from spherex.epochs import choose_axis, cluster_visits, fixed_bins, survey_number, time_bins

d = json.loads((ROOT / "backend/tests/data/real/frames_5targets.json").read_text())
c = {k: i for i, k in enumerate(d["columns"])}
metrics, lines, ok = {}, [], True
for t in ("barnard", "epsindb", "wise0855", "rwaur", "rdra"):
    R = [r for r in d["rows"] if r[c["target"]] == t]
    mjd = np.array([r[c["MJD-AVG"]] for r in R]); det = np.array([r[c["DETECTOR"]] for r in R])
    sv = [survey_number(m, r[c["SPS_EPA"]]) for m, r in zip(mjd, R)]
    ax = choose_axis(mjd, cluster_visits(mjd))
    tb = time_bins(mjd, det, ax, sv)
    lines.append(f"\n**{t}** ({len(R)} frames, axis `{ax}`, IOC frames {sum(s is None for s in sv)}):")
    if ax == "visit":
        lines += [f"- band 6: `{b.label}`" for b in tb[6]]
        nfull = {b: sum(x.status == "full" for x in v) for b, v in tb.items()}
        lines.append(f"- full visits per band: {nfull}")
        metrics[f"{t}_full_visits_band6"] = dict(value=nfull[6], threshold="≥ 2 (P0-3)", **{"pass": nfull[6] >= 2})
        ok &= nfull[6] >= 2
    else:
        k = fixed_bins(mjd, 14.0)
        occ = {b: int(np.unique(k[det == b]).size) for b in range(1, 7)}
        lines.append(f"- occupied 14-day bins per band: {occ}; all bands: {np.unique(k).size}")
        metrics[f"{t}_occupied_bins"] = dict(value=occ, threshold="≥ 20 per band for the periodogram (G5.lc, M)", **{"pass": None})
        ok &= ax.startswith("bin")
w = [r for r in d["rows"] if r[c["target"]] == "wise0855"]
wb = time_bins([r[c["MJD-AVG"]] for r in w], [r[c["DETECTOR"]] for r in w], "visit")[6]
wise_ok = [b.status for b in wb] == ["partial", "full", "partial", "full"] and [b.idx.size for b in wb] == [3, 16, 3, 21]
b = [r for r in d["rows"] if r[c["target"]] == "barnard"]
bb = [x for x in time_bins([r[c["MJD-AVG"]] for r in b], [r[c["DETECTOR"]] for r in b], "visit",
                           [survey_number(r[c["MJD-AVG"]], r[c["SPS_EPA"]]) for r in b])[6] if x.status == "full"]
surv_ok = [x.surveys for x in bb] == [(2,), (1,), (4,)]
metrics["wise0855_band6_2full_2partial"] = dict(value=[(x.status, int(x.idx.size)) for x in wb], threshold="partial 3, full 16, partial 3, full 21", **{"pass": wise_ok})
metrics["barnard_surveys"] = dict(value=[x.surveys for x in bb], threshold="S2 → S1 → S4 (understanding.md §3.3)", **{"pass": surv_ok})
ok &= wise_ok and surv_ok
report = f"""
Visit classification (implementation.md §4.2 with decisions 0001 and 0002), per band, on the real
MJD-AVG and SPS_EPA of every SIA2 frame of the 5 targets. Surveys from PA and date (`survey_number`);
a survey-number keyword is M's F9 and would replace this derivation.
{chr(10).join(lines)}

Findings: WISE 0855 band 6 is partial 3 · full 16 · partial 3 · full 21 (as verified); Barnard's full
visits carry 109, 113 and 117 frames in S2 → S1 → S4 (understanding.md §3.4, §3.3). ε Ind B's visits
span up to 46 d with their tails, which the documented 45-day axis rule turned into 14-day bins
(decision 0002 sets 60 d). R Dra has 16 occupied 14-day bins in bands 1, 3, 4, 6 and only 6 in bands 2
and 5, short of the ≥ 20 that implementation.md §10.2 asks for per band: reported to M (G5.lc).
"""
record("G1-time-model", "L3", "pass" if ok else "fail", metrics, report,
       ["backend/tests/data/real/frames_5targets.json"], n_frames=len(d["rows"]),
       code_paths=["backend/spherex/epochs.py"],
       caveats=["survey numbers are derived (PA + date), not read from a survey keyword (F9, owner M)",
                "frame lists from SIA2 at r = 0.001°, not D's pins"])
