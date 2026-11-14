/**
 * Flag planes for the overlay and tooltips. The manifest's `flags.bits` / `flags.info` are the
 * authority at runtime; these are the fallback copies of backend/spherex/flags.py CANONICAL_BITS and
 * FLAG_INFO (scientific text owned by I; tests/flags.test.ts checks they stay in step with flags.py).
 */
export const CANONICAL_BITS: Record<string, number> = {
  TRANSIENT: 0, OVERFLOW: 1, SUR_ERROR: 2, PHANTOM: 4, REFERENCE: 5, NONFUNC: 6, DICHROIC: 7, MISSING_DATA: 9,
  HOT: 10, COLD: 11, FULLSAMPLE: 12, PHANMISS: 14, NONLINEAR: 15, PERSIST: 17,
  OUTLIER: 19, CROSSTALK: 20, SOURCE: 21, GHOST: 22, GHOST_FPA: 23, GHOST_EXT: 24,
  STREAK: 25, BLOOM: 26, SNOWBALL: 27, HALO: 28, SATELLITE_HALO: 29,
};

export const FLAG_INFO: Record<string, string> = {
  TRANSIENT: "cosmic ray or bloom onset on the ramp",
  OVERFLOW: "reached about half full well (bright star); cores that overflowed early are blank",
  SUR_ERROR: "onboard ramp-fit error",
  PHANTOM: "phantom pixel (QR2 plane)", REFERENCE: "reference pixel, not light-sensitive (QR2 plane)",
  NONFUNC: "dead pixel", DICHROIC: "low throughput at the band 3/4 edge",
  MISSING_DATA: "lost in downlink", HOT: "hot pixel", COLD: "cold pixel",
  FULLSAMPLE: "informational", PHANMISS: "not correctable",
  NONLINEAR: "no reliable nonlinearity correction",
  PERSIST: "persistence from an earlier bright exposure (mimics transients)",
  OUTLIER: "isolated outlier outside known sources: could be an uncatalogued source",
  CROSSTALK: "electrical crosstalk echo", SOURCE: "pixel of a known catalogue source",
  GHOST: "optical ghost", GHOST_FPA: "optical ghost (focal plane)", GHOST_EXT: "optical ghost (external)",
  STREAK: "linear streak (satellite or fast asteroid)", BLOOM: "charge bloom",
  SNOWBALL: "snowball", HALO: "halo", SATELLITE_HALO: "satellite halo",
};

/** Informational planes propagated into every stack's flag_or (flags.INFO_FLAGS). These are the ones
 *  the overlay offers by default; SOURCE/OUTLIER/STREAK are hints, never masks (understanding.md §4.4). */
export const INFO_FLAGS = ["OVERFLOW", "SOURCE", "OUTLIER", "STREAK"] as const;

/** Colour per drawn plane (contours; distinguished also by dash pattern, never by hue alone). */
export const FLAG_STYLE: Record<string, { color: string; dash: string }> = {
  OVERFLOW: { color: "#ffb000", dash: "" },
  SOURCE: { color: "#6cc3ff", dash: "2 2" },
  OUTLIER: { color: "#ff5ca8", dash: "1 3" },
  STREAK: { color: "#b7ff5c", dash: "6 2" },
};
