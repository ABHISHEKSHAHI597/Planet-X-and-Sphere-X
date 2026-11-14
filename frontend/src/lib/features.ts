/**
 * Feature flags (workflow.md §9.6). The backend serves the effective set in /releases, so the
 * frontend and the API agree. A capability the backend does not list is OFF: the frontend never
 * enables something on its own (workflow.md §11.2 — e.g. the difference mode stays off until G4a).
 */
import type { FlagLevel, ReleasesResponse } from "../api/types";

/** Capabilities the UI can offer, with the gate that must be accepted before "on" (workflow.md §6). */
export const CAPABILITIES = {
  diff: "G4a λ-matched difference (P1-1)",
  spectrum: "G4b spectra on the fly (P1-2)",
  astrometry: "G3 motion: astrometry card and fitted vector (P1-3)",
  track: "G3 predicted track overlay (P1-3)",
  aladin: "Aladin Lite sky context (P1-4)",
  overlays: "Gaia/SIMBAD markers propagated to the visit epoch (P1-4)",
  wise_layer: "AllWISE positions as catalogued around 2010.5, not propagated (O5)",
  embed: "Embed route (P1-5, G5.eng)",
  freshness: "Release freshness badge (P1-6, G5.eng)",
  bright_fill: "Model-filled bright cores (P1-7)",
  blink25: "25-year blink (P2-1, G5.25yr)",
  flip: "Spectral flipbook (P2-2, G5.flip)",
  scrubber: "λ-scrubber (P2-2, G5.flip)",
  rgb: "RGB composites of band stacks",
  lightcurve: "Light curves (P2-3, G5.lc)",
  movers: "Mover finder (P2-4, G5.movers)",
  planetx: "Parallax-linked orphan candidates (P2-6, G5.planetx)",
  export: "Exports (P2-7, G5.eng)",
  candidates: "Candidate reports (P2-9, G5.eng)",
  sso: "Solar System track mode (P2-10, G5.sso)",
} as const;

export type Capability = keyof typeof CAPABILITIES;

export interface FeatureState {
  level: FlagLevel;
  /** Shown at all in this environment. */
  enabled: boolean;
  /** Shown with an "unvalidated" badge (dev/staging). Covers UX immaturity only (workflow.md §9.6). */
  unvalidated: boolean;
}

export function feature(rel: Pick<ReleasesResponse, "features" | "environment"> | null | undefined, cap: Capability): FeatureState {
  const level: FlagLevel = (rel?.features?.[cap] as FlagLevel | undefined) ?? "off";
  const env = rel?.environment ?? "production";
  let enabled: boolean;
  switch (level) {
    case "on": enabled = true; break;
    case "staging": enabled = env === "staging" || env === "local" || env === "mock"; break;
    case "dev": enabled = env === "local" || env === "mock"; break;
    default: enabled = false;
  }
  // Defence in depth: production and snapshot builds show only accepted ("on") capabilities.
  if ((env === "production" || env === "snapshot") && level !== "on") enabled = false;
  return { level, enabled, unvalidated: enabled && level !== "on" };
}
