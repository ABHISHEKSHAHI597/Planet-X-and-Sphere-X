/** Derived state shared by the viewer, timeline and panels. */
import { useMemo } from "react";
import type { StackInfo, TimeBinInfo, ViewManifest } from "../api/types";
import { feature, type Capability, type FeatureState } from "../lib/features";
import { playableBins } from "../lib/player";
import { useApp } from "../state/store";
import { selectedBands, type ViewState } from "../state/url";
import { channelBins, PRESET_BANDS } from "../lib/rgbBins";

export interface Current {
  band: number;
  rgbBands: number[] | null;
  allBins: TimeBinInfo[];
  bins: TimeBinInfo[];             // playable (partials only with partial=1)
  index: number;
  bin: TimeBinInfo | null;
  stack: (bin: string, band?: number) => StackInfo | undefined;
  limits: { lo: number; hi: number } | null;
  isReady: (bin: string, band?: number) => boolean;
}

/** The band shown and its playable bins for a view state (what the player steps through). Pure: shared by
 *  useCurrent and by band switching, which must land on the same epoch (audit F-06). */
export function playableFor(m: ViewManifest | null, view: Pick<ViewState, "bands" | "partial">): { band: number; allBins: TimeBinInfo[]; bins: TimeBinInfo[]; rgb3: number[] | null } {
  const sb = selectedBands(view.bands);
  const presetBands = sb.preset ? PRESET_BANDS[sb.preset] : undefined;
  const band = sb.list[0] ?? presetBands?.[0] ?? 6;
  const allBins = m?.bins[String(band)] ?? [];
  const rgb3 = sb.rgb && sb.list.length === 3 ? sb.list : null;
  // RGB triplets play only the frames where all three bands have a stack within RGB_MATCH_DAYS
  // (detector pairs see a target on different days, so on fixed-bin axes many frames lack a band).
  const bins = playableBins(allBins, view.partial)
    .filter((b) => !rgb3 || !m || channelBins(m.bins, b.id, rgb3).every((x) => x !== null))
    .filter((b) => !presetBands || !m || presetBands.every((pb) => (m.bins[String(pb)] ?? []).some((x) => x.id === b.id)));
  return { band, allBins, bins, rgb3 };
}

/** Index in `next` of the epoch shown at `from`: the same bin id when that band has it, else the nearest mean MJD.
 *  Bin ids differ between bands (partial clusters merge per band), so keeping the index would change the epoch. */
export function sameEpochIndex(from: TimeBinInfo | null | undefined, next: TimeBinInfo[]): number {
  if (!from || !next.length) return 0;
  const k = next.findIndex((b) => b.id === from.id);
  if (k >= 0) return k;
  let best = 0;
  for (let i = 1; i < next.length; i++) {
    if (Math.abs(next[i]!.mjd_mean - from.mjd_mean) < Math.abs(next[best]!.mjd_mean - from.mjd_mean)) best = i;
  }
  return best;
}

/** Switch the displayed band (or RGB choice) and stay on the epoch being shown. */
export function selectBands(bands: string): void {
  const st = useApp.getState();
  const cur = playableFor(st.manifest, st.view);
  const shown = cur.bins[Math.min(Math.max(0, st.frame), Math.max(0, cur.bins.length - 1))];
  const next = playableFor(st.manifest, { ...st.view, bands });
  st.setView({ bands });
  st.setFrame(sameEpochIndex(shown, next.bins));
}

export function useCurrent(): Current {
  const m = useApp((s) => s.manifest);
  const view = useApp((s) => s.view);
  const frame = useApp((s) => s.frame);
  const ready = useApp((s) => s.ready);
  return useMemo(() => {
    const { band, allBins, bins, rgb3 } = playableFor(m, { bands: view.bands, partial: view.partial });
    const index = Math.min(Math.max(0, frame), Math.max(0, bins.length - 1));
    const lim = m?.limits[String(band)];
    return {
      band,
      rgbBands: rgb3,
      allBins,
      bins,
      index,
      bin: bins[index] ?? null,
      stack: (bin, b = band) => m?.stacks.find((s) => s.bin === bin && s.band === b),
      limits: lim ? { lo: lim.lo, hi: lim.hi } : null,
      isReady: (bin, b = band) => ready.has(`${bin}|${b}`),
    };
  }, [m, view.bands, view.partial, frame, ready]);
}

export function useFeature(cap: Capability): FeatureState {
  const rel = useApp((s) => s.release);
  return useMemo(() => feature(rel, cap), [rel, cap]);
}
