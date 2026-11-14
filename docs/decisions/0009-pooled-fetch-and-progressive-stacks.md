# 0009 — Loading a view: pooled fetching, per-bin stacks, selected band first

2026-11-10. Author: P. Platform change, with one deliberate effect on stack values: every frame is cut to one
canonical pixel window (item 8), so a stack no longer depends on which source served its frames. Flags, skips and
the limit rule are unchanged. **Review requested:** D (access layer) and I (stacking inputs). Record 0008 is on
`p/tanmay/diff-and-spectrum`.

## Question
Teammates reported that opening a view "takes very long to load, not necessarily to fetch". Where does the time go,
from a home connection and from the frame cache, and what can be removed without changing results?

## Measurements (before)
All from a laptop in India (≈ 0.3 s round trip to us-east-1), Barnard's Star, pin `21a7689afc4b`, band 6 selected,
359 frames in 24 (bin, band) stacks.

| Phase | Measured | Cause |
|---|---|---|
| POST → job queued | 3–50 s | resolve (SIMBAD + Gaia, 6 s, disk-cached afterwards) and the pinned "newer data?" coverage check (4.5–30 s) awaited before answering |
| Cold build, `FRAMESOURCE=s3` | 427 s; first image at 224 s | S3 sections read whole 2,040-px detector rows: ≈ 3 MB per frame, ≈ 16× a cutout, ≈ 900 MB per view; 1.2 frames/s at concurrency 8 or 32 (bandwidth-bound) |
| IRSA cutouts alone | 1.1 frames/s at IRSA's 4-in-flight policy | per-request latency, not bandwidth (5.4 MB per 24 frames) |
| First image | after the whole selected band had downloaded *and* every bin of it had stacked | `run_view` fetched and stacked band by band |
| Display limits while building | placeholder 0–1 until `done` | the frontend re-read the manifest only at `planned` and `done` |
| Warm rebuild (frame cache) | first image 13.8 s, done 42.9 s | each cached frame is 35–70 ms of GIL-holding Python (FITS headers, WCS ≈ 18 ms) and ran **on the event loop** (≈ 25 s of blocked loop, SSE stalled); 2 stacking threads on Windows |
| Source attribution | wrong under concurrency | `FailoverSource.last_source` is one attribute shared by all in-flight fetches |

## Decision
1. **PooledSource outside AWS** (`FRAMESOURCE=auto`, `IN_AWS_US_EAST_1` unset). IRSA cutouts (≤ 4 in flight) and S3
   sections (12 frames in flight) work one queue. Each frame goes to the source with the earliest expected finish,
   from a per-source EWMA of seconds per frame. A source with 3 consecutive `SourceFailure`s rests for 60 s and its
   frames are retried on the other source; `FrameUnavailable` passes through as before. In us-east-1 nothing changes
   (S3 preferred, IRSA failover). `FRAMESOURCE=s3` outside us-east-1 now logs a warning at startup.
2. **Per-bin pipeline.** One fetch stream for the view (selected band first, then bin order). Each bin is stacked
   the moment its last frame arrives and announced with `stack_ready`. The band's shared limits are recomputed from
   the bins stacked so far and written to the manifest with each stack.
3. **Selected band first.** Stacks of other bands wait until the selected band's bins are stacked. Frames of other
   bands that are already in the frame cache also wait (network fetches never do): reading them beside the stacks
   starves the stacks of the GIL (each short numpy step waits a 5 ms switch interval), which held the first warm
   image at 15–20 s.
4. **Frame cache off the event loop**, on its own 2 threads (more would not read faster, only take the GIL from the
   stacks). A failing cache write (full disk) costs the cache entry, never the frame.
5. **Newer-data check bounded at 2 s** for pinned views. Past that, the query finishes in the background and fills
   the 24 h coverage cache; the next open of the pin shows the hint. A slow check is not reported as failed.
6. **Stacking threads**: `max(2, min(8, cpu − 1))` when `CPU_WORKERS=0` (was 2). Measured on cached frames:
   1 thread 8.6 s, 2 → 6.4 s, 4 → 5.0 s, 8 → 4.7 s for the same 119 frames.
7. **Frontend** re-reads the manifest while stacks land (≤ 1 per 1.2 s, trailing; immediately at `done`), so
   first visits are drawn with real limits.
8. **Canonical frame window** (`spherex/access/window.py`, applied in `fetch_frames`). IRSA cutouts and S3 sections
   of the same frame differ by a ring of up to 1 px: S3 reads IRSA's box rule padded by 1 px, because IRSA's exact
   sizing is not public (validation/F2). Frame-level statistics in the stack (the sky level) see that ring. Measured
   on Barnard D6, every stack pixel moved, p99 |Δ| ≈ 1 % of the median level, so two cold builds that mixed sources
   differently were not byte-identical (G2-repro). The pool mixes sources on every build; on `main` the same thing
   happened after any failover, and between an AWS and a home deployment. Every frame is now cut to IRSA's rule
   shrunk by 1 px, which lies inside both. Verified live on 43 frames in bands 1, 3 and 6: after the cut, IRSA and S3
   give identical pixels, origins, header origins and WCS, byte-identical stacks, and the same number of empty grid
   pixels (the request already carries a 4 px margin per side). The cut costs ≈ 3 ms per frame (headers shifted in
   place).
9. **Attribution** through a task-local `SERVED_BY` context variable, set by the failover, pool and cache wrappers; `job_end` logs and job stats
   gain `frames_by_source`, `fetch_s`, `stack_tail_s` and the pool's per-source `served` / `s_per_frame`.

## Result (after; same machine, same view)
| | Before | After |
|---|---|---|
| Cold, POST → queued | 3–50 s | ≤ 2.6 s (resolve cached) |
| Cold, first image (from `planned`) | +174 s (`s3`) | **+13.8 s** (`auto`, pooled) |
| Cold, whole view (from `planned`) | +377 s (`s3`) | **+161 s** |
| Warm (frame cache), first image | 13.8 s | **4.75 s** (band 6 complete at 6.7 s) |
| Warm, whole view | 42.9 s | ≈ 40 s (CPU-bound in one process) |

The cold numbers are bounded by bandwidth plus IRSA's request policy. The pool uses both, but on a slow link a view
of 300+ frames still takes minutes. The fix there is the frame cache or running the API in us-east-1.

## What does not change
- Which frames go into which stack, flags and skip reasons: `stack_task` gets the same frames per bin, each 1–3 px
  smaller per axis (item 8). Stack values change at the ≈ 1 % level of the sky through frame-level statistics. That
  is the size of the old IRSA-versus-S3 difference, which this removes.
- The final display limits: ZScale over the pixelwise median of a band's bin samples, in plan bin order. That is
  independent of the order in which bins complete, so the last update equals the old single computation.
- Solar-System targets still stack per band, because their frame centres come from one Horizons call per band.
- The job timeout still scales with the frame count; a failed or timed-out fetch now cancels pending stack tasks.

## Considered and not done
- A disk cache of S3 header maps and speculative parallel header reads: these save requests, but bandwidth dominates.
- Process-based stacking on Windows (`CPU_WORKERS>0`): spawn start-up and pickling every frame cost more than they
  save for a 359-frame view. It is still available by setting `CPU_WORKERS`.

## Tests
`backend/tests/unit/test_pooled_fetch.py` covers the pool (capacity, routing, retry and rest, `FrameUnavailable`,
all sources resting), attribution, the cache (hits, failed writes, `contains`) and the s3 warning.
`backend/tests/app/test_load_speed.py` covers selected-band-first stacking and the bounded newer-data check.
The canonical window (a fixture frame and 1-px-trimmed copies crop to identical bytes; header origin, WCS and
in-place cropping agree) is covered there too. `test_access_policy.py::test_build_source_defaults_by_region` is
updated for the pool. G2-repro was re-run on this code (`validation/G2-repro/2026-11-10-989bf01`, L3, **pass**): two cold live builds
split their 359 frames IRSA 187 / S3 172 and IRSA 195 / S3 164, and all 48 stack payloads were byte-identical.
Cold time was 176 s and 210 s (the 2026-11-07 record: 369 s and 313 s).
`frontend/tests/viewloader.test.tsx` covers the throttled manifest refresh.
