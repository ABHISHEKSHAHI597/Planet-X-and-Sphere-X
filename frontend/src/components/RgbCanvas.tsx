/**
 * RGB composites (implementation.md §5.3 `bands=rgb:…`, §7 "RGB presets").
 *
 * - `rgb:a,b,c`: three band visit stacks of the same bin, each stretched with its own band's SHARED
 *   limits from the manifest (so the colour of a static star does not flicker between visits).
 * - `rgb:methane` / `rgb:ice`: wavelength-range presets. The server builds each channel from the
 *   per-pixel spectral cube with the wavelength each pixel actually measured (cube.lambda_slice); the
 *   browser never approximates a λ range from band stacks. Limits are fixed per view from the first bin
 *   shown and reused for every bin, for the same no-flicker reason.
 *
 * Colour encodes spectral shape only; it is not a calibrated colour index. The canvas is drawn on the
 * CPU (row 0 = south at the bottom, lib/stretch.renderRGBA convention), north up, east left.
 */
import { useEffect, useRef, useState } from "react";
import { api } from "../api/client";
import { getValues } from "../hooks/stackCache";
import { decodeF16 } from "../lib/half";
import { NODATA_RGB } from "../gl/colormaps";
import { parseStretch, stretchValue, type StretchSpec } from "../lib/stretch";
import { useApp } from "../state/store";
import { useCurrent } from "../hooks/useCurrent";
import { channelBins, RGB_MATCH_DAYS } from "../lib/rgbBins";

export { channelBins, RGB_MATCH_DAYS };

export const RANGE_PRESETS: Record<string, { label: string; channels: [string, string, string] }> = {
  methane: { label: "methane: T/Y dwarfs glow red", channels: ["R 4.0–4.2 µm", "G 3.55–3.65 µm", "B 3.25–3.40 µm"] },
  ice: { label: "ice: ice-rich sightlines lose green (magenta)", channels: ["R 2.55–2.65 µm", "G 3.0–3.1 µm", "B 3.55–3.65 µm"] },
};
const BAND_TRIPLET_PRESETS: Record<string, [number, number, number]> = { thermal: [4, 5, 6] };

/** Robust per-channel limits: 1st–99.5th percentile of finite values. */
export function percentileLimits(a: Float32Array): { lo: number; hi: number } {
  const v = Array.from(a).filter((x) => Number.isFinite(x)).sort((x, y) => x - y);
  if (v.length < 10) return { lo: 0, hi: 1 };
  const q = (p: number) => v[Math.min(v.length - 1, Math.max(0, Math.round(p * (v.length - 1))))]!;
  const lo = q(0.01), hi = q(0.995);
  return { lo, hi: hi > lo ? hi : lo + 1 };
}

/** Compose three row0south channels into top-row-first RGBA. A pixel with no channel is no-data. */
export function composeRGB(ch: [Float32Array, Float32Array, Float32Array], lim: { lo: number; hi: number }[],
  nx: number, ny: number, spec: StretchSpec): Uint8ClampedArray {
  const out = new Uint8ClampedArray(nx * ny * 4);
  for (let row = 0; row < ny; row++) {
    const top = ny - 1 - row;
    for (let col = 0; col < nx; col++) {
      const i = row * nx + col, o = 4 * (top * nx + col);
      const t = ch.map((c, k) => stretchValue(c[i]!, lim[k]!.lo, lim[k]!.hi, spec));
      if (t.every((x) => Number.isNaN(x))) {
        out[o] = NODATA_RGB[0]; out[o + 1] = NODATA_RGB[1]; out[o + 2] = NODATA_RGB[2];
      } else {
        for (let k = 0; k < 3; k++) out[o + k] = Number.isNaN(t[k]!) ? 0 : Math.round(255 * t[k]!);
      }
      out[o + 3] = 255;
    }
  }
  return out;
}

const presetLimits = new Map<string, { lo: number; hi: number }[]>();
/** Decoded λ-range composites by view|bin|preset. Without it, playback re-downloaded every bin on every loop and
 *  hit the server's measurement rate limit (429 "Composite not available") within the first pass. Bounded LRU. */
const RGB_CACHE_MAX = 64;
const rgbCache = new Map<string, Promise<Float32Array>>();
function rgbValues(key: string, bin: string, preset: string): Promise<Float32Array> {
  const k = `${key}|${bin}|${preset}`;
  let p = rgbCache.get(k);
  if (p) { rgbCache.delete(k); rgbCache.set(k, p); return p; }   // refresh LRU position
  p = api.rgbF16(key, bin, preset).then(decodeF16);
  p.catch(() => rgbCache.delete(k));                              // a failure is retried next time, not cached
  rgbCache.set(k, p);
  while (rgbCache.size > RGB_CACHE_MAX) rgbCache.delete(rgbCache.keys().next().value!);
  return p;
}

/** Resolve `rgb:…` to what to fetch. null: not a composite this build knows (shown as a notice). */
export function rgbPlan(bands: string): { kind: "bands"; bands: [number, number, number] } | { kind: "range"; preset: string } | null {
  const rest = bands.replace(/^rgb:/, "");
  if (/^[1-6],[1-6],[1-6]$/.test(rest)) return { kind: "bands", bands: rest.split(",").map(Number) as [number, number, number] };
  if (BAND_TRIPLET_PRESETS[rest]) return { kind: "bands", bands: BAND_TRIPLET_PRESETS[rest]! };
  if (RANGE_PRESETS[rest]) return { kind: "range", preset: rest };
  return null;
}

export function RgbCanvas({ bin }: { bin: string }) {
  const m = useApp((s) => s.manifest);
  const view = useApp((s) => s.view);
  const ready = useApp((s) => s.ready);
  const ref = useRef<HTMLCanvasElement>(null);
  const [err, setErr] = useState<string | null>(null);
  const [drawn, setDrawn] = useState(false);
  const [hole, setHole] = useState(false);
  const plan = rgbPlan(view.bands);
  const playable = useCurrent().bins.length;
  const setView = useApp((s) => s.setView);
  const nx = m?.grid.shape[1] ?? 1, ny = m?.grid.shape[0] ?? 1;
  const chBins = plan?.kind === "bands" && m ? channelBins(m.bins, bin, plan.bands) : [];
  const missing = plan?.kind === "bands" && chBins.some((b) => b === null);
  const bandsReady = plan?.kind === "bands" ? !missing && plan.bands.every((b, k) => ready.has(`${chBins[k]}|${b}`)) : true;

  useEffect(() => {
    if (!m || !plan || !bandsReady) return;
    let live = true;
    setErr(null);
    (async () => {
      let ch: [Float32Array, Float32Array, Float32Array];
      let lim: { lo: number; hi: number }[];
      if (plan.kind === "bands") {
        ch = await Promise.all(plan.bands.map((b, k) => getValues(m.key, chBins[k]!, b, m.formats.stack))) as [Float32Array, Float32Array, Float32Array];
        lim = plan.bands.map((b) => m.limits[String(b)] ?? { lo: 0, hi: 1 });
      } else {
        const all = await rgbValues(m.key, bin, plan.preset);
        const n = nx * ny;
        ch = [all.subarray(0, n), all.subarray(n, 2 * n), all.subarray(2 * n, 3 * n)];
        const k = `${m.key}|${plan.preset}`;
        if (!presetLimits.has(k)) presetLimits.set(k, ch.map(percentileLimits));
        lim = presetLimits.get(k)!;
      }
      if (!live || !ref.current) return;
      const ctx = ref.current.getContext("2d");
      if (!ctx) { setErr("2D canvas unavailable"); return; }
      ctx.putImageData(new ImageData(composeRGB(ch, lim, nx, ny, parseStretch(view.stretch)), nx, ny), 0, 0);
      const c = Math.floor(ny / 2) * nx + Math.floor(nx / 2);
      setHole(ch.every((a) => !Number.isFinite(a[c]!)));
      setDrawn(true);
    })().catch((e: Error) => live && setErr(e.message));
    return () => { live = false; };
  }, [m, bin, chBins.join(","), view.bands, view.stretch, bandsReady, nx, ny]); // eslint-disable-line react-hooks/exhaustive-deps

  if (!m) return null;
  if (!plan) return <div className="notice small" role="note">The composite “{view.bands}” is not defined in this build.</div>;
  const legend = plan.kind === "bands"
    ? plan.bands.map((b, k) => `${"RGB"[k]} band ${b}${chBins[k] && chBins[k] !== bin ? ` (${chBins[k]})` : ""}`).join(" · ")
    : RANGE_PRESETS[plan.preset]!.channels.join(" · ");
  return (
    <div className="panel rgb">
      <div className="panel-title">RGB · {plan.kind === "range" ? RANGE_PRESETS[plan.preset]!.label : legend}</div>
      <div className="canvas-wrap">
        <canvas ref={ref} width={nx} height={ny} className="rgb-canvas" role="img"
          aria-label={`RGB composite of ${legend} for ${bin}; colour shows spectral shape, not a calibrated colour index`} />
        {missing && <div className="panel-loading" role="status">No stack within {RGB_MATCH_DAYS} days in {plan.kind === "bands" ? plan.bands.filter((_, k) => chBins[k] === null).map((b) => `band ${b}`).join(", ") : ""} for {bin}: step to another frame.</div>}
        {!missing && !drawn && !err && <div className="panel-loading" role="status">{bandsReady ? "Composing…" : "Waiting for the three band stacks…"}</div>}
        {err && <div className="panel-loading error" role="alert">Composite not available: {err}</div>}
      </div>
      {plan.kind === "bands" && playable < 2 && (
        <div className="notice small" role="note">
          Only {playable} frame{playable === 1 ? "" : "s"} here {playable === 1 ? "has" : "have"} all three bands within {RGB_MATCH_DAYS} days:
          SPHEREx sees this target with each detector pair (bands 1+4, 2+5, 3+6) in different seasons, so a three-band
          colour blink would mix in months of variability.{" "}
          <button className="link" onClick={() => setView({ bands: "rgb:ice" })}>Blink rgb:ice instead</button> (all three
          channels from band 4, so every frame is one epoch), or blink a single band.
        </div>
      )}
      <div className="legend small">{legend}. Colour shows spectral shape only, not a calibrated colour index.
        {chBins.some((b) => b && b !== bin) && " Bands were observed on different days here; for a variable star the colour mixes in its change over up to two weeks."}
        {hole && " The dark patch at the centre is no data: the star is so bright that its core overflowed early in every exposure, so those pixels have no valid measurement (they are not black sky)."}</div>
    </div>
  );
}
