/**
 * WebGL2 canvas for one panel of the blink (implementation.md §6.3). Textures are uploaded once per
 * payload and kept resident. Pan (drag), zoom (wheel / pinch-free double-click reset), and hover
 * report grid pixels through lib/viewport (the same algebra as the shader).
 */
import { useEffect, useRef } from "react";
import { BlinkRenderer, type ViewTransform } from "../gl/renderer";
import type { CmapName } from "../gl/colormaps";
import type { StretchSpec } from "../lib/stretch";
import { canvasToGrid, canvasToPixel, clampView, fullView, zoomAt } from "../lib/viewport";

export interface GLCanvasProps {
  bits: Uint16Array | null;
  bits2?: Uint16Array | null;
  mix?: number;
  nx: number;
  ny: number;
  lo: number;
  hi: number;
  stretch: StretchSpec;
  cmap: CmapName;
  transform: ViewTransform | null;
  onTransform?: (t: ViewTransform) => void;
  onHover?: (p: { col: number; row: number; x: number; y: number } | null) => void;
  onClickPixel?: (p: { col: number; row: number }) => void;
  onError?: (why: string) => void;
  label: string;
}

const RESTORE_MS = 3000;

export function GLCanvas(p: GLCanvasProps) {
  const ref = useRef<HTMLCanvasElement>(null);
  const r = useRef<BlinkRenderer | null>(null);
  const texCache = useRef(new WeakMap<Uint16Array, WebGLTexture>());
  const drag = useRef<{ x: number; y: number; t: ViewTransform; moved: boolean } | null>(null);
  // Two-finger pinch (audit F-22): pointers currently down, and the pinch's start distance and view.
  const pointers = useRef(new Map<number, { x: number; y: number }>());
  const pinch = useRef<{ d0: number; t: ViewTransform } | null>(null);
  const props = useRef(p);
  props.current = p;

  const draw = () => {
    const rr = r.current, c = ref.current, q = props.current;
    if (!rr || !c || !q.bits) {
      if (rr) { rr.gl.clearColor(0.047, 0.047, 0.063, 1); rr.gl.clear(rr.gl.COLOR_BUFFER_BIT); }
      return;
    }
    const tex = (bits: Uint16Array) => {
      let t = texCache.current.get(bits);
      if (!t) { t = rr.upload(q.nx, q.ny, bits); texCache.current.set(bits, t); }
      return t;
    };
    rr.draw({
      tex: tex(q.bits), tex2: q.bits2 ? tex(q.bits2) : null, mix: q.mix, lo: q.lo, hi: q.hi, stretch: q.stretch,
      cmap: q.cmap, nx: q.nx, ny: q.ny, view: q.transform ?? fullView(q.nx, q.ny),
    });
  };

  useEffect(() => {
    const c = ref.current!;
    try {
      r.current = new BlinkRenderer(c);
    } catch (e) {
      props.current.onError?.((e as Error).message);
      return;
    }
    // A lost context (a backgrounded phone tab, a GPU reset) is usually restored by the browser: rebuild the renderer
    // and redraw. Only if it is not back within RESTORE_MS does the viewer switch to server PNGs (audit F-17).
    let giveUp: ReturnType<typeof setTimeout> | null = null;
    const lost = (ev: Event) => {
      ev.preventDefault();                       // tells the browser we will handle the restore
      r.current = null;
      texCache.current = new WeakMap();          // textures died with the context
      giveUp = setTimeout(() => props.current.onError?.("WebGL context lost"), RESTORE_MS);
    };
    const restored = () => {
      if (giveUp) { clearTimeout(giveUp); giveUp = null; }
      try { r.current = new BlinkRenderer(c); draw(); } catch (e) { props.current.onError?.((e as Error).message); }
    };
    c.addEventListener("webglcontextlost", lost);
    c.addEventListener("webglcontextrestored", restored);
    const wheel = (e: WheelEvent) => {          // native + non-passive, so the page does not scroll
      const q = props.current;
      if (!q.onTransform) return;
      e.preventDefault();
      const b = c.getBoundingClientRect();
      q.onTransform(zoomAt(q.transform ?? fullView(q.nx, q.ny), e.deltaY < 0 ? 1.25 : 0.8,
        e.clientX - b.left, e.clientY - b.top, b.width, b.height, q.nx, q.ny));
    };
    c.addEventListener("wheel", wheel, { passive: false });
    const ro = new ResizeObserver(() => {
      const dpr = Math.min(2, window.devicePixelRatio || 1);
      c.width = Math.max(1, Math.round(c.clientWidth * dpr));
      c.height = Math.max(1, Math.round(c.clientHeight * dpr));
      draw();
    });
    ro.observe(c);
    return () => {
      ro.disconnect();
      if (giveUp) clearTimeout(giveUp);
      c.removeEventListener("webglcontextlost", lost);
      c.removeEventListener("webglcontextrestored", restored);
      c.removeEventListener("wheel", wheel);
      r.current?.dispose();
      r.current = null;
      texCache.current = new WeakMap();
    };
  }, []);

  // Redraw whenever anything visual changes; rAF keeps 60 fps blinking cheap.
  useEffect(() => {
    const id = requestAnimationFrame(draw);
    return () => cancelAnimationFrame(id);
  });

  const local = (e: React.PointerEvent | React.MouseEvent) => {
    const b = ref.current!.getBoundingClientRect();
    return { x: e.clientX - b.left, y: e.clientY - b.top, w: b.width, h: b.height };
  };
  const tf = () => p.transform ?? fullView(p.nx, p.ny);

  return (
    <canvas
      ref={ref}
      className="gl-canvas"
      role="img"
      aria-label={p.label}
      onPointerDown={(e) => {
        (e.target as Element).setPointerCapture?.(e.pointerId);
        const { x, y } = local(e);
        pointers.current.set(e.pointerId, { x, y });
        if (pointers.current.size === 2) {
          const [a, b] = [...pointers.current.values()] as [{ x: number; y: number }, { x: number; y: number }];
          pinch.current = { d0: Math.max(1, Math.hypot(a.x - b.x, a.y - b.y)), t: tf() };
          drag.current = null;
          return;
        }
        drag.current = { x, y, t: tf(), moved: false };
      }}
      onPointerMove={(e) => {
        const { x, y, w, h } = local(e);
        if (pointers.current.has(e.pointerId)) pointers.current.set(e.pointerId, { x, y });
        const pz = pinch.current;
        if (pz && pointers.current.size === 2 && p.onTransform) {
          const [a, b] = [...pointers.current.values()] as [{ x: number; y: number }, { x: number; y: number }];
          const ratio = Math.hypot(a.x - b.x, a.y - b.y) / pz.d0;
          p.onTransform(zoomAt(pz.t, ratio, (a.x + b.x) / 2, (a.y + b.y) / 2, w, h, p.nx, p.ny));
          return;
        }
        const d = drag.current;
        if (d && p.onTransform && d.t.zoom > 1) {
          const a = canvasToGrid(d.x, d.y, w, h, p.nx, p.ny, d.t), b = canvasToGrid(x, y, w, h, p.nx, p.ny, d.t);
          if (Math.hypot(x - d.x, y - d.y) > 3) d.moved = true;
          p.onTransform(clampView({ ...d.t, cx: d.t.cx - (b.gx - a.gx), cy: d.t.cy - (b.gy - a.gy) }, p.nx, p.ny));
        }
        const px = canvasToPixel(x, y, w, h, p.nx, p.ny, tf());
        p.onHover?.(px ? { ...px, x, y } : null);
      }}
      onPointerUp={(e) => {
        pointers.current.delete(e.pointerId);
        if (pinch.current) {                       // end of a pinch is never a click
          if (pointers.current.size < 2) pinch.current = null;
          drag.current = null;
          return;
        }
        const d = drag.current;
        drag.current = null;
        if (d && !d.moved && p.onClickPixel) {
          const { x, y, w, h } = local(e);
          const px = canvasToPixel(x, y, w, h, p.nx, p.ny, tf());
          if (px) p.onClickPixel(px);
        }
      }}
      onPointerCancel={(e) => { pointers.current.delete(e.pointerId); pinch.current = null; drag.current = null; }}
      onPointerLeave={() => p.onHover?.(null)}
      onDoubleClick={() => p.onTransform?.(fullView(p.nx, p.ny))}
    />
  );
}
