# F1 — PASS (L2)

**Question.** Does `CWAVE` (spectral_wcs, sliced at parent pixels) agree with each L2 file's `WCS-WAVE`
lookup to ≈1 nm, in the same orientation as `IMAGE`? Outcome: **confirmed**.

**Method.** For each detector, every 40th row of CWAVE (51 rows × 2040) against the bilinear lookup of
the `WCS-WAVE` table of one full QR3 L2 file (raw 1-based FITS coordinates, alt WCS `W`, `CRPIXnW = 1`
for full files). Orientation teeth: the same comparison with the lookup flipped in x and in y. Cutout
path: the 29×29 fixture's pixels mapped to parent pixels with `CRPIXnA` (`parent_origin`), against the
same lookup evaluated through the cutout's own alt WCS `W`. S3-section path: the same 29 rows read from
the full S3 file at origin (638, 1919).

| det | p99 |Δλ| nm | max nm | x-flipped p99 | y-flipped p99 | L2 table = cal table | DETCOORD |
|---|---|---|---|---|---|---|---|
| D1 | 0.76 | 1.37 | 0.94 | 380 | True | sky |
| D2 | 0.72 | 95.61 | 1.01 | 565 | True | sky |
| D3 | 1.16 | 5.34 | 1.90 | 801 | True | sky |
| D4 | 2.52 | 5.60 | 4.88 | 1425 | True | sky |
| D5 | 0.86 | 11.16 | 3.04 | 625 | True | sky |
| D6 | 1.27 | 2.29 | 1.90 | 604 | True | sky |

Findings: L2 files carry exactly the calibration file's WCS-WAVE table; CWAVE agrees with it at the
p99 level of 0.7–2.5 nm (D4 widest, matching its header `WLERRP99`). Maxima of 5–96 nm are localised
CWAVE structure the 9×9–13×20 lookup cannot follow (D2: 9 pixels near x≈40, row 1400; D5: the y = 0
edge), so CWAVE, not WCS-WAVE, must be used for science (as planned). A y-flip is excluded by a factor
≥ 300; an x-flip is worse on every detector but only by 1.2–3.5× (λ depends weakly on x), so the
x-orientation rests on that consistent preference plus `DETCOORD='sky'` in both files. In the cutout,
`CRPIXnW = CRPIXnA`, i.e. the λ lookup and the parent-pixel origin agree; the S3 section returns the
same pixel values as the cutout for all four HDUs.

**New fact for D (F2, S3 sections):** in full L2 files `FLAGS` is a RICE_1 tile-compressed BINTABLE
(`ZBITPIX = 32`, one-row tiles, ≈11 MB), not a plain image, so FLAGS byte offsets differ from IMAGE,
VARIANCE and ZODI (which are plain 16,646,400-byte images). One-row tiles make row sections cheap:
fetch the row descriptors, then each row's heap bytes (`scripts/verify/_archive.py::s3_rice_rows`).

## Metrics

| metric | value | threshold | pass |
|---|---|---|---|
| D1_p99_nm | 0.76 | < 3.0 | True |
| D1_max_nm | 1.37 | reported (localised structure) | None |
| D2_p99_nm | 0.72 | < 3.0 | True |
| D2_max_nm | 95.61 | reported (localised structure) | None |
| D3_p99_nm | 1.16 | < 3.0 | True |
| D3_max_nm | 5.34 | reported (localised structure) | None |
| D4_p99_nm | 2.52 | < 3.0 | True |
| D4_max_nm | 5.6 | reported (localised structure) | None |
| D5_p99_nm | 0.86 | < 3.0 | True |
| D5_max_nm | 11.16 | reported (localised structure) | None |
| D6_p99_nm | 1.27 | < 3.0 | True |
| D6_max_nm | 2.29 | reported (localised structure) | None |
| cutout_p99_nm | 0.66 | < 3.0 | True |
| cutout_CRPIXnW_equals_CRPIXnA | True | True | True |
| section_lambda_identical_to_cutout | True | same parent slice | True |
| section_pixels_equal_cutout | {'IMAGE': True, 'FLAGS': True, 'VARIANCE': True, 'ZODI': True} | all True (supporting evidence for F2, owner D) | True |

## Caveats

- CWAVE sampled every 40th row for D1–D5 (full map for D6)
- one L2 file per detector (Barnard field, QR3); QR2 files not checked (same calibration product)

git c12717d (dirty) · contract 0.1.0 · author I · reviewer pending
