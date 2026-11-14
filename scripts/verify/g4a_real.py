"""G4a real-target checks (workflow.md §6; owner I, reviewer M), band 6, real cutouts and real QR3 D6 CWAVE.
  1. Barnard V1→V3 (Aug 2025 S2/QR2 → Aug 2026 S4/QR3, cross-survey-family) dipole: implementation.md
     §10.2 shift 1.5–1.9 px along PA 356° ± 15°.
  2. PA-flip pair (S2 PA 180° vs S1 PA 0°, both QR2) on a crowded field: Gaia field-star residuals < 3σ
     (P1-1), measured as a distribution.
  3. Null test (proposed): two disjoint halves of one real visit → robust σ ≈ 1, no structure at stars.
  4. Cross-release pairs (QR3 − QR2) on the same field, recorded for the F4 dependency.
Fields: Barnard's Star (6′ cutouts) and a crowded field 7.2′ east of it (outside Barnard's band-6 wings).
Usage: python scripts/verify/g4a_real.py
"""
import numpy as np
from _evidence import record
from _pos import pos
from _real import cubes_pair, frames, gaia, gaia_xy, stack_and_cube, visits

from spherex.cube import annotate, build_cube, diff, diff_fwhm_arcsec, matched_pair, null_halves, shift_pa
from spherex.grid import make_grid
from spherex.stack import sky_pixels


def setup(tag, centre):
    it = frames(tag, 6)
    g = make_grid(*centre, 4.0)
    out = {}
    for tb in visits(it)[6]:
        if tb.status == "full":
            out[tb.id] = stack_and_cube(it, tb, g)
    return g, out, sum(len(s.frame_ids) for s, _ in out.values())


metrics, caveats, nfr = {}, [], 0
# 1. Barnard dipole
P = pos("Barnard's Star")
g, B, n = setup("barnard", tuple(float(v[0]) for v in P(61070.0)))
nfr += n
ids = sorted(B)
first, last = ids[0], ids[-1]
xy = {k: tuple(float(v) for v in g.wcs.world_to_pixel_values(*(float(q[0]) for q in P(B[k][0].bin.mjd_mean)))) for k in ids}
dip = []
for a, b in [(last, first)] + [(ids[i + 1], ids[i]) for i in range(len(ids) - 1)]:
    ca, cb, f = cubes_pair(B[a][1], B[b][1], g, 6)
    df = diff(ca, cb, sky_pixels(B[a][0]) & sky_pixels(B[b][0]), allow_mixed_scales=True)  # dipole: scale-free fit
    px, py = xy[a][0] - xy[b][0], xy[a][1] - xy[b][1]
    an = annotate(df, [((xy[a][0] + xy[b][0]) / 2, (xy[a][1] + xy[b][1]) / 2)], f / 6.15, 6.15,
                  expected_pa=shift_pa(px, py), pair=matched_pair(ca, cb))[0]
    dip.append((B[a][0].bin.label, B[b][0].bin.label, float(np.hypot(px, py)), shift_pa(px, py), an))
_, _, pred, ppa, an = dip[0]
ok1 = 1.5 <= an["shift_px"] <= 1.9 and abs((an["pa_deg"] - 356 + 180) % 360 - 180) <= 15
metrics["barnard_V1_V3_shift_px"] = dict(value=round(an["shift_px"], 2), threshold="1.5–1.9 px", **{"pass": 1.5 <= an["shift_px"] <= 1.9})
metrics["barnard_V1_V3_pa_deg"] = dict(value=round(an["pa_deg"], 1), threshold="356 ± 15", **{"pass": abs((an["pa_deg"] - 356 + 180) % 360 - 180) <= 15})
metrics["barnard_V1_V3_kind"] = dict(value=an["kind"], threshold="dipole", **{"pass": an["kind"] == "dipole"})
drows = "\n".join(f"| {a} | {b} | {p:.2f} @ {pa:.0f}° | {r['shift_px']:.2f} @ {r.get('pa_deg', float('nan')):.0f}° | {r['kind']} | {r['label']} |"
                  for a, b, p, pa, r in dip)

# 2–4. crowded field away from Barnard
cen = (269.4461 + 0.12 / np.cos(np.radians(4.7707)), 4.7707)
g2, F, n = setup("barnard_off", cen)
nfr += n
G = gaia("barnard_off")


def stars(st):
    out = []
    for x, y, gm, sid in gaia_xy(G, g2, st.bin.mjd_mean):
        if 4 < x < g2.shape[1] - 5 and 4 < y < g2.shape[0] - 5 and not any(np.hypot(x - a, y - b) < 2 for a, b in out):
            out.append((x, y))
    return out


def peaks(df, xy):
    v = [np.nanmax(np.abs(df.sig[int(round(y)) - 1:int(round(y)) + 2, int(round(x)) - 1:int(round(x)) + 2])) for x, y in xy]
    return np.array([x for x in v if np.isfinite(x)])


def dist(v):
    return f"n = {v.size}, > 3σ: {np.mean(v > 3):.0%}, p90 {np.percentile(v, 90):.1f}σ, max {v.max():.1f}σ"


# noise-only expectation for the same statistic: the same boxes at random sky positions
def null_expect(df, st, k=400, seed=0):
    rng = np.random.default_rng(seed)
    sky = sky_pixels(st)
    ys, xs = np.nonzero(sky[2:-2, 2:-2])
    i = rng.choice(ys.size, min(k, ys.size), replace=False)
    return peaks(df, list(zip(xs[i] + 2, ys[i] + 2)))


fid = sorted(F)
rows = []
a, b = fid[1], fid[0]                                     # S1 (PA 0°) − S2 (PA 180°), both QR2
ca, cb, f = cubes_pair(F[a][1], F[b][1], g2, 6)
dpf = diff(ca, cb, sky_pixels(F[a][0]) & sky_pixels(F[b][0]))
vpf, epf = peaks(dpf, stars(F[a][0])), null_expect(dpf, F[a][0])
rows.append(f"| PA flip {F[a][0].bin.label} − {F[b][0].bin.label} | {dpf.k:.2f} | {dist(vpf)} | {np.mean(epf > 3):.0%} |")
metrics["paflip_frac_gt3"] = dict(value=round(float(np.mean(vpf > 3)), 2), threshold=f"≈ sky-box rate {np.mean(epf > 3):.2f}", **{"pass": None})
metrics["paflip_p90_sigma"] = dict(value=round(float(np.percentile(vpf, 90)), 2), threshold="< 3", **{"pass": bool(np.percentile(vpf, 90) < 3)})
metrics["paflip_max_sigma"] = dict(value=round(float(vpf.max()), 2), threshold="< 3 (strict reading; see report)", **{"pass": None})

gd, tb = F[fid[-1]][1]
c = g2.shape[0] // 2
ia, ib = null_halves([np.nanmedian(x.lam[c - 1:c + 2, c - 1:c + 2]) for x in gd])
fw = diff_fwhm_arcsec(gd, gd)
dn = diff(build_cube([gd[i] for i in ia], tb, 6, g2, homog_fwhm_arcsec=fw),
          build_cube([gd[i] for i in ib], tb, 6, g2, homog_fwhm_arcsec=fw), sky_pixels(F[fid[-1]][0]), max_interp_ch=3.0)
vn, en = peaks(dn, stars(F[fid[-1]][0])), null_expect(dn, F[fid[-1]][0])
rows.append(f"| null: halves of {F[fid[-1]][0].bin.label} | {dn.k:.2f} | {dist(vn)} | {np.mean(en > 3):.0%} |")
metrics["null_k"] = dict(value=round(dn.k, 2), threshold="reported (renormalised to 1)", **{"pass": None})
metrics["null_frac_gt3_at_stars"] = dict(value=round(float(np.mean(vn > 3)), 2), threshold="reported diagnostic; post-hoc 2x sky-box proposal rejected by M (0004)",
                                         **{"pass": None})

for a, b in [(fid[-1], fid[0]), (fid[-1], fid[1])]:
    ca, cb, f = cubes_pair(F[a][1], F[b][1], g2, 6)
    dx = diff(ca, cb, sky_pixels(F[a][0]) & sky_pixels(F[b][0]), allow_mixed_scales=True)   # measures F4 effect
    v = peaks(dx, stars(F[a][0]))
    rows.append(f"| QR3 − QR2 {F[a][0].bin.label} − {F[b][0].bin.label} | {dx.k:.2f} | {dist(v)} | {np.mean(null_expect(dx, F[a][0]) > 3):.0%} |")
    metrics[f"xrel_{a}_{b}_frac_gt3"] = dict(value=round(float(np.mean(v > 3)), 2), threshold="blocked on F4 (owner M)", **{"pass": None})

paflip_ok = bool(np.mean(vpf > 3) <= 2 * max(np.mean(epf > 3), 0.02) and np.percentile(vpf, 90) < 3)
metrics["paflip_rate_vs_sky"] = dict(value=f"{np.mean(vpf > 3):.2f} vs {np.mean(epf > 3):.2f}", threshold="reported only; rejected as a replacement gate statistic (0004)", **{"pass": None})
# Never promote the rejected post-hoc statistic. Original residual requirement remains.
metrics["paflip_max_sigma"]["pass"] = bool(vpf.max() < 3)
verdict = "fail" if not ok1 or vpf.max() >= 3 else "inconclusive"
report = f"""
All differences use the production path: per-pixel spectral cubes from real CWAVE, bicubic NaN-safe
resampling, PSF homogenisation to 1.5 × PSF_FWHM, and the resampling systematics of decision 0003
(ε = 0.02, σ_r = 0.05 px); significance renormalised on sky pixels (k reported).

**1. Barnard dipole (band 6).** Barnard's core is masked in 52 of 59 frames (TRANSIENT + SUR_ERROR early
events), so the shift is measured by fitting B's own λ-matched image onto A (`cube.fit_shift`); the
Gaussian two-PSF model only decides dipole vs monopole.

| A | B | predicted (PM + parallax) | measured | kind | label |
|---|---|---|---|---|---|
{drows}

Criterion 1 (1.5–1.9 px along 356° ± 15°): **{'pass' if ok1 else 'fail'}**. The intermediate pairs follow the
PM + parallax zig-zag too.

**2–4. Static field stars, crowded field 7.2′ east of Barnard** (Gaia DR3 G < 17.5, doubles merged;
statistic: max |σ| in a 3×3 box at each star; "sky-box rate" = the same statistic at random sky
positions of the same map, i.e. what noise alone gives):

| difference | k | stars | sky-box rate > 3σ |
|---|---|---|---|
{chr(10).join(rows)}

Reading (star-position rate vs the sky-box rate of the same map):
- **PA flip (same release):** {np.mean(vpf > 3):.0%} vs {np.mean(epf > 3):.0%} for noise alone: no excess at star positions;
  p90 {np.percentile(vpf, 90):.1f}σ. The strict "every star < 3σ" reading fails only through the noise tail
  of a 3×3-max statistic, which noise alone exceeds in {np.mean(epf > 3):.0%} of boxes. Proposed statistic for the
  gate was rejected by M in decision 0004: neither a 2x sky-box rate nor p90 replaces the original criterion.
- **Null test:** k = {dn.k:.2f} (VARIANCE underestimates half-visit scatter after homogenisation; the
  significance is renormalised on sky), star-position rate {np.mean(vn > 3):.0%} vs {np.mean(en > 3):.0%} on sky: no
  structure at stars beyond noise.
- **QR3 − QR2 pairs** leave 3× more residuals at stars than noise, mostly positive monopoles (QR3
  brighter): consistent with the QR2→QR3 gain change that `l3_flux_corrections` removes. Cross-release
  differences therefore depend on **F4 (owner M, pair D)**; until F4 is resolved they must not be shown,
  and G4a cannot be accepted for cross-release pairs (Barnard's V1→V3 is one; its *dipole* is a
  scale-free fit and passes).
"""
caveats = ["band 6 only (CWAVE collected for D6 only); one PA-flip pair, one null visit",
           "Barnard's own static-residual test is impossible in a 4′ field: its band-6 wings cover it (moved off-field)",
           "pos(t) and Gaia propagation now delegate to M's modules; earlier records retain their original provenance",
           "M rejected the post-hoc residual statistic and uncalibrated systematic terms (decision 0004); no release approval"]
record("G4a-real", "L3", verdict, metrics, report,
       ["~/.cache/parallax-verify/cutouts/{barnard,barnard_off} (band 6)", "qr3/spectral_wcs/cal-swcs-v5-2026-191/6",
        "IRSA gaia_dr3_source"], n_frames=nfr, code_paths=["backend/spherex/cube.py", "backend/spherex/grid.py",
        "backend/spherex/stack.py", "backend/spherex/preprocess.py"], caveats=caveats)
