/** CPU twin ↔ backend render.stretch (values from its formula: arcsinh(t·β)/arcsinh(β), log1p, sqrt). */
import { describe, expect, it } from "vitest";
import { parseStretch, stretchValue } from "../src/lib/stretch";
import { lut, luminance, type CmapName } from "../src/gl/colormaps";

const X = [-1, 0, 0.25, 0.5, 1, 2];
const EXPECTED: Record<string, number[]> = {
  lin: [0, 0, 0.25, 0.5, 1, 1],
  asinh: [0, 0, 0.519953138, 0.754451093, 1, 1],
  log: [0, 0, 0.5, 0.73248676, 1, 1],
  sqrt: [0, 0, 0.5, 0.707106781, 1, 1],
};

describe("stretch", () => {
  for (const [mode, exp] of Object.entries(EXPECTED)) {
    it(`${mode} matches backend render.stretch`, () => {
      const spec = parseStretch(mode === "lin" || mode === "sqrt" ? mode : `${mode}:8`);
      X.forEach((x, i) => expect(stretchValue(x, 0, 1, spec)).toBeCloseTo(exp[i]!, 7));
    });
  }
  it("diverging is symmetric about 0 and clips at ±hi", () => {
    const s = { mode: "diverging" as const, beta: 1 };
    expect(stretchValue(0, -5, 5, s)).toBe(0.5);
    expect(stretchValue(5, -5, 5, s)).toBe(1);
    expect(stretchValue(-10, -5, 5, s)).toBe(0);
    expect(stretchValue(2.5, -5, 5, s)).toBe(0.75);
  });
  it("treats the sentinel and NaN as no data", () => {
    expect(Number.isNaN(stretchValue(-65504, 0, 1, parseStretch("lin")))).toBe(true);
    expect(Number.isNaN(stretchValue(NaN, 0, 1, parseStretch("lin")))).toBe(true);
  });
  it("defaults unknown specs to asinh:8", () => {
    expect(parseStretch("nonsense")).toEqual({ mode: "asinh", beta: 8 });
    expect(parseStretch(null)).toEqual({ mode: "asinh", beta: 8 });
  });
});

describe("colormaps", () => {
  it.each(["gray", "magma", "cividis"] as CmapName[])("%s is monotonic in lightness (readable without hue)", (name) => {
    const t = lut(name);
    let prev = -1;
    for (let i = 0; i < 256; i += 8) {
      const L = luminance([t[4 * i]!, t[4 * i + 1]!, t[4 * i + 2]!]);
      expect(L).toBeGreaterThanOrEqual(prev - 1e-3);
      prev = L;
    }
  });
  it("diverging is light at 0 and dark at both ends", () => {
    const t = lut("diverging");
    const L = (i: number) => luminance([t[4 * i]!, t[4 * i + 1]!, t[4 * i + 2]!]);
    expect(L(128)).toBeGreaterThan(L(0) * 5);
    expect(L(128)).toBeGreaterThan(L(255) * 5);
  });
});
