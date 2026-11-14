/**
 * Coordinate input (P0-1, implementation.md §1.3): decimal or sexagesimal RA/Dec, Unicode minus.
 * The backend resolver is the authority (and adds the epoch guard); this parser lets the UI accept
 * `?ra=08:55:10.831&dec=-07:14:42.53` URLs and give instant feedback on malformed input.
 */

export interface RaDec { ra: number; dec: number }

/** − – — → -, ’ ′ → ', ″ → ", collapse whitespace (same normalisation as targets.normalize_query). */
export function normalizeInput(q: string): string {
  return q
    .replace(/[−–—]/g, "-")
    .replace(/[’′]/g, "'")
    .replace(/[”″]/g, '"')
    .replace(/\s+/g, " ")
    .trim();
}

// Characters a pure coordinate string may contain. Anything else (e.g. "WISE 0855-0714") is a name.
const COORD_CHARS = /^[0-9+\-.,:;\s°'"hmsd]+$/i;
const NUM = /[+-]?\d+(?:\.\d*)?|[+-]?\.\d+/g;

export function looksLikeCoordinates(q: string): boolean {
  const s = normalizeInput(q);
  if (!COORD_CHARS.test(s)) return false;
  if (/[hmsd]/i.test(s) && !/\d\s*[hmsd]/i.test(s)) return false;   // letters only as unit markers
  return (s.match(NUM) ?? []).length >= 2;
}

function sexToNumber(parts: number[], sign: number): number {
  const [a = 0, b = 0, c = 0] = parts.map(Math.abs);
  if (b >= 60 || c >= 60) return NaN;
  return sign * (a + b / 60 + c / 3600);
}

/** Parse a right ascension: "08:55:10.831", "08h55m10.831s", "8 55 10.8" (hours) or "133.795" (deg). */
export function parseRA(s: string): number | null {
  const t = normalizeInput(s);
  if (!t || /-/.test(t)) return null;
  const nums = (t.match(NUM) ?? []).map(Number);
  if (!nums.length || nums.length > 3 || nums.some((n) => !Number.isFinite(n))) return null;
  const degMarked = /[d°]/i.test(t);
  const hourMarked = /h/i.test(t) || t.includes(":") || (nums.length > 1 && !degMarked);
  let deg: number;
  if (nums.length === 1 && !hourMarked) deg = nums[0]!;
  else if (degMarked) deg = sexToNumber(nums, 1);
  else {
    if (nums[0]! >= 24) return null;
    deg = 15 * sexToNumber(nums, 1);
  }
  if (!Number.isFinite(deg) || deg < 0 || deg >= 360) return null;
  return deg;
}

/** Parse a declination: "-07:14:42.53", "−7°14′42.5″", "+04 46 14.6", "-7.245". */
export function parseDec(s: string): number | null {
  const t = normalizeInput(s);
  if (!t) return null;
  const sign = t.trimStart().startsWith("-") ? -1 : 1;
  const nums = (t.replace(/^[+-]\s*/, "").match(/\d+(?:\.\d*)?|\.\d+/g) ?? []).map(Number);
  if (!nums.length || nums.length > 3) return null;
  const deg = sexToNumber(nums, sign);
  if (!Number.isFinite(deg) || deg < -90 || deg > 90) return null;
  return deg;
}

/** Split "RA Dec" typed in one box. Returns null when the string is not a coordinate pair. */
export function parseCoordinates(q: string): RaDec | null {
  const s = normalizeInput(q);
  if (!looksLikeCoordinates(s)) return null;
  let raStr: string, decStr: string;
  const comma = s.split(/[,;]/);
  if (comma.length === 2) {
    [raStr, decStr] = comma as [string, string];
  } else {
    // The Dec starts at the first sign that follows a number or unit marker.
    const m = /^(.*?[\d.hms"':°d])\s*([+-].*)$/i.exec(s);
    if (m) {
      raStr = m[1]!; decStr = m[2]!;
    } else {
      const toks = s.split(" ").filter(Boolean);
      if (toks.length === 2 || toks.length === 4 || toks.length === 6) {
        raStr = toks.slice(0, toks.length / 2).join(" ");
        decStr = toks.slice(toks.length / 2).join(" ");
      } else return null;
    }
  }
  const ra = parseRA(raStr);
  const dec = parseDec(decStr);
  return ra === null || dec === null ? null : { ra, dec };
}

const pad = (n: number, w: number, d = 0) => n.toFixed(d).padStart(d ? w + d + 1 : w, "0");

/** 269.4461 → "17h57m47.06s" (hours). */
export function formatRA(deg: number, digits = 2): string {
  let h = (((deg % 360) + 360) % 360) / 15;
  let hh = Math.floor(h); h = (h - hh) * 60;
  let mm = Math.floor(h); let ss = (h - mm) * 60;
  if (Number(ss.toFixed(digits)) >= 60) { ss = 0; mm += 1; }
  if (mm >= 60) { mm = 0; hh = (hh + 1) % 24; }
  return `${pad(hh, 2)}h${pad(mm, 2)}m${pad(ss, 2, digits)}s`;
}

/** 4.7707 → "+04°46′14.5″" (Unicode minus for negatives). */
export function formatDec(deg: number, digits = 1): string {
  const sign = deg < 0 ? "−" : "+";
  let d = Math.abs(deg);
  let dd = Math.floor(d); d = (d - dd) * 60;
  let mm = Math.floor(d); let ss = (d - mm) * 60;
  if (Number(ss.toFixed(digits)) >= 60) { ss = 0; mm += 1; }
  if (mm >= 60) { mm = 0; dd += 1; }
  return `${sign}${pad(dd, 2)}°${pad(mm, 2)}′${pad(ss, 2, digits)}″`;
}
