/**
 * 25-year blink (P2-1, implementation.md §4.13; gate G5.25yr): 2MASS → AllWISE → NEOWISE → SPHEREx on one grid,
 * built server-side (`GET /views/{key}/blink25`). Every epoch is in units of its own sky σ, so one stretch fits
 * all telescopes. The label "different telescopes, positions only" comes from the server and is always shown:
 * brightness differences between epochs mean nothing here. The ring marks pos(t) at each epoch (M's model).
 */
import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import type { TrackPoint } from "../api/types";
import { useFeature } from "../hooks/useCurrent";
import { parseStretch } from "../lib/stretch";
import { webgl2Available } from "../gl/renderer";
import { useApp } from "../state/store";
import { UnvalidatedBadge } from "./Badges";
import { GLCanvas } from "./GLCanvas";
import { Modal } from "./Dialogs";
import { Icon } from "./Icon";
import { OverlayLayer } from "./OverlayLayer";

/** Common stretch in sky-σ units: sky at the bottom, stars well above it. */
export const SIGMA_LIMITS = { lo: -2, hi: 40 };

export function Blink25Panel() {
  const m = useApp((s) => s.manifest);
  const fps = useApp((s) => s.view.fps);
  const setView = useApp((s) => s.setView);
  const f = useFeature("blink25");
  const [run, setRun] = useState(false);
  const [i, setI] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [expanded, setExpanded] = useState(false);
  const q = useQuery({
    queryKey: ["blink25", m?.key],
    enabled: f.enabled && !!m && run,
    retry: false,
    staleTime: Infinity,
    queryFn: () => api.blink25(m!.key),
  });
  const shown = q.data?.epochs.filter((e) => e.url) ?? [];
  const n = shown.length;
  const ep = shown[Math.min(i, Math.max(0, n - 1))];
  const bits = useQuery({
    queryKey: ["blink25-epoch", ep?.url],
    enabled: !!ep?.url && !!q.data,
    staleTime: Infinity,
    queryFn: () => api.payloadF16(ep!.url!, q.data!.format),
  });
  useEffect(() => { setI(0); setPlaying(false); }, [m?.key]);
  useEffect(() => {
    if (!playing || n < 2) return;
    const id = setInterval(() => setI((x) => (x + 1) % n), 1000 / Math.min(fps, 2));
    return () => clearInterval(id);
  }, [playing, n, fps]);

  if (!f.enabled || !m || m.target?.kind !== "star") return null;
  const g = q.data?.grid;
  const marks: TrackPoint[] = shown.map((e, k) => ({ bin: String(k), band: 6, mjd: 0, ra: e.ra, dec: e.dec }));
  const missing = q.data?.epochs.filter((e) => !e.url) ?? [];
  const narrow = q.data && q.data.view_fov_arcmin < q.data.view_fov_for_full_coverage_arcmin;
  const at = Math.min(i, Math.max(0, n - 1));
  const player = (big: boolean) => g && q.data ? (
    <div className={big ? "blink25-player big" : "blink25-player"}>
      <div className="controls small" role="toolbar" aria-label="25-year blink controls">
        <button aria-label={playing ? "Pause" : "Play"} className="play" aria-pressed={playing} disabled={n < 2} onClick={() => setPlaying(!playing)}><Icon name={playing ? "pause" : "play"} size={15} /></button>
        <input type="range" min={0} max={Math.max(0, n - 1)} value={at} disabled={n < 2}
          aria-label="Epoch" onChange={(e) => { setPlaying(false); setI(Number(e.target.value)); }} />
      </div>
      <div className="canvas-wrap blink25">
        {!webgl2Available() ? <div className="notice">The 25-year blink needs WebGL2.</div> : bits.data ? (
          <GLCanvas bits={bits.data} nx={g.shape[1]} ny={g.shape[0]} lo={SIGMA_LIMITS.lo} hi={SIGMA_LIMITS.hi}
            stretch={parseStretch("asinh:8")} cmap="gray" transform={null}
            label={`25-year blink, ${ep?.label} ${ep?.date}; ${q.data.label}`} />
        ) : <div className="panel-loading" role="status">Loading…</div>}
        <OverlayLayer grid={g} transform={null} track={marks} currentBin={String(at)} />
      </div>
      <div className="frame-caption" aria-live="polite">
        {ep && <strong>{ep.label} · {ep.date || ep.year.toFixed(1)}</strong>}
        {ep && ep.pairs_with_band && <span className="badge">pairs with SPHEREx band {ep.pairs_with_band}</span>}
        {ep && ep.n_images > 1 && <span className="badge">{ep.n_images} images combined</span>}
      </div>
    </div>
  ) : null;
  // pos_source reads "<model> (<what it uses>)": show the plain-language part, keep the model name as a detail
  const posModel = q.data?.pos_source.match(/^(\S+)\s*\((.*)\)$/);
  const details = q.data ? (
    <div className="blink25-details">
      <table className="compare b25-epochs">
        <thead><tr><th>epoch</th><th>date</th><th>images</th></tr></thead>
        <tbody>{shown.map((e, k) => (
          <tr key={k} className={k === at ? "current" : ""} onClick={() => { setPlaying(false); setI(k); }}>
            <td>{e.label}</td><td>{e.date || e.year.toFixed(1)}</td><td>{e.n_images}</td>
          </tr>
        ))}</tbody>
      </table>
      {Object.keys(q.data.expected_jumps_arcmin).length > 0 && (
        <table className="compare b25-jumps">
          <thead><tr><th>expected shift (catalogue)</th><th>arcmin</th></tr></thead>
          <tbody>{Object.entries(q.data.expected_jumps_arcmin).map(([k, v]) => {
            const [what, why] = [k.split(" (")[0]!, k.includes(" (") ? k.slice(k.indexOf(" (") + 2, -1) : ""];
            return <tr key={k} title={k}><td>{what.replace("→", " → ")}{why && <small className="hint"> {why}</small>}</td><td>{v.toFixed(2)}′</td></tr>;
          })}</tbody>
        </table>
      )}
      <dl className="kv stacked small">
        {q.data.twomass_match && <><dt>2MASS match</dt><dd>{q.data.twomass_match}</dd></>}
        <dt>positions (rings)</dt><dd>{posModel ? <>{posModel[2]} <small className="mono">{posModel[1]}</small></> : q.data.pos_source}</dd>
      </dl>
      {narrow && (
        <p className="hint small">The SPHEREx epoch only covers this view's {q.data.view_fov_arcmin}′ field.{" "}
          <button className="link" onClick={() => setView({ fov: Math.min(30, Math.ceil(q.data!.view_fov_for_full_coverage_arcmin)) })}>
            Open at {Math.min(30, Math.ceil(q.data.view_fov_for_full_coverage_arcmin))}′</button> to cover the whole blink field.</p>
      )}
      {missing.length > 0 && <p className="hint small">{missing.length} epoch(s) not shown: {missing.map((e) => `${e.label} ${e.date}: ${e.note ?? "unavailable"}`).join("; ")}</p>}
    </div>
  ) : null;
  return (
    <details className="card" open={run}>
      <summary><h2>25-year blink</h2>{f.unvalidated && <UnvalidatedBadge />}</summary>
      <div className="card-body">
        {!run ? (
          <>
            <p className="small">2MASS (≈2000) → AllWISE (2010) → NEOWISE (2014–2024) → SPHEREx, on one grid. Fetches archival images
              from IRSA; this can take a minute.</p>
            <button onClick={() => setRun(true)}>Build the 25-year blink</button>
          </>
        ) : q.isFetching && !q.data ? (
          <p role="status">Searching 2MASS and WISE archives and regridding every epoch…</p>
        ) : q.isError ? (
          <p className="error">25-year blink unavailable: {(q.error as Error).message}</p>
        ) : q.data && g ? (
          <>
            <p className="notice small" role="note"><strong>{q.data.label}</strong>. Very bright stars can appear as rings:
              where a detector saturated, the core is masked rather than filled.</p>
            {player(false)}
            <div className="row expand-row">
              <button onClick={() => setExpanded(true)} title="Open a large view of the 25-year blink"><Icon name="expand" size={12} />expand</button>
            </div>
            {details}
            {expanded && (
              <Modal title="25-year blink" onClose={() => setExpanded(false)} wide>
                <p className="notice small" role="note"><strong>{q.data.label}</strong>.</p>
                <div className="blink25-wide">{player(true)}{details}</div>
              </Modal>
            )}
          </>
        ) : null}
      </div>
    </details>
  );
}
