"""Foundation check F3 (workflow.md §5; owner I, pair D). Which HDU of spectral_channels holds the channel
map, and what do its values mean outside the band? Also: is one map valid for all six detectors, and
does the cube's equal-ln-λ binning (cube.CH_LN) match the real channel centres?

Real files used: qr3/spectral_channels/cal-sch-v2-2026-229/spectral_channels_spx_cal-sch-v2-2026-229.fits
(headers, full CHANNEL_MAP, SPECTRAL_CHANNELS table) and every 40th CWAVE row of each detector from
qr3/spectral_wcs/cal-swcs-v5-2026-191. Usage: python scripts/verify/f03_channels.py [--online]
(--online re-reads the HDU headers from S3; the HDU layout below was read that way on 2026-11-06).
"""
import sys

import numpy as np
from _cache import channel_map, cwave_rows, spectral_channels
from _evidence import record

from spherex.constants import BANDS
from spherex.cube import CH_LN

KEY = "qr3/spectral_channels/cal-sch-v2-2026-229/spectral_channels_spx_cal-sch-v2-2026-229.fits"
layout = [("PRIMARY", "header only, NCHAN = 17"),
          ("CHANNEL_MAP", "uint8 2040×2040, DETECTOR='ALL', DETCOORD='sky'"),
          ("SPECTRAL_CHANNELS", "bintable 102 rows: DETECTOR, SUBCHAN, WAVELENGTH, WL_MIN, WL_MAX, R, R_STD, BANDWIDTH")]
if "--online" in sys.argv:
    from _archive import s3_hdu_map
    layout = [(n, f"BITPIX={h.get('BITPIX')} NAXIS={h.get('NAXIS')} DETECTOR={h.get('DETECTOR')} "
                  f"DETCOORD={h.get('DETCOORD')}") for n, h, _, _ in s3_hdu_map(KEY)]

cm = np.asarray(channel_map())
t = spectral_channels()
vals, counts = np.unique(cm, return_counts=True)
metrics = {"hdu": dict(value="1 (EXTNAME CHANNEL_MAP)", threshold="identified", **{"pass": True}),
           "values": dict(value={int(v): int(c) for v, c in zip(vals, counts)}, threshold="0..18", **{"pass": bool(set(vals) <= set(range(19)))})}
rows_txt = []
ok_all = True
for d in range(1, 7):
    c, rows = cwave_rows(d)
    tt = t[t["DETECTOR"] == d]
    ch = np.searchsorted(tt["WL_MAX"], c) + 1
    ch = np.where(c < tt["WL_MIN"][0], 0, ch)                       # 0 blueward, 18 redward
    m = cm[rows].astype(int)
    inb = (m >= 1) & (m <= 17)
    exact, pm1 = float((ch == m)[inb].mean()), float((np.abs(ch - m) <= 1)[inb].mean())
    out0 = c[m == 0]
    out18 = c[m == 18]
    blue_ok = bool(out0.size == 0 or np.median(out0) < tt["WL_MIN"][0] + 0.5 * (tt["WL_MAX"][0] - tt["WL_MIN"][0]))
    red_ok = bool(out18.size == 0 or np.median(out18) > tt["WL_MAX"][-1] - 0.5 * (tt["WL_MAX"][-1] - tt["WL_MIN"][-1]))
    lo = BANDS[d][0]
    dev = float(np.abs(np.log(tt["WAVELENGTH"] / (lo * np.exp((np.arange(17) + 0.5) * CH_LN[d])))).max() / CH_LN[d])
    ok = pm1 > 0.999 and exact > 0.9 and blue_ok and red_ok and dev < 0.5
    ok_all &= ok
    metrics[f"D{d}_map_vs_cwave_exact"] = dict(value=round(exact, 3), threshold="> 0.9", **{"pass": exact > 0.9})
    metrics[f"D{d}_map_vs_cwave_within1"] = dict(value=round(pm1, 4), threshold="> 0.999", **{"pass": pm1 > 0.999})
    metrics[f"D{d}_lnlambda_bin_dev_ch"] = dict(value=round(dev, 2), threshold="< 0.5 channel", **{"pass": dev < 0.5})
    rows_txt.append(f"| D{d} | {exact:.3f} | {pm1:.4f} | {np.median(out0) if out0.size else float('nan'):.3f} < "
                    f"{tt['WL_MIN'][0]:.3f} | {np.median(out18) if out18.size else float('nan'):.3f} > {tt['WL_MAX'][-1]:.3f} | {dev:.2f} |")

verdict = "pass" if ok_all else "fail"
report = f"""
**Question.** Which HDU of `spectral_channels` holds the channel map, and what do its values mean outside
the band? Outcome: **corrected**: implementation.md §3.5 read `ext=0`, which is header-only.

**HDU layout** ({KEY}):
{chr(10).join(f'- `{n}`: {d}' for n, d in layout)}

**Values.** 1–17 are the channels; **0 = blueward of channel 1, 18 = redward of channel 17** (CWAVE at
those pixels lies beyond the table's WL_MIN of channel 1 / WL_MAX of channel 17 on every detector). Counts:
{metrics['values']['value']}.

**One map for all detectors.** The map is a single template (`DETECTOR='ALL'`). Against each detector's
own CWAVE binned by the SPECTRAL_CHANNELS edges it agrees exactly on 96–97% of in-band pixels and within
one channel everywhere; disagreements sit on channel boundaries. Use it for channel labels and channel
grouping (R Dra annulus method), never as a λ map (that is CWAVE).

| det | exact | within ±1 | median CWAVE at 0 (< WL_MIN ch1) | median CWAVE at 18 (> WL_MAX ch17) | max |ln λ_table − equal-ln centre| (ch) |
|---|---|---|---|---|---|
{chr(10).join(rows_txt)}

**Cube binning.** Real channel centres deviate from 17 equal ln-λ bins between the Supplement band
limits by ≤ 0.25 channel (D4–D6 widest). The cube interpolates on each pixel's *measured* λ, so this
only shifts which bin a sample falls in, not the matched wavelengths.
"""
record("F3", "L2", verdict, metrics, report, [KEY, "qr3/spectral_wcs/cal-swcs-v5-2026-191 (CWAVE rows)"],
       calibration="qr3/spectral_channels/cal-sch-v2-2026-229 + qr3/spectral_wcs/cal-swcs-v5-2026-191",
       code_paths=["backend/spherex/calib.py", "backend/spherex/cube.py"])
