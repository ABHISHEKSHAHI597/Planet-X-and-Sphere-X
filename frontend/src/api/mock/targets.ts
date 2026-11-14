/**
 * MOCK target table. Catalogue astrometry is backend/spherex/constants.py TEST_TARGETS (Gaia DR3 /
 * SIMBAD values, implementation.md §14.1). Visit structure follows validation/G1-time-model (real SIA2
 * MJDs, band 6) so the timeline is exercised on realistic shapes. Pixel data are SYNTHETIC
 * (scene.ts): nothing served by the mock is a measurement and the UI labels it "MOCK".
 */
import { dateToMjd } from "../../lib/time";

export interface MockVisit {
  id: string;
  start: string;              // ISO date
  end: string;
  surveys: (number | null)[];
  status: "full" | "partial" | "bin";
  nVisit: number;             // frames of the visit in all bands
  perBand?: Partial<Record<number, number>>;  // frames in a band (default ≈ nVisit/6)
  missingBands?: number[];
}

export interface MockTarget {
  key: string;
  name: string;
  main_id: string;
  aliases: string[];
  ra: number; dec: number; epoch: number;
  pm: [number, number]; plx: number; rv: number | null;
  otype: string; spt: string | null;
  source: string;
  axis: "visit" | "bin:14d";
  visits: MockVisit[];
  /** synthetic appearance */
  look: {
    /** relative peak brightness per band (1..6) of the target */
    bright: number[];
    /** saturated core → no-data sentinel in these bands (Barnard: F7 found NaN cores in bands 1–4) */
    holes?: number[];
    /** periodic variability (days, amplitude in mag) */
    period?: [number, number];
    /** a static field star at this offset (arcsec E, N) and relative brightness per band */
    neighbour?: { dxe: number; dyn: number; bright: number[] };
  };
}

const d = (s: string) => dateToMjd(new Date(`${s}T00:00:00Z`));
export const mjdOf = d;

export const TARGETS: MockTarget[] = [
  {
    key: "barnard", name: "Barnard's Star", main_id: "NAME Barnard's star",
    aliases: ["barnard's star", "barnards star", "barnard"],
    ra: 269.44850252544, dec: 4.73942005111, epoch: 2016.0, pm: [-801.551, 10362.394], plx: 546.976, rv: -110.47,
    otype: "HPM*", spt: "M4V", source: "Gaia DR3 4472832130942575872", axis: "visit",
    visits: [
      { id: "V1", start: "2025-08-15", end: "2025-08-27", surveys: [2], status: "full", nVisit: 109 },
      { id: "V3", start: "2026-03-19", end: "2026-04-10", surveys: [1], status: "full", nVisit: 113 },
      { id: "V4", start: "2026-05-04", end: "2026-05-05", surveys: [1], status: "partial", nVisit: 8, perBand: { 1: 1, 2: 1, 3: 1, 4: 1, 5: 0, 6: 4 } },
      { id: "V5", start: "2026-08-16", end: "2026-08-20", surveys: [4], status: "full", nVisit: 117 },
    ],
    look: { bright: [60, 70, 70, 50, 30, 25], holes: [1, 2, 3, 4] },
  },
  {
    key: "epsindb", name: "ε Indi B", main_id: "* eps Ind B",
    aliases: ["eps ind b", "eps indi b", "epsilon indi b", "ε indi b", "ε ind b"],
    ra: 331.07645259656, dec: -56.79381206688, epoch: 2016.0, pm: [3981.977, -2466.832], plx: 270.658, rv: null,
    otype: "BrownD*", spt: "T1+T6", source: "Gaia DR3 6412596012146801152 (Ba+Bb photocentre)", axis: "visit",
    visits: [
      { id: "V1", start: "2025-04-29", end: "2025-06-10", surveys: [1, null], status: "full", nVisit: 116 },
      { id: "V2", start: "2025-09-28", end: "2025-11-04", surveys: [2], status: "full", nVisit: 137 },
      { id: "V3", start: "2026-04-29", end: "2026-05-04", surveys: [1], status: "full", nVisit: 74, missingBands: [1, 4] },
      { id: "V4", start: "2026-09-22", end: "2026-09-28", surveys: [4], status: "full", nVisit: 120, missingBands: [1, 4] },
    ],
    look: { bright: [3, 6, 8, 4, 9, 7] },
  },
  {
    key: "wise0855", name: "WISE 0855−0714", main_id: "WISEA J085510.74-071442.5",
    aliases: ["wise 0855", "wise 0855-0714", "wise j0855-0714", "wise j085510.83-071442.5"],
    ra: 133.81890825, dec: -7.247048, epoch: 2000.0, pm: [-8123.7, 673.2], plx: 439.0, rv: null,
    otype: "BrownD*", spt: "Y", source: "SIMBAD J2000 from Kirkpatrick+2021 (linear)", axis: "visit",
    visits: [
      { id: "V1", start: "2025-05-05", end: "2025-05-05", surveys: [2], status: "partial", nVisit: 30, perBand: { 1: 6, 2: 5, 3: 4, 4: 4, 5: 8, 6: 3 } },
      { id: "V2", start: "2025-11-10", end: "2025-11-14", surveys: [1], status: "full", nVisit: 108, perBand: { 6: 16 } },
      { id: "V3", start: "2025-12-12", end: "2025-12-13", surveys: [1], status: "partial", nVisit: 18, perBand: { 1: 3, 2: 3, 3: 3, 4: 3, 5: 3, 6: 3 } },
      { id: "V4", start: "2026-04-21", end: "2026-05-11", surveys: [2], status: "full", nVisit: 100, perBand: { 6: 21 } },
    ],
    // invisible below ≈3.5 µm, but a static G = 16.3 field star sits 0.7–1.35 px away (understanding.md §8.4)
    look: { bright: [0, 0, 0, 0.4, 1.6, 2.2], neighbour: { dxe: -3, dyn: 2, bright: [4, 5, 4, 2, 0.8, 0.6] } },
  },
  {
    key: "rwaur", name: "RW Aurigae", main_id: "V* RW Aur",
    aliases: ["rw aur", "rw aurigae"],
    ra: 76.95654431103, dec: 30.40131614989, epoch: 2016.0, pm: [2.641, -27.398], plx: 6.406, rv: null,
    otype: "TT*", spt: "K1/5e+K5e", source: "Gaia DR3: position of A, PM and plx of B", axis: "visit",
    visits: [
      { id: "V1", start: "2025-09-11", end: "2025-09-20", surveys: [1], status: "full", nVisit: 110 },
      { id: "V2", start: "2026-02-20", end: "2026-03-02", surveys: [2], status: "full", nVisit: 114 },
      { id: "V3", start: "2026-09-13", end: "2026-09-16", surveys: [3], status: "full", nVisit: 109 },
    ],
    look: { bright: [25, 30, 35, 30, 25, 22], period: [90, 0.4] },
  },
  {
    key: "rdra", name: "R Draconis", main_id: "V* R Dra",
    aliases: ["r dra", "r draconis"],
    ra: 248.16737836729, dec: 66.75500674547, epoch: 2016.0, pm: [-20.643, 6.149], plx: 1.251, rv: null,
    otype: "Mi*", spt: "M4.5-6e", source: "Gaia DR3 1648328016354496384", axis: "bin:14d",
    visits: [],   // filled below: 14-day bins over the NEP deep-field coverage
    look: { bright: [80, 90, 95, 80, 60, 50], holes: [1, 2, 3, 4, 5, 6], period: [245, 1.0] },
  },
];

// R Dra: 14-day bins from 2025-04-24; G1 found 16 occupied bins in bands 1, 3, 4, 6 and 6 in bands 2, 5.
{
  const t0 = d("2025-04-24");
  const rdra = TARGETS.find((t) => t.key === "rdra")!;
  const occupied = [0, 2, 4, 6, 9, 11, 13, 15, 18, 20, 22, 25, 27, 29, 32, 35];
  const sparse = new Set([2, 9, 15, 22, 29, 35]);
  for (const k of occupied) {
    const s = new Date((t0 - 40587 + 14 * k) * 86400000).toISOString().slice(0, 10);
    const e = new Date((t0 - 40587 + 14 * k + 12) * 86400000).toISOString().slice(0, 10);
    rdra.visits.push({
      id: `B${k}`, start: s, end: e, surveys: [k < 27 ? (k % 2 ? 2 : 1) : (k % 2 ? 4 : 3)], status: "bin", nVisit: 60,
      missingBands: sparse.has(k) ? [] : [2, 5],
    });
  }
}

export function findTarget(q: string): MockTarget | null {
  const s = q.toLowerCase().replace(/[−–]/g, "-").replace(/\s+/g, " ").trim();
  return TARGETS.find((t) => t.aliases.includes(s) || t.name.toLowerCase() === s || t.main_id.toLowerCase() === s) ?? null;
}

/** Linear PM propagation (mock only; the real resolver uses Gaia + RV and parallax, M's targets.py). */
export function propagateLinear(t: MockTarget, year: number): { ra: number; dec: number } {
  const dt = year - t.epoch;
  return {
    ra: t.ra + (t.pm[0] * dt) / 3.6e6 / Math.cos((t.dec * Math.PI) / 180),
    dec: t.dec + (t.pm[1] * dt) / 3.6e6,
  };
}
