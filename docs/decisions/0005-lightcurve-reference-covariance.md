# Spectral-reference smoothing and covariance

## Covariance-aware search amendment

`correlated_periodogram` now whitens the supplied covariance by eigenvalue
decomposition. Positive stochastic directions above 1e-10 of the largest
eigenvalue are retained; negative eigenvalues beyond numerical tolerance are
rejected. A GLS constant-plus-sinusoid search uses Astropy's frequency grid.
Reference-normalization null directions add no observations. The simulated
Gaussian null uses the same covariance subspace, fitted constant, frequency
grid, and maximum-over-grid statistic as the data. A fixed seed and 1024 trials
are reported, with exceedance count and resolution 1/1025; no zero FAP or
significance below that resolution is claimed. Detector curves are combined
with an explicit linear map, propagating their complete covariance to the
independent-time-bin curve before searching.

This supersedes suppression of FAP for supported covariance inputs. It is
conditional on the estimated Gaussian measurement-noise covariance and the
linearized reference; it does not include changing median order, temporal
template bias, calibration or PSF mismatch. Tests recover a 245-day injection,
handle a singular normalization covariance, check permutation/reproducibility,
and run 30 independent correlated null experiments. Real AAVSO phase and G5.lc
acceptance remain outstanding; I's independent review is still required.

Role M, 2026-11-08; independent I review pending. Implements A section 4.9.

PSF light curves use temporal channel medians followed by a normalized [1,2,1]
kernel across adjacent observed channels of each detector. No detector boundary
or missing-channel gap is bridged. This is an explicit engineering smoothing
choice, not a new physical calibration. Annulus curves retain separate
detector/channel/parent-region medians without spectral smoothing.

Each ratio's first-order derivative includes both its numerator and its estimated
reference. Propagating independent measurement variance through this derivative
and the fixed inverse-variance bin weights retains cross-bin covariance. Median
ties share derivatives; the approximation is conditional on median order and bin
weights. A reference below five times its measurement uncertainty is excluded.
No finite ePSF wings or missing channels are extrapolated.

The API exports covariance with explicit detector/bin ordering, reference samples
and an uncertainty description. Synthetic noise trials compare the full method's
output scatter against predicted variances, test covariance positivity and
cross-detector isolation. A common multiplicative release calibration cancels;
the PSF extraction uses its statistical error instead of independently counting
the shared 3% floor on each point. Differential wavelength calibration, temporal
sampling of a variable source, PSF mismatch and changing median order remain
outside this conditional measurement covariance.

Astropy's independent-error analytic FAP is suppressed (nullable contract and UI)
for these reference-normalized curves. The marginal-error periodogram peak is
exploratory. A calibrated correlated-noise periodogram/FAP and external coherent
phase validation are still required; this decision does not approve G5.lc.

Real pinned RW Aur QR2 extraction returned only two D1 bins and 211 rejected
measurements. It tests transport/integration, not three-visit scientific
acceptance. F4/F5 failures and I's independent review remain separate.
