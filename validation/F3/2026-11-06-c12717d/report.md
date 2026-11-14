# F3 — PASS (L2)

**Question.** Which HDU of `spectral_channels` holds the channel map, and what do its values mean outside
the band? Outcome: **corrected**: implementation.md §3.5 read `ext=0`, which is header-only.

**HDU layout** (qr3/spectral_channels/cal-sch-v2-2026-229/spectral_channels_spx_cal-sch-v2-2026-229.fits):
- `PRIMARY`: BITPIX=8 NAXIS=0 DETECTOR=None DETCOORD=None
- `CHANNEL_MAP`: BITPIX=8 NAXIS=2 DETECTOR=ALL DETCOORD=sky
- `SPECTRAL_CHANNELS`: BITPIX=8 NAXIS=2 DETECTOR=None DETCOORD=None

**Values.** 1–17 are the channels; **0 = blueward of channel 1, 18 = redward of channel 17** (CWAVE at
those pixels lies beyond the table's WL_MIN of channel 1 / WL_MAX of channel 17 on every detector). Counts:
{0: 85817, 1: 237551, 2: 237531, 3: 237669, 4: 237531, 5: 237663, 6: 237539, 7: 237643, 8: 237559, 9: 237633, 10: 237567, 11: 237613, 12: 237569, 13: 237621, 14: 237593, 15: 237577, 16: 237613, 17: 236008, 18: 38303}.

**One map for all detectors.** The map is a single template (`DETECTOR='ALL'`). Against each detector's
own CWAVE binned by the SPECTRAL_CHANNELS edges it agrees exactly on 96–97% of in-band pixels and within
one channel everywhere; disagreements sit on channel boundaries. Use it for channel labels and channel
grouping (R Dra annulus method), never as a λ map (that is CWAVE).

| det | exact | within ±1 | median CWAVE at 0 (< WL_MIN ch1) | median CWAVE at 18 (> WL_MAX ch17) | max |ln λ_table − equal-ln centre| (ch) |
|---|---|---|---|---|---|
| D1 | 0.960 | 1.0000 | 0.742 < 0.743 | 1.118 > 1.116 | 0.07 |
| D2 | 0.971 | 1.0000 | 1.096 < 1.099 | 1.655 > 1.651 | 0.05 |
| D3 | 0.971 | 1.0000 | 1.631 < 1.636 | 2.424 > 2.440 | 0.13 |
| D4 | 0.963 | 1.0000 | 2.416 < 2.422 | 3.832 > 3.827 | 0.24 |
| D5 | 0.968 | 1.0000 | 3.811 < 3.814 | 4.430 > 4.426 | 0.25 |
| D6 | 0.962 | 1.0000 | 4.414 < 4.418 | 5.012 > 5.009 | 0.20 |

**Cube binning.** Real channel centres deviate from 17 equal ln-λ bins between the Supplement band
limits by ≤ 0.25 channel (D4–D6 widest). The cube interpolates on each pixel's *measured* λ, so this
only shifts which bin a sample falls in, not the matched wavelengths.

## Metrics

| metric | value | threshold | pass |
|---|---|---|---|
| hdu | 1 (EXTNAME CHANNEL_MAP) | identified | True |
| values | {0: 85817, 1: 237551, 2: 237531, 3: 237669, 4: 237531, 5: 237663, 6: 237539, 7: 237643, 8: 237559, 9: 237633, 10: 237567, 11: 237613, 12: 237569, 13: 237621, 14: 237593, 15: 237577, 16: 237613, 17: 236008, 18: 38303} | 0..18 | True |
| D1_map_vs_cwave_exact | 0.96 | > 0.9 | True |
| D1_map_vs_cwave_within1 | 1.0 | > 0.999 | True |
| D1_lnlambda_bin_dev_ch | 0.07 | < 0.5 channel | True |
| D2_map_vs_cwave_exact | 0.971 | > 0.9 | True |
| D2_map_vs_cwave_within1 | 1.0 | > 0.999 | True |
| D2_lnlambda_bin_dev_ch | 0.05 | < 0.5 channel | True |
| D3_map_vs_cwave_exact | 0.971 | > 0.9 | True |
| D3_map_vs_cwave_within1 | 1.0 | > 0.999 | True |
| D3_lnlambda_bin_dev_ch | 0.13 | < 0.5 channel | True |
| D4_map_vs_cwave_exact | 0.963 | > 0.9 | True |
| D4_map_vs_cwave_within1 | 1.0 | > 0.999 | True |
| D4_lnlambda_bin_dev_ch | 0.24 | < 0.5 channel | True |
| D5_map_vs_cwave_exact | 0.968 | > 0.9 | True |
| D5_map_vs_cwave_within1 | 1.0 | > 0.999 | True |
| D5_lnlambda_bin_dev_ch | 0.25 | < 0.5 channel | True |
| D6_map_vs_cwave_exact | 0.962 | > 0.9 | True |
| D6_map_vs_cwave_within1 | 1.0 | > 0.999 | True |
| D6_lnlambda_bin_dev_ch | 0.2 | < 0.5 channel | True |

git c12717d (dirty) · contract 0.1.0 · author I · reviewer pending
