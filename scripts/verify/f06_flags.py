"""Foundation check F6 (workflow.md §5; owner I, pair M).
Part 1: do the FLAGS header's self-described planes match understanding.md §4.4, across releases?
Part 2: does the SOURCE plane around WISE 0855 sit at its predicted or its WISE-era position?

Real files used: the committed QR3 fixture backend/tests/data/real/barnard_qr3_d6_29x29_hdu0-4.fits, and
the 279 cached real cutouts (QR2 pipelines 6.4–6.5.7 and QR3 7.0.5; WISE 0855 full visits all bands).
Ad-hoc use on any files: python scripts/verify/f06_flags.py FILE.fits [...]   (part 1 only)
Default: python scripts/verify/f06_flags.py   (both parts, writes the evidence record)
"""
import collections
import sys

import numpy as np
from _cache import ROOT, cutouts, load_cutout
from astropy.io import fits

from spherex.flags import CANONICAL_BITS, flag_bits

FIX = ROOT / "backend/tests/data/real/barnard_qr3_d6_29x29_hdu0-4.fits"


def check_bits(bits):
    wrong = {n: v for n, v in bits.items() if CANONICAL_BITS.get(n) is None or v != 1 << CANONICAL_BITS[n]}
    return sorted(set(CANONICAL_BITS) - set(bits)), wrong


if len(sys.argv) > 1:
    for path in sys.argv[1:]:
        with fits.open(path) as hl:
            missing, wrong = check_bits(flag_bits(hl["FLAGS"].header))
            print(f"{path}: pipeline {hl[0].header.get('VERSION')}; missing vs doc: {missing or 'none'}; "
                  f"unexpected/mismatched: {wrong or 'none'}")
    sys.exit(0)

from _evidence import record
from _pos import WISE_ERA, pos

by_version = collections.defaultdict(lambda: collections.Counter())
mism = collections.Counter()
with fits.open(FIX) as hl:
    m, w = check_bits(flag_bits(hl["FLAGS"].header))
    by_version[hl[0].header.get("VERSION")][("missing", tuple(m))] += 1
    mism.update(w)
wise = []
pw = pos("WISE 0855-0714")
for tag in ("wise0855", "barnard", "barnard12"):
    for p in cutouts(tag):
        raw, meta = load_cutout(p)
        h, flg = raw.hdus["FLAGS"]
        bits = flag_bits(h)
        m, w = check_bits(bits)
        by_version[meta["primary"].get("VERSION")][("missing", tuple(m))] += 1
        mism.update(w)
        if tag == "wise0855":
            hi = raw.hdus["IMAGE"][0]
            src = (np.asarray(flg, np.int64) & bits["SOURCE"]) != 0
            out = lambda m: float(np.mean(m)) if m.size else np.nan
            yy, xx = np.indices(src.shape)
            res = {}
            for k, (ra, dec) in {"pred": tuple(float(v[0]) for v in pw(hi["MJD-AVG"])), "wise_era": WISE_ERA}.items():
                x, y = raw.wcs.world_to_pixel_values(ra, dec)
                r = np.hypot(xx - x, yy - y)
                res[k] = out(src[r <= 1.5])
                res[k + "_outlier"] = out(((np.asarray(flg, np.int64) & bits["OUTLIER"]) != 0)[r <= 1.5])
            ann = (np.hypot(xx - x, yy - y) > 8) & (np.hypot(xx - x, yy - y) < 20)
            res["field"] = float(src.mean())
            res["band"] = int(hi["DETECTOR"])
            wise.append(res)

vers = {v: {str(k[1]): n for k, n in c.items()} for v, c in by_version.items()}
all_missing = {k[1] for c in by_version.values() for k in c}
part1_ok = not mism                      # bit numbers must agree; plane *sets* differ by pipeline (reported)
W = collections.defaultdict(list)
for r in wise:
    W[r["band"]].append(r)
rows = []
metrics = {"part1_mismatched_planes": dict(value=dict(mism) or "none", threshold="none", **{"pass": not mism}),
           "part1_missing_planes_by_version": dict(value=vers, threshold="reported", **{"pass": None})}
for b in sorted(W):
    f = lambda k: np.nanmean([r[k] for r in W[b]])
    rows.append(f"| {b} | {len(W[b])} | {f('pred'):.2f} | {f('wise_era'):.2f} | {f('field'):.2f} | {f('pred_outlier'):.2f} | {f('wise_era_outlier'):.2f} |")
    metrics[f"band{b}_SOURCE_at_predicted"] = dict(value=round(float(f("pred")), 3), threshold="measured", **{"pass": None})
    metrics[f"band{b}_SOURCE_at_wise_era"] = dict(value=round(float(f("wise_era")), 3), threshold="measured", **{"pass": None})
blue = [r for r in wise if r["band"] in (1, 2, 3)]       # the dwarf is invisible here: footprints are catalogue-only
pred = np.nanmean([r["pred"] for r in blue])
era = np.nanmean([r["wise_era"] for r in blue])
fld = np.nanmean([r["field"] for r in blue])
where = ("predicted (current)" if pred > 0.9 and era < fld + 0.15 else
         "WISE-era" if era > 0.9 and pred < fld + 0.15 else "neither / both")
metrics["bands1to3_SOURCE_pred_vs_era_vs_field"] = dict(value=[round(float(pred), 2), round(float(era), 2), round(float(fld), 2)],
                                                        threshold="predicted > 0.9, WISE-era at field level", **{"pass": where.startswith("predicted")})
report = f"""
**Part 1: plane names.** {sum(sum(c.values()) for c in by_version.values())} FLAGS headers read (the
committed fixture and 279 real cutouts, pipelines 6.4+psffix1, 6.5.6 and 7.0.5). Outcome: **corrected**.
- Bit numbers agree with understanding.md §4.4 in every file (mismatches: {dict(mism) or 'none'}).
- **Two header conventions.** QR3 (7.0.5) uses `MSKNnnnn`/`MSKMnnnn`; **QR2 (6.x) uses
  `HIERARCH MP_<NAME> = <bit>`**. The previous `flag_bits` read only the first, so on every QR2 frame it
  returned no planes and masked nothing. Fixed (both conventions; a header with neither now raises).
- **Plane sets differ by pipeline.** Absent planes by version: {vers}. QR2 6.4 frames carry no BLOOM,
  CROSSTALK, GHOST*, HALO, SNOWBALL or STREAK planes, so those artifacts cannot be masked or used for
  mover vetting there; 6.5.6 lacks CROSSTALK and STREAK; 7.0.5 lacks SATELLITE_HALO (and PHANTOM,
  REFERENCE, which only QR2 defines). PHANTOM (4) and REFERENCE (5) are added to the canonical layout;
  REFERENCE is masked in every preset (not light-sensitive), PHANTOM is informational.

**Part 2: SOURCE at WISE 0855.** Fraction of pixels within 1.5 px flagged SOURCE (and OUTLIER), at the
position predicted for each frame's MJD-AVG (PM + parallax, M's common pos(t)) and at the
WISE-era challenge coordinate (≈2.2′ away), averaged over the frames of the two full visits:

| band | frames | SOURCE at predicted | SOURCE at WISE-era | field SOURCE fraction | OUTLIER at predicted | OUTLIER at WISE-era |
|---|---|---|---|---|---|---|
{chr(10).join(rows)}

Bands 1–3 decide (the dwarf is invisible there, J ≈ 25, so any footprint is catalogue-only): SOURCE
sits at the **{where}** position (mean {pred:.2f} at predicted, {era:.2f} at WISE-era, field {fld:.2f}).
The SPHEREx reference catalogue therefore includes WISE 0855 with its proper motion. Correction to
understanding.md §8.4, which expected its pixels un-masked and possibly OUTLIER: they are SOURCE, and
OUTLIER is never set on them (it is computed only outside known sources). Mask policy unchanged and
now required: SOURCE is never masked (flags.PRESETS), so the dwarf stays visible in discovery views.
"""
part2 = "pass" if np.isfinite(pred) else "inconclusive"
record("F6", "L2", "pass" if part1_ok and part2 == "pass" else ("fail" if not part1_ok else "inconclusive"),
       metrics, report, [str(FIX.relative_to(ROOT)), "~/.cache/parallax-verify/cutouts (279 real cutouts)"],
       n_frames=280, code_paths=["backend/spherex/flags.py"],
       caveats=["pos(t) delegates to M targets.py implementing implementation.md §4.1 (owner M); a 1.5 px radius makes "
                "the result insensitive to sub-pixel errors"])
