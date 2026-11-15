/** Status badges and banners (workflow.md §7.2, §9.6; implementation.md §9). */
import { getTransport } from "../api/client";
import { useApp } from "../state/store";
import { useFeature } from "../hooks/useCurrent";
import { Icon } from "./Icon";

/** The full, server-backed tool, when this build is the static copy and names one (VITE_LIVE_URL). */
export const LIVE_URL: string | undefined = import.meta.env.VITE_LIVE_URL || undefined;

/** Release decision (owner, 2026-11-15): every built capability ships without a status badge. The API still reports
 *  each result's `validity`, and the /proof page states what each check has and has not shown. */
export function UnvalidatedBadge(): null {
  return null;
}

export function DataSourceBanner() {
  const m = useApp((s) => s.manifest);
  const rel = useApp((s) => s.release);
  const mock = m?.data_source === "mock" || rel?.environment === "mock";
  const snap = m?.data_source === "snapshot" || rel?.snapshot;
  // ParallaX Lite: the recorded pinned views as static files. LIVE_URL, when the build names one, is the full tool.
  if (getTransport().kind === "lite") return (
    <div className="banner snapshot" role="note"><Icon name="info" size={16} className="banner-icon" />
      <span className="banner-text">Frozen copy: real SPHEREx data for the targets on the home page, recorded from the ParallaX server.
        {LIVE_URL ? <> For any other coordinates, <a href={LIVE_URL}>open the live tool</a>.</> : " It cannot build other coordinates."}</span></div>
  );
  if (mock) return <div className="banner mock" role="note"><strong>MOCK DATA</strong> — synthetic images for development. Never use in a demo.</div>;
  if (snap) return <div className="banner snapshot" role="note"><Icon name="info" size={16} className="banner-icon" /><span className="banner-text">Cached demo data (offline snapshot).</span></div>;
  return null;
}

export function ReloadBanner() {
  const mismatch = useApp((s) => s.schemaMismatch);
  if (!mismatch) return null;
  return (
    <div className="banner reload" role="alert">
      <Icon name="alert" size={16} className="banner-icon" />
      <span className="banner-text">ParallaX was updated. Reload to keep the view correct.</span>
      <span className="banner-actions"><button className="primary" onClick={() => location.reload()}>Please reload</button></span>
    </div>
  );
}

export function NewerDataBanner() {
  const m = useApp((s) => s.manifest);
  const setView = useApp((s) => s.setView);
  // The frozen copy holds only the pinned views, so it cannot offer the newer frame list.
  if (!m?.newer_pin || getTransport().kind === "lite") return null;
  return (
    <div className="banner newer" role="note">
      <Icon name="info" size={16} className="banner-icon" />
      <span className="banner-text">This pinned link shows a frozen frame list. Newer data is available.</span>
      <span className="banner-actions"><button onClick={() => setView({ pin: null }, { push: true })}>Update to the latest</button></span>
    </div>
  );
}

/** " Checked <local time>." or "" when the server has never checked ("never") or sent no date (audit F-29). */
function checked(at: string | undefined): string {
  const t = at ? Date.parse(at) : NaN;
  return Number.isFinite(t) ? ` Checked ${new Date(t).toLocaleString()}.` : "";
}

export function FreshnessBadge() {
  const rel = useApp((s) => s.release);
  const f = useFeature("freshness");
  if (!rel || !f.enabled) return null;
  const rs = Object.entries(rel.release_state).map(([k, v]) => `${k.toUpperCase()} ${v}`).join(" · ");
  return (
    <span className="badge fresh" title={rel.newest_period
      ? `Newest SPHEREx planning period ingested: ${rel.newest_period}.${checked(rel.checked_at)}`
      : "The release watcher has not listed the archive yet on this server."}>
      {rel.newest_period ? <>data to <b>{rel.newest_period.replace(/_.*/, "")}</b></> : "data period unknown"}{f.unvalidated && <i> · unvalidated</i>}
      <span className="sr-only"> ({rs})</span>
    </span>
  );
}
