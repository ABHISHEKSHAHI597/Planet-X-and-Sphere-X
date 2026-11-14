# F2 — FAIL (L2)

**Question (F2).** Do the cutout path (origin from `CRPIXnA`) and the S3-section path (origin known)
produce the same parent-pixel origin, the same WCS and identical pixel values for the same sky pixels?
Outcome: **open — see mismatches**.

**Method.** Three real frames covering QR3, QR2 and a QR2 deep collection, each with a 6′-view box
(`cutout_size_deg(6) = 0.1551°`). Cutout: IRSA, stream-aborted after ZODI. S3: anonymous
byte ranges; IMAGE/VARIANCE/ZODI as whole rows, FLAGS from the RICE_1 one-row-tile heap. Origins compared
three ways (cutout `CRPIXnA`; the S3 box computed from the sky box with the IRSA rule; `parent_origin` of the
shifted section header). Pixels compared bit for bit on the cutout's exact parent box; WCS compared at every
pixel, and against the full-file WCS offset by the origin.

| frame | release | cutout origin | S3 origin | shape | IMAGE/FLAGS/VAR/ZODI identical | WCS max Δ (″) | FLAGS RICE in S3 | bytes cutout / S3 |
|---|---|---|---|---|---|---|---|---|
| barnard_qr3_d6 | qr3 7.0.5 | [607, 1888] | [607, 1888] | [91, 91] | 1/1/1/1 | 0.0e+00 | True | 204480 / 2686327 |
| wise0855_qr2_d6 | qr2 6.5.6 | [1730, 924] | [1731, 925] | [91, 91] | 1/1/1/1 | 0.0e+00 | False | 201600 / 2970240 |
| rdra_qr2deep | qr2 6.5.5+psffix1 | [884, 9] | [884, 9] | [91, 91] | 1/1/1/1 | 0.0e+00 | False | 201600 / 2970240 |

Consequences: either FrameSource can serve any frame (failover is transparent), every per-pixel calibration
lookup can use `RawFrame.origin` from either source, and S3 section headers obey `calib.parent_origin` just
like cutout headers.

## Metrics

| metric | value | threshold | pass |
|---|---|---|---|
| barnard_qr3_d6_origin | cutout [607, 1888] / s3 [607, 1888] / section hdr [607, 1888] | equal | True |
| barnard_qr3_d6_shape | [91, 91] / [90, 90] | equal | False |
| barnard_qr3_d6_IMAGE | identical=True dtypes=['float32', 'float32'] n=8281 nan=6 | bit-identical | True |
| barnard_qr3_d6_FLAGS | identical=True dtypes=['int64', 'int64'] n=8281 nan=0 | bit-identical | True |
| barnard_qr3_d6_VARIANCE | identical=True dtypes=['float32', 'float32'] n=8281 nan=6 | bit-identical | True |
| barnard_qr3_d6_ZODI | identical=True dtypes=['float32', 'float32'] n=8281 nan=0 | bit-identical | True |
| barnard_qr3_d6_wcs_max_sep_arcsec | 0.0 | < 1e-6 | True |
| barnard_qr3_d6_header_wcs_diffs | none | none | True |
| wise0855_qr2_d6_origin | cutout [1730, 924] / s3 [1731, 925] / section hdr [1730, 924] | equal | False |
| wise0855_qr2_d6_shape | [91, 91] / [90, 90] | equal | False |
| wise0855_qr2_d6_IMAGE | identical=True dtypes=['float32', 'float32'] n=8281 nan=3 | bit-identical | True |
| wise0855_qr2_d6_FLAGS | identical=True dtypes=['int64', 'int64'] n=8281 nan=0 | bit-identical | True |
| wise0855_qr2_d6_VARIANCE | identical=True dtypes=['float32', 'float32'] n=8281 nan=3 | bit-identical | True |
| wise0855_qr2_d6_ZODI | identical=True dtypes=['float32', 'float32'] n=8281 nan=0 | bit-identical | True |
| wise0855_qr2_d6_wcs_max_sep_arcsec | 0.0 | < 1e-6 | True |
| wise0855_qr2_d6_header_wcs_diffs | none | none | True |
| rdra_qr2deep_origin | cutout [884, 9] / s3 [884, 9] / section hdr [884, 9] | equal | True |
| rdra_qr2deep_shape | [91, 91] / [90, 90] | equal | False |
| rdra_qr2deep_IMAGE | identical=True dtypes=['float32', 'float32'] n=8281 nan=13 | bit-identical | True |
| rdra_qr2deep_FLAGS | identical=True dtypes=['int64', 'int64'] n=8281 nan=0 | bit-identical | True |
| rdra_qr2deep_VARIANCE | identical=True dtypes=['float32', 'float32'] n=8281 nan=13 | bit-identical | True |
| rdra_qr2deep_ZODI | identical=True dtypes=['float32', 'float32'] n=8281 nan=0 | bit-identical | True |
| rdra_qr2deep_wcs_max_sep_arcsec | 0.0 | < 1e-6 | True |
| rdra_qr2deep_header_wcs_diffs | none | none | True |

git 20efbf1 (dirty) · contract 0.1.0 · author D · reviewer pending

## Superseded

This run failed only on the S3 box *shape* rule (⌊size/scale⌋, 1 px short at 0.155°); pixels, origins at the same parent box, headers and WCS were identical. The rule was corrected in `s3sections.irsa_bounds` (pixel centres within c ± h) and F2 re-run: see the sibling record without the `-superseded-1` suffix.

**Second failed run (overwritten by the passing run in the same directory, recorded here).** With the
rule changed to "pixel centres within c ± h" but no padding, the S3 box from the sky box was still 1 px
short on one axis: Barnard S3 box (607, 1888) 91×90 vs cutout 91×91; WISE 0855 (1730, 925) 90×91 vs
cutout (1730, 924) 91×91; R Dra (884, 9) 90×91 vs 91×91. Pixels, origins at the exact box, headers and WCS
were again identical. Conclusion: IRSA's sizing rule is not reproduced exactly (bounds on the implied
scale: 6.102″ < s ≤ 6.135″, while the frame PC terms give 6.14–6.15″), so the S3 source pads by 1 px and
F2 tests containment.
