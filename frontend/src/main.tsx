import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { App } from "./App";
import { setTransport } from "./api/client";
import { BASE } from "./lib/base";
import { AppCrash, ErrorBoundary } from "./components/ErrorBoundary";
// Fonts ship with the app (SIL OFL 1.1, fontsource): first paint never waits on a third-party host or the venue
// network (audit F-19; workflow.md principle 8). Archivo with its width axis, Plex Mono in the three weights used.
import "@fontsource-variable/archivo/wdth.css";
import "@fontsource/ibm-plex-mono/400.css";
import "@fontsource/ibm-plex-mono/500.css";
import "@fontsource/ibm-plex-mono/600.css";
import "./styles.css";

async function boot() {
  // workflow.md §8.5: VITE_MOCK=1 swaps in the in-browser mock API (never in a demo; the UI says MOCK).
  if (import.meta.env.VITE_MOCK === "1") {
    const { mockTransport } = await import("./api/mock/server");
    setTransport(mockTransport);
    console.info("[ParallaX] MOCK transport active: synthetic data, not SPHEREx measurements");
  }
  // ParallaX Lite: the pinned demo views as static files next to the app (scripts/make_lite.py), no server.
  if (import.meta.env.VITE_LITE === "1") {
    const { makeLiteTransport } = await import("./api/lite");
    setTransport(makeLiteTransport(`${BASE}lite/`));
  }
  createRoot(document.getElementById("root")!).render(
    <StrictMode><ErrorBoundary label="ParallaX" fallback={(e) => <AppCrash error={e} />}><App /></ErrorBoundary></StrictMode>,
  );
}
void boot();
