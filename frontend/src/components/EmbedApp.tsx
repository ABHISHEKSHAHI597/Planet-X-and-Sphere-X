/**
 * /embed (P1-5, implementation.md §5.3): the viewer with minimal chrome. Host pages may drive it with
 * postMessage; messages are validated and anything else is ignored. The page posts its state back
 * (`parallax:state`) so hosts can follow along. CSP frame-ancestors * is set by the server on /embed only.
 */
import { useEffect, useRef } from "react";
import { href } from "../lib/base";
import { stepFrame } from "../lib/player";
import { selectBands, useCurrent, useFeature } from "../hooks/useCurrent";
import { useApp } from "../state/store";
import { toSearch, type ViewState } from "../state/url";
import { DataSourceBanner } from "./Badges";
import { useReducedMotion, Viewer } from "./Viewer";
import { Progress } from "./TargetBar";
import { Icon } from "./Icon";

type Msg =
  | { type: "parallax:goto"; ra: number; dec: number }
  | { type: "parallax:target"; q: string }
  | { type: "parallax:band"; band: number }
  | { type: "parallax:play"; playing: boolean };

export function validateMessage(d: unknown): Msg | null {
  if (!d || typeof d !== "object") return null;
  const o = d as Record<string, unknown>;
  const fin = (x: unknown): x is number => typeof x === "number" && Number.isFinite(x);
  switch (o.type) {
    case "parallax:goto":
      return fin(o.ra) && fin(o.dec) && o.ra >= 0 && o.ra < 360 && o.dec >= -90 && o.dec <= 90 ? { type: o.type, ra: o.ra, dec: o.dec } : null;
    case "parallax:target":
      return typeof o.q === "string" && o.q.length > 0 && o.q.length <= 100 ? { type: o.type, q: o.q } : null;
    case "parallax:band":
      return fin(o.band) && Number.isInteger(o.band) && o.band >= 1 && o.band <= 6 ? { type: o.type, band: o.band } : null;
    case "parallax:play":
      return typeof o.playing === "boolean" ? { type: o.type, playing: o.playing } : null;
    default:
      return null;
  }
}

export function applyMessage(msg: Msg): void {
  const st = useApp.getState();
  const reset: Partial<ViewState> = { pin: null, t: null, sel: null, a: null, b: null };
  switch (msg.type) {
    case "parallax:goto": useApp.setState({ frame: 0, transform: null }); st.setView({ ...reset, q: null, ra: msg.ra.toFixed(6), dec: msg.dec.toFixed(6) }); break;
    case "parallax:target": useApp.setState({ frame: 0, transform: null }); st.setView({ ...reset, q: msg.q, ra: null, dec: null }); break;
    case "parallax:band": selectBands(String(msg.band)); break;
    case "parallax:play": st.setPlaying(msg.playing); break;
  }
}

export function EmbedApp() {
  const m = useApp((s) => s.manifest);
  const view = useApp((s) => s.view);
  const cur = useCurrent();
  const f = useFeature("embed");
  useEffect(() => {
    const h = (e: MessageEvent) => { const msg = validateMessage(e.data); if (msg) applyMessage(msg); };
    window.addEventListener("message", h);
    return () => window.removeEventListener("message", h);
  }, []);
  useEffect(() => {
    if (window.parent !== window) window.parent.postMessage({ type: "parallax:state", search: toSearch(view), bin: cur.bin?.id ?? null }, "*");
  }, [view, cur.bin?.id]);
  const reduced = useReducedMotion();
  // Autoplay the blink once per view, except for visitors who asked for reduced motion (implementation.md §6.7).
  // Keyed on the view, not the manifest object: that is replaced about once a second while stacks land, and each
  // replacement used to undo a visitor's pause (audit F-12).
  const autoplayed = useRef<string | null>(null);
  useEffect(() => {
    if (!m || cur.bins.length < 2 || reduced || autoplayed.current === m.key) return;
    autoplayed.current = m.key;
    useApp.getState().setPlaying(true);
  }, [m, cur.bins.length, reduced]);
  const rel = useApp((s) => s.release);
  if (rel && !f.enabled) return <main className="embed"><p>Embedding is not enabled on this server.</p></main>;
  return (
    <main className="embed">
      <DataSourceBanner />
      <Progress />
      <Viewer embed />
      {m && <EmbedControls />}
      <a className="embed-link" href={`${href()}${toSearch(view)}`} target="_blank" rel="noreferrer">Open in ParallaX <Icon name="external" size={13} /></a>
    </main>
  );
}

/** Play, step and band chips for embeds, which on a phone have no keyboard (audit F-26). */
function EmbedControls() {
  const m = useApp((s) => s.manifest);
  const playing = useApp((s) => s.playing);
  const cur = useCurrent();
  const n = cur.bins.length;
  const st = useApp.getState;
  return (
    <div className="embed-controls" role="toolbar" aria-label="Blink controls">
      <button className="icon-btn" aria-label="Previous frame" disabled={n < 2}
        onClick={() => { st().setPlaying(false); st().setFrame(stepFrame(cur.index, n, -1)); }}><Icon name="prev" size={14} /></button>
      <button className="icon-btn" aria-label={playing ? "Pause" : "Play"} aria-pressed={playing} disabled={n < 2}
        onClick={() => st().setPlaying(!playing)}><Icon name={playing ? "pause" : "play"} size={14} /></button>
      <button className="icon-btn" aria-label="Next frame" disabled={n < 2}
        onClick={() => { st().setPlaying(false); st().setFrame(stepFrame(cur.index, n, 1)); }}><Icon name="next" size={14} /></button>
      <span className="bands" role="radiogroup" aria-label="Band">
        {(m?.bands ?? []).map((b) => (
          <button key={b} role="radio" aria-checked={cur.band === b} className={cur.band === b ? "on" : ""} data-band={b}
            onClick={() => selectBands(String(b))}>{b}</button>
        ))}
      </span>
    </div>
  );
}
