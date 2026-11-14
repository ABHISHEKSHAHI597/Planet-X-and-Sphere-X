import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";
import { DEFAULTS, parseURL, selectedBands, toSearch, viewParams } from "../src/state/url";

const fixtures = readFileSync(resolve(__dirname, "../fixtures/urls/demo-links.txt"), "utf8")
  .split("\n").map((l) => l.trim()).filter((l) => l && !l.startsWith("#"));

describe("URL schema (implementation.md §5.3)", () => {
  it.each(fixtures)("fixture %s parses without warnings and is canonical", (u) => {
    const { state, warnings } = parseURL(u);
    expect(warnings).toEqual([]);
    expect(toSearch(state)).toBe(u);
  });

  it("omits defaults, so the empty state is the empty query", () => {
    expect(toSearch(DEFAULTS)).toBe("");
  });

  it("round-trips a full state", () => {
    const s = { ...DEFAULTS, q: "Barnard's Star", fov: 12, px: 6.15, axis: "bin:14d", partial: true, bands: "rgb:4,5,6", mode: "diff" as const,
      a: "V1", b: "V5", stretch: "lin", lim: "manual:-0.1,2.5", cmap: "magma" as const, fps: 4, center: "track" as const,
      ov: ["gaia", "simbad"], flags: ["OVERFLOW", "OUTLIER"], mask: "bright", rel: "qr3", pin: "3fa9c27e01bd", sel: "269.4461,4.7707", t: "V3", ui: "expert" as const };
    expect(parseURL(toSearch(s)).state).toEqual(s);
  });

  it("ignores unknown parameters with a warning and keeps aliases working", () => {
    const { state, warnings } = parseURL("?band=5&target=R%20Dra&foo=1&speed=4");
    expect(state.bands).toBe("5");
    expect(state.q).toBe("R Dra");
    expect(state.fps).toBe(4);
    expect(warnings).toEqual(['ignored unknown URL parameter "foo"']);
  });

  it("rejects invalid values instead of passing them on", () => {
    const { state, warnings } = parseURL("?bands=7&mode=explode&pin=XYZ&fov=999&lim=evil()");
    expect(state.bands).toBe("6");
    expect(state.mode).toBe("blink");
    expect(state.pin).toBeNull();
    expect(state.fov).toBe(30);                      // clamped to the P0-4 range
    expect(state.lim).toBe("zscale");
    expect(warnings.length).toBe(4);
  });

  it("normalises Unicode minus in names and coordinates", () => {
    expect(parseURL("?q=WISE%200855%E2%88%920714").state.q).toBe("WISE 0855-0714");
    expect(parseURL("?ra=08:55:10.831&dec=%E2%88%9207:14:42.53").state.dec).toBe("-07:14:42.53");
  });

  it("explicit coordinates win over q", () => {
    expect(parseURL("?q=Barnard&ra=1&dec=2").state.q).toBeNull();
  });

  it("accepts the debug flag gl=0 silently", () => {
    expect(parseURL("?q=x&gl=0").warnings).toEqual([]);
  });

  it("sends only science parameters to POST /views", () => {
    const p = viewParams({ ...DEFAULTS, q: "R Dra", cmap: "magma", fps: 8, ui: "simple" });
    expect(p).toEqual({ q: "R Dra", fov: "6", px: "3", axis: "auto", partial: "0", bands: "6", center: "fixed", mask: "auto", rel: "auto", lim: "zscale" });
  });

  it("parses band selections", () => {
    expect(selectedBands("6")).toEqual({ list: [6], rgb: false, preset: null });
    expect(selectedBands("rgb:4,5,6")).toEqual({ list: [4, 5, 6], rgb: true, preset: null });
    expect(selectedBands("rgb:methane")).toEqual({ list: [], rgb: true, preset: "methane" });
  });
});
