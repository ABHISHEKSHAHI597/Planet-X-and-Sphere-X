# 0003 — Resampling systematics in the λ-matched difference

**Date:** 2026-11-06 · **Owner:** I · **Reviewer:** M (reviewed; proposed systematics rejected for release, 2026-11-08; decision 0004) · **Status of the numbers:** proposed

## Context
implementation.md §4.6's synthetic test generated frames directly on the common grid. Running the same
algorithm on *native* synthetic frames (TAN-SIP, PA 0°/180°, dithers, CWAVE per detector) through the
real reprojection showed static-star residuals of 16–30σ at peak S/N ≈ 90 per frame, even for flat
spectra with no PA flip (`tests/synthetic/test_synthetic_pipeline.py::test_synthetic_resampling_trap_teeth`).
Cause: the PSF (FWHM ≈ 1.46 native px) is undersampled, so bilinear resampling changes its shape with
sub-pixel phase, and each cube bin holds a single frame; the phase error does not average down.

On real data a second effect appeared: Barnard's band-6 core is masked in 52/59 frames (TRANSIENT +
SUR_ERROR early events), so a Gaussian two-PSF dipole fit sees only non-Gaussian wings (3.7 px fitted
vs 1.68 px predicted).

## Decision (difference path only; stacks keep bilinear)
1. Resample with NaN-safe bicubic (`grid.to_grid(order="bicubic")`: holes filled for the spline and
   re-masked, dilated 2 px).
2. Homogenise every frame of both visits to a Gaussian-equivalent PSF of 1.5 × the largest
   `PSF_FWHM` (`cube.homogenise`, `diff_fwhm_arcsec`).
3. Add resampling systematics to the bin variance: (0.02·F)² + (0.05 px·|∇F|)² per visit
   (`DIFF_SYS_FRAC`, `DIFF_SYS_SHIFT_PX`, ZOGY-style astrometric term).
4. `at_wavelengths` brackets with the nearest *sampled* bins (equal to the documented adjacent-bin
   version wherever that version is defined, `tests/unit/test_cube_grid_unit.py`); `max_interp_ch`
   (2 by default, 3 for the null test) bounds the bridge.
5. Dipole shifts are measured with `cube.fit_shift` (B's own λ-matched image fitted onto A, free scale),
   which works with masked cores; the Gaussian model still decides dipole vs monopole.

Synthetic result: static stars ≤ 2.7σ from S/N 6 to 370 per frame on two seeds, 1.7 px mover recovered
to ±0.1 px at ≥ 50σ. Real result (`validation/G4a-real/`): Barnard V1→V3 1.62 px at 354° (criterion
1.5–1.9 px, 356° ± 15°); same-release PA-flip and null residuals at star positions match the noise rate
of the same statistic.

## Open
- ε and σ_r were chosen on synthetic data; the real null test is consistent with them but M must
  approve them before G4a (workflow.md §4.4).
- QR3 − QR2 differences leave 3× the noise rate of residuals (positive monopoles): F4 (owner M).

## Alternatives rejected
- Bilinear without homogenisation (documented): fails the synthetic test above.
- Larger ε only: hides real faint changes at bright stars; the gradient term targets the cause.
- `reproject_exact`: also phase-dependent for one frame per bin, ≈10× slower.
