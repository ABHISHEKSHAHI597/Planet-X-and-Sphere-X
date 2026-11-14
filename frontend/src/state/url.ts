/**
 * URL schema (implementation.md §5.3; workflow.md §7.2: always additive — unknown parameters are
 * ignored with a console warning; removed parameters keep working through ALIASES).
 * Every pinned link in the README, slides and video is a URL fixture tested in CI
 * (fixtures/urls/*.txt → tests/url.test.ts).
 */
import { FOV_MAX, FOV_MIN } from "../lib/constants";
import { normalizeInput } from "../lib/coords";

export type Mode = "blink" | "diff" | "side" | "flip" | "onion";
export type Center = "fixed" | "track";
export type Cmap = "gray" | "magma" | "cividis";
export type UiLevel = "simple" | "explorer" | "expert";

export interface ViewState {
  q: string | null;           // name, alias, "sso:<name>" or coordinates typed in one box
  ra: string | null;          // as typed (decimal or sexagesimal); parsed by lib/coords
  dec: string | null;
  fov: number;                // arcmin
  px: number;                 // display pixel (arcsec); native 6.15
  axis: string;               // auto | visit | survey | bin:14d | exposure | multi
  partial: boolean;
  bands: string;              // "6" | "1,2,3" | "rgb:4,5,6" | "rgb:ice" | "rgb:methane"
  mode: Mode;
  a: string | null;
  b: string | null;
  stretch: string;            // lin | sqrt | log | asinh:β
  lim: string;                // zscale | p99.5 | manual:lo,hi
  cmap: Cmap;
  fps: number;
  center: Center;
  ov: string[];               // overlays: track, vec, gaia, simbad, sso, flags
  flags: string[];            // flag planes to draw
  mask: string;               // auto | discovery | bright | imaging
  rel: string;                // auto | qr3 | qr2
  pin: string | null;         // 12 hex
  sel: string | null;         // "ra,dec" of the selected source
  t: string | null;           // current time bin id (additive, F)
  ui: UiLevel;                // simple | explorer | expert (additive, F)
}

export const DEFAULTS: ViewState = {
  q: null, ra: null, dec: null, fov: 6, px: 3, axis: "auto", partial: false, bands: "6", mode: "blink",
  a: null, b: null, stretch: "asinh:8", lim: "zscale", cmap: "gray", fps: 2, center: "fixed",
  ov: ["track"], flags: [], mask: "auto", rel: "auto", pin: null, sel: null, t: null, ui: "explorer",
};

/** Serialisation order: the order of implementation.md §5.3, then additive params. */
export const ORDER: (keyof ViewState)[] = ["q", "ra", "dec", "fov", "px", "axis", "partial", "bands", "mode", "a", "b",
  "stretch", "lim", "cmap", "fps", "center", "ov", "flags", "mask", "rel", "pin", "sel", "t", "ui"];

/** Removed or alternative spellings → current parameter (never delete an entry). */
export const ALIASES: Record<string, keyof ViewState> = {
  band: "bands", target: "q", name: "q", overlays: "ov", release: "rel", speed: "fps",
};
/** Value aliases kept for old links. */
const MODE_ALIASES: Record<string, Mode> = { sidebyside: "side", flipbook: "flip", difference: "diff", onionskin: "onion" };

/** Parameters outside the view schema, accepted silently: gl=0 forces the PNG viewer (debug); lang=hi|es picks the
 *  interface language (lib/lang.ts reads it once at load and remembers it in the browser). */
const DEBUG_PARAMS = new Set(["gl", "lang"]);

const MODES: Mode[] = ["blink", "diff", "side", "flip", "onion"];
const CMAPS: Cmap[] = ["gray", "magma", "cividis"];
const UIS: UiLevel[] = ["simple", "explorer", "expert"];
// bin:<N>d with 1 ≤ N ≤ 365 (the server refuses 0 and > 365; audit B-10)
const AXIS = /^(auto|visit|survey|exposure|multi|bin:([1-9]\d?|[12]\d\d|3[0-5]\d|36[0-5])d)$/;
const BANDS = /^([1-6](,[1-6]){0,5}|rgb:[1-6],[1-6],[1-6]|rgb:(ice|methane|thermal))$/;
const LIM = /^(zscale|p\d{2}(\.\d+)?|manual:-?[\d.e+-]+,-?[\d.e+-]+)$/;
const STRETCH = /^(lin|sqrt|log(:\d+(\.\d+)?)?|asinh(:\d+(\.\d+)?)?)$/;
const PIN = /^[0-9a-f]{12}$/;
// `wise` draws AllWISE positions as catalogued (about 2010.5), not moved to the visit (optimisation.md REL-5).
// `catwise` is still accepted (additive URL schema) but not drawn: its epoch columns are unverified (audit V-08, F-11).
const OVERLAYS = ["track", "vec", "gaia", "wise", "simbad", "sso", "catwise", "flags", "crosshair"];

const clamp = (x: number, lo: number, hi: number) => Math.min(hi, Math.max(lo, x));

export interface ParseResult { state: ViewState; warnings: string[] }

export function parseURL(search: string): ParseResult {
  const sp = new URLSearchParams(search.startsWith("?") ? search.slice(1) : search);
  const s: ViewState = { ...DEFAULTS, ov: [...DEFAULTS.ov], flags: [] };
  const warnings: string[] = [];
  const known = new Set<string>(ORDER);
  for (const [rawKey, rawVal] of sp) {
    const key = (known.has(rawKey) ? rawKey : ALIASES[rawKey]) as keyof ViewState | undefined;
    if (!key && DEBUG_PARAMS.has(rawKey)) continue;
    if (!key) { warnings.push(`ignored unknown URL parameter "${rawKey}"`); continue; }
    const v = rawVal.trim();
    const bad = () => warnings.push(`ignored invalid ${key}="${rawVal}"`);
    switch (key) {
      case "q": s.q = v ? normalizeInput(v) : null; break;
      case "ra": s.ra = v || null; break;
      case "dec": s.dec = v ? normalizeInput(v) : null; break;
      case "fov": { const n = Number(v); if (Number.isFinite(n) && n > 0) s.fov = clamp(n, FOV_MIN, FOV_MAX); else bad(); break; }
      case "px": { const n = Number(v); if (Number.isFinite(n) && n >= 1 && n <= 30) s.px = n; else bad(); break; }
      case "axis": if (AXIS.test(v)) s.axis = v; else bad(); break;
      case "partial": s.partial = v === "1" || v === "true"; break;
      case "bands": if (BANDS.test(v)) s.bands = v; else bad(); break;
      case "mode": { const m = (MODE_ALIASES[v] ?? v) as Mode; if (MODES.includes(m)) s.mode = m; else bad(); break; }
      case "a": s.a = v || null; break;
      case "b": s.b = v || null; break;
      case "stretch": if (STRETCH.test(v)) s.stretch = v; else bad(); break;
      case "lim": if (LIM.test(v)) s.lim = v; else bad(); break;
      case "cmap": if (CMAPS.includes(v as Cmap)) s.cmap = v as Cmap; else bad(); break;
      case "fps": { const n = Number(v); if (Number.isFinite(n) && n > 0) s.fps = clamp(n, 0.25, 30); else bad(); break; }
      case "center": if (v === "fixed" || v === "track") s.center = v; else bad(); break;
      case "ov": s.ov = v ? v.split(",").map((x) => x.trim()).filter((x) => {
        if (OVERLAYS.includes(x)) return true;
        warnings.push(`ignored unknown overlay "${x}"`); return false;
      }) : []; break;
      case "flags": s.flags = v ? v.split(",").map((x) => x.trim().toUpperCase()).filter((x) => /^[A-Z_]+$/.test(x)) : []; break;
      case "mask": if (["auto", "discovery", "bright", "imaging"].includes(v)) s.mask = v; else bad(); break;
      case "rel": if (/^(auto|qr\d|dr\d)$/.test(v)) s.rel = v; else bad(); break;
      case "pin": if (PIN.test(v)) s.pin = v; else bad(); break;
      case "sel": if (/^-?\d+(\.\d+)?,-?\d+(\.\d+)?$/.test(v)) s.sel = v; else bad(); break;
      case "t": s.t = v && /^[A-Za-z?]{1,3}\d{0,4}$/.test(v) ? v : null; break;
      case "ui": if (UIS.includes(v as UiLevel)) s.ui = v as UiLevel; else bad(); break;
    }
  }
  // q and ra/dec are alternatives; explicit coordinates win (the epoch guard runs on them).
  if (s.ra && s.dec) s.q = null;
  return { state: s, warnings };
}

function valueOf(s: ViewState, k: keyof ViewState): string | null {
  const v = s[k];
  const d = DEFAULTS[k];
  if (Array.isArray(v)) {
    const dv = d as string[];
    return v.length === dv.length && v.every((x, i) => x === dv[i]) ? null : v.join(",");
  }
  if (v === d || v === null) return null;
  if (typeof v === "boolean") return v ? "1" : "0";
  return String(v);
}

/** Canonical query string: fixed key order, defaults omitted, so identical views share one link. */
export function toSearch(s: ViewState): string {
  const parts: string[] = [];
  for (const k of ORDER) {
    const v = valueOf(s, k);
    if (v === null) continue;
    // keep , and : readable (they are legal in query strings)
    parts.push(`${k}=${encodeURIComponent(v).replace(/%2C/g, ",").replace(/%3A/g, ":")}`);
  }
  return parts.length ? `?${parts.join("&")}` : "";
}

/** Parameters the backend needs to build a view (POST /views body): science-relevant only. */
export function viewParams(s: ViewState): Record<string, string> {
  const out: Record<string, string> = {};
  const keys: (keyof ViewState)[] = ["q", "ra", "dec", "fov", "px", "axis", "partial", "bands", "center", "mask", "rel", "pin", "lim"];
  for (const k of keys) {
    const v = s[k];
    if (v === null || v === undefined) continue;
    out[k] = typeof v === "boolean" ? (v ? "1" : "0") : String(v);
  }
  return out;
}

/** Display-only parameters of the POST /views body: they never change the view key (backend app/viewkey.py). */
export const DISPLAY_ONLY_PARAMS = ["bands", "partial"] as const;

/** The body without its display-only parameters: what identifies the view the server builds. */
export function computeParams(p: Record<string, string>): Record<string, string> {
  const out = { ...p };
  for (const k of DISPLAY_ONLY_PARAMS) delete out[k];
  return out;
}

/** Bands selected for display: "6" → [6]; "rgb:4,5,6" → [4,5,6] (RGB presets resolved by the server). */
export function selectedBands(bands: string): { list: number[]; rgb: boolean; preset: string | null } {
  if (bands.startsWith("rgb:")) {
    const rest = bands.slice(4);
    if (/^[1-6],[1-6],[1-6]$/.test(rest)) return { list: rest.split(",").map(Number), rgb: true, preset: null };
    return { list: [], rgb: true, preset: rest };
  }
  return { list: bands.split(",").map(Number).filter((b) => b >= 1 && b <= 6), rgb: false, preset: null };
}
