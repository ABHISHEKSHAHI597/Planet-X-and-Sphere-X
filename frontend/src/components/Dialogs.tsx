/** Share/embed (P0-5, P1-5), About & Credits (P0-7), keyboard help, candidate report (P2-9). */
import { Fragment, useEffect, useRef, useState } from "react";
import { api } from "../api/client";
import type { CandidateKind, CandidateResponse } from "../api/types";
import { CREDITS, DISCLAIMER, SI_USE, SOFTWARE } from "../content/credits";
import { useCurrent, useFeature } from "../hooks/useCurrent";
import { href } from "../lib/base";
import { reportText } from "../lib/linkouts";
import { displayName } from "../lib/names";
import { mjdToISODate } from "../lib/time";
import { useApp } from "../state/store";
import { toSearch } from "../state/url";
import { Icon } from "./Icon";

export function Modal({ title, onClose, children, narrow = false, wide = false }: { title: string; onClose: () => void; children: React.ReactNode; narrow?: boolean; wide?: boolean }) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const d = ref.current;
    if (d && !d.open) { try { d.showModal(); } catch { d.setAttribute("open", ""); } }
  }, []);
  return (
    <dialog ref={ref} className={`modal${narrow ? " narrow" : ""}${wide ? " wide" : ""}`} aria-label={title} onClose={onClose} onCancel={onClose}>
      <header><h2>{title}</h2><button className="icon-btn" onClick={onClose} aria-label="Close"><Icon name="close" size={16} /></button></header>
      <div className="modal-body">{children}</div>
    </dialog>
  );
}

function Copy({ text, label }: { text: string; label: string }) {
  const [ok, setOk] = useState(false);
  return (
    <div className="copy">
      <label>{label}<textarea readOnly value={text} rows={text.length > 120 ? 4 : 2} onFocus={(e) => e.target.select()} /></label>
      <button onClick={() => navigator.clipboard?.writeText(text).then(() => { setOk(true); setTimeout(() => setOk(false), 1500); })}><Icon name={ok ? "check" : "copy"} size={14} />{ok ? "Copied" : "Copy"}</button>
    </div>
  );
}

export function ShareDialog({ onClose }: { onClose: () => void }) {
  const view = useApp((s) => s.view);
  const m = useApp((s) => s.manifest);
  const fEmbed = useFeature("embed");
  const [pinned, setPinned] = useState(true);
  const state = { ...view, pin: pinned ? m?.pin ?? view.pin : null };
  const url = `${location.origin}${href()}${toSearch(state)}`;
  const embed = `${location.origin}${href("embed")}${toSearch({ ...state, ui: "simple" })}`;
  const iframe = `<iframe src="${embed.replace(/&/g, "&amp;")}" width="480" height="520" style="border:0" loading="lazy" allowfullscreen title="ParallaX SPHEREx blink"></iframe>`;
  return (
    <Modal title="Share this view" onClose={onClose}>
      <label className="check"><input type="checkbox" checked={pinned} onChange={(e) => setPinned(e.target.checked)} />
        Pin the frame list (the link keeps showing exactly these frames when new data arrives)</label>
      <Copy label="Link" text={url} />
      {fEmbed.enabled && <Copy label="Embed (iframe)" text={iframe} />}
      {fEmbed.enabled && <p className="small">Host pages can drive the embed with <code>postMessage({"{"}type: "parallax:goto", ra, dec{"}"})</code>.</p>}
    </Modal>
  );
}

export function AboutPage({ onClose }: { onClose?: () => void }) {
  const H = onClose ? "h3" : "h2";       // under the dialog's h2, or under the /about page's h1
  const H4 = onClose ? "h4" : "h3";
  const body = (
    <div className="about">
      <section>
        <H>What this is</H>
        <p>ParallaX blinks SPHEREx images of any patch of sky so you can see what moves and what changes. A frame is one
          <em> visit</em> (a 1–3 week pass over the patch, stacked per detector band), not a single exposure: consecutive SPHEREx
          exposures are taken at different wavelengths, so blinking them would show the spectrum, not motion.</p>
        <p>Every frame of a blink uses the same brightness scale. Partial visits are hatched and left out by default.
          Pixels with no data are tinted purple, never shown as black sky.</p>
        <p><a href={href("proof")}>What we checked, and what we have not</a>: each claim with its number and its evidence record.</p>
      </section>
      <section>
        <H>Data and acknowledgements</H>
        {CREDITS.map((c) => (
          <div key={c.id} className="credit">
            <H4>{c.name}</H4>
            <p>{c.text}</p>
            {c.dois && <p>DOIs: {c.dois.map((d) => <a key={d} href={`https://doi.org/${d}`} rel="noreferrer" target="_blank">{d} </a>)}</p>}
            <p className="small"><a href={c.url} target="_blank" rel="noreferrer">{c.url}</a></p>
          </div>
        ))}
      </section>
      <section>
        <H>Software</H>
        <ul>{SOFTWARE.map((s) => <li key={s.name}><a href={s.url} target="_blank" rel="noreferrer">{s.name}</a> — {s.cite}</li>)}</ul>
      </section>
      <section><p className="small">{SI_USE}</p><p className="small">{DISCLAIMER}</p></section>
    </div>
  );
  return onClose ? <Modal title="About & credits" onClose={onClose}>{body}</Modal> : body;
}

export const SHORTCUTS: [string, string][] = [
  ["Space", "play / pause"], ["← →", "previous / next frame"], ["1–6", "choose band"], ["hold B", "flash the previous frame"],
  ["O", "onion-skin"], ["S", "side by side"], ["D", "difference (when available)"], ["F", "spectral flipbook (when available)"],
  ["+ / −", "zoom"], ["0", "reset zoom"], ["?", "this help"],
];

export function HelpDialog({ onClose }: { onClose: () => void }) {
  return (
    <Modal title="Keyboard shortcuts" onClose={onClose} narrow>
      <dl className="kv">{SHORTCUTS.map(([k, v]) => <Fragment key={k}><dt><kbd>{k}</kbd></dt><dd>{v}</dd></Fragment>)}</dl>
    </Modal>
  );
}

export function ReportDialog({ onClose }: { onClose: () => void }) {
  const m = useApp((s) => s.manifest);
  const view = useApp((s) => s.view);
  const cur = useCurrent();
  const [kind, setKind] = useState<CandidateKind>("mover");
  const [note, setNote] = useState("");
  const [res, setRes] = useState<CandidateResponse | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const pos = view.sel?.split(",").map(Number);
  // Claim only what the reporter looked at: the visit on screen, plus any they tick (audit F-21: sending every
  // visit made the "seen in ≥ 2 visits" check pass for every report).
  const [extra, setExtra] = useState<string[]>([]);
  const shown = cur.bin?.id ?? null;
  const seen = [...new Set([...(shown ? [shown] : []), ...extra])];
  if (!m || !pos) return <Modal title="Report a candidate" onClose={onClose} narrow><p>Click a source in the viewer first.</p></Modal>;
  // The same report as plain text, for a forum post or an e-mail (optimisation.md IMP-3). It needs no server, so it
  // also works in the frozen copy, where a report cannot be saved.
  const asText = reportText({
    kind, ra: pos[0]!, dec: pos[1]!, target: m.target ? displayName(m.target) : null, band: cur.band, note, reportId: res?.id,
    visits: cur.bins.filter((b) => seen.includes(b.id)).map((b) => ({ label: b.id, date: mjdToISODate(b.mjd_mean) })),
    permalink: `${location.origin}${href()}${toSearch({ ...view, pin: m.pin ?? view.pin })}`,
  });
  return (
    <Modal title="Report a candidate" onClose={onClose} narrow>
      <p className="honesty">Candidates are not discoveries until confirmed by follow-up.</p>
      {res ? (
        <>
          <p>Thank you. Report <code>{res.id}</code> was saved. Automatic checks:</p>
          <ul className="checks">{res.auto_checks.map((c) => <li key={c.name} className={c.passed === null ? "pending" : c.passed ? "pass" : "fail"}>
            {c.passed === null ? <span className="dot" aria-label="pending" /> : <Icon name={c.passed ? "check" : "close"} size={14} />}
            <span className="sr-only">{c.passed === null ? "pending" : c.passed ? "passed" : "failed"}</span> {c.name} <small>{c.detail}</small></li>)}</ul>
        </>
      ) : (
        <form onSubmit={async (e) => {
          e.preventDefault();
          setErr(null);
          try {
            setRes(await api.candidate({ ra: pos[0]!, dec: pos[1]!, view_key: m.key, pin: m.pin, visits: seen, kind, note: note.slice(0, 1000) }));
          } catch (x) { setErr((x as Error).message); }
        }}>
          <label>What do you see?
            <select value={kind} onChange={(e) => setKind(e.target.value as CandidateKind)}>
              {(["mover", "variable", "transient", "artifact", "other"] as const).map((k) => <option key={k}>{k}</option>)}
            </select>
          </label>
          {cur.bins.length > 1 && (
            <fieldset className="seen-in">
              <legend>Also seen in (band {cur.band})</legend>
              {cur.bins.filter((b) => b.id !== shown).map((b) => (
                <label key={b.id} className="check"><input type="checkbox" checked={extra.includes(b.id)}
                  onChange={(e) => setExtra((x) => e.target.checked ? [...x, b.id] : x.filter((y) => y !== b.id))} /> {b.label}</label>
              ))}
            </fieldset>
          )}
          <p className="small">Reported for {shown ?? "no visit"}{extra.length ? ` and ${extra.length} more` : ""}.</p>
          <label>Note (plain text, up to 1000 characters)
            <textarea value={note} maxLength={1000} onChange={(e) => setNote(e.target.value)} rows={4} />
          </label>
          {err && <p className="error" role="alert">{err}</p>}
          <button type="submit">Send report</button>
        </form>
      )}
      <Copy label="As text, to post or send" text={asText} />
    </Modal>
  );
}
