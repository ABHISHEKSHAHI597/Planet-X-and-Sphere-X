/**
 * float16 helpers (implementation.md §5.2). The GPU path uploads the raw bits into an R16F texture
 * with no decoding; the CPU path (loupe, PNG-less previews, tests) decodes here.
 */

/** Most negative finite float16. The server writes it for "no data" (never NaN, §6.3). */
export const NODATA = -65504;
/** Anything below this is treated as the sentinel (the shader uses the same threshold). */
export const NODATA_THRESHOLD = -6.0e4;
/** Raw bit pattern of −65504 in IEEE half precision. */
export const NODATA_BITS = 0xfbff;

const pow2 = (e: number) => Math.pow(2, e);

/** Decode one IEEE 754 binary16 bit pattern. */
export function halfToFloat(h: number): number {
  const s = h & 0x8000 ? -1 : 1;
  const e = (h >> 10) & 0x1f;
  const f = h & 0x3ff;
  if (e === 0) return s * pow2(-14) * (f / 1024);
  if (e === 0x1f) return f ? NaN : s * Infinity;
  return s * pow2(e - 15) * (1 + f / 1024);
}

const f32 = new Float32Array(1);
const u32 = new Uint32Array(f32.buffer);

/** Encode a float into binary16 bits, round-half-to-even (via float32). Mock transport and tests. */
export function floatToHalf(v: number): number {
  f32[0] = v;
  const x = u32[0]!;
  const sign = (x >>> 16) & 0x8000;
  const exp = (x >>> 23) & 0xff;
  let mant = x & 0x7fffff;
  if (exp === 0xff) return sign | 0x7c00 | (mant ? 0x200 : 0);
  const e = exp - 127 + 15;
  if (e >= 31) return sign | 0x7c00;
  if (e <= 0) {
    if (e < -10) return sign;
    mant |= 0x800000;
    const shift = 14 - e;
    let half = mant >>> shift;
    const rem = mant & ((1 << shift) - 1);
    const mid = 1 << (shift - 1);
    if (rem > mid || (rem === mid && half & 1)) half++;
    return sign | half;
  }
  let half = (e << 10) | (mant >>> 13);
  const rem = mant & 0x1fff;
  if (rem > 0x1000 || (rem === 0x1000 && half & 1)) half++;   // a carry correctly bumps the exponent
  return sign | half;
}

/** Decode a whole .f16 payload to float32, mapping the sentinel to NaN (CPU path only). */
export function decodeF16(bits: Uint16Array): Float32Array {
  const out = new Float32Array(bits.length);
  for (let i = 0; i < bits.length; i++) {
    const v = halfToFloat(bits[i]!);
    out[i] = v < NODATA_THRESHOLD ? NaN : v;
  }
  return out;
}

/** View an ArrayBuffer of a little-endian .f16 payload as Uint16 bits, whatever the host endianness. */
export function f16Bits(buf: ArrayBuffer): Uint16Array {
  if (buf.byteLength % 2) throw new Error(`f16 payload has odd length ${buf.byteLength}`);
  const le = new Uint8Array(new Uint16Array([1]).buffer)[0] === 1;
  if (le) return new Uint16Array(buf);
  const dv = new DataView(buf);
  const out = new Uint16Array(buf.byteLength / 2);
  for (let i = 0; i < out.length; i++) out[i] = dv.getUint16(2 * i, true);
  return out;
}
