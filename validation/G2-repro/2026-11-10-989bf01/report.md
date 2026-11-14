# G2-repro — PASS (L3)

**Method.** Two cold in-process builds of pin `21a7689afc4b` (Barnard's Star), each with an empty cache, through POST /views → SSE → payload GETs, from HPVictusTPS (Windows). Compared every `.f16` and `.f32` stack payload.

**Result.** Byte-identical: 24 f16 payloads, 359 frames stacked, 0 skipped with reasons.

## Metrics

| metric | value | threshold | pass |
|---|---|---|---|
| same_key | 689aae6e44f729c76d6dac0b / 689aae6e44f729c76d6dac0b | equal | True |
| f16_payloads | 24 | > 0 (every ready stack) | True |
| byte_identical_f16_f32 | all identical | byte-identical | True |
| f16_digest | c78616ac063ba3db | reported | None |
| frames_stacked | 359 | reported | None |
| frames_skipped | 0 | reported (each with a reason) | None |
| job_errors | 0 | 0 | True |
| cold_s | [175.7, 210.0] | reported (budgets are G2-perf) | None |
| frames_by_source | [{'irsa-cutout': 187, 's3-section': 172}, {'irsa-cutout': 195, 's3-section': 164}] | reported | None |

## Caveats

- CALIB_ROOT not set: stacks do not use λ maps, so bytes are unaffected
- runtime 389 s
- recorded on a dirty working tree: code_digest identifies the exact code

git 989bf01 (dirty) · contracts {'spherex.types': '0.1.0', 'http-api': '0.1.0'} · calibration 94e18b883fdc9b28 · author P · reviewer pending
