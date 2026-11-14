import { describe, expect, it } from "vitest";
import { floatToHalf, halfToFloat, NODATA, NODATA_BITS, decodeF16, f16Bits } from "../src/lib/half";

describe("float16", () => {
  it("encodes the sentinel exactly", () => {
    expect(floatToHalf(NODATA)).toBe(NODATA_BITS);
    expect(halfToFloat(0xfbff)).toBe(-65504);
  });
  it("round-trips representable values bit-exactly", () => {
    for (let h = 0; h < 0x10000; h += 7) {
      const e = (h >> 10) & 0x1f;
      if (e === 0x1f) continue;                       // inf/NaN
      const v = halfToFloat(h);
      const back = floatToHalf(v);
      if (Object.is(v, -0)) expect(back).toBe(0x8000); else expect(back).toBe(h);
    }
  });
  it("rounds to nearest even; relative error ≤ 2^-11 in the normal range, absolute ≤ 2^-25 below it", () => {
    expect(Math.abs(halfToFloat(floatToHalf(1e-5)) - 1e-5)).toBeLessThanOrEqual(Math.pow(2, -25));
    for (const v of [0.1, 1 / 3, 123.456, 6.5e4, -5e4, 7e-5, 3.14159]) {
      const r = halfToFloat(floatToHalf(v));
      expect(Math.abs(r - v) / Math.abs(v)).toBeLessThanOrEqual(Math.pow(2, -11) + 1e-9);
    }
    expect(floatToHalf(1 + Math.pow(2, -11))).toBe(0x3c00);     // tie → even
  });
  it("decodes the sentinel as NaN on the CPU path", () => {
    const d = decodeF16(new Uint16Array([0x3c00, NODATA_BITS]));
    expect(d[0]).toBe(1);
    expect(Number.isNaN(d[1]!)).toBe(true);
  });
  it("rejects odd-length payloads", () => {
    expect(() => f16Bits(new ArrayBuffer(3))).toThrow();
  });
});
