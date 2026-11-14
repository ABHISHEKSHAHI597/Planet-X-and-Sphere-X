/**
 * The five acceptance targets as guided "missions" (implementation.md §1.2, workflow.md §6 target
 * stewards; storyboard: docs/frontend/storyboard.md). Text is QUALITATIVE on purpose: numbers shown
 * next to a mission come from the live API response (resolver, manifest, accepted evidence), never
 * from the planning documents (workflow.md §4.1 claims rule, §11.2). Scientific wording is reviewed by
 * the target's steward (I or M) before release (workflow.md §9.4).
 */
import type { Capability } from "../lib/features";

export interface Mission {
  id: string;
  q: string;
  title: string;
  hook: string;
  look: string[];
  bands: string;
  fov: number;
  /** steward (workflow.md §6) who reviews this text */
  steward: "I" | "M" | "D";
  /** per step of `look` (same order): the capability that step talks about, or null. The step is hidden where that
   *  capability is off, so a public visitor is never told to use a control they do not have (browser test 2026-11-14). */
  lookNeeds?: (Capability | null)[];
  /** capability this mission leans on beyond the P0 blink (hidden when the flag is off) */
  extras?: string[];
  /** D's frozen frame list (config/pins/<pin>.json, index.json): the button opens the prewarmed view, never a cold
   *  live build, and works offline from the snapshot (audit F-01). tests/content.test.ts checks each file exists. */
  pin?: string;
  /** matches resolver names, SIMBAD main ids and what people type */
  match: RegExp;
}

export const MISSIONS: Mission[] = [
  {
    id: "barnard", pin: "21a7689afc4b", match: /barnard/i, q: "Barnard's Star", steward: "M", bands: "6", fov: 6,
    title: "The fastest star in the sky",
    hook: "The closest single star to the Sun, crossing the sky faster than any other star.",
    look: [
      "Blink the visits: the bright star hops while the field stays put.",
      "The dark hole in its core is not a bug: the star is so bright the detector overflowed. Turn on the OVERFLOW flag layer.",
      "The predicted track (dots) includes parallax: the small side-step between visits is the Earth's orbit.",
    ],
    lookNeeds: [null, null, "track"],
    extras: ["astrometry", "diff", "blink25"],
  },
  {
    id: "epsindb", pin: "3addc0f80339", match: /(^|[\s*])(eps|ε|epsilon)\s*ind(i)?\s*b$/i, q: "eps Ind B", steward: "I", bands: "4", fov: 6,
    title: "Two brown dwarfs, one dot",
    hook: "A pair of cold brown dwarfs, too close together for SPHEREx to split, drifting together.",
    look: [
      "Step through the bands from short to long wavelengths: the dot changes brightness because its spectrum is shaped by methane and water.",
      "A very bright star nearby can leave ghosts and echoes. If something odd appears, check the flag layers first.",
    ],
    extras: ["spectrum"],
  },
  {
    id: "wise0855", pin: "325c57328320", match: /0855/, q: "WISE 0855-0714", steward: "D", bands: "6", fov: 6,
    title: "The coldest known brown dwarf",
    hook: "Colder than any star, it glows almost only at the longest SPHEREx wavelengths.",
    look: [
      "The famous coordinate for this object is an old position from the WISE era. ParallaX tells you so and moves the view to where it is now.",
      "Compare band 1 with band 6. In the short bands what you see at its position is a different, ordinary star sitting right next to it.",
      "Partial visits (only a few frames) are hatched on the timeline and left out of the blink by default.",
    ],
    extras: ["spectrum"],
  },
  {
    id: "rwaur", pin: "177ce03ed2a6", match: /\brw\s*aur/i, q: "RW Aur", steward: "I", bands: "3", fov: 6,
    title: "A young star behind shifting dust",
    hook: "A baby star still feeding from its disc, known for dimming when dust drifts across it.",
    look: [
      "It does not move: watch for brightness changes between visits instead.",
      "It is bright enough to overflow the detector in some bands; the flag layer shows where.",
    ],
    extras: ["lightcurve", "spectrum"],
  },
  {
    id: "rdra", pin: "152b410215da", match: /^(v\*\s*)?r\s*dra(conis)?$/i, q: "R Dra", steward: "D", bands: "3", fov: 6,
    title: "A breathing giant",
    hook: "A pulsating red giant that swells and fades over months, watched almost continuously from near the ecliptic pole.",
    look: [
      "Here the time axis switches itself from visits to 14-day bins, because SPHEREx sees this patch almost all the time.",
      "Its core is saturated in most bands; brightness changes are measured in a ring around the star, so treat them as relative.",
    ],
    lookNeeds: [null, "lightcurve"],
    extras: ["lightcurve"],
  },
];

export function missionFor(names: string[]): Mission | null {
  return MISSIONS.find((m) => names.some((n) => n && m.match.test(n.trim()))) ?? null;
}

/** The challenge's own WISE 0855 coordinate (its ≈2010.45 position): opens the pinned 12′ demo view, which is wide
 *  enough to hold both the typed position and where the dwarf is now (config/demo_views.yaml; audit F-02). */
export const CHALLENGE = { ra: "08:55:10.831", dec: "-07:14:42.53", fov: 12, pin: "325c57328320", bands: "6" } as const;

