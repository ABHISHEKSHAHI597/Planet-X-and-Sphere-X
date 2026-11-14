import { describe, expect, it } from "vitest";
import { formatDec, formatRA, looksLikeCoordinates, parseCoordinates, parseDec, parseRA } from "../src/lib/coords";

describe("coordinate parsing (P0-1)", () => {
  it("parses the challenge's WISE 0855 coordinate", () => {
    const c = parseCoordinates("08h55m10.831s -07d14m42.53s")!;
    expect(c.ra).toBeCloseTo(15 * (8 + 55 / 60 + 10.831 / 3600), 8);
    expect(c.dec).toBeCloseTo(-(7 + 14 / 60 + 42.53 / 3600), 8);
  });
  it.each([
    ["08:55:10.831 -07:14:42.53"], ["08 55 10.831 -07 14 42.53"], ["08:55:10.831, -07:14:42.53"],
    ["08:55:10.831 −07:14:42.53"], ["08:55:10.831 –07°14′42.53″"],
  ])("accepts %s", (s) => {
    const c = parseCoordinates(s)!;
    expect(c.ra).toBeCloseTo(133.795129, 5);
    expect(c.dec).toBeCloseTo(-7.245147, 5);
  });
  it("parses decimal degrees", () => {
    expect(parseCoordinates("269.4461 4.7707")).toEqual({ ra: 269.4461, dec: 4.7707 });
    expect(parseCoordinates("269.4461, +4.7707")).toEqual({ ra: 269.4461, dec: 4.7707 });
    expect(parseCoordinates("133.795 -7.245")).toEqual({ ra: 133.795, dec: -7.245 });
  });
  it("treats names as names, not coordinates", () => {
    for (const s of ["WISE 0855-0714", "WISE 0855−0714", "Barnard's Star", "eps Ind B", "R Dra", "sso:Pluto", "M 31"]) {
      expect(looksLikeCoordinates(s)).toBe(false);
    }
  });
  it("rejects out-of-range values", () => {
    expect(parseRA("24:00:01")).toBeNull();
    expect(parseRA("361")).toBeNull();
    expect(parseDec("+91")).toBeNull();
    expect(parseDec("10:61:00")).toBeNull();
    expect(parseCoordinates("12 34")).toEqual({ ra: 12, dec: 34 });
  });
  it("formats sexagesimal with Unicode minus", () => {
    expect(formatRA(133.79512917, 2)).toBe("08h55m10.83s");
    expect(formatDec(-7.24514722, 1)).toBe("−07°14′42.5″");
    expect(formatDec(4.7707, 1)).toBe("+04°46′14.5″");
  });
});
