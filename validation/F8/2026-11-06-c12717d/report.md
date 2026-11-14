# F8 — PASS (L2)

**Question.** What fraction of frames per target fails `L2DQAFLG` or `FINAST`, and why?
Outcome: **confirmed, with a policy decision**: none of the 3878 frames covering the 5 acceptance targets
fails `L1DQAFLG`, `L2DQAFLG` or `FINAST` (pipelines 6.5.6 ×1327, 6.4+psffix1 ×1297, 7.0.5 ×1071, 6.5.7 ×133, 6.5.4+psffix1 ×34, 6.5.5+psffix1 ×16).

| target | frames | of which QR3 | L1DQAFLG ≠ Pass | L2DQAFLG ≠ Pass | FINAST ≠ 0 |
|---|---|---|---|---|---|
| barnard | 359 | 119 | 0 | 0 | 0 |
| epsindb | 447 | 120 | 0 | 0 | 0 |
| wise0855 | 256 | 0 | 0 | 0 | 0 |
| rwaur | 333 | 109 | 0 | 0 | 0 |
| rdra | 2483 | 723 | 0 | 0 | 0 |

**Why none fail.** No failing frame exists to inspect. The archive appears to serve only frames that
passed both QA stages (an inference from 0/3878, not a documented IRSA rule).

**Policy (preprocess.REJECT_ON_DQAFLG = ("L1DQAFLG", "L2DQAFLG"), plus FINAST ≠ 0).** Hard-reject
on any failure: on today's archive it removes no frame (measured), and it protects every stack if a
failing frame ever appears (e.g. in DR1). Rejected frames are listed in the manifest with the reason,
never dropped silently. The "> 50% of the box bad" rule rejected
1/279 real cutouts under the discovery preset
(median bad fraction 0.0134).

## Metrics

| metric | value | threshold | pass |
|---|---|---|---|
| barnard_fail_fraction | 0/359 | measured | None |
| epsindb_fail_fraction | 0/447 | measured | None |
| wise0855_fail_fraction | 0/256 | measured | None |
| rwaur_fail_fraction | 0/333 | measured | None |
| rdra_fail_fraction | 0/2483 | measured | None |
| total_fail | 0/3878 | measured | None |
| cutouts_over_50pct_bad_discovery | 1/279 | measured | None |
| cutouts_median_bad_discovery | 0.0134 | measured | None |
| cutouts_over_50pct_bad_bright | 0/279 | measured | None |
| cutouts_median_bad_bright | 0.0071 | measured | None |
| cutouts_over_50pct_bad_imaging | 1/279 | measured | None |
| cutouts_median_bad_imaging | 0.0134 | measured | None |

## Caveats

- L2 not L3: QA keywords counted over every frame of the 5 targets (the level F8 asks for); pixel bad fractions only over the 279 cutouts collected (WISE 0855 full visits, Barnard band 6, Barnard 12′ field)
- frames come from SIA2 at a 0.001° radius; pinned lists (D) may differ slightly

git c12717d (dirty) · contract 0.1.0 · author I · reviewer pending
