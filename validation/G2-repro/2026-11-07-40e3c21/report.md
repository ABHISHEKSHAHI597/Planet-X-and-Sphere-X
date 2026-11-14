# G2-repro — PASS (L3)

**Method.** Two cold in-process builds of pin `21a7689afc4b` (Barnard's Star), each with an empty cache, through POST /views → SSE → payload GETs, from developer laptop (Windows 11), residential network, not us-east-1. Compared every `.f16` and `.f32` stack payload.

**Result.** Byte-identical: 24 f16 payloads, 355 frames stacked, 4 skipped with reasons.

## Metrics

| metric | value | threshold | pass |
|---|---|---|---|
| same_key | 088db33cfb6f43c74bfa5649 / 088db33cfb6f43c74bfa5649 | equal | True |
| f16_payloads | 24 | > 0 (every ready stack) | True |
| byte_identical_f16_f32 | all identical | byte-identical | True |
| f16_digest | 066d225f7ecbd0ae | reported | None |
| frames_stacked | 355 | reported | None |
| frames_skipped | 4 | reported (each with a reason) | None |
| job_errors | 0 | 0 | True |
| cold_s | [368.8, 313.2] | reported (budgets are G2-perf) | None |

## Caveats

- CALIB_ROOT not set: stacks do not use λ maps, so bytes are unaffected
- runtime 701 s
- recorded on a dirty working tree: code_digest identifies the exact code

git 40e3c21 (dirty) · contracts {'spherex.types': '0.1.0', 'http-api': '0.1.0'} · calibration 94e18b883fdc9b28 · author P · reviewer pending
