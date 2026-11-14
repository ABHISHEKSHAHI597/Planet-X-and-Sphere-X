/**
 * Target bar (P0-1): one box for names, aliases, "sso:<name>" or RA/Dec (decimal or sexagesimal,
 * Unicode minus). The backend resolves names (alias table, escaped SIMBAD query, PM propagation) and
 * runs the epoch guard on coordinates.
 */
import { useEffect, useId, useState } from "react";
import { looksLikeCoordinates, normalizeInput, parseCoordinates } from "../lib/coords";
import { href } from "../lib/base";
import { displayName } from "../lib/names";
import { FOV_PRESETS } from "../lib/constants";
import { missionFor } from "../content/missions";
import { useApp } from "../state/store";
import type { ViewState } from "../state/url";
import { FreshnessBadge } from "./Badges";
import { Icon } from "./Icon";

export function targetPatch(text: string): { patch: Partial<ViewState> } | { error: string } {
  const t = text.trim();
  if (!t) return { error: "Type a star's name or its coordinates." };
  const reset: Partial<ViewState> = { sel: null, t: null, a: null, b: null, pin: null };
  if (looksLikeCoordinates(t)) {
    const c = parseCoordinates(t);
    if (!c) return { error: "Those coordinates could not be read. Try 269.4461 4.7707 or 17:57:47.1 +04:46:14." };
    return { patch: { ...reset, q: null, ra: c.ra.toFixed(6), dec: c.dec.toFixed(6) } };
  }
  // One of the five test targets opens its pinned frame list (prewarmed, works offline); the "newer data"
  // banner offers the live list when the archive has moved on (audit F-01).
  return { patch: { ...reset, q: t, ra: null, dec: null, pin: missionFor([t])?.pin ?? null } };
}

/** Wordmark: two overlapping plates (the blink) and the name. */
export function Brand() {
  return (
    <a className="brand" href={href()} aria-label="ParallaX home">
      <svg className="brand-mark" viewBox="0 0 28 28" aria-hidden="true"><circle cx="11" cy="14" r="5.5" /><circle cx="17" cy="14" r="5.5" /></svg>
      <span className="brand-word">Paralla<span>X</span></span>
    </a>
  );
}

/** The one target box (P0-1). `hero` is the large home-page version; both submit through targetPatch. */
export function TargetSearch({ variant = "bar", autoFocus = false }: { variant?: "bar" | "hero"; autoFocus?: boolean }) {
  const view = useApp((s) => s.view);
  const setView = useApp((s) => s.setView);
  const shown = view.q ?? (view.ra && view.dec ? `${view.ra} ${view.dec}` : "");
  const [text, setText] = useState(shown);
  const [err, setErr] = useState<string | null>(null);
  const id = useId();
  useEffect(() => { setText(shown); }, [shown]);

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    const r = targetPatch(text);
    if ("error" in r) { setErr(r.error); return; }
    setErr(null);
    useApp.setState({ frame: 0, transform: null, dismissedHint: null });
    setView(r.patch, { push: true });
  };

  return (
    <form onSubmit={submit} role="search" className={`target-form${variant === "hero" ? " hero" : ""}`}>
      <label htmlFor={id} className={variant === "hero" ? "target-label" : "sr-only"}>Star name or RA/Dec</label>
      <div className="target-field">
        <Icon name="search" size={variant === "hero" ? 20 : 16} className="target-icon" />
        <input id={id} value={text} onChange={(e) => { setText(e.target.value); if (err) setErr(null); }}
          placeholder={variant === "hero" ? "e.g. Barnard's Star" : "Barnard's Star · WISE 0855 · 08:55:10.8 −07:14:42"}
          autoComplete="off" spellCheck={false} autoFocus={autoFocus} aria-invalid={!!err} aria-describedby={err ? `${id}-err` : undefined} />
        <button type="submit"><span>{variant === "hero" ? "Blink it" : "Go"}</span><Icon name="arrow" size={15} /></button>
      </div>
      {err && <span id={`${id}-err`} className="field-error" role="alert">{err}</span>}
    </form>
  );
}

export function TargetBar() {
  const view = useApp((s) => s.view);
  const setView = useApp((s) => s.setView);
  const m = useApp((s) => s.manifest);
  const setDialog = useApp((s) => s.setDialog);
  const hasTarget = !!(view.q || (view.ra && view.dec));

  const levels: [ViewState["ui"], string][] = [["simple", "Simple"], ["explorer", "Explorer"], ["expert", "Expert"]];
  return (
    <header className={`target-bar${hasTarget ? "" : " on-home"}`}>
      <Brand />
      {hasTarget && <TargetSearch />}
      <div className="readout">
        {m?.target && <span className="resolved" title={m.target.astrometry_source ?? undefined}><Icon name="target" size={14} />{displayName(m.target)}</span>}
        <label className="fov"><span className="micro">FOV</span>
          <select value={view.fov} onChange={(e) => setView({ fov: Number(e.target.value) })} aria-label="Field of view (arcminutes)">
            {[...new Set([...FOV_PRESETS, view.fov])].sort((a, b) => a - b).map((f) => <option key={f} value={f}>{f}′</option>)}
          </select>
        </label>
        {!hasTarget && <FreshnessBadge />}{/* in the viewer it sits in the timeline header */}
      </div>
      <div className="actions">
        <div className="ui-level segmented" role="radiogroup" aria-label="Detail level">
          {levels.map(([v, l]) => (
            <button key={v} type="button" role="radio" aria-checked={view.ui === v} className={view.ui === v ? "on" : ""}
              onClick={() => setView({ ui: v })}>{l}</button>
          ))}
        </div>
        {hasTarget && <button className="share" onClick={() => setDialog("share")} disabled={!m}><Icon name="share" size={15} /><span>Share</span></button>}
        <button className="icon-btn" onClick={() => setDialog("help")} aria-label="Keyboard shortcuts" title="Keyboard shortcuts (?)"><Icon name="keyboard" size={17} /></button>
        <a href={href("about")} className="about-link button icon-btn" aria-label="About & credits" title="About & credits"
          onClick={(e) => { e.preventDefault(); setDialog("about"); }}><Icon name="info" size={17} /></a>
      </div>
    </header>
  );
}

export function EpochBanner() {
  const m = useApp((s) => s.manifest);
  const view = useApp((s) => s.view);
  const dismissed = useApp((s) => s.dismissedHint);
  const dismiss = useApp((s) => s.dismissHint);
  const setView = useApp((s) => s.setView);
  const h = m?.target?.epoch_hint;
  if (!h || dismissed === m!.key) return null;
  const moved = h.moved_arcmin >= 1 ? `${h.moved_arcmin.toFixed(1)}′` : `${(h.moved_arcmin * 60).toFixed(0)}″`;
  return (
    <div className="banner epoch" role="alert">
      <Icon name="alert" size={16} className="banner-icon" />
      <span className="banner-text">These coordinates match <strong>{h.object}</strong> as of ≈{h.epoch.toFixed(1)}. It has since moved {moved} {h.direction}.</span>
      <span className="banner-actions"><button className="primary" onClick={() => {
        // Keep the view's pin: it is the frame list of this field, so the tracked view is the prewarmed one (F-03).
        const mission = missionFor([h.object]);
        useApp.setState({ frame: 0, transform: null });
        setView({ q: mission?.q ?? normalizeInput(h.object), ra: null, dec: null, pin: m!.pin && view.pin ? m!.pin : mission?.pin ?? null, t: null }, { push: true });
      }}>
        Track it
      </button>{" "}
      <button onClick={() => dismiss(m!.key)}>Keep fixed sky</button></span>
    </div>
  );
}

/** `placeholderShowsError`: the main app's empty-plate placeholder already explains errors that stop a view being built. */
export function Progress({ placeholderShowsError = false }: { placeholderShowsError?: boolean }) {
  const p = useApp((s) => s.progress);
  const err = useApp((s) => s.error);
  const m = useApp((s) => s.manifest);
  if (err && placeholderShowsError && !m) return null;
  if (err) return <div className="banner error" role="alert"><Icon name="alert" size={16} className="banner-icon" /><span className="banner-text">{err}</span></div>;
  if (p.phase === "idle" || p.phase === "done") return null;
  const label = p.phase === "resolving" ? "Finding the target…" : p.phase === "planning" ? "Planning the frames…"
    : `Fetching and stacking frames ${p.i}/${p.n} (your band first)`;
  return (
    <div className="progress" role="status" aria-live="polite">
      <span className="progress-dot" aria-hidden="true" />
      <span>{label}</span>
      {p.n > 0 && <progress max={p.n} value={p.i} />}
      {p.n > 0 && <span className="progress-count">{Math.round((100 * p.i) / p.n)}%</span>}
    </div>
  );
}
