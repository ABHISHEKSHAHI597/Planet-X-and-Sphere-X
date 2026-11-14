/**
 * HTTP contract between the API (P) and the frontend (F), workflow.md §2.4 / §7.1.
 *
 * PROVISIONAL (v0.x). workflow.md §1 makes `backend/app/schemas.py → /openapi.json → this file
 * (generated)` the authority. Until P's schemas land, this file is hand-written from:
 *   - implementation.md §5.1 (endpoints), §5.2 (payloads), §5.3 (URL schema), §4.2 (time model);
 *   - backend/spherex/types.py v0.1.0 (TimeBin, Stack, Diff), render.py (FORMAT_* ids),
 *     flags.py (CANONICAL_BITS, FLAG_INFO).
 * Every field P renames must be renamed here in the same PR (CONTRACTS.md, "HTTP API").
 * When P's generator lands, this file is replaced by the generated one and the tests in
 * tests/contract.test.ts keep guarding the shapes the UI relies on.
 */

export const API_SCHEMA_VERSION = "0.1.0";

/* ----------------------------- /resolve ----------------------------- */

export type TargetKind = "star" | "sso" | "coords";

export interface EpochHint {
  /** Name of the high-PM object whose track passes closest to the typed coordinates. */
  object: string;
  /** Decimal year at which the typed coordinate matches the object (epoch_of_match, §4.1). */
  epoch: number;
  /** Separation between the typed coordinate and the object's track at that epoch (arcsec). */
  sep_arcsec: number;
  /** Where the object is now (deg) and how far it has moved from the typed position. */
  now_ra: number;
  now_dec: number;
  moved_arcmin: number;
  /** Compass direction of the motion from the typed position to now, e.g. "west". */
  direction: string;
}

export interface ResolveResult {
  query: string;
  kind: TargetKind;
  name: string;                 // display name (main id or the coordinate string)
  main_id?: string;             // SIMBAD main id when known
  ra: number;                   // deg, at `epoch`
  dec: number;
  epoch: number;                // decimal year of ra/dec (catalogue epoch)
  pm?: [number, number] | null; // pmra*, pmdec (mas/yr)
  plx?: number | null;          // mas
  rv?: number | null;           // km/s
  otype?: string | null;
  spt?: string | null;
  astrometry_source?: string | null;
  /** pos(now) as seen by SPHEREx (deg). The view centres on this, not on ra/dec. */
  propagated_now: { ra: number; dec: number; epoch: number };
  /** Present when typed coordinates match a high-PM object at another epoch (P0-1). */
  epoch_hint?: EpochHint | null;
  /** e.g. "Barnard's Star (2026 position)" when the typed coordinates are its current position. */
  label_hint?: string | null;
}

/* ----------------------------- /coverage ---------------------------- */

export interface CoverageVisit {
  id: string;
  status: BinStatus;
  mjd_min: number;
  mjd_max: number;
  surveys: (number | null)[];
  frames_per_band: Record<string, number>;
  releases: string[];
}

export interface Coverage {
  ra: number;
  dec: number;
  fov: number;
  n_frames: number;
  axis: string;
  visits: CoverageVisit[];
  releases: string[];
  freshness: ReleaseState;
}

/* ----------------------------- /releases ---------------------------- */

export type FlagLevel = "off" | "dev" | "staging" | "on";

export interface ReleaseState {
  /** e.g. { qr3: "2026W40_2A", qr2: "…" }: newest planning period ingested per release. */
  release_state: Record<string, string>;
  newest_period: string;
  checked_at: string;           // ISO time of the last watcher run
}

export interface ReleasesResponse extends ReleaseState {
  /** Effective feature flags for this deployment (workflow.md §9.6). The UI never enables a
   *  capability the backend has not enabled. "staging" shows an "unvalidated" badge. */
  features: Record<string, FlagLevel>;
  environment: "local" | "staging" | "production" | "snapshot" | "mock";
  /** true when the API serves pre-computed demo data (implementation.md §9 snapshot mode). */
  snapshot: boolean;
  api_version: string;
}

/* ------------------------------- /views ----------------------------- */

/** Mirrors spherex.types.Status. */
export type BinStatus = "full" | "partial" | "bin" | "survey" | "exposure";

/** One entry of the time axis for one band (spherex.types.TimeBin without `idx`). */
export interface TimeBinInfo {
  id: string;                   // V1, V2… (same dates in every band), B0…, S1…, E0…
  band: number;
  status: BinStatus;
  mjd_mean: number;
  mjd_min: number;
  mjd_max: number;
  surveys: (number | null)[];   // null = IOC (commissioning)
  label: string;                // e.g. "V2 · 2026-03-11→04-10 · S1 · 113 frames" (from I's epochs.label)
  n_frames: number;             // frames of this bin in this band
  n_visit_frames: number;       // frames of this visit in all bands
}

export interface StackInfo {
  bin: string;
  band: number;
  ready: boolean;
  format: string;               // e.g. "f16le-row0south-nodata-65504@1"
  nhits_max: number;
  /** P1-7: display stack has model-filled cores; `filled_url` returns their mask. Never measured. */
  filled: boolean;
  /** (frame id, reason) — never dropped silently (workflow.md §11.2). */
  skipped: [string, string][];
  frame_ids: string[];
  /** Per-exposure transients on empty sky (asteroid candidates before vetting, P2-5). */
  transients?: { frame: string; x: number; y: number; ra: number; dec: number; npix: number }[];
}

export interface FrameMeta {
  id: string;
  band: number;
  detector: number;
  bin: string;
  mjd: number;
  survey: number | null;
  obsid: string;
  release: string;
  collection: string;
  pipeline: string;
  qa: { L1DQAFLG?: string; L2DQAFLG?: string; FINAST?: number; [k: string]: unknown };
  /** null when the frame is in the stack; otherwise why it was skipped. */
  skipped: string | null;
}

export interface GridInfo {
  /** TAN projection, FITS 1-based CRPIX. cdelt[0] < 0 (east left), cdelt[1] > 0 (north up). */
  ctype: [string, string];
  crval: [number, number];
  crpix: [number, number];
  cdelt: [number, number];
  shape: [number, number];      // [ny, nx]; row 0 = south edge
  pix_arcsec: number;
  native: boolean;              // false = upsampled, display only (implementation.md §4.4)
}

export interface TrackPoint {
  bin: string;
  band: number;
  mjd: number;
  ra: number;
  dec: number;
}

export interface ViewWarning {
  code: string;                 // e.g. "frames_skipped", "partial_only", "qr_mix", "bright_fill"
  message: string;
  severity: "info" | "warn";
}

export interface ViewManifest {
  schema_version: string;
  key: string;
  /** 12 hex of sha256(frame list): freezes the frame list (implementation.md §2.3). */
  pin: string;
  /** For pinned views: a newer frame list exists for these params (→ "newer data available"). */
  newer_pin?: string | null;
  params: Record<string, string>; // canonical view params (§5.3)
  target: ResolveResult | null;
  grid: GridInfo;
  axis: string;                 // "visit" | "bin:14d" | "survey" | "exposure"
  bands: number[];
  bins: Record<string, TimeBinInfo[]>;  // key: band ("1".."6")
  stacks: StackInfo[];
  /** Shared stretch per band, from the median stack (understanding.md §5.4). Never per frame. */
  limits: Record<string, { lo: number; hi: number; lim: string }>;
  frames: FrameMeta[];
  /** Predicted track pos(t) at each (bin, band) mid-epoch, PM + parallax (M's targets.pos). */
  track: TrackPoint[];
  flags: { bits: Record<string, number>; info: Record<string, string>; format: string };
  formats: { stack: string; science: string; flags: string };
  release: ReleaseState;
  warnings: ViewWarning[];
  /** Source of the data: "live", "snapshot" (cached demo data) or "mock" (never in a demo). */
  data_source: "live" | "snapshot" | "mock";
}

export type ViewsResponse =
  | { status: "ready"; manifest: ViewManifest }
  | { status: "queued"; job_id: string; key: string };

/** SSE events from /jobs/{id}/events (implementation.md §5.1). */
export type JobEvent =
  | { type: "planned"; n: number }
  | { type: "fetched"; i: number; n: number }
  | { type: "stack_ready"; bin: string; band: number }
  | { type: "diff_ready"; a: string; b: string; band: number }
  | { type: "warning"; code: string; message: string }
  | { type: "done"; key: string }
  | { type: "error"; message: string };

/* ------------------------------- /diff ------------------------------ */

export interface DiffAnnotation {
  kind: "dipole" | "monopole";
  /** Sky position(s); for a dipole, from = the − lobe (old), to = the + lobe (new). */
  ra: number;
  dec: number;
  to_ra?: number;
  to_dec?: number;
  shift_px?: number;
  shift_arcsec?: number;
  pa_deg?: number;
  /** Absent across releases before F4: a monopole is then a residual, not a brightness change. */
  sign?: "brightened" | "faded" | null;
  agrees_with_track?: boolean;
  label: string;
}

/** One λ bin of the in-situ match: B·scale + offset ≈ A (decision record 0008). */
export interface PhotometricMatchBin {
  lam?: number | null;          // µm
  scale: number;
  err: number;
  raw?: number | null;          // the bin's own fit before shrinkage toward the broadband scale
  raw_err?: number | null;
  shrink: number;               // weight on the broadband scale (1 = fully pooled)
  offset: number;
  n_pix: number;
  n_sources: number;
  pooled: boolean;
}

/** How visit B was put on visit A's photometric scale (workflow.md §11.2, decision record 0008).
 *  applied=false: same release, numbers are a calibration check only. cross_release=true: positions and
 *  motions are valid; brightness changes are not interpreted until F4 is resolved. */
export interface PhotometricMatch {
  applied: boolean;
  cross_release: boolean;
  scales_a: string[];
  scales_b: string[];
  method: string;
  note: string;
  scale?: number | null;
  scale_err?: number | null;
  offset?: number | null;
  offset_err?: number | null;
  n_sources?: number | null;
  n_pix?: number | null;
  residual_scale?: number | null;
  tau?: number | null;
  q_flat?: number | null;
  dof_flat?: number | null;
  static_z_before?: number | null;
  static_z_after?: number | null;
  bins?: PhotometricMatchBin[];
}

export interface DiffInfo {
  a: string;
  b: string;
  band: number;
  format: string;
  k: number;                    // significance renormalisation factor (QA)
  clip_sigma: number;           // display clip, ±5σ (implementation.md §4.6)
  annotations: DiffAnnotation[];
  validity: "accepted" | "unvalidated";
  photometric_match?: PhotometricMatch | null;
}

/* ---------------------------- /spectrum ----------------------------- */

export interface SpectrumRow {
  lam: number;                  // µm
  dlam: number;                 // µm (x error)
  flux: number;                 // µJy
  err: number;                  // µJy (3% floor included)
  mjd: number;
  visit: string;
  detector: number;
  flags: string[];
  rchi2: number;
  /** Hidden by default but counted: He 1.083 µm contamination or flagged pixels (G4b). */
  contaminated: boolean;
  release: string;
}

export interface SpectrumResponse {
  templates?: {name: string; spectral_type: string; visit: string; release: string; label: string; chi2: number; dof: number; provenance?: {url: string; reference?: string; note?: string}; samples: {lam: number; flux: number}[]}[];
  ra: number;
  dec: number;
  rows: SpectrumRow[];
  indices?: { methane_rel?: number | null; w1w2_syn?: number | null } | null;
  validity: "accepted" | "unvalidated";
  notes: string[];
  photometric_scales?: string[];
  skipped?: string[][];
  pin?: string | null;
  indices_by_visit?: Record<string, Record<string, unknown>>;
}

/* --------------------------- /astrometry ---------------------------- */

export interface AstrometryResponse {
  name: string;
  points: { visit: string; mjd: number; xi: number; eta: number; s_xi: number; s_eta: number; band: number; method?: string; fit_included?: boolean }[];
  fit: {
    pmra: number; pmdec: number; e_pmra: number; e_pmdec: number;
    mu: number; e_mu: number; pa_deg: number;
    plx_fixed: number | null; chi2: number; dof: number; delta_chi2: number;
  } | null;
  catalogue: { source: string; mu: number; pa_deg: number; pmra: number; pmdec: number } | null;
  validity: "accepted" | "unvalidated";
  tangent_origin?: number[] | null;
  pin?: string | null;
  skipped?: string[][];
  registration?: Record<string, unknown>[];
  joint_fits?: Record<string, unknown>[];
  notes?: string[];
}

/* --------------------------- /lightcurve ---------------------------- */

export interface LightCurveResponse {
  covariance?: number[][];
  covariance_order?: string[][];
  reference_spectrum?: Record<string, unknown>[];
  uncertainty?: string;
  bands: Record<string, { mjd: number; rel: number; err: number; bin: string }[]>;
  periodogram?: { period_days: number[]; power: number[]; best_days: number; fap: number | null; method?: string; fap_trials?: number | null; fap_resolution?: number | null } | null;
  method: "psf" | "annulus";
  label: string;                // e.g. "relative, qualitative" for annulus ratios
  validity: "accepted" | "unvalidated";
  skipped?: string[][];
  photometric_scales?: string[];
}

/* ---------------------------- /overlays ----------------------------- */

export interface OverlaySource {
  id: string;
  ra: number;                   // propagated to the requested epoch server-side (§6.6), unless `epoch` is set
  dec: number;
  label?: string;
  mag?: number | null;
}

export interface OverlayResponse {
  catalogue: "gaia" | "catwise" | "allwise" | "simbad" | "sso";
  mjd: number;
  sources: OverlaySource[];
  /** Set when positions are as catalogued at this decimal year, NOT moved to `mjd` (the AllWISE layer). */
  epoch?: number | null;
}

/* --------------------------- /candidates ---------------------------- */

export type CandidateKind = "mover" | "variable" | "transient" | "artifact" | "other";

export interface CandidateRequest {
  ra: number;
  dec: number;
  view_key: string;
  pin: string;
  visits: string[];
  kind: CandidateKind;
  note: string;                 // ≤ 1000 chars, rendered as plain text only (implementation.md §8)
}

export interface CandidateResponse {
  id: string;
  auto_checks: { name: string; passed: boolean | null; detail: string }[];
}
