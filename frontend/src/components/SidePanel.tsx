/**
 * Side panel (implementation.md §6.1–6.2, §6.5): target card, mission guide, astrometry card,
 * spectrum, light curve, frame inspector, sky context. Science panels appear only when the backend
 * enables their capability (workflow.md §9.6) and carry an "unvalidated" badge until accepted.
 * Every number shown comes from an API response; none is hard-coded (workflow.md §4.1).
 */
import { lazy, Suspense, useEffect, useMemo, useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import { missionFor } from "../content/missions";
import { useCurrent, useFeature } from "../hooks/useCurrent";
import { FEATURES, VARIABLE_OTYPE } from "../lib/constants";
import { feature } from "../lib/features";
import { formatDec, formatRA } from "../lib/coords";
import { missionText } from "../content/translations";
import { useLang } from "../lib/lang";
import { linkOuts } from "../lib/linkouts";
import { displayName } from "../lib/names";
import { sepArcsec } from "../lib/wcs";
import { mjdToISODate } from "../lib/time";
import { useApp } from "../state/store";
import { UnvalidatedBadge } from "./Badges";
import { Icon } from "./Icon";
import { Blink25Panel } from "./Blink25";
import { ScatterChart } from "./charts";
import { SpectrumChart } from "./SpectrumChart";
import { releaseOf } from "../lib/spectrum";
import { Modal } from "./Dialogs";
import { playSpectrum } from "../lib/sonify";
import { ErrorBoundary } from "./ErrorBoundary";
import { expo, fix, isNum, prec } from "../lib/format";

const SkyContext = lazy(() => import("./SkyContext"));
/** 2025-05-01: frames before it are commissioning (IOC); a null survey after it is "not known yet" (audit K-47). */
const SCIENCE_START_MJD = 60796.0;

function Section({ title, children, open = true, badge, kicker, className }: { title: string; children: React.ReactNode; open?: boolean; badge?: React.ReactNode; kicker?: string; className?: string }) {
  return (
    <details className={`card${className ? ` ${className}` : ""}`} open={open}>
      <summary><span className="summary-text">{kicker && <span className="kicker">{kicker}</span>}<h2>{title}</h2></span>{badge}</summary>
      <div className="card-body"><ErrorBoundary label={title}>{children}</ErrorBoundary></div>
    </details>
  );
}

export function TargetCard() {
  const m = useApp((s) => s.manifest);
  const t = m?.target;
  if (!t) return null;
  const mu = t.pm ? Math.hypot(t.pm[0], t.pm[1]) / 1000 : null;
  return (
    <Section title={displayName(t)} kicker="Target" className="target-card">
      <dl className="kv">
        {t.otype && <><dt>type</dt><dd>{t.otype}{t.spt ? ` · ${t.spt}` : ""}</dd></>}
        <dt>now (pos(t))</dt><dd>{formatRA(t.propagated_now.ra)} {formatDec(t.propagated_now.dec)} <small>({t.propagated_now.epoch.toFixed(2)})</small></dd>
        {mu !== null && <><dt>μ (catalogue)</dt><dd>{mu.toFixed(2)}″/yr</dd></>}
        {t.plx ? <><dt>ϖ (catalogue)</dt><dd>{t.plx.toFixed(1)} mas</dd></> : null}
        {t.astrometry_source && <><dt>source</dt><dd>{t.astrometry_source}</dd></>}
        <dt>grid</dt><dd>{m!.grid.shape[1]}×{m!.grid.shape[0]} px at {m!.grid.pix_arcsec}″{m!.grid.native ? " (native)" : " (upsampled, display only)"}</dd>
        <dt>axis</dt><dd>{m!.axis === "visit" ? "visits" : m!.axis}</dd>
        <dt>pin</dt><dd><code>{m!.pin}</code></dd>
      </dl>
    </Section>
  );
}

/** The same patch of sky in the tools people already use (optimisation.md IMP-3). The selected source if there is
 *  one, else the target where it is now. Plain links: nothing is sent to these sites until the visitor clicks. */
export function ElsewhereCard() {
  const m = useApp((s) => s.manifest);
  const sel = useApp((s) => s.view.sel);
  if (!m) return null;
  const picked = sel?.split(",").map(Number);
  const at = picked && picked.length === 2 && picked.every(Number.isFinite)
    ? { ra: picked[0]!, dec: picked[1]! }
    : m.target ? m.target.propagated_now : { ra: m.grid.crval[0], dec: m.grid.crval[1] };
  const fov = (m.grid.pix_arcsec * m.grid.shape[1]) / 60;
  return (
    <Section title="Look elsewhere" open={false}>
      <p className="small">{picked ? "The selected position" : "This position"} in other public tools:</p>
      <ul className="linkouts">
        {linkOuts(at.ra, at.dec, fov).map((l) => (
          <li key={l.id}><a href={l.url} target="_blank" rel="noreferrer">{l.name}</a> <small>{l.what}</small></li>
        ))}
      </ul>
    </Section>
  );
}

/** Details of an asteroid-layer marker clicked in the viewer: a known asteroid (JPL Horizons, as seen from SPHEREx) or
 *  a per-exposure transient of the stack. Everything shown comes from the overlay response or the manifest. */
export function MarkerCard() {
  const m = useApp((s) => s.manifest);
  const p = useApp((s) => s.picked);
  const setPicked = useApp((s) => s.setPicked);
  const setView = useApp((s) => s.setView);
  const qc = useQueryClient();
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => { if (p) ref.current?.scrollIntoView({ block: "nearest", behavior: "smooth" }); }, [p]);
  if (!m || !p) return null;
  const frame = p.frame ? m.frames.find((f) => f.id === p.frame) : undefined;
  const stack = m.stacks.find((x) => x.bin === p.bin && x.band === p.band);
  const t = m.target;
  const fromTarget = t ? sepArcsec(p.ra, p.dec, t.propagated_now.ra, t.propagated_now.dec) : null;
  // known asteroids already fetched at this visit's epoch (overlay queries in the cache), to name the nearest one
  const binMjd = m.bins[String(p.band)]?.find((b) => b.id === p.bin)?.mjd_mean;
  const known = qc.getQueriesData<{ cat?: string; id: string; ra: number; dec: number }[]>({ queryKey: ["overlays"] })
    .filter(([k]) => binMjd !== undefined && k[4] === Math.round(binMjd))
    .flatMap(([, d]) => d ?? []).filter((x) => x.cat === "sso");
  const nearest = p.cat === "transient" && known.length
    ? known.map((k) => ({ k, d: sepArcsec(p.ra, p.dec, k.ra, k.dec) })).sort((a, b) => a.d - b.d)[0]! : null;
  const sameSpot = p.cat === "transient" ? (stack?.transients ?? []).filter((x) => x.frame !== p.frame && sepArcsec(p.ra, p.dec, x.ra, x.dec) < m.grid.pix_arcsec * 2).length : 0;
  return (
    <div ref={ref}>
      <Section title={p.cat === "sso" ? p.id : "Transient detection"} kicker={p.cat === "sso" ? "Known asteroid" : "Unvetted"} className="marker-card">
        <dl className="kv">
          <dt>position</dt><dd>{formatRA(p.ra)} {formatDec(p.dec)}</dd>
          <dt>visit</dt><dd>{p.bin}, band {p.band}</dd>
          {p.cat === "sso" && isNum(p.mag) && <><dt>V mag</dt><dd>{fix(p.mag, 1)}</dd></>}
          {frame && <><dt>exposure</dt><dd>{mjdToISODate(frame.mjd)} · <span className="mono" title={frame.id}>{frame.id.replace(/\.fits$/, "")}</span></dd></>}
          {p.cat === "transient" && isNum(p.npix) && <><dt>size</dt><dd>{p.npix} px rejected</dd></>}
          {p.cat === "transient" && <><dt>same spot</dt><dd>{sameSpot} other exposure{sameSpot === 1 ? "" : "s"} of this visit</dd></>}
          {nearest && <><dt>nearest known</dt><dd>{nearest.k.id}, {nearest.d < 60 ? `${nearest.d.toFixed(1)}″` : `${(nearest.d / 60).toFixed(1)}′`} away</dd></>}
          {fromTarget !== null && <><dt>from target</dt><dd>{fromTarget < 60 ? `${fromTarget.toFixed(1)}″` : `${(fromTarget / 60).toFixed(2)}′`}</dd></>}
        </dl>
        <p className="small hint">{p.cat === "sso"
          ? "Position from JPL Horizons as seen from SPHEREx at this visit's mean time (bodies found with IMCCE SkyBoT, V ≤ 19)."
          : "Pixels rejected as a single-exposure outlier while stacking this visit. It may be an asteroid, a cosmic ray or a detector artefact: nothing here is vetted. A real asteroid usually appears at a shifted position in neighbouring exposures."}</p>
        <div className="row">
          <button onClick={() => setView({ sel: `${p.ra.toFixed(5)},${p.dec.toFixed(5)}` })} title="Select this position for the spectrum, light curve and candidate report">Select this position</button>
          <button className="link" onClick={() => setPicked(null)}>Close</button>
        </div>
      </Section>
    </div>
  );
}

export function MissionCard() {
  const lang = useLang();
  const m = useApp((s) => s.manifest);
  const rel = useApp((s) => s.release);
  const t = m?.target;
  const mission = t ? missionFor([t.name, t.main_id ?? "", t.query, t.epoch_hint?.object ?? ""]) : null;
  if (!mission) return null;
  const text = missionText(mission, lang);
  const look = text.look.filter((_, i) => { const cap = mission.lookNeeds?.[i]; return !cap || feature(rel, cap).enabled; });
  return (
    <Section title={text.title} kicker="Mission" className="mission-card">
      <p className="mission-hook">{text.hook}</p>
      <ol className="look">{look.map((l) => <li key={l}>{l}</li>)}</ol>
    </Section>
  );
}

export function WarningsCard() {
  const m = useApp((s) => s.manifest);
  const jw = useApp((s) => s.jobWarnings);
  const items = [...(m?.warnings ?? []).map((w) => w.message), ...jw];
  if (!items.length) return null;
  return (
    <Section title={`Notes (${items.length})`} open={items.length < 4}>
      <ul className="warnings">{items.map((w, i) => <li key={i}>{w}</li>)}</ul>
    </Section>
  );
}

/** Heavy measurements (hundreds of native-frame fits; minutes on a cold laptop) start on request, not on page load. */
function useRunOnce(key: string | undefined): [boolean, () => void] {
  const [k, setK] = useState<string | null>(null);
  return [!!key && k === key, () => setK(key ?? null)];
}

/** Decision 0007 measured the archive VARIANCE plane 10–28 % low in detectors 1–4, and no production path rescales it
 *  yet (F5 is open). Every error derived from it is that much too small, so say so next to them (audit V-02). */
export function VarianceNote() {
  return <p className="small hint">Error bars use the archive's VARIANCE plane, which our noise check found 10–28 % low in
    bands 1–4 (decision 0007): uncertainties in those bands are about 5–15 % too small until that is calibrated.</p>;
}

function RunButton({ onClick, what }: { onClick: () => void; what: string }) {
  return <p className="run"><button onClick={onClick}>Measure {what}</button> <span className="small hint">fits every native frame; the first run can take minutes, then it is cached with the view</span></p>;
}

/** Width of charts in an expanded dialog (SVG user units; the side panel's charts are 380). */
const BIG_W = 900;

/** "expand" button and wide dialog, as in the spectrum panel: the same content, larger. */
export function Expandable({ title, children }: { title: string; children: React.ReactNode }) {
  const [open, setOpen] = useState(false);
  return (
    <>
      <div className="row expand-row">
        <button onClick={() => setOpen(true)} title={`Open a large view of the ${title.toLowerCase()}`}><Icon name="expand" size={12} />expand</button>
      </div>
      {open && <Modal title={title} onClose={() => setOpen(false)} wide><ErrorBoundary label={title}>{children}</ErrorBoundary></Modal>}
    </>
  );
}

export function AstrometryCard() {
  const m = useApp((s) => s.manifest);
  const f = useFeature("astrometry");
  const t = m?.target;
  const [run, start] = useRunOnce(m?.key);
  const q = useQuery({
    queryKey: ["astrometry", t?.name, m?.key],
    enabled: f.enabled && t?.kind === "star" && run,
    queryFn: () => api.astrometry(t!.propagated_now.ra, t!.propagated_now.dec, t!.name, m?.key),
  });
  if (!f.enabled || t?.kind !== "star") return null;
  const d = q.data;
  const badge = (f.unvalidated || d?.validity === "unvalidated") ? <UnvalidatedBadge /> : null;
  return (
    <Section title="Astrometry" badge={badge}>
      {!run && <RunButton onClick={start} what="proper motion" />}
      {q.isLoading && <p role="status">Fitting positions…</p>}
      {q.isError && <p className="error">Astrometry failed: {(q.error as Error).message}</p>}
      {d?.fit && (
        <>
          <table className="compare">
            <thead><tr><th></th><th>fitted (SPHEREx)</th><th>catalogue</th></tr></thead>
            <tbody>
              <tr><th>μ</th><td>{fix(d.fit.mu)} ± {fix(d.fit.e_mu)}″/yr</td><td>{d.catalogue ? `${fix(d.catalogue.mu)}″/yr` : "—"}</td></tr>
              <tr><th>PA</th><td>{fix(d.fit.pa_deg, 0)}°</td><td>{d.catalogue ? `${fix(d.catalogue.pa_deg, 0)}°` : "—"}</td></tr>
            </tbody>
          </table>
          <p className="small">Parallax {isNum(d.fit.plx_fixed) ? `fixed at the catalogue ${fix(d.fit.plx_fixed, 1)} mas` : "fitted"};
            motion significance Δχ² = {fix(d.fit.delta_chi2, 0)} (moving vs stationary).{d.catalogue ? ` Catalogue: ${d.catalogue.source}.` : ""}
            {d.fit.dof > 0 && d.fit.chi2 / d.fit.dof > 1 && ` Fit χ² ${fix(d.fit.chi2, 0)} / ${d.fit.dof}: the per-frame errors are too small, so the quoted uncertainty is scaled up by √(χ²/dof) = ${fix(Math.sqrt(d.fit.chi2 / d.fit.dof), 1)}.`}</p>
        </>
      )}
      {d && d.points.length > 0 && (() => {
        const chart = (height: number, width?: number) => (
          <ScatterChart label="Tangent-plane positions measured from native pixels" xLabel="−ξ (″): west →, east ← (as in the viewer)" yLabel="η (″, north +)"
            points={d.points.map((p) => ({ x: -p.xi, y: p.eta, ex: p.s_xi, ey: p.s_eta, series: p.visit, title: `${p.visit} ${mjdToISODate(p.mjd)}` }))}
            height={height} width={width} clipErrors />
        );
        return (
          <>
            {chart(200)}
            <Expandable title="Astrometry">
              {chart(560, BIG_W)}
              <p className="small hint">One marker per native frame, coloured and shaped by visit; error bars are 1σ, cut at the plot edge so one poorly fitted frame cannot squash the rest. Hover a point for its visit and date.</p>
            </Expandable>
          </>
        );
      })()}
      {d && <p className="small hint">{d.tangent_origin ? `Tangent origin: ${formatRA(d.tangent_origin[0]!)} ${formatDec(d.tangent_origin[1]!)}` : "Offsets from the first visit"}; east is to the left. {d.skipped?.length ?? 0} frames excluded; full visits enter the motion fit.</p>}
      {d?.notes?.map((note) => <p className="small hint" key={note}>{note}</p>)}
      {d && <VarianceNote />}
    </Section>
  );
}

export function SpectrumPanel() {
  const m = useApp((s) => s.manifest);
  const view = useApp((s) => s.view);
  const setView = useApp((s) => s.setView);
  const f = useFeature("spectrum");
  const [showBad, setShowBad] = useState(false);
  const [logX, setLogX] = useState(false);
  const [mag, setMag] = useState(false);
  const [table, setTable] = useState(false);
  const [templateIndex, setTemplateIndex] = useState(-1);
  const [yAll, setYAll] = useState(false);
  const [points, setPoints] = useState(true);
  const [expanded, setExpanded] = useState(false);
  const sel = view.sel?.split(",").map(Number) as [number, number] | undefined;
  const pos = sel ?? (m?.target ? [m.target.propagated_now.ra, m.target.propagated_now.dec] as [number, number] : undefined);
  const [run, start] = useRunOnce(m ? `${m.key}|${view.sel ?? ""}` : undefined);
  const q = useQuery({
    queryKey: ["spectrum", pos?.[0], pos?.[1], view.center, m?.key, !!sel],
    enabled: f.enabled && !!pos && run,
    queryFn: () => api.spectrum(pos![0], pos![1], !sel || view.center === "track", m?.key),
  });
  // A failed fit arrives with null numbers (NaN on the server): never plot or tabulate those, count them (F-16).
  const all = useMemo(() => q.data?.rows ?? [], [q.data]);
  const rows = useMemo(() => all.filter((r) => isNum(r.lam) && isNum(r.flux) && isNum(r.err)), [all]);
  const unmeasured = all.length - rows.length;
  const hidden = rows.filter((r) => r.contaminated);
  const shown = showBad ? rows : rows.filter((r) => !r.contaminated);
  const overlay = q.data?.templates?.[templateIndex];
  if (!f.enabled) return null;
  const badge = (f.unvalidated || q.data?.validity === "unvalidated") ? <UnvalidatedBadge /> : null;
  const releases = [...new Set(shown.map((r) => releaseOf(r).toUpperCase()))].sort();
  const chart = (height: number, big = false) => (
    <SpectrumChart rows={shown} mag={mag} logX={logX} height={height} yMode={yAll ? "all" : "robust"} showPoints={points}
      template={overlay?.samples?.map((p) => ({ lam: p.lam, flux: p.flux }))} templateLabel={overlay ? `${overlay.spectral_type} template` : undefined}
      features={FEATURES} label={`Spectrum${big ? " (expanded)" : ""}: flux against wavelength, binned per release`} />
  );
  const controls = (
    <div className="row chart-controls">
      <label className="check"><input type="checkbox" checked={logX} onChange={(e) => setLogX(e.target.checked)} /> log λ</label>
      <label className="check"><input type="checkbox" checked={mag} onChange={(e) => setMag(e.target.checked)} /> AB mag</label>
      <label className="check" title="Robust: the y-range follows the binned spectrum and ignores a few wild points. All: every point and error bar."><input type="checkbox" checked={yAll} onChange={(e) => setYAll(e.target.checked)} /> full y-range</label>
      <label className="check"><input type="checkbox" checked={points} onChange={(e) => setPoints(e.target.checked)} /> frames</label>
      <label className="check"><input type="checkbox" checked={showBad} onChange={(e) => setShowBad(e.target.checked)} /> show contaminated ({hidden.length})</label>
    </div>
  );
  const methane = q.data?.indices?.methane_rel;
  return (
    <Section title="Spectrum" badge={badge}>
      <p className="small">{sel ? `Clicked position ${formatRA(sel[0])} ${formatDec(sel[1])}` : "At the target's predicted position."}
        {sel && <> <button className="link" onClick={() => setView({ sel: null })}>back to target</button></>}
        {!sel && " Click any source in the viewer to measure it."}</p>
      {!run && <RunButton onClick={start} what="spectrum" />}
      {q.isLoading && <p role="status">Measuring the spectrum in every frame…</p>}
      {q.isError && <p className="error">Spectrum failed: {(q.error as Error).message}</p>}
      {rows.length > 0 && (
        <>
          {controls}
          <div className="row">
            <label className="check"><input type="checkbox" checked={table} onChange={(e) => setTable(e.target.checked)} /> table</label>
            <button onClick={() => playSpectrum(shown)} title="Pitch follows wavelength, loudness follows flux (≈2 s)"><Icon name="play" size={12} />hear spectrum</button>
            <button onClick={() => setExpanded(true)} title="Open a large, interactive view of this spectrum"><Icon name="expand" size={12} />expand</button>
          </div>
          {!!q.data?.templates?.length && <label>Spectral template <select value={templateIndex} onChange={(e) => setTemplateIndex(Number(e.target.value))}><option value={-1}>None</option>{q.data.templates.map((t, i) => <option key={i} value={i}>{t.spectral_type}: {t.visit} / {t.release}</option>)}</select></label>}
          {overlay && <p className="small">{overlay.label} Scaled separately for {overlay.visit}/{overlay.release}; chi-square {fix(overlay.chi2, 1)} / {overlay.dof} degrees of freedom. {overlay.provenance?.note} {overlay.provenance?.url && <a href={overlay.provenance.url} target="_blank" rel="noreferrer">Template source</a>}</p>}
          {chart(280)}
          <p className="small hint">{shown.length} frame measurements, binned per release{releases.length > 1 ? ` (${releases.join(" and ")} separately: not on a common photometric scale until F4)` : ""}: σ-clipped
            inverse-variance mean per ln-λ bin, error widened by √χ²ᵣ where frames scatter more than their errors. Hover a bin for details.</p>
          {expanded && (
            <Modal title="Spectrum" onClose={() => setExpanded(false)} wide>
              {controls}
              {chart(Math.min(560, Math.max(360, Math.round((typeof window !== "undefined" ? window.innerHeight : 800) * 0.55))), true)}
              <p className="small hint">{sel ? `Clicked position ${formatRA(sel[0])} ${formatDec(sel[1])}.` : "Target's predicted position."} Shaded columns are the six
                SPHEREx detectors; dashed lines mark contaminants (He 1.083 µm airglow). Carets count measurements outside the robust y-range.</p>
            </Modal>
          )}
          {unmeasured > 0 && <p className="small hint">{unmeasured} frame{unmeasured > 1 ? "s" : ""} without a finite flux (fit failed) left out.</p>}
          {!showBad && hidden.length > 0 && hidden.length < rows.length && <p className="small hint">{hidden.length} point{hidden.length > 1 ? "s" : ""} hidden (He 1.083 µm airglow or flagged pixels).</p>}
          {!showBad && rows.length > 0 && hidden.length === rows.length && (
            <p className="notice small" role="note">All {rows.length} points carry saturation or artefact flags near the star (a very bright
              target such as R Dra overflows in every band), so none is trusted for a spectrum. Tick “show contaminated” to see them
              anyway; for bright variables use the light curve, which measures same-channel annulus ratios instead.</p>
          )}
          {typeof methane === "number" && Number.isFinite(methane) && (
            <div className="meter" role="meter" aria-valuemin={0} aria-valuemax={1.5} aria-valuenow={methane} aria-label="Methane index relative to field stars">
              <span>methane index vs field stars</span>
              <div className="meter-bar"><div style={{ width: `${Math.min(100, Math.max(0, (methane / 1.5) * 100))}%` }} /></div>
              <span>{methane.toFixed(2)} {methane < 0.5 ? "— strong methane: T/Y-dwarf-like (cold)" : "— no strong methane"}</span>
            </div>
          )}
          {table && (
            <table className="data">
              <thead><tr><th>visit</th><th>λ µm</th><th>Δλ</th><th>flux µJy</th><th>σ</th><th>det</th><th>χ²ᵣ</th><th>notes</th></tr></thead>
              <tbody>{shown.map((r, i) => (
                <tr key={i}><td>{r.visit}</td><td>{fix(r.lam, 4)}</td><td>{fix(r.dlam, 4)}</td><td>{prec(r.flux, 4)}</td><td>{prec(r.err, 3)}</td>
                  <td>D{r.detector}</td><td>{fix(r.rchi2)}</td><td>{[r.contaminated && "He", ...r.flags].filter(Boolean).join(" ")}</td></tr>
              ))}</tbody>
            </table>
          )}
          {q.data?.notes.map((n) => <p key={n} className="small hint">{n}</p>)}
          <VarianceNote />
        </>
      )}
    </Section>
  );
}

/** The release with more frames in this view: the light curve's default scale (audit F-24; QR2 and QR3 are never
 *  mixed photometrically, so a QR3-only field used to answer 409 until the menu was changed). */
export function majorityRelease(frames: { release: string }[] | undefined): "qr2" | "qr3" {
  let n2 = 0, n3 = 0;
  for (const f of frames ?? []) { if (f.release === "qr2") n2++; else if (f.release === "qr3") n3++; }
  return n3 > n2 ? "qr3" : "qr2";
}

export function LightCurvePanel() {
  const m = useApp((s) => s.manifest);
  const view = useApp((s) => s.view);
  const f = useFeature("lightcurve");
  const t = m?.target;
  const [chosen, setRelease] = useState<string | null>(null);
  const release = chosen ?? majorityRelease(m?.frames);
  // Offered for any position (audit F-23): open by default for a catalogued variable or a binned axis, collapsed
  // otherwise, so "is this new source variable?" can be asked of whatever was clicked.
  const variable = !!t && (VARIABLE_OTYPE.test(t.otype ?? "") || !!m?.axis.startsWith("bin"));
  const sel = view.sel?.split(",").map(Number) as [number, number] | undefined;
  const pos = sel ?? (t ? [t.propagated_now.ra, t.propagated_now.dec] as [number, number] : undefined);
  const [run, start] = useRunOnce(m ? `${m.key}|${release}|${view.sel ?? ""}` : undefined);
  const q = useQuery({
    queryKey: ["lightcurve", pos?.[0], pos?.[1], m?.key, release],
    enabled: f.enabled && !!pos && run,
    queryFn: () => api.lightcurve(pos![0], pos![1], (m!.params.mask_resolved ?? m!.params.mask) === "bright" ? "annulus" : "psf", m?.key, release),
  });
  if (!f.enabled || !pos) return null;
  const d = q.data;
  return (
    <Section title="Light curve" badge={(f.unvalidated || d?.validity === "unvalidated") ? <UnvalidatedBadge /> : null} open={variable && !sel}>
      <p className="small">{sel ? `Clicked position ${formatRA(sel[0])} ${formatDec(sel[1])}.` : "At the target's predicted position."}</p>
      <label>Photometric release <select value={release} onChange={(e) => setRelease(e.target.value)}><option value="qr2">QR2</option><option value="qr3">QR3</option></select></label>
      {!run && <RunButton onClick={start} what="light curve" />}
      {d?.uncertainty && <p className="small">{d.uncertainty}</p>}
      {q.isLoading && <p role="status">Building the light curve…</p>}
      {q.isError && <p className="error">Light curve failed: {(q.error as Error).message}</p>}
      {d && (() => {
        const charts = (w?: number) => {
          const k = w ? 1.8 : 1;   // taller in the expanded dialog
          return (
            <>
              <ScatterChart label="Relative flux against time, one marker per band" xLabel="MJD" yLabel="relative flux" height={220 * k} width={w}
                points={Object.entries(d.bands).flatMap(([b, pts]) => pts.map((p) => ({ x: p.mjd, y: p.rel, ey: p.err, series: `band ${b}`, title: `${p.bin} ${mjdToISODate(p.mjd)}` })))} />
              {d.periodogram && (
                <>
                  <ScatterChart label="Periodogram" xLabel="period (days)" yLabel="power" height={160 * k} width={w}
                    points={[]} line={d.periodogram.period_days.map((p, i) => ({ x: p, y: d.periodogram!.power[i]! }))}
                    vlines={[{ x: d.periodogram.best_days, label: `best ${fix(d.periodogram.best_days, 0)} d` }]} />
                  <p className="small">{d.periodogram.fap == null ? 'False-alarm probability unavailable: correlated reference errors.' : 'False-alarm probability ' + expo(d.periodogram.fap) + '.'}</p>
                  {d.periodogram.method && <p className="small">{d.periodogram.method}; {d.periodogram.fap_trials} noise trials. Values are limited by the simulated tail resolution.</p>}
                  <ScatterChart label="Phase-folded relative light curve" xLabel="phase" yLabel="relative flux" height={220 * k} width={w}
                    points={Object.entries(d.bands).flatMap(([b, pts]) => pts.map((p) => ({x: ((p.mjd / d.periodogram!.best_days) % 1 + 1) % 1, y: p.rel, ey: p.err, series: `band ${b}`, title: `${p.bin} ${mjdToISODate(p.mjd)}`})))} />
                </>
              )}
            </>
          );
        };
        return (
          <>
            <p className="small">{d.label} · method: {d.method === "annulus" ? "same-channel annulus ratios" : "PSF photometry, spectrally normalised"}</p>
            {charts()}
            <Expandable title="Light curve">
              <p className="small">{sel ? `Clicked position ${formatRA(sel[0])} ${formatDec(sel[1])}` : "Target's predicted position"} · {release.toUpperCase()} scale · {d.label}</p>
              {charts(BIG_W)}
            </Expandable>
          </>
        );
      })()}
    </Section>
  );
}

export function FrameInspector() {
  const m = useApp((s) => s.manifest);
  const cur = useCurrent();
  if (!m || !cur.bin) return null;
  const frames = m.frames.filter((f) => f.bin === cur.bin!.id && f.band === cur.band).sort((a, b) => a.mjd - b.mjd);
  const skipped = frames.filter((f) => f.skipped);
  const title = `Frames: ${cur.bin.id}, band ${cur.band} (${frames.length})`;
  const table = (
      <table className="data frames">
        <thead><tr><th>date (UTC)</th><th>survey</th><th>release</th><th>QA</th><th>file</th></tr></thead>
        <tbody>
          {frames.map((f) => {
            const qaFail = f.qa.L1DQAFLG === "Fail" || f.qa.L2DQAFLG === "Fail" || (f.qa.FINAST !== undefined && f.qa.FINAST !== 0);
            return (
              <tr key={f.id} className={f.skipped ? "skipped" : ""}>
                <td>{mjdToISODate(f.mjd)}</td>
                <td title={f.survey === null && f.mjd >= SCIENCE_START_MJD ? "survey not read yet (frame not stacked, or skipped before calibration)" : undefined}>
                  {f.survey !== null && f.survey > 0 ? `S${f.survey}` : f.mjd < SCIENCE_START_MJD ? "IOC" : "—"}</td>
                <td>{f.release.toUpperCase()} <small>{f.pipeline}</small></td>
                <td><span className={`badge ${qaFail ? "warn" : "ok"}`} title={`L1DQAFLG=${f.qa.L1DQAFLG ?? "?"} L2DQAFLG=${f.qa.L2DQAFLG ?? "?"} FINAST=${f.qa.FINAST ?? "?"}`}>{qaFail ? "QA fail" : "QA pass"}</span></td>
                <td className="mono" title={f.id}>{f.skipped ? <>skipped: {f.skipped}</> : f.id.replace(/\.fits$/, "")}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
  );
  return (
    <Section title={title} open={false}
      badge={skipped.length ? <span className="badge warn">{skipped.length} skipped</span> : null}>
      {frames.length > 0 && <Expandable title={title}>{table}</Expandable>}
      {table}
    </Section>
  );
}

export function SkyContextSection() {
  const f = useFeature("aladin");
  const [open, setOpen] = useState(false);
  if (!f.enabled) return null;
  return (
    <details className="card" onToggle={(e) => setOpen((e.target as HTMLDetailsElement).open)}>
      <summary><h2>Sky context (Aladin Lite)</h2>{f.unvalidated && <UnvalidatedBadge />}</summary>
      <div className="card-body">
        {open ? <Suspense fallback={<p role="status">Loading Aladin Lite…</p>}><SkyContext /></Suspense> : <p className="hint">Open to load the sky atlas.</p>}
      </div>
    </details>
  );
}

export function MoversPanel() {
  const m = useApp((s) => s.manifest);
  const stellar = useFeature("movers");
  const planet = useFeature("planetx");
  const [mode, setMode] = useState<"stellar" | "planetx">("stellar");
  const [muMax, setMuMax] = useState(10);
  const [run, setRun] = useState("");
  const enabled = mode === "planetx" ? planet.enabled : stellar.enabled;
  const validView = mode === "stellar" || (!!m?.axis.startsWith("bin:1d") && Number(m.params.fov) >= 30);
  const validSpeed = Number.isFinite(muMax) && muMax > 0 && muMax <= 1000;
  const targetMu = m?.target?.kind === "star" && m.target.pm ? Math.hypot(m.target.pm[0], m.target.pm[1]) / 1000 : null;
  const q = useQuery({queryKey: ["movers", m?.key, mode, muMax], enabled: enabled && validView && validSpeed && !!m && run === `${m.key}|${mode}|${muMax}`, retry: false, queryFn: () => api.movers(m!.key, mode, muMax)});
  if (!stellar.enabled && !planet.enabled) return null;
  return <Section title="Mover candidates" badge={<UnvalidatedBadge />} open={false}>
    <p className="small">Candidates require independent follow-up. Image recovery, completeness and false-positive rates remain unvalidated.</p>
    <label>Search mode <select value={mode} onChange={(e) => setMode(e.target.value as "stellar" | "planetx")}><option value="stellar" disabled={!stellar.enabled}>Stellar motion</option><option value="planetx" disabled={!planet.enabled}>Distant-body parallax</option></select></label>
    {!validView && <p className="hint">Distant-body linking needs daily bins and a field of at least 30 arcminutes.</p>}
    {mode === "stellar" && <label>Maximum motion (arcsec/year) <input type="number" min="0.1" max="1000" step="1" value={muMax} onChange={(e) => setMuMax(Number(e.target.value))} /></label>}
    {mode === "stellar" && targetMu !== null && validSpeed && targetMu > muMax && (
      <p className="hint small">{displayName(m!.target!)} moves {targetMu.toFixed(2)}″/yr (catalogue), faster than this limit: visits farther apart
        than the limit allows (beyond the 1.5-pixel minimum link radius) are not linked.{" "}
        <button className="link" onClick={() => setMuMax(Math.ceil(targetMu * 1.2))}>Use {Math.ceil(targetMu * 1.2)}″/yr</button></p>
    )}
    <button disabled={!enabled || !validView || !validSpeed || !m || q.isFetching} onClick={() => setRun(`${m!.key}|${mode}|${muMax}`)}>Find candidates</button>
    {q.isFetching && <p role="status">Measuring native frames and checking catalogues… The first search of a view fits every
      detection in every native frame and can take several minutes; later searches with another limit or mode reuse it.</p>}
    {q.isError && <p className="error">Search failed: {(q.error as Error).message}</p>}
    {q.data && <><p>{q.data.candidates.length} vetted candidate chains; {q.data.orphans?.length ?? 0} single-bin detections queued for exposure-level asteroid/parallax vetting.</p>
      <ul>{q.data.candidates.map((c) => <li key={c.id}>{c.known ?? "Unmatched candidate"}: {formatRA(c.ra)} {formatDec(c.dec)}; {c.distance_au != null ? `${fix(c.distance_au, 1)} ± ${fix(c.distance_error_au, 1)} AU (approximate)` : `${fix(c.pm_arcsec_yr)}″/yr`}; {c.visits.join(", ")}</li>)}</ul>
      {!!q.data.skipped?.length && (
        <details className="small">
          <summary>{q.data.skipped.length} chain{q.data.skipped.length === 1 ? "" : "s"} or input{q.data.skipped.length === 1 ? "" : "s"} excluded</summary>
          <ul>{q.data.skipped.slice(0, 20).map(([id, why], i) => <li key={i} title={id}>{why}</li>)}</ul>
          {q.data.skipped.length > 20 && <p className="hint">… and {q.data.skipped.length - 20} more in the API response.</p>}
        </details>
      )}
    </>}
  </Section>;
}


/** Exports (P2-7, implementation.md §5.1): server-rendered with the SHARED stretch of the band. */
export function ExportSection() {
  const m = useApp((s) => s.manifest);
  const view = useApp((s) => s.view);
  const cur = useCurrent();
  const f = useFeature("export");
  if (!f.enabled || !m) return null;
  const bins = cur.bins.filter((b) => cur.isReady(b.id)).map((b) => b.id);
  const o = { key: m.key, band: cur.band, bins, stretch: view.stretch, cmap: view.cmap, fps: view.fps };
  const items: { fmt: "gif" | "apng" | "fits" | "csv"; label: string; hint: string }[] = [
    { fmt: "gif", label: "Animated GIF", hint: "the blink, labelled, shared stretch" },
    { fmt: "apng", label: "Animated PNG", hint: "lossless blink" },
    { fmt: "fits", label: "FITS stacks", hint: "science values (NaN = no data) with the grid WCS" },
    { fmt: "csv", label: "Frame list (CSV)", hint: "every frame, QA and skipped reason" },
  ];
  return (
    <Section title="Export" badge={f.unvalidated ? <UnvalidatedBadge /> : undefined} open={false}>
      <p className="small">Band {cur.band}, {bins.length} {m.axis === "visit" ? "visit" : "bin"} stack(s) ready{view.partial ? " (partials included)" : ""}.</p>
      <ul className="exports">
        {items.map((x) => (
          <li key={x.fmt}>
            {bins.length ? <a href={api.exportURL(x.fmt, o)} download>{x.label}</a> : <span aria-disabled="true">{x.label}</span>}
            <span className="hint"> — {x.hint}</span>
          </li>
        ))}
      </ul>
    </Section>
  );
}

/** Solar System track mode (P2-10, implementation.md §4.11): Horizons positions as seen from SPHEREx at
 * each bin's mean MJD, and how far the view's own track point sits from them. */
export function SolarSystemCard() {
  const m = useApp((s) => s.manifest);
  const view = useApp((s) => s.view);
  const setView = useApp((s) => s.setView);
  const cur = useCurrent();
  const f = useFeature("sso");
  const t = m?.target;
  const isSso = t?.kind === "sso";
  const mjds = cur.allBins.map((b) => b.mjd_mean);
  const q = useQuery({
    queryKey: ["sso", t?.name, mjds.join(",")],
    enabled: f.enabled && isSso && mjds.length > 0,
    retry: false,
    queryFn: () => api.sso(t!.name, mjds),
  });
  if (!f.enabled || !isSso || !m) return null;
  return (
    <Section title="Solar System track" badge={f.unvalidated ? <UnvalidatedBadge /> : undefined}>
      <p className="small">Positions from JPL Horizons as seen from SPHEREx{q.data ? ` (observer ${q.data.observer})` : ""}. Track mode centres each
        frame on the body, so it stays still while the stars stream past.</p>
      <label className="check"><input type="checkbox" checked={view.center === "track"}
        onChange={(e) => setView({ center: e.target.checked ? "track" : "fixed" })} /> track the body (center=track)</label>
      {q.isFetching && <p role="status">Asking Horizons…</p>}
      {q.isError && <p className="error">Ephemeris unavailable: {(q.error as Error).message}</p>}
      {q.data && (
        <table className="small">
          <thead><tr><th>bin</th><th>date</th><th>RA, Dec (Horizons)</th><th>view track Δ</th></tr></thead>
          <tbody>{q.data.points.map((p, k) => {
            const b = cur.allBins[k];
            const tp = m.track.find((x) => x.bin === b?.id && x.band === cur.band);
            return (
              <tr key={k}>
                <td>{b?.id}</td><td>{mjdToISODate(p.mjd)}</td><td>{formatRA(p.ra)} {formatDec(p.dec)}</td>
                <td>{tp ? `${sepArcsec(p.ra, p.dec, tp.ra, tp.dec).toFixed(2)}″` : "—"}</td>
              </tr>
            );
          })}</tbody>
        </table>
      )}
    </Section>
  );
}

export function SidePanel() {
  const ui = useApp((s) => s.view.ui);
  return (
    <aside className="side-panel" aria-label="Details">
      <TargetCard />
      <MarkerCard />
      {ui !== "expert" && <MissionCard />}
      <WarningsCard />
      <AstrometryCard />
      <SpectrumPanel />
      <LightCurvePanel />
      <MoversPanel />
      <SolarSystemCard />
      {ui !== "simple" && <Blink25Panel />}
      {ui !== "simple" && <ExportSection />}
      {ui !== "simple" && <FrameInspector />}
      {ui !== "simple" && <SkyContextSection />}
      <ElsewhereCard />
    </aside>
  );
}
