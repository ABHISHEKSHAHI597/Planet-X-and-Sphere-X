/** MJD helpers for labels and the timeline. UTC, no leap-second precision needed for display. */
const MJD_UNIX_EPOCH = 40587;

export function mjdToDate(mjd: number): Date {
  return new Date((mjd - MJD_UNIX_EPOCH) * 86400000);
}

export function mjdToISODate(mjd: number): string {
  return mjdToDate(mjd).toISOString().slice(0, 10);
}

export function mjdToMonth(mjd: number): string {
  return mjdToDate(mjd).toLocaleString("en", { month: "short", year: "numeric", timeZone: "UTC" });
}

export function mjdToDecimalYear(mjd: number): number {
  const d = mjdToDate(mjd);
  const y = d.getUTCFullYear();
  const start = Date.UTC(y, 0, 1), end = Date.UTC(y + 1, 0, 1);
  return y + (d.getTime() - start) / (end - start);
}

export function dateToMjd(d: Date): number {
  return d.getTime() / 86400000 + MJD_UNIX_EPOCH;
}
