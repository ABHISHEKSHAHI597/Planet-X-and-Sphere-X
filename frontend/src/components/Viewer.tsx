/**
 * The blink viewer (implementation.md §6.2–6.4). WebGL2 when available, otherwise the PNG fallback
 * (switches automatically; P0-8). Modes: blink (default), onion-skin, side-by-side, and — only when
 * the backend enables it — the λ-matched difference. The frontend never subtracts stacks itself:
 * naive visit subtraction is a forbidden fallback (workflow.md §11.2).
 */
import { useEffect, useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import type { CmapName } from "../gl/colormaps";
import { webgl2Available } from "../gl/renderer";
import { getF16 } from "../hooks/stackCache";
import { useCurrent, useFeature } from "../hooks/useCurrent";
import { altText } from "../lib/alttext";
import { compareIndex, defaultDiffPair, nextFrame } from "../lib/player";
import { parseStretch } from "../lib/stretch";
import { gridForBin, pixelToSky } from "../lib/wcs";
import { formatDec, formatRA } from "../lib/coords";
import { useApp } from "../state/store";
import { FlagLayer } from "./FlagLayer";
import { FilledLayer } from "./FilledLayer";
import { Flipbook } from "./Flipbook";
import { RgbCanvas } from "./RgbCanvas";
import { GLCanvas } from "./GLCanvas";
import { Loupe } from "./Loupe";
import { OverlayLayer } from "./OverlayLayer";
import { PngViewer, preloadPngs } from "./PngViewer";
import { UnvalidatedBadge } from "./Badges";
import { Icon } from "./Icon";
import { PhotometricMatchCard } from "./PhotometricMatch";
import { fix, isNum } from "../lib/format";

let glProbe: boolean | null = null;
const glOK = () => (glProbe ??= webgl2Available());

export function useReducedMotion(): boolean {
  const [r, setR] = useState(() => typeof matchMedia !== "undefined" && matchMedia("(prefers-reduced-motion: reduce)").matches);
  useEffect(() => {
    if (typeof matchMedia === "undefined") return;
    const q = matchMedia("(prefers-reduced-motion: reduce)");
    const h = () => setR(q.matches);
    q.addEventListener?.("change", h);
    return () => q.removeEventListener?.("change", h);
  }, []);
  return r;
}

/** Load the f16 payloads of the given bins as they become ready. */
function useStackBits(key: string | undefined, band: number, bins: string[], format: string | undefined, ready: (b: string) => boolean, raw = false) {
  const [bits, setBits] = useState<Record<string, Uint16Array>>({});
  const readyList = bins.filter(ready).join(",");
  useEffect(() => { setBits({}); }, [key, band, raw]);
  useEffect(() => {
    if (!key || !format) return;
    let live = true;
    for (const b of readyList ? readyList.split(",") : []) {
      getF16(key, b, band, format, raw).then((x) => live && setBits((o) => (o[b] === x ? o : { ...o, [b]: x })),
        (e) => useApp.getState().setError(`Could not load stack ${b} (band ${band}): ${e.message}`));
    }
    return () => { live = false; };
  }, [key, band, format, readyList, raw]);
  return bits;
}

export function Viewer({ embed = false }: { embed?: boolean }) {
  const m = useApp((s) => s.manifest);
  const view = useApp((s) => s.view);
  const setView = useApp((s) => s.setView);
  const playing = useApp((s) => s.playing);
  const setPlaying = useApp((s) => s.setPlaying);
  const comparing = useApp((s) => s.comparing);
  const transform = useApp((s) => s.transform);
  const setTransform = useApp((s) => s.setTransform);
  const hover = useApp((s) => s.hover);
  const setHover = useApp((s) => s.setHover);
  const picked = useApp((s) => s.picked);
  const setPicked = useApp((s) => s.setPicked);
  const glFailed = useApp((s) => s.glFailed);
  const setGlFailed = useApp((s) => s.setGlFailed);
  const cur = useCurrent();
  const fDiff = useFeature("diff");
  const fTrack = useFeature("track");
  const fAstro = useFeature("astrometry");
  const fOver = useFeature("overlays");
  const fWise = useFeature("wise_layer");
  const fSpec = useFeature("spectrum");
  const fRgb = useFeature("rgb");
  const fCand = useFeature("candidates");
  const reduced = useReducedMotion();
  const useGL = glOK() && !glFailed && !forcePng();

  const nx = m?.grid.shape[1] ?? 1, ny = m?.grid.shape[0] ?? 1;
  const binIds = cur.bins.map((b) => b.id);
  const [showRaw, setShowRaw] = useState(false);
  const bits = useStackBits(m?.key, cur.band, binIds, m?.formats.stack, (b) => cur.isReady(b), showRaw);
  const stretch = useMemo(() => parseStretch(view.stretch), [view.stretch]);
  const cmap = view.cmap as CmapName;
  const lo = cur.limits?.lo ?? 0, hi = cur.limits?.hi ?? 1;

  // Player loop: ping-pong at view.fps (implementation.md §6.3). Reduced motion: no autoplay.
  useEffect(() => {
    if (!playing || cur.bins.length < 2) return;
    let pos = { i: useApp.getState().frame, dir: 1 as 1 | -1 };
    const id = setInterval(() => {
      pos = nextFrame(pos, cur.bins.length);
      useApp.getState().setFrame(pos.i);
    }, 1000 / view.fps);
    return () => clearInterval(id);
  }, [playing, cur.bins.length, view.fps]);
  useEffect(() => { if (reduced && playing && !embed) setPlaying(false); }, [reduced, playing, embed, setPlaying]);
  // The flipbook runs its own player; the visit blink must not keep advancing underneath it.
  useEffect(() => { if (view.mode === "flip" && playing) setPlaying(false); }, [view.mode, playing, setPlaying]);

  // keep URL `t` in step with the frame shown (so a pause → share reproduces it)
  useEffect(() => {
    if (!playing && cur.bin && view.t !== cur.bin.id) setView({ t: cur.bin.id });
  }, [playing, cur.bin, view.t, setView]);

  // overlays: catalogue markers at the current bin epoch (propagated server-side, §6.6)
  // `wise` is the one layer that is NOT moved to the bin epoch: AllWISE positions as catalogued around 2010.5.
  const wantCats = view.ov.filter((o) => (fOver.enabled && (o === "gaia" || o === "simbad" || o === "sso")) || (fWise.enabled && o === "wise")) as ("gaia" | "wise" | "simbad" | "sso")[];
  const catsKey = wantCats.join(",");
  const mjd = cur.bin?.mjd_mean ?? 0;
  const ovq = useQuery({
    queryKey: ["overlays", catsKey, m?.grid.crval, m?.grid.shape, Math.round(mjd)],
    enabled: !!m && wantCats.length > 0 && !!cur.bin,
    // markers stay on screen while the next bin's epoch loads, instead of vanishing every frame (audit F-07), but only
    // for the same set of catalogues: unticking Gaia or SIMBAD must remove its markers at once, not keep the old ones
    placeholderData: (prev, prevQuery) => (prevQuery?.queryKey[1] === catsKey ? prev : undefined),
    queryFn: async () => {
      const r = (m!.grid.pix_arcsec * m!.grid.shape[1]) / 3600 / Math.SQRT2;
      const out = await Promise.all(wantCats.map((c) => api.overlays(c === "wise" ? "allwise" : c, m!.grid.crval[0], m!.grid.crval[1], r, mjd)));
      return out.flatMap((o, i) => o.sources.map((s) => ({ ...s, cat: wantCats[i]! })));
    },
  });
  const catSources = wantCats.length ? ovq.data ?? [] : [];
  useEffect(() => { if (!view.ov.includes("sso") && picked) setPicked(null); }, [view.ov, picked, setPicked]);
  // The fitted vector reuses the astrometry card's result; it never starts that measurement (minutes of native
  // fits) by itself, so ticking "fitted motion" draws nothing until "Measure proper motion" has run (audit F-09).
  const qc = useQueryClient();
  const astroKey = ["astrometry", m?.target?.name, m?.key];
  const astroStarted = !!qc.getQueryState(astroKey);
  const astro = useQuery({
    queryKey: astroKey,
    enabled: !!m?.target && m.target.kind === "star" && fAstro.enabled && view.ov.includes("vec") && astroStarted,
    queryFn: () => api.astrometry(m!.target!.propagated_now.ra, m!.target!.propagated_now.dec, m!.target!.name, m!.key),
  });

  // difference view (only if the backend enables it)
  const pair = useMemo(() => {
    if (view.a && view.b) return [view.a, view.b] as [string, string];
    return defaultDiffPair(cur.allBins);
  }, [view.a, view.b, cur.allBins]);
  // A − B: without an explicit pair, the latest visit minus the earliest, so +σ is where the source is now
  const diffPair = view.a && view.b ? pair : pair && ([pair[1], pair[0]] as [string, string]);
  const diffOn = view.mode === "diff" && fDiff.enabled && !!diffPair;
  const diffq = useQuery({
    queryKey: ["diff", m?.key, diffPair?.[0], diffPair?.[1], cur.band],
    enabled: !!m && diffOn,
    queryFn: async () => {
      const info = await api.diff(m!.key, diffPair![0], diffPair![1], cur.band);
      return { info, bits: await api.diffF16(info.url, info.format) };
    },
  });

  useEffect(() => {      // PNG fallback: preload every frame of the band with the shared limits
    if (useGL || !m || !cur.limits) return;
    preloadPngs(cur.bins.filter((b) => cur.isReady(b.id)).map((b) => api.pngURL(m.key, b.id, cur.band, { stretch: view.stretch, lo, hi, cmap: view.cmap, raw: showRaw })));
  }, [useGL, m, cur, view.stretch, view.cmap, lo, hi, showRaw]);

  if (!m) return null;
  if (!cur.bins.length) {
    return (
      <div className="viewer empty" role="status">
        <p>No {view.partial ? "" : "full "}{m.axis === "visit" ? "visits" : "time bins"} in band {cur.band} for this view.</p>
        {cur.allBins.some((b) => b.status === "partial") && !view.partial && (
          <button onClick={() => setView({ partial: true })}>Include partial visits</button>
        )}
      </div>
    );
  }

  const shownIdx = comparing ? compareIndex(cur.index, cur.bins.length) : cur.index;
  const shown = cur.bins[shownIdx]!;
  const prev = cur.bins[compareIndex(cur.index, cur.bins.length)]!;
  const label = altText(m, cur.band, cur.bins);
  const selected = view.sel ? { ra: Number(view.sel.split(",")[0]), dec: Number(view.sel.split(",")[1]) } : null;
  const shownGrid = gridForBin(m, shown.id, cur.band);      // track mode: this bin's own centre (F-20)
  const onClickPixel = fSpec.enabled ? (px: { col: number; row: number }) => {
    const s = pixelToSky(shownGrid, px.col, px.row);
    setView({ sel: `${s.ra.toFixed(5)},${s.dec.toFixed(5)}` });
  } : undefined;
  const onHover = (p: { col: number; row: number; x: number; y: number } | null) => {
    if (!p) { setHover(null); return; }
    const s = pixelToSky(shownGrid, p.col, p.row);
    setHover({ ...p, ra: s.ra, dec: s.dec });
  };
  const vector = astro.data?.fit && isNum(astro.data.fit.pmra) && isNum(astro.data.fit.pmdec) && cur.bin && astro.data.validity ? (() => {
    const tp = m.track.find((t) => t.bin === shown.id && t.band === cur.band);
    const f = astro.data.fit!;
    return tp ? { ra: tp.ra, dec: tp.dec, pmra: f.pmra, pmdec: f.pmdec, label: `μ ${fix(f.mu)}″/yr (×10)` } : null;
  })() : null;

  const panel = (binId: string, opts: { bits2?: Uint16Array | null; mix?: number; title?: string; key?: string }) => {
    const b = bits[binId] ?? null;
    const stack = cur.stack(binId);
    const tr = fTrack.enabled && view.ov.includes("track") ? m.track.filter((t) => t.band === cur.band && cur.bins.some((x) => x.id === t.bin)) : [];
    return (
      <div className="panel" key={opts.key ?? binId}>
        {opts.title && <div className="panel-title">{opts.title}</div>}
        <div className="canvas-wrap">
          {useGL ? (
            <GLCanvas bits={b} bits2={opts.bits2} mix={opts.mix} nx={nx} ny={ny} lo={lo} hi={hi} stretch={stretch} cmap={cmap}
              transform={transform} onTransform={setTransform} onHover={onHover} onClickPixel={onClickPixel}
              onError={(why) => setGlFailed(why)} label={label} />
          ) : (
            <PngViewer url={cur.isReady(binId) ? api.pngURL(m.key, binId, cur.band, { stretch: view.stretch, lo, hi, cmap: view.cmap, raw: showRaw }) : null}
              label={label} nx={nx} ny={ny} onClickPixel={onClickPixel} />
          )}
          {view.flags.length > 0 && stack && cur.isReady(binId) && (
            <FlagLayer viewKey={m.key} bin={binId} band={cur.band} format={m.flags.format} planes={view.flags} bits={m.flags.bits}
              nx={nx} ny={ny} transform={useGL ? transform : null} />
          )}
          {stack?.filled && !showRaw && <FilledLayer viewKey={m.key} bin={binId} band={cur.band} nx={nx} ny={ny}
            transform={useGL ? transform : null} />}
          <OverlayLayer grid={gridForBin(m, binId, cur.band)} transform={useGL ? transform : null} track={tr} currentBin={binId}
            crosshair={view.ov.includes("crosshair")} vector={view.ov.includes("vec") && fAstro.enabled ? vector : null}
            sources={[...catSources, ...(view.ov.includes("sso") ? (stack?.transients ?? []).map((t, k) => ({
              id: `transient ${k} in ${t.frame}`, ra: t.ra, dec: t.dec, cat: "transient" as const, frame: t.frame, npix: t.npix })) : [])]}
            onPick={embed ? undefined : (s) => setPicked({ ...s, bin: binId, band: cur.band })} picked={picked?.id}
            selected={selected} />
          {!b && useGL && <div className="panel-loading" role="status">Loading {binId}…</div>}
          {useGL && hover && b && stack && !embed && (
            <Loupe hover={hover} viewKey={m.key} bin={binId} band={cur.band} formats={m.formats} nx={nx} ny={ny} lo={lo} hi={hi}
              stretch={stretch} cmap={cmap} bits={m.flags.bits} nhits={stack.nhits_max} />
          )}
        </div>
      </div>
    );
  };

  let body: React.ReactNode;
  if (view.mode === "diff" && !fDiff.enabled) {
    body = (
      <>
        <div className="notice" role="note">
          The difference view is switched off until it passes its validation gate. Use blink, onion-skin or
          side-by-side to compare visits.
        </div>
        {panel(shown.id, { title: shown.label })}
      </>
    );
  } else if (view.mode === "diff" && !diffPair) {
    body = <><div className="notice" role="note">A difference needs two full visits in this band.</div>{panel(shown.id, {})}</>;
  } else if (diffOn) {
    const d = diffq.data;
    body = (
      <div className="panel">
        <div className="panel-title">
          {diffPair![0]} − {diffPair![1]} · band {cur.band} · λ-matched significance (±{d?.info.clip_sigma ?? 5}σ)
          {(fDiff.unvalidated || d?.info.validity === "unvalidated") && <UnvalidatedBadge />}
        </div>
        <div className="canvas-wrap">
          {d && useGL ? (
            <GLCanvas bits={d.bits} nx={nx} ny={ny} lo={-(d.info.clip_sigma)} hi={d.info.clip_sigma} stretch={{ mode: "diverging", beta: 1 }}
              cmap="diverging" transform={transform} onTransform={setTransform} onHover={onHover} onError={(why) => setGlFailed(why)}
              label={`λ-matched difference ${diffPair![0]} minus ${diffPair![1]}, band ${cur.band}`} />
          ) : d ? (
            <div className="notice">The difference view needs WebGL2.</div>
          ) : <div className="panel-loading" role="status">{diffq.isError ? `Difference failed: ${(diffq.error as Error).message}` : "Computing difference…"}</div>}
          <OverlayLayer grid={m.grid} transform={transform} annotations={d?.info.annotations} />
        </div>
        <div className="legend diverging" aria-hidden="true"><span>−{d?.info.clip_sigma ?? 5}σ (where it was in {diffPair![1]})</span><span>0</span><span>+{d?.info.clip_sigma ?? 5}σ (where it is in {diffPair![0]})</span></div>
        {d?.info.photometric_match && <PhotometricMatchCard pm={d.info.photometric_match} />}
      </div>
    );
  } else if (view.mode === "side") {
    const [a, z] = pair ?? [cur.bins[0]!.id, cur.bins[cur.bins.length - 1]!.id];
    const la = cur.allBins.find((x) => x.id === a), lz = cur.allBins.find((x) => x.id === z);
    body = <div className="side">{panel(a, { title: la?.label ?? a, key: "A" })}{panel(z, { title: lz?.label ?? z, key: "B" })}</div>;
  } else if (view.mode === "onion") {
    body = panel(shown.id, { bits2: bits[prev.id] ?? null, mix: 0.5, title: `${shown.id} + ${prev.id} (50/50 onion-skin)`, key: "main" });
  } else if (view.mode === "flip") {
    body = <Flipbook webgl={useGL} />;
  } else if (cur.rgbBands || view.bands.startsWith("rgb:")) {
    body = fRgb.enabled ? <RgbCanvas bin={shown.id} /> : panel(shown.id, { key: "main" });
  } else {
    // One canvas for the whole blink: its textures stay resident, so frames switch without re-upload, and a new
    // WebGL context is not created on every frame (browsers cap live contexts at about 16).
    body = panel(shown.id, { key: "main" });
  }

  return (
    <div className={`viewer mode-${view.mode}`}>
      {m.stacks.some((s) => s.filled) && <label className="raw-toggle"><input type="checkbox" checked={showRaw}
        onChange={(e) => setShowRaw(e.target.checked)} />Show raw pixels (fitted cores are display only)</label>}
      {view.bands.startsWith("rgb:") && !fRgb.enabled && (
        <div className="notice small" role="note">RGB composites are switched off in this environment; showing band {cur.band} alone.</div>
      )}
      {!useGL && <div className="notice small" role="note">Showing server-rendered frames{glFailed ? ` (WebGL unavailable: ${glFailed})` : ""}.</div>}
      {useGL && view.mode !== "flip" && <ZoomButtons nx={nx} ny={ny} />}
      {body}
      {view.mode !== "side" && view.mode !== "diff" && view.mode !== "flip" && (
        <div className={`frame-caption ${shown.status}`} aria-live="polite">
          <strong>{shown.label}</strong>
          {shown.status === "partial" && <span className="badge partial">partial: {shown.n_frames} frames</span>}
          {comparing && <span className="badge">comparing with previous</span>}
          {/* Catalogue cones can take tens of seconds at IRSA the first time (AllWISE: ≈40 s): say so instead of
              leaving a ticked layer that seems to do nothing (browser test 2026-11-14). */}
          {wantCats.length > 0 && !ovq.data && ovq.isFetching && <span className="badge">loading catalogue markers…</span>}
          {wantCats.length > 0 && ovq.isError && <span className="badge warn" title={String(ovq.error)}>catalogue markers unavailable right now</span>}
          {view.ov.includes("sso") && (() => {
            const nt = cur.stack(shown.id)?.transients?.length ?? 0, na = catSources.filter((x) => x.cat === "sso").length;
            return <span className="badge" title="Asteroid layer: circles are known asteroids (JPL Horizons, as seen from SPHEREx); diamonds are unvetted single-exposure transients. Click one for details.">
              {na} known asteroid{na === 1 ? "" : "s"} · {nt} transient{nt === 1 ? "" : "s"} (click for details)</span>;
          })()}
          {(cur.stack(shown.id)?.skipped.length ?? 0) > 0 && (
            <span className="badge warn" title={cur.stack(shown.id)!.skipped.map(([id, why]) => `${id}: ${why}`).join("\n")}>
              {cur.stack(shown.id)!.skipped.length} frame(s) skipped
            </span>
          )}
        </div>
      )}
      {!embed && selected && (
        <div className="selection-bar" role="group" aria-label="Selected position">
          <Icon name="target" size={14} />
          <span className="mono">{formatRA(selected.ra)} {formatDec(selected.dec)}</span>
          {fCand.enabled && (
            <button onClick={() => useApp.getState().setDialog("report")}>Report a candidate here</button>
          )}
          <button className="link" onClick={() => setView({ sel: null })}>Clear</button>
        </div>
      )}
    </div>
  );
}

/** On-screen zoom (audit F-22): wheel and +/− keys do not exist on a phone or in an embed. */
export function ZoomButtons({ nx, ny }: { nx: number; ny: number }) {
  const transform = useApp((s) => s.transform);
  const setTransform = useApp((s) => s.setTransform);
  const v = transform ?? { cx: nx / 2, cy: ny / 2, zoom: 1 };
  const zoom = (f: number) => {
    const z = Math.min(16, Math.max(1, v.zoom * f));
    setTransform(z === 1 ? null : { ...v, zoom: z });
  };
  return (
    <div className="zoom-buttons" role="group" aria-label="Zoom">
      <button className="icon-btn" onClick={() => zoom(1.5)} disabled={v.zoom >= 16} aria-label="Zoom in" title="Zoom in (+)">+</button>
      <button className="icon-btn" onClick={() => zoom(1 / 1.5)} disabled={v.zoom <= 1} aria-label="Zoom out" title="Zoom out (−)">−</button>
      <button className="icon-btn" onClick={() => setTransform(null)} disabled={v.zoom <= 1} aria-label="Fit the whole field" title="Fit (0)">fit</button>
      {v.zoom > 1 && <span className="micro">×{v.zoom.toFixed(1)}</span>}
    </div>
  );
}

/** ?gl=0 forces the PNG fallback (testing P0-8 without disabling WebGL in the browser). */
const FORCE_PNG = (() => {   // read once at load: the canonical URL rewrite drops debug params
  try { return new URLSearchParams(location.search).get("gl") === "0"; } catch { return false; }
})();
function forcePng(): boolean { return FORCE_PNG; }
