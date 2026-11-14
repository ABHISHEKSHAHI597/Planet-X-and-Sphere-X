"""G2 registration check (workflow.md §6, proposed): static Gaia stars show a median positional offset
between visit stacks of < 0.1 px. Owner I. Real data: band-6 cutouts of the three full Barnard visits
(S2 QR2, S1 QR2, S4 QR3) of a crowded field 7.2′ east of Barnard's Star (outside its band-6 wings), and
Gaia DR3 (IRSA, G < 17.5) propagated to each visit's mean epoch. Usage: python scripts/verify/g2_registration.py
"""
import numpy as np
from _evidence import record
from _real import frames, gaia, gaia_xy, stack_and_cube, visits

from spherex.grid import make_grid, registration_offsets, significance
from spherex.stack import sky_pixels

g = make_grid(269.4461 + 0.12 / np.cos(np.radians(4.7707)), 4.7707, 4.0)
it = frames("barnard_off", 6)
S = {tb.id: stack_and_cube(it, tb, g, cube=False)[0] for tb in visits(it)[6] if tb.status == "full"}
G = gaia("barnard_off")


def stars(st, snmin=10.0):
    sig, _ = significance(st.mean, st.var, sky_pixels(st))
    out = []
    for x, y, gm, sid in gaia_xy(G, g, st.bin.mjd_mean):
        if not (4 < x < g.shape[1] - 5 and 4 < y < g.shape[0] - 5) or any(np.hypot(x - a, y - b) < 2 for a, b in out):
            continue
        if np.nanmax(sig[int(round(y)) - 1:int(round(y)) + 2, int(round(x)) - 1:int(round(x)) + 2]) >= snmin:
            out.append((x, y))
    return out


metrics, rows, ok = {}, [], True
ids = sorted(S)
for i in range(len(ids)):
    for j in range(i + 1, len(ids)):
        a, b = ids[i], ids[j]
        d = registration_offsets(S[a].mean, S[b].mean, stars(S[a]))
        med = np.median(d, 0)
        off = float(np.hypot(*med))
        radial=float(np.median(np.linalg.norm(d,axis=1))) if len(d) else float('inf')
        ok &= off < 0.1 and radial < 0.1
        metrics[f"{a}_{b}_median_radial_px"]=dict(value=radial,threshold='< 0.1 px per-star separation',**{'pass':radial<.1})
        metrics[f"{a}_{b}_median_offset_px"] = dict(value=round(off, 3), threshold="< 0.1 px (proposed)", **{"pass": off < 0.1})
        rows.append(f"| {S[a].bin.label} | {S[b].bin.label} | {len(d)} | {med[0]:+.3f} | {med[1]:+.3f} | {off:.3f} | "
                    f"{(1.4826 * np.median(np.abs(d - med), 0)).round(3).tolist()} |")
report = f"""
**Check.** Median offset of static Gaia stars (S/N ≥ 10 in the first stack; doubles < 2 px merged)
between band-6 visit stacks on the common grid, measured with background-subtracted first-moment
centroids re-centred twice (`grid.registration_offsets`). Each frame's own WCS (TAN-SIP) is used as
delivered; no re-registration (M's §4.7b) is applied.

| visit A | visit B | stars | median Δx (px) | median Δy (px) | |median| (px) | per-star robust σ (x, y) |
|---|---|---|---|---|---|---|
{chr(10).join(rows)}

The pairs include a PA flip (S2↔S1) and a release change (QR2↔QR3, new R7 astrometry).
"""
record("G2-registration", "L3", "pass" if ok else "fail", metrics, report,
       ["~/.cache/parallax-verify/cutouts/barnard_off (59 band-6 frames)", "IRSA gaia_dr3_source r=0.07°"],
       n_frames=sum(len(s.frame_ids) for s in S.values()), code_paths=["backend/spherex/grid.py", "backend/spherex/stack.py"],
       caveats=["one field, band 6 only; G2 also needs every target and band (pins, D) and both viewers (F)",
                "M review 0004 requires both radial separation and translation; one field does not satisfy the all-target gate"])
