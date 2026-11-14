/**
 * App shell (implementation.md §6.1–6.2). Routes: "/" app, "/embed" minimal viewer, "/about"
 * credits page, "/proof" evidence page, "/f14" orientation check. The URL is the state (P0-5): parsed on load and on
 * back/forward, written back canonically on every change.
 */
import { useEffect } from "react";
import { QueryClient, QueryClientProvider, useQuery } from "@tanstack/react-query";
import { api, ApiError } from "./api/client";
import { href, routePath } from "./lib/base";
import { displayName } from "./lib/names";
import { feature } from "./lib/features";
import { indexOfBin, stepFrame } from "./lib/player";
import { useViewLoader } from "./hooks/useViewLoader";
import { playableFor, selectBands } from "./hooks/useCurrent";
import { useApp, takePendingPush } from "./state/store";
import { parseURL, toSearch } from "./state/url";
import { DataSourceBanner, NewerDataBanner, ReloadBanner } from "./components/Badges";
import { AboutPage, HelpDialog, ReportDialog, ShareDialog } from "./components/Dialogs";
import { EmbedApp } from "./components/EmbedApp";
import { F14Page } from "./components/F14Page";
import { Home } from "./components/Home";
import { PlayerControls } from "./components/PlayerControls";
import { ProofPage } from "./components/ProofPage";
import { SidePanel } from "./components/SidePanel";
import { Brand, EpochBanner, Progress, TargetBar } from "./components/TargetBar";
import { Timeline } from "./components/Timeline";
import { Viewer } from "./components/Viewer";
import { FLIP_KEY } from "./components/Flipbook";
import { Icon } from "./components/Icon";
import { ErrorBoundary } from "./components/ErrorBoundary";

/** One retry for network or server trouble; never for a refusal (4xx: off, unknown, not possible, rate-limited), which
 *  would only repeat the same answer, or repeat minutes of measurement work (audit F-08). */
export function retryOnce(failures: number, e: unknown): boolean {
  if (e instanceof ApiError && e.status >= 400 && e.status < 500) return false;
  return failures < 1;
}

export const queryClient = new QueryClient({ defaultOptions: { queries: { retry: retryOnce, staleTime: 5 * 60_000, refetchOnWindowFocus: false } } });

function readURL() {
  const { state, warnings } = parseURL(location.search);
  for (const w of warnings) console.warn(`[ParallaX] ${w}`);
  useApp.getState().replaceView(state);
}

/** URL ⇄ store. Target changes push a history entry; everything else replaces. */
function useURLSync() {
  useEffect(() => {
    readURL();
    const pop = () => { readURL(); useApp.setState({ frame: 0, transform: null }); };
    window.addEventListener("popstate", pop);
    const unsub = useApp.subscribe((s, prev) => {
      if (s.view === prev.view) return;
      const next = `${location.pathname}${toSearch(s.view)}`;
      if (next === `${location.pathname}${location.search}`) { takePendingPush(); return; }
      if (takePendingPush()) history.pushState(null, "", next); else history.replaceState(null, "", next);
    });
    return () => { window.removeEventListener("popstate", pop); unsub(); };
  }, []);
}

function useReleases() {
  const q = useQuery({ queryKey: ["releases"], queryFn: api.releases, refetchInterval: 10 * 60_000 });
  useEffect(() => { useApp.getState().setRelease(q.data ?? null); }, [q.data]);
}

/** When a manifest arrives, honour `t=` (the bin to show) from the URL once. */
function useInitialBin() {
  const m = useApp((s) => s.manifest);
  useEffect(() => {
    if (!m) return;
    const st = useApp.getState();
    const { bins } = playableFor(m, st.view);
    if (st.view.t) st.setFrame(indexOfBin(bins, st.view.t));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [m?.key]);
}

function useKeyboard() {
  useEffect(() => {
    const down = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement;
      if (t && (t.tagName === "INPUT" || t.tagName === "TEXTAREA" || t.tagName === "SELECT" || t.isContentEditable)) return;
      if (e.ctrlKey || e.metaKey || e.altKey) return;
      const st = useApp.getState();
      const m = st.manifest;
      const n = playableFor(m, st.view).bins.length;    // the same list the player and the counter use
      const k = e.key;
      // In the spectral flipbook, play/step keys drive the flipbook's own player (components/Flipbook.tsx).
      if (st.view.mode === "flip" && (k === " " || k === "ArrowLeft" || k === "ArrowRight")) {
        e.preventDefault();
        window.dispatchEvent(new CustomEvent(FLIP_KEY, { detail: k }));
        return;
      }
      if (k === " ") { e.preventDefault(); st.setPlaying(!st.playing); }
      else if (k === "ArrowRight" || k === "ArrowLeft") { e.preventDefault(); st.setPlaying(false); st.setFrame(stepFrame(st.frame, n, k === "ArrowRight" ? 1 : -1)); }
      else if (/^[1-6]$/.test(k)) { if (!m || m.bands.includes(Number(k))) selectBands(k); }
      else if (k === "b" || k === "B") { if (!e.repeat) st.setComparing(true); }
      else if (k === "o" || k === "O") st.setView({ mode: st.view.mode === "onion" ? "blink" : "onion" });
      else if (k === "s" || k === "S") st.setView({ mode: st.view.mode === "side" ? "blink" : "side" });
      else if (k === "d" || k === "D") { if (feature(st.release, "diff").enabled) st.setView({ mode: st.view.mode === "diff" ? "blink" : "diff" }); }
      else if (k === "f" || k === "F") { if (feature(st.release, "flip").enabled) st.setView({ mode: st.view.mode === "flip" ? "blink" : "flip" }); }
      else if (k === "+" || k === "=" || k === "-" || k === "0") {
        if (!m) return;
        const [ny, nx] = m.grid.shape;
        const v = st.transform ?? { cx: nx / 2, cy: ny / 2, zoom: 1 };
        const zoom = k === "0" ? 1 : Math.min(16, Math.max(1, v.zoom * (k === "-" ? 0.8 : 1.25)));
        st.setTransform(zoom === 1 ? null : { ...v, zoom });
      }
      else if (k === "?") st.setDialog("help");
      else if (k === "Escape") st.setDialog(null);
    };
    const up = (e: KeyboardEvent) => { if (e.key === "b" || e.key === "B") useApp.getState().setComparing(false); };
    window.addEventListener("keydown", down);
    window.addEventListener("keyup", up);
    return () => { window.removeEventListener("keydown", down); window.removeEventListener("keyup", up); };
  }, []);
}

function DialogHost() {
  const d = useApp((s) => s.dialog);
  const close = () => useApp.getState().setDialog(null);
  if (d === "share") return <ShareDialog onClose={close} />;
  if (d === "about") return <AboutPage onClose={close} />;
  if (d === "help") return <HelpDialog onClose={close} />;
  if (d === "report") return <ReportDialog onClose={close} />;
  return null;
}

/** Before a manifest exists: an empty plate holder that says what is happening, or what went wrong and where to go next. */
function StagePlaceholder() {
  const p = useApp((s) => s.progress);
  const err = useApp((s) => s.error);
  const view = useApp((s) => s.view);
  const name = view.q ?? `${view.ra} ${view.dec}`;
  const step = p.phase === "resolving" ? 1 : p.phase === "planning" ? 2 : p.phase === "fetching" ? 3 : 0;
  return (
    <div className={`placeholder${err ? " failed" : ""}`} role={err ? undefined : "status"} aria-live="polite">
      <div className="placeholder-plate" aria-hidden="true"><span className="reticle" /></div>
      <div className="placeholder-text">
        <span className="micro">{err ? "Nothing to show" : "Preparing view"}</span>
        <p className="placeholder-target">{name}</p>
        {err ? (
          <>
            <p className="hint">{err}</p>
            <a className="button" href={href()}><Icon name="back" size={15} />Back to the target list</a>
          </>
        ) : (
          <ol className="steps">
            {["Resolve the target", "Plan visits and bands", "Fetch and stack frames"].map((t, i) => (
              <li key={t} className={step > i + 1 ? "done" : step === i + 1 ? "now" : ""}>{t}</li>
            ))}
          </ol>
        )}
      </div>
    </div>
  );
}

function MainApp() {
  useViewLoader();
  useInitialBin();
  useKeyboard();
  const m = useApp((s) => s.manifest);
  const view = useApp((s) => s.view);
  const hasTarget = !!(view.q || (view.ra && view.dec));
  return (
    <div className={`app ui-${view.ui}`}>
      {hasTarget && <a href="#viewer" className="skip">Skip to the viewer</a>}
      <ReloadBanner />
      <DataSourceBanner />
      <TargetBar />
      {/* a landmark, so screen-reader users can find the notices (axe "region", 2026-11-14) */}
      <div role="region" aria-label="Notices" className="notices">
        <EpochBanner />
        <NewerDataBanner />
        <Progress placeholderShowsError={hasTarget} />
      </div>
      {!hasTarget ? <Home /> : (
        <main className={`layout${m ? "" : " pending"}`} id="viewer">
          <h1 className="sr-only">ParallaX blink of {m?.target ? displayName(m.target) : view.q ?? `${view.ra} ${view.dec}`}</h1>
          <section className="stage" aria-label="Blink viewer">
            {m ? (
              <div className="bench">
                <ErrorBoundary label="Viewer" key={m.key}><Viewer /></ErrorBoundary>
                <PlayerControls compact={view.ui === "simple"} />
              </div>
            ) : <StagePlaceholder />}
            {m && <ErrorBoundary label="Timeline"><Timeline /></ErrorBoundary>}
          </section>
          {m && <ErrorBoundary label="Details panel" key={m.key}><SidePanel /></ErrorBoundary>}
        </main>
      )}
      <DialogHost />
    </div>
  );
}

function Routes() {
  useURLSync();
  useReleases();
  const path = routePath();
  if (path === "/embed") return <EmbedRoute />;
  if (path === "/about") return (
    <>
      <header className="page-bar"><Brand />
        <a className="page-back" href={href()}><Icon name="back" size={15} />Open the viewer</a></header>
      <main className="about-page"><h1>About ParallaX</h1><AboutPage /></main>
    </>
  );
  if (path === "/proof") return (
    <>
      <header className="page-bar"><Brand />
        <a className="page-back" href={href()}><Icon name="back" size={15} />Open the viewer</a></header>
      <main className="about-page"><h1>What we checked</h1><ProofPage /></main>
    </>
  );
  if (path === "/f14") return <F14Page />;
  return <MainApp />;
}

function EmbedRoute() {
  useViewLoader();
  useInitialBin();
  useKeyboard();
  return <EmbedApp />;
}

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <Routes />
    </QueryClientProvider>
  );
}
