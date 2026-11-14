# Contract changelog (workflow.md §7)

### Role M additive measurement integration — 2026-11-08 (review pending)

`AstroPoint.method` distinguishes individual native frames and joint native visit
positions. `AstrometryResponse.joint_fits` retains contributing frame IDs,
per-frame fluxes, registration nuisances, covariance, chi-square/dof and all
starting solutions; `notes` states conditional errors and the two-epoch dof=0
limitation. Optional/default-empty additions preserve older clients. Spectrum
`templates` carries independently scaled per-visit/release samples and complete
asset provenance; model surface/relative spectra are explicitly labelled.
Generated OpenAPI/TypeScript and frontend consumers land together. No feature
flag or capability promotion follows from these contracts.

## Python boundary types — `backend/spherex/types.py`, `CONTRACT_VERSION`

### 0.1.0 — 2026-11-06 (I; pairs D↔I, I↔M, I↔P must approve)
- New: `FrameRef`, `RawFrame` (D → I), `Calib` protocol (D → I; `channel` = the single CHANNEL_MAP,
  HDU 1, F3), `CalFrame` (I → M: sci, var, bad, bad_phot, lam, dlam, flags, bits, sky, w_frame, wcs,
  origin, detector, mjd, obsid, survey, header, qa, photometric_scale, preset, `flags_near()`), `Grid`,
  `GridFrame`, `TimeBin`, `Stack` (I → P: mean/var/nhits/flag_or/rej, frame_ids, **skipped with
  reasons**, display/filled for P1-7, transients), `Cube` (I → P, M), `Diff` (I → P, with
  annotations), `PSFModel` protocol (M → I, bright-target display fill).
- Constructed from the real QR3 fixture in `tests/real/test_real_flags.py::test_real_calframe_contract_from_fixture`.
- Consumers to update when they land: D's FrameSources must return `RawFrame` with `origin`; M's
  `spectrum_point` reads `CalFrame` fields (`lam`, `dlam`, `bad_phot`, `flags_near`, `origin`, `wcs`).


### 0.1.0 consumers landed — 2026-11-07 (D; pairs D↔I, D↔M, D↔P)
- No type change. D's FrameSources (`spherex/access/fitsstream.py` IRSA cutout, `s3sections.py` S3 section,
  `fixture.py` committed fixtures, `failover.py` wrapper) return `RawFrame` with `origin` set by the source.
  `hdus` holds IMAGE, FLAGS, VARIANCE, ZODI **plus PRIMARY** (header only; `VERSION` lives there). FLAGS is
  always int64 (decoded from RICE_1 in QR3 full files, plain in QR2 full files and in cutouts).
  `release` = registry id of the frame's collection. S3 section headers have NAXISn and every CRPIXn<alt>
  shifted, so `calib.parent_origin(header) == origin` for both sources (F2).
- `Calib` is implemented by `calib.Calib` (locked, sha256-verified files, lazy per detector) and
  `calib.SlicedCalib` (fixtures). `fluxcorr[d]` is the raw `l3_flux_corrections` IMAGE HDU (multiply vs
  divide is F4, M). Additive: `Calib.solid_angle[d]` (solid_angle_pixel_map IMAGE HDU, F13, M).
- D↔I contract test: `tests/real/test_real_access.py::test_d_to_i_contract_both_sources_calibrate_identically`.

## FrameSource interface — `backend/spherex/access/frames.py` (D; consumers P, I)
- 0.1.0 — 2026-11-07 (D proposes; pairs D↔P, D↔I): `FrameSource.fetch(ref: FrameRef, box: FrameBox) ->
  RawFrame`, raising `FrameUnavailable` (box off the frame, HTTP 4xx; no failover count) or `SourceFailure`
  (after retries; counts toward failover). `FrameBox(ra, dec, size_deg)`, sized with `cutout_size_deg(fov)`,
  or snapped with `snap_box`. `fetch_frames(...) -> [FetchOutcome]`: band first, and every frame either
  fetched or `skipped_reason` (for the manifest's skipped list). Sources: `IrsaCutoutSource`,
  `S3SectionSource` (`bounds="irsa"` = IRSA's box + 1 px, a superset), `FixtureSource`, `FailoverSource`
  (3 consecutive failures → switch; re-probe after 300 s), `CachedSource`.

## Pins — `config/pins/<pin>.json`, `backend/spherex/access/pins.py` (D; consumers P, F)
- `parallax-pin@1` — 2026-11-07 (D; pairs D↔P): `pin = sha256("\n".join(sorted(frame access URLs)))[:12]`
  (`frame_list_digest`; P's view key must hash F the same way). Fields: `pin`, `params`, `counts`, `mjd_range`,
  `provenance`, `frames[]` {access_url, s3_key, collection, obs_id, detector, t_min, release, file_version,
  proc_date, psffix, retry}. `config/pins/index.json`: target → {pin, params, counts, candidates[]}. Pins are
  immutable. New data adds `candidates`, which are adopted only by moving `pin` in an RC PR (docs/data-refresh.md).

## Config files (D)
- `config/releases.yaml` — validated by `access/releases.py::parse` (unique ids, collections, priorities;
  `never_use` refused; `include_deep: auto|always|never`). Code never writes it.
- `config/calibration.lock` — `parallax-calibration-lock@1` (`calib.CalibrationLock`): `files[]` {product,
  detector, s3_key, version_dir, size, etag_md5, sha256}, `lock_hash` (cite in evidence records), `complete`.
  2026-11-07: 25 files, `lock_hash 94e18b883fdc9b28`, complete.
- Release state (runtime, not committed): `access/watcher.py::ReleaseState` JSON; its `token()` invalidates
  coverage caches.

## Binary payloads (`backend/spherex/render.py`)
- `f16le-row0south-nodata-65504@1` (`to_f16`): display stacks and cubes, as implementation.md §5.2.
- `f32le-row0south-nodata-nan@1` (`to_f32`): `.f32`, `.var.f32`.
- `u32le-row0south-flags-canonical@1` (`to_u32_flags`): `.flags.u32`; bit meanings are
  `flags.CANONICAL_BITS` (understanding.md §4.4 plus PHANTOM = 4, REFERENCE = 5 from QR2 headers),
  re-packed per frame from its own header layout.
- Golden: `frontend/fixtures/golden/stack_F_121x121.f16` + `.json` (encoder test:
  `tests/unit/test_render.py::test_golden_F_contract_file_and_orientation`; the TypeScript decoder test is F's).

## HTTP API — `frontend/src/api/types.ts` (provisional), `API_SCHEMA_VERSION`

### 0.1.0 — 2026-11-07 (F proposes; pair P↔F must approve, workflow.md §2.4)
- Hand-written from implementation.md §5 and `spherex/types.py` 0.1.0 until P's `app/schemas.py` →
  `/openapi.json` → generated `types.ts` lands; then the generated file replaces it and keeps these names.
- `ViewManifest`: `schema_version`, `key`, `pin`, `newer_pin`, `params`, `target` (`ResolveResult`), `grid`
  (TAN `crval`/`crpix` 1-based/`cdelt`, `shape` [ny, nx], row 0 = south), `axis`, `bands`,
  `bins[band]` = `TimeBinInfo` (= `TimeBin` without `idx`, plus `n_frames`), `stacks[]` (`StackInfo`:
  `ready`, `format`, `skipped` (id, reason), `frame_ids`, `filled`), **`limits[band]` = shared stretch from
  the median stack** (never per frame), `frames[]` (QA, release, skipped reason), **`track[]`** = M's
  `pos(t)` at each (bin, band) mid-epoch, `flags` {`bits` = `flags.CANONICAL_BITS`, `info` = `FLAG_INFO`,
  `format`}, `formats`, `release`, `warnings[]`, `data_source` (`live` | `snapshot` | `mock`).
- `POST /views` → `{status: "ready", manifest}` or `{status: "queued", job_id, key}` (202). The manifest is
  readable from `planned` on, with `stacks[].ready` false until `stack_ready`; it is refetched on `done`.
- SSE `/jobs/{id}/events`: event name = `type`; data = JSON of the other fields (`planned{n}`,
  `fetched{i,n}`, `stack_ready{bin,band}`, `diff_ready{a,b,band}`, `warning{code,message}`, `done{key}`,
  `error{message}`). Unnamed events with `type` inside the payload are also accepted.
- `GET /views/{key}/diff?a=&b=&band=` returns **JSON** `DiffInfo` (`k`, `clip_sigma`, `annotations`,
  `validity`, `format`) **plus `url`** of the `.f16` significance map (§5.1 left the split open).
- `GET /views/{key}/png/{bin}/{band}.png?stretch=&lim=manual:lo,hi&cmap=`: the client always sends the
  manifest's shared limits as `manual:`; PNG rows are top = north (standard image order).
- `GET /releases` adds **`features`** (effective flag levels, workflow.md §9.6), `environment`, `snapshot`,
  `api_version`. A capability missing from `features` is OFF in the UI.
- `/resolve` adds `epoch_hint` {object, epoch, sep_arcsec, now_ra, now_dec, moved_arcmin, direction} and
  `label_hint` (implementation.md §4.1 epoch guard; numbers shown verbatim in the banner).
- Error bodies: `{detail: string}` (FastAPI default), shown to the user as is.

### 0.1.0 approved with amendments — 2026-11-07 (P; pair P↔F)
- **Authority moves to `backend/app/schemas.py`** → `/openapi.json` (committed at `frontend/src/api/openapi.json`)
  → `frontend/src/api/generated.ts` (`scripts/gen_contracts.py`; CI fails if either is stale). F's hand-written
  `types.ts` keeps its names; `tests/app/test_contract.py` fails if it declares a field the schemas lack.
  Switching imports to `generated.ts` is F's call.
- Every name and field above is implemented as written. Additive amendments: `ReleasesResponse.features`
  values are `off|dev|staging|on`; `environment` adds `mock`; `Health` (`/healthz`: `ok`, `mode`
  live|snapshot|mock|fixture, `environment`, `api_version`, `git_sha`, `calibration`, `probes[]`);
  `CandidateRequest`/`CandidateResponse`/`CandidateGallery` (implementation.md §8; note ≤ 1000 chars, plain text);
  `FramesResponse`, `MoversResponse`, `SsoResponse`, `OverlayResponse` for the remaining §5.1 routes.
- Every model is `extra="forbid"`; responses are validated against `/openapi.json` in mock and fixture-backed
  mode (CI "Contract") and against staging nightly (`scripts/contract_probe.py`).
- Status codes: 404 = capability off in this environment (`config/features.yaml`) or unknown view/pin;
  501 = capability whose upstream module is missing, with the owner named in `detail`; 409 = view cannot be
  planned (no coverage); 429 = per-IP rate limit; 400 = invalid view parameters.
- Additive only from RC1 (workflow.md §7.2).

### 0.1.0 additive — 2026-11-08 (integration pass; pairs I↔P and P↔F must approve)
- `GET /views/{key}/frames?band=&sort=lambda|time` now answers (was 501 naming I). `FramesResponse` unchanged:
  `label` is `cube.SPECTRAL_LABEL` for `sort=lambda`, a "time order mixes wavelength" label for `sort=time`;
  `frames[].lam_um` is the reprojected CWAVE at the target's grid pixel for that frame (`targets.pos(t)`);
  `sort=lambda` omits frames whose λ is unknown instead of placing them by guess. ≤ 64 frames (`cube.flipbook_order`).
- **New** `GET /views/{key}/frames/{band}/{digest}.f16`: one gridded exposure (same format and grid as stacks;
  `digest` = first 16 hex of sha256(frame id)). Flag `flip`.
- **New** `GET /views/{key}/rgb/{bin}/{methane|ice}.f16`: λ-range RGB preset, (3, ny, nx) f16 in R, G, B order,
  each plane `cube.lambda_slice` over the per-pixel measured λ of every band covering the preset range
  (`cube.RGB_PRESETS`). Flag `rgb`; 409 without calibration. Band-triplet composites (`rgb:a,b,c`, `rgb:thermal`)
  are composed in the browser from the existing stacks with each band's shared limits.
- Store layout adds `views/<key>/frames/<band>/` and `views/<key>/rgb/<bin>/` (snapshots copy them unchanged).
- **New** `GET /views/{key}/blink25` → `Blink25Response` {`label` (= `render.BLINK25_LABEL`), `format`, `grid` (its
  own `GridInfo`: centred between the archival and current positions, ≥ 1.5 × the jump), `view_fov_arcmin`,
  `fov_needed_arcmin`, `view_fov_for_full_coverage_arcmin`, `expected_jumps_arcmin`, `twomass_match`, `pos_source`,
  `epochs[]` {`label`, `year`, `date`, `pairs_with_band`, `n_images`, `ra`, `dec` (= pos(t) at that epoch), `url`
  (null when unavailable), `note`}}, and `GET /views/{key}/blink25/{i}.f16` (values in units of each epoch's own
  sky σ). Flag `blink25`; 409 offline or for targets without proper motion; 502 when the archive search fails.

## URL schema — `frontend/src/state/url.ts` (additive only)
- 2026-11-07 (F): implementation.md §5.3 as written, plus `t` (current bin id), `ui`
  (simple|explorer|expert), `mode=onion`, `ov` values `track` and `crosshair`. Aliases kept forever:
  `band→bands`, `target|name→q`, `overlays→ov`, `release→rel`, `speed→fps`; mode values `sidebyside`,
  `flipbook`, `difference`, `onionskin`. Canonical form: fixed key order, defaults omitted. CI fixtures:
  `frontend/fixtures/urls/demo-links.txt`. Debug-only `gl=0` (force the PNG viewer) is not part of the schema.

## Embed messages — `frontend/src/components/EmbedApp.tsx`
- 2026-11-07 (F): host → embed `parallax:goto{ra,dec}`, `parallax:target{q}`, `parallax:band{band}`,
  `parallax:play{playing}`; anything else is ignored. Embed → host `parallax:state{search, bin}`.

## Colormaps — `frontend/src/gl/colormaps.ts` → `frontend/fixtures/colormaps.json`
- `rgba8-256@1` (F, 2026-11-07): gray, magma, cividis, diverging LUTs; index = round(t·255); no-data RGB
  (46, 26, 56). P's PNG renderer should load this file so both viewers show identical colours.

## Feature flags — `config/features.yaml` (P; consumers F, everyone)
- `parallax-features@1` — 2026-11-07 (P): `flags.<capability>: {level: off|dev|staging|on, capability, requires:
  [F…/G…], note?, core?}`. Names match `frontend/src/lib/features.ts` CAPABILITIES; `core: true` marks the P0
  product, which the UI always shows (the API still gates it). The effective level per environment is served in
  `/releases.features`. `scripts/check_flags.py` (CI) refuses `on` without accepted requirements and enforces
  workflow.md §11.2.

## Evidence records — `validation/schema.json`, `validation/registry.yaml` (P; consumers everyone)
- `parallax-evidence@1` — 2026-11-07 (P): the §4.5 fields plus `code_digest` (sha256 of `code_paths` contents,
  exact staleness even on a dirty tree), `environment`, `threshold_changes`, `supersedes`. Written by
  `scripts/validate.py:record` (`scripts/verify/_evidence.py` delegates; call signature unchanged).
  `parallax-evidence@0-temporary` stays readable; its staleness falls back to git history.
- Reviews: `review.json` beside `record.json` (`parallax-review@1`: role, verdict approve|changes, reproduced,
  notes, code digest at review). The author cannot review; the registry names the reviewer role (§9.4).
- `registry.yaml` (`parallax-registry@1`): checks (kind, owner, level, reviewer, script) and gates (requires,
  criteria, sign-off). `validation/STATUS.md` is generated from records + registry.

## Snapshot — `<SNAPSHOT_DIR>/index.json` (P; consumers P's API, offline laptops)
- `parallax-snapshot@1` — 2026-11-07 (P): ViewStore layout (`views/<key>/…`, identical to the live cache) plus
  `index.json` {`views`: canonical request → key, `pins`: pin → key, `keys`, `content_sha256`, `created`} and the
  cache's `release_state.json`. Written by `scripts/make_snapshot.py`.

## Release manifest — `release/<RC>/release.json` (P)
- `parallax-release@1` — 2026-11-07 (P): `rc`, `git_sha`, `git_dirty`, `image_digests`, `contract_versions`,
  `calibration_lock`, `pins`, `features_production`, `validation` {`status_sha256`, `report`}, `demo_views`
  (workflow.md §12.2). Written by `scripts/make_release.py`.

## Demo views — `config/demo_views.yaml` (P; consumers prewarm, perf probe, snapshot)
- `parallax-demo-views@1` — 2026-11-07 (P): `views[]: {name, body}` where `body` is a `POST /views` body with a pin.


## Measurement amendments - 2026-11-08 (M with P/F integration)

HTTP 0.1.0 remains additive. Science routes now call `app.measurement`, and missing
locked calibration/insufficient native data return 409. Optional `key` on spectrum,
astrometry and lightcurve preserves a view's immutable frame list. Lightcurve adds
`release=qr2|qr3`; mixed-release aggregation is refused until F4. `plx_fixed` is **mas**
on HTTP, and arcsec inside the pure fit functions. Motion points are in the returned
`tangent_origin`, not necessarily relative to the first visit. Points include native
frame IDs, sky covariance and full-visit fit inclusion. Responses retain `skipped`,
`native_frames`, scales and pin; spectral quality separates statistical and 3% calibration
errors. Exact fields remain in schemas.py and regenerated OpenAPI/TypeScript.

Raw stack/display routes accept `?raw=1` for f16/PNG encoded from immutable science f32;
filled display pixels carry a separate outline mask. SSO overlays refine SkyBoT IDs
with exact Horizons/SPHEREx positions and report failed refinements. `/movers` accepts
`mode=planetx` behind its own off flag and requires per-day bins plus FOV >=30 arcmin.
Implementation availability never promotes a capability or changes evidence levels.
# Role M light-curve uncertainty amendment (2026-11-08)

SpectrumResponse adds `templates` with separately scaled visit/release observed
template samples, provenance and an approximate-response warning. No missing
template coverage is filled. AstroPoint adds optional `native_xy`, `flux_snr`
and `rchi2`; registration entries retain local offsets, errors and reference
Gaia identifiers for audit. WISE motion uses D6-only wider-field registration;
display view geometry remains immutable.

LightCurveResponse adds `covariance`, `covariance_order` (detector/bin pairs),
`reference_spectrum`, and `uncertainty`. `Periodogram.fap` is nullable: a missing
calibrated false-alarm probability must be displayed as unavailable. Clients
must not turn null into zero. Shared-reference covariance includes numerator /
reference dependence; see decision 0005 for conditional uncertainty limits.

## Audit amendments - 2026-11-08 (improvements.md; additive, HTTP 0.1.0 unchanged)

- `ViewManifest.target.epoch_hint` / `label_hint` are now filled for coordinate input (the epoch guard runs in
  view planning, not only in `/resolve`). Display only; not part of the view key.
- `StackInfo.transients` (optional, default `[]`): per-exposure transients on empty sky with grid and sky
  positions, ≤ 200 per stack. Asteroid candidates before vetting (P2-5); drawn with the `ov=sso` layer.
- `MoversResponse.tracked` (optional, default `[]`): Planet X shift-and-stack detections per distance hypothesis.
- URL schema: `bands=rgb:pah` is no longer accepted (it never had a producer). Old links fall back to the default band.
- Feature flags: built-but-unaccepted capabilities moved from `off` to `dev` (visible on a local machine with the
  "unvalidated" badge). Nothing is `on`.
- Derived products (diff, flipbook, RGB, cube, 25-year blink) and view-bound science results (`?key=`) are cached
  with the view and read from the snapshot when offline.

## Cross-release difference - 2026-11-09 (decision record 0008; additive, HTTP 0.1.0 unchanged; pairs I↔P and P↔F)

- `DiffInfo.photometric_match` (optional, `null` when absent): `applied`, `cross_release`, `scales_a`, `scales_b`,
  `method`, `note`; when a fit exists, also `scale`, `scale_err`, `offset`, `offset_err`, `n_sources`, `n_pix`,
  `residual_scale`, `tau`, `q_flat`, `dof_flat`, `static_z_before`, `static_z_after` and `bins[]` (`lam`, `scale`,
  `err`, `raw`, `raw_err`, `shrink`, `offset`, `n_pix`, `n_sources`, `pooled`). B·scale + offset ≈ A.
- `DiffAnnotation.sign` is `null` on a cross-release pair: a monopole there is a residual, not a brightness change.
- `/views/{key}/diff` on a mixed QR2/QR3 pair now returns 200 with the match applied, or 409 with the reason the match
  could not be made (never the raw difference).
- `spherex.types.Diff.photometric_match` (optional dict, default `None`): the I → P report behind the field above.
- `worker.diff_task(…, exclude_xy=None)` (optional): positions excluded from the match (target in both visits).

## Audit fixes - 2026-11-10 (audit/09-implementation-status.md; pair P↔F must approve)

- **Not additive:** `/spectrum`, `/astrometry` and `/lightcurve` now require `key` (400 without it). The bundled frontend
  always sends it; the unbound form planned and fetched a whole 12′ view per request (audit K-40).
- Status codes: **503** when an archive or catalogue service fails (`{detail}` says which kind; was a bare 500); **400**
  for a key, bin id or payload name that cannot name a store path (was 500); **409** when `pin` belongs to another field;
  **404** for an unknown name, with a sentence (was 500); **429** also for lookups (60/min) and measurements (20/min).
- `POST /views` for a view already being built answers 202 with that job and never counts against the job limit.
- Solar System targets are planned with `center=track` automatically, with an `sso_track` manifest warning.
- `pin`: committed pins in `config/pins/`, then runtime pins of views built on the server (`<CACHE_DIR>/pins/`, same
  `parallax-pin@1` format). The manifest's `pin` of any un-pinned view is therefore a working share link.
- View keys include `pv` (`viewkey.PIPELINE_VERSION`) and `cal` (calibration identity): cached views from older code are
  rebuilt, not served. `axis=bin:<N>d` needs 1 ≤ N ≤ 365; `fov` ≤ 30 by default (`MAX_FOV_ARCMIN`).
- `CandidateRequest.view_key` max length 64 (the store's limit). Manifest `release` is filled when the manifest is read.
- **507** from `POST /views` when the cache disk has under 1 GiB free (a new build would fail half-way); built and
  pinned views still open. `CACHE_MAX_GB` sets an LRU budget for frames and views (`app/cachegc.py`).
- SSE unchanged on the wire; clients must ignore `error` events that carry no data (EventSource's own) and close the
  stream after a job `error`.
