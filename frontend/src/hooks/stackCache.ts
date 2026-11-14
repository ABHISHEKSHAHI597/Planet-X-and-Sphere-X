/**
 * Payload cache: every stack of a view stays resident (implementation.md §6.3: 24 stacks × 29 KB is
 * trivial) so switching bins and bands is instant. Keyed by view key, so a new view never shows an
 * old view's pixels.
 */
import { api } from "../api/client";
import { decodeF16 } from "../lib/half";

const f16 = new Map<string, Promise<Uint16Array>>();
const f32 = new Map<string, Promise<Float32Array>>();
const flags = new Map<string, Promise<Uint32Array>>();
const MAX = 400;

function remember<T>(m: Map<string, Promise<T>>, k: string, make: () => Promise<T>): Promise<T> {
  let p = m.get(k);
  if (!p) {
    p = make();
    p.catch(() => m.delete(k));
    m.set(k, p);
    if (m.size > MAX) m.delete(m.keys().next().value as string);
  }
  return p;
}

export function getF16(key: string, bin: string, band: number, format: string, raw = false): Promise<Uint16Array> {
  return remember(f16, `${key}|${bin}|${band}|${raw}`, () => api.stackF16(key, bin, band, format, raw));
}

/** Decoded values for the loupe (sentinel → NaN). */
export async function getValues(key: string, bin: string, band: number, format: string): Promise<Float32Array> {
  return remember(f32, `${key}|${bin}|${band}|dec`, async () => decodeF16(await getF16(key, bin, band, format)));
}

export function getVariance(key: string, bin: string, band: number, format: string): Promise<Float32Array> {
  return remember(f32, `${key}|${bin}|${band}|var`, () => api.stackF32(key, bin, band, "var.f32", format));
}

export function getFlags(key: string, bin: string, band: number, format: string): Promise<Uint32Array> {
  return remember(flags, `${key}|${bin}|${band}`, () => api.stackFlags(key, bin, band, format));
}

export function clearStackCache(): void { f16.clear(); f32.clear(); flags.clear(); }
