/**
 * Research-grade spectrum chart (implementation.md §6.5). Layers, back to front:
 *   band shading (one tint per SPHEREx detector) → horizontal grid → feature lines with collision-free
 *   labels → individual frame measurements (faint, error bars clipped to the plot) → per-release binned
 *   spectrum (robust weighted mean, error ribbon, bold markers) → template → hover read-out.
 * The y-range is robust (quantiles of the values, never the error bars) and always contains the binned
 * spectrum ± its errors; measurements outside it are drawn as edge carets and counted. Width follows the
 * container, so the same component fills the side panel or an expanded dialog.
 */
import { useEffect, useId, useMemo, useRef, useState, type PointerEvent as RPointerEvent } from "react";
import type { SpectrumRow } from "../api/types";
import { BANDS } from "../lib/constants";
import { abMag, abMagErr, binSpectrum, hampelOutliers, layoutLabels, releaseOf, releaseStyle, robustRange, type SpecBin } from "../lib/spectrum";
import { niceTicks } from "./charts";

const BAND_VAR = ["", "var(--b1)", "var(--b2)", "var(--b3)", "var(--b4)", "var(--b5)", "var(--b6)"];

function Mark({ shape, x, y, r, fill, stroke }: { shape: string; x: number; y: number; r: number; fill: string; stroke?: string }) {
  const s = stroke ? { stroke, strokeWidth: 1 } : {};
  if (shape === "square") return <rect x={x - r} y={y - r} width={2 * r} height={2 * r} fill={fill} {...s} />;
  if (shape === "diamond") return <path d={`M${x},${y - r * 1.3} L${x + r * 1.3},${y} L${x},${y + r * 1.3} L${x - r * 1.3},${y} Z`} fill={fill} {...s} />;
  if (shape === "triangle") return <path d={`M${x},${y - r * 1.3} L${x + r * 1.3},${y + r} L${x - r * 1.3},${y + r} Z`} fill={fill} {...s} />;
  return <circle cx={x} cy={y} r={r} fill={fill} {...s} />;
}

function useWidth(fallback: number) {
  const ref = useRef<HTMLDivElement>(null);
  const [w, setW] = useState(fallback);
  useEffect(() => {
    const el = ref.current;
    if (!el || typeof ResizeObserver === "undefined") return;
    const ro = new ResizeObserver(([e]) => { const cw = Math.round(e!.contentRect.width); if (cw > 120) setW(cw); });
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  return [ref, w] as const;
}

const fmt = (v: number) => {
  const a = Math.abs(v);
  return a >= 1e4 || (a < 1e-2 && v !== 0) ? v.toExponential(1) : a >= 100 ? v.toFixed(0) : a >= 10 ? v.toFixed(1) : v.toPrecision(2);
};

export interface SpectrumChartProps {
  rows: readonly SpectrumRow[];
  mag?: boolean;
  logX?: boolean;
  height?: number;
  template?: { lam: number; flux: number }[];
  templateLabel?: string;
  features?: { lam: number; label: string; contaminant?: boolean }[];
  /** "robust": quantile range around the binned spectrum; "all": every point and error bar. */
  yMode?: "robust" | "all";
  showPoints?: boolean;
  label?: string;
}

export function SpectrumChart({ rows, mag = false, logX = false, height = 260, template, templateLabel, features = [],
  yMode = "robust", showPoints = true, label = "Spectrum: flux against wavelength" }: SpectrumChartProps) {
  const [box, W] = useWidth(380);
  const [hover, setHover] = useState<number | null>(null);
  const clipId = `spc${useId().replace(/[^a-zA-Z0-9]/g, "")}`;
  const spikes = useMemo(() => hampelOutliers(rows), [rows]);
  const bins = useMemo(() => binSpectrum(rows.filter((_, i) => !spikes[i])), [rows, spikes]);
  const nSpikes = spikes.filter(Boolean).length;
  const releases = useMemo(() => [...new Set(rows.map(releaseOf))].sort(), [rows]);

  const Y = (f: number) => (mag ? abMag(f) : f);
  const EY = (f: number, e: number) => (mag ? abMagErr(f, e) : e);
  const keep = (r: SpectrumRow) => Number.isFinite(r.flux) && Number.isFinite(r.lam) && (!mag || r.flux > 0);
  const pts = rows.filter((r, i) => keep(r) && !spikes[i]);
  const rej = rows.filter((r, i) => keep(r) && spikes[i]);
  const bns = bins.filter((b) => !mag || b.flux > 0);
  const tpl = (template ?? []).filter((p) => Number.isFinite(p.flux) && (!mag || p.flux > 0));

  const H = height, L = 56, R = 14, T = 12, B = 40;
  const fx = (v: number) => (logX ? Math.log10(v) : v);
  const xs = pts.concat(rej).flatMap((r) => [r.lam - r.dlam / 2, r.lam + r.dlam / 2]).concat(tpl.map((p) => p.lam)).filter((v) => v > 0 && Number.isFinite(v));
  if (!xs.length) return <p className="hint">No data points.</p>;
  let x0 = fx(Math.min(...xs)), x1 = fx(Math.max(...xs));
  const xp = (x1 - x0 || 0.1) * 0.02; x0 -= xp; x1 += xp;

  // the binned *values* must always be visible; their error bars and ribbons may run off the frame (clipped),
  // or ±1000 µJy errors on a faint source would squash the spectrum into one line again
  const must: [number, number][] = bns.map((b) => [Y(b.flux), Y(b.flux)]);
  const [y0, y1] = yMode === "all"
    ? robustRange(pts.concat(rej).flatMap((r) => [Y(r.flux) - EY(r.flux, r.err), Y(r.flux) + EY(r.flux, r.err)]), must, { qLo: 0, qHi: 1, pad: 0.05 })
    : robustRange(pts.map((r) => Y(r.flux)).concat(tpl.map((p) => Y(p.flux))), must);

  const pw = W - L - R, ph = H - T - B;
  const sx = (v: number) => L + ((fx(v) - x0) / (x1 - x0)) * pw;
  const sy = (v: number) => (mag ? T + ((v - y0) / (y1 - y0)) * ph : T + ph - ((v - y0) / (y1 - y0)) * ph);   // mag: brighter is up
  const inY = (v: number) => v >= y0 && v <= y1;
  const xt = logX ? niceTicks(Math.pow(10, x0), Math.pow(10, x1), Math.max(3, Math.round(pw / 70))) : niceTicks(x0, x1, Math.max(3, Math.round(pw / 70)));
  const yt = niceTicks(y0, y1, Math.max(3, Math.round(ph / 45)));
  // journal style: a common power of ten goes into the axis title, ticks stay short (4, 3, 2 … not 4.0e+5)
  const ymax = Math.max(...yt.map(Math.abs));
  const p10 = !mag && ymax > 0 && (ymax >= 1e4 || ymax < 1e-2) ? Math.floor(Math.log10(ymax)) : 0;
  const tick = (t: number) => (p10 ? Number((t / 10 ** p10).toPrecision(6)).toString() : fmt(t));
  const SUP: Record<string, string> = { "-": "⁻", 0: "⁰", 1: "¹", 2: "²", 3: "³", 4: "⁴", 5: "⁵", 6: "⁶", 7: "⁷", 8: "⁸", 9: "⁹" };
  const yTitle = mag ? "AB mag" : `flux density (${p10 ? `10${String(p10).split("").map((c) => SUP[c] ?? c).join("")} ` : ""}µJy)`;

  // feature labels: lanes so neighbours never overlap (≈ 5.6 px per monospace character at 9 px)
  const feats = features.filter((f) => fx(f.lam) >= x0 && fx(f.lam) <= x1);
  const lanes = layoutLabels(feats.map((f) => ({ x: sx(f.lam) + 2, w: f.label.length * 5.6 })), 3);

  // off-scale points (robust mode): counted and drawn as carets on the edge they left through
  const offScale = pts.concat(rej).filter((r) => !inY(Y(r.flux))).length;

  const segs = new Map<string, SpecBin[]>();      // contiguous ribbons per (release, detector)
  bns.forEach((b) => { const k = `${b.release}|${b.detector}`; const s = segs.get(k); if (s) s.push(b); else segs.set(k, [b]); });

  const onMove = (e: RPointerEvent<SVGRectElement>) => {
    const svg = e.currentTarget.ownerSVGElement!, rect = svg.getBoundingClientRect();
    const mx = ((e.clientX - rect.left) / rect.width) * W, my = ((e.clientY - rect.top) / rect.height) * H;
    let best = -1, bd = Infinity;
    bns.forEach((b, i) => { const d = (sx(b.lam) - mx) ** 2 + 0.25 * (sy(Y(b.flux)) - my) ** 2; if (d < bd) { bd = d; best = i; } });
    setHover(best >= 0 && bd < 60 ** 2 ? best : null);
  };
  const hb = hover !== null ? bns[hover] : undefined;

  return (
    <figure className="chart spectrum-chart" ref={box}>
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={label} style={{ height: H }}>
        <defs><clipPath id={clipId}><rect x={L} y={T} width={pw} height={ph} /></clipPath></defs>
        <rect x={L} y={T} width={pw} height={ph} className="plot-bg" />
        <g clipPath={`url(#${clipId})`}>
          {Object.entries(BANDS).map(([d, [lo, hi]]) => {
            const a = Math.max(fx(lo), x0), b = Math.min(fx(hi), x1);
            if (!(b > a)) return null;
            const X0 = L + ((a - x0) / (x1 - x0)) * pw, X1 = L + ((b - x0) / (x1 - x0)) * pw;
            return <g key={d} className="band-shade"><rect x={X0} y={T} width={X1 - X0} height={ph} style={{ fill: BAND_VAR[Number(d)] }} />
              <text x={X0 + 4} y={T + ph - 5} style={{ fill: BAND_VAR[Number(d)] }}>D{d}</text></g>;
          })}
          {yt.map((t) => <line key={`g${t}`} x1={L} x2={L + pw} y1={sy(t)} y2={sy(t)} className="grid" />)}
          {feats.map((f, i) => (
            <g key={f.label} className={`vline${f.contaminant ? " dashed" : ""}`}>
              <line x1={sx(f.lam)} x2={sx(f.lam)} y1={T} y2={T + ph} />
              {lanes[i]! >= 0 && <text x={sx(f.lam) + 3} y={T + 10 + lanes[i]! * 11}>{f.label}</text>}
              <title>{f.label} · {f.lam} µm</title>
            </g>
          ))}
          {showPoints && pts.map((r, i) => {
            const st = releaseStyle(releaseOf(r)), X = sx(r.lam), v = Y(r.flux), e = EY(r.flux, r.err);
            if (!inY(v)) return null;
            return (
              <g key={i} className={`raw${r.contaminated ? " bad" : ""}`}>
                <line x1={X} x2={X} y1={sy(v - e)} y2={sy(v + e)} stroke={st.colour} />
                <circle cx={X} cy={sy(v)} r={1.7} fill={r.contaminated ? "none" : st.colour} stroke={r.contaminated ? "var(--warn)" : "none"} />
                <title>{`${r.visit} · ${releaseOf(r).toUpperCase()} · D${r.detector} · ${r.lam.toFixed(3)} µm · ${r.flux.toPrecision(3)} ± ${r.err.toPrecision(2)} µJy${r.contaminated ? " · contaminated" : ""}${r.flags?.length ? ` · ${r.flags.join(",")}` : ""}`}</title>
              </g>
            );
          })}
          {showPoints && rej.map((r, i) => {
            const v = Y(r.flux), X = sx(r.lam);
            if (!inY(v)) return null;
            return <g key={`r${i}`} className="spike"><path d={`M${X - 2.5},${sy(v) - 2.5} l5,5 m0,-5 l-5,5`} />
              <title>{`rejected as a spike (Hampel): ${r.visit} · ${releaseOf(r).toUpperCase()} · ${r.lam.toFixed(3)} µm · ${r.flux.toPrecision(3)} ± ${r.err.toPrecision(2)} µJy`}</title></g>;
          })}
          {[...segs.entries()].map(([k, s]) => {
            const st = releaseStyle(s[0]!.release);
            const up = s.map((b) => `${sx(b.lam)},${sy(Y(b.flux) + EY(b.flux, b.err))}`), dn = s.map((b) => `${sx(b.lam)},${sy(Y(b.flux) - EY(b.flux, b.err))}`).reverse();
            return (
              <g key={k} className="binned">
                {s.length > 1 && <polygon points={[...up, ...dn].join(" ")} fill={st.colour} className="ribbon" />}
                {s.length > 1 && <polyline points={s.map((b) => `${sx(b.lam)},${sy(Y(b.flux))}`).join(" ")} stroke={st.colour} className="bin-line" />}
              </g>
            );
          })}
          {tpl.length > 1 && <polyline className="template-line" points={tpl.map((p) => `${sx(p.lam)},${sy(Y(p.flux))}`).join(" ")}><title>{templateLabel}</title></polyline>}
          {bns.map((b, i) => {
            const st = releaseStyle(b.release), X = sx(b.lam), v = Y(b.flux), e = EY(b.flux, b.err);
            return (
              <g key={`b${i}`} className={`bin-pt${hover === i ? " on" : ""}`}>
                <line x1={X} x2={X} y1={sy(v - e)} y2={sy(v + e)} stroke={st.colour} strokeWidth={1.4} />
                <Mark shape={st.shape} x={X} y={sy(v)} r={hover === i ? 4.2 : 3.1} fill={st.colour} stroke="var(--ink-0)" />
              </g>
            );
          })}
        </g>
        {showPoints && pts.concat(rej).map((r, i) => {          // off-scale measurements: a caret on the edge, at their own λ
          const v = Y(r.flux);
          if (inY(v)) return null;
          const top = mag ? v < y0 : v > y1, X = sx(r.lam);
          return <path key={`o${i}`} className="offscale" d={top ? `M${X - 3},${T + 6} l3,-5 l3,5 Z` : `M${X - 3},${T + ph - 6} l3,5 l3,-5 Z`}>
            <title>{`off-scale ${top ? "above" : "below"}: ${r.visit} · ${r.lam.toFixed(3)} µm · ${r.flux.toPrecision(3)} µJy`}</title></path>;
        })}
        {xt.map((t) => <g key={`x${t}`}><line x1={sx(t)} x2={sx(t)} y1={T + ph} y2={T + ph + 4} className="tick" /><text x={sx(t)} y={T + ph + 15} textAnchor="middle" className="tick-label">{t}</text></g>)}
        {yt.map((t) => <g key={`y${t}`}><line x1={L - 4} x2={L} y1={sy(t)} y2={sy(t)} className="tick" /><text x={L - 6} y={sy(t) + 3} textAnchor="end" className="tick-label">{tick(t)}</text></g>)}
        <text x={L + pw / 2} y={H - 6} textAnchor="middle" className="axis-label">λ (µm)</text>
        <text x={13} y={T + ph / 2} textAnchor="middle" className="axis-label" transform={`rotate(-90 13 ${T + ph / 2})`}>{yTitle}</text>
        {hb && (() => {
          const X = sx(hb.lam), Yp = sy(Y(hb.flux)), st = releaseStyle(hb.release);
          const lines = [`${hb.release.toUpperCase()} · D${hb.detector} · ${hb.lam.toFixed(3)} µm`,
            mag ? `${abMag(hb.flux).toFixed(2)} ± ${abMagErr(hb.flux, hb.err).toFixed(2)} AB` : `${hb.flux.toPrecision(4)} ± ${hb.err.toPrecision(2)} µJy`,
            `n = ${hb.n}${hb.nClipped ? ` (+${hb.nClipped} clipped)` : ""} · χ²ᵣ ${hb.chi2r.toFixed(2)}`];
          const bw = Math.min(pw - 8, 14 + 6.4 * Math.max(...lines.map((l) => l.length))), bh = 14 * lines.length + 8;
          const bx = Math.max(L + 4, X + 12 + bw > L + pw ? X - 12 - bw : X + 12), by = Math.min(Math.max(Yp - bh / 2, T + 2), T + ph - bh - 2);
          return (
            <g className="hover" pointerEvents="none">
              <line x1={X} x2={X} y1={T} y2={T + ph} className="crosshair" />
              <rect x={bx} y={by} width={bw} height={bh} rx={4} className="tip" style={{ stroke: st.colour }} />
              {lines.map((l, i) => <text key={i} x={bx + 7} y={by + 16 + 14 * i} className={i ? "tip-text" : "tip-head"}>{l}</text>)}
            </g>
          );
        })()}
        <rect x={L} y={T} width={pw} height={ph} fill="transparent" onPointerMove={onMove} onPointerLeave={() => setHover(null)} />
      </svg>
      <figcaption className="legend">
        {releases.map((r) => { const st = releaseStyle(r); return (
          <span key={r}><svg width="14" height="12" aria-hidden="true"><rect x="0" y="3" width="14" height="6" fill={st.colour} opacity="0.25" /><Mark shape={st.shape} x={7} y={6} r={3} fill={st.colour} /></svg>
            {r.toUpperCase()} binned (n = {bins.filter((b) => b.release === r).reduce((s, b) => s + b.n, 0)})</span>); })}
        {showPoints && <span><svg width="10" height="10" aria-hidden="true"><circle cx="5" cy="5" r="1.8" fill="var(--text-3)" /></svg>individual frames</span>}
        {tpl.length > 1 && <span><svg width="16" height="8" aria-hidden="true"><line x1="0" x2="16" y1="4" y2="4" className="template-line" /></svg>{templateLabel ?? "template"}</span>}
        {nSpikes > 0 && <span className="muted" title="Single frames far from their wavelength neighbours (Hampel filter, 5σ): excluded from the bins, drawn as ×"><svg width="10" height="10" aria-hidden="true"><path d="M2.5,2.5 l5,5 m0,-5 l-5,5" className="spike-key" /></svg>{nSpikes} spike{nSpikes > 1 ? "s" : ""} rejected</span>}
        {offScale > 0 && showPoints && <span className="muted" title="Frames outside the robust y-range: carets on the edge at their wavelength; tick “full y-range” to see them"><svg width="8" height="8" aria-hidden="true"><path d="M1,7 l3,-6 l3,6 Z" className="offscale" /></svg>{offScale} off-scale</span>}
      </figcaption>
    </figure>
  );
}
