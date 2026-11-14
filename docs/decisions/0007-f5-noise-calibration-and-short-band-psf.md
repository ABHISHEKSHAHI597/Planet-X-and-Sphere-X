# 0007 — F5: VARIANCE is 10–28 % low in D1–D4; the short-band ePSF residual is field-dependent

2026-11-08. Author: integration pass (acting for M). **Independent review required** (workflow §9.4): I reviews the
record `validation/M-noise-scale/2026-11-08-5f9f54b`; M (a human, not the author) reviews this decision.
No production change, no flag change.

## Question
F5 fails because the median reduced χ² of native ePSF fits exceeds 3 in D1–D4 (4.46 / 3.57 / 3.27 / 3.60) but not in
D5–D6 (1.43 / 1.19). `M-epsf-residuals` showed blank-sky pulls with robust σ ≈ 2.1–2.3 in D1–D4. Is F5 a noise-model
failure (VARIANCE too small) rather than a PSF failure?

## History of this analysis (kept, because it changed the answer)
- **r1** (record `M-noise-scale/2026-11-08-3ae8487`): one sky-mask noise scale (16-px blocks), F5's rule, antisymmetry
  against an analytic √(1/2N) noise level → "fail, D1 3.59, antisymmetric PSF residual in D1–D3".
- **Reviewer aid** (`scripts/verify/m_noise_scale_review.py`) showed r1 was fragile: D1 moved 2.08 → 3.98 with block
  size (each size kept a different subset of frames), and the analytic yardstick was miscalibrated (under a sign-flip
  permutation null D1's antisymmetry was not significant).
- **r2** (record `M-noise-scale/2026-11-08-5f9f54b`, **inconclusive**): four estimators, permutation tests per field,
  a conservative pre-stated rule. This decision rests on r2.
- The ≈ 2.2× figure from `M-epsf-residuals` came from a Gaia-only (G < 18) mask that leaves fainter sources in the
  "sky"; it is an upper bound and is not used.

## Result (r2; 491 stars, 22 frames, two fields, locked calibration)
| D | χ²ᵣ VARIANCE | noise scale s (4 estimators) | χ²ᵣ after calibration (range over estimators) | antisymmetry p: Barnard field / ε Ind B field |
|---|---|---|---|---|
| 1 | 4.46 | 1.10–1.23 | 2.08–3.98 (difference estimator, all 87 stars: 3.21) | 0.027 / **0.0002** |
| 2 | 3.57 | 1.17–1.25 | 1.23–2.62 | 0.99 / **0.0017** |
| 3 | 3.27 | 1.11–1.28 | 1.48–2.41 | 0.66 / **0.0002** |
| 4 | 3.60 | 1.15–1.25 | 1.75–3.25 | 0.15 / 0.13 |
| 5 | 1.43 | 1.02–1.06 | 1.23–1.45 | 0.50 / 0.80 |
| 6 | 1.19 | 1.01–1.04 | 1.07–1.15 | 0.42 / (n = 4) |

## Decision
1. **VARIANCE underestimates the sky noise by ≈ 10–28 % in σ in D1–D4** and ≈ 2–6 % in D5–D6, consistently across
   block sizes and an independent adjacent-difference estimator. This explains most, not all, of the short-band χ².
2. **F5 is not repaired and not accepted.** After noise calibration D2–D3 fall below 3 under every estimator, but D1
   and D4 still exceed 3 under some estimators. The record's verdict is **inconclusive**; F5's own record stays
   **fail** (its rule uses VARIANCE as delivered).
3. **The short-band PSF residual is field-dependent, not global.** A significant antisymmetric residual appears in
   D1–D3 in the ε Ind B field and not, or only weakly, in the Barnard field. That points to a zone- or
   position-dependent ePSF mismatch (or a field-specific systematic such as crowding or a frame-specific PSF), not a
   uniform shape or orientation error. Decision 0004/0006's orientation and width experiments are consistent with this.
4. **No production noise rescaling and no PSF change are adopted.** Neither is established by two fields.
   `preprocess.sky_noise_scale` stays as a tested diagnostic.
5. **Next experiment (pre-state it before running):** more fields (≥ 4, including both hemispheres and several ePSF
   zones per detector), 24′ cutouts so every detector has enough sky, the difference estimator as the primary noise
   scale, and residuals binned by ePSF zone to test the zone-dependence hypothesis; a held-out field decides.
