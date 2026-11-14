# F12-concurrency2 — INCONCLUSIVE (L3)

**Question (F12).** From the deployment region, which FrameSource meets the budgets, and what concurrency
does IRSA tolerate? **Run from:** developer laptop, residential network (not us-east-1).

**Method.** Barnard's Star field, 6′ view (box 0.1551°, `cutout_size_deg`). (1) 0
frames read once by each source, sequentially, no retries; then S3 at concurrency 8. (2) Soak: 2
workers issuing stream-aborted cutouts back to back over 359 distinct Barnard frames for
300 s, retries off, every request logged in `requests.json`.

**Results.** S3 section p50 None s, None B/frame mean; cutout p50
None s, None B/frame. Soak: 219 requests in 299 s,
9 failures {'HTTP 503': 9}, total p50/p95 2.4340945610001654/4.909690501000114 s,
TTFB p50/p95 1.230023503000666/3.1671801580005194 s.

**Verdict.** NOT the deployment region: this answers F12 only for this network. F12 stays open until the same script runs on the us-east-1 VM (owner P provides the VM; D runs it).

## Metrics

| metric | value | threshold | pass |
|---|---|---|---|
| host | infinityFedora (Linux); developer laptop, residential network (not us-east-1) | deployment VM (us-east-1) | False |
| box_deg | 0.15509 | cutout_size_deg(6′) | None |
| s3_single_p50_s | None | reported | None |
| s3_single_bytes_mean | None | reported (≈ rows × 8160 B × 3 + FLAGS) | None |
| s3_single_failures | 0 | 0 | True |
| cutout_single_p50_s | None | reported | None |
| cutout_single_bytes_mean | None | ≈190 KB for 6′ (implementation.md §3.4) | None |
| cutout_single_failures | 0 | 0 | True |
| s3_conc8_frames_per_s | 0.0 | reported | None |
| soak_seconds | 299.0 | >= 270 | True |
| soak_concurrency_peak | 2 | == 2 | True |
| soak_requests | 219 | reported | None |
| soak_failures | 9 | reported | None |
| soak_503 | 9 | 0 (§10.3: no 503s before raising concurrency) | False |
| soak_failure_kinds | {'HTTP 503': 9} | reported | None |
| soak_total_p50_s | 2.4340945610001654 | reported | None |
| soak_total_p95_s | 4.909690501000114 | reported | None |
| soak_ttfb_p50_s | 1.230023503000666 | reported | None |
| soak_ttfb_p95_s | 3.1671801580005194 | reported | None |
| soak_bytes_mean | 200406.85714285713 | reported | None |
| soak_bytes_total | 42085440 | reported | None |

## Caveats

- run from a non-deployment network; latency and throughput are not the VM's

git 20efbf1 (dirty) · contract 0.1.0 · author D · reviewer pending
