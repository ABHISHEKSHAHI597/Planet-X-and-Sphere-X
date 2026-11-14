# G4b-wise-stacks — INCONCLUSIVE (L3)

**Finding (new, real data): WISE 0855 is passing a field star during both full visits.** Gaia DR3
5756956644387831296 (G = 16.31, ϖ = 0.29 mas, static) lies 1.35 px (8.3″) from the propagated position in
Nov 2025 and 0.7 px (4.2″) in Apr–May 2026. In bands 1–3 the stack centroid sits on that star; in band 6
it sits within 0.1–0.3 px of WISE 0855's predicted position, pulled toward the star.

| band | visit | σ at the predicted pixel | predicted ↔ star (px) | stack centroid ↔ predicted (px) | centroid ↔ star (px) |
|---|---|---|---|---|---|
| 1 | V1 · 2025-10-31→11-03 · S1 · 108 frames | 12.8 | 1.36 | 1.35 | 0.04 |
| 1 | V2 · 2026-05-01/05 · S2 · 100 frames | 42.0 | 0.68 | 0.66 | 0.04 |
| 2 | V1 · 2025-11-07/10 · S1 · 108 frames | 11.5 | 1.34 | 1.34 | 0.03 |
| 2 | V2 · 2026-05-01/14 · S2 · 100 frames | 45.0 | 0.67 | 0.67 | 0.06 |
| 3 | V1 · 2025-11-10/14 · S1 · 108 frames | 7.3 | 1.33 | 1.32 | 0.04 |
| 3 | V2 · 2026-04-21→05-11 · S2 · 100 frames | 35.9 | 0.70 | 0.69 | 0.04 |
| 4 | V1 · 2025-10-31→11-03 · S1 · 108 frames | 6.3 | 1.36 | 1.27 | 0.12 |
| 4 | V2 · 2026-05-01/05 · S2 · 100 frames | 18.5 | 0.68 | 0.64 | 0.06 |
| 5 | V1 · 2025-11-07/10 · S1 · 108 frames | 10.1 | 1.34 | 0.68 | 0.67 |
| 5 | V2 · 2026-05-01/14 · S2 · 100 frames | 15.5 | 0.67 | 0.29 | 0.40 |
| 6 | V1 · 2025-11-10/14 · S1 · 108 frames | 13.4 | 1.33 | 0.30 | 1.05 |
| 6 | V2 · 2026-04-21→05-11 · S2 · 100 frames | 18.1 | 0.70 | 0.11 | 0.62 |

Criteria: band-6 S/N ≥ 5 in both full visits: **met** (but blended with the star's
band-6 flux). Bands 1–3 < 3σ at the position: **not met: the field star is there**. As written,
the bands 1–3 criterion cannot pass; it has to be evaluated with a two-source forced fit (WISE 0855 at
pos(t) plus the Gaia star), which is M's photometry (§4.8). Consequences:
- **M:** the two-visit displacement (0.78 px) and the PM fit must model the star; a one-source centroid
  is biased toward it by up to ≈0.2–0.3 px. Spectra and the methane meter need the two-source fit too.
- **F / storytelling:** "empty at 1–2 µm" is false at WISE 0855's pixel in 2025–26; the empty-blue,
  bright-red story needs the two-source model or a label pointing at the neighbour.
- **I:** stacks, significance and centroids behave as specified; no Role I change needed.

## Metrics

| metric | value | threshold | pass |
|---|---|---|---|
| band1_V1_sig_at_pos | 12.8 | ≥ 5 (band 6); < 3 (bands 1–3) | False |
| band1_V2_sig_at_pos | 42.0 | ≥ 5 (band 6); < 3 (bands 1–3) | False |
| band2_V1_sig_at_pos | 11.5 | ≥ 5 (band 6); < 3 (bands 1–3) | False |
| band2_V2_sig_at_pos | 45.0 | ≥ 5 (band 6); < 3 (bands 1–3) | False |
| band3_V1_sig_at_pos | 7.3 | ≥ 5 (band 6); < 3 (bands 1–3) | False |
| band3_V2_sig_at_pos | 35.9 | ≥ 5 (band 6); < 3 (bands 1–3) | False |
| band4_V1_sig_at_pos | 6.3 | ≥ 5 (band 6); < 3 (bands 1–3) | None |
| band4_V2_sig_at_pos | 18.5 | ≥ 5 (band 6); < 3 (bands 1–3) | None |
| band5_V1_sig_at_pos | 10.1 | ≥ 5 (band 6); < 3 (bands 1–3) | None |
| band5_V2_sig_at_pos | 15.5 | ≥ 5 (band 6); < 3 (bands 1–3) | None |
| band6_V1_sig_at_pos | 13.4 | ≥ 5 (band 6); < 3 (bands 1–3) | True |
| band6_V2_sig_at_pos | 18.1 | ≥ 5 (band 6); < 3 (bands 1–3) | True |

## Caveats

- the 'σ at the predicted pixel' is the stack significance, not forced photometry (M)
- pos(t) from the temporary adapter; WISE 0855 astrometry is SIMBAD J2000 (Kirkpatrick+2021), linear

git c12717d (dirty) · contract 0.1.0 · author I · reviewer pending
