/**
 * App state (Zustand, implementation.md §2.2). `view` is the URL state (state/url.ts); everything
 * else is runtime. The URL is the single source of truth for what is shown: reload reproduces the
 * view (P0-5).
 */
import { create } from "zustand";
import type { JobEvent, ReleasesResponse, ViewManifest } from "../api/types";
import type { ViewTransform } from "../gl/renderer";
import type { Marker } from "../components/OverlayLayer";
import { DEFAULTS, type ViewState } from "./url";

export interface JobProgress {
  phase: "idle" | "resolving" | "planning" | "fetching" | "done" | "error";
  i: number;
  n: number;
  message?: string;
}

export interface Hover {
  col: number;
  row: number;
  ra: number;
  dec: number;
  /** canvas CSS px, for the loupe position */
  x: number;
  y: number;
}

export interface AppState {
  view: ViewState;
  setView: (patch: Partial<ViewState>, opts?: { push?: boolean }) => void;
  replaceView: (v: ViewState) => void;

  release: ReleasesResponse | null;
  setRelease: (r: ReleasesResponse | null) => void;

  manifest: ViewManifest | null;
  setManifest: (m: ViewManifest | null) => void;
  ready: Set<string>;                // `${bin}|${band}` stacks whose payload is available
  markReady: (bin: string, band: number) => void;
  progress: JobProgress;
  setProgress: (p: JobProgress) => void;
  jobWarnings: string[];
  onJobEvent: (e: JobEvent) => void;
  error: string | null;
  setError: (e: string | null) => void;
  schemaMismatch: boolean;
  setSchemaMismatch: (b: boolean) => void;

  frame: number;                     // index into the playable bins of the current band
  setFrame: (i: number) => void;
  playing: boolean;
  setPlaying: (b: boolean) => void;
  comparing: boolean;                // "hold B to compare"
  setComparing: (b: boolean) => void;

  transform: ViewTransform | null;
  setTransform: (t: ViewTransform | null) => void;
  hover: Hover | null;
  setHover: (h: Hover | null) => void;
  picked: (Marker & { bin: string; band: number }) | null;   // asteroid-layer marker clicked in the viewer
  setPicked: (p: AppState["picked"]) => void;

  dismissedHint: string | null;
  dismissHint: (q: string | null) => void;
  dialog: null | "share" | "about" | "help" | "report";
  setDialog: (d: AppState["dialog"]) => void;
  glFailed: string | null;           // why the WebGL viewer is unavailable (→ PNG fallback)
  setGlFailed: (s: string | null) => void;
}

export const useApp = create<AppState>((set) => ({
  view: DEFAULTS,
  setView: (patch, opts) => set((s) => {
    const next = { ...s.view, ...patch };
    pendingPush = pendingPush || !!opts?.push;
    return { view: next };
  }),
  replaceView: (v) => set({ view: v }),

  release: null,
  setRelease: (r) => set({ release: r }),

  manifest: null,
  setManifest: (m) => set((s) => ({
    manifest: m,
    picked: m && s.manifest?.key === m.key ? s.picked : null,
    ready: m ? new Set([...(s.manifest?.key === m.key ? s.ready : []), ...m.stacks.filter((x) => x.ready).map((x) => `${x.bin}|${x.band}`)]) : new Set(),
  })),
  ready: new Set(),
  markReady: (bin, band) => set((s) => {
    const r = new Set(s.ready); r.add(`${bin}|${band}`);
    return { ready: r };
  }),
  progress: { phase: "idle", i: 0, n: 0 },
  setProgress: (p) => set({ progress: p }),
  jobWarnings: [],
  onJobEvent: (e) => set((s) => {
    switch (e.type) {
      case "planned": return { progress: { phase: "fetching", i: 0, n: e.n } };
      case "fetched": return { progress: { phase: "fetching", i: e.i, n: e.n } };
      case "warning": return { jobWarnings: [...s.jobWarnings, e.message].slice(-50) };
      case "done": return { progress: { ...s.progress, phase: "done", i: s.progress.n } };
      case "error": return { progress: { ...s.progress, phase: "error", message: e.message }, error: e.message };
      default: return {};
    }
  }),
  error: null,
  setError: (e) => set({ error: e }),
  schemaMismatch: false,
  setSchemaMismatch: (b) => set({ schemaMismatch: b }),

  frame: 0,
  setFrame: (i) => set({ frame: i }),
  playing: false,
  setPlaying: (b) => set({ playing: b }),
  comparing: false,
  setComparing: (b) => set({ comparing: b }),

  transform: null,
  setTransform: (t) => set({ transform: t }),
  hover: null,
  setHover: (h) => set({ hover: h }),
  picked: null,
  setPicked: (p) => set({ picked: p }),

  dismissedHint: null,
  dismissHint: (q) => set({ dismissedHint: q }),
  dialog: null,
  setDialog: (d) => set({ dialog: d }),
  glFailed: null,
  setGlFailed: (s) => set({ glFailed: s }),
}));

/** true when the last setView asked for a history entry (target changes), consumed by the URL sync. */
let pendingPush = false;
export function takePendingPush(): boolean {
  const p = pendingPush; pendingPush = false; return p;
}
