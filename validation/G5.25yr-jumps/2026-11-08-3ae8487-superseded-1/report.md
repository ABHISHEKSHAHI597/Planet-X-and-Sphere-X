# G5.25yr-jumps — INCONCLUSIVE (L3)

# G5.25yr-jumps — measured archival → SPHEREx jumps

Verdict **inconclusive**. Runtime 188 s. Label shown in the product: "different telescopes, positions only".

| Target | Ref. epoch | SPHEREx visit | Measured jump ′ | Predicted (pos(t)) ′ | Doc expectation | Old offset from pos(t) ″ | New offset ″ |
|---|---|---|---|---|---|---|---|
| Barnard's Star | 2MASS Ks 2000-05-28 (2 img) | V4 2026.63 (17 fr) | 4.540 | 4.540 | 4.55 ± 0.1 (implementation.md §10.2) | 0.026 | 0.208 |
| eps Ind B | 2MASS Ks 1999-11-08 (2 img) | V6 2026.73 (36 fr) | 2.085 | 2.101 | 2.1 ± 0.1 (implementation.md §4.13 (≈)) | 1.498 | 0.792 |
| WISE 0855-0714 | AllWISE W2 2010-01..2011-02 (0 img) | V4 2026.32 (21 fr) | — | 2.153 | 2.2 ± 0.1 (implementation.md §4.13 (≈)) | — | 0.832 |

Method: module docstring of `scripts/verify/g5_25yr_jumps.py`. Calibration: none needed (positions only; λ unknown). Saturated cores are NaN and excluded from the centroid (count in the JSON).

```json
{
 "barnard": {
  "target": "Barnard's Star",
  "pin": "21a7689afc4b",
  "reference_epoch": "2MASS Ks",
  "reference_year": 2000.405542076503,
  "reference_date": "2000-05-28",
  "reference_images": 2,
  "twomass_match": {
   "designation": "17574849+0441405",
   "ra": 269.452044,
   "dec": 4.694597,
   "k_m": 4.52400016784668,
   "jdate": 2451692.9284,
   "date": "2000-05-28",
   "epoch": 2000.406
  },
  "spherex_visit": "V4",
  "spherex_year": 2026.6277392520835,
  "spherex_frames_stacked": 17,
  "spherex_frames_skipped": 0,
  "grid": {
   "centre": [
    269.4490205549615,
    4.732358200919296
   ],
   "fov_arcmin": 7.810343552675015,
   "pix_arcsec": 3.0,
   "shape": [
    157,
    157
   ]
  },
  "predicted_jump_arcmin": 4.540229035116677,
  "old": {
   "ra": 269.45204833206765,
   "dec": 4.694640164230962,
   "peak_sigma": 3285.4944451957867,
   "offset_from_prediction_arcsec": 0.02608023462607586,
   "n_nan_in_aperture": 0
  },
  "new": {
   "ra": 269.44605713454786,
   "dec": 4.770078979573411,
   "peak_sigma": 44452.42985421625,
   "offset_from_prediction_arcsec": 0.20784799842224247,
   "n_nan_in_aperture": 0
  },
  "measured_jump_arcmin": 4.540483889983
 },
 "epsindb": {
  "target": "eps Ind B",
  "pin": "3addc0f80339",
  "reference_epoch": "2MASS Ks",
  "reference_year": 1999.8523643835613,
  "reference_date": "1999-11-08",
  "reference_images": 2,
  "twomass_match": {
   "designation": "22041052-5646577",
   "ra": 331.043836,
   "dec": -56.782707,
   "k_m": 11.208000183105469,
   "jdate": 2451490.613,
   "date": "1999-11-08",
   "epoch": 1999.852
  },
  "spherex_visit": "V6",
  "spherex_year": 2026.7329638129136,
  "spherex_frames_stacked": 36,
  "spherex_frames_skipped": 0,
  "grid": {
   "centre": [
    331.0708946911894,
    -56.791995963904036
   ],
   "fov_arcmin": 4.151246612535937,
   "pix_arcsec": 3.0,
   "shape": [
    83,
    83
   ]
  },
  "predicted_jump_arcmin": 2.100831075023958,
  "old": {
   "ra": 331.0443957891437,
   "dec": -56.78296819732446,
   "peak_sigma": 39.689179735224414,
   "offset_from_prediction_arcsec": 1.4984381599433858,
   "n_nan_in_aperture": 0
  },
  "new": {
   "ra": 331.09813649729034,
   "dec": -56.80143590310644,
   "peak_sigma": 416.5026441222366,
   "offset_from_prediction_arcsec": 0.7921148274361245,
   "n_nan_in_aperture": 0
  },
  "measured_jump_arcmin": 2.084800448347547
 },
 "wise0855": {
  "target": "WISE 0855-0714",
  "pin": "325c57328320",
  "reference_epoch": "AllWISE W2",
  "reference_year": 2010.5,
  "reference_date": "2010-01..2011-02",
  "reference_images": 0,
  "twomass_match": null,
  "spherex_visit": "V4",
  "spherex_year": 2026.320135164043,
  "spherex_frames_stacked": 21,
  "spherex_frames_skipped": 0,
  "grid": {
   "centre": [
    133.77693966513232,
    -7.243559336024649
   ],
   "fov_arcmin": 4.228832879987818,
   "pix_arcsec": 3.0,
   "shape": [
    85,
    85
   ]
  },
  "predicted_jump_arcmin": 2.152555253325212,
  "old": null,
  "new": {
   "ra": 133.7588606028951,
   "dec": -7.241870931745725,
   "peak_sigma": 14.117432039018443,
   "offset_from_prediction_arcsec": 0.8317044114799093,
   "n_nan_in_aperture": 0
  }
 }
}
```

## Metrics

| metric | value | threshold | pass |
|---|---|---|---|
| barnard_jump_arcmin | 4.540483889983 | 4.55 ± 0.1 (implementation.md §10.2, 2MASS Ks → SPHEREx) | True |
| barnard_predicted_jump_arcmin | 4.540229035116677 | pos(t) at the actual epochs (informational) | None |
| epsindb_jump_arcmin | 2.084800448347547 | 2.1 ± 0.1 (implementation.md §4.13 (≈), 2MASS Ks → SPHEREx) | True |
| epsindb_predicted_jump_arcmin | 2.100831075023958 | pos(t) at the actual epochs (informational) | None |
| wise0855_jump_arcmin | None | 2.2 ± 0.1 (implementation.md §4.13 (≈), AllWISE W2 → SPHEREx) | False |
| wise0855_predicted_jump_arcmin | 2.152555253325212 | pos(t) at the actual epochs (informational) | None |

## Caveats

- Archival and SPHEREx fluxes are not compared (positions only).
- The §4.13 ε Ind B and WISE 0855 expectations are approximate (≈) and computed for Aug 2026; the predicted jump at the actual epochs is listed beside each measurement.
- recorded on a dirty working tree: code_digest identifies the exact code

git 3ae8487 (dirty) · contracts {'spherex.types': '0.1.0', 'http-api': '0.1.0'} · calibration none (positions only) · author I · reviewer pending
