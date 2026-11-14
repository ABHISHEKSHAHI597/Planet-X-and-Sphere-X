import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { binSpectrum, hampelOutliers, layoutLabels, quantile, robustRange, weightedMedian, type SpecInput } from "../src/lib/spectrum";
import { SpectrumChart } from "../src/components/SpectrumChart";
import { PhotometricMatchCard } from "../src/components/PhotometricMatch";
import type { PhotometricMatch, SpectrumRow } from "../src/api/types";

const row = (lam: number, flux: number, err: number, release = "qr3", detector = 6): SpecInput => ({ lam, dlam: 0.005, flux, err, release, detector });

// deterministic pseudo-noise
const rnd = (() => { let s = 12345; return () => ((s = (s * 1103515245 + 12345) % 2 ** 31) / 2 ** 31); })();
const gauss = () => Math.sqrt(-2 * Math.log(rnd() + 1e-12)) * Math.cos(2 * Math.PI * rnd());

describe("robust spectrum statistics", () => {
  it("quantile and weighted median", () => {
    expect(quantile([1, 2, 3, 4], 0.5)).toBe(2.5);
    expect(weightedMedian([1, 2, 100], [1, 1, 1])).toBe(2);
    expect(weightedMedian([1, 2, 100], [1, 1, 10])).toBe(100);
  });

  it("bins per release and never mixes QR2 with QR3", () => {
    const rows = [row(4.70, 100, 5), row(4.701, 102, 5), row(4.70, 93, 5, "qr2"), row(4.701, 94, 5, "qr2")];
    const b = binSpectrum(rows);
    expect(b.map((x) => x.release).sort()).toEqual(["qr2", "qr3"]);
    expect(b.find((x) => x.release === "qr3")!.flux).toBeCloseTo(101, 6);
  });

  it("σ-clips a wild point that a plain mean would follow", () => {
    const rows = Array.from({ length: 12 }, () => row(4.7, 100 + 5 * gauss(), 5)).concat([row(4.7, 2000, 5)]);
    const [b] = binSpectrum(rows);
    expect(b!.nClipped).toBe(1);
    expect(Math.abs(b!.flux - 100)).toBeLessThan(5);
    const naive = rows.reduce((s, r) => s + r.flux, 0) / rows.length;
    expect(Math.abs(naive - 100)).toBeGreaterThan(100);
  });

  it("one over-confident point cannot hijack the clipping centre", () => {
    const rows = Array.from({ length: 8 }, () => row(4.7, 50 + 300 * gauss(), 900)).concat([row(4.7, 9000, 5)]);
    const [b] = binSpectrum(rows);
    expect(b!.nClipped).toBe(1);
    expect(Math.abs(b!.flux)).toBeLessThan(1000);
  });

  it("tolerates rows without a release (older cached responses)", () => {
    const rows = [{ lam: 4.7, dlam: 0.01, flux: 10, err: 1, detector: 6 }, { lam: 4.7, dlam: 0.01, flux: 12, err: 1, detector: 6, release: null }];
    const b = binSpectrum(rows);
    expect(b).toHaveLength(1);
    expect(b[0]!.release).toBe("unknown");
  });

  it("Hampel despiking removes a lone wild frame that in-bin clipping cannot (one frame per bin)", () => {
    const rows = Array.from({ length: 60 }, (_, i) => row(4.42 + i * 0.0098, 1000 * Math.pow(4.42 + i * 0.0098, -2) + 0.5 * gauss(), 1.5));
    rows[30] = { ...rows[30]!, flux: rows[30]!.flux * 9 };
    const out = hampelOutliers(rows);
    expect(out.filter(Boolean)).toHaveLength(1);
    expect(out[30]).toBe(true);
    const single = binSpectrum([rows[30]!]);
    expect(single[0]!.nClipped).toBe(0);                      // teeth: alone in its bin, clipping cannot see it
  });

  it("Hampel never rejects honest points on a faint, noisy spectrum (errors ≫ flux)", () => {
    const rows = Array.from({ length: 400 }, (_, i) => row(0.75 + i * 0.011, 5 + 1000 * gauss(), 1000, i % 2 ? "qr2" : "qr3", 1 + Math.floor(i / 67)));
    expect(hampelOutliers(rows).filter(Boolean).length).toBeLessThanOrEqual(1);
  });

  it("inflates the error by √χ²ᵣ when frames scatter more than their errors", () => {
    const rows = Array.from({ length: 20 }, (_, i) => row(4.7, 100 + (i % 2 ? 10 : -10), 2));
    const [b] = binSpectrum(rows);
    expect(b!.chi2r).toBeGreaterThan(10);
    expect(b!.err).toBeGreaterThan(3 * b!.errFormal);
  });

  it("error bars do not set the y-range; the binned spectrum always fits", () => {
    const vals = Array.from({ length: 500 }, () => 100 + 3 * gauss());
    vals.push(5000, -4000);                                     // two wild points
    const [lo, hi] = robustRange(vals, [[90, 112]]);
    expect(lo).toBeLessThanOrEqual(90);
    expect(hi).toBeGreaterThanOrEqual(112);
    expect(hi - lo).toBeLessThan(60);                         // not stretched to ±4000
  });

  it("lays feature labels out without overlaps", () => {
    const items = [{ x: 10, w: 60 }, { x: 20, w: 60 }, { x: 30, w: 60 }, { x: 200, w: 30 }, { x: 40, w: 60 }];
    const lanes = layoutLabels(items, 3);
    expect(lanes).toEqual([0, 1, 2, 0, -1]);
    for (let i = 0; i < items.length; i++) for (let j = i + 1; j < items.length; j++) {
      if (lanes[i] === lanes[j] && lanes[i]! >= 0) {
        const [a, b] = items[i]!.x < items[j]!.x ? [items[i]!, items[j]!] : [items[j]!, items[i]!];
        expect(a.x + a.w).toBeLessThanOrEqual(b.x);
      }
    }
  });
});

const sRow = (lam: number, flux: number, err: number, release: string): SpectrumRow => ({
  lam, dlam: 0.005, flux, err, mjd: 61000, visit: "V1", detector: 6, flags: [], rchi2: 1, contaminated: false, release,
});

describe("SpectrumChart", () => {
  it("renders binned series per release with a legend and counts off-scale points", () => {
    const rows: SpectrumRow[] = [];
    for (let i = 0; i < 200; i++) rows.push(sRow(4.42 + (0.58 * i) / 200, 50 + 2 * gauss(), 900, i % 2 ? "qr2" : "qr3"));
    rows.push(sRow(4.6, 9000, 5, "qr3"));
    const { container } = render(<SpectrumChart rows={rows} features={[{ lam: 4.67, label: "CO" }]} />);
    expect(screen.getByRole("img", { name: /Spectrum/ })).toBeTruthy();
    expect(container.querySelectorAll(".binned").length).toBe(2);
    expect(container.textContent).toContain("QR2 binned");
    expect(container.textContent).toContain("QR3 binned");
    expect(container.querySelector(".offscale")).toBeTruthy();
  });
  it("says so when there is nothing to plot", () => {
    render(<SpectrumChart rows={[]} />);
    expect(screen.getByText("No data points.")).toBeTruthy();
  });
});

describe("PhotometricMatchCard", () => {
  const pm: PhotometricMatch = {
    applied: true, cross_release: true, scales_a: ["qr3"], scales_b: ["qr2"], method: "in-situ", note: "QR2 visit matched to QR3 in situ.",
    scale: 1.0752, scale_err: 0.0011, n_sources: 12, static_z_before: 41.2, static_z_after: 0.9, tau: 0.004,
    bins: [{ lam: 4.5, scale: 1.08, err: 0.002, shrink: 0.4, offset: 0, n_pix: 100, n_sources: 12, pooled: false, raw: 1.081 },
      { lam: 4.9, scale: 1.07, err: 0.002, shrink: 0.4, offset: 0, n_pix: 100, n_sources: 12, pooled: false, raw: 1.069 }],
  };
  it("frames a cross-release difference as positions-only and shows the evidence", () => {
    const { container } = render(<PhotometricMatchCard pm={pm} />);
    expect(container.textContent).toContain("Cross-release difference (QR3 − QR2)");
    expect(container.textContent).toContain("brightness not compared");
    expect(container.textContent).toContain("41.2σ → 0.9σ");
    expect(container.querySelector(".photmatch.cross")).toBeTruthy();
    expect(container.querySelectorAll(".pm-spark .fit").length).toBe(2);
  });
  it("shows a failed or absent fit as text only", () => {
    const { container } = render(<PhotometricMatchCard pm={{ applied: false, cross_release: false, scales_a: ["qr3"], scales_b: ["qr3"], method: "m", note: "No photometric check: too few sources" }} />);
    expect(container.textContent).toContain("too few sources");
    expect(container.querySelector(".pm-spark")).toBeNull();
  });
});
