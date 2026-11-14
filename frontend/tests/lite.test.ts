/** ParallaX Lite: the static transport answers the pinned views from recorded files and refuses the rest honestly. */
import { describe, expect, it } from "vitest";
import { liteFile, liteMatchKey, makeLiteTransport, NOT_IN_COPY } from "../src/api/lite";
import { routePath } from "../src/lib/base";
import { DEFAULTS, viewParams } from "../src/state/url";

// The same pairs as backend/tests/unit/test_lite_export.py: the exporter and the browser must name files alike.
const FILES: [string, string][] = [
  ["/views/abc123/manifest", "api/views/abc123/manifest.json"],
  ["/views/abc123/stack/V1/6.f16", "api/views/abc123/stack/V1/6.f16"],
  ["/views/abc123/stack/V1/6.f16?raw=1", "api/views/abc123/stack/V1/6.f16"],
  ["/views/abc123/stack/B2026-01-05%3A14d/3.flags.u32", "api/views/abc123/stack/B2026-01-05_14d/3.flags.u32"],
  ["/views/abc123/frames?sort=time&band=4", "api/views/abc123/frames@band_4_sort_time.json"],
  ["/views/abc123/blink25", "api/views/abc123/blink25.json"],
  ["/views/abc123/blink25/2mass_ks.f16", "api/views/abc123/blink25/2mass_ks.f16"],
];

const manifest = { key: "abc123", schema_version: "x", grid: { shape: [2, 2] } };
const index = {
  schema: "parallax-lite@1", created: "2026-11-14T00:00:00+00:00",
  views: [{ key: "abc123", name: "Barnard", match: { q: "Barnard's Star", pin: "21a7689afc4b" } }],
  resolve: { "Barnard's Star": { name: "Barnard's Star", ra: 269.45, dec: 4.69 } },
};

function fakeHost(files: Record<string, unknown>) {
  const seen: string[] = [];
  const fetcher = (async (url: RequestInfo | URL) => {
    const name = String(url).replace("/lite/", "");
    seen.push(name);
    // A static host answers an unknown path with its HTML page and status 200 (SPA fallback).
    if (!(name in files)) return new Response("<!doctype html>", { status: 200, headers: { "content-type": "text/html" } });
    return new Response(JSON.stringify(files[name]), { status: 200, headers: { "content-type": "application/json" } });
  }) as typeof fetch;
  return { fetcher, seen };
}

describe("ParallaX Lite", () => {
  it("names files like scripts/make_lite.py", () => {
    for (const [url, file] of FILES) expect(liteFile(url)).toBe(file);
  });

  it("matches a view on its compute parameters only", () => {
    const posted = viewParams({ ...DEFAULTS, q: "barnard's  star", pin: "21a7689afc4b", bands: "3", partial: true });
    expect(liteMatchKey(posted)).toBe(liteMatchKey({ q: "Barnard's Star", pin: "21a7689afc4b" }));
    expect(liteMatchKey({ ...posted, fov: "12" })).not.toBe(liteMatchKey(posted));
  });

  it("serves a recorded view, its resolver answer, and refuses anything else with a sentence", async () => {
    const { fetcher } = fakeHost({ "index.json": index, "api/views/abc123/manifest.json": manifest });
    const t = makeLiteTransport("/lite/", fetcher);
    const post = (body: Record<string, string>) => t.request("/views", { method: "POST", body: JSON.stringify(body) });

    const ok = await post(viewParams({ ...DEFAULTS, q: "Barnard's Star", pin: "21a7689afc4b" }));
    expect(await ok.json()).toEqual({ status: "ready", manifest });

    const other = await post(viewParams({ ...DEFAULTS, q: "Vega" }));
    expect(other.status).toBe(404);
    expect((await other.json()).detail).toBe(NOT_IN_COPY);

    expect((await (await t.request("/resolve?q=barnard%27s%20star")).json()).ra).toBe(269.45);
    expect((await t.request("/resolve?q=Vega")).status).toBe(404);
    expect((await t.request("/views/abc123/blink25")).status).toBe(404);      // HTML fallback is not our file
    expect((await t.request("/candidates", { method: "POST", body: "{}" })).status).toBe(404);
  });
});

describe("mount point", () => {
  it("finds the route at the root and under a sub-path", () => {
    expect(routePath("/", "/")).toBe("/");
    expect(routePath("/embed", "/")).toBe("/embed");
    expect(routePath("/Nasa-Space-Apps-2026/", "/Nasa-Space-Apps-2026/")).toBe("/");
    expect(routePath("/Nasa-Space-Apps-2026/embed/", "/Nasa-Space-Apps-2026/")).toBe("/embed");
  });
});
