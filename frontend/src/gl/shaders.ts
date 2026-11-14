/**
 * GLSL for the blink viewer (implementation.md §6.3). The stretch algebra is mirrored on the CPU in
 * lib/stretch.ts (stretchValue) and on the server in backend/spherex/render.py (stretch); keep all three
 * in step.
 *
 * Orientation: the payload's row 0 is the SOUTH edge of the north-up grid. WebGL stores the first
 * uploaded row at v = 0, and the quad puts v = 0 at the bottom of the canvas, so the image is
 * north-up, east-left with NO flip (§6.3; checked by the F14 page against the golden "F").
 */
export const VERT = `#version 300 es
in vec2 a_pos;            // clip-space quad, (-1,-1) bottom-left
out vec2 v_uv;            // (0,0) bottom-left of the canvas
void main() {
  v_uv = a_pos * 0.5 + 0.5;
  gl_Position = vec4(a_pos, 0.0, 1.0);
}`;

export const FRAG = `#version 300 es
precision highp float;
uniform sampler2D u_img;      // R16F stack (raw float16 bits; R32F also works)
uniform sampler2D u_img2;     // second stack for onion-skin
uniform sampler2D u_cmap;     // 256x1 RGBA LUT
uniform float u_lo, u_hi, u_beta;
uniform int u_mode;           // 0 lin, 1 asinh, 2 log, 3 sqrt, 4 diverging (diff, symmetric)
uniform float u_mix;          // 0 = only u_img; 0.5 = onion-skin 50/50
uniform vec2 u_center;        // view centre in grid pixel-edge units (col, row)
uniform vec2 u_span;          // visible extent in grid pixels (x, y)
uniform vec2 u_size;          // grid size (nx, ny)
in vec2 v_uv; out vec4 o;

const vec4 NODATA_TINT = vec4(0.18, 0.10, 0.22, 1.0);   // "no data" tint, never black
const vec4 OUTSIDE = vec4(0.047, 0.047, 0.063, 1.0);

float stretch(float x) {
  float t;
  if (u_mode == 4) { t = clamp(0.5 + 0.5 * x / u_hi, 0.0, 1.0); }
  else {
    t = clamp((x - u_lo) / (u_hi - u_lo), 0.0, 1.0);
    if (u_mode == 1) t = asinh(t * u_beta) / asinh(u_beta);
    else if (u_mode == 2) t = log(1.0 + t * u_beta) / log(1.0 + u_beta);
    else if (u_mode == 3) t = sqrt(t);
  }
  return t;
}

vec4 shade(sampler2D img, vec2 uv) {
  float x = texture(img, uv).r;
  if (x < -6.0e4) return NODATA_TINT;
  return texture(u_cmap, vec2((stretch(x) * 255.0 + 0.5) / 256.0, 0.5));
}

void main() {
  vec2 px = u_center + (v_uv - 0.5) * u_span;      // grid pixel-edge coordinates under this fragment
  if (px.x < 0.0 || px.y < 0.0 || px.x >= u_size.x || px.y >= u_size.y) { o = OUTSIDE; return; }
  vec2 uv = px / u_size;
  vec4 c = shade(u_img, uv);
  if (u_mix > 0.0) c = mix(c, shade(u_img2, uv), u_mix);
  o = c;
}`;
