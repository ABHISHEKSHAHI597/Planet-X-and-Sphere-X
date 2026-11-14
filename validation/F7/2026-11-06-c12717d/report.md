# F7 — INCONCLUSIVE (L2)

**Question.** At what brightness does `OVERFLOW` set in, per band? Outcome: **open**.

| band | 2MASS stars matched | with OVERFLOW ≤ 1 px | onset K (≥ 50% flagged, 0.5-mag bins) | faintest flagged K | 4 brightest field stars | Barnard's Star (K = 4.5) at pos(t) |
|---|---|---|---|---|---|---|
| 1 | 1301 | 0 | – | – | K=8.6:no, K=8.6:no, K=9.3:no, K=9.3:no | 2/2 OV, NaN px [1, 1] |
| 2 | 1303 | 5 | 9.5 | 9.60 | K=8.6:OV, K=8.6:OV, K=9.3:no, K=9.3:OV | 2/2 OV, NaN px [2, 2] |
| 3 | 1319 | 5 | 9.5 | 9.42 | K=8.6:OV, K=8.6:OV, K=9.3:OV, K=9.3:no | 2/2 OV, NaN px [3, 3] |
| 4 | 1306 | 4 | – | 15.29 | K=8.6:OV, K=8.6:OV, K=9.3:no, K=9.3:no | 2/2 OV, NaN px [4, 4] |
| 5 | 1304 | 0 | – | – | K=8.6:no, K=8.6:no, K=9.3:no, K=9.3:no | 2/2 OV, NaN px [0, 0] |
| 6 | 1318 | 0 | – | – | K=8.6:no, K=8.6:no, K=9.3:no, K=9.3:no | 2/2 OV, NaN px [0, 0] |

Reading: bands 2–3 flag stars from K ≈ 9.5 and band 4 from K ≈ 9 (K = 8.6 flagged, 9.3 not), within
the ≈7–10 photon-budget estimate. Bands 1, 5 and 6 do not flag the K = 8.6 stars, so their onset lies
between K = 4.5 (Barnard's Star overflows in every band) and 8.6. Barnard's core is NaN (early overflow)
in bands 1–4 only (1–4 pixels within 1.5 px), confirming understanding.md §8.2's expectation; bands 5–6
keep ramp-fitted values. The single flagged K ≈ 15 star in band 4 is a chance coincidence with an
unrelated flagged pixel. A precise onset for bands 1, 5 and 6 needs a field with more K = 5–8 stars
(D: collect from the VM, e.g. an open cluster), hence `inconclusive` for those bands.

Use: the `bright` preset and the bright-target display fill apply to targets brighter than the onset in
the displayed band (Barnard K = 4.5, RW Aur 7.0, R Dra 2.2: all above it). NaN pixels near faint stars
are mostly unrelated masked pixels, so only the bright end of that column is meaningful.

## Metrics

| metric | value | threshold | pass |
|---|---|---|---|
| D1_onset_K50 | None | measured (≈7–10 expected, bands 1–3) | None |
| D1_faintest_flagged_K | None | measured | None |
| D1_barnard_K4.5_overflow | 2/2 | measured | None |
| D2_onset_K50 | 9.5 | measured (≈7–10 expected, bands 1–3) | None |
| D2_faintest_flagged_K | 9.6 | measured | None |
| D2_barnard_K4.5_overflow | 2/2 | measured | None |
| D3_onset_K50 | 9.5 | measured (≈7–10 expected, bands 1–3) | None |
| D3_faintest_flagged_K | 9.42 | measured | None |
| D3_barnard_K4.5_overflow | 2/2 | measured | None |
| D4_onset_K50 | None | measured (≈7–10 expected, bands 1–3) | None |
| D4_faintest_flagged_K | 15.29 | measured | None |
| D4_barnard_K4.5_overflow | 2/2 | measured | None |
| D5_onset_K50 | None | measured (≈7–10 expected, bands 1–3) | None |
| D5_faintest_flagged_K | None | measured | None |
| D5_barnard_K4.5_overflow | 2/2 | measured | None |
| D6_onset_K50 | None | measured (≈7–10 expected, bands 1–3) | None |
| D6_faintest_flagged_K | None | measured | None |
| D6_barnard_K4.5_overflow | 2/2 | measured | None |

## Caveats

- one field, 2 frames per detector, QR3 only; the onset depends on the channel (λ) within a band and on the PSF's peak fraction, so treat it as ±0.5 mag
- 2MASS K compared for all bands; for bands 4–6 the relevant colour (K − W1/W2) adds scatter

git c12717d (dirty) · contract 0.1.0 · author I · reviewer pending
