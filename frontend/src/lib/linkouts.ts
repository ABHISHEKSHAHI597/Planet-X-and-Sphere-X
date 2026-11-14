/**
 * Links from a ParallaX view to the tools volunteers and astronomers already use for the same patch of sky, and the
 * plain-text form of a candidate report (optimisation.md IMP-3; advanced_research.md B6). Links only: ParallaX has
 * no partnership with any of these projects.
 * WiseView's parameters are the ones its own source reads (backyardworlds/wiseview, flash3.js: hash `ra`, `dec` in
 * degrees and `size` in arcseconds); the Legacy Survey link is the form WiseView itself builds.
 */
import { formatDec, formatRA } from "./coords";

export interface LinkOut { id: string; name: string; what: string; url: string }

const deg = (x: number) => x.toFixed(5);

export function linkOuts(ra: number, dec: number, fovArcmin: number): LinkOut[] {
  const fovDeg = fovArcmin / 60;
  return [
    { id: "wiseview", name: "WiseView", what: "the same patch in WISE, 2010–2024 (Backyard Worlds' blink tool)",
      url: `http://byw.tools/wiseview#ra=${deg(ra)}&dec=${deg(dec)}&size=${Math.round(Math.min(2000, Math.max(60, fovArcmin * 60)))}` },
    { id: "legacy", name: "Legacy Survey viewer", what: "deep optical and unWISE images",
      url: `https://www.legacysurvey.org/viewer?ra=${deg(ra)}&dec=${deg(dec)}&zoom=13&layer=unwise-neo4` },
    { id: "esasky", name: "ESASky", what: "every mission's images of this position",
      url: `https://sky.esa.int/esasky/?target=${deg(ra)}%20${deg(dec)}&hips=AllWISE+color&fov=${Math.max(0.05, fovDeg * 2).toFixed(3)}&cooframe=J2000&sci=true` },
    { id: "simbad", name: "SIMBAD", what: "known objects within 2′",
      url: `https://simbad.cds.unistra.fr/simbad/sim-coo?Coord=${deg(ra)}+${dec >= 0 ? "%2B" : ""}${deg(dec)}&Radius=2&Radius.unit=arcmin` },
  ];
}

export interface ReportInput {
  kind: string; ra: number; dec: number; target?: string | null; band: number;
  visits: { label: string; date: string }[]; note: string; permalink: string; reportId?: string | null;
}

/** A candidate report as plain text, in the order a citizen-science forum post needs: what, where, when, link. */
export function reportText(r: ReportInput): string {
  const lines = [
    `Candidate ${r.kind}${r.target ? ` near ${r.target}` : ""} (ParallaX, SPHEREx band ${r.band})`,
    `Position (ICRS): ${formatRA(r.ra)} ${formatDec(r.dec)}  =  ${deg(r.ra)} ${r.dec >= 0 ? "+" : ""}${deg(r.dec)}`,
    `Seen in: ${r.visits.map((v) => `${v.label} (${v.date})`).join("; ") || "no visit selected"}`,
  ];
  if (r.note.trim()) lines.push(`Note: ${r.note.trim()}`);
  lines.push(`View: ${r.permalink}`);
  lines.push(...linkOuts(r.ra, r.dec, 2).slice(0, 2).map((l) => `${l.name}: ${l.url}`));
  if (r.reportId) lines.push(`ParallaX report id: ${r.reportId}`);
  lines.push("This is a candidate, not a discovery: it needs checking against known objects and image artefacts.");
  return lines.join("\n");
}
