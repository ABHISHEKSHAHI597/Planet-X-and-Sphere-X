# F6 — PASS (L2)

**Part 1: plane names.** 280 FLAGS headers read (the
committed fixture and 279 real cutouts, pipelines 6.4+psffix1, 6.5.6 and 7.0.5). Outcome: **corrected**.
- Bit numbers agree with understanding.md §4.4 in every file (mismatches: none).
- **Two header conventions.** QR3 (7.0.5) uses `MSKNnnnn`/`MSKMnnnn`; **QR2 (6.x) uses
  `HIERARCH MP_<NAME> = <bit>`**. The previous `flag_bits` read only the first, so on every QR2 frame it
  returned no planes and masked nothing. Fixed (both conventions; a header with neither now raises).
- **Plane sets differ by pipeline.** Absent planes by version: {'7.0.5': {"('PHANTOM', 'REFERENCE', 'SATELLITE_HALO')": 28, "('PHANTOM', 'REFERENCE', 'SATELLITE_HALO', 'SNOWBALL')": 2}, '6.4+psffix1': {"('BLOOM', 'CROSSTALK', 'GHOST', 'GHOST_EXT', 'GHOST_FPA', 'HALO', 'SATELLITE_HALO', 'SNOWBALL', 'STREAK')": 126}, '6.5.6': {"('CROSSTALK', 'SATELLITE_HALO', 'STREAK')": 119, "('CROSSTALK', 'SATELLITE_HALO', 'SNOWBALL', 'STREAK')": 5}}. QR2 6.4 frames carry no BLOOM,
  CROSSTALK, GHOST*, HALO, SNOWBALL or STREAK planes, so those artifacts cannot be masked or used for
  mover vetting there; 6.5.6 lacks CROSSTALK and STREAK; 7.0.5 lacks SATELLITE_HALO (and PHANTOM,
  REFERENCE, which only QR2 defines). PHANTOM (4) and REFERENCE (5) are added to the canonical layout;
  REFERENCE is masked in every preset (not light-sensitive), PHANTOM is informational.

**Part 2: SOURCE at WISE 0855.** Fraction of pixels within 1.5 px flagged SOURCE (and OUTLIER), at the
position predicted for each frame's MJD-AVG (PM + parallax, temporary pos(t) adapter) and at the
WISE-era challenge coordinate (≈2.2′ away), averaged over the frames of the two full visits:

| band | frames | SOURCE at predicted | SOURCE at WISE-era | field SOURCE fraction | OUTLIER at predicted | OUTLIER at WISE-era |
|---|---|---|---|---|---|---|
| 1 | 32 | 0.97 | 0.29 | 0.31 | 0.00 | 0.03 |
| 2 | 34 | 1.00 | 0.48 | 0.42 | 0.00 | 0.07 |
| 3 | 39 | 1.00 | 0.52 | 0.42 | 0.00 | 0.13 |
| 4 | 32 | 1.00 | 0.60 | 0.46 | 0.00 | 0.13 |
| 5 | 34 | 1.00 | 0.78 | 0.48 | 0.00 | 0.02 |
| 6 | 37 | 1.00 | 1.00 | 0.29 | 0.00 | 0.00 |

Bands 1–3 decide (the dwarf is invisible there, J ≈ 25, so any footprint is catalogue-only): SOURCE
sits at the **predicted (current)** position (mean 0.99 at predicted, 0.44 at WISE-era, field 0.39).
The SPHEREx reference catalogue therefore includes WISE 0855 with its proper motion. Correction to
understanding.md §8.4, which expected its pixels un-masked and possibly OUTLIER: they are SOURCE, and
OUTLIER is never set on them (it is computed only outside known sources). Mask policy unchanged and
now required: SOURCE is never masked (flags.PRESETS), so the dwarf stays visible in discovery views.

## Metrics

| metric | value | threshold | pass |
|---|---|---|---|
| part1_mismatched_planes | none | none | True |
| part1_missing_planes_by_version | {'7.0.5': {"('PHANTOM', 'REFERENCE', 'SATELLITE_HALO')": 28, "('PHANTOM', 'REFERENCE', 'SATELLITE_HALO', 'SNOWBALL')": 2}, '6.4+psffix1': {"('BLOOM', 'CROSSTALK', 'GHOST', 'GHOST_EXT', 'GHOST_FPA', 'HALO', 'SATELLITE_HALO', 'SNOWBALL', 'STREAK')": 126}, '6.5.6': {"('CROSSTALK', 'SATELLITE_HALO', 'STREAK')": 119, "('CROSSTALK', 'SATELLITE_HALO', 'SNOWBALL', 'STREAK')": 5}} | reported | None |
| band1_SOURCE_at_predicted | 0.966 | measured | None |
| band1_SOURCE_at_wise_era | 0.285 | measured | None |
| band2_SOURCE_at_predicted | 1.0 | measured | None |
| band2_SOURCE_at_wise_era | 0.479 | measured | None |
| band3_SOURCE_at_predicted | 1.0 | measured | None |
| band3_SOURCE_at_wise_era | 0.524 | measured | None |
| band4_SOURCE_at_predicted | 1.0 | measured | None |
| band4_SOURCE_at_wise_era | 0.595 | measured | None |
| band5_SOURCE_at_predicted | 1.0 | measured | None |
| band5_SOURCE_at_wise_era | 0.782 | measured | None |
| band6_SOURCE_at_predicted | 1.0 | measured | None |
| band6_SOURCE_at_wise_era | 1.0 | measured | None |
| bands1to3_SOURCE_pred_vs_era_vs_field | [0.99, 0.44, 0.39] | predicted > 0.9, WISE-era at field level | True |

## Caveats

- pos(t) from a temporary adapter of implementation.md §4.1 (owner M); a 1.5 px radius makes the result insensitive to sub-pixel errors

git c12717d (dirty) · contract 0.1.0 · author I · reviewer pending
