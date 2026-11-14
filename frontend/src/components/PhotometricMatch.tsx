/**
 * The photometric match behind a difference image (decision record 0008, workflow.md §11.2): what was
 * matched, how well, and what may be read from the image. Cross-release (QR2 − QR3) pairs carry the amber
 * "positions only" framing; same-release pairs show the in-situ check as a calibration diagnostic.
 */
import type { PhotometricMatch } from "../api/types";

function Spark({ pm }: { pm: PhotometricMatch }) {
  const bins = (pm.bins ?? []).filter((b) => b.lam != null && Number.isFinite(b.scale));
  if (bins.length < 2 || pm.scale == null) return null;
  const W = 640, H = 78, L = 40, R = 8, T = 8, B = 16;
  const lam = bins.map((b) => b.lam!), x0 = Math.min(...lam), x1 = Math.max(...lam);
  const vals = bins.flatMap((b) => [b.scale - b.err, b.scale + b.err, ...(b.raw != null ? [b.raw] : [])]).concat([1, pm.scale]);
  let y0 = Math.min(...vals), y1 = Math.max(...vals);
  const p = (y1 - y0 || 0.01) * 0.12; y0 -= p; y1 += p;
  const sx = (v: number) => L + ((v - x0) / (x1 - x0 || 1)) * (W - L - R);
  const sy = (v: number) => T + (1 - (v - y0) / (y1 - y0)) * (H - T - B);
  return (
    <svg className="pm-spark" viewBox={`0 0 ${W} ${H}`} role="img"
      aria-label={`Per-wavelength photometric scale, ${bins.length} bins, from ${Math.min(...bins.map((b) => b.scale)).toFixed(3)} to ${Math.max(...bins.map((b) => b.scale)).toFixed(3)}`}>
      <line x1={L} x2={W - R} y1={sy(1)} y2={sy(1)} className="unity"><title>scale = 1 (no gain change)</title></line>
      <text x={L - 5} y={sy(1) + 3} textAnchor="end" className="lbl">1.00</text>
      <text x={L - 5} y={sy(pm.scale) + 3} textAnchor="end" className="lbl amber">{pm.scale.toFixed(3)}</text>
      <text x={L} y={H - 3} className="lbl">{x0.toFixed(2)} µm</text>
      <text x={W - R} y={H - 3} textAnchor="end" className="lbl">{x1.toFixed(2)} µm</text>
      <text x={(L + W - R) / 2} y={H - 3} textAnchor="middle" className="lbl">scale per λ bin (B → A)</text>
      <line x1={L} x2={W - R} y1={sy(pm.scale)} y2={sy(pm.scale)} className="global"><title>broadband scale {pm.scale.toFixed(4)}</title></line>
      {bins.map((b, i) => (
        <g key={i}>
          <line x1={sx(b.lam!)} x2={sx(b.lam!)} y1={sy(b.scale - b.err)} y2={sy(b.scale + b.err)} className="err" />
          {b.raw != null && <circle cx={sx(b.lam!)} cy={sy(b.raw)} r={2} className="raw" />}
          <circle cx={sx(b.lam!)} cy={sy(b.scale)} r={3} className="fit">
            <title>{`${b.lam!.toFixed(3)} µm: ${b.scale.toFixed(4)} ± ${b.err.toFixed(4)}${b.pooled ? " (pooled: too few pixels)" : ""} · ${b.n_sources} sources`}</title>
          </circle>
        </g>
      ))}
    </svg>
  );
}

export function PhotometricMatchCard({ pm }: { pm: PhotometricMatch }) {
  const fitted = pm.scale != null && pm.scale_err != null;
  const cls = pm.cross_release ? "cross" : fitted && Math.abs(pm.scale! - 1) > 3 * pm.scale_err! ? "warn" : "";
  return (
    <div className={`photmatch ${cls}`} role="note" aria-label="Photometric match of the two visits">
      <div className="pm-head">
        <strong>{pm.cross_release ? `Cross-release difference (${pm.scales_a.join("/").toUpperCase()} − ${pm.scales_b.join("/").toUpperCase()})` : "Photometric check"}</strong>
        {pm.cross_release && <span>positions and motions valid · brightness not compared</span>}
      </div>
      <span>{pm.note}</span>
      {fitted && (
        <div className="pm-stats">
          <span>scale <b>{pm.scale!.toFixed(4)} ± {pm.scale_err!.toFixed(4)}</b>{pm.applied ? " applied" : " (not applied)"}</span>
          {pm.n_sources != null && <span>static sources <b>{pm.n_sources}</b></span>}
          {pm.static_z_before != null && pm.static_z_after != null && (
            <span title="Median |residual| of the static sources, in σ, without and with the match">static residual <b>{pm.static_z_before.toFixed(1)}σ → {pm.static_z_after.toFixed(1)}σ</b></span>
          )}
          {pm.tau != null && pm.tau > 0 && <span title="Scatter of the per-λ scale beyond its noise: a chromatic gain">chromatic τ <b>{pm.tau.toFixed(4)}</b></span>}
        </div>
      )}
      {fitted && <Spark pm={pm} />}
      <details>
        <summary>method</summary>
        <p className="small">{pm.method}. Amber dots: per-λ scale after shrinkage toward the broadband value (line), with 1σ bootstrap errors;
          grey dots: each bin's own fit; dashed: scale 1. The target is excluded from the fit, and variable stars are down-weighted.</p>
      </details>
    </div>
  );
}
