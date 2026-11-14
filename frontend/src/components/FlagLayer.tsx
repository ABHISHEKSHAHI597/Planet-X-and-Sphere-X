/**
 * Flag contours (P0-6): outlines of the selected flag planes of the CURRENT stack's flag_or, drawn
 * at pixel edges so a hole like Barnard's OVERFLOW core is visible and explained. Planes are told
 * apart by dash pattern as well as colour (implementation.md §6.7).
 */
import { useEffect, useRef, useState } from "react";
import type { ViewTransform } from "../gl/renderer";
import { FLAG_STYLE } from "../content/flags";
import { getFlags } from "../hooks/stackCache";
import { fullView, gridToCanvas } from "../lib/viewport";

export function FlagLayer({ viewKey, bin, band, format, planes, bits, nx, ny, transform }: {
  viewKey: string; bin: string; band: number; format: string; planes: string[]; bits: Record<string, number>;
  nx: number; ny: number; transform: ViewTransform | null;
}) {
  const ref = useRef<HTMLCanvasElement>(null);
  const [flags, setFlags] = useState<Uint32Array | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    let live = true;
    setFlags(null); setErr(null);
    if (!planes.length) return;
    getFlags(viewKey, bin, band, format).then((f) => live && setFlags(f), (e) => live && setErr(String(e.message ?? e)));
    return () => { live = false; };
  }, [viewKey, bin, band, format, planes.length]);

  useEffect(() => {
    const c = ref.current;
    if (!c) return;
    const dpr = Math.min(2, window.devicePixelRatio || 1);
    c.width = Math.round(c.clientWidth * dpr); c.height = Math.round(c.clientHeight * dpr);
    const ctx = c.getContext("2d");
    if (!ctx) return;
    ctx.clearRect(0, 0, c.width, c.height);
    if (!flags || flags.length !== nx * ny) return;
    const w = c.clientWidth, h = c.clientHeight, v = transform ?? fullView(nx, ny);
    ctx.scale(dpr, dpr);
    for (const name of planes) {
      const bit = bits[name];
      if (bit === undefined) continue;
      const m = 1 << bit;
      const on = (col: number, row: number) => col >= 0 && row >= 0 && col < nx && row < ny && (flags[row * nx + col]! & m) !== 0;
      const st = FLAG_STYLE[name] ?? { color: "#ffffff", dash: "3 3" };
      ctx.strokeStyle = st.color; ctx.lineWidth = 1.5;
      ctx.setLineDash(st.dash ? st.dash.split(" ").map(Number) : []);
      ctx.beginPath();
      for (let row = 0; row < ny; row++) for (let col = 0; col < nx; col++) {
        if (!on(col, row)) continue;
        const seg = (x0: number, y0: number, x1: number, y1: number) => {
          const a = gridToCanvas(x0, y0, w, h, nx, ny, v), b = gridToCanvas(x1, y1, w, h, nx, ny, v);
          ctx.moveTo(a.x, a.y); ctx.lineTo(b.x, b.y);
        };
        if (!on(col - 1, row)) seg(col, row, col, row + 1);
        if (!on(col + 1, row)) seg(col + 1, row, col + 1, row + 1);
        if (!on(col, row - 1)) seg(col, row, col + 1, row);
        if (!on(col, row + 1)) seg(col, row + 1, col + 1, row + 1);
      }
      ctx.stroke();
    }
  });

  return (
    <>
      <canvas ref={ref} className="flag-layer" aria-hidden="true" />
      {err && <div className="flag-error" role="status">Flags unavailable: {err}</div>}
    </>
  );
}
