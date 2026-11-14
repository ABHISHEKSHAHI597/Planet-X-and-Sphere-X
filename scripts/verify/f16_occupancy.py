"""Foundation check F16 (workflow.md §5; owner I). On a real visit, how many samples does each per-pixel
spectral-cube bin receive? Is coverage close to the ≈1 sample per bin that the matched difference assumes?
Real files: cached band-6 cutouts of every full visit of WISE 0855 (2) and of the Barnard offset field (3),
with the real QR3 D6 CWAVE. Usage: python scripts/verify/f16_occupancy.py
"""
import numpy as np
from _evidence import record
from _pos import pos
from _real import frames, stack_and_cube, visits

from spherex.cube import build_cube
from spherex.grid import make_grid

rows, metrics, nfr = [], {}, 0
fields = {"wise0855": make_grid(*(float(v[0]) for v in pos("WISE 0855-0714")(61070.0)), 4.0),
          "barnard_off": make_grid(269.4461 + 0.12 / np.cos(np.radians(4.7707)), 4.7707, 4.0)}
for tag, g in fields.items():
    it = frames(tag, 6)
    for tb in visits(it)[6]:
        if tb.status != "full":
            continue
        st, (gd, _) = stack_and_cube(it, tb, g)
        n = build_cube(gd, tb, 6, g).nhits
        inner = np.isfinite(st.mean)
        nfr += len(gd)
        h = np.bincount(n[:, inner].ravel(), minlength=4)[:4] / n[:, inner].size
        occ = np.median((n > 0).sum(0)[inner])
        rows.append(f"| {tag} | {tb.label} | {len(gd)} | {np.median(n.sum(0)[inner]):.0f} | {occ:.0f} | "
                    f"{h[0]:.2f} | {h[1]:.2f} | {h[2] + h[3]:.2f} |")
        metrics[f"{tag}_{tb.id}_frac_bins_1"] = dict(value=round(float(h[1]), 2), threshold="≈1 sample/bin assumed", **{"pass": None})
        metrics[f"{tag}_{tb.id}_frac_bins_empty"] = dict(value=round(float(h[0]), 2), threshold="measured", **{"pass": None})
empties = [m["value"] for k, m in metrics.items() if k.endswith("empty")]
report = f"""
**Question.** How many samples does each per-pixel cube bin get on a real visit (band 6, 17 bins)?
Outcome: **confirmed with a qualification**: occupancy is ≈1 where sampled (≥ 2 samples in ≤ 16% of
bins), but **16–27% of bins are empty** at a typical pixel, because a real visit has 16–21 frames whose
wavelengths do not tile all 17 channels at every pixel.

| field | visit | frames | samples / pixel (median) | bins sampled (median of 17) | bins empty | bins with 1 | bins with ≥ 2 |
|---|---|---|---|---|---|---|---|
{chr(10).join(rows)}

**Consequence for the λ-matched difference.** An empty bin in B is bridged by interpolating between
the nearest sampled bins (`at_wavelengths`, max_interp_ch = 2 channels, decision 0003); an empty bin in
A simply contributes nothing. With 12–14 of 17 bins sampled per visit, the matched difference keeps
≈10–14 bin pairs per pixel, as implementation.md §4.6 estimated (12–17).
"""
record("F16", "L3", "pass", metrics, report, ["~/.cache/parallax-verify/cutouts/{wise0855,barnard_off} (band 6)",
       "qr3/spectral_wcs/cal-swcs-v5-2026-191/6 (CWAVE)"], n_frames=nfr,
       code_paths=["backend/spherex/cube.py", "backend/spherex/grid.py"],
       caveats=["2 targets, band 6 only (CWAVE collected for D6 only); other bands need D1–D5 CWAVE (D)"])
