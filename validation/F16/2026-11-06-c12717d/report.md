# F16 — PASS (L3)

**Question.** How many samples does each per-pixel cube bin get on a real visit (band 6, 17 bins)?
Outcome: **confirmed with a qualification**: occupancy is ≈1 where sampled (≥ 2 samples in ≤ 16% of
bins), but **16–27% of bins are empty** at a typical pixel, because a real visit has 16–21 frames whose
wavelengths do not tile all 17 channels at every pixel.

| field | visit | frames | samples / pixel (median) | bins sampled (median of 17) | bins empty | bins with 1 | bins with ≥ 2 |
|---|---|---|---|---|---|---|---|
| wise0855 | V1 · 2025-11-10/14 · S1 · 16 frames | 16 | 13 | 12 | 0.27 | 0.70 | 0.03 |
| wise0855 | V2 · 2026-04-21→05-11 · S2 · 21 frames | 21 | 18 | 14 | 0.17 | 0.68 | 0.15 |
| barnard_off | V1 · 2025-08-15/27 · S2 · 18 frames | 18 | 15 | 14 | 0.16 | 0.78 | 0.06 |
| barnard_off | V2 · 2026-03-19→04-10 · S1 · 20 frames | 20 | 16 | 14 | 0.18 | 0.71 | 0.11 |
| barnard_off | V4 · 2026-08-16/20 · S4 · 17 frames | 17 | 14 | 14 | 0.20 | 0.80 | 0.00 |

**Consequence for the λ-matched difference.** An empty bin in B is bridged by interpolating between
the nearest sampled bins (`at_wavelengths`, max_interp_ch = 2 channels, decision 0003); an empty bin in
A simply contributes nothing. With 12–14 of 17 bins sampled per visit, the matched difference keeps
≈10–14 bin pairs per pixel, as implementation.md §4.6 estimated (12–17).

## Metrics

| metric | value | threshold | pass |
|---|---|---|---|
| wise0855_V1_frac_bins_1 | 0.7 | ≈1 sample/bin assumed | None |
| wise0855_V1_frac_bins_empty | 0.27 | measured | None |
| wise0855_V2_frac_bins_1 | 0.68 | ≈1 sample/bin assumed | None |
| wise0855_V2_frac_bins_empty | 0.17 | measured | None |
| barnard_off_V1_frac_bins_1 | 0.78 | ≈1 sample/bin assumed | None |
| barnard_off_V1_frac_bins_empty | 0.16 | measured | None |
| barnard_off_V2_frac_bins_1 | 0.71 | ≈1 sample/bin assumed | None |
| barnard_off_V2_frac_bins_empty | 0.18 | measured | None |
| barnard_off_V4_frac_bins_1 | 0.8 | ≈1 sample/bin assumed | None |
| barnard_off_V4_frac_bins_empty | 0.2 | measured | None |

## Caveats

- 2 targets, band 6 only (CWAVE collected for D6 only); other bands need D1–D5 CWAVE (D)

git c12717d (dirty) · contract 0.1.0 · author I · reviewer pending
