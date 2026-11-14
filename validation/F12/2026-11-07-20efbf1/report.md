# F12 — INCONCLUSIVE (L3)

**Question (F12).** From the deployment region, which FrameSource meets the budgets, and what concurrency
does IRSA tolerate? **Run from:** developer laptop, residential network (not us-east-1).

**Method.** Barnard's Star field, 6′ view (box 0.1551°, `cutout_size_deg`). (1) 6
frames read once by each source, sequentially, no retries; then S3 at concurrency 8. (2) Soak: 4
workers issuing stream-aborted cutouts back to back over 359 distinct Barnard frames for
600 s, retries off, every request logged in `requests.json`.

**Results.** S3 section p50 14.43349603300021 s, 2970293.8 B/frame mean; cutout p50
2.662605423000059 s, 211309 B/frame. Soak: 710 requests in 599 s,
68 failures {'HTTP 503': 68}, total p50/p95 2.9715279950000877/6.553108961999897 s,
TTFB p50/p95 1.6221717589996842/3.6838807780000025 s.

**Verdict.** NOT the deployment region: this answers F12 only for this network. F12 stays open until the same script runs on the us-east-1 VM (owner P provides the VM; D runs it).

## Metrics

| metric | value | threshold | pass |
|---|---|---|---|
| host | infinityFedora (Linux); developer laptop, residential network (not us-east-1) | deployment VM (us-east-1) | False |
| box_deg | 0.15509 | cutout_size_deg(6′) | None |
| s3_single_p50_s | 14.43349603300021 | reported | None |
| s3_single_bytes_mean | 2970293.8 | reported (≈ rows × 8160 B × 3 + FLAGS) | None |
| s3_single_failures | 1 | 0 | False |
| cutout_single_p50_s | 2.662605423000059 | reported | None |
| cutout_single_bytes_mean | 211309 | ≈190 KB for 6′ (implementation.md §3.4) | None |
| cutout_single_failures | 0 | 0 | True |
| s3_conc8_frames_per_s | 0.139 | reported | None |
| soak_seconds | 598.9 | >= 570 | True |
| soak_concurrency_peak | 4 | == 4 | True |
| soak_requests | 710 | reported | None |
| soak_failures | 68 | reported | None |
| soak_503 | 68 | 0 (§10.3: no 503s before raising concurrency) | False |
| soak_failure_kinds | {'HTTP 503': 68} | reported | None |
| soak_total_p50_s | 2.9715279950000877 | reported | None |
| soak_total_p95_s | 6.553108961999897 | reported | None |
| soak_ttfb_p50_s | 1.6221717589996842 | reported | None |
| soak_ttfb_p95_s | 3.6838807780000025 | reported | None |
| soak_bytes_mean | 200720.7476635514 | reported | None |
| soak_bytes_total | 128862720 | reported | None |

## Caveats

- run from a non-deployment network; latency and throughput are not the VM's

git 20efbf1 (dirty) · contract 0.1.0 · author D · reviewer pending
