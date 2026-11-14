# G5.25yr-data — FAIL (L3)

**Scope.** The data half of G5.25yr (workflow.md §6: "D (data), I (normalisation), F"). Archival epochs are
found and fetched server-side; the jumps below are **catalogue-based** (2MASS PSC position at the target's
own epoch → pos(2026.63)), not image measurements, and pos(t) is a temporary linear-PM adapter until M's
`targets.pos(t)` exists. The image-measured jumps of implementation.md §10.2 remain I's/M's/F's.

| target | 2MASS epoch (fp_psc) | jumps | FOV | NEOWISE W2 epochs | sample cutout contains (archival, 2026) |
|---|---|---|---|---|---|
| barnard | 2000-05-28 | 2MASS→now (catalogue position → pos(now)): 4.539′, AllWISE→now (pos): 2.794′ | 6.8′ | 21 | {'archival': False, 'now': True} |
| epsindb | 1999-11-08 | 2MASS→now (catalogue position → pos(now)): 2.092′, AllWISE→now (pos): 1.259′ | 3.1′ | 21 | {'archival': True, 'now': True} |
| wise0855 | — | AllWISE→now (pos): 2.191′ | 3.3′ | 21 | None |

WISE 0855 has no 2MASS epoch: 2MASS 08551654-0714457 (K = 15.8) lies 3.6″ from its J2000 position but is a
different star (WISE 0855: J ≈ 25); the client's brightness check rejects it.

## Metrics

| metric | value | threshold | pass |
|---|---|---|---|
| barnard_jump_arcmin | 4.539 | 4.55 ± 0.1 (2MASS→now (catalogue position → pos(now))) | True |
| barnard_2mass_epoch | 2000-05-28 | per-target fp_psc.jdate | True |
| barnard_fov_arcmin | 6.81 | ≥ 1.5 × jump | True |
| barnard_sample_cutout | {'bytes': 277402, 'shape': [323, 311], 'contains': {'archival': False, 'now': True}} | valid FITS containing archival and 2026 positions | False |
| barnard_epochs | {'2MASS Ks': 1, 'AllWISE W1': 8, 'AllWISE W2': 8, 'NEOWISE W2 epochs': 21} | reported | None |
| epsindb_jump_arcmin | 2.092 | 2.1 ± 0.1 (2MASS→now (catalogue position → pos(now))) | True |
| epsindb_2mass_epoch | 1999-11-08 | per-target fp_psc.jdate | True |
| epsindb_fov_arcmin | 3.14 | ≥ 1.5 × jump | True |
| epsindb_sample_cutout | {'bytes': 83062, 'shape': [190, 156], 'contains': {'archival': True, 'now': True}} | valid FITS containing archival and 2026 positions | True |
| epsindb_epochs | {'2MASS Ks': 2, 'AllWISE W1': 15, 'AllWISE W2': 16, 'NEOWISE W2 epochs': 21} | reported | None |
| wise0855_jump_arcmin | 2.191 | 2.2 ± 0.1 (AllWISE→now (pos)) | True |
| wise0855_2mass_epoch | not detected | not detected (J≈25) | True |
| wise0855_fov_arcmin | 3.29 | ≥ 1.5 × jump | True |
| wise0855_sample_cutout | {'bytes': 190, 'error': "OSError('No SIMPLE card found, this file does not appear to be a valid FITS file. If this is really a FITS file, try with ignore_missing_simple=True')"} | valid FITS containing archival and 2026 positions | False |
| wise0855_epochs | {'2MASS Ks': 0, 'AllWISE W1': 7, 'AllWISE W2': 8, 'NEOWISE W2 epochs': 21} | reported | None |

## Caveats

- pos(t) is a temporary linear-PM adapter (no parallax): ≲1″ error, far below the 0.1′ tolerance
- catalogue-based jumps only; image-measured jumps belong to I/M/F

git 20efbf1 (dirty) · contract 0.1.0 · author D · reviewer pending

## Superseded

Failed on two acquisition bugs found by this run: (1) the 2MASS image search queried only the midpoint, and Barnard's one returned Atlas image did not contain the 2000 position; (2) AllWISE SIA2 rows include artefact tables and the plan picked a `.tbl`. Fixed (search at archival, mid and 2026 positions; `science` subtype only) and re-run: see the sibling record.
