# Data refresh and DR1 procedure (owner D)

The step-by-step version of workflow.md §12.4. D runs it. P decides release timing. I and M decide
whether science gates still pass.

## What runs automatically

| Job | Command | Effect |
|---|---|---|
| Release watcher, hourly | `python scripts/refresh_check.py --state $PARALLAX_CACHE/release_state.json --out refresh.json` | Lists S3 (top level and `<release>/level2/`, all pages, planning periods sorted by parsed fields) and stores `release_state`. The new state token invalidates **coverage** caches (`CoverageCache`, 24 h TTL otherwise) and feeds the freshness badge. **Pins and view keys of pinned views never change.** |
| Same run | (same) | Live SIA2 coverage for the 5 acceptance targets → dedup → diff against `config/pins/index.json`. Differences are reported only. |

Nothing in the code writes `config/releases.yaml`. A collection the registry doesn't list (e.g. a new
`spherex_dr1`) is skipped by dedup with the reason "not in config/releases.yaml". So DR1 can't leak
into any view before a human adds it.

## When the report shows a change

1. **Record what changed.** Keep `refresh.json`, which has the new periods, any new top-level prefix and
   the per-target added/removed/replaced frames, in the evidence for step 4.
2. **Staging only.** If it is a new release (DR1):
   - Get the SIA2 collection names from IRSA (SIA2 lags S3 by about a day; TAP gets new data first).
   - In a PR, add the release to `config/releases.yaml` with a priority above the release it supersedes.
     DR1 is R7, `photometric_scale: qr3`, priority 40. `python -c "from spherex.access.releases import load; load()"`
     validates it: duplicate priorities, overlapping collections and `never_use` collisions are refused.
   - If its calibration differs, run `python scripts/bootstrap_calib.py discover`. Then run `fetch --freeze`
     in the same PR. I and M review it.
3. **Candidate pins.** Run `python scripts/refresh_check.py --write-candidates`. This stores candidate pins
   beside the current ones (`config/pins/<pin>.json`) and lists them under `candidates` in
   `config/pins/index.json`. The current `pin` entries are untouched.
4. **Re-run the L3 checks on the candidate pins** (F11 and the target checks of each enabled gate). For DR1,
   also re-run F1–F5 and F13 if the calibration lock changed.
5. **Adopt only through a normal RC** (P is release manager), and only if every enabled gate still passes.
   Adopting means moving a target's `pin` in `index.json` to the candidate in that RC's PR. Demo pins never
   change in place. Until then the UI's "newer data available" notice (`newer_pin`) covers the gap.
6. **WISE 0855's autumn-2026 visit** (understanding.md §8.4): if new WISE 0855 frames appear, D and M
   assess them as a candidate improvement to G3, not as a reason to change a passing release late.

## Event Saturday morning (workflow.md §10.3)

```bash
python scripts/refresh_check.py --out validation/refresh-$(date +%F).json   # on the VM
```
Results go to staging only.

## Facts as of 2026-11-07 (from the recorded listings and F11)

- S3 top level: `qr2/`, `qr3/` only (no `dr1/`).
- Newest QR3 period: `2026W40_2A` (22 periods). QR2 holds 129 periods; its newest is `2026W29_2A`.
- Pinned frame counts are unchanged since 2026-11-06: Barnard 359, ε Ind B 447, WISE 0855 256 (QR2 only),
  RW Aur 333, R Dra 2,483.
