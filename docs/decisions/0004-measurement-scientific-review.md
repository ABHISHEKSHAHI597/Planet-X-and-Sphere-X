# 0004 — Role M measurement and imaging evidence review

2026-11-08. Author/reviewer of I's evidence: M. Independent reviewer of M's code and evidence: **I, pending**.

The governing hierarchy is workflow §1. No synthetic test or catalogue prediction is a real-image acceptance result.

* **0001 partial merging: approve the rule**, not an overall gate. The 21-day total-span bound preserves the
  observed WISE 3/16/3/21 band-6 clusters. The former 45-day-neighbour rule contradicted the real MJDs.
* **0002 time axis: approve as the configured engineering classification for these pins.** A 60-day maximum
  cluster span separates epsilon Indi's 46-day tails from R Dra's 89-day-or-longer clusters. It is not a
  universal physical definition of a visit. The stale legacy record cannot establish G1 by itself.
* **0003 resampling: retain the implementation as experimental and reject release acceptance.** Reversed LVF
  gradients require per-pixel wavelengths; interpolation needs both sampled support and a maximum gap. Bicubic
  interpolation and broadening address phase-dependent undersampling, but they do not establish the proposed
  2% flux and 0.05-pixel gradient error terms on independent real fields. Those terms need held-out calibration
  and uncertainty coverage tests. Do not enlarge them just to hide residuals.
* **G4a statistics: reject the proposed replacement criterion.** A post-hoc star-box exceedance rate of up to
  twice the sky-box rate is not the documented <3-sigma residual criterion. Maxima over 3x3 correlated pixels
  have a look-elsewhere distribution. Report that distribution, a PSF-amplitude residual and independent
  sky trials; neither a p90 nor a maximum may silently replace the requirement. Cross-release residuals
  in the retained record visibly fail, so `diff` remains unavailable in releases.
* **Barnard shift fit: retain as a diagnostic.** Fitting one matched image to another with free scale is
  useful when cores are missing. Reused/interpolated samples, masked support, field backgrounds and a free
  scale can bias its shift and its uncertainty. The 1.62-pixel self-template fit is not an independent PM
  measurement. G3 still needs native-frame centroids and differential registration, catalogue comparison
  and visit-correlated uncertainty. No scale-free fit validates mixed-release fluxes.
* **G2 registration: narrow the claim to the tested band/field.** Norm of the median vector measures a
  translation; median per-star radial separation measures a distribution. Both are needed to expose
  cancellation. One band-6 field is not all five targets in six bands.
* **G4b WISE: reject a single-pixel S/N as source S/N.** The blue light and some band-6 light belong to the
  nearby Gaia star. Use simultaneous signed-flux fits and blend covariance, and a free-target-centroid
  blend model for motion. A non-detection is not zero flux or a log magnitude. Do not label the pixel empty.
* **F4: direction established from the locked header** (`COMMENT Multiplicative flux correction factor for
  pre-QR3 data`, `DETCOORD=sky`). The required real matched-star improvement check remains separate and
  unaccepted until measured. Production retains separate QR2/QR3 scales; no mixed indices/curves/diffs.
* **F5: use QR3 ePSF for QR2 too**, following the official IRSA ePSF tutorial. Preserve table orientation,
  normalize the oversampled integral to 25, point sample with a smooth zero extension, and never extend
  its finite support into R Dra's 3–6-pixel annulus. Native-star residuals, not the table header, decide F5.
* **F10: corrected response order.** Horizons sorts epochs; all results must be mapped back to the caller's
  order, including duplicates. Three mission epochs agree with geocentric ICRF-equatorial vectors within
  10 km without fitting a rotation/time offset. This passes the numerical foundation; I review remains.
* **Saturation: no brightness cut replaces flags.** Keep late ramp-fitted OVERFLOW photometry with a quality
  warning; exclude SUR_ERROR/nonfinite cores. Astrometric references exclude OVERFLOW. Model-filled display
  pixels never enter measurements. Unconstrained wings fail explicitly; annulus output is qualitative.
* **Light curves:** same detector/channel **and parent region** for annuli. Singleton groups cannot define
  a relative time series. Spectral and temporal variability must not be conflated. At least 20 independent
  time bins are required for R Dra acceptance; multiple bands at one epoch are not independent extra bins.

Primary references inspected: [IRSA ePSF tutorial](https://caltech-ipac.github.io/irsa-tutorials/spherex-psf/),
[data products](https://caltech-ipac.github.io/spherex-archive-documentation/spherex-data-products/),
[Supplement](https://irsa.ipac.caltech.edu/data/SPHEREx/docs/SPHEREx_Expsupp_QR.pdf).

Outdated text: implementation §16's temporary-target and missing-M-module rows are superseded by §17;
implementation §15's historical 45-day time-axis row is superseded by §4.2 and decision 0002. The estimated
"empty blue" demo script (§11.4 step 4) must be read with understanding §8.4's actual blend finding.
