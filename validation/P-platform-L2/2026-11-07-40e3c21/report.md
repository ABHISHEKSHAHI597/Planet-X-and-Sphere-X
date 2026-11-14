# P-platform-L2 — PASS (L2)

**Scope.** Fixture-backed end-to-end run of the API (workflow.md §8.5) at git HEAD; pinned Barnard view (21a7689afc4b), key `e4314077b3a6bb98525724b6`, cold build 1.5 s in-process.

**What this establishes (L2).** The API, job runner, SSE, manifest, payload encodings, PNG renderer, warm cache and snapshot packaging work on real SPHEREx bytes and real recorded archive answers.

**What it does not.** Anything about stacks of the science targets: only one real frame is stacked. G2-repro (scripts/verify/p_repro.py) and the staging perf probe are the L3 evidence.

## Metrics

| metric | value | threshold | pass |
|---|---|---|---|
| events_order | planned … done (386 events) | planned first, done last | True |
| planned_frames | 359 | = pin size 359 | True |
| first_stack_band | 6 | selected band (6) first | True |
| stacked_frames | 1 | = committed fixture frames (1) | True |
| skipped_with_reason | 358 | every other frame listed with a reason | True |
| payload_sizes | 2 payloads, grid 59×59 | bytes = ny·nx·itemsize | True |
| png | HTTP 200 4368 B | 200 | True |
| warm_second_request | ready in 123 ms | ready, ≤ 300 ms (in-process) | True |
| repro_fixture | identical | two cold builds byte-identical (fixture frames only) | True |
| snapshot_index | 1 view(s), pin→key True | packaged and addressable by pin | True |

## Caveats

- fixture-backed: 1 real frame stacked, 358 skipped by design; not real-target evidence
- runtime 4.6 s
- recorded on a dirty working tree: code_digest identifies the exact code

git 40e3c21 (dirty) · contracts {'spherex.types': '0.1.0', 'http-api': '0.1.0'} · calibration 94e18b883fdc9b28 · author P · reviewer pending
