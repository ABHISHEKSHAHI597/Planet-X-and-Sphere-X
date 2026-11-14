# G2-registration — PASS (L3)

**Check.** Median offset of static Gaia stars (S/N ≥ 10 in the first stack; doubles < 2 px merged)
between band-6 visit stacks on the common grid, measured with background-subtracted first-moment
centroids re-centred twice (`grid.registration_offsets`). Each frame's own WCS (TAN-SIP) is used as
delivered; no re-registration (M's §4.7b) is applied.

| visit A | visit B | stars | median Δx (px) | median Δy (px) | |median| (px) | per-star robust σ (x, y) |
|---|---|---|---|---|---|---|
| V1 · 2025-08-15/27 · S2 · 18 frames | V2 · 2026-03-19→04-10 · S1 · 20 frames | 15 | -0.049 | -0.037 | 0.062 | [0.111, 0.139] |
| V1 · 2025-08-15/27 · S2 · 18 frames | V4 · 2026-08-16/20 · S4 · 17 frames | 15 | +0.015 | +0.079 | 0.080 | [0.088, 0.106] |
| V2 · 2026-03-19→04-10 · S1 · 20 frames | V4 · 2026-08-16/20 · S4 · 17 frames | 16 | +0.028 | +0.036 | 0.046 | [0.265, 0.166] |

The pairs include a PA flip (S2↔S1) and a release change (QR2↔QR3, new R7 astrometry).

## Metrics

| metric | value | threshold | pass |
|---|---|---|---|
| V1_V2_median_offset_px | 0.062 | < 0.1 px (proposed) | True |
| V1_V4_median_offset_px | 0.08 | < 0.1 px (proposed) | True |
| V2_V4_median_offset_px | 0.046 | < 0.1 px (proposed) | True |

## Caveats

- one field, band 6 only; G2 also needs every target and band (pins, D) and both viewers (F)
- threshold is proposed (workflow.md §6) and needs M's sign-off

git c12717d (dirty) · contract 0.1.0 · author I · reviewer pending
