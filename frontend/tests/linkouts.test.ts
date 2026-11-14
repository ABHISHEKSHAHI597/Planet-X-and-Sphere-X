/** Link-outs and the plain-text candidate report (optimisation.md IMP-3). */
import { describe, expect, it } from "vitest";
import { linkOuts, reportText } from "../src/lib/linkouts";

describe("link-outs", () => {
  it("opens the same position elsewhere, with WiseView's size in arcseconds", () => {
    const l = Object.fromEntries(linkOuts(133.7947, -7.2451, 6).map((x) => [x.id, x.url]));
    expect(l.wiseview).toBe("http://byw.tools/wiseview#ra=133.79470&dec=-7.24510&size=360");
    expect(l.legacy).toContain("ra=133.79470&dec=-7.24510");
    expect(l.simbad).toContain("Coord=133.79470+-7.24510");
    expect(Object.fromEntries(linkOuts(10, 4.5, 6).map((x) => [x.id, x.url])).simbad).toContain("Coord=10.00000+%2B4.50000");
    expect(linkOuts(10, 4.5, 60)[0]!.url).toContain("size=2000");      // WiseView's own cap
  });

  it("writes a report a forum can use, and never calls it a discovery", () => {
    const t = reportText({ kind: "mover", ra: 133.7947, dec: -7.2451, target: "WISE 0855-0714", band: 6, note: " moves west ",
      visits: [{ label: "V2", date: "2025-11-12" }, { label: "V4", date: "2026-04-28" }], permalink: "https://example.org/?q=x&pin=abc" });
    expect(t).toContain("Candidate mover near WISE 0855-0714");
    expect(t).toContain("133.79470 -7.24510");
    expect(t).toContain("V2 (2025-11-12); V4 (2026-04-28)");
    expect(t).toContain("Note: moves west");
    expect(t).toContain("View: https://example.org/?q=x&pin=abc");
    expect(t).toContain("candidate, not a discovery");
  });
});
