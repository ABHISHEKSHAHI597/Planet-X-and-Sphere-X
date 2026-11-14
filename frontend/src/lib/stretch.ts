/**
 * Stretch: the CPU twin of the WebGL shader (gl/shaders.ts) and of backend render.stretch.
 * Used by the loupe, the mock PNG renderer and tests. The three implementations must agree:
 * tests/stretch.test.ts pins values computed with backend/spherex/render.py.
 */
import { NODATA_THRESHOLD } from "./half";
import { lut, NODATA_RGB, type CmapName } from "../gl/colormaps";

export type StretchMode = "lin" | "asinh" | "log" | "sqrt" | "diverging";

export interface StretchSpec { mode: StretchMode; beta: number }

/** "asinh:8" → {mode: asinh, beta: 8}; unknown → asinh:8 (the default, implementation.md §5.3). */
export function parseStretch(s: string | null | undefined): StretchSpec {
  const [m = "asinh", b] = (s ?? "asinh:8").split(":");
  const mode = (["lin", "asinh", "log", "sqrt"].includes(m) ? m : "asinh") as StretchMode;
  const beta = b !== undefined && Number.isFinite(Number(b)) && Number(b) > 0 ? Number(b) : 8;
  return { mode, beta };
}

export function formatStretch(s: StretchSpec): string {
  return s.mode === "asinh" || s.mode === "log" ? `${s.mode}:${s.beta}` : s.mode;
}

/** Shader mode ids (u_mode). */
export const MODE_ID: Record<StretchMode, number> = { lin: 0, asinh: 1, log: 2, sqrt: 3, diverging: 4 };

/** x → t ∈ [0, 1]; NaN for no data. Same algebra as the fragment shader. */
export function stretchValue(x: number, lo: number, hi: number, spec: StretchSpec): number {
  if (!(x >= NODATA_THRESHOLD) || Number.isNaN(x)) return NaN;
  if (spec.mode === "diverging") return Math.min(1, Math.max(0, 0.5 + 0.5 * x / hi));
  let t = Math.min(1, Math.max(0, (x - lo) / (hi - lo)));
  if (spec.mode === "asinh") t = Math.asinh(t * spec.beta) / Math.asinh(spec.beta);
  else if (spec.mode === "log") t = Math.log(1 + t * spec.beta) / Math.log(1 + spec.beta);
  else if (spec.mode === "sqrt") t = Math.sqrt(t);
  return t;
}

/**
 * Render a row0south float image to top-row-first RGBA (HTML canvas / PNG convention).
 * This is the ONE place the CPU path flips rows (implementation.md §6.3: libraries that treat row 0
 * as the top need a flip; WebGL does not).
 */
export function renderRGBA(data: Float32Array, nx: number, ny: number, lo: number, hi: number,
  spec: StretchSpec, cmap: CmapName): Uint8ClampedArray {
  const table = lut(spec.mode === "diverging" ? "diverging" : cmap);
  const out = new Uint8ClampedArray(nx * ny * 4);
  for (let row = 0; row < ny; row++) {
    const top = ny - 1 - row;                       // row 0 (south) → bottom of the image
    for (let col = 0; col < nx; col++) {
      const t = stretchValue(data[row * nx + col]!, lo, hi, spec);
      const o = 4 * (top * nx + col);
      if (Number.isNaN(t)) {
        out[o] = NODATA_RGB[0]; out[o + 1] = NODATA_RGB[1]; out[o + 2] = NODATA_RGB[2];
      } else {
        const i = Math.min(255, Math.max(0, Math.round(t * 255)));
        out[o] = table[4 * i]!; out[o + 1] = table[4 * i + 1]!; out[o + 2] = table[4 * i + 2]!;
      }
      out[o + 3] = 255;
    }
  }
  return out;
}

/** ZScale-like fallback limits on the CPU (used only when a manifest has no limits, e.g. the F14 page). */
export function percentileLimits(data: Float32Array, p = 99.5): { lo: number; hi: number } {
  const v = Array.from(data).filter((x) => Number.isFinite(x)).sort((a, b) => a - b);
  if (!v.length) return { lo: 0, hi: 1 };
  const q = (f: number) => v[Math.min(v.length - 1, Math.max(0, Math.round(f * (v.length - 1))))]!;
  const lo = q(1 - p / 100), hi = q(p / 100);
  return hi > lo ? { lo, hi } : { lo, hi: lo + 1 };
}
