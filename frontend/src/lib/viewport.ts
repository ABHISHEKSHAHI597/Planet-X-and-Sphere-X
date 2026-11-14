/**
 * Canvas ↔ grid mapping, shared by the WebGL shader (same algebra in gl/shaders.ts main()),
 * the SVG overlay, the loupe and pan/zoom. Grid "edge" coordinates: pixel (col, row) covers
 * [col, col+1] × [row, row+1]; gy grows NORTH (row 0 = south). Canvas y grows DOWN.
 */
import { viewSpan, type ViewTransform } from "../gl/renderer";

export function fullView(nx: number, ny: number): ViewTransform {
  return { cx: nx / 2, cy: ny / 2, zoom: 1 };
}

export function canvasToGrid(x: number, y: number, w: number, h: number, nx: number, ny: number, v: ViewTransform) {
  const { sx, sy } = viewSpan(nx, ny, w, h, v.zoom);
  return { gx: v.cx + (x / w - 0.5) * sx, gy: v.cy + (0.5 - y / h) * sy };
}

export function gridToCanvas(gx: number, gy: number, w: number, h: number, nx: number, ny: number, v: ViewTransform) {
  const { sx, sy } = viewSpan(nx, ny, w, h, v.zoom);
  return { x: ((gx - v.cx) / sx + 0.5) * w, y: (0.5 - (gy - v.cy) / sy) * h };
}

/** Pixel centre (0-based col,row) → canvas. */
export function pixelToCanvas(col: number, row: number, w: number, h: number, nx: number, ny: number, v: ViewTransform) {
  return gridToCanvas(col + 0.5, row + 0.5, w, h, nx, ny, v);
}

/** Canvas → the pixel under it, or null outside the grid. */
export function canvasToPixel(x: number, y: number, w: number, h: number, nx: number, ny: number, v: ViewTransform) {
  const { gx, gy } = canvasToGrid(x, y, w, h, nx, ny, v);
  const col = Math.floor(gx), row = Math.floor(gy);
  if (col < 0 || row < 0 || col >= nx || row >= ny) return null;
  return { col, row };
}

/** Zoom about a canvas point, keeping it fixed; clamps zoom to [1, 16]. */
export function zoomAt(v: ViewTransform, factor: number, x: number, y: number, w: number, h: number, nx: number, ny: number): ViewTransform {
  const zoom = Math.min(16, Math.max(1, v.zoom * factor));
  const before = canvasToGrid(x, y, w, h, nx, ny, v);
  const after = canvasToGrid(x, y, w, h, nx, ny, { ...v, zoom });
  return clampView({ cx: v.cx + before.gx - after.gx, cy: v.cy + before.gy - after.gy, zoom }, nx, ny);
}

export function clampView(v: ViewTransform, nx: number, ny: number): ViewTransform {
  if (v.zoom <= 1) return fullView(nx, ny);
  return { zoom: v.zoom, cx: Math.min(nx, Math.max(0, v.cx)), cy: Math.min(ny, Math.max(0, v.cy)) };
}
