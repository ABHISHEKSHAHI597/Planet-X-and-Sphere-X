# F11 — PASS (L3)

**Question (F11).** Does the SIA2 response carry the columns coverage needs, and does it return the same
frame set as TAP after dedup? Outcome: see verdict and per-target table.

**Method.** For each target, one SIA2 call with all four registry collections (radius 0.001°, the
target-centred default) and one TAP call (`CONTAINS(POINT, p.poly)` over plane ⋈ artifact ⋈ observation,
the same collections), both through `spherex.access.coverage`, then `spherex.access.dedup` with
`config/releases.yaml`. Deduplicated access URLs are compared as sets. Counts are reconciled against
understanding.md §3.4 and against the committed 2026-11-06 coverage fixture (`frames_5targets.json`,
same positions): frames added since then are attributed to their planning periods. Responses are
recorded in `backend/tests/data/real/recorded/coverage/` (recorded live).

| target | rows SIA2 / TAP | frames after dedup SIA2 / TAP | identical | collections | IOC | `_retry` | pair fraction | vs 2026-11-06 fixture | understanding.md §3.4 |
|---|---|---|---|---|---|---|---|---|---|
| barnard | 359 / 359 | 359 / 359 | yes | {'spherex_qr2': 240, 'spherex_qr3': 119} | 0 | 0 | 0.9834 | 359 → 359 (+0 {}, −0) | 359 |
| epsindb | 447 / 447 | 447 / 447 | yes | {'spherex_qr2': 327, 'spherex_qr3': 120} | 66 | 2 | 0.8861 | 447 → 447 (+0 {}, −0) | 449 (✅ 11-06: 447 SIA2 rows) |
| wise0855 | 256 / 256 | 256 / 256 | yes | {'spherex_qr2': 256} | 0 | 0 | 0.9845 | 256 → 256 (+0 {}, −0) | 256, all QR2 |
| rwaur | 333 / 333 | 333 / 333 | yes | {'spherex_qr2': 224, 'spherex_qr3': 109} | 0 | 2 | 0.9821 | 333 → 333 (+0 {}, −0) | 333 |
| rdra | 2483 / 2483 | 2483 / 2483 | yes | {'spherex_qr2_deep': 1224, 'spherex_qr2': 536, 'spherex_qr3_deep': 723} | 58 | 7 | 0.9753 | 2483 → 2483 (+0 {}, −0) | ≈2,480 (≈1,950 deep) |

"pair fraction" = obs ids whose frames are exactly one co-aligned pair (D1+D4, D2+D5, D3+D6); the rest
are single-detector edge cases (understanding.md §3.3: 178 of 181 for Barnard).

## Metrics

| metric | value | threshold | pass |
|---|---|---|---|
| barnard_sia2_eq_tap | 359 vs 359; only SIA2 0, only TAP 0 | identical deduplicated sets | True |
| barnard_vs_doc | 359 now; 359 on 2026-11-06; doc 359; +0 new ({}), -0 gone | every difference explained | None |
| epsindb_sia2_eq_tap | 447 vs 447; only SIA2 0, only TAP 0 | identical deduplicated sets | True |
| epsindb_vs_doc | 447 now; 447 on 2026-11-06; doc 449 (✅ 11-06: 447 SIA2 rows); +0 new ({}), -0 gone | every difference explained | None |
| wise0855_sia2_eq_tap | 256 vs 256; only SIA2 0, only TAP 0 | identical deduplicated sets | True |
| wise0855_vs_doc | 256 now; 256 on 2026-11-06; doc 256, all QR2; +0 new ({}), -0 gone | every difference explained | None |
| rwaur_sia2_eq_tap | 333 vs 333; only SIA2 0, only TAP 0 | identical deduplicated sets | True |
| rwaur_vs_doc | 333 now; 333 on 2026-11-06; doc 333; +0 new ({}), -0 gone | every difference explained | None |
| rdra_sia2_eq_tap | 2483 vs 2483; only SIA2 0, only TAP 0 | identical deduplicated sets | True |
| rdra_vs_doc | 2483 now; 2483 on 2026-11-06; doc ≈2,480 (≈1,950 deep); +0 new ({}), -0 gone | every difference explained | None |
| sia2_required_columns | present | obs_collection, obs_id, access_url, t_min, energy_bandpassname, cloud_access | True |

git 20efbf1 (dirty) · contract 0.1.0 · author D · reviewer pending
