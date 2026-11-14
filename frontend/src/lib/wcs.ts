/**
 * Gnomonic (TAN) projection for the manifest grid (implementation.md §4.4 make_grid: north up,
 * east left, odd square, CRPIX 1-based). Overlays are drawn in sky coordinates through this
 * (implementation.md §6.3), so the predicted track, Gaia markers and diff annotations land on the
 * same pixels the server reprojected to.
 *
 * Pixel convention used throughout the frontend: (col, row), 0-based pixel CENTRES,
 * col 0 = east edge, row 0 = SOUTH edge (the payload layout "row0south").
 */
import type { GridInfo } from "../api/types";

const D2R = Math.PI / 180;

export function skyToPixel(g: GridInfo, ra: number, dec: number): { col: number; row: number } | null {
  const [a0, d0] = [g.crval[0] * D2R, g.crval[1] * D2R];
  const a = ra * D2R, d = dec * D2R;
  const cosc = Math.sin(d0) * Math.sin(d) + Math.cos(d0) * Math.cos(d) * Math.cos(a - a0);
  if (cosc <= 0) return null;                       // other hemisphere: not on the tangent plane
  const xi = (Math.cos(d) * Math.sin(a - a0)) / cosc / D2R;            // deg, + toward east
  const eta = (Math.cos(d0) * Math.sin(d) - Math.sin(d0) * Math.cos(d) * Math.cos(a - a0)) / cosc / D2R;
  // FITS: x = CRPIX1 + xi / CDELT1 (1-based). CDELT1 < 0 so east (xi > 0) is left (lower col).
  return { col: g.crpix[0] - 1 + xi / g.cdelt[0], row: g.crpix[1] - 1 + eta / g.cdelt[1] };
}

export function pixelToSky(g: GridInfo, col: number, row: number): { ra: number; dec: number } {
  const xi = (col - (g.crpix[0] - 1)) * g.cdelt[0] * D2R;
  const eta = (row - (g.crpix[1] - 1)) * g.cdelt[1] * D2R;
  const [a0, d0] = [g.crval[0] * D2R, g.crval[1] * D2R];
  const den = Math.cos(d0) - eta * Math.sin(d0);
  const a = a0 + Math.atan2(xi, den);
  const d = Math.atan2(Math.sin(d0) + eta * Math.cos(d0), Math.hypot(xi, den));
  return { ra: ((a / D2R) % 360 + 360) % 360, dec: d / D2R };
}

/** Angular separation (arcsec), haversine. */
export function sepArcsec(ra1: number, dec1: number, ra2: number, dec2: number): number {
  const s = Math.sin(((dec2 - dec1) * D2R) / 2) ** 2 +
    Math.cos(dec1 * D2R) * Math.cos(dec2 * D2R) * Math.sin(((ra2 - ra1) * D2R) / 2) ** 2;
  return (2 * Math.asin(Math.min(1, Math.sqrt(s)))) / D2R * 3600;
}

/** Position angle (deg, east of north) from point 1 to point 2. */
export function positionAngle(ra1: number, dec1: number, ra2: number, dec2: number): number {
  const da = (ra2 - ra1) * D2R;
  const y = Math.sin(da) * Math.cos(dec2 * D2R);
  const x = Math.cos(dec1 * D2R) * Math.sin(dec2 * D2R) - Math.sin(dec1 * D2R) * Math.cos(dec2 * D2R) * Math.cos(da);
  return ((Math.atan2(y, x) / D2R) + 360) % 360;
}

/**
 * The grid a bin's stack was drawn on. In track mode (`center=track`) every frame is reprojected onto a grid centred
 * on the target's position at that frame, so the stack of a bin is centred on pos(t) at the bin's epoch, not on the
 * manifest's single grid (the median epoch). Overlays, hover coordinates and clicked positions must use that centre,
 * or a Solar System body's read-out is off by its whole motion (audit F-20). The manifest's track rows carry pos(t)
 * at each bin's mean epoch.
 */
export function gridForBin(
  m: { grid: GridInfo; params: Record<string, string>; track: { bin: string; band: number; ra: number; dec: number }[] },
  bin: string | null | undefined,
  band: number,
): GridInfo {
  if (m.params.center !== "track" || !bin) return m.grid;
  const tp = m.track.find((t) => t.bin === bin && t.band === band);
  return tp ? { ...m.grid, crval: [tp.ra, tp.dec] } : m.grid;
}
