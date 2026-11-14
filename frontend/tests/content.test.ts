/** Content in step with its owners: flag tables (I's flags.py), credits (understanding.md §4.8), missions. */
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";
import { CANONICAL_BITS, FLAG_INFO } from "../src/content/flags";
import { CREDITS, UNVERIFIED } from "../src/content/credits";
import { CHALLENGE, MISSIONS, missionFor } from "../src/content/missions";
import { CAPABILITIES } from "../src/lib/features";
import { HOME_TEXT, MISSION_TEXT, missionText } from "../src/content/translations";

const root = resolve(__dirname, "../..");
const flagsPy = readFileSync(resolve(root, "backend/spherex/flags.py"), "utf8");
const understanding = readFileSync(resolve(root, "understanding.md"), "utf8");

describe("flag tables match backend/spherex/flags.py", () => {
  it("CANONICAL_BITS", () => {
    const block = flagsPy.slice(flagsPy.indexOf("CANONICAL_BITS = {"), flagsPy.indexOf("}", flagsPy.indexOf("CANONICAL_BITS = {")));
    const py = Object.fromEntries([...block.matchAll(/"([A-Z_]+)":\s*(\d+)/g)].map((m) => [m[1]!, Number(m[2])]));
    expect(CANONICAL_BITS).toEqual(py);
  });
  it("FLAG_INFO", () => {
    const start = flagsPy.indexOf("FLAG_INFO = {");
    const block = flagsPy.slice(start, flagsPy.indexOf("}\n", start));
    // join Python's implicit string concatenation, then read "KEY": "text"
    const joined = block.replace(/"\s*\n\s*"/g, "");
    const py = Object.fromEntries([...joined.matchAll(/"([A-Z_]+)":\s*"([^"]*)"/g)].map((m) => [m[1]!, m[2]!]));
    expect(FLAG_INFO).toEqual(py);
  });
});

describe("credits (P0-7)", () => {
  it("quote the SPHEREx acknowledgement verbatim from understanding.md §4.8, with both DOIs", () => {
    const sp = CREDITS.find((c) => c.id === "spherex")!;
    expect(sp.verbatim).toBe(true);
    expect(understanding.replace(/\s+/g, " ")).toContain(sp.text);
    expect(sp.dois).toEqual(["10.26131/IRSA652", "10.26131/IRSA662"]);
  });
  it("cover every acknowledgement understanding.md §4.8 lists", () => {
    for (const id of ["spherex", "irsa", "gaia", "2mass", "wise", "simbad", "aladin", "horizons", "skybot", "aavso"]) {
      expect(CREDITS.some((c) => c.id === id)).toBe(true);
    }
  });
  it.runIf(process.env.RELEASE === "1")("release check: every acknowledgement re-checked verbatim against its source page", () => {
    expect(UNVERIFIED).toEqual([]);
  });
});

describe("missions", () => {
  it("cover the five acceptance targets and match resolver names", () => {
    expect(MISSIONS.map((m) => m.id)).toEqual(["barnard", "epsindb", "wise0855", "rwaur", "rdra"]);
    expect(missionFor(["NAME Barnard's star"])?.id).toBe("barnard");
    expect(missionFor(["* eps Ind B"])?.id).toBe("epsindb");
    expect(missionFor(["ε Indi B"])?.id).toBe("epsindb");
    expect(missionFor(["WISEA J085510.74-071442.5"])?.id).toBe("wise0855");
    expect(missionFor(["V* RW Aur"])?.id).toBe("rwaur");
    expect(missionFor(["V* R Dra"])?.id).toBe("rdra");
    expect(missionFor(["Vega"])).toBeNull();
  });
  it("quote no measured numbers (claims rule, workflow.md §4.1): numbers come from the live API", () => {
    // allowed: band names ("band 6") and product parameters ("14-day bins"); nothing else
    const strip = (s: string) => s.replace(/\bbands? \d\b/gi, "").replace(/\b\d+-day\b/g, "");
    for (const m of MISSIONS) for (const s of [m.hook, ...m.look]) expect(strip(s)).not.toMatch(/\d/);
  });
  it("tie a step to a capability only with one entry per step and a known capability", () => {
    for (const m of MISSIONS) {
      if (!m.lookNeeds) continue;
      expect(m.lookNeeds, m.id).toHaveLength(m.look.length);
      for (const c of m.lookNeeds) if (c) expect(Object.keys(CAPABILITIES), m.id).toContain(c);
    }
    expect(MISSIONS.find((m) => m.id === "barnard")!.lookNeeds?.[2]).toBe("track");   // the track is not public yet
  });
  it("never call WISE 0855 empty in the short bands (a field star sits on it)", () => {
    const w = MISSIONS.find((m) => m.id === "wise0855")!;
    expect([w.hook, ...w.look].join(" ")).not.toMatch(/\bempty\b|nothing (at|in) (band|1)/i);
  });
});

describe("demo entry points open pinned, prewarmed views (audit F-01 to F-04)", () => {
  const index = JSON.parse(readFileSync(resolve(root, "config/pins/index.json"), "utf8")) as Record<string, { pin: string }>;
  const demo = readFileSync(resolve(root, "config/demo_views.yaml"), "utf8");
  it("every mission carries the committed pin of its target", () => {
    for (const m of MISSIONS) {
      expect(m.pin, m.id).toBe(index[m.id]?.pin);
      expect(() => readFileSync(resolve(root, `config/pins/${m.pin}.json`))).not.toThrow();
      expect(demo, m.id).toContain(`q: "${m.q}", pin: "${m.pin}"`);
    }
  });
  it("the challenge coordinate opens the prewarmed 12′ WISE 0855 view", () => {
    expect(CHALLENGE.pin).toBe(index.wise0855!.pin);
    expect(demo).toContain(`ra: "${CHALLENGE.ra}", dec: "${CHALLENGE.dec}", pin: "${CHALLENGE.pin}", bands: "6", fov: "${CHALLENGE.fov}"`);
    expect(demo).toContain(`q: "WISE 0855-0714", pin: "${CHALLENGE.pin}", bands: "6", fov: "${CHALLENGE.fov}"`);
  });
});

describe("translations (optimisation.md IMP-5)", () => {
  const langs = Object.keys(MISSION_TEXT) as (keyof typeof MISSION_TEXT)[];
  it("give every mission the same steps in every language", () => {
    for (const lang of langs) {
      expect(Object.keys(MISSION_TEXT[lang]).sort()).toEqual(MISSIONS.map((m) => m.id).sort());
      for (const m of MISSIONS) {
        const t = missionText(m, lang);
        expect(t.look).toHaveLength(m.look.length);
        expect(t.title).not.toBe(m.title);
      }
    }
    expect(missionText(MISSIONS[0]!, "en").title).toBe(MISSIONS[0]!.title);
  });
  it("quote no measured numbers either: only band names and the 14-day bin size", () => {
    const strip = (s: string) => s.replace(/(bandas?|बैंड) \d/gi, "").replace(/\b14\b/g, "");
    for (const lang of langs) for (const t of Object.values(MISSION_TEXT[lang])) for (const s of [t.title, t.hook, ...t.look]) expect(strip(s)).not.toMatch(/\d/);
  });
  it("translate every home-page string", () => {
    const keys = Object.keys(HOME_TEXT.en).sort();
    for (const lang of langs) {
      expect(Object.keys(HOME_TEXT[lang]).sort()).toEqual(keys);
      for (const k of keys) expect(HOME_TEXT[lang][k as keyof typeof HOME_TEXT.en].trim()).not.toBe("");
    }
  });
});
