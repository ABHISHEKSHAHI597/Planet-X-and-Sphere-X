# ParallaX — SPHEREx blink comparator 

A free web tool that plays NASA [SPHEREx](https://spherex.caltech.edu/) images of any patch of sky like a short
video, so that anyone can spot stars and brown dwarfs that move and objects that change brightness. Built for the
[NASA Space Apps Challenge 2026](https://www.spaceappschallenge.org/), challenge *Planet X and SPHEREx*.

Type a star name or coordinates. ParallaX finds every SPHEREx frame of that patch, groups them into visits, stacks
each visit in each of six infrared bands on one shared grid and brightness scale, north up, and plays the visits as
a blink. Moving stars hop; varying objects pulse.

## Quick start

```bash
# backend
cd backend && uv sync --frozen && uv run uvicorn app.main:app --reload

# frontend (separate terminal)
cd frontend && npm ci && npm run dev
```

See [docs/deploy.md](docs/deploy.md) for Docker, staging and production deployment.

## Evidence & validation

Every claim is backed by a machine-written evidence record under `validation/`.
Run `python scripts/validate.py status` to see the current state, or visit the `/proof` page in the tool.

<!-- proof:begin (scripts/make_proof.py --write) -->

| What we claim | Our number | Reference | State | Record |
|---|---|---|---|---|
| Barnard's Star has moved by the amount its catalogue motion predicts | 4.540′ | 4.540′ predicted | passed, review pending | [G5.25yr-jumps](validation/G5.25yr-jumps/2026-11-08-5f9f54b/report.md) (L3) |
| So has ε Indi B | 2.085′ | 2.101′ predicted | passed, review pending | [G5.25yr-jumps](validation/G5.25yr-jumps/2026-11-08-5f9f54b/report.md) (L3) |
| The challenge's WISE 0855 coordinate is an old position, and we know where the object is now | 2.149′ | 2.153′ predicted | passed, review pending | [G5.25yr-jumps](validation/G5.25yr-jumps/2026-11-08-5f9f54b/report.md) (L3) |
| A motion fitted from SPHEREx alone agrees with the catalogue | 0.06″/yr | rule: <1.5 | passed, re-run pending | [G3-pm-epsindb](validation/G3-pm-epsindb/2026-11-08-8d12a02/report.md) (L3) |
| Every moving test target has at least two full visits to blink | 2 | rule: ≥ 2 (P0-3) | passed, re-run pending | [G1-time-model](validation/G1-time-model/2026-11-06-c12717d/report.md) (L3) |
| We find every frame the archive has, by two independent routes | 5 of 5 | rule: identical deduplicated sets | passed, re-run pending | [F11](validation/F11/2026-11-07-20efbf1/report.md) (L3) |
| The same link gives the same pixels | all identical | rule: byte-identical | passed, re-run pending | [G2-repro](validation/G2-repro/2026-11-10-989bf01/report.md) (L3) |

Not proven yet (each is hidden or marked *unvalidated* in the tool):

| What we claim | Our number | Reference | State | Record |
|---|---|---|---|---|
| Stars that should stay still, stay still | 0.08 px | rule: < 0.1 px (proposed) | changes requested | [G2-registration](validation/G2-registration/2026-11-06-c12717d/report.md) (L3) |
| Each pixel is given the right wavelength | 2.52 nm | rule: < 3.0 | changes requested | [F1](validation/F1/2026-11-06-c12717d/report.md) (L2) |
| Subtracting two visits naively is wrong for SPHEREx, and our tests show it | passed | rule: pass | changes requested | [I-L1-synthetic](validation/I-L1-synthetic/2026-11-06-c12717d/report.md) (L1) |
| Where nothing moves, the matched difference shows nothing | passed | rule: pass | changes requested | [I-L1-synthetic](validation/I-L1-synthetic/2026-11-06-c12717d/report.md) (L1) |
| Star profiles in the short-wavelength bands | — | — | failed | [F5](validation/F5/2026-11-08-d6d2e45/report.md) (L3) |
| The wavelength-matched difference image on real data | 354.3° dipole direction | rule: 356 ± 15 | changes requested | [G4a-real](validation/G4a-real/2026-11-06-c12717d/report.md) (L3) |
| WISE 0855's spectrum at short wavelengths | -3.24σ | rule: abs(S/N)<3 (signed blend flux must be consistent with zero) | failed | [G4b-wise-stacks](validation/G4b-wise-stacks/2026-11-08-8d12a02/report.md) (L3) |
| R Draconis's pulsation period | 18 independent bins | rule: >=20 | failed | [G5.lc-rdra](validation/G5.lc-rdra/2026-11-08-8d12a02/report.md) (L3) |
| Barnard's Star's motion fitted from SPHEREx alone | 0.30″/yr from the catalogue | rule: <1.0 | inconclusive | [G3-pm-barnard](validation/G3-pm-barnard/2026-11-08-d6d2e45/report.md) (L3) |

<!-- proof:end -->

## Project structure

| Directory | What |
|---|---|
| `backend/` | FastAPI service: archive access, image stacking, science pipeline |
| `frontend/` | React + Three.js viewer |
| `scripts/` | Evidence harness, contract generation, release tooling |
| `validation/` | Evidence records, registry, schema |
| `config/` | Feature flags, proof spec, releases |
| `deploy/` | Dockerfiles, deploy script |
| `docs/` | Architecture, deploy, contribution guides |
| `submission/` | Space Apps submission drafts |

## Licence

[GPL-3.0-or-later](LICENSE) (Aladin Lite is GPL-3 and bundled).

## Citation

See [CITATION.cff](CITATION.cff).
