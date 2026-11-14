# ParallaX — Engineering Workflow

### How a five-person team builds, validates, releases and demos the SPHEREx blink tool

> **Scope of this document:** process. It covers who owns what, how work moves through the team, what evidence makes a capability valid, how the pieces are integrated and released, and how the demo is run. It does not explain the science or the algorithms; those live in the two companion documents and are referenced by section.
>
> Written 2026-11-06. Development runs from **Fri 2026-11-06**. The Space Apps Resources tab opens **Fri 2026-11-13**. The event runs **Sat 2026-11-14 09:00 → Sun 2026-11-15 23:59** (local).

---

## 0. Principles

1. **Evidence decides, not dates.** A capability is done when its exit criteria are met with recorded evidence (§5–§6). Calendar dates in §10 are targets. When a target slips, we change scope, never the criteria.
2. **Foundations first.** Facts about the real SPHEREx files that are still unverified (§5) block every capability that depends on them. Code may be written against an assumption, but it is not *valid* until the assumption is checked on real data.
3. **Synthetic tests prove algorithms; real data proves the product.** The two are recorded and reported separately (§4). A synthetic pass never becomes a scientific claim.
4. **No misleading fallbacks.** If a scientifically correct method isn't ready, the feature is switched off. It is never replaced with a simpler method that can create false signals (§11.2).
5. **Contracts are versioned and tested, not frozen.** Interfaces evolve through versioned, reviewed changes that land with their consumers (§7).
6. **Everything is reproducible.** Every validation result cites the git commit, contract versions, calibration lock and pinned frame list that produced it (§8).
7. **`main` is always releasable.** Small reviewed changes, green CI, unfinished work behind flags, automatic deployment to staging (§9).
8. **The demo cannot depend on the venue.** Pinned data, offline snapshots and rehearsed failure drills (§13).

---

## 1. Sources of truth

| Question | Authority | How it changes |
|---|---|---|
| What is true about SPHEREx, the archive, the targets and the science | [`understanding.md`](./understanding.md) | A PR that cites evidence (query, file, measurement) and marks the fact ✅ with its date |
| What the product does and how its algorithms work | [`implementation.md`](./implementation.md) | Updated **in the same PR** as any code that deviates from it |
| Exact wire formats: Python boundary types, HTTP schemas, binary payloads, config files | Code: `backend/spherex/types.py`, `backend/app/schemas.py` → `/openapi.json` → generated `frontend/src/api/types.ts`; `CONTRACTS.md` changelog | Versioned contract PRs (§7) |
| Whether a capability is currently valid | `validation/STATUS.md`, generated from evidence records (§4.5) | Only by merging evidence |
| Who owns what, how work flows, gates, releases, demo operations | This document | Team agreement at a daily sync; product lead merges |
| Why a non-obvious decision was made | `docs/decisions/NNNN-*.md` (one-page records) | Added when a decision closes off an alternative |

**Rules**
- When two documents disagree, the authority in this table wins and the other document is fixed in the same week.
- This document never restates a number, algorithm or threshold from the other two; it points to them. Where a gate needs a threshold that the other documents don't define, it is marked **proposed** here and moves into implementation.md §10 once a real-data run has confirmed it.
- implementation.md §11.0–§11.3 (day-1 checklist, roles and 39-hour plan) are superseded by this document: the day-1 checks become the foundation checks in §5. implementation.md §11.4 (demo script) and §11.5 (submission checklist) remain authoritative.

---

## 2. Team, ownership and decision rights

### 2.1 Roles

Five owners. Each module has exactly one owner and one backup. The owner decides how the module is built; the backup reviews its PRs and can keep it running if the owner is unavailable.

| ID | Role | Owns | Backup for |
|---|---|---|---|
| **D** | Data and archive engineer | `spherex/access/*` (coverage, dedup, both FrameSources, retries, caches, releases, watcher) · `calib.py` and the calibration lock · `spherex/external/*` (SIMBAD, Gaia, 2MASS, AllWISE/NEOWISE, CatWISE, SkyBoT clients) · real-file fixtures and pinned frame lists · the data-refresh and DR1 procedure · 25-year-blink data acquisition | P |
| **I** | Imaging scientist | `flags.py`, `preprocess.py`, `epochs.py` (time model), `grid.py`, `stack.py`, `cube.py` (spectral cubes and the λ-matched difference), `significance`, `render.py` (stretch, float16) · bright-target display fill · spectral flipbook and λ-scrubber products · mover *detection* · 25-year-blink normalisation · the shared **synthetic scene generator** (§8.1) | M |
| **M** | Measurement scientist | `targets.py` science (propagation, `seen_by_spherex`, `pos(t)`, epoch guard) · `parallax_factors` · `epsf.py`, re-registration, `astrometry.py` (PM and parallax fit) · `photometry.py` (spectra, indices) · `lightcurve.py` · `ephem.py` (Horizons, Pluto track mode) · mover *linking and scoring* · `planetx.py` | I |
| **P** | Platform and release engineer | `backend/app/*` (routers, job runner, SSE, schemas, view keys and pins, PNG renderer, exports, candidates) · mock mode · CI/CD, staging and production deploys, observability · the validation harness (§4.5) · snapshot mode and offline demo machines · **release manager** (§12) | D, F |
| **F** | Frontend and product lead | All of `frontend/` (WebGL viewer, PNG viewer, player, overlays, timeline, URL state, embed, target bar, panels, Aladin context, About/Credits, accessibility) · **product lead**: scope, priorities, the public narrative, the submission package (§13.6) | — (P backs up the frontend) |

**Why the science is split this way.** Pixel-domain work (calibration through stacks, cubes and differences) and source-domain work (positions, fluxes, motion, spectra, time series) have different failure modes and different validation targets. Splitting them gives each scientist one P1 headline capability (I: λ-matched difference; M: spectra and motion), one share of the P2 work, and makes each the mandatory reviewer of the other (§9.4). Neither scientist owns platform or UI code.

**Load across the schedule.** D's and P's work is front-loaded (data plumbing, platform). F's is spread evenly and peaks at submission. The scientists peak in the middle. The plan rebalances deliberately:

| Role | Foundations | Vertical slice | Science | Hardening | Event |
|---|---|---|---|---|---|
| D | High | High | Medium: takes the 25-year blink data and R Dra's scale problem off the scientists | Medium: data refresh, evidence publishing, README technical sections | Medium: refresh check, video support |
| I | Medium | High | High | Medium | Low–medium |
| M | Medium | Medium | High | Medium | Low–medium |
| P | High | High | Medium | High: RCs, snapshots | High: demo operations |
| F | Medium | High | High | Medium | High: story and submission |

### 2.2 Hats (cross-cutting duties)

| Hat | Worn by | Duty |
|---|---|---|
| Product lead | F | Owns the backlog order and scope decisions; runs the daily sync; owns the submission |
| Science sign-off | I and M | Each signs off gates in their own domain; the other scientist reviews the evidence |
| Release manager | P | Cuts release candidates, runs go/no-go, owns rollback (§12) |
| Data steward | D | Owns pinned data, the calibration lock, and the response to new archive data (§12.4) |
| Target stewards | see §6, "Target stewards" | Each acceptance target has one person who knows its pitfalls and runs its acceptance checks |

### 2.3 Decision rights

| Decision | Decides | Must consult | Veto |
|---|---|---|---|
| Backlog order, P2 picks, what is cut | F | Module owners affected | — |
| Whether a capability is scientifically valid | Domain scientist (I or M) | The other scientist | Either scientist can block a scientific claim |
| A contract change | The interface pair (§2.4) | Other consumers of that surface | Any consumer, for breaking changes |
| Algorithm deviation from implementation.md | Module owner | The other scientist | — (but the doc must be updated) |
| Release go/no-go | P | I, M (science), F (product) | I or M for a failing science gate; F for a broken core journey |
| Adopting new archive data in a release | D | I, M | P (release timing) |

Disagreements are settled by evidence. If evidence can't settle one before a release, the contested capability ships **off**.

### 2.4 Interface pairs

Every boundary has a pair who own its contract and its integration tests.

| Boundary | Pair | Surface (§7) |
|---|---|---|
| Raw frames and calibration → pixel pipeline | D ↔ I | `FrameRef`, `RawFrame`, `Calib` |
| Catalogues and calibration → measurements | D ↔ M | catalogue rows, ePSF tables, solid-angle maps |
| Pixel pipeline → measurements | I ↔ M | `CalFrame`, `Grid`, `Cube`, the ePSF used for bright-target fill |
| Science → API | I ↔ P, M ↔ P | `Stack`, `Cube`, spectrum rows, motion fits, light curves |
| Data → API | D ↔ P | coverage, pins, release state, caches |
| API → frontend | P ↔ F | OpenAPI schemas, binary formats, SSE events, URL schema |

---

## 3. Module boundaries

```
 frontend/ (F)  ── HTTP + SSE only ──►  backend/app/ (P)  ──►  backend/spherex/ (D, I, M)
                                                                   ├─ access/, external/, calib.py   (D)
                                                                   ├─ flags, preprocess, epochs, grid,
                                                                   │  stack, cube, render              (I)
                                                                   └─ targets, epsf, astrometry,
                                                                      photometry, lightcurve, ephem,
                                                                      movers (linking), planetx        (M)
```

**Rules, enforced in CI**
- `spherex/` never imports `app/`, FastAPI, or settings. Configuration arrives as arguments. Every science function is testable with pytest and fixtures alone. (`import-linter` contract in CI.)
- `spherex/access/` is the only package that performs network I/O for SPHEREx pixels. Science modules receive data; they never fetch it.
- The frontend never calls IRSA, SIMBAD or any external service except Aladin's HiPS tiles. Everything else goes through our API.
- Boundary functions take and return the types in `spherex/types.py`. Internal helpers are free-form.
- `mypy --strict` runs on `types.py` and on every module's public functions.

Module specifications are in implementation.md §3 (data access), §4 (science core), §5 (API), §6 (frontend). The repository layout is implementation.md §13, plus the additions in §15 below.

---

## 4. Evidence model

### 4.1 Evidence levels

| Level | Name | Data | What it can establish | What it cannot establish |
|---|---|---|---|---|
| **L0** | Unit | Any (hand-made arrays, recorded responses) | Code logic, edge cases, error handling | Anything about SPHEREx |
| **L1** | Synthetic | Simulated scenes with injected truth and stated assumptions (§8.1) | An algorithm recovers the truth *when the world matches the assumptions* | That the assumptions hold for real files |
| **L2** | Real-file | Committed real SPHEREx fixtures with provenance | Format handling and conventions: HDUs, flags, WCS, orientation, units, pixel origins | Behaviour on the science targets |
| **L3** | Real-target | Pinned real frame sets of the acceptance targets (§8.3) | That a capability works on the science cases, with measured numbers | Agreement with independent tools |
| **L4** | External | Comparison with an independent source: Gaia, IRSA Spectrophotometry Tool, AAVSO, Horizons, 2MASS | That our numbers agree with the community's | — |

**Claims rule.** Any scientific statement in the UI, README, slides, video or a judge conversation needs **L3**, and **L4** where the gate (§6) requires it. L1 results may be quoted only as "in simulation". Numbers quoted anywhere come from the latest accepted evidence record, never from the planning documents.

### 4.2 Synthetic test rules
- Every synthetic test declares its assumptions in its docstring: PSF model, LVF wavelength map, PA, survey offset, noise model, source spectrum.
- Synthetic scenes come from one shared generator (§8.1), seeded, so I and M test against the same simulated sky.
- Synthetic tests include the known traps: the 180° PA flip with reversed LVF gradient, the half-channel S1/S2 ↔ S3/S4 offset, steep spectra, saturated cores, partial visits. Each trap has at least one test that the naive method *fails*, so we can see the test has teeth.
- A synthetic test can raise a capability from `draft` to `synthetic` (§4.3), never higher.

### 4.3 Capability validity states

| State | Meaning | Feature-flag ceiling |
|---|---|---|
| `blocked` | A foundation check it depends on (§5) is unresolved or failed | Off everywhere except a developer's machine |
| `draft` | Code exists; no passing evidence beyond L0 | Off except in dev |
| `synthetic` | L1 passes | Dev and staging, labelled "unvalidated", never in a release |
| `real` | L2 and L3 pass | Staging; release only with the domain scientist's sign-off |
| `accepted` | All exit criteria of its gate (§6) pass, L4 included where required | Release |

The state of every capability is in `validation/STATUS.md`. A CI check (`scripts/check_flags.py`) fails any release configuration that turns on a flag whose capability is below `accepted` (§9.6).

### 4.4 Real-data validation rules
- Real-data checks run against **pinned** frame lists (§8.3) and the **locked** calibration set (§8.4), so reruns are reproducible.
- Thresholds come from implementation.md §10, or are marked *proposed* in §6 until a run confirms them. A threshold changed after seeing the data needs a written reason in the evidence record and the other scientist's approval.
- A failed check is recorded, not deleted. A fix produces a new record that supersedes it.
- When a check reveals that a documented fact is wrong, the fact is corrected in understanding.md or implementation.md in the same PR as the evidence.

### 4.5 Evidence records

Produced by `scripts/validate.py <check-id>` (the harness is owned by P; checks are owned by the scientists and D). Each record is a directory:

```
validation/<check-id>/<YYYY-MM-DD>-<shortsha>/
  record.json     # machine-readable; schema in validation/schema.json
  report.md       # what was tested, how, result, figures, caveats
  figures/*.png   # e.g. residual maps, track plots, periodograms
```

`record.json` contains at least: check id, evidence level, verdict (`pass` / `fail` / `inconclusive`), metrics with thresholds, git sha, contract versions, calibration lock hash, pin ids, input frame count, runtime, author, reviewer.

Evidence enters `main` through a PR reviewed by someone other than the author, and by the other scientist for science checks. `validation/STATUS.md` is regenerated from the records in CI. Records are invalidated automatically (state drops one level, shown as **stale**) when a file in the check's declared code path changes after the record's sha; the nightly run (§9.5) re-establishes them.

---

## 5. Foundation checks: real-file uncertainties

These are the facts the plan depends on but has not yet confirmed on real files. They are resolved first, because they decide whether downstream science is correct. Each check produces an L2 evidence record. Its outcome is one of: **confirmed** (the documents were right), **corrected** (the documents are fixed in the same PR, and dependent code is updated), or **open** (dependent capabilities stay `blocked`).

| ID | Question | Method (outline) | Owner (+ pair) | Blocks |
|---|---|---|---|---|
| **F1** | Does `CWAVE` from `spectral_wcs`, sliced at the frame's parent pixels, agree with the file's `WCS-WAVE` lookup to ≈1 nm, in the same orientation as `IMAGE`? | One full QR3 file per detector; compare maps; test both a cutout and an S3 section | I (+D) | Cubes, λ-matched difference, every spectrum's λ axis, λ-scrubber |
| **F2** | Do the cutout path (`CRPIXnA`) and the S3-section path produce the same parent-pixel origin, the same WCS and identical pixel values for the same sky pixel? | Fetch one frame both ways; compare pixel by pixel and through the WCS | D (+I) | Every per-pixel calibration lookup; FrameSource failover |
| **F3** | Which HDU of `spectral_channels` holds the channel map, and what do its values mean outside the band? | Read headers; overlay on `CWAVE` | I (+D) | Channel-binned spectra, same-channel annulus grouping (R Dra) |
| **F4** | Do `l3_flux_corrections` factors multiply or divide QR2 fluxes, and are they on the same pixel grid as `IMAGE`? | Headers, plus one star observed in both QR2 and QR3 frames: corrected fluxes must agree better than uncorrected | M (+D) | Any photometry mixing QR2 and QR3: spectra, light curves, indices |
| **F5** | Is the ePSF normalised as implementation.md §4.7 assumes, oriented like `IMAGE`, and zoned in 0-based parent pixels? | Fit 5+ isolated unsaturated stars per detector; residuals symmetric, reduced χ² ≈ 1 | M (+I) | Astrometry, photometry, spectra, bright-target fill |
| **F6** | Do the `FLAGS` header's self-described bit names match understanding.md §4.4, and does the `SOURCE` plane around WISE 0855 sit at its predicted or its WISE-era position? | Parse headers of several releases; inspect planes at the target | I (+M) | Flag presets; the discovery mask policy |
| **F7** | At what brightness does `OVERFLOW` set in, per band? | Match `OVERFLOW` flags to 2MASS K in one crowded field | I (+D) | Bright-target handling thresholds; display fill |
| **F8** | What fraction of frames per target fails `L2DQAFLG` or `FINAST`, and why? | Count over all frames of the 5 targets; inspect failures | I (+D) | The frame-rejection policy, and therefore every stack |
| **F9** | Is there a survey-number keyword? Does the PA-and-date derivation match it on sample frames? | Search headers and archive tables; compare | M (+D) | Timeline and survey labels |
| **F10** | Does Horizons' SPHEREx position (−163182) agree with header `X_SC/Y_SC/Z_SC` within ≈10 km, and in which frame are the header values? | 3+ frames spread across the mission | M (+D) | Pluto track mode; any topocentric correction |
| **F11** | Does the SIA2 response contain the columns the coverage code needs, and does it return the same frame set as TAP after dedup? | 5 targets, both services | D | Coverage, pins, everything downstream |
| **F12** | From the deployment region, which FrameSource meets the budgets, and what concurrency does IRSA tolerate? | Timed S3-section and cutout reads; 10-minute soak at 4 concurrent requests | D (+P) | The default FrameSource; cold-view budgets; demo pre-warm plan |
| **F13** | Which HDU and orientation does the solid-angle pixel map have, and how far is it from `OMEGA_MEDIAN` across a detector? | Read map; compare with header values | M (+D) | Flux units in spectra |
| **F14** | Are both viewers north-up, east-left? | Asymmetric test pattern, then a real field blinked beside Aladin's 2MASS HiPS | F (+P) | Any visual release |
| **F15** | How large are absolute frame WCS residuals against Gaia, and does differential re-registration reduce them as implementation.md §4.7 expects? | Gaia DR3 stars in 12′ regions around 2+ targets | M (+I) | Astrometric claims, PM fits |
| **F16** | On a real visit, how many samples does each per-pixel spectral-cube bin receive? Is coverage close to the ≈1 sample per bin that the matched difference assumes? | Build cubes for one full visit of 2+ targets; histogram occupancy | I | λ-matched difference validity, λ-scrubber |

**Order.** F2, F11, F14 and F6/F8 gate the P0 blink and go first. F1, F3, F16 gate the pixel science; F4, F5, F13, F15 gate the measurement science; F10 gates Pluto. F7, F9, F12 are needed before the first release candidate.

**Scripts** live in `scripts/verify/fNN_<name>.py`. Each runs offline against committed fixtures where possible, and states which real files it used.

---

## 6. Capability gates

Gates group capabilities by dependency, not by calendar. Several can be open at once. A gate is passed when every exit criterion has a passing evidence record at the required level and the sign-off in §2.3 is recorded in the gate PR.

```
 F11 ─► G1 targets & coverage ─┐
 F2, F6, F8, F14 ──────────────┼─► G2 P0 blink ─► RC0 ─┬─► G3 motion            (F5, F15)
 F9 (labels) ──────────────────┘                       ├─► G4a λ-matched diff   (F1, F3, F16)
                                                       ├─► G4b spectra          (F1, F4, F5, F13)
                                                       └─► G5.x extensions      (each with its own deps)
 G2 + G3 + G4a + G4b ─► RC1 ─► G6 release readiness ─► final release
```

### G0 — Ready to build
| Exit criterion | Evidence |
|---|---|
| Repo skeleton, CI with all stages of §9.5 green | CI run |
| Contracts at v0.x for every surface in §7.1, with contract tests running in CI against mock mode | CI run |
| Real-file fixture set committed with provenance (§8.2); calibration lock created (§8.4) | Files in repo |
| Synthetic scene generator produces the traps listed in §4.2 | L0 tests |
| Staging deploy from `main` working | Staging URL |
| Every foundation check has an owner and a target date | `validation/STATUS.md` |

### G1 — Targets, coverage and the time model
| Exit criterion | Level | Owner |
|---|---|---|
| Resolver, propagation and epoch-guard tests of implementation.md §10.1 pass against recorded fixtures (L0) and live services (L3) | L0, L3 | M (with D for clients) |
| F11 confirmed; SIA2 and TAP return identical deduplicated frame sets for all 5 targets; counts reconcile with understanding.md §3.4 (or understanding.md is corrected) | L3 | D |
| Visit classification of implementation.md §10.1 holds on real MJDs (WISE 0855: 2 full + 2 partial in band 6; R Dra: fixed bins); survey numbers consistent with F9 | L3 | I |
| Pinned frame lists exist for the 5 targets at the default FOVs (§8.3) | — | D |

### G2 — P0 blink (`accepted` unlocks RC0)
Requires G1, F2, F6, F8, F14.

| Exit criterion | Level | Owner |
|---|---|---|
| All P0 acceptance items of implementation.md §1.3 met | L3 | per item |
| Visit stacks for all 6 bands render for each target in both viewers from pinned data, with full/partial labels, surveys and dates correct | L3 | I, F |
| **Registration check (proposed):** static Gaia stars show a median positional offset between visit stacks of < 0.1 px | L3 | I |
| **Reproducibility:** two cold builds of the same pinned view produce byte-identical `.f16` payloads | L3 | P |
| Stack flux unbiasedness (implementation.md §10.1 `weighted_stack`) | L1 | I |
| Orientation correct against Aladin on a real field (F14) | L2 | F |
| PNG fallback works with WebGL disabled; pinned links reproduce views after reload | L3 | F, P |
| Cold and warm performance measured from staging against implementation.md §6.7 and §10.3 budgets (record, even if missed) | L3 | P, D |
| Credits/About page carries every acknowledgement of understanding.md §4.8 | — | F |

### G3 — Motion
Requires G2, F5, F15.

| Exit criterion | Level | Owner |
|---|---|---|
| `fit_star` and `fit_pm` synthetic tests of implementation.md §10.1 | L1 | M |
| PM fits of implementation.md §10.2 for Barnard's Star, ε Indi B and WISE 0855 (parallax fixed at catalogue values) | L3 | M |
| Fitted PMs compared with Gaia DR3 (or the literature astrometry for WISE 0855) | L4 | M |
| Predicted-track overlay (PM + parallax through `pos(t)`) passes within the per-visit centroid error of the measured positions | L3 | M, F |
| Re-registration residuals before and after (F15) reported | L3 | M |

### G4a — Wavelength-matched difference imaging
Requires G2, F1, F2, F3, F16.

| Exit criterion | Level | Owner |
|---|---|---|
| The synthetic test of implementation.md §10.1 (`spectral_cube` + `at_wavelengths` + `matched_difference`): residuals within threshold across the field, dipole recovered; the naive method demonstrably fails the same scene | L1 | I |
| **Null test (proposed):** two disjoint halves of one real visit, differenced the same way, give significance maps with robust σ ≈ 1 and no structure at star positions | L3 | I |
| Barnard V1→V3 band-6 dipole of implementation.md §10.2 (this is a cross-survey-family pair, the hardest case) | L3 | I |
| A PA-flip pair (PA 0° vs 180°) on a crowded field: Gaia field stars leave residuals below implementation.md §1.3 P1-1's limit, measured as a distribution, not by eye | L3 | I |
| Reviewed by M, with the residual maps in the record | — | M |

Until G4a is `accepted`, the difference mode is off in every release. See §11.2.

### G4b — Spectra on the fly
Requires G2, F1, F5, F13; F4 if releases are mixed.

| Exit criterion | Level | Owner |
|---|---|---|
| ε Indi B spectrum criteria of implementation.md §10.2 | L3 | M |
| WISE 0855 criteria of implementation.md §10.2 (band-6 stack S/N; non-detection in bands 1–3) | L3 | M, I |
| **Repeatability (proposed):** a non-variable field star's per-visit spectra agree with reduced χ² ≈ 1 after the 3% floor | L3 | M |
| One bright isolated star agrees with IRSA's Spectrophotometry Tool within implementation.md §4.8's tolerance | L4 | M |
| Points flagged near He 1.083 µm or by flags are hidden by default and counted | L3 | M, F |
| Reviewed by I | — | I |

### G5 — Extensions (each gated independently)

| Gate | Capability (impl. ID) | Extra dependencies | Exit criteria | Owner |
|---|---|---|---|---|
| G5.25yr | 25-year blink (P2-1) | G2 | Jumps of implementation.md §10.2 / §4.13 for Barnard, ε Ind B and WISE 0855; "positions only" labelling | D (data), I (normalisation), F |
| G5.lc | Light curves (P2-3) | G4b, F3, F4 | R Dra periodogram criterion of implementation.md §10.2; phase compared with AAVSO (L4); RW Aur ≥ 3 visits per band | M, D (scale) |
| G5.sso | Pluto track mode (P2-10) | G4b, F10 | Pluto criteria of implementation.md §10.2 | M |
| G5.flip | Spectral flipbook, λ-scrubber (P2-2) | G4a | Cube planes sorted by measured λ; flipbook labelled as spectral, not temporal | I, F |
| G5.movers | Mover finder (P2-4) | G3 | **Proposed:** recovers every Gaia star with μ > 0.5″/yr in the test fields; candidate counts per field recorded on ≥ 5 random fields; no unmatched candidate shown without passing vetting | I (detection), M (linking) |
| G5.planetx | Planet X mode (P2-6) | G5.movers, G5.sso | Distances of Makemake, Haumea and Eris within implementation.md §4.12's tolerance | M |
| G5.eng | Exports, embed, candidates, freshness badge (P1-5, P1-6, P2-7, P2-9) | G2 | Engineering acceptance in implementation.md §1.3 | P, F, D |

### G6 — Release readiness
The release-candidate checklist in §12.2.

### Target stewards

Each acceptance target has one steward who runs its acceptance checks, knows its traps, and briefs the team before rehearsals. Stewardship is spread so that every scientist and D carries two.

| Target | Steward | Why them | Traps to watch (understanding.md §8) |
|---|---|---|---|
| Barnard's Star | M | Motion headline | Saturated core, wing fits, parallax zig-zag, 2MASS epoch |
| ε Indi B | I | Artifact literacy | ε Indi A ghosts, crosstalk at 64-column multiples |
| WISE 0855 | D | Data and epoch traps | Name resolution, 2010 coordinate, QR2-only, partial visits, possible autumn-2026 visit |
| RW Aurigae | I | Flags and variability in stacks | Overflow, Hipparcos parallax trap, asteroid traffic |
| R Draconis | D | Deep-field data volume | ≈2,480 frames, frame caps, fixed bins, annulus method (with M) |
| Pluto (P2) | M | Ephemerides | Track mode only; per-visit coverage |

F is the steward of the **public experience** across all targets; P is the steward of their **pinned views and snapshots**.

---

## 7. Contracts

### 7.1 Surfaces

| Surface | Lives in | Version carried in | Consumers |
|---|---|---|---|
| Python boundary types | `backend/spherex/types.py` | `CONTRACT_VERSION` constant | All backend modules |
| HTTP API | `backend/app/schemas.py` → `/openapi.json` → `frontend/src/api/types.ts` (generated, committed) | OpenAPI `info.version`; `schema_version` in every manifest | Frontend, embed hosts |
| Binary payloads (`.f16`, `.f32`, `.u32`) | Defined in implementation.md §5.2; encoded in `render.py`, decoded in `gl/` | `format` field in the manifest, e.g. `f16le-row0south-nodata-65504@1` | Viewer, exports |
| SSE events | `app/schemas.py` | API version | Frontend |
| URL schema | implementation.md §5.3; parsed in `state/url.ts` and the backend canonicaliser | Additive-only (see below) | Users, pinned links, embeds |
| Config files | `config/releases.yaml`, `config/features.yaml`, `config/pins/*.json`, `config/calibration.lock` | pydantic schemas in `app/settings.py` | Backend, CI |
| Evidence records | `validation/schema.json` | `schema` field | Harness, `STATUS.md` |

Shapes are not reproduced in this document. The code is the specification.

### 7.2 Versioning rules
- **Before RC1 (0.x):** changes may break, provided the same PR updates every consumer, regenerates types and fixtures, and is approved by both members of the interface pair. Each change gets a line in `CONTRACTS.md`.
- **From RC1 (1.x):** additive changes only (new optional fields, new endpoints, new event types). Breaking changes need a new major version served side by side; in practice, we avoid them until after the event.
- **URL schema:** always additive. Unknown parameters are ignored with a console warning; removed parameters keep working through an alias table. Every pinned link in the README, slides and video is a URL fixture tested in CI.
- **Binary formats:** a format change means a new `format` id. The viewer refuses unknown formats with a clear message rather than drawing garbage.
- The frontend checks `schema_version` on every manifest and shows a "please reload" banner on mismatch, so a deploy never leaves an open tab silently wrong.

### 7.3 Contract tests (CI)
- Every endpoint's response is validated against its OpenAPI schema in three modes: mock, fixture-backed real pipeline (§8.5), and staging (nightly).
- Generated TypeScript types must match `/openapi.json`; a stale file fails CI.
- Golden binary file (`fixtures/golden/stack_F_121x121.f16`, an "F" in the north-east corner with sentinel pixels) is encoded by Python and decoded by TypeScript tests; both must agree bit for bit.
- Boundary types: each is constructed from real-file fixtures in a test, so a field that real data can't fill shows up immediately.
- Config files are validated against their schemas on load and in CI.

---

## 8. Data for development and validation

### 8.1 Synthetic scenes
- One generator, `backend/tests/synthetic/scene.py`, owned by I and used by everyone. It produces frame sets with known truth: star fields with spectra, an LVF wavelength map per detector, PA 0°/180° visits, the half-channel survey offset, SIP-like distortion, ePSF-like PSFs (Gaussian *and* a table PSF), noise from a variance model, saturated cores, injected movers and variables, cosmic rays.
- Every call is seeded. Scenes are generated at test time, not committed.
- Directory and test names start with `synthetic_`, and CI reports synthetic results in their own section.

### 8.2 Real-file fixtures
Small real SPHEREx files committed under `backend/tests/data/real/`, each with a sidecar `*.provenance.json`: source URL or S3 key, retrieval date, release, pipeline version, byte size, sha256, and the check or test that needs it.

| Fixture | Used by |
|---|---|
| The 29×29 QR3 cutout of implementation.md §10.1 (all HDUs) | Stream parser, flags, headers |
| Stream-aborted cutouts of one full visit of Barnard (band 6) and one of WISE 0855 (bands 5–6), at 6′ | Stacks, cubes, registration, offline pipeline |
| One cutout and one S3 section of the same frame | F2 |
| Headers (not data) of the calibration products | F1, F3, F4, F5, F13 |
| Saved SIA2 and TAP responses for the 5 targets; MJD lists of WISE 0855 and R Dra | Coverage, dedup, time model |
| Recorded SIMBAD, Gaia, Horizons and SkyBoT responses | Resolver and ephemeris tests |

**Limits:** ≤ 5 MB per file and ≤ 60 MB in total in git. Larger sets (full calibration files, whole visits at 12′) go to object storage or GitHub release assets, with their hashes committed. Fixtures are collected from the cloud VM, never over our own link (understanding.md §4.6 measured 30–80 KB/s).

### 8.3 Pinned frame lists
- A pin is the frame list of a view, identified by the 12-hex `pin` of implementation.md §2.3. Pins for the acceptance targets live in `config/pins/<pin>.json` (frame URLs, releases, pipeline versions; a few hundred lines each, R Dra a few thousand).
- Every L3 evidence record names the pins it used. Demo links, README links and validation runs use the same pins.
- New archive data never changes an existing pin. It creates a candidate pin that is evaluated as in §12.4.

### 8.4 Calibration lock
`config/calibration.lock` lists the exact calibration files in use (S3 key, version directory, sha256), discovered by listing as implementation.md §3.5 requires and then frozen. Changing it is a PR owned by D, reviewed by I and M, and it re-runs the foundation checks that read calibration (F1, F3, F4, F5, F13).

### 8.5 Mock mode and fixture-backed mode
- **`MOCK=1`** serves golden manifests and payloads from `frontend/fixtures/` with realistic delays and SSE progress. It lets the frontend work without a backend, and it must always pass the contract tests. It is never used in a demo.
- **`FRAMESOURCE=fixture`** runs the *real* pipeline on committed real-file fixtures with no network. CI uses it for an end-to-end test: resolve → coverage (recorded) → fetch (fixtures) → calibrate → stack → manifest → PNG. This is the cheapest guard against integration breakage.
- Golden payloads are regenerated by `scripts/make_goldens.py` from fixture-backed mode, so mocks track the real pipeline. Regenerated goldens are reviewed as diffs.

### 8.6 Environments and locks
Python dependencies locked with `uv.lock`, Node with `package-lock.json`, container images pinned by digest. The staging and production VMs run the same images. Our local machines are slow to download (understanding.md §4.6), so heavy work — fixture collection, pre-warming, snapshots, nightly validation — runs on the VM.

---

## 9. Development workflow

### 9.1 Tasks
One board with columns **Backlog → Ready → In progress → In review → Done**. A card is Ready only when it has:

- **Outcome:** what will be true when it's done, in one sentence.
- **Owner and reviewer.**
- **Depends on:** cards, foundation checks or gates.
- **Gate and evidence level:** which gate criterion it serves and the level its evidence must reach (L0–L4).
- **Flag:** which feature flag hides it until it's accepted, if any.
- **Size:** fits in one PR. Larger work is split.

**Work-in-progress limit:** one card in progress and one in review per person. Pairing on foundation checks is encouraged, and the pair counts as one card.

### 9.2 Branches and pull requests
- Trunk-based. `main` is protected. Branches are short-lived: `d/s3-sections`, `i/spectral-cube`, `contract/manifest-format`, `verify/f05-epsf`.
- **One concern per PR**, ideally under ≈400 changed lines excluding generated files and fixtures. Draft PRs early for direction checks.
- **PR template** (`.github/pull_request_template.md`):
  - What and why.
  - Evidence level reached, with links to tests or evidence records.
  - Gate and foundation checks affected; state changes expected in `STATUS.md`.
  - Contract changes and `CONTRACTS.md` entry, if any.
  - Docs updated: implementation.md for deviations, understanding.md for facts.
  - Screenshots or a staging link for anything visible.
  - Flags touched.
- Squash-merge. Commit messages state what changed and why.

### 9.3 CODEOWNERS
`.github/CODEOWNERS` maps every path to its owner and backup (§2.1). Contract files list both members of each interface pair. `validation/` lists both scientists. `config/features.yaml` and release configuration list P.

### 9.4 Review rules

| Change touches | Required reviewer(s) | Reviewer checks |
|---|---|---|
| Pixel-domain science (I's modules) | M | Assumptions stated; synthetic test includes the relevant trap; no forbidden fallback (§11.2); doc deviations recorded |
| Measurement science (M's modules) | I | Same, plus units and error propagation |
| Data access, calibration lock, pins | P (and I or M if pixels or calibration values change) | Retries, provenance, reproducibility |
| A contract surface | Both members of the interface pair | Consumers updated; versions bumped; goldens regenerated |
| Evidence records | The other scientist (science) or P (engineering), never the author | Reproducible from the record; thresholds unchanged or justified |
| Frontend | P (code) and, for user-facing text, the relevant scientist for scientific accuracy | Screenshots; accessibility; no unlabelled scientific claim |
| Release config, feature flags | P | `check_flags.py` green; gates accepted |

**Response times:** within the same working half-day before the event; within an hour during the event weekend. Reviewing is higher priority than starting new work.

**When `main` breaks,** anyone reverts the offending PR immediately, without discussion. The fix comes in a new PR.

### 9.5 Continuous integration

| Stage | Runs | Content |
|---|---|---|
| Static | Every PR | `ruff`, `mypy` (boundary modules strict), `import-linter`, `tsc --noEmit`, `eslint` |
| Unit | Every PR | pytest L0; vitest |
| Synthetic | Every PR | pytest L1, reported separately |
| Real-file | Every PR | pytest L2 on committed fixtures, offline |
| Contract | Every PR | §7.3 |
| End-to-end offline | Every PR | Fixture-backed pipeline to PNG (§8.5); frontend smoke test in a headless browser against mock mode, with and without WebGL |
| Build and deploy | Merge to `main` | Images built, pushed by digest, deployed to staging |
| Nightly validation | 02:00 on the VM | Network tests (`-m network`), all L3 checks on pinned data, performance probes; regenerates `STATUS.md`, opens an issue for any regression |

### 9.6 Feature flags
- Defined in `config/features.yaml`, one per capability, with `requires:` naming foundation checks and gates, e.g. `diff: {requires: [F1, F2, F3, F16, G4a]}`.
- Values per environment: `off`, `dev`, `staging`, `on`. The backend serves the effective set in `/releases`, so the frontend and the API agree.
- `scripts/check_flags.py` fails CI if a release configuration sets a flag `on` whose requirements are not `accepted` in `STATUS.md`.
- A flag at `staging` shows an "unvalidated" badge in the UI. That badge covers UX immaturity only; it never licenses showing a scientifically wrong result (§11.2).
- Flags are removed after the event once their capability is accepted; they are not permanent configuration.

### 9.7 Definition of done
A card is done when:
1. its outcome is met at the evidence level the card names, with records merged;
2. CI is green and the change is deployed to staging;
3. docs deviations and contract changes are recorded;
4. user-facing text has been read by F, and scientific text by the relevant scientist;
5. any flag it adds is registered with its requirements.

---

## 10. Plan

### 10.1 Phases

Phases are defined by their exit gates. Dates are targets for planning and are reviewed at every daily sync.

| Phase | Target window | Exit |
|---|---|---|
| **A. Foundations** | Fri Nov 6 → Sun Nov 8 | G0; F2, F6, F8, F11, F14 resolved; F1, F5 started |
| **B. Vertical slice** | Sun Nov 8 → Tue Nov 10 | G1, G2 accepted; **RC0** on production |
| **C. Science** | Tue Nov 10 → Thu Nov 12 | G3, G4a, G4b accepted, or explicitly descoped by the rules in §11.1 |
| **D. Hardening** | Thu Nov 12 → Fri Nov 13 | **RC1**; G6 checklist green; first full rehearsal; Resources-tab review (Nov 13) |
| **E. Event** | Sat Nov 14 → Sun Nov 15 | Final release, complete submission, demo |

**Mid-point review, Tue Nov 10.** The team reviews `STATUS.md` against this table. Anything P1 not on track for Phase C is re-planned by F with the owner. P2 work starts only for items whose dependencies are already `accepted`.

### 10.2 Work per person and phase

| | **A. Foundations** | **B. Vertical slice** | **C. Science** | **D. Hardening** |
|---|---|---|---|---|
| **D** | F11; F2 and F12 (with P, from the VM); real-file fixtures with provenance; calibration bootstrap and lock; coverage + dedup | Both FrameSources, failover, caches, fixture FrameSource; external clients (SIMBAD, Gaia, 2MASS); pins for the 5 targets | Release watcher and freshness data; 25-year-blink data path; R Dra frame volume (caps, deep collections); light-curve input plumbing for M | Data-refresh check; final pins; README technical sections and validation table from `STATUS.md` |
| **I** | Synthetic scene generator; F6, F8; F1 and F3 (with D) | `calibrate`, flag presets, `epochs.py`, grid, stacks, significance, stretch and float16; G1 time-model criteria; G2 science criteria; F7, F16 | Spectral cubes and the λ-matched difference (G4a); bright-target display fill (with M's ePSF); reviews M's G3/G4b | Mover detection or flipbook if gates allow; evidence re-runs; judge Q&A notes on visits and λ matching |
| **M** | Propagation, `pos(t)` and epoch guard against live services; F5, F9, F13 | ePSF class and `fit_star` (L1); parallax factors; predicted-track data; F15 re-registration; F4 (with D); reviews I's G2 | PM fit (G3); spectra and indices (G4b); IRSA cross-check (L4); F10 and Horizons if G5.sso is chosen | Light curves or Pluto if gates allow; evidence re-runs; judge Q&A notes on motion and spectra |
| **P** | Repo, CI stages, contract tooling and v0 contracts, mock mode, validation harness, staging deploy; F12 (with D) | `/resolve`, `/coverage`, `/views` with jobs, SSE, manifests, view keys and pins; PNG renderer; perf probes; RC0 | `/diff`, `/spectrum`, `/astrometry` routes; nightly validation; snapshot mode; offline demo machine image | RC1; G6 checklist; two offline laptops verified; rollback drill |
| **F** | App shell; PNG viewer on goldens; WebGL renderer on goldens; F14 test pattern; URL state; storyboard of the 5 targets | Viewer on real data, timeline, flags overlay, target bar and epoch banner, frame inspector, share/embed | Diff display (behind its flag), spectrum panel, astrometry card, Aladin context, accessibility pass | Polish; mobile; submission draft (video script, slides, README narrative); rehearsal 1 |

### 10.3 Event weekend

The product is built before the event. The weekend is for checking new information, finishing gated extensions, telling the story and running the demo. Everyone sleeps on Saturday night.

| When | What | Owner |
|---|---|---|
| Sat 09:00 | Kickoff: review the 2026 rules, the Resources tab and understanding.md §11 open questions; decide whether anything changes the plan | F |
| Sat morning | Data-refresh check (§12.4): new QR3 periods, DR1, WISE 0855's autumn visit. Results go to staging only | D |
| Sat | Gated P2 work; bug fixes from rehearsal 1; video recording from the release build | All |
| Sat 18:00 | Rehearsal 2 on production and on an offline laptop | F, P |
| Sun 12:00 | **Feature freeze.** Release manager cuts the final RC from `main` (or re-promotes RC1) | P |
| Sun 15:00 | Final snapshot built from the release; both offline laptops verified with Wi-Fi off; rehearsal 3 | P |
| Sun 19:00 | **Complete submission in place** (implementation.md §11.5) | F |
| Sun 19:00–23:00 | Only submission polish and blocking fixes, each through a reviewed PR and an RC patch | F, P |
| Sun 23:00 | Final submission update. Hands off. | F |

### 10.4 Cadence
- **Daily sync, 20 minutes, fixed time.** Rotating presenter demos staging end to end on one target. Then `STATUS.md` changes, blockers, decisions needed. F runs it and records decisions.
- **Written update** in the team channel at the end of each working day: done, next, blocked on whom.
- **Gate reviews** are scheduled by the gate owner when the evidence is ready: 30 minutes, the owner presents the records, reviewers sign in the gate PR.
- **Blockers** are raised in the channel immediately, tagged with the person who can unblock, not held for the sync.
- **Sustainable pace.** No all-nighters before or during the event. Nobody merges after a long day without a second reviewer.

---

## 11. Scope management and scientific integrity

### 11.1 Priorities and descoping
- Tiers are those of implementation.md §1.3 (P0, P1, P2). P0 is the product; P1 is what makes it stand out; P2 is chosen by F from items whose dependencies are `accepted`.
- **Never cut** (implementation.md §11.3): the 5 targets working, URL coordinates and name aliases, flags, epoch handling, credits, the PNG fallback.
- **When a gate is at risk,** F and the owner choose one of: add help from another owner (D and P are the designated helpers for the scientists after Phase B), narrow the capability (fewer bands, one target, a smaller FOV), or ship it off. Lowering the scientific bar is not an option.
- New ideas after the mid-point review go to a post-event column unless every P0 and P1 gate is already accepted.

### 11.2 Forbidden fallbacks

Each of these would make the product easier to finish and scientifically misleading. None may ship in any release, behind a flag or otherwise, labelled or not.

| Tempting shortcut | Why it misleads | What we do instead |
|---|---|---|
| **Naive visit subtraction** (visit-stack A − visit-stack B) | Visits sample different channel mixes, the LVF gradient reverses between PA 0° and 180°, and Surveys 3/4 are offset by half a channel. Static stars leave 6–13σ false residuals (understanding.md §5.3, implementation.md §4.6) | Difference mode stays off until G4a passes. Motion is shown with the blink, side-by-side, onion-skin, the predicted track and the astrometry card, none of which creates false signals |
| Frame pairing at the target, used for a whole field | The same gradient reversal, growing with distance from the target | `pair_frames` only for target-only spectra, under implementation.md §4.6's conditions |
| Exposure-order playback as the default "video" | Wavelength changes between exposures read as variability (understanding.md §5.2) | Visit stacks by default; exposure flipbook in expert mode only, sorted and labelled as spectral |
| Per-frame auto-stretch by default | Creates flicker that looks like variability | One shared stretch (implementation.md §6.3) |
| Raw fluxes across channels as a light curve | Spectral shape masquerades as variability | Spectrally normalised curves or same-channel annulus ratios (implementation.md §4.9) |
| Mixing QR2 and QR3 photometry before F4 is resolved | The absolute gain changed between releases | Photometry per release, or positions only, until F4 is confirmed |
| Masking `SOURCE`, `OUTLIER` or `STREAK` in discovery views | Hides exactly the uncatalogued movers we want | Flag presets of implementation.md §4.3 |
| Measuring on model-filled cores or upsampled grids | False precision | Native frames only (implementation.md §4.4, §4.7) |
| Unrenormalised significance | "5σ" isn't 5σ after resampling | `significance` (implementation.md §4.4) |
| Using the challenge's WISE 0855 coordinate, or a J2000 position, as "now" | Puts the target arcminutes away | Resolver propagation and the epoch banner |
| A PM-only fit for WISE 0855 | Overestimates μ by ≈20% | Parallax fixed at the catalogue value |
| Showing partial visits as full epochs | Depth mismatch reads as fading | Partial visits hatched, off by default |
| Dropping failed frames silently | Hides coverage gaps | Skipped frames listed in the manifest |
| Quoting numbers from the planning documents in the demo | Not reproducible | Numbers from accepted evidence records only |
| Calling a candidate a discovery | Unverified | Candidate language and the honesty banner (implementation.md §8) |

### 11.3 Allowed degradations
- A slower path that gives the same answer (IRSA cutouts instead of S3 sections; server PNG instead of WebGL).
- Fewer targets, bands or FOV presets for a capability, provided what ships passed its gate.
- Pre-computed (snapshot) results instead of live computation, labelled "cached demo data" as implementation.md §9 specifies.
- A capability shipped off, with the UI simply not offering it.

---

## 12. Integration and release

### 12.1 Environments

| Environment | Source | Data | Purpose |
|---|---|---|---|
| Local | Any branch | Mock, fixture-backed, or live | Development |
| Staging | `main`, deployed on merge | Live archive, with pins | Integration, nightly validation, daily demo |
| Production | A release-candidate tag | Live archive, pinned demo views pre-warmed | The public URL in the submission |
| Offline demo laptops (×2) | The same RC images | Snapshot of the RC's pinned views | Demo without the venue network |

### 12.2 Release candidates
- **RC0** after G2: proves the release machinery on the P0 product.
- **RC1** after G3, G4a and G4b (or their explicit descope): the release we would submit if nothing else happened.
- **Final** on Sun Nov 15: RC1 plus gated P2 work and fixes.

Each RC is a git tag with `release.json`: git sha, image digests, contract versions, calibration lock hash, pins, effective feature flags, and a link to the validation report generated for that sha.

**Go/no-go checklist (G6)**, run by P with I, M and F:
- [ ] `check_flags.py` green: every enabled capability is `accepted`
- [ ] Nightly validation on this sha passed; no stale records for enabled capabilities
- [ ] All pinned links in README, slides and video resolve and render identically on production and on both offline laptops
- [ ] Device matrix: current Chrome, Firefox and Safari; one Android and one iPhone; WebGL disabled
- [ ] Cold and warm performance recorded against the budgets; pre-warm complete
- [ ] Credits and DOIs present; no NASA insignia; licensed images only
- [ ] Health checks, rate limits and job time-outs active (implementation.md §9)
- [ ] Rollback rehearsed: previous RC redeploys in under 5 minutes

**Rollback** is redeploying the previous RC tag. It is the first response to any production problem during the event; diagnosis comes after.

### 12.3 Freezes
Freezes are narrow and late, because the product is built well ahead of them.
- **Contract stability** from RC1 (§7.2).
- **Feature freeze** Sun Nov 15 12:00: only fixes after this, each through a reviewed PR and an RC patch.
- **Data freeze** for the demo: the pins in the final RC. New data can appear on staging but not in the demo views.

### 12.4 New archive data and DR1
Weekly QR3 data is expected, and DR1 may appear during the event (understanding.md §4.1). The response is the same in both cases:
1. D detects it (release watcher, or the Saturday-morning check) and records what changed.
2. On staging only: add the release to `releases.yaml` if needed, compute new candidate pins for the acceptance targets, and diff them against the current pins.
3. Re-run the L3 checks on the candidate pins. For DR1, also re-run F1–F5 and F13 if its calibration differs.
4. Adopt the new data in a release only if every enabled gate still passes, and only through a normal RC. Demo pins never change in place; the UI's "newer data available" notice covers the gap.
5. If WISE 0855's autumn-2026 visit appears (understanding.md §8.4), D and M assess it as a candidate improvement to G3, not as a reason to change a passing release late.

---

## 13. Demo operations

### 13.1 Assets
- Pinned permalinks for the 5 targets (and Pluto if G5.sso passed), in the README, on a printed card, and as bookmarks on both laptops.
- Production URL, pre-warmed.
- Two offline laptops with the final RC and its snapshot.
- The 30 s video and the slides, stored locally and uploaded.
- One page of current numbers, generated from the accepted evidence records.

### 13.2 Script
The demo arc is implementation.md §11.4. Each segment uses only capabilities enabled in the final RC. If a segment's capability was descoped, F replaces the segment with the next one in that script; the arc is never patched with an unvalidated feature.

### 13.3 Rehearsals
- **Rehearsal 1** (Phase D): full script on production; timed; every presenter.
- **Rehearsal 2** (Sat evening): on an offline laptop with Wi-Fi off.
- **Rehearsal 3** (Sun afternoon): on the final RC, with one injected failure from §13.5.
- The target stewards brief the presenters on their target's traps before rehearsal 1, and are present to answer questions.

### 13.4 Pre-flight
| When | Check | Owner |
|---|---|---|
| T−24 h | Final RC on production; pre-warm complete; snapshot copied to both laptops | P |
| T−2 h | Every pinned link opens on production and offline; laptops charged; browsers updated and cache-warmed; notifications off | P, F |
| T−15 min | Production health check; choose live or offline mode based on venue network; video open in a tab | P |

### 13.5 Failure drills

| Failure | Detection | Response |
|---|---|---|
| IRSA slow or down | `/healthz`, or the first pinned link stalls | Pinned views are pre-warmed; if needed, switch to snapshot mode (badge shown) |
| Venue network slow or down | Pre-flight | Present from the offline laptop |
| WebGL fails on the presenting machine | Viewer reports fallback | The PNG viewer takes over automatically; continue |
| Production down | Health check | Roll back to the previous RC; meanwhile present offline |
| Laptop fails | — | Second laptop |
| Everything fails | — | Play the video and walk the slides |

### 13.6 Submission package
Owned by F, with content from everyone: implementation.md §11.5 is the checklist.
- **README:** pitch (F); architecture and how to run (P); validation table generated from `STATUS.md` and the evidence records (D, signed by I and M); limitations stated honestly (I, M); credits (F).
- **Video and slides:** narrative by F; science captions checked by I and M; recordings from the release build only.
- **AI-use disclosure and the account of pre-event work,** as the 2026 rules require (F confirms the wording at the Saturday kickoff).

---

## 14. Risk ownership

The risk register is implementation.md §12. Each risk has an owner who watches for its early signal and acts.

| Risk (implementation.md §12) | Owner | Early signal | First action |
|---|---|---|---|
| IRSA slow, throttling or down | D | Nightly perf probes; 5xx rate in logs | S3 path; pre-warm earlier; snapshot |
| Slow venue network | P | Pre-flight | Offline laptop |
| New data cold-starts views; DR1 mid-event | D | Release watcher | §12.4 |
| Name resolution, epoch confusion | M | G1 tests; nightly live resolver run | Alias table; epoch banner |
| Cutout bandwidth explosion | D | Bytes-per-view metric | Stream-abort; FOV caps |
| WISE 0855 too faint, or too few frames | M (with D as steward) | G4b S/N | Band 5+6 stacks; long-baseline blink; honest labels |
| Saturated targets | I | F7; G2 visual check on Barnard and R Dra | `bright` preset; marked display fill; annulus method |
| False variability from channel mixing | I | G4a null test; §11.2 review | Keep diff off until accepted |
| WebGL bugs on judges' devices | F | Device matrix | PNG fallback |
| Calibration conventions wrong | I and M | F1–F5, F13 | Fix and re-run dependent checks |
| Scope creep | F | Mid-point review; cards outside the plan | §11.1 |
| Deadline confusion | F | — | Complete submission by Sun 19:00 |

---

## 15. Repository additions

These extend the layout in implementation.md §13.

```
CONTRACTS.md                        # changelog of every contract surface (§7)
docs/decisions/NNNN-*.md            # one-page decision records (§1)
validation/
  schema.json                       # evidence-record schema (§4.5)
  STATUS.md                         # generated: foundation checks, gates, capability states
  <check-id>/<date>-<sha>/          # evidence records
backend/spherex/types.py            # boundary types (§7.1)
backend/app/schemas.py              # API schemas (§7.1)
backend/tests/synthetic/            # scene generator and L1 tests (§8.1)
backend/tests/data/real/            # real-file fixtures + provenance (§8.2)
config/features.yaml                # flags and their requirements (§9.6)
config/pins/                        # pinned frame lists (§8.3)
config/calibration.lock             # locked calibration files (§8.4)
frontend/fixtures/golden/           # golden payloads for mock mode and contract tests (§8.5)
scripts/verify/fNN_*.py             # foundation checks (§5)
scripts/validate.py                 # evidence harness (§4.5)
scripts/check_flags.py              # release flag guard (§9.6)
scripts/make_goldens.py             # regenerate golden payloads (§8.5)
.github/CODEOWNERS                  # ownership (§9.3)
.github/pull_request_template.md    # PR checklist (§9.2)
.github/workflows/{ci,nightly,release}.yml
```

---

## 16. Quick reference

| I need to… | Go to |
|---|---|
| Understand a science fact or a target | understanding.md |
| Know how a module should behave | implementation.md §3–§6 |
| Find the exact shape of a payload | `/openapi.json`, `spherex/types.py`, `CONTRACTS.md` |
| Know whether a capability is valid right now | `validation/STATUS.md` |
| Know who owns a file | `.github/CODEOWNERS`, §2.1 |
| Decide whether a shortcut is acceptable | §11.2, §11.3 |
| Prepare or run the demo | §13, implementation.md §11.4 |
| React to new archive data | §12.4 |
