/**
 * Small SVG charts (spectra with x/y error bars, light curves, periodograms, astrometric tracks).
 * SVG rather than uPlot (implementation.md §2.2 allowed uPlot or Plotly): error bars in x and y,
 * marker shapes per series (never hue alone, §6.7), no canvas, and testable in jsdom.
 */
import { useId, type ReactNode } from "react";

export interface Pt { x: number; y: number; ex?: number; ey?: number; series: string; title?: string }

const SHAPES = ["circle", "square", "triangle", "diamond", "cross"] as const;
const COLOURS = ["#74c7ec", "#f2b33d", "#f2656f", "#6fcf97", "#b9a2f0", "#ebedf0"];

export function niceTicks(lo: number, hi: number, n = 5): number[] {
  if (!(hi > lo)) return [lo];
  const step0 = (hi - lo) / n, mag = Math.pow(10, Math.floor(Math.log10(step0)));
  const step = [1, 2, 5, 10].map((k) => k * mag).find((s) => s >= step0) ?? step0;
  const out: number[] = [];
  for (let v = Math.ceil(lo / step) * step; v <= hi + 1e-12; v += step) out.push(Number(v.toPrecision(10)));
  return out;
}

function Marker({ shape, x, y, c }: { shape: (typeof SHAPES)[number]; x: number; y: number; c: string }) {
  const r = 3.2;
  switch (shape) {
    case "square": return <rect x={x - r} y={y - r} width={2 * r} height={2 * r} fill={c} />;
    case "triangle": return <path d={`M${x},${y - r - 1} L${x + r + 1},${y + r} L${x - r - 1},${y + r} Z`} fill={c} />;
    case "diamond": return <path d={`M${x},${y - r - 1} L${x + r + 1},${y} L${x},${y + r + 1} L${x - r - 1},${y} Z`} fill={c} />;
    case "cross": return <path d={`M${x - r},${y - r} L${x + r},${y + r} M${x - r},${y + r} L${x + r},${y - r}`} stroke={c} strokeWidth={1.6} />;
    default: return <circle cx={x} cy={y} r={r} fill={c} />;
  }
}

export function ScatterChart({ points, xLabel, yLabel, logX = false, height = 220, width = 380, vlines = [], line, yInvert = false, label, clipErrors = false }: {
  points: Pt[]; xLabel: string; yLabel: string; logX?: boolean; height?: number; width?: number;
  vlines?: { x: number; label: string; dashed?: boolean }[]; line?: { x: number; y: number }[]; yInvert?: boolean; label: string;
  /** Axis range from the points alone; error bars are clipped at the plot edge (one degenerate fit with a huge error
   *  bar must not shrink every other point to a dot). */
  clipErrors?: boolean;
}) {
  const clipId = useId();
  const W = width, H = Math.round(height * 0.85), L = 50, R = 8, T = 10, B = 36;   // default W ≈ the side panel's width, so SVG text renders near its nominal size; wider in an expanded dialog
  const fx = (v: number) => (logX ? Math.log10(v) : v);
  const ex = (p: Pt) => (clipErrors ? 0 : p.ex ?? 0), ey = (p: Pt) => (clipErrors ? 0 : p.ey ?? 0);
  const xs = points.flatMap((p) => [p.x - ex(p), p.x + ex(p)]).concat(line?.map((p) => p.x) ?? []).filter((v) => Number.isFinite(v) && (!logX || v > 0));
  const ys = points.flatMap((p) => [p.y - ey(p), p.y + ey(p)]).concat(line?.map((p) => p.y) ?? []).filter(Number.isFinite);
  if (!xs.length || !ys.length) return <p className="hint">No data points.</p>;
  let x0 = fx(Math.min(...xs)), x1 = fx(Math.max(...xs)), y0 = Math.min(...ys), y1 = Math.max(...ys);
  if (x1 === x0) { x0 -= 1; x1 += 1; }
  if (y1 === y0) { y0 -= 1; y1 += 1; }
  const py = (y1 - y0) * 0.06; y0 -= py; y1 += py;
  const sx = (v: number) => L + ((fx(v) - x0) / (x1 - x0)) * (W - L - R);
  const sy = (v: number) => (yInvert ? T + ((v - y0) / (y1 - y0)) * (H - T - B) : H - B - ((v - y0) / (y1 - y0)) * (H - T - B));
  const series = [...new Set(points.map((p) => p.series))];
  const xt = logX ? niceTicks(Math.pow(10, x0), Math.pow(10, x1), 6) : niceTicks(x0, x1, 6);
  const yt = niceTicks(y0, y1, 5);
  const els: ReactNode[] = [];
  points.forEach((p, i) => {
    const k = series.indexOf(p.series), c = COLOURS[k % COLOURS.length]!, shape = SHAPES[k % SHAPES.length]!;
    const X = sx(p.x), Y = sy(p.y);
    if (!Number.isFinite(X) || !Number.isFinite(Y)) return;
    els.push(
      <g key={i} className="pt">
        {p.ex ? <line x1={sx(p.x - p.ex)} x2={sx(p.x + p.ex)} y1={Y} y2={Y} stroke={c} strokeOpacity={0.6} /> : null}
        {p.ey ? <line x1={X} x2={X} y1={sy(p.y - p.ey)} y2={sy(p.y + p.ey)} stroke={c} strokeOpacity={0.6} /> : null}
        <Marker shape={shape} x={X} y={Y} c={c} />
        {p.title && <title>{p.title}</title>}
      </g>,
    );
  });
  return (
    <figure className="chart">
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={label}>
        <rect x={L} y={T} width={W - L - R} height={H - T - B} className="plot-bg" />
        {xt.map((t) => <g key={`x${t}`}><line x1={sx(t)} x2={sx(t)} y1={H - B} y2={H - B + 4} className="tick" /><text x={sx(t)} y={H - B + 15} textAnchor="middle" className="tick-label">{t}</text></g>)}
        {yt.map((t) => <g key={`y${t}`}><line x1={L - 4} x2={L} y1={sy(t)} y2={sy(t)} className="tick" /><text x={L - 6} y={sy(t) + 3} textAnchor="end" className="tick-label">{Math.abs(t) >= 1e4 || (Math.abs(t) < 1e-2 && t !== 0) ? t.toExponential(1) : t}</text></g>)}
        {vlines.filter((v) => fx(v.x) >= x0 && fx(v.x) <= x1).map((v, i) => (   // alternate label heights so close features stay readable
          <g key={v.label} className={`vline${v.dashed ? " dashed" : ""}`}><line x1={sx(v.x)} x2={sx(v.x)} y1={T} y2={H - B} /><text x={sx(v.x) + 2} y={T + 10 + (i % 2) * 11}>{v.label}</text></g>
        ))}
        {line && <polyline className="median-line" points={line.map((p) => `${sx(p.x)},${sy(p.y)}`).join(" ")} />}
        {clipErrors && <clipPath id={clipId}><rect x={L} y={T} width={W - L - R} height={H - T - B} /></clipPath>}
        <g clipPath={clipErrors ? `url(#${clipId})` : undefined}>{els}</g>
        <text x={(L + W - R) / 2} y={H - 4} textAnchor="middle" className="axis-label">{xLabel}</text>
        <text x={12} y={(T + H - B) / 2} textAnchor="middle" className="axis-label" transform={`rotate(-90 12 ${(T + H - B) / 2})`}>{yLabel}</text>
      </svg>
      {series.length > 1 && (
        <figcaption className="legend">
          {series.map((s, k) => (
            <span key={s}><svg width="12" height="12" aria-hidden="true"><Marker shape={SHAPES[k % SHAPES.length]!} x={6} y={6} c={COLOURS[k % COLOURS.length]!} /></svg> {s}</span>
          ))}
        </figcaption>
      )}
    </figure>
  );
}
