/** Which stack each RGB channel uses for one frame (shared by RgbCanvas and the player). */
/** Max time between the channel bins of one RGB frame. Detector pairs D1/D4, D2/D5 and D3/D6 see a target on
 * different days, so on fixed-bin axes (R Dra) the three bands rarely share a bin id. */
export const RGB_MATCH_DAYS = 14;

/** For each band, the bin with this id, else the band's bin nearest in time (≤ RGB_MATCH_DAYS). */
export function channelBins(bins: Record<string, { id: string; mjd_mean: number }[]>, bin: string,
  bands: number[]): (string | null)[] {
  const t = Object.values(bins).flat().find((b) => b.id === bin)?.mjd_mean;
  return bands.map((band) => {
    const list = bins[String(band)] ?? [];
    if (list.some((b) => b.id === bin)) return bin;
    if (t === undefined) return null;
    const best = list.reduce<{ id: string; dt: number } | null>((acc, b) => {
      const dt = Math.abs(b.mjd_mean - t);
      return acc === null || dt < acc.dt ? { id: b.id, dt } : acc;
    }, null);
    return best && best.dt <= RGB_MATCH_DAYS ? best.id : null;
  });
}


/** Detector bands each λ-range preset reads (cube.RGB_PRESETS ranges vs constants.BANDS). The server needs
 * every one in the same bin, so the player steps through the first band's bins that the others share. */
export const PRESET_BANDS: Record<string, number[]> = { ice: [4], methane: [4, 5] };
