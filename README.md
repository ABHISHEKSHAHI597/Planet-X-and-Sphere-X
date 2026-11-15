# ParallaX — SPHEREx blink comparator

A free web tool that plays NASA [SPHEREx](https://spherex.caltech.edu/) images of any patch of sky like a short
video, so that anyone can spot stars and brown dwarfs that move and objects that change brightness. Built for the
[NASA Space Apps Challenge 2026](https://www.spaceappschallenge.org/), challenge *Planet X and SPHEREx*.

Type a star name or coordinates. ParallaX finds every SPHEREx frame of that patch, groups them into visits, stacks
each visit in each of six infrared bands on one shared grid and brightness scale, north up, and plays the visits as
a blink. Moving stars hop; varying objects pulse.

## What it does

**Core blink** (always shown)

- **Resolver**: star names, aliases or coordinates, with an epoch banner when a catalogue position is out of date.
- **Coverage summary**: every SPHEREx frame of the patch, found by two independent archive routes.
- **Visit-stack blink** in two viewers, a WebGL2 canvas and a PNG fallback, with timeline and player controls.
- **Flags overlay** and per-frame QA badges.
- **Pinned permalinks**: the URL is the state, and pinned views give the same pixels every time.

**Science and context layers**

| Area | Capabilities |
|---|---|
| Motion | predicted track overlay, astrometry card with a motion vector fitted from SPHEREx alone, mover finder, Solar System track mode (JPL Horizons) |
| Spectra | spectra on the fly (forced blend photometry), spectral flipbook, λ-scrubber, λ-matched difference images |
| Time | light curves, 25-year blink (2MASS → AllWISE → NEOWISE → SPHEREx) |
| Context | Aladin Lite sky, Gaia/SIMBAD markers at the visit epoch, AllWISE layer at its own epoch, RGB composites of band stacks, model-filled bright cores |
| Planet X | parallax-linked orphan candidates, candidate reports, exports |
| Sharing | `/embed` route, release-freshness badge, `/proof` evidence page |

Every built capability ships to production at flag level `staging` (release decision of 2026-11-15, see
[config/features.yaml](config/features.yaml)). Until its checks are accepted, the API marks its results with
validity `"unvalidated"`. The UI shows no badge for this. A flag goes to `on` only when every check it requires is
accepted, which `scripts/check_flags.py` enforces in CI.

## Quick start

Requirements: Python 3.12 with [uv](https://docs.astral.sh/uv/), and Node.js with npm.

```bash
# backend
cd backend && uv sync --frozen

# one-time: the locked calibration (~430 MB from the public SPHEREx bucket, sha256-checked against
# config/calibration.lock) into ~/.cache/parallax/calib
uv run python ../scripts/bootstrap_calib.py fetch

uv run uvicorn app.main:app --reload            # API on :8000, under /api/v1

# frontend (separate terminal); Vite proxies /api to $PARALLAX_API (default http://localhost:8000)
cd frontend && npm ci && npm run dev
```

**No network or no backend?** Run `npm run dev:mock` for an in-browser mock, or start the API with `MOCK=1` to serve
the golden payloads in `frontend/fixtures`. Neither is for demos.

**Calibration.** The backend finds the calibration in `~/.cache/parallax/calib` (or `$PARALLAX_CALIB`) by itself.
Set `CALIB_ROOT` if you keep it somewhere else, or `CALIB_ROOT=` to run without one. Without it the blink still
works, but spectra, astrometry, light curves, differences, cubes and the flipbook answer *409 needs the locked
calibration*. `GET /healthz` shows which calibration is loaded (`"calibration": "locked 94e18b883fdc9b28 at …"`).

**Archive outages.** Gaia, AllWISE, CatWISE and new-target lookups go through IRSA. When IRSA is down (`/healthz`
probe `sia2` not ok), those lookups fail with *archive service not answering*. Views that are already built, the
pinned demos and the stars in [config/prewarm_stars.txt](config/prewarm_stars.txt) (pre-loaded with
`scripts/prewarm.py`) still open.

## Configuration

All settings are optional environment variables. They are documented in
[backend/app/settings.py](backend/app/settings.py), and [.env.example](.env.example) is the template for a server.

| Variable | Meaning |
|---|---|
| `ENVIRONMENT` | `local` (default), `staging`, `production`, `snapshot` or `mock` |
| `MOCK=1` | serve golden payloads instead of real data |
| `FRAMESOURCE` | `auto` (default), `s3`, `irsa` or `fixture`; `IN_AWS_US_EAST_1=1` prefers S3 sections |
| `OFFLINE=1`, `SNAPSHOT_DIR` | no network: serve pre-warmed views only (demo laptops) |
| `CACHE_DIR`, `CACHE_MAX_GB` | disk cache root, and an LRU budget for frames and views (pinned demos are kept) |
| `CALIB_ROOT` | calibration location (see above) |
| `CPU_WORKERS`, `JOB_TIMEOUT_S`, `MAX_FOV_ARCMIN`, `MAX_FRAMES_PER_VIEW` | compute limits |
| `*_PER_MINUTE_PER_IP`, `CANDIDATES_PER_HOUR_PER_IP` | rate limits |
| `PUBLIC_GALLERY=1` | show the candidate gallery (off by default) |

## API

FastAPI serves everything under `/api/v1`, plus `/healthz` and `/metrics`. The OpenAPI schema is committed at
[frontend/src/api/openapi.json](frontend/src/api/openapi.json) and the TypeScript client is generated from it
(`scripts/gen_contracts.py`).

| Group | Endpoints |
|---|---|
| Core | `GET /resolve`, `GET /coverage`, `GET /releases` |
| Views | `POST /views`, `GET /jobs/{id}/events` (progress stream), `GET /views/{key}/manifest`, stack, PNG, RGB and cube images |
| Science | `/views/{key}/diff`, `/views/{key}/blink25`, `/views/{key}/frames`, `/spectrum`, `/astrometry`, `/lightcurve`, `/sso`, `/movers`, `/overlays/{cat}` |
| Output | `GET /export/{fmt}`, `POST`/`GET /candidates` |

## Testing

```bash
cd backend
uv run pytest -q tests/unit tests/synthetic tests/real tests/app   # unit, synthetic science, recorded real files, platform/contract
uv run lint-imports                                                # spherex/ never imports app/; only access/ and external/ do network I/O
uv run mypy -p app --follow-imports=silent && uv run mypy -p spherex

cd ../frontend
npm test && npm run typecheck && npm run lint
```

Tests run offline: real-data tests use the recorded archive responses and FITS files in `backend/tests/data/real`.
`tests/network` needs live archives and is not part of CI.

CI ([.github/workflows/ci.yml](.github/workflows/ci.yml)) runs the jobs `static`, `unit`, `synthetic`,
`real-file`, `contract` and `e2e-offline` on every push and pull request. Pushes to `main` then run
`build-deploy`. The `contract` job also fails if any generated file is out of date:

```bash
cd backend
uv run python ../scripts/gen_contracts.py             # openapi.json + generated.ts
uv run python ../scripts/make_goldens.py              # frontend/fixtures/golden (mock payloads)
uv run python ../scripts/validate.py status --write   # validation/STATUS.md
uv run python ../scripts/make_proof.py --write        # /proof page data and the table below
```

`nightly.yml` re-runs validation on the project VM every night, and `release.yml` builds release candidates.

## Evidence & validation

Every claim is backed by a machine-written evidence record under `validation/`.
Run `python scripts/validate.py status` to see the current state, or visit the `/proof` page in the tool.
[validation/STATUS.md](validation/STATUS.md) lists every check, its level and whether it is stale. A record goes
stale when code it covers changes after it was made. A stale record counts one level lower until it is re-run.

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
| Subtracting two visits naively is wrong for SPHEREx, and our tests show it | passed | rule: pass | passed, re-run pending | [I-L1-synthetic](validation/I-L1-synthetic/2026-11-15-15f3ca1/report.md) (L1) |
| Where nothing moves, the matched difference shows nothing | passed | rule: pass | passed, re-run pending | [I-L1-synthetic](validation/I-L1-synthetic/2026-11-15-15f3ca1/report.md) (L1) |

Not proven yet (each is hidden or marked *unvalidated* in the tool):

| What we claim | Our number | Reference | State | Record |
|---|---|---|---|---|
| Stars that should stay still, stay still | 0.08 px | rule: < 0.1 px (proposed) | changes requested | [G2-registration](validation/G2-registration/2026-11-06-c12717d/report.md) (L3) |
| Each pixel is given the right wavelength | 2.52 nm | rule: < 3.0 | changes requested | [F1](validation/F1/2026-11-06-c12717d/report.md) (L2) |
| Star profiles in the short-wavelength bands | — | — | failed | [F5](validation/F5/2026-11-08-d6d2e45/report.md) (L3) |
| The wavelength-matched difference image on real data | 354.3° dipole direction | rule: 356 ± 15 | changes requested | [G4a-real](validation/G4a-real/2026-11-06-c12717d/report.md) (L3) |
| WISE 0855's spectrum at short wavelengths | -3.24σ | rule: abs(S/N)<3 (signed blend flux must be consistent with zero) | failed | [G4b-wise-stacks](validation/G4b-wise-stacks/2026-11-08-8d12a02/report.md) (L3) |
| R Draconis's pulsation period | 18 independent bins | rule: >=20 | failed | [G5.lc-rdra](validation/G5.lc-rdra/2026-11-08-8d12a02/report.md) (L3) |
| Barnard's Star's motion fitted from SPHEREx alone | 0.30″/yr from the catalogue | rule: <1.0 | inconclusive | [G3-pm-barnard](validation/G3-pm-barnard/2026-11-08-d6d2e45/report.md) (L3) |

<!-- proof:end -->

## Deployment

```bash
cp .env.example .env                                     # then edit
IMAGE_TAG=<sha or RC> docker compose up -d               # staging / production (api + Caddy web with automatic HTTPS)
docker compose --env-file deploy/offline.env up -d       # offline demo laptop, serving the snapshot
```

[docs/deploy.md](docs/deploy.md) is the full runbook: creating the VM, release candidates, rollback, snapshots,
offline laptops, failure drills, and **ParallaX Lite**, a frozen static copy for GitHub Pages
(`npm run build:lite`, `scripts/publish_lite.sh`).

## Project structure

| Path | What |
|---|---|
| `backend/app/` | FastAPI service: routes, view pipeline and job queue, cache, settings, rate limits |
| `backend/spherex/` | Science library: archive access (`access/`), external catalogues (`external/`), preprocessing, stacking, astrometry, photometry, spectra, light curves, movers. It never imports `app/` |
| `backend/tests/` | `unit`, `synthetic`, `real` (recorded data), `app` (platform/contract), `network` (live, manual) |
| `frontend/` | React + TypeScript + Vite viewer: WebGL2 renderer (`src/gl/`), Aladin Lite, TanStack Query, Zustand |
| `scripts/` | Evidence harness (`validate.py`, `verify/`), generators, calibration bootstrap, pre-warm, snapshot, release tooling |
| `validation/` | Evidence records (`<check>/<date>-<sha>/record.json`, report, review) and `STATUS.md` |
| `config/` | Feature flags, proof spec, releases, calibration lock, pinned targets, pre-warm list |
| `deploy/` | Web Dockerfile, Caddyfile, AWS setup, deploy script, offline env |
| `docs/` | Deploy runbook, [extending](docs/extending.md) (new release, pin, mission or capability), [data refresh](docs/data-refresh.md), [classroom activity](docs/classroom-barnard.md), [decision records](docs/decisions/), [Hugging Face Spaces](docs/DEPLOY_HF.md) |
| `ParallaX-presentation/` | Space Apps presentation (`main.tex` source, compiled `presentation.pdf`) |

## Licence

[GPL-3.0-or-later](LICENSE) (Aladin Lite is GPL-3 and bundled).

## Citation

See [CITATION.cff](CITATION.cff).
