# 0008 — Cross-release (QR2 − QR3) differences by in-situ photometric matching

**Date:** 2026-11-09 · **Owner:** P (on I's `spherex/cube.py`; I to adopt) · **Reviewers needed:** I (code owner),
M (science; workflow.md §4.4) · **Status of the numbers:** proposed · **Base:** `main` @ `989bf01`

## Context
A teammate's live run (`FRAMESOURCE=s3`, Barnard's Star, band 6, `mode=diff`, V1 − V5) failed with
`mixed photometric scales ('qr2',) vs ('qr3',): apply l3_flux_corrections (F4) first`. V1 (Aug 2025) is QR2 and
V5 is QR3. `cube.diff` refused the pair by design: uncorrected QR2 and QR3 differ by a gain, and a naive
subtraction leaves flux-proportional residuals at every static star (workflow.md §11.2).

The message's advice cannot be followed. F4 is **inconclusive** (`validation/F4/2026-11-08-d6d2e45`):

| QR2 / QR3 flux ratio | value |
|---|---|
| uncorrected | 0.9306 |
| × `l3_flux_corrections` | 0.913 |
| ÷ `l3_flux_corrections` | 0.948 |

Neither direction of the correction brings the releases together, so "apply F4 first" has no correct implementation
today. Most Barnard visit pairs that span the motion are cross-release, so the difference mode was unusable on the
target the demo is built around.

## Decision
Match the two visits **in situ**, on the static sources they share, the way image-subtraction codes do
(Alard & Lupton 1998; HOTPANTS, Becker 2015; ZOGY, Zackay, Ofek & Gal-Yam 2016). This takes no position on what
the correct release-to-release correction is; it measures the ratio this particular pair needs.

`cube.fit_relative_scale(a, va, b, vb, lam, sky, exclude_xy, …)` fits a_k ≈ s_k·b_k + c_k per λ bin k, with B already
evaluated at A's wavelengths and both on the common PSF (decision 0003). Each step guards against one failure:

| Step | Guards against |
|---|---|
| Calibration pixels: broadband S/N > 10 in **both** visits, not sky, ≥ 3-pixel 8-connected islands | noise-dominated pixels, cosmic-ray and hot-pixel singletons |
| Mask within 3 × common-PSF FWHM of the target in **both** visits and the view centre | the mover itself (its pixels say nothing about the gain) |
| York et al. (2004) errors-in-variables regression | regression dilution: an ordinary weighted slope is biased low by the noise in B (measured: −3σ on average before this change) |
| Tukey biweight IRLS (c = 4.685) started from the median of per-source flux ratios; residual scale re-estimated by MAD each pass | variable stars, residual artefacts, PSF-mismatch cores (breakdown ≈ 50 % of sources) |
| Systematic term 2·(0.02·f_ref)² in the weights, f_ref a 3×3-smoothed flux | bright cores dominating; weights computed from the noisy pixel itself would correlate with its noise and bias s low |
| 1σ from a bootstrap over **source islands** (200 replicates; 100 per bin), plus a 0.002 floor in quadrature | pixels of one PSF being correlated (a per-pixel covariance would understate the error); interpolation and homogenisation systematics the bootstrap cannot see |
| Per-bin scales shrunk toward the broadband scale with weight σ_k²/(σ_k² + τ²), τ² the DerSimonian–Laird between-bin variance; bins with too little data are pooled and flagged | noisy single bins, while still following a real chromatic gain |
| Offsets c_k anchored on a capped sky-pixel sample | release-to-release background differences, without the sky swamping the slope |
| Refusal with a reason when < 5 static sources qualify, or the broadband scale is outside 0.5–2 | matching on nothing; never falls back to the raw difference |

`matched_difference` applies B → s_k·B + c_k and propagates the uncertainty of the fit into the variance:
σ²_B → s_k²·σ²_B + σ_s,k²·B² + σ_c,k². A poorly determined gain widens the significance; it cannot hide.

**When it is applied.** In `diff(…, photometric_match="auto")` (the default):

- **Mixed-scale pair:** the match is applied, and the difference is refused if it cannot be made.
- **Same-release pair:** the match is computed as a calibration diagnostic (reported, expected ≈ 1) and **never
  applied**, so those differences stay bit-identical to before (tested).
- **`allow_mixed_scales=True`:** keeps the raw, unmatched difference for the validation scripts that measure the F4
  effect (`scripts/verify/g4a_real.py`).

**What may be read from a cross-release difference (workflow.md §11.2).** Positions and motions are valid: the
dipole and `fit_shift` are scale-free. Brightness changes are **not** interpreted, so `annotate` labels a monopole
"residual (brightness not comparable across releases before F4)", and the API's `sign` is `null`. The UI shows this
framing next to the image.

## Evidence (L1, `backend/tests/synthetic/test_synthetic_photmatch.py`; native chain with PA flip, half-channel offset, SIP, dithers)
| Test | Result | Teeth |
|---|---|---|
| QR3 − QR2 with a 0.93 gain, 16 field stars | scale 1.0734 ± 0.0021 (nominal 1/0.93 = 1.0753; the 0.17 % difference is the λ-interpolation and PSF homogenisation the scale correctly absorbs); static-star max 3.1σ, median 1.9σ; median static residual 55.8σ → 1.6σ; k = 1.11 | raw mixed difference: 11.2σ at static stars |
| Chromatic gain 0.92 → 0.98 across band 4 | per-bin scales follow the truth (median pull < 1.5); blue − red > 0.03; τ > 0 | a single broadband scale mis-scales both ends |
| One 40 % variable + a 1.7 px mover | scale unbiased; only the variable remains (> 5σ) and is labelled a residual; the mover is still "moved" | OLS on the same pixels is pulled further from the truth |
| Same release (QR3 − QR3) | diagnostic only, consistent with 1; difference bit-identical to `photometric_match="off"` | — |
| Sparse field | refused: "in-situ photometric match failed … static sources" | — |
| Bootstrap calibration, 40 realisations (numpy scene, floor off) | pulls: mean +0.02, robust σ 1.00 | — |
| 3 of 14 sources 2× brighter in B | robust fit within 3σ | one-pass weighted LS > 5σ off |

The existing 17 L1 pipeline tests pass unchanged, including the G4a static-star, resampling-trap, mover-dipole and
null tests. Cost: ≈ 4.6 s per cross-release difference on a 83 × 83 grid (the bootstrap dominates); results are cached
with the view.

## Open (for I and M)
- **Real-data check before G4a:** Barnard V1 − V5 (band 6) and WISE 0855. Record the fitted scale against F4's
  0.93 and the static residual before → after in `validation/G4a-real/`. M decides whether a cross-release pair may
  count toward G4a, or only same-release pairs.
- `PHOTMATCH_SNR`, `PHOTMATCH_EXCLUDE_FWHM`, the 0.002 floor and `PHOTMATCH_MIN_SOURCES` were chosen on synthetic data
  and need M's approval with the other G4a numbers (workflow.md §4.4).
- When F4 resolves, keep the in-situ match as the cross-check. A pair whose in-situ scale disagrees with the F4
  correction by > 3σ should be flagged, not silently corrected.

## Alternatives rejected
- **Apply `l3_flux_corrections`:** F4 shows that neither direction works.
- **A fixed global 0.93:** F4 measured it on one field. It ignores the chromatic part and gives no per-pair
  uncertainty.
- **Keep refusing:** correct, but it makes the headline target's difference unusable, and the in-situ match is the
  standard remedy.
- **Kernel-based PSF matching (full Alard–Lupton) instead of a scale:** both visits are already homogenised to a
  common Gaussian PSF (0003). A spatially varying kernel would add degrees of freedom that can absorb real motion
  next to the target.
- **Plain least squares:** biased by noise in B (regression dilution) and pulled by variables (both tested).
