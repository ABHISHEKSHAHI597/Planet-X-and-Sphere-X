/**
 * Number formatting for measured values. The API sends a failed fit's NaN or ±inf as JSON null (pydantic), although
 * the types say `number`, so every measured number goes through here: null and non-finite print as "—" instead of
 * throwing in `.toFixed()` and blanking the page (audit F-16).
 */
export const DASH = "—";

export function isNum(x: unknown): x is number {
  return typeof x === "number" && Number.isFinite(x);
}

/** x.toFixed(digits), or "—". */
export function fix(x: number | null | undefined, digits = 2): string {
  return isNum(x) ? x.toFixed(digits) : DASH;
}

/** x.toPrecision(digits), or "—". */
export function prec(x: number | null | undefined, digits = 3): string {
  return isNum(x) ? x.toPrecision(digits) : DASH;
}

/** x.toExponential(digits), or "—". */
export function expo(x: number | null | undefined, digits = 1): string {
  return isNum(x) ? x.toExponential(digits) : DASH;
}
