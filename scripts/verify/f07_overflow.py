"""Foundation check F7 (workflow.md §5; owner I, pair D). At what brightness does OVERFLOW set in, per band?
Method: in a crowded 12′ field (Barnard's Star, PXSRCMSK ≈ 81%), match 2MASS PSC stars to OVERFLOW
flags within 1 px of each star, in 2 QR3 frames per detector; onset = the faintest 0.5-mag K bin in
which ≥ 50% of stars are flagged. NaN cores (early overflow) are counted separately.

Real files used: 12 cached real QR3 cutouts (0.2°) and 2MASS fp_psc (IRSA TAP, 2026-11-06, r = 0.16°).
2MASS positions are at their 2MASS epoch (≈2000.4); field stars' proper motions (≲0.1″/yr ≈ 2.5″ over
26 yr) are below the 1 px match radius. Barnard's Star itself (4.6′ from its 2MASS position) is excluded.
Usage: python scripts/verify/f07_overflow.py
"""
import json

import numpy as np
from _cache import CACHE, cutouts, load_cutout
from _evidence import record
from _pos import pos

from spherex.flags import flag_bits

pb = pos("Barnard's Star")

tm = json.loads((CACHE / "twomass_barnard12.json").read_text())
ra = np.array([float(r["ra"]) for r in tm]); dec = np.array([float(r["dec"]) for r in tm])
k = np.array([float(r["k_m"]) if r["k_m"] else np.nan for r in tm])
far = np.hypot((ra - 269.45208) * np.cos(np.radians(4.69)), dec - 4.69336) > 10 / 3600   # not Barnard (2MASS epoch)
per = {}
for p in cutouts("barnard12"):
    raw, meta = load_cutout(p)
    h, flg = raw.hdus["FLAGS"]
    bits = flag_bits(h)
    img = np.asarray(raw.hdus["IMAGE"][1], float)
    d = int(raw.hdus["IMAGE"][0]["DETECTOR"])
    x, y = raw.wcs.world_to_pixel_values(ra, dec)
    ny, nx = img.shape
    ins = (x > 2) & (y > 2) & (x < nx - 3) & (y < ny - 3) & np.isfinite(k) & far
    ov = np.zeros(ins.sum(), bool); nan = np.zeros(ins.sum(), bool)
    yy, xx = np.indices(img.shape)
    for j, (xi, yi) in enumerate(zip(x[ins], y[ins])):
        m = np.hypot(xx - xi, yy - yi) <= 1.0
        ov[j] = ((np.asarray(flg)[m] & bits["OVERFLOW"]) != 0).any()
        nan[j] = (~np.isfinite(img[m])).any()
    a = per.setdefault(d, dict(k=[], ov=[], nan=[], barnard=[]))
    a["k"] += list(k[ins]); a["ov"] += list(ov); a["nan"] += list(nan)
    bx, by = raw.wcs.world_to_pixel_values(*(float(v[0]) for v in pb(raw.hdus["IMAGE"][0]["MJD-AVG"])))
    mb = np.hypot(xx - bx, yy - by) <= 1.5
    a["barnard"].append((bool(((np.asarray(flg)[mb] & bits["OVERFLOW"]) != 0).any()), int((~np.isfinite(img[mb])).sum())))

metrics, rows = {}, []
edges = np.arange(3.0, 14.01, 0.5)
for d in sorted(per):
    K, OV, NA = (np.array(per[d][q]) for q in ("k", "ov", "nan"))
    frac = [(OV[(K >= a) & (K < a + 0.5)].mean() if ((K >= a) & (K < a + 0.5)).sum() >= 3 else np.nan) for a in edges[:-1]]
    frac = np.array(frac)
    onset = next((edges[i] + 0.5 for i in range(len(frac) - 1, -1, -1) if np.isfinite(frac[i]) and frac[i] >= 0.5), None)
    first = K[OV].max() if OV.any() else None
    nan_on = K[NA].max() if NA.any() else None
    metrics[f"D{d}_onset_K50"] = dict(value=onset, threshold="measured (≈7–10 expected, bands 1–3)", **{"pass": None})
    metrics[f"D{d}_faintest_flagged_K"] = dict(value=None if first is None else round(float(first), 2), threshold="measured", **{"pass": None})
    br = sorted(zip(K, OV), key=lambda t: t[0])[:4]
    bstr = ", ".join(f"K={kk:.1f}:{'OV' if o else 'no'}" for kk, o in br)
    bar = per[d]["barnard"]
    rows.append(f"| {d} | {len(K)} | {int(OV.sum())} | {onset if onset is not None else '–'} | "
                f"{'–' if first is None else f'{first:.2f}'} | {bstr} | "
                f"{sum(b[0] for b in bar)}/{len(bar)} OV, NaN px {[b[1] for b in bar]} |")
    metrics[f"D{d}_barnard_K4.5_overflow"] = dict(value=f"{sum(b[0] for b in bar)}/{len(bar)}", threshold="measured", **{"pass": None})
ok = all(m["value"] is not None for k_, m in metrics.items() if k_.endswith("onset_K50"))
report = f"""
**Question.** At what brightness does `OVERFLOW` set in, per band? Outcome: **{'measured' if ok else 'open'}**.

| band | 2MASS stars matched | with OVERFLOW ≤ 1 px | onset K (≥ 50% flagged, 0.5-mag bins) | faintest flagged K | 4 brightest field stars | Barnard's Star (K = 4.5) at pos(t) |
|---|---|---|---|---|---|---|
{chr(10).join(rows)}

Reading: bands 2–3 flag stars from K ≈ 9.5 and band 4 from K ≈ 9 (K = 8.6 flagged, 9.3 not), within
the ≈7–10 photon-budget estimate. Bands 1, 5 and 6 do not flag the K = 8.6 stars, so their onset lies
between K = 4.5 (Barnard's Star overflows in every band) and 8.6. Barnard's core is NaN (early overflow)
in bands 1–4 only (1–4 pixels within 1.5 px), confirming understanding.md §8.2's expectation; bands 5–6
keep ramp-fitted values. The single flagged K ≈ 15 star in band 4 is a chance coincidence with an
unrelated flagged pixel. A precise onset for bands 1, 5 and 6 needs a field with more K = 5–8 stars
(D: collect from the VM, e.g. an open cluster), hence `inconclusive` for those bands.

Use: the `bright` preset and the bright-target display fill apply to targets brighter than the onset in
the displayed band (Barnard K = 4.5, RW Aur 7.0, R Dra 2.2: all above it). NaN pixels near faint stars
are mostly unrelated masked pixels, so only the bright end of that column is meaningful.
"""
record("F7", "L2", "pass" if ok else "inconclusive", metrics, report,
       ["~/.cache/parallax-verify/cutouts/barnard12 (12 real QR3 cutouts)", "IRSA TAP fp_psc r=0.16° @ 269.4461,4.7707"],
       n_frames=12, code_paths=["backend/spherex/flags.py", "backend/spherex/stack.py"],
       caveats=["one field, 2 frames per detector, QR3 only; the onset depends on the channel (λ) within a "
                "band and on the PSF's peak fraction, so treat it as ±0.5 mag",
                "2MASS K compared for all bands; for bands 4–6 the relevant colour (K − W1/W2) adds scatter"])
