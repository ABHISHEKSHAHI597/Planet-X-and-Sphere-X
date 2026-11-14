/**
 * Auto-generated alt text for the viewer (implementation.md §6.7). Only facts from the manifest
 * (and an ACCEPTED astrometry fit, if one is passed) are stated; nothing comes from planning documents
 * (workflow.md §4.1 claims rule).
 */
import type { TimeBinInfo, ViewManifest } from "../api/types";
import { mjdToMonth } from "./time";

export function altText(m: ViewManifest, band: number, shown: TimeBinInfo[], extra?: { motion?: string }): string {
  if (!shown.length) return `No ${m.axis === "visit" ? "visits" : "time bins"} to show in band ${band}.`;
  const first = shown[0]!, last = shown[shown.length - 1]!;
  const unit = m.axis === "visit" ? (shown.length === 1 ? "visit" : "visits") : (shown.length === 1 ? "time bin" : "time bins");
  const span = first === last ? mjdToMonth(first.mjd_mean) : `${mjdToMonth(first.mjd_min)}–${mjdToMonth(last.mjd_max)}`;
  const partial = shown.filter((b) => b.status === "partial").length;
  const name = m.target?.name ? ` of ${m.target.name}` : "";
  let s = `Band ${band} stacks${name} from ${shown.length} ${unit} (${span}), north up, east left.`;
  if (partial) s += ` ${partial} of them ${partial === 1 ? "is a partial visit" : "are partial visits"} with few frames.`;
  if (extra?.motion) s += ` ${extra.motion}`;
  return s;
}
