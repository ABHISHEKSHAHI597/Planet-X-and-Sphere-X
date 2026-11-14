/**
 * The client against the in-browser mock (workflow.md §8.5): job + progress flow, band-first
 * ordering (implementation.md §2.3), manifest shape and payload sizes, the epoch guard.
 * L0 only: mock pixels are synthetic.
 */
import { beforeAll, describe, expect, it } from "vitest";
import { api, checkManifest, setTransport } from "../src/api/client";
import { mockTransport, resetMock } from "../src/api/mock/server";
import type { JobEvent, ViewManifest } from "../src/api/types";
import { DEFAULTS, viewParams } from "../src/state/url";
import { UnknownFormatError } from "../src/api/formats";

beforeAll(() => { setTransport(mockTransport); resetMock(); });

async function load(params: Record<string, string>): Promise<{ m: ViewManifest; events: JobEvent[] }> {
  const r = await api.createView(params);
  if (r.status === "ready") return { m: r.manifest, events: [] };
  const events: JobEvent[] = [];
  await new Promise<void>((resolve, reject) => {
    api.jobEvents(r.job_id, (e) => { events.push(e); if (e.type === "done") resolve(); if (e.type === "error") reject(new Error(e.message)); }, reject);
  });
  return { m: await api.manifest(r.key), events };
}

describe("mock API", () => {
  it("serves releases with mock features and environment", async () => {
    const r = await api.releases();
    expect(r.environment).toBe("mock");
    expect(r.features.diff).toBe("dev");
  });

  it("epoch guard: the challenge's WISE 0855 coordinate is an old position", async () => {
    const r = await api.resolve("08:55:10.831 -07:14:42.53");
    expect(r.kind).toBe("coords");
    expect(r.epoch_hint?.object).toBe("WISE 0855−0714");
    expect(r.epoch_hint!.epoch).toBeGreaterThan(2009.9);
    expect(r.epoch_hint!.epoch).toBeLessThan(2011);
    expect(r.epoch_hint!.direction).toBe("west");
  });

  it("builds WISE 0855 band-first with 2 full + 2 partial band-6 visits", async () => {
    const { m, events } = await load(viewParams({ ...DEFAULTS, q: "WISE 0855-0714" }));
    const ready = events.filter((e): e is Extract<JobEvent, { type: "stack_ready" }> => e.type === "stack_ready");
    const firstOther = ready.findIndex((e) => e.band !== 6);
    expect(ready.slice(0, firstOther).every((e) => e.band === 6)).toBe(true);
    expect(ready.slice(firstOther).some((e) => e.band === 6)).toBe(false);
    expect(events[0]?.type).toBe("planned");
    expect(m.bins["6"]!.map((b) => [b.status, b.n_frames])).toEqual([["partial", 3], ["full", 16], ["partial", 3], ["full", 21]]);
    expect(m.stacks.every((s) => s.ready)).toBe(true);
    expect(m.data_source).toBe("mock");
    expect(m.warnings.some((w) => w.code === "partial_hidden")).toBe(true);
    const bits = await api.stackF16(m.key, "V2", 6, m.formats.stack);
    expect(bits.length).toBe(m.grid.shape[0] * m.grid.shape[1]);
    const lim = m.limits["6"]!;
    expect(lim.hi).toBeGreaterThan(lim.lo);
  }, 20000);

  it("answers a warm view immediately and lists skipped frames", async () => {
    const p = viewParams({ ...DEFAULTS, q: "Barnard's Star" });
    await load(p);
    const r = await api.createView(p);
    expect(r.status).toBe("ready");
    if (r.status !== "ready") return;
    const st = r.manifest.stacks.find((s) => s.bin === "V3" && s.band === 6)!;
    expect(st.skipped.length).toBe(1);
    expect(r.manifest.frames.filter((f) => f.skipped).length).toBe(1);
  }, 20000);

  it("checkManifest refuses unknown payload formats", () => {
    const fake = { schema_version: "0.1.0", formats: { stack: "f16le-something-else@2", science: "", flags: "" } } as unknown as ViewManifest;
    expect(() => checkManifest(fake)).toThrow(UnknownFormatError);
  });

  it("reports unresolvable names as errors", async () => {
    await expect(api.resolve("Nonexistent Object 123")).rejects.toThrow(/Nothing called/);
  });
  it("knows pins like the server: committed demo pins and views it built, 404 otherwise (audit B-05)", async () => {
    const { m } = await load(viewParams({ ...DEFAULTS, q: "Barnard's Star", pin: "21a7689afc4b" }));
    expect(m.newer_pin).toBeNull();
    const own = await load(viewParams({ ...DEFAULTS, q: "RW Aur" }));
    await expect(api.createView(viewParams({ ...DEFAULTS, q: "RW Aur", pin: own.m.pin }))).resolves.toBeTruthy();
    await expect(api.createView(viewParams({ ...DEFAULTS, q: "RW Aur", pin: "0123456789ab" }))).rejects.toMatchObject({ status: 404 });
  });
});
