/** Instrument constants (implementation.md §14.1; backend/spherex/constants.py is the authority). */
export const PIXEL_ARCSEC = 6.15;
/** detector/band: [λmin µm, λmax µm, R] — Supplement v2.0 Table 2 */
export const BANDS: Record<number, [number, number, number]> = {
  1: [0.744, 1.116, 39], 2: [1.099, 1.651, 41], 3: [1.636, 2.421, 41],
  4: [2.423, 3.822, 35], 5: [3.809, 4.420, 112], 6: [4.412, 5.002, 128],
};
export const BAND_IDS = [1, 2, 3, 4, 5, 6] as const;
export const FOV_MIN = 2;
export const FOV_MAX = 30;            // P0-4; up to 60 binned is P2
export const FOV_PRESETS = [3, 6, 12, 24, 30];

export function bandLabel(b: number): string {
  const r = BANDS[b];
  return r ? `Band ${b} · ${r[0].toFixed(2)}–${r[1].toFixed(2)} µm` : `Band ${b}`;
}

/** Spectral features to mark on spectra (implementation.md §4.8). He 1.083 is a contaminant. */
export const FEATURES: { lam: number; label: string; contaminant?: boolean }[] = [
  { lam: 1.083, label: "He 1.083 (airglow)", contaminant: true },
  { lam: 1.875, label: "Paα" }, { lam: 2.7, label: "H₂O" }, { lam: 3.05, label: "H₂O ice" },
  { lam: 3.3, label: "CH₄" }, { lam: 4.05, label: "Brα" }, { lam: 4.26, label: "CO₂" }, { lam: 4.67, label: "CO" },
];

/** SIMBAD object-type codes of variables (Mi* Mira, TT* T Tauri, Or* Orion variable, …); long names kept. */
export const VARIABLE_OTYPE = /^(Mi\*|TT\*|Or\*|V\*|Y\*O|LP\*|SR\*|RR\*|Ce\*|EB\*|C\*|Ir\*|Er\*|Pu\*|Mira|TTau|Var)/;
