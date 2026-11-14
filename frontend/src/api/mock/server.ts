/**
 * In-browser MOCK API (VITE_MOCK=1; workflow.md §8.5). Answers every endpoint the frontend uses with
 * the shapes in ../types.ts, realistic delays and SSE-like progress (selected band first, §2.3), so F
 * can build and test without P's backend. Manifests say data_source: "mock" and the UI shows a MOCK
 * badge. It must never be used in a demo (workflow.md §8.5).
 *
 * When P's real mock mode (MOCK=1 on the backend, golden manifests from scripts/make_goldens.py)
 * lands, this transport stays useful for offline frontend tests only.
 */
import type {
  AstrometryResponse, Coverage, DiffInfo, FrameMeta, JobEvent, LightCurveResponse, OverlayResponse, ReleasesResponse,
  ResolveResult, SpectrumResponse, StackInfo, TimeBinInfo, TrackPoint, ViewManifest, ViewWarning,
} from "../types";
import { API_SCHEMA_VERSION } from "../types";
import type { EventStreamLike, Transport } from "../client";
import { FORMAT_F16, FORMAT_F32, FORMAT_U32_FLAGS } from "../formats";
import { CANONICAL_BITS, FLAG_INFO } from "../../content/flags";
import { BANDS } from "../../lib/constants";
import { floatToHalf, NODATA_BITS } from "../../lib/half";
import { parseCoordinates } from "../../lib/coords";
import { parseStretch, renderRGBA } from "../../lib/stretch";
import { mjdToDecimalYear, mjdToISODate } from "../../lib/time";
import { pixelToSky, positionAngle, sepArcsec, skyToPixel } from "../../lib/wcs";
import { fieldStars, hashString, makeGrid, mockLimits, mulberry32, sceneStack, type SceneStack } from "./scene";
import { findTarget, mjdOf, propagateLinear, TARGETS, type MockTarget } from "./targets";
import { CHALLENGE, MISSIONS } from "../../content/missions";

/** Pins the mock knows, like the server: the committed demo pins, then every frame list it has built (runtime pins).
 *  An unknown pin answers 404, as the real API does, so the Share dialog's links are tested honestly (audit B-05). */
const COMMITTED_PINS = new Set<string>([...MISSIONS.map((m) => m.pin).filter((x): x is string => !!x), CHALLENGE.pin]);
const knownPins = new Set<string>(COMMITTED_PINS);
import goldenUrl from "../../../fixtures/golden/stack_F_121x121.f16?url";

const NOW_YEAR = 2026.85;
const RELEASE_STATE = { qr3: "2026W40_2A" };

/** Mock flag levels: what the frontend can exercise. "dev" = visible with an "unvalidated" badge. */
export const MOCK_FEATURES: ReleasesResponse["features"] = {
  diff: "dev", spectrum: "dev", astrometry: "dev", track: "dev", aladin: "dev", overlays: "dev", wise_layer: "dev", embed: "dev",
  freshness: "dev", bright_fill: "off", blink25: "dev", flip: "dev", scrubber: "dev", rgb: "dev", lightcurve: "dev",
  movers: "off", export: "dev", candidates: "dev", sso: "dev",
};

interface MockView {
  key: string;
  manifest: ViewManifest;
  target: MockTarget | null;
  stacks: Map<string, SceneStack>;   // `${bin}|${band}`
  golden?: boolean;
  ready: Set<string>;
}

const views = new Map<string, MockView>();
const jobs = new Map<string, string>();       // job id → view key
let goldenBits: Uint16Array | null = null;

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));
const hex = (s: string, n: number) => {
  let a = hashString(s).toString(16).padStart(8, "0"), b = hashString(`${s}#`).toString(16).padStart(8, "0");
  while ((a + b).length < n) { a += b; b = hashString(a).toString(16).padStart(8, "0"); }
  return (a + b).slice(0, n);
};
const jsonResponse = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
const notFound = (detail: string) => jsonResponse({ detail }, 404);

/* ------------------------------------------------------------------ resolve */

function resolve(qRaw: string): ResolveResult | null {
  const q = qRaw.trim();
  if (q.toLowerCase() === "golden" || q.toLowerCase() === "f14") {
    return { query: q, kind: "coords", name: "Orientation golden (F14)", ra: 180, dec: 0, epoch: 2026, propagated_now: { ra: 180, dec: 0, epoch: NOW_YEAR } };
  }
  const t = findTarget(q);
  if (t) {
    const now = propagateLinear(t, NOW_YEAR);
    return {
      query: q, kind: "star", name: t.name, main_id: t.main_id, ra: t.ra, dec: t.dec, epoch: t.epoch, pm: t.pm, plx: t.plx,
      rv: t.rv, otype: t.otype, spt: t.spt, astrometry_source: t.source, propagated_now: { ...now, epoch: NOW_YEAR },
    };
  }
  const c = parseCoordinates(q);
  if (!c) return null;
  return coordsResolve(q, c.ra, c.dec);
}

/** Mock epoch guard (implementation.md §4.1): which high-PM target's track passes the typed point? */
function coordsResolve(q: string, ra: number, dec: number): ResolveResult {
  const base: ResolveResult = { query: q, kind: "coords", name: q, ra, dec, epoch: NOW_YEAR, propagated_now: { ra, dec, epoch: NOW_YEAR } };
  for (const t of TARGETS) {
    if (Math.hypot(t.pm[0], t.pm[1]) < 500) continue;
    let best = { y: 0, sep: Infinity };
    for (let y = 1990; y <= 2031; y += 0.02) {
      const p = propagateLinear(t, y);
      const s = sepArcsec(ra, dec, p.ra, p.dec);
      if (s < best.sep) best = { y, sep: s };
    }
    if (best.sep > 3) continue;
    const now = propagateLinear(t, NOW_YEAR);
    if (Math.abs(best.y - NOW_YEAR) <= 1) return { ...base, label_hint: `${t.name} (${Math.floor(NOW_YEAR)} position)` };
    const pa = positionAngle(ra, dec, now.ra, now.dec);
    const dir = ["north", "north-east", "east", "south-east", "south", "south-west", "west", "north-west"][Math.round(pa / 45) % 8]!;
    return {
      ...base,
      epoch_hint: { object: t.name, epoch: Math.round(best.y * 100) / 100, sep_arcsec: Math.round(best.sep * 10) / 10,
        now_ra: now.ra, now_dec: now.dec, moved_arcmin: sepArcsec(ra, dec, now.ra, now.dec) / 60, direction: dir },
    };
  }
  return base;
}

/* -------------------------------------------------------------------- views */

function dateRange(a: number, b: number): string {
  const x = mjdToISODate(a), y = mjdToISODate(b);
  if (x === y) return x;
  if (x.slice(0, 7) === y.slice(0, 7)) return `${x}/${y.slice(8)}`;
  if (x.slice(0, 4) === y.slice(0, 4)) return `${x}→${y.slice(5)}`;
  return `${x}→${y}`;
}

/** Same format as backend epochs.label (I). */
function label(id: string, status: string, a: number, b: number, surveys: (number | null)[], nBand: number, band: number, nVisit: number) {
  const sv = [...new Set(surveys.filter((s): s is number => !!s))].sort().map((s) => `S${s}`);
  if (surveys.includes(null)) sv.push("IOC");
  const head = `${id} · ${dateRange(a, b)} · ${sv.join("+")}`;
  return status === "partial" ? `${head} · partial (${nBand} in band ${band})` : `${head} · ${nVisit || nBand} frames`;
}

function buildView(params: Record<string, string>): MockView | { error: string; status: number } {
  const fov = Number(params.fov ?? 6), px = Number(params.px ?? 3);
  const includePartial = params.partial === "1";
  const selBand = Number((params.bands ?? "6").replace(/^rgb:/, "").split(",")[0]) || 6;
  const q = params.q ?? (params.ra && params.dec ? `${params.ra} ${params.dec}` : "");
  const res = q ? resolve(q) : null;
  if (!res) return { error: `Could not resolve "${q}". Try a name such as Barnard's Star, or RA/Dec.`, status: 404 };
  if (params.pin && !knownPins.has(params.pin)) {
    return { error: `unknown pin ${params.pin}: it is neither a committed demo pin nor a view built on this server`, status: 404 };
  }
  const golden = res.name.startsWith("Orientation golden");
  let target = res.kind === "star" ? findTarget(res.query) : null;
  if (!target && res.epoch_hint) target = TARGETS.find((t) => t.name === res.epoch_hint!.object) ?? null;
  const key = hex(JSON.stringify(Object.entries(params).sort()), 16);
  const bins: Record<string, TimeBinInfo[]> = {};
  const frames: FrameMeta[] = [];
  const stacks: StackInfo[] = [];
  const track: TrackPoint[] = [];
  const warnings: ViewWarning[] = [];

  let center = res.propagated_now;
  let grid = makeGrid(center.ra, center.dec, fov, px);
  if (golden) {
    grid = makeGrid(180, 0, 121 * 3 / 60, 3);
    bins["6"] = [{ id: "G", band: 6, status: "full", mjd_mean: mjdOf("2026-01-01"), mjd_min: mjdOf("2026-01-01"), mjd_max: mjdOf("2026-01-01"),
      surveys: [1], label: "G · golden F (orientation test, not sky data)", n_frames: 1, n_visit_frames: 1 }];
    stacks.push({ bin: "G", band: 6, ready: true, format: FORMAT_F16, nhits_max: 1, filled: false, skipped: [], frame_ids: ["golden"] });
  } else {
    const visits = target?.visits ?? TARGETS[0]!.visits.slice(0, 3);
    const mids = visits.map((v) => (mjdOf(v.start) + mjdOf(v.end)) / 2).sort((a, b) => a - b);
    if (target && res.kind === "star" && params.center !== "track") {   // named target, fixed sky: centre on pos(t) at the median frame time
      const p = propagateLinear(target, mjdToDecimalYear(mids[mids.length >> 1]!));
      center = { ...p, epoch: mjdToDecimalYear(mids[mids.length >> 1]!) };
      grid = makeGrid(center.ra, center.dec, fov, px);
    }
    for (const b of [1, 2, 3, 4, 5, 6]) {
      const list: TimeBinInfo[] = [];
      for (const v of visits) {
        if (v.missingBands?.includes(b)) continue;
        const n = v.perBand?.[b] ?? Math.round(v.nVisit / 6);
        if (!n) continue;
        const a = mjdOf(v.start), z = mjdOf(v.end) + 0.9;
        const status = v.status === "bin" ? "bin" : n >= 10 ? "full" : "partial";
        list.push({ id: v.id, band: b, status, mjd_mean: (a + z) / 2, mjd_min: a, mjd_max: z, surveys: v.surveys,
          label: label(v.id, status, a, z, v.surveys, n, b, status === "partial" ? 0 : v.nVisit), n_frames: n, n_visit_frames: v.nVisit });
        const ids: string[] = [];
        const skipped: [string, string][] = [];
        for (let i = 0; i < n; i++) {
          const mjd = a + ((z - a) * (i + 0.5)) / n;
          const id = `mock_${target?.key ?? "field"}_${v.id}_D${b}_${String(i).padStart(3, "0")}.fits`;
          const rel = mjd >= mjdOf("2026-08-01") ? "qr3" : "qr2";
          const skip = target?.key === "barnard" && v.id === "V3" && b === 6 && i === 7 ? "cutout failed after 4 retries (HTTP 503)" : null;
          frames.push({ id, band: b, detector: b, bin: v.id, mjd, survey: v.surveys[0] ?? null, obsid: `MOCK_${v.id}_${i}`, release: rel,
            collection: `spherex_${rel}`, pipeline: rel === "qr3" ? "7.0.5" : "6.5.6",
            qa: { L1DQAFLG: "Pass", L2DQAFLG: "Pass", FINAST: 0 }, skipped: skip });
          if (skip) skipped.push([id, skip]); else ids.push(id);
        }
        stacks.push({ bin: v.id, band: b, ready: false, format: FORMAT_F16, nhits_max: ids.length, filled: false, skipped, frame_ids: ids });
        if (target) {
          const p = propagateLinear(target, mjdToDecimalYear((a + z) / 2));
          track.push({ bin: v.id, band: b, mjd: (a + z) / 2, ra: p.ra, dec: p.dec });
        }
      }
      if (list.length) bins[String(b)] = list;
    }
    const nPartial = (bins[String(selBand)] ?? []).filter((x) => x.status === "partial").length;
    if (nPartial && !includePartial) warnings.push({ code: "partial_hidden", severity: "info",
      message: `${nPartial} partial visit${nPartial > 1 ? "s" : ""} in band ${selBand} hidden from the blink (turn on "partial" to include).` });
    const nSkip = stacks.reduce((s, x) => s + x.skipped.length, 0);
    if (nSkip) warnings.push({ code: "frames_skipped", severity: "warn", message: `${nSkip} frame${nSkip > 1 ? "s" : ""} could not be fetched and ${nSkip > 1 ? "are" : "is"} listed as skipped.` });
    if (target?.look.holes?.length) warnings.push({ code: "saturated_core", severity: "info",
      message: `Saturated core: no data at the target in band${target.look.holes.length > 1 ? "s" : ""} ${target.look.holes.join(", ")} (no-data tint). Turn on the OVERFLOW flag layer.` });
  }
  const pinCurrent = hex(frames.map((f) => f.id).join("|") || "golden", 12);
  knownPins.add(pinCurrent);
  // A committed demo pin is the mock's current frame list (its synthetic frames have no other identity).
  const newer = params.pin && !COMMITTED_PINS.has(params.pin) && params.pin !== pinCurrent ? pinCurrent : null;
  const manifest: ViewManifest = {
    schema_version: API_SCHEMA_VERSION, key, pin: params.pin ?? pinCurrent,
    newer_pin: newer,
    params, target: res, grid, axis: golden ? "visit" : target?.axis ?? "visit",
    bands: Object.keys(bins).map(Number), bins, stacks, limits: {}, frames, track,
    flags: { bits: CANONICAL_BITS, info: FLAG_INFO, format: FORMAT_U32_FLAGS },
    formats: { stack: FORMAT_F16, science: FORMAT_F32, flags: FORMAT_U32_FLAGS },
    release: { release_state: RELEASE_STATE, newest_period: "2026W40_2A", checked_at: new Date().toISOString() },
    warnings, data_source: "mock",
  };
  const view: MockView = { key, manifest, target, stacks: new Map(), golden, ready: new Set() };
  if (golden) {
    manifest.limits["6"] = { lo: 0, hi: 100, lim: "manual:0,100" };
    view.ready.add("G|6");
  } else {
    for (const [b, list] of Object.entries(bins)) {
      const arr = list.map((tb) => stackOf(view, tb.id, Number(b)).data);
      const { lo, hi } = mockLimits(arr);
      manifest.limits[b] = { lo, hi, lim: params.lim ?? "zscale" };
    }
  }
  return view;
}

function stackOf(v: MockView, bin: string, band: number): SceneStack {
  const k = `${bin}|${band}`;
  let s = v.stacks.get(k);
  if (!s) {
    const tb = v.manifest.bins[String(band)]?.find((x) => x.id === bin);
    if (!tb) throw new Error(`no bin ${bin} in band ${band}`);
    s = sceneStack({ grid: v.manifest.grid, band, mjd: tb.mjd_mean, nFrames: tb.n_frames, target: v.target,
      seedKey: v.manifest.params.q ?? `${v.manifest.params.ra},${v.manifest.params.dec}`, partial: tb.status === "partial" });
    v.stacks.set(k, s);
  }
  return s;
}

function toF16(a: Float32Array): ArrayBuffer {
  const out = new Uint16Array(a.length);
  for (let i = 0; i < a.length; i++) {
    const x = a[i]!;
    out[i] = Number.isFinite(x) ? floatToHalf(Math.min(6.5e4, Math.max(-5e4, x))) : NODATA_BITS;
  }
  return out.buffer;
}

async function golden(): Promise<Uint16Array> {
  if (!goldenBits) goldenBits = new Uint16Array(await (await fetch(goldenUrl)).arrayBuffer());
  return goldenBits;
}

async function pngOf(data: Float32Array, nx: number, ny: number, url: URL): Promise<Response> {
  const lim = url.searchParams.get("lim") ?? "manual:0,1";
  const [lo, hi] = lim.replace("manual:", "").split(",").map(Number) as [number, number];
  const rgba = renderRGBA(data, nx, ny, lo, hi, parseStretch(url.searchParams.get("stretch")),
    (url.searchParams.get("cmap") ?? "gray") as "gray");
  const c = document.createElement("canvas");
  c.width = nx; c.height = ny;
  c.getContext("2d")!.putImageData(new ImageData(rgba, nx, ny), 0, 0);
  const blob: Blob = await new Promise((r) => c.toBlob((b) => r(b!), "image/png"));
  return new Response(blob, { headers: { "Content-Type": "image/png" } });
}

/* ------------------------------------------------------------- science mocks */

function spectrumFor(t: MockTarget | null, ra: number, dec: number): SpectrumResponse {
  const r = mulberry32(hashString(`spec|${ra.toFixed(4)}|${dec.toFixed(4)}`));
  const rows: SpectrumResponse["rows"] = [];
  const kind = t?.key ?? "field";
  const model = (lam: number) => {
    switch (kind) {
      case "epsindb": return 400 * Math.exp(-((lam - 1.25) ** 2) / 0.05) + 250 * Math.exp(-((lam - 4.1) ** 2) / 0.2) +
        120 * Math.exp(-((lam - 2.1) ** 2) / 0.04) + 30 - 25 * Math.exp(-((lam - 3.3) ** 2) / 0.02);
      case "wise0855": return lam < 3.5 ? 2 : 400 * Math.exp(-((lam - 4.6) ** 2) / 0.12);
      case "barnard": return 3e5 * Math.pow(lam, -2) * (1 - 0.15 * Math.exp(-((lam - 1.4) ** 2) / 0.01));
      case "rwaur": return 5e4 * Math.pow(lam, -0.8);
      case "rdra": return 2e6 * Math.pow(lam, -1.6) * (1 - 0.3 * Math.exp(-((lam - 2.7) ** 2) / 0.05));
      default: return 800 * Math.pow(lam, -2);
    }
  };
  const visits = (t?.visits ?? []).filter((v) => v.status === "full").slice(0, 4);
  // MOCK realism: visits before 2025-12 are QR2 (uncorrected gain ≈ 0.93 vs QR3, validation/F4), later ones QR3;
  // ~1 % of frames are wild (cosmic ray / blend), so the chart's robust range and clipping are exercised offline
  for (const v of visits.length ? visits : [{ id: "V1", start: "2025-09-01" }]) {
    const release = v.start < "2025-12" ? "qr2" : "qr3", gain = release === "qr2" ? 0.93 : 1;
    for (const b of [1, 2, 3, 4, 5, 6]) {
      const [lo, hi] = BANDS[b]!;
      for (let i = 0; i < 18; i++) {
        const lam = lo * Math.pow(hi / lo, (i + r()) / 18);
        const f = gain * model(lam);
        const err = Math.hypot(0.03 * Math.abs(f), 3 + 0.02 * Math.abs(f));
        const wild = r() < 0.01 ? (r() < 0.5 ? 8 : -6) * Math.abs(f) : 0;
        rows.push({ lam, dlam: lam / BANDS[b]![2], flux: f + err * (r() * 2 - 1) + wild, err, mjd: mjdOf(v.start) + i * 0.3,
          visit: v.id, detector: b, flags: [], rchi2: 0.8 + 0.4 * r(), contaminated: Math.abs(lam - 1.083) < 0.012, release });
      }
    }
  }
  const mean = (a: number, b: number) => {
    const s = rows.filter((x) => x.lam >= a && x.lam <= b);
    return s.length ? s.reduce((q, x) => q + x.flux, 0) / s.length : NaN;
  };
  const meth = mean(3.25, 3.4) / mean(3.95, 4.2);
  return { ra, dec, rows, indices: { methane_rel: Number.isFinite(meth) ? meth / 1.5 : null, w1w2_syn: null }, validity: "unvalidated",
    notes: ["MOCK spectrum: synthetic shape, not a measurement."] };
}

function astrometryFor(t: MockTarget | null): AstrometryResponse {
  if (!t) return { name: "field", points: [], fit: null, catalogue: null, validity: "unvalidated" };
  const r = mulberry32(hashString(`ast|${t.key}`));
  const full = t.visits.filter((v) => v.status !== "partial");
  const t0 = mjdToDecimalYear(mjdOf(full[0]?.start ?? "2025-08-01"));
  const p0 = propagateLinear(t, t0);
  const points = full.map((v) => {
    const mjd = (mjdOf(v.start) + mjdOf(v.end)) / 2;
    const p = propagateLinear(t, mjdToDecimalYear(mjd));
    const xi = (p.ra - p0.ra) * Math.cos((p.dec * Math.PI) / 180) * 3600 + 0.15 * (r() * 2 - 1);
    const eta = (p.dec - p0.dec) * 3600 + 0.15 * (r() * 2 - 1);
    return { visit: v.id, mjd, xi, eta, s_xi: 0.2, s_eta: 0.2, band: 6 };
  });
  let fit: AstrometryResponse["fit"] = null;
  if (points.length >= 2) {
    const ts = points.map((p) => mjdToDecimalYear(p.mjd) - t0);
    const tm = ts.reduce((a, b) => a + b, 0) / ts.length;
    const sl = (ys: number[]) => {
      const ym = ys.reduce((a, b) => a + b, 0) / ys.length;
      const num = ts.reduce((s, x, i) => s + (x - tm) * (ys[i]! - ym), 0), den = ts.reduce((s, x) => s + (x - tm) ** 2, 0);
      return { m: num / den, e: 0.2 / Math.sqrt(den) };
    };
    const a = sl(points.map((p) => p.xi)), d = sl(points.map((p) => p.eta));
    const mu = Math.hypot(a.m, d.m);
    fit = { pmra: a.m * 1000, pmdec: d.m * 1000, e_pmra: a.e * 1000, e_pmdec: d.e * 1000, mu, e_mu: Math.hypot(a.e, d.e) / Math.SQRT2,
      pa_deg: ((Math.atan2(a.m, d.m) * 180) / Math.PI + 360) % 360, plx_fixed: t.plx, chi2: points.length * 2 - 4, dof: Math.max(1, points.length * 2 - 4),
      delta_chi2: (mu * mu) / 0.04 * points.length };
  }
  const muCat = Math.hypot(t.pm[0], t.pm[1]) / 1000;
  return { name: t.name, points, fit, validity: "unvalidated",
    catalogue: { source: t.source, mu: muCat, pa_deg: ((Math.atan2(t.pm[0], t.pm[1]) * 180) / Math.PI + 360) % 360, pmra: t.pm[0], pmdec: t.pm[1] } };
}

function lightcurveFor(t: MockTarget | null): LightCurveResponse {
  const r = mulberry32(hashString(`lc|${t?.key}`));
  const bands: LightCurveResponse["bands"] = {};
  const period = t?.look.period?.[0] ?? 200, amp = t?.look.period?.[1] ?? 0;
  const all: { mjd: number; rel: number }[] = [];
  for (const b of [1, 2, 3, 4, 5, 6]) {
    bands[String(b)] = (t?.visits ?? []).filter((v) => !v.missingBands?.includes(b)).map((v) => {
      const mjd = (mjdOf(v.start) + mjdOf(v.end)) / 2;
      const rel = Math.pow(10, -0.4 * amp * 0.5 * Math.sin((2 * Math.PI * mjd) / period)) + 0.02 * (r() * 2 - 1);
      all.push({ mjd, rel });
      return { mjd, rel, err: 0.02, bin: v.id };
    });
  }
  const periods: number[] = [], power: number[] = [];
  const mean = all.reduce((s, x) => s + x.rel, 0) / Math.max(1, all.length);
  for (let P = 30; P <= 600; P += 3) {       // classical (Lomb-like) periodogram for the mock only
    const w = (2 * Math.PI) / P;
    let c = 0, s = 0, cc = 0, ss = 0;
    for (const x of all) { const y = x.rel - mean; c += y * Math.cos(w * x.mjd); s += y * Math.sin(w * x.mjd); cc += Math.cos(w * x.mjd) ** 2; ss += Math.sin(w * x.mjd) ** 2; }
    periods.push(P); power.push((c * c) / Math.max(1e-9, cc) + (s * s) / Math.max(1e-9, ss));
  }
  const best = periods[power.indexOf(Math.max(...power))] ?? 0;
  return { bands, periodogram: all.length > 8 ? { period_days: periods, power, best_days: best, fap: 0.01 } : null,
    method: t?.key === "rdra" ? "annulus" : "psf", label: t?.key === "rdra" ? "relative, qualitative (MOCK)" : "relative flux (MOCK)", validity: "unvalidated" };
}

/* -------------------------------------------------------------------- router */

async function route(path: string, init?: RequestInit): Promise<Response> {
  const url = new URL(path, "http://mock.local");
  const p = url.pathname;
  const g = (k: string) => url.searchParams.get(k);
  await sleep(60 + Math.random() * 120);

  if (p === "/releases") {
    const r: ReleasesResponse = { release_state: RELEASE_STATE, newest_period: "2026W40_2A", checked_at: new Date().toISOString(),
      features: MOCK_FEATURES, environment: "mock", snapshot: false, api_version: API_SCHEMA_VERSION };
    return jsonResponse(r);
  }
  if (p === "/resolve") {
    const r = resolve(g("q") ?? "");
    return r ? jsonResponse(r) : notFound(`Nothing called "${g("q")}" was found. Try another name, or RA/Dec such as 269.4461 4.7707.`);
  }
  if (p === "/coverage") {
    const ra = Number(g("ra")), dec = Number(g("dec"));
    const c: Coverage = { ra, dec, fov: Number(g("fov") ?? 6), n_frames: 0, axis: "visit", visits: [], releases: ["qr2", "qr3"],
      freshness: { release_state: RELEASE_STATE, newest_period: "2026W40_2A", checked_at: new Date().toISOString() } };
    return jsonResponse(c);
  }
  if (p === "/views" && init?.method === "POST") {
    const params = JSON.parse(String(init.body ?? "{}")) as Record<string, string>;
    const probe = buildView(params);
    if ("error" in probe) return jsonResponse({ detail: probe.error }, probe.status);
    const existing = views.get(probe.key);
    if (existing && existing.ready.size === existing.manifest.stacks.length) {
      return jsonResponse({ status: "ready", manifest: snapshotManifest(existing) });
    }
    views.set(probe.key, existing ?? probe);
    const job = `job_${probe.key}_${Date.now().toString(36)}`;
    jobs.set(job, probe.key);
    return jsonResponse({ status: "queued", job_id: job, key: probe.key }, 202);
  }
  let m = /^\/views\/([^/]+)\/manifest$/.exec(p);
  if (m) {
    const v = views.get(decodeURIComponent(m[1]!));
    return v ? jsonResponse(snapshotManifest(v)) : notFound("unknown view");
  }
  m = /^\/views\/([^/]+)\/(stack|png)\/([^/]+)\/(\d)\.(f16|f32|var\.f32|flags\.u32|png)$/.exec(p);
  if (m) {
    const v = views.get(decodeURIComponent(m[1]!));
    if (!v) return notFound("unknown view");
    const bin = decodeURIComponent(m[3]!), band = Number(m[4]), ext = m[5]!;
    if (!v.ready.has(`${bin}|${band}`)) return notFound("stack not ready");
    const [ny, nx] = v.manifest.grid.shape;
    if (v.golden) {
      const bits = await golden();
      if (ext === "f16") return new Response(bits.slice().buffer);
      const { decodeF16 } = await import("../../lib/half");
      if (ext === "png") return pngOf(decodeF16(bits), nx, ny, url);
      return notFound("golden has only f16/png");
    }
    const s = stackOf(v, bin, band);
    if (ext === "f16") return new Response(toF16(s.data));
    if (ext === "f32") return new Response(s.data.slice().buffer);
    if (ext === "var.f32") return new Response(s.var.slice().buffer);
    if (ext === "flags.u32") return new Response(s.flags.slice().buffer);
    if (ext === "png") return pngOf(s.data, nx, ny, url);
  }
  m = /^\/views\/([^/]+)\/diff$/.exec(p);
  if (m) {
    const v = views.get(decodeURIComponent(m[1]!));
    if (!v) return notFound("unknown view");
    const a = g("a")!, b = g("b")!, band = Number(g("band"));
    const ta = v.manifest.track.find((x) => x.bin === a && x.band === band), tb = v.manifest.track.find((x) => x.bin === b && x.band === band);
    const ann: DiffInfo["annotations"] = [];
    if (ta && tb) {
      const pa = positionAngle(tb.ra, tb.dec, ta.ra, ta.dec), sep = sepArcsec(ta.ra, ta.dec, tb.ra, tb.dec);
      if (sep / v.manifest.grid.pix_arcsec > 0.3) ann.push({ kind: "dipole", ra: tb.ra, dec: tb.dec, to_ra: ta.ra, to_dec: ta.dec,
        shift_arcsec: sep, shift_px: sep / 6.15, pa_deg: pa, agrees_with_track: true, label: `moved ≈${sep.toFixed(1)}″ (MOCK)` });
    }
    // MOCK: a cross-release match with a gentle chromatic gain, so the UI's match panel can be exercised offline
    const [lo, hi] = BANDS[band] ?? [0.75, 1.0];
    const bins = Array.from({ length: 17 }, (_, i) => {
      const lam = lo * Math.pow(hi / lo, (i + 0.5) / 17), s = 1.075 - 0.03 * (i / 16 - 0.5);
      return { lam, scale: s, err: 0.004, raw: s + 0.006 * Math.sin(i * 2.3), raw_err: 0.009, shrink: 0.35, offset: 0, n_pix: 900,
        n_sources: 14, pooled: false };
    });
    const info: DiffInfo & { url: string } = { a, b, band, format: FORMAT_F16, k: 1.0, clip_sigma: 5, annotations: ann, validity: "unvalidated",
      url: `/views/${v.key}/diff/${encodeURIComponent(a)}/${encodeURIComponent(b)}/${band}.f16`,
      photometric_match: { applied: true, cross_release: true, scales_a: ["qr3"], scales_b: ["qr2"],
        method: "in-situ relative photometry (MOCK)", scale: 1.075, scale_err: 0.003, offset: 0, offset_err: 0.01, n_sources: 14,
        n_pix: 15200, residual_scale: 1.1, tau: 0.009, q_flat: 41, dof_flat: 16, static_z_before: 38.2, static_z_after: 0.9, bins,
        note: "QR2 visit matched to QR3 in situ on 14 static sources (scale 1.075 ± 0.003). Positions and motions are valid; " +
          "brightness changes across releases are not interpreted until F4 is resolved. (MOCK)" } };
    return jsonResponse(info);
  }
  m = /^\/views\/([^/]+)\/diff\/([^/]+)\/([^/]+)\/(\d)\.f16$/.exec(p);
  if (m) {
    const v = views.get(decodeURIComponent(m[1]!));
    if (!v) return notFound("unknown view");
    const A = stackOf(v, decodeURIComponent(m[2]!), Number(m[4])), B = stackOf(v, decodeURIComponent(m[3]!), Number(m[4]));
    const sig = new Float32Array(A.data.length);
    for (let i = 0; i < sig.length; i++) sig[i] = (A.data[i]! - B.data[i]!) / Math.sqrt(A.var[i]! + B.var[i]!);
    return new Response(toF16(sig));
  }
  m = /^\/views\/([^/]+)\/frames$/.exec(p);
  if (m) {
    const v = views.get(decodeURIComponent(m[1]!));
    if (!v) return notFound("unknown view");
    const band = Number(g("band")), sort = g("sort") === "time" ? "time" : "lambda";
    const [lo, hi] = BANDS[band]!;
    const rows = v.manifest.frames.filter((f) => f.band === band && f.skipped === null && v.ready.has(`${f.bin}|${band}`))
      .map((f) => ({ id: f.id, mjd: f.mjd, lam_um: lo + (hi - lo) * ((hashString(f.id) % 1000) / 1000),
        url: `/views/${v.key}/frames/${band}/${hex(f.id, 16)}.f16` }));
    rows.sort((a, b) => (sort === "lambda" ? a.lam_um - b.lam_um : a.mjd - b.mjd));
    const label = sort === "lambda" ? "spectral sequence (sorted by wavelength), not a time sequence (MOCK)"
      : "exposure (time) order: the wavelength changes between exposures, so brightness changes are spectral, not variability (MOCK)";
    return jsonResponse({ key: v.key, band, sort, label, format: FORMAT_F16, frames: rows.slice(0, 64) });
  }
  m = /^\/views\/([^/]+)\/frames\/(\d)\/([0-9a-f]{16})\.f16$/.exec(p);
  if (m) {
    const v = views.get(decodeURIComponent(m[1]!));
    if (!v) return notFound("unknown view");
    const band = Number(m[2]);
    const f = v.manifest.frames.find((x) => x.band === band && hex(x.id, 16) === m![3]);
    if (!f) return notFound("frame not computed");
    const st = stackOf(v, f.bin, band), k = 0.8 + 0.4 * ((hashString(f.id) % 1000) / 1000);
    return new Response(toF16(st.data.map((x) => x * k)));
  }
  m = /^\/views\/([^/]+)\/cube\/([^/]+)\/(\d)\.f16$/.exec(p);
  if (m) {
    const v = views.get(decodeURIComponent(m[1]!));
    if (!v) return notFound("unknown view");
    const st = stackOf(v, decodeURIComponent(m[2]!), Number(m[3]));
    const out = new Float32Array(17 * st.data.length);
    for (let k = 0; k < 17; k++) for (let i = 0; i < st.data.length; i++) out[k * st.data.length + i] = st.data[i]! * (0.7 + 0.6 * k / 16);
    return new Response(toF16(out));
  }
  m = /^\/views\/([^/]+)\/rgb\/([^/]+)\/(methane|ice)\.f16$/.exec(p);
  if (m) {
    const v = views.get(decodeURIComponent(m[1]!));
    if (!v) return notFound("unknown view");
    const bin = decodeURIComponent(m[2]!);
    const planes = (m[3] === "methane" ? [5, 4, 4] : [4, 4, 4]).map((b, k) => stackOf(v, bin, b).data.map((x) => x * (1 - 0.15 * k)));
    const out = new Float32Array(3 * planes[0]!.length);
    planes.forEach((pl, k) => out.set(pl, k * pl.length));
    return new Response(toF16(out));
  }
  if (p === "/sso") {
    const name = g("name") ?? "";
    const mjds = (g("mjd") ?? "").split(",").filter(Boolean).map(Number);
    const v = [...views.values()].find((x) => x.manifest.target?.name === name);
    const c = v?.manifest.grid.crval ?? [0, 0];
    return jsonResponse({ name, observer: "500@-163182 (MOCK)", points: mjds.map((t, k) => ({ mjd: t, ra: c[0] + 1e-4 * k, dec: c[1] })) });
  }
  if (/^\/views\/[^/]+\/blink25/.test(p)) return jsonResponse({ detail: "mock: the 25-year blink fetches 2MASS/WISE archives; use the backend" }, 409);
  if (/^\/export\//.test(p)) return notFound("mock: exports are rendered by the backend (MOCK=1 or FRAMESOURCE=fixture)");
  if (p === "/spectrum") {
    const ra = Number(g("ra")), dec = Number(g("dec"));
    const t = TARGETS.find((x) => { const q = propagateLinear(x, NOW_YEAR); return sepArcsec(ra, dec, q.ra, q.dec) < 30; }) ?? null;
    return jsonResponse(spectrumFor(t, ra, dec));
  }
  if (p === "/astrometry") {
    const t = findTarget(g("name") ?? "") ?? null;
    return jsonResponse(astrometryFor(t));
  }
  if (p === "/lightcurve") {
    const ra = Number(g("ra")), dec = Number(g("dec"));
    const t = TARGETS.find((x) => sepArcsec(ra, dec, x.ra, x.dec) < 120) ?? null;
    return jsonResponse(lightcurveFor(t));
  }
  m = /^\/overlays\/(gaia|catwise|allwise|simbad|sso)$/.exec(p);
  if (m) {
    const ra = Number(g("ra")), dec = Number(g("dec")), mjd = Number(g("mjd"));
    const v = [...views.values()].find((x) => sepArcsec(ra, dec, x.manifest.grid.crval[0], x.manifest.grid.crval[1]) < 1);
    const sources: OverlayResponse["sources"] = [];
    if (v && m[1] === "gaia") {
      for (const [i, s] of fieldStars(v.manifest.grid, v.manifest.params.q ?? `${v.manifest.params.ra},${v.manifest.params.dec}`).entries()) {
        if (s.peak(3) < 0.15) continue;
        const sky = pixelToSky(v.manifest.grid, s.col, s.row);
        sources.push({ id: `MOCK Gaia ${i}`, ra: sky.ra, dec: sky.dec, mag: 18 - 2.5 * Math.log10(s.peak(3) / 0.06) });
      }
    }
    if (v?.target && (m[1] === "simbad" || m[1] === "gaia")) {
      const p2 = propagateLinear(v.target, mjdToDecimalYear(mjd));
      if (skyToPixel(v.manifest.grid, p2.ra, p2.dec)) sources.push({ id: v.target.main_id, ra: p2.ra, dec: p2.dec, label: v.target.name });
    }
    if (v?.target && m[1] === "allwise") {       // as catalogued around 2010.5: never moved to `mjd`
      const old = propagateLinear(v.target, 2010.5);
      sources.push({ id: `WISEA ${v.target.main_id}`, ra: old.ra, dec: old.dec });
      return jsonResponse({ catalogue: "allwise", mjd, sources, epoch: 2010.5 } satisfies OverlayResponse);
    }
    return jsonResponse({ catalogue: m[1] as OverlayResponse["catalogue"], mjd, sources } satisfies OverlayResponse);
  }
  if (p === "/candidates" && init?.method === "POST") {
    const body = JSON.parse(String(init.body ?? "{}"));
    return jsonResponse({ id: `mock-${hex(JSON.stringify(body), 8)}`, auto_checks: [
      { name: "Known in SIMBAD/Gaia/CatWISE?", passed: null, detail: "MOCK: not checked" },
      { name: "Known asteroid (SkyBoT)?", passed: null, detail: "MOCK: not checked" },
      { name: "Seen in ≥ 2 visits?", passed: (body.visits?.length ?? 0) >= 2, detail: `${body.visits?.length ?? 0} visit(s) attached` },
      { name: "Inside an artifact footprint?", passed: null, detail: "MOCK: not checked" },
    ] });
  }
  return notFound(`mock: no route for ${p}`);
}

function snapshotManifest(v: MockView): ViewManifest {
  return { ...v.manifest, stacks: v.manifest.stacks.map((s) => ({ ...s, ready: v.ready.has(`${s.bin}|${s.band}`) })) };
}

/** Simulated job: band-first planning (§2.3), then the rest; progress events like the real SSE. */
function runJob(jobId: string, onEvent: (e: JobEvent) => void): () => void {
  let cancelled = false;
  (async () => {
    const key = jobs.get(jobId);
    const v = key ? views.get(key) : undefined;
    if (!v) { onEvent({ type: "error", message: "unknown job" }); return; }
    const sel = Number((v.manifest.params.bands ?? "6").replace(/^rgb:/, "").split(",")[0]) || 6;
    const order = [...v.manifest.stacks].sort((a, b) => (a.band === sel ? 0 : 1) - (b.band === sel ? 0 : 1) || a.band - b.band);
    const n = v.manifest.frames.length || 1;
    await sleep(250);
    if (cancelled) return;
    onEvent({ type: "planned", n });
    let i = 0;
    for (const s of order) {
      if (v.ready.has(`${s.bin}|${s.band}`)) continue;
      const nf = s.frame_ids.length + s.skipped.length;
      for (let k = 0; k < nf; k += Math.max(1, Math.ceil(nf / 3))) {
        await sleep(s.band === sel ? 45 : 18);
        if (cancelled) return;
        i = Math.min(n, i + Math.ceil(nf / 3));
        onEvent({ type: "fetched", i, n });
      }
      for (const [id, why] of s.skipped) onEvent({ type: "warning", code: "frame_skipped", message: `${id}: ${why}` });
      v.ready.add(`${s.bin}|${s.band}`);
      onEvent({ type: "stack_ready", bin: s.bin, band: s.band });
    }
    if (!cancelled) onEvent({ type: "done", key: v.key });
  })();
  return () => { cancelled = true; };
}

export const mockTransport: Transport = {
  kind: "mock",
  request: (path, init) => route(path, init),
  events(path, onEvent, _onError): EventStreamLike {
    const m = /^\/jobs\/([^/]+)\/events$/.exec(path);
    const stop = m ? runJob(decodeURIComponent(m[1]!), onEvent) : () => undefined;
    void _onError;
    return { close: stop };
  },
};

/** Test hook: forget all mock views. */
export function resetMock(): void { views.clear(); jobs.clear(); }
