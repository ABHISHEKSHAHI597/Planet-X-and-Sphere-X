/**
 * Spectrum sonification (implementation.md §6.5, P2-8): pitch follows wavelength (0.75 → 5 µm mapped
 * logarithmically onto 220 → 1760 Hz), loudness follows flux (relative to the brightest point). ≈2 s.
 */
export interface Tone { lam: number; flux: number }

export function schedule(points: Tone[], seconds = 2): { t: number; hz: number; gain: number }[] {
  const pts = points.filter((p) => Number.isFinite(p.lam) && Number.isFinite(p.flux)).sort((a, b) => a.lam - b.lam);
  const peak = Math.max(...pts.map((p) => p.flux), 0);
  if (!pts.length || peak <= 0) return [];
  const f = (lam: number) => 220 * 8 ** (Math.log(Math.min(5, Math.max(0.75, lam)) / 0.75) / Math.log(5 / 0.75));
  return pts.map((p, i) => ({ t: (i / pts.length) * seconds, hz: f(p.lam), gain: 0.3 * Math.max(0, p.flux) / peak }));
}

export function playSpectrum(points: Tone[], seconds = 2): void {
  const steps = schedule(points, seconds);
  if (!steps.length || typeof AudioContext === "undefined") return;
  const ctx = new AudioContext();
  const osc = ctx.createOscillator();
  const g = ctx.createGain();
  osc.connect(g).connect(ctx.destination);
  const t0 = ctx.currentTime + 0.05;
  g.gain.setValueAtTime(0, ctx.currentTime);
  for (const s of steps) {
    osc.frequency.setValueAtTime(s.hz, t0 + s.t);
    g.gain.linearRampToValueAtTime(s.gain, t0 + s.t + 0.01);
  }
  g.gain.linearRampToValueAtTime(0, t0 + seconds + 0.05);
  osc.start(t0);
  osc.stop(t0 + seconds + 0.1);
  osc.onended = () => void ctx.close();
}
