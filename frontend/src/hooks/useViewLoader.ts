/**
 * Loads the view for the current URL state (implementation.md §2.3): POST /views → 200 manifest
 * (warm) or 202 job → SSE progress; stacks become drawable as `stack_ready` arrives, selected band
 * first, so the first blink appears long before the whole view is in.
 * The manifest is re-read as stacks land (throttled to one read per MANIFEST_REFRESH_MS, trailing): it carries
 * the band's shared display limits, which the server writes with each stack. Reading it only at `planned`
 * and `done` drew the first visits with placeholder 0–1 limits for the whole build.
 */
import { useEffect, useMemo } from "react";
import { api, ApiError } from "../api/client";
import { SchemaMismatchError, UnknownFormatError } from "../api/formats";
import { useApp } from "../state/store";
import { computeParams, viewParams } from "../state/url";

export const MANIFEST_REFRESH_MS = 1200;

export function useViewLoader(): void {
  const view = useApp((s) => s.view);
  // Only parameters that change the view key restart the load. Band and partial-visit choices are display-only:
  // re-posting on each band key used to trip the per-IP job limit during a first load (audit B-03).
  const sig = useMemo(() => JSON.stringify(computeParams(viewParams(view))), [view]);

  useEffect(() => {
    const st = useApp.getState();
    const p = viewParams(st.view);              // the full body: `bands` still says which band to build first
    if (!p.q && !(p.ra && p.dec)) {
      st.setManifest(null);
      st.setProgress({ phase: "idle", i: 0, n: 0 });
      return;
    }
    let closed = false;
    let stream: { close(): void } | null = null;
    let timer: ReturnType<typeof setTimeout> | null = null;
    let lastRefresh = 0;
    useApp.setState({ error: null, jobWarnings: [], progress: { phase: "resolving", i: 0, n: 0 } });

    const fail = (e: unknown) => {
      if (closed) return;
      if (e instanceof SchemaMismatchError) { useApp.getState().setSchemaMismatch(true); return; }
      const msg = e instanceof ApiError || e instanceof UnknownFormatError || e instanceof Error ? e.message : String(e);
      useApp.setState({ error: msg, progress: { phase: "error", i: 0, n: 0, message: msg } });
    };
    const refresh = async (key: string) => {
      lastRefresh = Date.now();
      try {
        const m = await api.manifest(key);
        if (!closed) useApp.getState().setManifest(m);
      } catch (e) { fail(e); }
    };
    const refreshSoon = (key: string) => {       // throttled, trailing: the last stack of a burst is never missed
      if (timer) return;
      timer = setTimeout(() => { timer = null; if (!closed) void refresh(key); },
        Math.max(0, MANIFEST_REFRESH_MS - (Date.now() - lastRefresh)));
    };

    (async () => {
      try {
        const r = await api.createView(p);
        if (closed) return;
        if (r.status === "ready") {
          useApp.getState().setManifest(r.manifest);
          useApp.getState().setProgress({ phase: "done", i: 1, n: 1 });
          return;
        }
        useApp.getState().setProgress({ phase: "planning", i: 0, n: 0 });
        let fetchedManifest = false;
        stream = api.jobEvents(r.job_id, (e) => {
          if (closed) return;
          useApp.getState().onJobEvent(e);
          if (e.type === "planned" && !fetchedManifest) { fetchedManifest = true; void refresh(r.key); }
          if (e.type === "stack_ready") {
            useApp.getState().markReady(e.bin, e.band);
            if (!fetchedManifest) { fetchedManifest = true; void refresh(r.key); } else refreshSoon(r.key);
          }
          if (e.type === "done") {
            if (timer) { clearTimeout(timer); timer = null; }
            void refresh(r.key); stream?.close();
          }
          // A failed job is final: close the stream, or the browser reconnects and the server replays the job (B-04).
          if (e.type === "error") {
            if (timer) { clearTimeout(timer); timer = null; }
            stream?.close();
          }
        }, fail);
      } catch (e) { fail(e); }
    })();
    return () => { closed = true; stream?.close(); if (timer) clearTimeout(timer); };
  }, [sig]);
}
