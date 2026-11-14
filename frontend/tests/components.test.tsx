import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { TimeBinInfo, ViewManifest } from "../src/api/types";
import { Timeline } from "../src/components/Timeline";
import { EpochBanner, targetPatch } from "../src/components/TargetBar";
import { AboutPage } from "../src/components/Dialogs";
import { DataSourceBanner } from "../src/components/Badges";
import { useApp } from "../src/state/store";
import { DEFAULTS } from "../src/state/url";
import { altText } from "../src/lib/alttext";
import { MoversPanel, SpectrumPanel } from "../src/components/SidePanel";
import { OverlayLayer } from "../src/components/OverlayLayer";
import { api } from "../src/api/client";
import * as currentHooks from "../src/hooks/useCurrent";

afterEach(() => { cleanup(); vi.restoreAllMocks(); useApp.setState({ manifest: null, view: DEFAULTS, ready: new Set(), dismissedHint: null }); });

const bin = (id: string, status: TimeBinInfo["status"], mjd: number, n: number): TimeBinInfo => ({
  id, band: 6, status, mjd_mean: mjd, mjd_min: mjd - 2, mjd_max: mjd + 2, surveys: [1], n_frames: n, n_visit_frames: n * 6,
  label: status === "partial" ? `${id} · partial (${n} in band 6)` : `${id} · ${n * 6} frames`,
});

function manifest(extra: Partial<ViewManifest> = {}): ViewManifest {
  return {
    schema_version: "0.1.0", key: "k", pin: "0123456789ab", params: {}, axis: "visit", bands: [6],
    target: { query: "WISE 0855-0714", kind: "star", name: "WISE 0855−0714", ra: 0, dec: 0, epoch: 2000, propagated_now: { ra: 0, dec: 0, epoch: 2026.8 } },
    grid: { ctype: ["RA---TAN", "DEC--TAN"], crval: [0, 0], crpix: [61, 61], cdelt: [-3 / 3600, 3 / 3600], shape: [121, 121], pix_arcsec: 3, native: false },
    bins: { "6": [bin("V1", "partial", 60800, 3), bin("V2", "full", 60990, 16), bin("V3", "partial", 61020, 3), bin("V4", "full", 61160, 21)] },
    stacks: [], limits: { "6": { lo: 0, hi: 1, lim: "zscale" } }, frames: [], track: [],
    flags: { bits: {}, info: {}, format: "u32le-row0south-flags-canonical@1" },
    formats: { stack: "f16le-row0south-nodata-65504@1", science: "f32le-row0south-nodata-nan@1", flags: "u32le-row0south-flags-canonical@1" },
    release: { release_state: {}, newest_period: "2026W40_2A", checked_at: "" }, warnings: [], data_source: "live", ...extra,
  };
}

describe("Timeline", () => {
  it("shows partial visits but disables them in the blink by default", () => {
    useApp.setState({ manifest: manifest(), ready: new Set(["V2|6", "V4|6"]) });
    render(<Timeline />);
    const chips = screen.getAllByRole("button");
    expect(chips.map((c) => (c as HTMLButtonElement).disabled)).toEqual([true, false, true, false]);
    expect(screen.getByText(/Hatched: partial visits/)).toBeTruthy();
    expect(document.querySelectorAll("rect.bin.partial").length).toBe(2);
  });
  it("enables partial visits with partial=1", () => {
    useApp.setState({ manifest: manifest(), view: { ...DEFAULTS, partial: true } });
    render(<Timeline />);
    expect(screen.getAllByRole("button").every((c) => !(c as HTMLButtonElement).disabled)).toBe(true);
  });
});

it("keeps SOURCE-only science and displays separately scaled template provenance", () => {
  vi.spyOn(currentHooks, "useFeature").mockReturnValue({ level: "dev", enabled: true, unvalidated: true });
  useApp.setState({ manifest: manifest() });
  const client = new QueryClient({ defaultOptions: { queries: { staleTime: Infinity } } });
  const row = { visit: "V2", lam: 4.5, dlam: .04, flux: 10, err: 1, detector: 6, rchi2: 1, flags: ["SOURCE"], contaminated: false };
  client.setQueryData(["spectrum", 0, 0, DEFAULTS.center, "k", false], { rows: [row, { ...row, lam: 1.083, contaminated: true }], notes: [], templates: [{ name: "model", spectral_type: "500 K", visit: "V2", release: "qr2", label: "Atmosphere model, illustrative", chi2: 2, dof: 3, samples: [{lam: 4.5, flux: 9}], provenance: { url: "https://example.org/original-model", note: "No temperature inference" } }] });
  render(<QueryClientProvider client={client}><SpectrumPanel /></QueryClientProvider>);
  expect(screen.getByText(/show contaminated \(1\)/)).toBeTruthy();
  expect(screen.getByText(/D6.*SOURCE/)).toBeTruthy();
  fireEvent.change(screen.getByLabelText("Spectral template"), { target: { value: "0" } });
  expect(screen.getByText(/Atmosphere model, illustrative/)).toBeTruthy();
  expect(screen.getByRole("link", { name: "Template source" }).getAttribute("href")).toBe("https://example.org/original-model");
  expect(screen.queryByText("observed template")).toBeNull();
  client.clear();
});

it("runs mover work only on request and guards the daily distant-body view", async () => {
  vi.spyOn(currentHooks, "useFeature").mockReturnValue({ level: "dev", enabled: true, unvalidated: true });
  const request = vi.spyOn(api, "movers").mockResolvedValue({key:"k", candidates:[], orphans:[{id:"one"}], validity:"unvalidated"});
  useApp.setState({ manifest: manifest() });
  const client = new QueryClient();
  render(<QueryClientProvider client={client}><MoversPanel /></QueryClientProvider>);
  expect(request).not.toHaveBeenCalled();
  fireEvent.click(screen.getByText("Find candidates"));
  expect(await screen.findByText(/0 vetted candidate chains/)).toBeTruthy();
  expect(request).toHaveBeenCalledWith("k", "stellar", 10);
  fireEvent.change(screen.getByLabelText("Search mode"), {target:{value:"planetx"}});
  expect(screen.getByText(/needs daily bins/)).toBeTruthy();
  expect((screen.getByText("Find candidates") as HTMLButtonElement).disabled).toBe(true);
  client.clear();
});

describe("EpochBanner (P0-1)", () => {
  it("explains an old-epoch coordinate with numbers from the resolver", () => {
    const m = manifest({ target: { query: "08:55:10.831 -07:14:42.53", kind: "coords", name: "x", ra: 133.795, dec: -7.245, epoch: 2026.8,
      propagated_now: { ra: 133.795, dec: -7.245, epoch: 2026.8 },
      epoch_hint: { object: "WISE 0855−0714", epoch: 2010.46, sep_arcsec: 0.2, now_ra: 133.758, now_dec: -7.242, moved_arcmin: 2.23, direction: "west" } } });
    useApp.setState({ manifest: m });
    render(<EpochBanner />);
    const t = screen.getByRole("alert").textContent!;
    expect(t).toContain("WISE 0855−0714");
    expect(t).toContain("≈2010.5");
    expect(t).toContain("2.2′ west");
    expect(screen.getByText("Track it")).toBeTruthy();
    expect(screen.getByText("Keep fixed sky")).toBeTruthy();
  });
});

describe("target input", () => {
  it("turns coordinates into ra/dec and names into q, resetting pins", () => {
    expect(targetPatch("08:55:10.831 −07:14:42.53")).toEqual({ patch: { sel: null, t: null, a: null, b: null, pin: null, q: null, ra: "133.795129", dec: "-7.245147" } });
    // a test target opens its pinned frame list (audit F-01); any other name resets the pin
    expect(targetPatch("WISE 0855-0714")).toEqual({ patch: { sel: null, t: null, a: null, b: null, pin: "325c57328320", q: "WISE 0855-0714", ra: null, dec: null } });
    expect(targetPatch("Proxima Cen")).toEqual({ patch: { sel: null, t: null, a: null, b: null, pin: null, q: "Proxima Cen", ra: null, dec: null } });
    // the home page's coordinate example is Barnard's J2000 position; config/demo_views.yaml prewarms exactly this body
    expect(targetPatch("17:57:48.5 +04:41:36")).toMatchObject({ patch: { ra: "269.452083", dec: "4.693333" } });
    expect("error" in targetPatch("  ")).toBe(true);
    expect("error" in targetPatch("25:00:00 +91:00:00")).toBe(true);
  });
});

describe("About & credits (P0-7)", () => {
  it("lists the SPHEREx DOIs and the no-endorsement disclaimer", () => {
    render(<QueryClientProvider client={new QueryClient()}><AboutPage /></QueryClientProvider>);
    expect(screen.getByText("10.26131/IRSA652", { exact: false })).toBeTruthy();
    expect(screen.getByText("10.26131/IRSA662", { exact: false })).toBeTruthy();
    expect(screen.getByText(/not affiliated with or endorsed by NASA/)).toBeTruthy();
  });
});

describe("data-source banner", () => {
  it("labels mock data loudly", () => {
    useApp.setState({ manifest: manifest({ data_source: "mock" }) });
    render(<DataSourceBanner />);
    expect(screen.getByRole("note").textContent).toMatch(/MOCK DATA/);
  });
});

describe("alt text (implementation.md §6.7)", () => {
  it("describes what is shown from the manifest only", () => {
    const m = manifest();
    const full = m.bins["6"]!.filter((b) => b.status === "full");
    expect(altText(m, 6, full)).toMatch(/^Band 6 stacks of WISE 0855−0714 from 2 visits \(\w+ 2025–\w+ 2026\), north up, east left\.$/);
  });
});

describe("Mover search limit (Barnard's 10.39″/yr is above the default 10″/yr)", () => {
  it("says when the target moves faster than the limit and offers a limit that covers it", () => {
    vi.spyOn(currentHooks, "useFeature").mockImplementation(() => ({ level: "dev", enabled: true, unvalidated: true }));
    const m = manifest();
    m.target = { ...m.target!, name: "Barnard's Star", pm: [-801.551, 10362.394] };
    useApp.setState({ manifest: m });
    const client = new QueryClient();
    render(<QueryClientProvider client={client}><MoversPanel /></QueryClientProvider>);
    expect(screen.getByText(/moves 10\.39″\/yr/)).toBeTruthy();
    fireEvent.click(screen.getByText("Use 13″/yr"));
    expect(screen.queryByText(/moves 10\.39″\/yr/)).toBeNull();
    client.clear();
  });
});

describe("OverlayLayer asteroid markers", () => {
  it("draws transients without labels and reports a clicked asteroid-layer marker; catalogue stars are not clickable", () => {
    vi.stubGlobal("ResizeObserver", class { observe() {} disconnect() {} });
    const onPick = vi.fn();
    const grid = manifest().grid;
    const { container } = render(<OverlayLayer grid={grid} transform={null} onPick={onPick} sources={[
      { id: "t0", ra: 0, dec: 0, cat: "transient", frame: "f1", npix: 3 },
      { id: "(433) Eros", ra: 0.001, dec: 0.001, cat: "sso", label: "(433) Eros (SPHEREx observer)", mag: 12 },
      { id: "Gaia 1", ra: 0.002, dec: 0.002, cat: "gaia" },
    ]} />);
    expect(container.querySelector(".ov-transient text")).toBeNull();
    expect(container.querySelector(".ov-sso text")?.textContent).toBe("(433) Eros");
    expect(container.querySelector(".ov-gaia.pickable")).toBeNull();
    fireEvent.click(container.querySelector(".ov-transient")!);
    expect(onPick).toHaveBeenCalledWith(expect.objectContaining({ id: "t0", frame: "f1" }));
    vi.unstubAllGlobals();
  });
});
