// Sky atlas survey resolution: never hand Aladin a survey CDS cannot serve (components/SkyContext.tsx).
import { afterEach, describe, expect, it, vi } from "vitest";
import { CDS_MIRRORS, resolveHips } from "../src/components/SkyContext";

type Route = (url: string) => Response | Promise<Response> | null;
function mockFetch(route: Route) {
  return vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
    const url = String(input);
    const r = await route(url);
    if (!r) throw new TypeError(`network error: ${url}`);
    return r;
  });
}

afterEach(() => vi.restoreAllMocks());

describe("resolveHips", () => {
  it("uses the direct HiPS path on the first mirror that answers", async () => {
    mockFetch((u) => (u === `${CDS_MIRRORS[1]}/2MASS/Color/properties` ? new Response("creator_did = ivo://CDS/P/2MASS/color") : null));
    expect(await resolveHips("CDS/P/2MASS/color")).toBe(`${CDS_MIRRORS[1]}/2MASS/Color`);
  });

  it("falls back to the MocServer's hips_service_url when the direct path fails", async () => {
    const moved = "https://example.org/hips/DSS2";
    mockFetch((u) => {
      if (u.includes("/MocServer/query")) return new Response(JSON.stringify([{ hips_service_url: moved }]));
      if (u === `${moved}/properties`) return new Response("ok");
      return new Response("gone", { status: 404 });
    });
    expect(await resolveHips("CDS/P/DSS2/color")).toBe(moved);
  });

  it("uses a listed mirror when alasky and its MocServer answer 404 (CDS outage of 2026-11-09)", async () => {
    const mirror = "https://stpubdata.s3.us-east-1.amazonaws.com/mast/skybackgrounds/PanSTARRS";
    mockFetch((u) => (u === `${mirror}/properties` ? new Response("creator_did = ivo://CDS/P/PanSTARRS/DR1/color-i-r-g") : new Response("gone", { status: 404 })));
    expect(await resolveHips("CDS/P/PanSTARRS/DR1/color-i-r-g")).toBe(mirror);
  });

  it("returns null when no CDS server answers (the panel then shows the unavailable state)", async () => {
    mockFetch(() => new Response("Service Unavailable", { status: 503 }));
    expect(await resolveHips("CDS/P/allWISE/color")).toBeNull();
  });
});
