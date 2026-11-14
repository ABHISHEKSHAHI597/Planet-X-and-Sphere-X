/**
 * 256-entry RGBA LUTs (implementation.md §6.7: colour-blind-safe sequential cividis/magma, a
 * diverging blue–white–red map; never encode by hue alone). gray/cividis/magma vary monotonically
 * in lightness; the diverging map is dark at both ends and light at 0.
 *
 * These tables are the frontend's authority. scripts/export_colormaps.mjs writes them to
 * fixtures/colormaps.json so P's PNG renderer (app/render_png.py) can use byte-identical LUTs, and the
 * two viewers look the same (CONTRACTS.md, "Colormaps").
 */
export type CmapName = "gray" | "magma" | "cividis" | "diverging";
export const SEQUENTIAL_CMAPS: CmapName[] = ["gray", "magma", "cividis"];

type RGB = [number, number, number];

function fromStops(stops: RGB[]): (t: number) => RGB {
  return (t) => {
    const x = Math.min(1, Math.max(0, t)) * (stops.length - 1);
    const i = Math.min(stops.length - 2, Math.floor(x));
    const f = x - i;
    const a = stops[i]!, b = stops[i + 1]!;
    return [a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f, a[2] + (b[2] - a[2]) * f];
  };
}

// matplotlib magma, 6th-order polynomial fit (matches #000004 #51127c #b73779 #fc8961 #fcfdbf ±6/255).
const MAGMA = [
  [-0.002136485053939582, -0.000749655052795221, -0.005386127855323933],
  [0.2516605407371642, 0.6775232436837668, 2.494026599312351],
  [8.353717279216625, -3.577719514958484, 0.3144679030132573],
  [-27.66873308576866, 14.26473078096533, -13.64921318813922],
  [52.17613981234068, -27.94360607168351, 12.94416944238394],
  [-50.76852536473588, 29.04658282127291, 4.23415299384598],
  [18.65570506591883, -11.48977351997711, -5.601961508734096],
];
const magma = (t: number): RGB => {
  const c = [0, 1, 2].map((i) => MAGMA.reduceRight((acc, k) => acc * t + k[i]!, 0) * 255);
  return c as RGB;
};
// cividis (Nuñez et al. 2018), 5 stops: #00204D #414D6B #7C7B78 #BCAF6F #FFEA46
const cividis = fromStops([[0, 32, 77], [65, 77, 107], [124, 123, 120], [188, 175, 111], [255, 234, 70]]);
// ColorBrewer RdBu reversed: #053061 #4393c3 #f7f7f7 #d6604d #67001f (negative = blue, positive = red)
const diverging = fromStops([[5, 48, 97], [67, 147, 195], [247, 247, 247], [214, 96, 77], [103, 0, 31]]);
const gray = (t: number): RGB => [255 * t, 255 * t, 255 * t];

const FN: Record<CmapName, (t: number) => RGB> = { gray, magma, cividis, diverging };

const cache = new Map<CmapName, Uint8Array>();

/** 256×1 RGBA LUT for the shader (u_cmap) and the CPU twin. */
export function lut(name: CmapName): Uint8Array {
  const hit = cache.get(name);
  if (hit) return hit;
  const f = FN[name] ?? gray;
  const out = new Uint8Array(256 * 4);
  for (let i = 0; i < 256; i++) {
    const [r, g, b] = f(i / 255);
    out[4 * i] = Math.round(Math.min(255, Math.max(0, r)));
    out[4 * i + 1] = Math.round(Math.min(255, Math.max(0, g)));
    out[4 * i + 2] = Math.round(Math.min(255, Math.max(0, b)));
    out[4 * i + 3] = 255;
  }
  cache.set(name, out);
  return out;
}

/** "No data" tint: never black, so a hole is never mistaken for empty sky (implementation.md §6.3). */
export const NODATA_RGB: RGB = [Math.round(0.18 * 255), Math.round(0.10 * 255), Math.round(0.22 * 255)];
/** Outside the grid (pan/zoom margins). */
export const OUTSIDE_RGB: RGB = [12, 12, 16];

/** Relative luminance (sRGB), used by the monotonicity test. */
export function luminance([r, g, b]: RGB | number[]): number {
  const lin = (c: number) => { const s = c / 255; return s <= 0.04045 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4; };
  return 0.2126 * lin(r!) + 0.7152 * lin(g!) + 0.0722 * lin(b!);
}
