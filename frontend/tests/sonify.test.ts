import { describe, expect, it } from "vitest";
import { schedule } from "../src/lib/sonify";

describe("sonify", () => {
  it("maps λ to rising pitch and flux to loudness, sorted by λ", () => {
    const s = schedule([{ lam: 5, flux: 1 }, { lam: 0.75, flux: 2 }]);
    expect(s[0]!.hz).toBeCloseTo(220);
    expect(s[1]!.hz).toBeCloseTo(1760);
    expect(s[0]!.gain).toBeCloseTo(0.3);
    expect(s[1]!.gain).toBeCloseTo(0.15);
  });
  it("is silent without positive flux", () => {
    expect(schedule([{ lam: 2, flux: -1 }])).toEqual([]);
  });
});
