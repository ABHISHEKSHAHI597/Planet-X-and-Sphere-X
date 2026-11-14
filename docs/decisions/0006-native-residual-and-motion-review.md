# Native residual, motion and external-reference review

Role M, 2026-11-08. Independent I review pending; no science flag promotion.

## F5/F15

Reproduced the 421-star real native-frame sample. F5 fails and F15 remains
inconclusive. Eight orientation/reflection experiments, five Gaussian widths,
and constant-versus-planar local sky experiments are retained separately.
The latter uses correct additional parameter counts and an explicit stable
source-level training/holdout split. Across 99 samples, plane-sky detector
medians are 2.944/3.768/2.548/2.909/1.288/1.184. Short-band mismatch persists.
These experiments reject simple width or local-gradient explanations as a
sufficient repair. They do not uniquely distinguish chromatic/spatial ePSF
mismatch from all calibration/variance or unresolved-neighbour contributions.
The optional plane fit is tested but the production constant-sky default stays.
No input-variance inflation, relaxed residual threshold or post-hoc pass is used.

Next discriminating experiment: normalized residual maps versus subpixel phase,
zone, wavelength and flux on independent isolated-star fields, with held-out
zones/epochs; check variance against repeated blank-sky and source measurements.
An empirically revised PSF needs independent training/validation coverage before
replacing the mission table. Existing two-field samples do not establish that.

## WISE

Audit confirmed xi=east, eta=north, PA=atan2(east,north), later-minus-earlier
epochs. Catalogue predictions evaluated at the same epochs give approximately
277 degrees; no coordinate flip is justified. Four accepted D6 centroids were
insufficient. Removed an erroneous prerequisite on a single-source fit before
the required two-source fit; align the fixed neighbour with the measured local
registration. WISE astrometry now acquires only D6, with a 30-arcminute field and
15-arcminute Gaia cone to retain the same five-star isolation/SNR requirement.
This yields 16 and 19 full-visit centroids without lowering quality cuts.

The wider field's arithmetic displacement 0.8043 px / PA 289.47 degrees passes
the nominal numerical window, but covariance-aware means yield 1.0030 px /
304.53 +/-4.36 degrees and excess scatter. An arithmetic pass is insufficient
when the reported heteroscedastic errors disagree. The acceptance runner now
uses `visit_centroid` GLS; all earlier arithmetic records remain superseded.
The diagnostic/gate reanalysis fails with unchanged 0.78 +/-0.3 px and
277 +/-20 degree thresholds. No new centroid rejection was tuned to PA.

Next: joint native-pixel visit likelihood with per-frame colour amplitudes,
neighbour covariance and registration nuisance terms; evaluate pixel residuals
and injection recovery at the real noise/crowding. Independent F5/F15 acceptance
and visit-correlated systematic conditioning remain necessary for G3.

## References and overlays

Observed M/L/T templates are integrated with separately fitted visit/release
scales. CBAND boxcar averaging is explicitly approximate; incomplete coverage,
telluric/order gaps and missing flux are rejected. Template noise/calibration
does not enter the target-noise-only scale error, so overlays are illustrative,
not spectral-type likelihoods. Y/grid completion and independent colour checks
remain open. SOURCE flags are not a reason to hide valid science points.

Acquired 325 V and 406 visual AAVSO R Dra observations over the SPHEREx interval,
plus VSX period 246.12 d and HJD epoch 2457370. Original responses, URLs, hashes,
phase points and a labeled phase figure are retained. SPHEREx has 18 distinct
retained bins, below the required 20. Visual error blanks remain blanks; optical
and infrared amplitudes/phase lags are not assumed identical. The comparison
requires independent coherence review and does not pass G5.lc.

IRSA external-export comparison tooling now enforces matching frames/channels,
release, units and bright-source S/N; all matched channels must agree within
10%. No genuine independent Spectrophotometry Tool export has been supplied to
it, and no L4 agreement was manufactured from synthetic tests.

## Pluto

Actual-epoch header checks reject geometric noncoverage before requesting up
to six native cutouts. Six detector samples were acquired. D6's centroid is
0.0365 px from Horizons (S/N 4.50, reduced chi-square 1.008); D1/D2 have high
S/N but excess PSF residuals, and D4's centroid is about 1.03 px away. Raw
quantized cutout-centre offsets are not tracked display-grid offsets. This is
image-level evidence, not proof of every-frame track centring, streaming stars
or methane-ice spectral dips. Full valid-epoch track/spectral recovery remains
an experiment to perform after the measurement foundations are corrected.
