/**
 * Contract test (workflow.md §7.3): the golden payload encoded by Python (backend render.golden_F,
 * tests/unit/test_render.py) decodes in TypeScript bit for bit, and BOTH display paths put the "F"
 * upright in the top-left (north-east), the sentinel in the bottom-right, the ramp brightening right.
 * This is the L0/L2 half of F14; the real-field half runs on staging.
 */
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";
import meta from "../fixtures/golden/stack_F_121x121.json";
import { FORMAT_F16 } from "../src/api/formats";
import { viewSpan } from "../src/gl/renderer";
import { decodeF16, f16Bits, halfToFloat, NODATA, NODATA_BITS } from "../src/lib/half";
import { renderRGBA } from "../src/lib/stretch";
import { canvasToPixel, fullView } from "../src/lib/viewport";
import { NODATA_RGB } from "../src/gl/colormaps";

const N = 121;
const buf = readFileSync(resolve(__dirname, "../fixtures/golden/stack_F_121x121.f16"));
const bits = f16Bits(buf.buffer.slice(buf.byteOffset, buf.byteOffset + buf.byteLength));
const vals = decodeF16(bits);
const at = (row: number, col: number) => vals[row * N + col]!;

describe("golden F payload", () => {
  it("has the advertised format and shape", () => {
    expect(meta.format).toBe(FORMAT_F16);
    expect(meta.shape).toEqual([N, N]);
    expect(bits.length).toBe(N * N);
  });

  it("uses the −65504 sentinel bit pattern, never NaN", () => {
    expect(halfToFloat(NODATA_BITS)).toBe(NODATA);
    for (const b of bits) expect(Number.isNaN(halfToFloat(b))).toBe(false);
    for (let r = 0; r < 3; r++) for (let c = N - 3; c < N; c++) expect(bits[r * N + c]).toBe(NODATA_BITS);
    expect(bits[60 * N + 60]).toBe(NODATA_BITS);
  });

  it("row 0 is south: the F (value 100) sits at high rows and low columns (north-east)", () => {
    let rows: number[] = [], cols: number[] = [];
    for (let r = 0; r < N; r++) for (let c = 0; c < N; c++) if (at(r, c) === 100) { rows.push(r); cols.push(c); }
    expect(Math.min(...rows)).toBeGreaterThan(60);
    expect(Math.max(...cols)).toBeLessThan(60);
    rows = []; cols = [];
    expect(at(0, 100)).toBeGreaterThan(at(0, 10));             // ramp brightens westward (higher columns)
  });

  it("CPU/PNG path: F upright top-left, sentinel bottom-right, ramp brighter to the right", () => {
    const rgba = renderRGBA(vals, N, N, 0, 100, { mode: "lin", beta: 1 }, "gray");
    const px = (x: number, y: number) => [rgba[4 * (y * N + x)]!, rgba[4 * (y * N + x) + 1]!, rgba[4 * (y * N + x) + 2]!];
    // the F's top bar is at image row (N-1) - (N-6) = 5 from the top, spanning columns 5..24
    expect(px(5, 5)).toEqual([255, 255, 255]);
    expect(px(24, 5)).toEqual([255, 255, 255]);
    expect(px(110, 5)).toEqual([0, 0, 0]);                      // top-right is background
    // stem goes DOWN from the top bar on the left: upright F
    expect(px(6, 30)).toEqual([255, 255, 255]);
    expect(px(20, 30)).toEqual([0, 0, 0]);
    // sentinel tint in the bottom-right corner and at the centre
    expect(px(N - 1, N - 1)).toEqual(NODATA_RGB);
    expect(px(60, 60)).toEqual(NODATA_RGB);
    // bottom row: ramp increases to the right
    expect(px(100, N - 1)[0]!).toBeGreaterThan(px(10, N - 1)[0]!);
  });

  it("WebGL path math: canvas top-left maps to the north-east pixel with NO flip", () => {
    // Shader: px = u_center + (v_uv - 0.5) * u_span, with v_uv = (0,0) at the canvas BOTTOM-left.
    const v = fullView(N, N);
    const { sx, sy } = viewSpan(N, N, 400, 400, 1);
    const shader = (uvx: number, uvy: number) => ({ col: Math.floor(v.cx + (uvx - 0.5) * sx), row: Math.floor(v.cy + (uvy - 0.5) * sy) });
    const topLeft = shader(0.001, 0.999), bottomRight = shader(0.999, 0.001);
    expect(topLeft).toEqual({ col: 0, row: N - 1 });
    expect(bottomRight).toEqual({ col: N - 1, row: 0 });
    // and the overlay/loupe mapping (canvas y down) agrees with the shader
    expect(canvasToPixel(0.4, 0.4, 400, 400, N, N, v)).toEqual(topLeft);
    expect(canvasToPixel(399.6, 399.6, 400, 400, N, N, v)).toEqual(bottomRight);
    expect(at(topLeft.row - 5, topLeft.col + 5)).toBe(100);    // the F's top bar is there
    expect(Number.isNaN(at(bottomRight.row, bottomRight.col))).toBe(true);   // sentinel there
  });
});
