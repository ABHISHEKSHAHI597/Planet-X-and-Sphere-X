# G1-time-model — PASS (L3)

Visit classification (implementation.md §4.2 with decisions 0001 and 0002), per band, on the real
MJD-AVG and SPS_EPA of every SIA2 frame of the 5 targets. Surveys from PA and date (`survey_number`);
a survey-number keyword is M's F9 and would replace this derivation.

**barnard** (359 frames, axis `visit`, IOC frames 0):
- band 6: `V1 · 2025-08-15/27 · S2 · 109 frames`
- band 6: `V3 · 2026-03-19→04-10 · S1 · 113 frames`
- band 6: `V4 · 2026-05-04/05 · S1 · partial (4 in band 6)`
- band 6: `V5 · 2026-08-16/20 · S4 · 117 frames`
- full visits per band: {1: 3, 2: 3, 3: 3, 4: 3, 5: 3, 6: 3}

**epsindb** (447 frames, axis `visit`, IOC frames 66):
- band 6: `V1 · 2025-04-29→06-10 · S1+IOC · 116 frames`
- band 6: `V2 · 2025-09-28→11-04 · S2 · 137 frames`
- band 6: `V3 · 2026-04-29→05-04 · S1 · 74 frames`
- band 6: `V4 · 2026-09-22/28 · S4 · 120 frames`
- full visits per band: {1: 2, 2: 3, 3: 4, 4: 2, 5: 3, 6: 4}

**wise0855** (256 frames, axis `visit`, IOC frames 0):
- band 6: `V1 · 2025-05-05 · S2 · partial (3 in band 6)`
- band 6: `V2 · 2025-11-10/14 · S1 · 108 frames`
- band 6: `V3 · 2025-12-12/13 · S1 · partial (3 in band 6)`
- band 6: `V4 · 2026-04-21→05-11 · S2 · 100 frames`
- full visits per band: {1: 2, 2: 2, 3: 2, 4: 2, 5: 2, 6: 2}

**rwaur** (333 frames, axis `visit`, IOC frames 0):
- band 6: `V1 · 2025-09-11/20 · S1 · 110 frames`
- band 6: `V2 · 2026-02-20→03-02 · S2 · 114 frames`
- band 6: `V3 · 2026-09-13/16 · S3 · 109 frames`
- full visits per band: {1: 3, 2: 3, 3: 3, 4: 3, 5: 3, 6: 3}

**rdra** (2483 frames, axis `bin:14d`, IOC frames 58):
- occupied 14-day bins per band: {1: 16, 2: 6, 3: 16, 4: 16, 5: 6, 6: 16}; all bands: 35

Findings: WISE 0855 band 6 is partial 3 · full 16 · partial 3 · full 21 (as verified); Barnard's full
visits carry 109, 113 and 117 frames in S2 → S1 → S4 (understanding.md §3.4, §3.3). ε Ind B's visits
span up to 46 d with their tails, which the documented 45-day axis rule turned into 14-day bins
(decision 0002 sets 60 d). R Dra has 16 occupied 14-day bins in bands 1, 3, 4, 6 and only 6 in bands 2
and 5, short of the ≥ 20 that implementation.md §10.2 asks for per band: reported to M (G5.lc).

## Metrics

| metric | value | threshold | pass |
|---|---|---|---|
| barnard_full_visits_band6 | 3 | ≥ 2 (P0-3) | True |
| epsindb_full_visits_band6 | 4 | ≥ 2 (P0-3) | True |
| wise0855_full_visits_band6 | 2 | ≥ 2 (P0-3) | True |
| rwaur_full_visits_band6 | 3 | ≥ 2 (P0-3) | True |
| rdra_occupied_bins | {1: 16, 2: 6, 3: 16, 4: 16, 5: 6, 6: 16} | ≥ 20 per band for the periodogram (G5.lc, M) | None |
| wise0855_band6_2full_2partial | [('partial', 3), ('full', 16), ('partial', 3), ('full', 21)] | partial 3, full 16, partial 3, full 21 | True |
| barnard_surveys | [(2,), (1,), (4,)] | S2 → S1 → S4 (understanding.md §3.3) | True |

## Caveats

- survey numbers are derived (PA + date), not read from a survey keyword (F9, owner M)
- frame lists from SIA2 at r = 0.001°, not D's pins

git c12717d (dirty) · contract 0.1.0 · author I · reviewer pending
