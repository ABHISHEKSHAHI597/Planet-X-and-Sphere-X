/**
 * ParallaX Lite transport (optimisation.md item 0.3; advanced_research.md A1): the API's own answers for the
 * pinned demo views, recorded by scripts/make_lite.py and served as static files. No server, no archive: the
 * link keeps working for as long as the files are hosted. It cannot build a new patch of sky, and says so.
 *
 * Layout under the Lite root (`<base>lite/`):
 *   index.json            { views: [{key, name, match}], resolve: {name → ResolveResult} }
 *   releases.json         the /releases answer, with only the capabilities a static copy can serve
 *   api/<path>            every recorded GET, named by `liteFile` (scripts/make_lite.py has the same rule)
 * PNGs for the WebGL-free viewer are drawn here from the recorded float16 stack, with the same shared limits.
 */
import type { EventStreamLike, Transport } from "./client";
import { decodeF16, f16Bits } from "../lib/half";
import { parseStretch, renderRGBA } from "../lib/stretch";

export interface LiteIndex {
  schema: string;
  created: string;
  views: { key: string; name: string; match: Record<string, string> }[];
  resolve: Record<string, unknown>;
}

/** POST /views defaults (backend app/viewkey.py DEFAULTS; state/url.ts DEFAULTS). */
const MATCH_DEFAULTS: Record<string, string> = { fov: "6", px: "3", axis: "auto", center: "fixed", mask: "auto", rel: "auto", lim: "zscale" };
const MATCH_KEYS = ["q", "ra", "dec", "fov", "px", "axis", "center", "mask", "rel", "pin", "lim"];

export const NOT_IN_COPY =
  "This is the frozen copy of ParallaX. It holds the targets listed on the home page and cannot build a new patch of sky.";

const norm = (s: string) => s.trim().toLowerCase().replace(/\s+/g, " ");

/** What identifies a recorded view: the compute parameters of the POST /views body, defaults filled, names folded. */
export function liteMatchKey(body: Record<string, unknown>): string {
  const out: string[] = [];
  for (const k of MATCH_KEYS) {
    let v = body[k] === null || body[k] === undefined || body[k] === "" ? MATCH_DEFAULTS[k] : String(body[k]);
    if (v === undefined) continue;
    if (k === "fov" || k === "px") v = String(Number(v));
    out.push(`${k}=${k === "q" ? norm(v) : v.trim()}`);
  }
  return out.join("&");
}

const safe = (s: string) => decodeURIComponent(s).replace(/[^A-Za-z0-9._-]/g, "_");

/** The static file of a GET: path segments made file-safe; a payload (it has an extension) is named by its path
 *  alone, a JSON answer by its path and sorted query. `/views/k/frames?band=4&sort=time` →
 *  `api/views/k/frames@band_4_sort_time.json`. */
export function liteFile(pathAndQuery: string): string {
  const [path = "", query = ""] = pathAndQuery.split("?");
  const segs = path.split("/").filter(Boolean).map(safe);
  const name = `api/${segs.join("/")}`;
  if (/\.[A-Za-z0-9]+$/.test(segs[segs.length - 1] ?? "")) return name;
  const q = query.split("&").filter(Boolean).map((p) => decodeURIComponent(p)).sort().join("&").replace(/[^A-Za-z0-9._-]/g, "_");
  return `${name}${q ? `@${q}` : ""}.json`;
}

const jsonResponse = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });

export function makeLiteTransport(root: string, fetcher: typeof fetch = (...a) => fetch(...a)): Transport {
  let index: Promise<{ byMatch: Map<string, string>; resolve: Map<string, unknown> }> | null = null;
  const shapes = new Map<string, Promise<[number, number]>>();     // view key → [ny, nx]

  /** A recorded file, or 404: a static host answers an unknown path with its HTML page, which is not our file. */
  const file = async (name: string): Promise<Response> => {
    let r: Response;
    try { r = await fetcher(root + name); } catch { return jsonResponse({ detail: NOT_IN_COPY }, 404); }
    if (!r.ok || (r.headers.get("content-type") ?? "").includes("text/html")) return jsonResponse({ detail: NOT_IN_COPY }, 404);
    return r;
  };
  const loadIndex = () => {
    index ??= file("index.json").then(async (r) => {
      if (!r.ok) throw new Error("ParallaX Lite: index.json is missing from this copy");
      const ix = (await r.json()) as LiteIndex;
      return {
        byMatch: new Map(ix.views.map((v) => [liteMatchKey(v.match), v.key])),
        resolve: new Map(Object.entries(ix.resolve ?? {}).map(([k, v]) => [norm(k), v])),
      };
    });
    return index;
  };
  const shapeOf = (key: string) => {
    let p = shapes.get(key);
    if (!p) {
      p = file(liteFile(`/views/${key}/manifest`)).then(async (r) => ((await r.json()) as { grid: { shape: [number, number] } }).grid.shape);
      shapes.set(key, p);
    }
    return p;
  };

  async function png(key: string, bin: string, band: string, query: string): Promise<Response> {
    const r = await file(liteFile(`/views/${key}/stack/${bin}/${band}.f16`));
    if (!r.ok) return r;
    const [ny, nx] = await shapeOf(key);
    const q = new URLSearchParams(query);
    const [lo, hi] = (q.get("lim") ?? "manual:0,1").replace("manual:", "").split(",").map(Number) as [number, number];
    const rgba = renderRGBA(decodeF16(f16Bits(await r.arrayBuffer())), nx, ny, lo, hi, parseStretch(q.get("stretch")), (q.get("cmap") ?? "gray") as "gray");
    const c = document.createElement("canvas");
    c.width = nx; c.height = ny;
    c.getContext("2d")!.putImageData(new ImageData(rgba, nx, ny), 0, 0);
    const blob: Blob = await new Promise((done) => c.toBlob((b) => done(b!), "image/png"));
    return new Response(blob, { headers: { "Content-Type": "image/png" } });
  }

  return {
    kind: "lite",
    async request(pathAndQuery, init) {
      const [path = "", query = ""] = pathAndQuery.split("?");
      if ((init?.method ?? "GET").toUpperCase() !== "GET") {
        if (path !== "/views") return jsonResponse({ detail: "The frozen copy of ParallaX is read-only." }, 404);
        const key = (await loadIndex()).byMatch.get(liteMatchKey(JSON.parse(String(init?.body ?? "{}")) as Record<string, unknown>));
        if (!key) return jsonResponse({ detail: NOT_IN_COPY }, 404);
        const m = await file(liteFile(`/views/${key}/manifest`));
        return m.ok ? jsonResponse({ status: "ready", manifest: await m.json() }) : m;
      }
      if (path === "/releases") return file("releases.json");
      if (path === "/resolve") {
        const hit = (await loadIndex()).resolve.get(norm(new URLSearchParams(query).get("q") ?? ""));
        return hit ? jsonResponse(hit) : jsonResponse({ detail: NOT_IN_COPY }, 404);
      }
      const p = /^\/views\/([^/]+)\/png\/([^/]+)\/(\d)\.png$/.exec(path);
      if (p) return png(p[1]!, p[2]!, p[3]!, query);
      return file(liteFile(pathAndQuery));
    },
    events(_path, _onEvent, onError): EventStreamLike {
      // Every recorded view is complete, so POST /views never answers with a job.
      queueMicrotask(() => onError(new Error(NOT_IN_COPY)));
      return { close: () => undefined };
    },
  };
}
