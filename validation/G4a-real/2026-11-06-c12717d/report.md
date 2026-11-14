# G4a-real — INCONCLUSIVE (L3)

All differences use the production path: per-pixel spectral cubes from real CWAVE, bicubic NaN-safe
resampling, PSF homogenisation to 1.5 × PSF_FWHM, and the resampling systematics of decision 0003
(ε = 0.02, σ_r = 0.05 px); significance renormalised on sky pixels (k reported).

**1. Barnard dipole (band 6).** Barnard's core is masked in 52 of 59 frames (TRANSIENT + SUR_ERROR early
events), so the shift is measured by fitting B's own λ-matched image onto A (`cube.fit_shift`); the
Gaussian two-PSF model only decides dipole vs monopole.

| A | B | predicted (PM + parallax) | measured | kind | label |
|---|---|---|---|---|---|
| V4 · 2026-08-16/20 · S4 · 17 frames | V1 · 2025-08-15/27 · S2 · 18 frames | 1.68 @ 356° | 1.62 @ 354° | dipole | moved ≈10.0″ |
| V2 · 2026-03-19→04-10 · S1 · 20 frames | V1 · 2025-08-15/27 · S2 · 18 frames | 0.97 @ 5° | 1.01 @ 8° | dipole | moved ≈6.2″ |
| V4 · 2026-08-16/20 · S4 · 17 frames | V2 · 2026-03-19→04-10 · S1 · 20 frames | 0.74 @ 343° | 0.80 @ 334° | dipole | moved ≈4.9″ |

Criterion 1 (1.5–1.9 px along 356° ± 15°): **pass**. The intermediate pairs follow the
PM + parallax zig-zag too.

**2–4. Static field stars, crowded field 7.2′ east of Barnard** (Gaia DR3 G < 17.5, doubles merged;
statistic: max |σ| in a 3×3 box at each star; "sky-box rate" = the same statistic at random sky
positions of the same map, i.e. what noise alone gives):

| difference | k | stars | sky-box rate > 3σ |
|---|---|---|---|
| PA flip V2 · 2026-03-19→04-10 · S1 · 20 frames − V1 · 2025-08-15/27 · S2 · 18 frames | 1.33 | n = 26, > 3σ: 12%, p90 2.8σ, max 3.6σ | 8% |
| null: halves of V4 · 2026-08-16/20 · S4 · 17 frames | 1.26 | n = 26, > 3σ: 12%, p90 2.9σ, max 4.4σ | 14% |
| QR3 − QR2 V4 · 2026-08-16/20 · S4 · 17 frames − V1 · 2025-08-15/27 · S2 · 18 frames | 1.18 | n = 26, > 3σ: 46%, p90 6.3σ, max 7.1σ | 18% |
| QR3 − QR2 V4 · 2026-08-16/20 · S4 · 17 frames − V2 · 2026-03-19→04-10 · S1 · 20 frames | 1.12 | n = 26, > 3σ: 38%, p90 8.2σ, max 11.5σ | 12% |

Reading (star-position rate vs the sky-box rate of the same map):
- **PA flip (same release):** 12% vs 8% for noise alone: no excess at star positions;
  p90 2.8σ. The strict "every star < 3σ" reading fails only through the noise tail
  of a 3×3-max statistic, which noise alone exceeds in 8% of boxes. Proposed statistic for the
  gate (needs M): star-position rate ≤ 2 × the sky-box rate, and p90 < 3σ.
- **Null test:** k = 1.26 (VARIANCE underestimates half-visit scatter after homogenisation; the
  significance is renormalised on sky), star-position rate 12% vs 14% on sky: no
  structure at stars beyond noise.
- **QR3 − QR2 pairs** leave 3× more residuals at stars than noise, mostly positive monopoles (QR3
  brighter): consistent with the QR2→QR3 gain change that `l3_flux_corrections` removes. Cross-release
  differences therefore depend on **F4 (owner M, pair D)**; until F4 is resolved they must not be shown,
  and G4a cannot be accepted for cross-release pairs (Barnard's V1→V3 is one; its *dipole* is a
  scale-free fit and passes).

## Metrics

| metric | value | threshold | pass |
|---|---|---|---|
| barnard_V1_V3_shift_px | 1.62 | 1.5–1.9 px | True |
| barnard_V1_V3_pa_deg | 354.3 | 356 ± 15 | True |
| barnard_V1_V3_kind | dipole | dipole | True |
| paflip_frac_gt3 | 0.12 | ≈ sky-box rate 0.08 | None |
| paflip_p90_sigma | 2.82 | < 3 | True |
| paflip_max_sigma | 3.58 | < 3 (strict reading; see report) | None |
| null_k | 1.26 | reported (renormalised to 1) | None |
| null_frac_gt3_at_stars | 0.12 | ≤ 2 × sky-box rate (0.14) | True |
| xrel_V4_V1_frac_gt3 | 0.46 | blocked on F4 (owner M) | None |
| xrel_V4_V2_frac_gt3 | 0.38 | blocked on F4 (owner M) | None |
| paflip_rate_vs_sky | 0.12 vs 0.08 | ≤ 2 × sky-box rate (proposed) | True |

## Caveats

- band 6 only (CWAVE collected for D6 only); one PA-flip pair, one null visit
- Barnard's own static-residual test is impossible in a 4′ field: its band-6 wings cover it (moved off-field)
- pos(t) and Gaia propagation are temporary adapters for M's modules
- proposed thresholds and the distribution statistic need M's sign-off

git c12717d (dirty) · contract 0.1.0 · author I · reviewer pending
