/**
 * Spectral flipbook and λ-scrubber (P2-2, implementation.md §4.6, §7; gate G5.flip).
 *
 * - Exposures: every QA-passing exposure of one band, sorted by the wavelength it saw at the target
 *   (server: worker.flipbook_task + cube.flipbook_order). The label comes from the server and is shown
 *   verbatim: this is a spectral sequence, never a time sequence (workflow.md §11.2). Time order is
 *   offered only in expert mode, labelled as mixing wavelength with time.
 * - Cube planes: the per-pixel spectral cube of the current bin (17 planes per band). The plane label is
 *   the plane's nominal channel range; each pixel's own measured λ inside that range differs slightly.
 *
 * Both use the band's SHARED stretch limits from the manifest (one stretch for every frame, §6.3), so
 * brightness changes between frames are real spectral changes, not per-frame auto-stretch flicker.
 */
import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import type { CmapName } from "../gl/colormaps";
import { useCurrent, useFeature } from "../hooks/useCurrent";
import { BANDS } from "../lib/constants";
import { parseStretch } from "../lib/stretch";
import { mjdToISODate } from "../lib/time";
import { useApp } from "../state/store";
import { UnvalidatedBadge } from "./Badges";
import { GLCanvas } from "./GLCanvas";
import { Icon } from "./Icon";

export const CUBE_PLANES = 17;
/** Window event the app's keyboard handler sends while the flipbook is shown: detail is " ", "ArrowLeft" or "ArrowRight". */
export const FLIP_KEY = "parallax:flip-key";

/** Nominal channel range [lo, hi] µm of cube plane k of a band (ln-λ bins, as in cube.spectral_cube). */
export function planeRange(band: number, k: number, n = CUBE_PLANES): [number, number] {
  const [lo, hi] = BANDS[band]!;
  const r = Math.log(hi / lo) / n;
  return [lo * Math.exp(r * k), lo * Math.exp(r * (k + 1))];
}

type Source = "exposures" | "cube";

export function Flipbook({ webgl }: { webgl: boolean }) {
  const m = useApp((s) => s.manifest);
  const view = useApp((s) => s.view);
  const transform = useApp((s) => s.transform);
  const setTransform = useApp((s) => s.setTransform);
  const setGlFailed = useApp((s) => s.setGlFailed);
  const cur = useCurrent();
  const fFlip = useFeature("flip");
  const fScrub = useFeature("scrubber");
  const [source, setSource] = useState<Source>(fFlip.enabled ? "exposures" : "cube");
  const [sort, setSort] = useState<"lambda" | "time">("lambda");
  const [i, setI] = useState(0);
  const [playing, setPlaying] = useState(false);
  const src: Source = source === "exposures" && !fFlip.enabled ? "cube" : source === "cube" && !fScrub.enabled ? "exposures" : source;
  const effSort = view.ui === "expert" ? sort : "lambda";

  const framesQ = useQuery({
    queryKey: ["frames", m?.key, cur.band, effSort],
    enabled: !!m && src === "exposures" && fFlip.enabled,
    retry: false,
    queryFn: () => api.frames(m!.key, cur.band, effSort),
  });
  const binId = cur.bin?.id;
  const cubeQ = useQuery({
    queryKey: ["cube", m?.key, binId, cur.band],
    enabled: !!m && !!binId && src === "cube" && fScrub.enabled,
    retry: false,
    queryFn: () => api.cubeF16(m!.key, binId!, cur.band),
  });

  const n = src === "exposures" ? framesQ.data?.frames.length ?? 0 : cubeQ.data ? CUBE_PLANES : 0;
  useEffect(() => { setI(0); setPlaying(false); }, [m?.key, cur.band, src, effSort, binId]);
  useEffect(() => {
    if (!playing || n < 2) return;
    const id = setInterval(() => setI((x) => (x + 1) % n), 1000 / view.fps);
    return () => clearInterval(id);
  }, [playing, n, view.fps]);
  useEffect(() => {
    const onKey = (e: Event) => {
      const k = (e as CustomEvent<string>).detail;
      if (n < 2) return;
      if (k === " ") setPlaying((p) => !p);
      else { setPlaying(false); setI((x) => (x + (k === "ArrowRight" ? 1 : n - 1)) % n); }
    };
    window.addEventListener(FLIP_KEY, onKey);
    return () => window.removeEventListener(FLIP_KEY, onKey);
  }, [n]);

  const frame = src === "exposures" ? framesQ.data?.frames[Math.min(i, Math.max(0, n - 1))] : undefined;
  const frameQ = useQuery({
    queryKey: ["frame", frame?.url],
    enabled: !!frame && !!framesQ.data,
    staleTime: Infinity,
    queryFn: () => api.payloadF16(frame!.url, framesQ.data!.format),
  });

  const nx = m?.grid.shape[1] ?? 1, ny = m?.grid.shape[0] ?? 1;
  const bits = useMemo(() => {
    if (src === "exposures") return frameQ.data ?? null;
    if (!cubeQ.data) return null;
    const k = Math.min(i, CUBE_PLANES - 1);
    return cubeQ.data.subarray(k * nx * ny, (k + 1) * nx * ny);
  }, [src, frameQ.data, cubeQ.data, i, nx, ny]);

  if (!m) return null;
  if (!fFlip.enabled && !fScrub.enabled) {
    return <div className="notice" role="note">The spectral flipbook is switched off until it passes its validation gate (G5.flip).</div>;
  }
  const lo = cur.limits?.lo ?? 0, hi = cur.limits?.hi ?? 1;
  const err = (src === "exposures" ? framesQ.error ?? frameQ.error : cubeQ.error) as Error | null;
  const loading = src === "exposures" ? framesQ.isFetching || frameQ.isFetching : cubeQ.isFetching;
  const unvalidated = src === "exposures" ? fFlip.unvalidated : fScrub.unvalidated;

  let caption = "";
  if (src === "exposures" && frame) {
    caption = `${frame.lam_um != null ? `λ = ${frame.lam_um.toFixed(3)} µm at the target · ` : "λ unknown · "}${mjdToISODate(frame.mjd)} · exposure ${i + 1}/${n}`;
  } else if (src === "cube" && cubeQ.data) {
    const [a, z] = planeRange(cur.band, i);
    caption = `cube plane ${i + 1}/${CUBE_PLANES} · ${a.toFixed(3)}–${z.toFixed(3)} µm (nominal) · ${cur.bin?.label ?? ""}`;
  }
  const label = src === "exposures"
    ? (framesQ.data?.label ?? "")
    : "per-pixel spectral cube of one visit, scanned in wavelength (not a time sequence)";

  return (
    <div className="panel flipbook">
      <div className="panel-title">
        {src === "exposures" ? "Spectral flipbook" : "λ-scrubber"} · band {cur.band}
        {unvalidated && <UnvalidatedBadge />}
      </div>
      <div className="controls small" role="toolbar" aria-label="Flipbook controls">
        {fFlip.enabled && fScrub.enabled && (
          <div className="group" role="radiogroup" aria-label="Source">
            <button role="radio" aria-checked={src === "exposures"} className={src === "exposures" ? "on" : ""} onClick={() => setSource("exposures")}>Exposures</button>
            <button role="radio" aria-checked={src === "cube"} className={src === "cube" ? "on" : ""} onClick={() => setSource("cube")}>Cube planes</button>
          </div>
        )}
        {src === "exposures" && view.ui === "expert" && (
          <label>order <select value={sort} onChange={(e) => setSort(e.target.value as "lambda" | "time")}>
            <option value="lambda">by wavelength</option><option value="time">by time (expert)</option>
          </select></label>
        )}
        <button aria-label={playing ? "Pause" : "Play"} className="play" aria-pressed={playing} disabled={n < 2} onClick={() => setPlaying(!playing)}><Icon name={playing ? "pause" : "play"} size={15} /></button>
        <label className="scrub">
          <span className="sr-only">{src === "exposures" ? "Exposure" : "Cube plane"}</span>
          <input type="range" min={0} max={Math.max(0, n - 1)} value={Math.min(i, Math.max(0, n - 1))} disabled={n < 2}
            onChange={(e) => { setPlaying(false); setI(Number(e.target.value)); }} />
        </label>
      </div>
      <p className="notice small" role="note"><strong>{label}</strong></p>
      <div className="canvas-wrap">
        {!webgl ? (
          <div className="notice">The flipbook needs WebGL2; the blink below still works without it.</div>
        ) : bits ? (
          <GLCanvas bits={bits} nx={nx} ny={ny} lo={lo} hi={hi} stretch={parseStretch(view.stretch)} cmap={view.cmap as CmapName}
            transform={transform} onTransform={setTransform} onError={(why) => setGlFailed(why)}
            label={`${src === "exposures" ? "Spectral flipbook" : "Spectral cube"}, band ${cur.band}: ${caption}`} />
        ) : (
          <div className="panel-loading" role="status">{err ? `Not available: ${err.message}` : loading ? "Loading…" : "No frames."}</div>
        )}
      </div>
      <div className="frame-caption" aria-live="polite">{caption}</div>
    </div>
  );
}
