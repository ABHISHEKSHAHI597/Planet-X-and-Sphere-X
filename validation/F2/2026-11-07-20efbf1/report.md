# F2 — PASS (L2)

**Question (F2).** Do the cutout path (origin from `CRPIXnA`) and the S3-section path (origin known)
produce the same parent-pixel origin, the same WCS and identical pixel values for the same sky pixels?
Outcome: **confirmed**.

**Method.** Three real frames covering QR3, QR2 and a QR2 deep collection, each with a 6′-view box
(`cutout_size_deg(6) = 0.1551°`). Cutout: IRSA, stream-aborted after ZODI. S3: anonymous
byte ranges; IMAGE/VARIANCE/ZODI as whole rows, FLAGS from the RICE_1 one-row-tile heap. Origins compared
three ways (cutout `CRPIXnA`; the S3 box computed from the sky box with the IRSA rule; `parent_origin` of the
shifted section header). Pixels compared bit for bit on the cutout's exact parent box; WCS compared at every
pixel, and against the full-file WCS offset by the origin. The S3 box computed from the *sky* box uses an
empirical copy of IRSA's sizing (pixel centres within c ± size/2) padded by 1 px, because IRSA's exact rule
is not public (an unpadded run, `-superseded-1`, was 1 px short on one axis): it must contain the cutout box.

| frame | release | cutout origin | S3 box origin | cutout shape | IMAGE/FLAGS/VAR/ZODI identical | WCS max Δ (″) | FLAGS RICE in S3 | bytes cutout / S3 |
|---|---|---|---|---|---|---|---|---|
| barnard_qr3_d6 | qr3 7.0.5 | [607, 1888] | [606, 1887] | [91, 91] | 1/1/1/1 | 0.0e+00 | True | 204480 / 2686327 |
| wise0855_qr2_d6 | qr2 6.5.6 | [1730, 924] | [1729, 924] | [91, 91] | 1/1/1/1 | 0.0e+00 | False | 201600 / 2970240 |
| rdra_qr2deep | qr2 6.5.5+psffix1 | [884, 9] | [883, 8] | [91, 91] | 1/1/1/1 | 0.0e+00 | False | 201600 / 2970240 |

Consequences: either FrameSource can serve any frame (failover is transparent), every per-pixel calibration
lookup can use `RawFrame.origin` from either source, and S3 section headers obey `calib.parent_origin` just
like cutout headers.

## Metrics

| metric | value | threshold | pass |
|---|---|---|---|
| barnard_qr3_d6_origin | cutout [607, 1888] / s3 [606, 1887] / section hdr [607, 1888] | equal | True |
| barnard_qr3_d6_s3_box_contains_cutout | cutout [607, 1888] [91, 91]; S3 box [606, 1887] [93, 92]; edge offsets (x0, y0, x1, y1) [-1, -1, 0, 1] | S3 box ⊇ cutout box (failover never loses pixels) | True |
| barnard_qr3_d6_IMAGE | identical=True dtypes=['float32', 'float32'] n=8281 nan=6 | bit-identical | True |
| barnard_qr3_d6_FLAGS | identical=True dtypes=['int64', 'int64'] n=8281 nan=0 | bit-identical | True |
| barnard_qr3_d6_VARIANCE | identical=True dtypes=['float32', 'float32'] n=8281 nan=6 | bit-identical | True |
| barnard_qr3_d6_ZODI | identical=True dtypes=['float32', 'float32'] n=8281 nan=0 | bit-identical | True |
| barnard_qr3_d6_wcs_max_sep_arcsec | 0.0 | < 1e-6 | True |
| barnard_qr3_d6_header_wcs_diffs | none | none | True |
| wise0855_qr2_d6_origin | cutout [1730, 924] / s3 [1729, 924] / section hdr [1730, 924] | equal | True |
| wise0855_qr2_d6_s3_box_contains_cutout | cutout [1730, 924] [91, 91]; S3 box [1729, 924] [92, 93]; edge offsets (x0, y0, x1, y1) [-1, 0, 1, 1] | S3 box ⊇ cutout box (failover never loses pixels) | True |
| wise0855_qr2_d6_IMAGE | identical=True dtypes=['float32', 'float32'] n=8281 nan=3 | bit-identical | True |
| wise0855_qr2_d6_FLAGS | identical=True dtypes=['int64', 'int64'] n=8281 nan=0 | bit-identical | True |
| wise0855_qr2_d6_VARIANCE | identical=True dtypes=['float32', 'float32'] n=8281 nan=3 | bit-identical | True |
| wise0855_qr2_d6_ZODI | identical=True dtypes=['float32', 'float32'] n=8281 nan=0 | bit-identical | True |
| wise0855_qr2_d6_wcs_max_sep_arcsec | 0.0 | < 1e-6 | True |
| wise0855_qr2_d6_header_wcs_diffs | none | none | True |
| rdra_qr2deep_origin | cutout [884, 9] / s3 [883, 8] / section hdr [884, 9] | equal | True |
| rdra_qr2deep_s3_box_contains_cutout | cutout [884, 9] [91, 91]; S3 box [883, 8] [92, 93]; edge offsets (x0, y0, x1, y1) [-1, -1, 1, 0] | S3 box ⊇ cutout box (failover never loses pixels) | True |
| rdra_qr2deep_IMAGE | identical=True dtypes=['float32', 'float32'] n=8281 nan=13 | bit-identical | True |
| rdra_qr2deep_FLAGS | identical=True dtypes=['int64', 'int64'] n=8281 nan=0 | bit-identical | True |
| rdra_qr2deep_VARIANCE | identical=True dtypes=['float32', 'float32'] n=8281 nan=13 | bit-identical | True |
| rdra_qr2deep_ZODI | identical=True dtypes=['float32', 'float32'] n=8281 nan=0 | bit-identical | True |
| rdra_qr2deep_wcs_max_sep_arcsec | 0.0 | < 1e-6 | True |
| rdra_qr2deep_header_wcs_diffs | none | none | True |

git 20efbf1 (dirty) · contract 0.1.0 · author D · reviewer pending
