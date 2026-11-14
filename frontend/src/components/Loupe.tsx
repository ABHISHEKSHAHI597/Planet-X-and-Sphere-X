/**
 * Loupe (implementation.md §6.3): ×4 magnifier under the cursor with pixel value, σ, λ range,
 * frames and flags. Values are decoded from the .f16 on the CPU; σ and flags load lazily.
 */
import { useEffect, useLayoutEffect, useRef, useState } from "react";
import type { CmapName } from "../gl/colormaps";
import { BANDS } from "../lib/constants";
import { formatDec, formatRA } from "../lib/coords";
import { renderRGBA, type StretchSpec } from "../lib/stretch";
import { getFlags, getValues, getVariance } from "../hooks/stackCache";
import type { Hover } from "../state/store";

const R = 7;                 // 15×15 pixels around the cursor
const SCALE = 8;
const GAP = 16;              // distance between the cursor and the loupe
const PAD = 6;               // minimum inset from the plate edge

/**
 * Place a w×h box near the cursor (x, y) inside a W×H container without clipping. Tries, in order:
 * right of the cursor, left, below, above — first with a comfortable gap, then a tight one — and keeps
 * the box centred on the cursor along the other axis. Only when no side has room (tiny plate) does it
 * fall back to the corner farthest from the cursor, still fully inside.
 */
export function placeLoupe(x: number, y: number, w: number, h: number, W: number, H: number): { left: number; top: number } {
  const clamp = (v: number, lo: number, hi: number) => Math.max(lo, Math.min(v, Math.max(lo, hi)));
  const maxL = W - w - PAD, maxT = H - h - PAD;
  const midT = clamp(y - h / 2, PAD, maxT), midL = clamp(x - w / 2, PAD, maxL);
  for (const g of [GAP, 4]) {
    if (x + g + w <= W - PAD) return { left: x + g, top: midT };
    if (x - g - w >= PAD) return { left: x - g - w, top: midT };
    if (y + g + h <= H - PAD) return { left: midL, top: y + g };
    if (y - g - h >= PAD) return { left: midL, top: y - g - h };
  }
  return { left: x > W / 2 ? PAD : clamp(maxL, PAD, maxL), top: y > H / 2 ? PAD : clamp(maxT, PAD, maxT) };
}

export function Loupe({ hover, viewKey, bin, band, formats, nx, ny, lo, hi, stretch, cmap, bits, nhits }: {
  hover: Hover; viewKey: string; bin: string; band: number; formats: { stack: string; science: string; flags: string };
  nx: number; ny: number; lo: number; hi: number; stretch: StretchSpec; cmap: CmapName; bits: Record<string, number>; nhits: number;
}) {
  const ref = useRef<HTMLCanvasElement>(null);
  const box = useRef<HTMLDivElement>(null);
  const [vals, setVals] = useState<Float32Array | null>(null);
  const [vr, setVr] = useState<Float32Array | null>(null);
  const [fl, setFl] = useState<Uint32Array | null>(null);

  useEffect(() => {
    let live = true;
    getValues(viewKey, bin, band, formats.stack).then((v) => live && setVals(v), () => undefined);
    getVariance(viewKey, bin, band, formats.science).then((v) => live && setVr(v), () => live && setVr(null));
    getFlags(viewKey, bin, band, formats.flags).then((v) => live && setFl(v), () => live && setFl(null));
    return () => { live = false; };
  }, [viewKey, bin, band, formats.stack, formats.science, formats.flags]);

  useEffect(() => {
    const c = ref.current;
    if (!c || !vals) return;
    const n = 2 * R + 1;
    const patch = new Float32Array(n * n).fill(NaN);
    for (let dy = -R; dy <= R; dy++) for (let dx = -R; dx <= R; dx++) {
      const col = hover.col + dx, row = hover.row + dy;
      if (col >= 0 && row >= 0 && col < nx && row < ny) patch[(dy + R) * n + (dx + R)] = vals[row * nx + col]!;
    }
    const rgba = renderRGBA(patch, n, n, lo, hi, stretch, cmap);    // row-flipped to top-north
    const ctx = c.getContext("2d")!;
    const tmp = document.createElement("canvas");
    tmp.width = n; tmp.height = n;
    tmp.getContext("2d")!.putImageData(new ImageData(rgba, n, n), 0, 0);
    ctx.imageSmoothingEnabled = false;
    ctx.clearRect(0, 0, c.width, c.height);
    ctx.drawImage(tmp, 0, 0, n * SCALE, n * SCALE);
    ctx.strokeStyle = "#fff"; ctx.lineWidth = 1;
    ctx.strokeRect(R * SCALE + 0.5, R * SCALE + 0.5, SCALE - 1, SCALE - 1);
  }, [vals, hover.col, hover.row, nx, ny, lo, hi, stretch, cmap]);

  const i = hover.row * nx + hover.col;
  const v = vals?.[i];
  const sig = vr ? Math.sqrt(vr[i]!) : NaN;
  const f = fl?.[i] ?? 0;
  const names = Object.entries(bits).filter(([, b]) => f & (1 << b)).map(([n]) => n);
  const lam = BANDS[band];

  // Measure after every render (content height changes as σ/flags load) and keep the box inside the plate.
  useLayoutEffect(() => {
    const el = box.current, parent = el?.offsetParent as HTMLElement | null;
    if (!el || !parent) return;
    const { left, top } = placeLoupe(hover.x, hover.y, el.offsetWidth, el.offsetHeight, parent.clientWidth, parent.clientHeight);
    el.style.left = `${Math.round(left)}px`;
    el.style.top = `${Math.round(top)}px`;
  });

  return (
    <div ref={box} className="loupe" role="status" aria-live="off">
      <canvas ref={ref} width={(2 * R + 1) * SCALE} height={(2 * R + 1) * SCALE} aria-hidden="true" />
      <dl>
        <dt>pixel</dt><dd>({hover.col}, {hover.row})</dd>
        <dt>RA, Dec</dt><dd>{formatRA(hover.ra, 2)} {formatDec(hover.dec, 1)}</dd>
        <dt>value</dt><dd>{v === undefined ? "…" : Number.isNaN(v) ? "no data" : `${v.toPrecision(4)} MJy/sr`}</dd>
        <dt>σ</dt><dd>{Number.isFinite(sig) ? `${sig.toPrecision(3)} MJy/sr` : "—"}</dd>
        <dt>λ range</dt><dd>{lam ? `${lam[0]}–${lam[1]} µm (band ${band})` : "—"}</dd>
        <dt>frames</dt><dd>≤ {nhits}</dd>
        <dt>flags</dt><dd>{fl ? (names.length ? names.join(", ") : "none") : "—"}</dd>
      </dl>
    </div>
  );
}
