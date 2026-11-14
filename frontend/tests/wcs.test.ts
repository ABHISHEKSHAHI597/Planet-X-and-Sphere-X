import { describe, expect, it } from "vitest";
import { makeGrid } from "../src/api/mock/scene";
import { gridForBin, pixelToSky, positionAngle, sepArcsec, skyToPixel } from "../src/lib/wcs";

describe("TAN grid (north up, east left, row 0 south)", () => {
  const g = makeGrid(269.4461, 4.7707, 6, 3);
  it("is odd and centred on a pixel", () => {
    expect(g.shape).toEqual([121, 121]);
    const c = skyToPixel(g, 269.4461, 4.7707)!;
    expect(c.col).toBeCloseTo(60, 9);
    expect(c.row).toBeCloseTo(60, 9);
  });
  it("puts north at higher rows and east at lower columns", () => {
    const n = skyToPixel(g, 269.4461, 4.7707 + 30 / 3600)!;
    const e = skyToPixel(g, 269.4461 + 30 / 3600 / Math.cos((4.7707 * Math.PI) / 180), 4.7707)!;
    expect(n.row).toBeCloseTo(70, 3);
    expect(e.col).toBeCloseTo(50, 3);
  });
  it("round-trips pixel ↔ sky", () => {
    for (const [c, r] of [[0, 0], [120, 120], [10.3, 99.7]] as const) {
      const s = pixelToSky(g, c, r);
      const p = skyToPixel(g, s.ra, s.dec)!;
      expect(p.col).toBeCloseTo(c, 8);
      expect(p.row).toBeCloseTo(r, 8);
    }
  });
  it("works across RA = 0", () => {
    const g0 = makeGrid(0.001, 10, 6, 3);
    const p = skyToPixel(g0, 359.999, 10)!;
    expect(p.col).toBeGreaterThan(60);                // west of centre → right
  });
  it("separation and PA", () => {
    expect(sepArcsec(10, 0, 10, 1 / 60)).toBeCloseTo(60, 6);
    expect(positionAngle(10, 0, 10, 0.01)).toBeCloseTo(0, 6);
    expect(positionAngle(10, 0, 10.01, 0)).toBeCloseTo(90, 6);
  });
});

describe("track-mode grids (audit F-20)", () => {
  const grid = { ctype: ["RA---TAN", "DEC--TAN"], crval: [10, 0], crpix: [61, 61], cdelt: [-3 / 3600, 3 / 3600], shape: [121, 121], pix_arcsec: 3, native: false } as never;
  const track = [{ bin: "V1", band: 6, ra: 11, dec: 0.5 }];
  it("centres a tracked bin on its own pos(t), and leaves fixed views alone", () => {
    expect(gridForBin({ grid, params: { center: "track" }, track }, "V1", 6).crval).toEqual([11, 0.5]);
    expect(gridForBin({ grid, params: { center: "fixed" }, track }, "V1", 6).crval).toEqual([10, 0]);
    expect(gridForBin({ grid, params: { center: "track" }, track }, "V2", 6).crval).toEqual([10, 0]);
  });
});
