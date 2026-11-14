/**
 * Robust statistics for the spectrum chart (implementation.md §6.5). Pure functions, unit-tested in
 * tests/spectrum.test.ts.
 *
 * Binning is per *release* and detector: QR2 and QR3 are not on a common photometric scale until F4 is
 * resolved (workflow.md §11.2), so one median line through both would draw a spectrum that exists in
 * neither. Within a bin: inverse-variance weighted mean after iterative σ-clipping about the weighted
 * median, with the error inflated by the Birge ratio √χ²ᵣ when the points scatter more than their errors
 * (frames of one visit share systematics the per-frame errors do not carry).
 */
import { BANDS } from "./constants";

export interface SpecInput {
  lam: number; dlam: number; flux: number; err: number; release?: string | null; detector: number; contaminated?: boolean;
}

/** A row's release, lower-case; "unknown" for responses that predate the field. */
export const releaseOf = (r: { release?: string | null }) => (r.release ? String(r.release).toLowerCase() : "unknown");

export interface SpecBin {
  release: string; detector: number; k: number;
  lam: number; lamLo: number; lamHi: number;
  flux: number; err: number; errFormal: number;
  n: number; nClipped: number; chi2r: number;
}

/** Linear-interpolated quantile of an ascending array (NaN when empty). */
export function quantile(sorted: readonly number[], q: number): number {
  if (!sorted.length) return NaN;
  const p = Math.min(Math.max(q, 0), 1) * (sorted.length - 1), i = Math.floor(p), f = p - i;
  return i + 1 < sorted.length ? sorted[i]! * (1 - f) + sorted[i + 1]! * f : sorted[i]!;
}

/** Weighted median: the value where the cumulative weight first reaches half the total. */
export function weightedMedian(values: readonly number[], weights: readonly number[]): number {
  const idx = values.map((_, i) => i).filter((i) => Number.isFinite(values[i]) && weights[i]! > 0).sort((a, b) => values[a]! - values[b]!);
  if (!idx.length) return NaN;
  const total = idx.reduce((s, i) => s + weights[i]!, 0);
  let acc = 0;
  for (const i of idx) { acc += weights[i]!; if (acc >= total / 2) return values[i]!; }
  return values[idx[idx.length - 1]!]!;
}

function mad(a: number[]): number {
  if (a.length < 2) return 0;
  const s = [...a].sort((x, y) => x - y), m = quantile(s, 0.5);
  return 1.4826 * quantile(a.map((v) => Math.abs(v - m)).sort((x, y) => x - y), 0.5);
}

/** The ln-λ bin (0…nPerBand−1) of a wavelength within a detector's band. */
export function lnBin(lam: number, detector: number, nPerBand = 17): number {
  const [lo, hi] = BANDS[detector] ?? [lam, lam * 2];
  return Math.min(nPerBand - 1, Math.max(0, Math.floor((nPerBand * Math.log(lam / lo)) / Math.log(hi / lo))));
}

/** Hampel despiking across wavelength, per release: a point is an outlier when it deviates from the
 *  median of its `half` neighbours on each side (in λ order) by more than k·√(σ_MAD² + err²), σ_MAD the
 *  neighbours' robust scatter. In-bin clipping needs ≥ 3 points per bin; this catches the single wild frame
 *  that would otherwise *be* a bin when a release has one frame per λ bin. Including the point's own error
 *  means a noisy-but-honest faint point is never rejected. Returns true for outliers (input order). */
export function hampelOutliers(rows: readonly SpecInput[], { half = 4, k = 5 } = {}): boolean[] {
  const out = new Array<boolean>(rows.length).fill(false);
  const by = new Map<string, number[]>();
  rows.forEach((r, i) => {
    if (!(Number.isFinite(r.flux) && Number.isFinite(r.lam))) return;
    const key = releaseOf(r), g = by.get(key);
    if (g) g.push(i); else by.set(key, [i]);
  });
  for (const idx of by.values()) {
    idx.sort((a, b) => rows[a]!.lam - rows[b]!.lam);
    for (let p = 0; p < idx.length; p++) {
      const nb: number[] = [];
      for (let q = Math.max(0, p - half); q <= Math.min(idx.length - 1, p + half); q++) if (q !== p) nb.push(rows[idx[q]!]!.flux);
      if (nb.length < 4) continue;
      const sorted = [...nb].sort((a, b) => a - b), m = quantile(sorted, 0.5), s = mad(nb);
      const r = rows[idx[p]!]!, e = Number.isFinite(r.err) && r.err > 0 ? r.err : 0;
      if (Math.abs(r.flux - m) > k * Math.hypot(s, e)) out[idx[p]!] = true;
    }
  }
  return out;
}

/** Robust binned spectrum: one point per (release, detector, ln-λ bin). */
export function binSpectrum(rows: readonly SpecInput[], { nPerBand = 17, clip = 3, maxIter = 6 } = {}): SpecBin[] {
  const groups = new Map<string, SpecInput[]>();
  for (const r of rows) {
    if (!(Number.isFinite(r.flux) && Number.isFinite(r.lam) && r.err > 0 && Number.isFinite(r.err))) continue;
    const key = `${releaseOf(r)}|${r.detector}|${lnBin(r.lam, r.detector, nPerBand)}`;
    const g = groups.get(key);
    if (g) g.push(r); else groups.set(key, [r]);
  }
  const out: SpecBin[] = [];
  for (const [key, g] of groups) {
    const [release, det, k] = key.split("|");
    let keep = g.map(() => true);
    for (let it = 0; it < maxIter && g.length >= 3; it++) {
      const kept = g.filter((_, i) => keep[i]);
      // centre: weights capped at the median error, so one over-confident point cannot hijack the clip
      const eMed = quantile(kept.map((r) => r.err).sort((a, b) => a - b), 0.5);
      const c = weightedMedian(kept.map((r) => r.flux), kept.map((r) => 1 / Math.max(r.err, eMed) ** 2));
      const s = Math.max(1, mad(kept.map((r) => (r.flux - c) / r.err)));    // errors underestimated → widen, never narrow
      const next = g.map((r) => Math.abs(r.flux - c) / r.err <= clip * s);
      if (next.filter(Boolean).length < 2 || next.every((v, i) => v === keep[i])) break;
      keep = next;
    }
    const kept = g.filter((_, i) => keep[i]);
    const w = kept.map((r) => 1 / r.err ** 2), sw = w.reduce((a, b) => a + b, 0);
    const flux = kept.reduce((s, r, i) => s + w[i]! * r.flux, 0) / sw;
    const lam = kept.reduce((s, r, i) => s + w[i]! * r.lam, 0) / sw;
    const errFormal = 1 / Math.sqrt(sw);
    const chi2r = kept.length > 1 ? kept.reduce((s, r, i) => s + w[i]! * (r.flux - flux) ** 2, 0) / (kept.length - 1) : 1;
    out.push({
      release: release!, detector: Number(det), k: Number(k), lam,
      lamLo: Math.min(...kept.map((r) => r.lam - r.dlam / 2)), lamHi: Math.max(...kept.map((r) => r.lam + r.dlam / 2)),
      flux, errFormal, err: errFormal * Math.sqrt(Math.max(1, chi2r)), n: kept.length, nClipped: g.length - kept.length, chi2r,
    });
  }
  return out.sort((a, b) => a.release.localeCompare(b.release) || a.lam - b.lam);
}

/** Robust y-range: the [qLo, qHi] quantiles of the individual values, widened to contain every binned value
 *  ± its error (the binned spectrum is what must never be cut), then padded. A few wild points or
 *  ±1000 µJy error bars therefore no longer squash the spectrum into one line. */
export function robustRange(values: readonly number[], must: readonly [number, number][] = [], { qLo = 0.02, qHi = 0.98, pad = 0.08 } = {}): [number, number] {
  const s = values.filter(Number.isFinite).sort((a, b) => a - b);
  let lo = quantile(s, qLo), hi = quantile(s, qHi);
  for (const [a, b] of must) {
    if (Number.isFinite(a)) lo = Number.isFinite(lo) ? Math.min(lo, a) : a;
    if (Number.isFinite(b)) hi = Number.isFinite(hi) ? Math.max(hi, b) : b;
  }
  if (!Number.isFinite(lo) || !Number.isFinite(hi)) return [0, 1];
  if (hi - lo <= 1e-12 * Math.max(1, Math.abs(hi))) { const d = Math.abs(hi) * 0.1 || 1; lo -= d; hi += d; }
  const p = (hi - lo) * pad;
  return [lo - p, hi + p];
}

/** Greedy lane assignment for labels at screen x with pixel widths w: each label takes the lowest lane
 *  whose previous label ends before it starts (+gap). Returns the lane per item, −1 when all lanes are
 *  full (the label is then shown on hover only). Order of the input is preserved. */
export function layoutLabels(items: readonly { x: number; w: number }[], lanes = 3, gap = 4): number[] {
  const order = items.map((_, i) => i).sort((a, b) => items[a]!.x - items[b]!.x);
  const end = new Array<number>(lanes).fill(-Infinity), out = new Array<number>(items.length).fill(-1);
  for (const i of order) {
    const it = items[i]!;
    for (let l = 0; l < lanes; l++) if (it.x >= end[l]! + gap) { out[i] = l; end[l] = it.x + it.w; break; }
  }
  return out;
}

/** AB magnitude and its error from µJy. */
export const abMag = (uJy: number) => 23.9 - 2.5 * Math.log10(uJy);
export const abMagErr = (uJy: number, err: number) => (2.5 / Math.LN10) * (err / Math.abs(uJy));

/** Release colours and marker shapes: fixed per release, so QR2 and QR3 read the same in every chart. */
export const RELEASE_STYLE: Record<string, { colour: string; shape: "circle" | "square" | "diamond" | "triangle" }> = {
  qr3: { colour: "#74c7ec", shape: "circle" },
  qr2: { colour: "#f2b33d", shape: "square" },
  qr1: { colour: "#b9a2f0", shape: "diamond" },
};
export const releaseStyle = (r?: string | null) => RELEASE_STYLE[(r ?? "").toLowerCase()] ?? { colour: "#6fcf97", shape: "triangle" as const };
