/**
 * SVG overlays drawn in SKY coordinates through the manifest grid (implementation.md §6.3):
 * fixed crosshair, predicted track pos(t) (PM + parallax, from the manifest), fitted motion vector
 * (×10), catalogue markers propagated server-side to the bin epoch, diff annotations, the selected
 * source, a compass and a scale bar.
 */
import { useEffect, useRef, useState } from "react";
import type { DiffAnnotation, GridInfo, OverlaySource, TrackPoint } from "../api/types";

/** A marker on the image: a catalogue source (`cat` names the overlay it came from) or, for the asteroid layer, a
 *  per-exposure transient of the stack (`frame`, `npix`). */
export interface Marker extends OverlaySource {
  cat?: "gaia" | "wise" | "simbad" | "sso" | "transient";
  frame?: string;
  npix?: number;
}
import type { ViewTransform } from "../gl/renderer";
import { fullView, pixelToCanvas } from "../lib/viewport";
import { skyToPixel } from "../lib/wcs";

export interface OverlayProps {
  grid: GridInfo;
  transform: ViewTransform | null;
  track?: TrackPoint[];
  currentBin?: string | null;
  crosshair?: boolean;
  vector?: { ra: number; dec: number; pmra: number; pmdec: number; label: string } | null;
  sources?: Marker[];
  /** Asteroid-layer markers (known bodies, transients) become clickable and report the marker here. */
  onPick?: (s: Marker) => void;
  picked?: string | null;
  annotations?: DiffAnnotation[];
  selected?: { ra: number; dec: number } | null;
  badge?: string | null;
}

function useSize(ref: React.RefObject<SVGSVGElement | null>) {
  const [s, setS] = useState({ w: 1, h: 1 });
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const ro = new ResizeObserver(() => setS({ w: el.clientWidth || 1, h: el.clientHeight || 1 }));
    ro.observe(el);
    return () => ro.disconnect();
  }, [ref]);
  return s;
}

export function OverlayLayer(p: OverlayProps) {
  const ref = useRef<SVGSVGElement>(null);
  const { w, h } = useSize(ref);
  const [ny, nx] = p.grid.shape;
  const v = p.transform ?? fullView(nx, ny);
  const at = (ra: number, dec: number) => {
    const px = skyToPixel(p.grid, ra, dec);
    return px ? pixelToCanvas(px.col, px.row, w, h, nx, ny, v) : null;
  };
  const pxPerGrid = (w / nx) * v.zoom;
  const trackPts = (p.track ?? []).map((t) => ({ t, c: at(t.ra, t.dec) })).filter((x) => x.c) as { t: TrackPoint; c: { x: number; y: number } }[];
  const centre = pixelToCanvas((nx - 1) / 2, (ny - 1) / 2, w, h, nx, ny, v);
  // scale bar: 1′ (or 30″ for small views)
  const barArcsec = p.grid.pix_arcsec * nx > 240 ? 60 : 30;
  const barPx = (barArcsec / p.grid.pix_arcsec) * pxPerGrid;

  let vec: { a: { x: number; y: number }; b: { x: number; y: number } } | null = null;
  if (p.vector) {
    const a = at(p.vector.ra, p.vector.dec);
    // ×10 scaling of one year's motion (implementation.md §6.3 "fitted vector: an arrow scaled ×10")
    const dra = (10 * p.vector.pmra) / 3.6e6 / Math.cos((p.vector.dec * Math.PI) / 180), ddec = (10 * p.vector.pmdec) / 3.6e6;
    const b = at(p.vector.ra + dra, p.vector.dec + ddec);
    if (a && b) vec = { a, b };
  }

  return (
    <svg ref={ref} className="overlay" aria-hidden="true">
      <defs>
        <marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
          <path d="M0,0 L10,5 L0,10 z" fill="currentColor" />
        </marker>
      </defs>
      {p.crosshair && (
        <g className="ov-crosshair">
          {[[-1, 0], [1, 0], [0, -1], [0, 1]].map(([dx, dy], i) => (
            <line key={i} x1={centre.x + dx! * 0.9 * pxPerGrid * 2} y1={centre.y + dy! * 0.9 * pxPerGrid * 2}
              x2={centre.x + dx! * 0.9 * pxPerGrid * 5} y2={centre.y + dy! * 0.9 * pxPerGrid * 5} />
          ))}
        </g>
      )}
      {trackPts.length > 0 && (
        <g className="ov-track">
          <polyline points={trackPts.map((x) => `${x.c.x},${x.c.y}`).join(" ")} />
          {trackPts.map(({ t, c }) => (
            <circle key={t.bin} cx={c.x} cy={c.y} r={t.bin === p.currentBin ? 4.5 : 3} className={t.bin === p.currentBin ? "current" : ""} />
          ))}
        </g>
      )}
      {vec && (
        <g className="ov-vector">
          <line x1={vec.a.x} y1={vec.a.y} x2={vec.b.x} y2={vec.b.y} markerEnd="url(#arrow)" />
          <text x={vec.b.x + 6} y={vec.b.y - 6}>{p.vector!.label}</text>
        </g>
      )}
      {(p.sources ?? []).map((s) => {
        const c = at(s.ra, s.dec);
        if (!c) return null;
        const pick = p.onPick && (s.cat === "sso" || s.cat === "transient") ? () => p.onPick!(s) : undefined;
        const cls = `${s.cat === "transient" ? "ov-transient" : s.cat === "sso" ? "ov-sso" : s.label ? "ov-simbad" : "ov-gaia"}${pick ? " pickable" : ""}${p.picked === s.id ? " picked" : ""}`;
        if (s.cat === "transient") {
          // Transients are many and unvetted: a small unlabelled diamond each; details on click (side panel).
          const r = Math.max(3.5, 0.9 * pxPerGrid);
          return (
            <g key={s.id} className={cls} onClick={pick}>
              <path d={`M${c.x},${c.y - r} L${c.x + r},${c.y} L${c.x},${c.y + r} L${c.x - r},${c.y} Z`} />
            </g>
          );
        }
        if (s.cat === "wise") {
          // AllWISE: where WISE saw the source around 2010, not moved to this visit. A square, so it is never
          // mistaken for a Gaia circle (which IS moved to the visit epoch).
          const r = Math.max(5, 1.6 * pxPerGrid);
          return <g key={s.id} className="ov-wise"><rect x={c.x - r} y={c.y - r} width={2 * r} height={2 * r} /></g>;
        }
        return (
          <g key={s.id} className={cls} onClick={pick}>
            <circle cx={c.x} cy={c.y} r={Math.max(5, 1.6 * pxPerGrid)} />
            {s.cat === "sso" ? <text x={c.x + 8} y={c.y - 8}>{s.id}</text> : s.label && <text x={c.x + 8} y={c.y - 8}>{s.label}</text>}
          </g>
        );
      })}
      {(p.annotations ?? []).map((a, i) => {
        const c = at(a.ra, a.dec);
        if (!c) return null;
        const d = a.to_ra !== undefined && a.to_dec !== undefined ? at(a.to_ra, a.to_dec) : null;
        return (
          <g key={i} className={`ov-ann ${a.kind}`}>
            {d ? <line x1={c.x} y1={c.y} x2={d.x} y2={d.y} markerEnd="url(#arrow)" /> : <circle cx={c.x} cy={c.y} r={10} />}
            <text x={(d ?? c).x + 8} y={(d ?? c).y + 16}>{a.label}</text>
          </g>
        );
      })}
      {p.selected && (() => {
        const c = at(p.selected.ra, p.selected.dec);
        return c ? <rect className="ov-sel" x={c.x - 9} y={c.y - 9} width={18} height={18} /> : null;
      })()}
      <g className="ov-compass" transform={`translate(${w - 46},${h - 18})`}>
        <line x1={0} y1={0} x2={0} y2={-26} markerEnd="url(#arrow)" />
        <text x={-4} y={-30}>N</text>
        <line x1={0} y1={0} x2={-26} y2={0} markerEnd="url(#arrow)" />
        <text x={-40} y={4}>E</text>
      </g>
      <g className="ov-scale" transform={`translate(12,${h - 14})`}>
        <line x1={0} y1={0} x2={barPx} y2={0} />
        <text x={0} y={-5}>{barArcsec === 60 ? "1′" : "30″"}</text>
      </g>
      {p.badge && <text className="ov-badge" x={10} y={20}>{p.badge}</text>}
    </svg>
  );
}
