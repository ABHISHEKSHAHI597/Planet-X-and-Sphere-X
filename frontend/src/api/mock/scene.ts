/**
 * MOCK synthetic stacks for frontend development (workflow.md §8.5). Seeded, generated at request
 * time, never committed. Static stars are identical in every bin (only the noise changes), the target
 * moves with its catalogue PM, so the blink, overlays and the mock difference behave plausibly.
 * Nothing here is a SPHEREx measurement.
 */
import type { GridInfo } from "../types";
import { mjdToDecimalYear } from "../../lib/time";
import { skyToPixel } from "../../lib/wcs";
import { PIXEL_ARCSEC } from "../../lib/constants";
import { propagateLinear, type MockTarget } from "./targets";

export function mulberry32(seed: number): () => number {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

export function hashString(s: string): number {
  let h = 2166136261;
  for (let i = 0; i < s.length; i++) { h ^= s.charCodeAt(i); h = Math.imul(h, 16777619); }
  return h >>> 0;
}

function gauss(r: () => number): number {
  const u = Math.max(1e-12, r()), v = r();
  return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v);
}

export function makeGrid(ra: number, dec: number, fov: number, px: number): GridInfo {
  const n = Math.floor((fov * 60) / px) | 1;
  return {
    ctype: ["RA---TAN", "DEC--TAN"], crval: [ra, dec], crpix: [(n + 1) / 2, (n + 1) / 2],
    cdelt: [-px / 3600, px / 3600], shape: [n, n], pix_arcsec: px, native: px >= PIXEL_ARCSEC * 0.999,
  };
}

/** Static field stars of a mock view: same positions in every bin (seeded on the view, not the bin). */
export function fieldStars(grid: GridInfo, seedKey: string): { col: number; row: number; peak: (band: number) => number }[] {
  const [ny, nx] = grid.shape;
  const r = mulberry32(hashString(`${seedKey}|field`));
  const n = Math.round((45 * nx * ny) / (121 * 121));
  const out = [];
  for (let k = 0; k < n; k++) {
    const col = r() * nx, row = r() * ny;
    const colour = 0.5 + r();                                         // per-star spectral slope
    const amp = 0.06 / Math.pow(r() + 0.02, 1.2);
    out.push({ col, row, peak: (band: number) => Math.min(40, amp * Math.pow(colour, (3.5 - band) / 2)) });
  }
  return out;
}

export interface SceneStack { data: Float32Array; var: Float32Array; flags: Uint32Array; target: { col: number; row: number } | null }

const SKY_SIGMA = 0.02;                 // MJy/sr per stack pixel (arbitrary mock scale)
const BIT = { OVERFLOW: 1, OUTLIER: 19, SOURCE: 21 } as const;

export function sceneStack(o: {
  grid: GridInfo; band: number; mjd: number; nFrames: number; target: MockTarget | null; seedKey: string; partial: boolean;
}): SceneStack {
  const [ny, nx] = o.grid.shape;
  const N = nx * ny;
  const truth = new Float32Array(N);
  const src = new Uint8Array(N);
  const sigmaPsf = (1.46 * PIXEL_ARCSEC) / o.grid.pix_arcsec / 2.355;
  const addStar = (cx: number, cy: number, peak: number) => {
    const r = Math.ceil(4 * sigmaPsf);
    for (let y = Math.max(0, Math.floor(cy - r)); y <= Math.min(ny - 1, Math.ceil(cy + r)); y++) {
      for (let x = Math.max(0, Math.floor(cx - r)); x <= Math.min(nx - 1, Math.ceil(cx + r)); x++) {
        const v = peak * Math.exp(-((x - cx) ** 2 + (y - cy) ** 2) / (2 * sigmaPsf ** 2));
        truth[y * nx + x]! += v;
        if (v > 3 * SKY_SIGMA) src[y * nx + x] = 1;
      }
    }
  };
  for (const s of fieldStars(o.grid, o.seedKey)) addStar(s.col, s.row, s.peak(o.band));
  let tpos: { col: number; row: number } | null = null;
  const lk = o.target?.look;
  if (o.target && lk) {
    const year = mjdToDecimalYear(o.mjd);
    const p = propagateLinear(o.target, year);
    tpos = skyToPixel(o.grid, p.ra, p.dec);
    let peak = (lk.bright[o.band - 1] ?? 0) * 0.1;
    if (lk.period) peak *= Math.pow(10, -0.4 * lk.period[1] * 0.5 * Math.sin((2 * Math.PI * o.mjd) / lk.period[0]));
    if (tpos && peak > 0) addStar(tpos.col, tpos.row, peak);
    if (lk.neighbour) {
      // A STATIC field star: fixed on the sky (offset from the target's 2026.0 position), same in every bin.
      const ref = propagateLinear(o.target, 2026.0);
      const nra = ref.ra + lk.neighbour.dxe / 3600 / Math.cos((ref.dec * Math.PI) / 180);
      const np = skyToPixel(o.grid, nra, ref.dec + lk.neighbour.dyn / 3600);
      if (np) addStar(np.col, np.row, (lk.neighbour.bright[o.band - 1] ?? 0) * 0.1);
    }
  }
  const noise = mulberry32(hashString(`${o.seedKey}|${o.band}|${o.mjd.toFixed(3)}`));
  const sig = SKY_SIGMA * Math.sqrt(20 / Math.max(1, o.nFrames));      // partial visits are noisier
  const data = new Float32Array(N), variance = new Float32Array(N), flags = new Uint32Array(N);
  for (let i = 0; i < N; i++) {
    const v = sig * sig + 0.002 * Math.abs(truth[i]!) * sig;
    variance[i] = v;
    data[i] = truth[i]! + Math.sqrt(v) * gauss(noise);
    if (src[i]) flags[i]! |= 1 << BIT.SOURCE;
    if (noise() < 0.0008) flags[i]! |= 1 << BIT.OUTLIER;
  }
  if (tpos && lk?.holes?.includes(o.band)) {
    const r0 = (1.2 * PIXEL_ARCSEC) / o.grid.pix_arcsec, r1 = 2.6 * r0;
    for (let y = 0; y < ny; y++) for (let x = 0; x < nx; x++) {
      const r = Math.hypot(x - tpos.col, y - tpos.row);
      if (r < r1) flags[y * nx + x]! |= 1 << BIT.OVERFLOW;
      if (r < r0) { data[y * nx + x] = NaN; variance[y * nx + x] = NaN; }
    }
  }
  if (o.partial) {                                            // partial coverage: a strip with no data
    const w = Math.max(2, Math.floor(nx / 8));
    for (let y = 0; y < ny; y++) for (let x = nx - w; x < nx; x++) { data[y * nx + x] = NaN; variance[y * nx + x] = NaN; }
  }
  return { data, var: variance, flags, target: tpos };
}

/** NaN-aware median-stack limits, a stand-in for the server's ZScale (render.shared_limits). */
export function mockLimits(stacks: Float32Array[]): { lo: number; hi: number } {
  if (!stacks.length) return { lo: 0, hi: 1 };
  const n = stacks[0]!.length;
  const med: number[] = [];
  const buf: number[] = [];
  for (let i = 0; i < n; i += 3) {
    buf.length = 0;
    for (const s of stacks) { const v = s[i]!; if (Number.isFinite(v)) buf.push(v); }
    if (!buf.length) continue;
    buf.sort((a, b) => a - b);
    med.push(buf[buf.length >> 1]!);
  }
  med.sort((a, b) => a - b);
  if (!med.length) return { lo: 0, hi: 1 };
  const q = (f: number) => med[Math.min(med.length - 1, Math.max(0, Math.round(f * (med.length - 1))))]!;
  const lo = q(0.05), hi = q(0.995);
  return { lo, hi: hi > lo ? hi : lo + 1 };
}
