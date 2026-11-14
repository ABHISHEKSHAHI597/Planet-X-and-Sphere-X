# RDra-inputs — PASS (L3)

**Scope.** R Draconis data volume and per-frame inputs for M's light curve (workflow.md §6, R Dra steward D;
§10.2 "light-curve input plumbing for M"). Data only: binning, normalisation and the periodogram are M's.

**Method.** The frames of pin 152b410215da (config/pins). For each, the full-file IMAGE header via S3 byte ranges
(no pixels); R Dra's 0-based parent pixel through that WCS (SIP included); CHANNEL_MAP and CWAVE at that
pixel from the locked calibration (config/calibration.lock); header QA and timing keywords. Output:
`backend/tests/data/real/rdra_frame_inputs.json.gz`.

## Metrics

| metric | value | threshold | pass |
|---|---|---|---|
| frames | 2483 | ≈2,480 (understanding.md §3.4) | True |
| deep_frames | 1947 | ≈1,950 | True |
| header_errors | 0 | 0 | True |
| target_off_detector | 5 | reported (circle overlaps, pixel centre outside) | None |
| outside_band_ch0_or_18 | 68 | reported | None |
| qa_pass_frames | 2483 | reported (F8) | None |
| channel_groups | 102 | reported; ≤ 102 | True |
| frames_per_group_min_median | [4, 31] | reported (annulus method needs ≥ 2 per group) | True |
| by_collection | {'spherex_qr2': 536, 'spherex_qr2_deep': 1224, 'spherex_qr3_deep': 723} | reported | None |

git 20efbf1 (dirty) · contract 0.1.0 · author D · reviewer pending
