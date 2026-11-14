/**
 * API client (implementation.md §5.1). The frontend talks only to our API (workflow.md §3); the
 * transport is real HTTP + SSE, or the in-browser mock (VITE_MOCK=1, workflow.md §8.5) for
 * frontend work without a backend. The mock is never used in a demo: the UI shows a MOCK badge.
 * VITE_LITE=1 selects the static transport of ParallaX Lite (api/lite.ts).
 */
import {
  API_SCHEMA_VERSION,
  type AstrometryResponse,
  type CandidateRequest,
  type CandidateResponse,
  type Coverage,
  type DiffInfo,
  type JobEvent,
  type LightCurveResponse,
  type OverlayResponse,
  type ReleasesResponse,
  type ResolveResult,
  type SpectrumResponse,
  type ViewManifest,
  type ViewsResponse,
} from "./types";
import type { Blink25Response, FramesResponse, MoversResponse, SsoResponse } from "./generated";
import { assertFormat, FORMAT_F16, FORMAT_F32, FORMAT_U32_FLAGS, SchemaMismatchError, schemaCompatible } from "./formats";
import { f16Bits } from "../lib/half";

export const API_BASE = "/api/v1";

export class ApiError extends Error {
  constructor(public readonly status: number, message: string, public readonly detail?: unknown) {
    super(message);
    this.name = "ApiError";
  }
}

export interface EventStreamLike {
  close(): void;
}

export interface Transport {
  request(path: string, init?: RequestInit): Promise<Response>;
  events(path: string, onEvent: (e: JobEvent) => void, onError: (err: Error) => void): EventStreamLike;
  /** "lite": the recorded answers of the pinned demo views as static files (api/lite.ts). */
  readonly kind: "http" | "mock" | "lite";
}

const JOB_EVENT_TYPES = ["planned", "fetched", "stack_ready", "diff_ready", "warning", "done", "error"] as const;

export const httpTransport: Transport = {
  kind: "http",
  request: (path, init) => fetch(API_BASE + path, init),
  events(path, onEvent, onError) {
    const es = new EventSource(API_BASE + path);
    const handle = (type: string) => (ev: MessageEvent) => {
      // The job's failure event is named "error", which is also the name of EventSource's own connection-error
      // event (a plain Event with no data). Only server messages carry a string `data` (audit B-04).
      if (typeof (ev as Partial<MessageEvent>).data !== "string") return;
      try {
        const data = ev.data ? JSON.parse(ev.data) : {};
        onEvent({ type, ...data } as JobEvent);
      } catch (e) {
        onError(e instanceof Error ? e : new Error(String(e)));
      }
    };
    for (const t of JOB_EVENT_TYPES) es.addEventListener(t, handle(t) as EventListener);
    // Servers that send unnamed events put the type in the payload.
    es.onmessage = (ev) => {
      try { const d = JSON.parse(ev.data); if (d && typeof d.type === "string") onEvent(d as JobEvent); } catch { /* ignore */ }
    };
    es.onerror = () => {
      if (es.readyState === EventSource.CLOSED) onError(new Error("progress stream closed"));
    };
    return es;
  },
};

let transport: Transport = httpTransport;

export function setTransport(t: Transport): void { transport = t; }
export function getTransport(): Transport { return transport; }

async function json<T>(path: string, init?: RequestInit): Promise<T> {
  let r: Response;
  try {
    r = await transport.request(path, init);
  } catch (e) {
    throw new ApiError(0, `Network error talking to the ParallaX API (${(e as Error).message}).`);
  }
  if (!r.ok) {
    let detail: unknown;
    try { detail = await r.json(); } catch { /* not JSON */ }
    const given = (detail as { detail?: unknown } | undefined)?.detail;
    const msg = typeof given === "string" ? given : friendlyStatus(r.status, r.statusText);
    if (typeof given !== "string") console.warn(`[ParallaX] ${r.status} ${r.statusText} from ${path}`, detail);
    throw new ApiError(r.status, msg, detail);
  }
  return (await r.json()) as T;
}

/** A sentence for an error without a JSON detail (a crash or a proxy page), instead of "500 Internal Server Error"
 *  under "View not built" (audit F-05). FastAPI's own errors carry `detail` and are shown as they are. */
export function friendlyStatus(status: number, statusText = ""): string {
  if (status === 429) return "Too many requests from this address; please wait a minute and try again.";
  if (status === 502 || status === 503 || status === 504)
    return "The ParallaX server or an archive it needs is not answering right now. Try again in a minute; the pinned targets on the home page still work.";
  if (status >= 500) return "ParallaX hit a problem building this. Try again, or open one of the pinned targets on the home page.";
  return `${status} ${statusText}`.trim();
}

async function binary(path: string): Promise<ArrayBuffer> {
  const r = await transport.request(path);
  if (!r.ok) throw new ApiError(r.status, `${r.status} fetching ${path}`);
  return r.arrayBuffer();
}

const enc = encodeURIComponent;
const qs = (o: Record<string, string | number | boolean | null | undefined>) =>
  Object.entries(o).filter(([, v]) => v !== null && v !== undefined && v !== "")
    .map(([k, v]) => `${enc(k)}=${enc(String(v))}`).join("&");

/** Every manifest carries schema_version; a mismatch means a deploy happened under an open tab. */
export function checkManifest(m: ViewManifest): ViewManifest {
  if (!schemaCompatible(m.schema_version, API_SCHEMA_VERSION)) throw new SchemaMismatchError(m.schema_version, API_SCHEMA_VERSION);
  assertFormat(m.formats.stack, FORMAT_F16);
  return m;
}

export const api = {
  releases: () => json<ReleasesResponse>("/releases"),
  resolve: (q: string) => json<ResolveResult>(`/resolve?${qs({ q })}`),
  coverage: (ra: number, dec: number, fov: number) => json<Coverage>(`/coverage?${qs({ ra, dec, fov })}`),

  async createView(params: Record<string, string>): Promise<ViewsResponse> {
    const r = await json<ViewsResponse>("/views", {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(params),
    });
    if (r.status === "ready") checkManifest(r.manifest);
    return r;
  },
  manifest: async (key: string) => checkManifest(await json<ViewManifest>(`/views/${enc(key)}/manifest`)),
  jobEvents: (jobId: string, onEvent: (e: JobEvent) => void, onError: (e: Error) => void) =>
    transport.events(`/jobs/${enc(jobId)}/events`, onEvent, onError),

  stackPath: (key: string, bin: string, band: number | string, ext: "f16" | "f32" | "var.f32" | "flags.u32" | "filled.u8") =>
    `/views/${enc(key)}/stack/${enc(bin)}/${enc(String(band))}.${ext}`,
  /** Display-only mask of model-filled core pixels (P1-7), one byte per grid pixel. */
  filledMask: async (key: string, bin: string, band: number) => new Uint8Array(await binary(api.stackPath(key, bin, band, "filled.u8"))),
  async stackF16(key: string, bin: string, band: number, format: string, raw = false): Promise<Uint16Array> {
    assertFormat(format, FORMAT_F16);
    return f16Bits(await binary(api.stackPath(key, bin, band, "f16") + (raw ? "?raw=1" : "")));
  },
  async stackF32(key: string, bin: string, band: number, which: "f32" | "var.f32", format: string): Promise<Float32Array> {
    assertFormat(format, FORMAT_F32);
    const buf = await binary(api.stackPath(key, bin, band, which));
    return new Float32Array(buf);
  },
  async stackFlags(key: string, bin: string, band: number, format: string): Promise<Uint32Array> {
    assertFormat(format, FORMAT_U32_FLAGS);
    return new Uint32Array(await binary(api.stackPath(key, bin, band, "flags.u32")));
  },
  /** Server-rendered PNG with the SHARED limits (fallback viewer, implementation.md §6.4). */
  pngURL: (key: string, bin: string, band: number, o: { stretch: string; lo: number; hi: number; cmap: string; raw?: boolean }) =>
    `${transport.kind === "http" ? API_BASE : "mock:"}/views/${enc(key)}/png/${enc(bin)}/${band}.png?` +
    qs({ stretch: o.stretch, lim: `manual:${o.lo},${o.hi}`, cmap: o.cmap, ...(o.raw ? {raw: "1"} : {}) }),
  pngBlob: (url: string) => transport.request(url.replace(/^mock:/, "")).then((r) => r.blob()),

  diff: (key: string, a: string, b: string, band: number) =>
    json<DiffInfo & { url: string }>(`/views/${enc(key)}/diff?${qs({ a, b, band })}`),
  async diffF16(url: string, format: string): Promise<Uint16Array> {
    assertFormat(format, FORMAT_F16);
    return f16Bits(await binary(url.startsWith(API_BASE) ? url.slice(API_BASE.length) : url));
  },
  spectrum: (ra: number, dec: number, track: boolean, key?: string) =>
    json<SpectrumResponse>(`/spectrum?${qs({ ra, dec, track: track ? 1 : 0, visits: "all", key })}`),
  astrometry: (ra: number, dec: number, name?: string, key?: string) => json<AstrometryResponse>(`/astrometry?${qs({ ra, dec, name, key })}`),
  movers: (key: string, mode: "stellar" | "planetx", mu_max = 10) => json<MoversResponse>(`/movers?${qs({key, mode, mu_max})}`),
  lightcurve: (ra: number, dec: number, method: "psf" | "annulus", key?: string, release?: string) =>
    json<LightCurveResponse>(`/lightcurve?${qs({ ra, dec, bin: "14d", method, key, release })}`),
  overlays: (cat: "gaia" | "catwise" | "allwise" | "simbad" | "sso", ra: number, dec: number, r: number, mjd: number) =>
    json<OverlayResponse>(`/overlays/${cat}?${qs({ ra, dec, r, mjd })}`),
  /** Exposure flipbook (P2-2): frames of one band sorted by the λ each saw at the target (default) or by time. */
  frames: (key: string, band: number, sort: "lambda" | "time" = "lambda") =>
    json<FramesResponse>(`/views/${enc(key)}/frames?${qs({ band, sort })}`),
  /** One gridded exposure or any other server-relative f16 payload URL from a response. */
  async payloadF16(url: string, format: string): Promise<Uint16Array> {
    assertFormat(format, FORMAT_F16);
    return f16Bits(await binary(url.startsWith(API_BASE) ? url.slice(API_BASE.length) : url));
  },
  /** λ-scrubber: the (17, ny, nx) per-pixel spectral cube of one bin and band, planes in bin order. */
  async cubeF16(key: string, bin: string, band: number): Promise<Uint16Array> {
    return f16Bits(await binary(`/views/${enc(key)}/cube/${enc(bin)}/${band}.f16`));
  },
  /** λ-range RGB preset (methane | ice): (3, ny, nx) f16, R, G, B from per-pixel measured λ (server). */
  async rgbF16(key: string, bin: string, preset: string): Promise<Uint16Array> {
    return f16Bits(await binary(`/views/${enc(key)}/rgb/${enc(bin)}/${enc(preset)}.f16`));
  },
  /** 25-year blink (P2-1): archival epochs + SPHEREx on one grid, each on its own sky σ (server-side). */
  blink25: (key: string) => json<Blink25Response>(`/views/${enc(key)}/blink25`),
  sso: (name: string, mjd: number[]) => json<SsoResponse>(`/sso?${qs({ name, mjd: mjd.map((x) => x.toFixed(6)).join(",") })}`),
  /** Server-rendered export (P2-7). A plain link: the browser downloads it. */
  exportURL: (fmt: "gif" | "apng" | "mp4" | "fits" | "csv", o: { key: string; band: number; bins: string[]; stretch: string; cmap: string; fps: number }) =>
    `${API_BASE}/export/${fmt}?${qs({ key: o.key, band: o.band, bins: o.bins.join(","), stretch: o.stretch, cmap: o.cmap, fps: o.fps })}`,
  candidate: (body: CandidateRequest) => json<CandidateResponse>("/candidates", {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
  }),
};
