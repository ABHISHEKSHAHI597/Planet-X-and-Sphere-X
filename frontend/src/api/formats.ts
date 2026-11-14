/**
 * Binary payload format ids (workflow.md §7.2: "a format change means a new format id; the viewer
 * refuses unknown formats with a clear message rather than drawing garbage"). Ids are defined in
 * backend/spherex/render.py (FORMAT_F16, FORMAT_F32, FORMAT_U32_FLAGS).
 */
export const FORMAT_F16 = "f16le-row0south-nodata-65504@1";
export const FORMAT_F32 = "f32le-row0south-nodata-nan@1";
export const FORMAT_U32_FLAGS = "u32le-row0south-flags-canonical@1";

export const KNOWN_FORMATS = new Set([FORMAT_F16, FORMAT_F32, FORMAT_U32_FLAGS]);

export class UnknownFormatError extends Error {
  constructor(public readonly format: string, public readonly expected: string) {
    super(`This viewer cannot draw payload format "${format}" (it understands "${expected}"). ` +
      "Please reload; if the problem persists the server and the app are out of step.");
    this.name = "UnknownFormatError";
  }
}

export function assertFormat(format: string, expected: string): void {
  if (format !== expected) throw new UnknownFormatError(format, expected);
}

export class SchemaMismatchError extends Error {
  constructor(public readonly got: string, public readonly want: string) {
    super(`Server schema ${got} differs from this app's ${want}. Please reload the page.`);
    this.name = "SchemaMismatchError";
  }
}

/** Same major.minor = compatible (pre-1.0 every minor may break, workflow.md §7.2). */
export function schemaCompatible(got: string, want: string): boolean {
  const [ga, gb] = got.split(".");
  const [wa, wb] = want.split(".");
  if (ga !== wa) return false;
  return ga !== "0" || gb === wb;
}
