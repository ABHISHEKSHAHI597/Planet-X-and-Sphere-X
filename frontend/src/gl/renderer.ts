/**
 * WebGL2 renderer (implementation.md §6.3). Stacks are uploaded once as R16F textures straight from
 * the .f16 payload (no decoding) and kept resident for instant switching.
 */
import { FRAG, VERT } from "./shaders";
import { lut, type CmapName } from "./colormaps";
import { MODE_ID, type StretchSpec } from "../lib/stretch";

export { NODATA } from "../lib/half";

export interface ViewTransform {
  /** centre of the view in grid pixel-edge units: (nx/2, ny/2) shows the whole grid */
  cx: number;
  cy: number;
  /** 1 = whole grid; 2 = 2× magnified */
  zoom: number;
}

export interface DrawParams {
  tex: WebGLTexture;
  tex2?: WebGLTexture | null;
  mix?: number;
  lo: number;
  hi: number;
  stretch: StretchSpec;
  cmap: CmapName;
  nx: number;
  ny: number;
  view: ViewTransform;
}

/** true when the browser can run the WebGL2 viewer (R16F textures need WebGL2). */
export function webgl2Available(): boolean {
  try {
    if (typeof document === "undefined") return false;
    const c = document.createElement("canvas");
    const gl = c.getContext("webgl2");
    const ok = !!gl;
    gl?.getExtension("WEBGL_lose_context")?.loseContext();
    return ok;
  } catch {
    return false;
  }
}

export function uploadStack(gl: WebGL2RenderingContext, w: number, h: number, half: Uint16Array): WebGLTexture {
  if (half.length !== w * h) throw new Error(`stack has ${half.length} pixels, expected ${w}×${h}`);
  const tex = gl.createTexture()!;
  gl.bindTexture(gl.TEXTURE_2D, tex);
  gl.pixelStorei(gl.UNPACK_ALIGNMENT, 1);          // odd widths: 2-byte rows aren't 4-byte aligned
  gl.pixelStorei(gl.UNPACK_FLIP_Y_WEBGL, false);   // row 0 = south = v 0 = bottom: no flip
  gl.texImage2D(gl.TEXTURE_2D, 0, gl.R16F, w, h, 0, gl.RED, gl.HALF_FLOAT, half);   // raw float16 bits
  // NEAREST: honest pixels, and the sentinel never blends with real values. For a smoother look,
  // ask the server for px=3 (upsampled) instead of enabling LINEAR here.
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.NEAREST);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.NEAREST);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
  return tex;
}

function compile(gl: WebGL2RenderingContext, type: number, src: string): WebGLShader {
  const s = gl.createShader(type)!;
  gl.shaderSource(s, src);
  gl.compileShader(s);
  if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) {
    const log = gl.getShaderInfoLog(s);
    gl.deleteShader(s);
    throw new Error(`shader compile failed: ${log}`);
  }
  return s;
}

export class BlinkRenderer {
  readonly gl: WebGL2RenderingContext;
  private prog: WebGLProgram;
  private vao: WebGLVertexArrayObject;
  private cmapTex: WebGLTexture;
  private cmapName: CmapName | null = null;
  private u: Record<string, WebGLUniformLocation | null> = {};
  private textures = new Set<WebGLTexture>();

  constructor(canvas: HTMLCanvasElement) {
    const gl = canvas.getContext("webgl2", { antialias: false, premultipliedAlpha: false, preserveDrawingBuffer: true });
    if (!gl) throw new Error("WebGL2 unavailable");
    this.gl = gl;
    const p = gl.createProgram()!;
    gl.attachShader(p, compile(gl, gl.VERTEX_SHADER, VERT));
    gl.attachShader(p, compile(gl, gl.FRAGMENT_SHADER, FRAG));
    gl.bindAttribLocation(p, 0, "a_pos");
    gl.linkProgram(p);
    if (!gl.getProgramParameter(p, gl.LINK_STATUS)) throw new Error(`link failed: ${gl.getProgramInfoLog(p)}`);
    this.prog = p;
    for (const n of ["u_img", "u_img2", "u_cmap", "u_lo", "u_hi", "u_beta", "u_mode", "u_mix", "u_center", "u_span", "u_size"]) {
      this.u[n] = gl.getUniformLocation(p, n);
    }
    this.vao = gl.createVertexArray()!;
    gl.bindVertexArray(this.vao);
    const buf = gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER, buf);
    gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 1, -1, -1, 1, 1, 1]), gl.STATIC_DRAW);
    gl.enableVertexAttribArray(0);
    gl.vertexAttribPointer(0, 2, gl.FLOAT, false, 0, 0);
    this.cmapTex = gl.createTexture()!;
  }

  upload(w: number, h: number, half: Uint16Array): WebGLTexture {
    const t = uploadStack(this.gl, w, h, half);
    this.textures.add(t);
    return t;
  }

  release(t: WebGLTexture): void {
    if (this.textures.delete(t)) this.gl.deleteTexture(t);
  }

  private setCmap(name: CmapName): void {
    if (name === this.cmapName) return;
    const gl = this.gl;
    gl.bindTexture(gl.TEXTURE_2D, this.cmapTex);
    gl.pixelStorei(gl.UNPACK_ALIGNMENT, 4);
    gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA8, 256, 1, 0, gl.RGBA, gl.UNSIGNED_BYTE, lut(name));
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.NEAREST);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.NEAREST);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
    this.cmapName = name;
  }

  draw(p: DrawParams): void {
    const gl = this.gl;
    const canvas = gl.canvas as HTMLCanvasElement;
    gl.viewport(0, 0, canvas.width, canvas.height);
    gl.useProgram(this.prog);
    gl.bindVertexArray(this.vao);
    this.setCmap(p.stretch.mode === "diverging" ? "diverging" : p.cmap);
    gl.activeTexture(gl.TEXTURE0); gl.bindTexture(gl.TEXTURE_2D, p.tex);
    gl.activeTexture(gl.TEXTURE1); gl.bindTexture(gl.TEXTURE_2D, p.tex2 ?? p.tex);
    gl.activeTexture(gl.TEXTURE2); gl.bindTexture(gl.TEXTURE_2D, this.cmapTex);
    gl.uniform1i(this.u.u_img!, 0);
    gl.uniform1i(this.u.u_img2!, 1);
    gl.uniform1i(this.u.u_cmap!, 2);
    gl.uniform1f(this.u.u_lo!, p.lo);
    gl.uniform1f(this.u.u_hi!, p.hi);
    gl.uniform1f(this.u.u_beta!, p.stretch.beta);
    gl.uniform1i(this.u.u_mode!, MODE_ID[p.stretch.mode]);
    gl.uniform1f(this.u.u_mix!, p.tex2 ? p.mix ?? 0.5 : 0);
    const span = viewSpan(p.nx, p.ny, canvas.width, canvas.height, p.view.zoom);
    gl.uniform2f(this.u.u_center!, p.view.cx, p.view.cy);
    gl.uniform2f(this.u.u_span!, span.sx, span.sy);
    gl.uniform2f(this.u.u_size!, p.nx, p.ny);
    gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4);
  }

  /** Free GPU resources. Never lose the context: a canvas keeps ONE context for life, so a remount
   *  (React StrictMode, mode switches) would otherwise get a dead context and draw nothing. */
  dispose(): void {
    const gl = this.gl;
    for (const t of this.textures) gl.deleteTexture(t);
    this.textures.clear();
    gl.deleteTexture(this.cmapTex);
    gl.deleteVertexArray(this.vao);
    gl.deleteProgram(this.prog);
  }
}

/** Visible extent in grid pixels for a canvas aspect, keeping pixels square (shared with overlays). */
export function viewSpan(nx: number, ny: number, w: number, h: number, zoom: number): { sx: number; sy: number } {
  const fit = Math.max(nx / Math.max(1, w), ny / Math.max(1, h));   // grid px per canvas px at zoom 1
  return { sx: (fit * w) / zoom, sy: (fit * h) / zoom };
}
