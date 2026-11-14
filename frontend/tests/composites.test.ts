import { describe, expect, it } from "vitest";
import { CUBE_PLANES, planeRange } from "../src/components/Flipbook";
import { composeRGB, percentileLimits, rgbPlan } from "../src/components/RgbCanvas";
import { BANDS } from "../src/lib/constants";

describe("λ-scrubber plane ranges", () => {
  it("tile each band exactly in ln λ (cube.spectral_cube binning)", () => {
    for (const b of [1, 2, 3, 4, 5, 6]) {
      const [lo, hi] = BANDS[b]!;
      expect(planeRange(b, 0)[0]).toBeCloseTo(lo, 10);
      expect(planeRange(b, CUBE_PLANES - 1)[1]).toBeCloseTo(hi, 10);
      for (let k = 1; k < CUBE_PLANES; k++) expect(planeRange(b, k)[0]).toBeCloseTo(planeRange(b, k - 1)[1], 12);
    }
  });
});

describe("RGB composites", () => {
  it("parse band triplets and presets; unknown presets are refused, not guessed", () => {
    expect(rgbPlan("rgb:4,5,6")).toEqual({ kind: "bands", bands: [4, 5, 6] });
    expect(rgbPlan("rgb:thermal")).toEqual({ kind: "bands", bands: [4, 5, 6] });
    expect(rgbPlan("rgb:methane")).toEqual({ kind: "range", preset: "methane" });
    expect(rgbPlan("rgb:ice")).toEqual({ kind: "range", preset: "ice" });
    expect(rgbPlan("rgb:pah")).toBeNull();
  });
  it("flips rows (row 0 south at the bottom) and keeps no-data distinct from black", () => {
    const nx = 2, ny = 2;
    const r = new Float32Array([1, NaN, 0, NaN]), g = new Float32Array([0, NaN, 0, NaN]), b = new Float32Array([0, NaN, 1, NaN]);
    const out = composeRGB([r, g, b], [{ lo: 0, hi: 1 }, { lo: 0, hi: 1 }, { lo: 0, hi: 1 }], nx, ny, { mode: "lin", beta: 1 });
    // source row 0 (south) → output row 1 (bottom)
    expect(Array.from(out.slice(8, 11))).toEqual([255, 0, 0]);
    expect(Array.from(out.slice(0, 3))).toEqual([0, 0, 255]);
    // all-NaN pixel is the no-data colour, not black
    expect(Array.from(out.slice(12, 15))).not.toEqual([0, 0, 0]);
  });
  it("robust limits ignore NaN and outliers", () => {
    const a = new Float32Array(1000).map((_, i) => i / 999);
    a[0] = NaN; a[1] = 1e6;
    const l = percentileLimits(a);
    expect(l.lo).toBeGreaterThan(0);
    expect(l.hi).toBeLessThan(1.01);
  });
});
