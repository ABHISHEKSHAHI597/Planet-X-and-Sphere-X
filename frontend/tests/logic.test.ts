import { describe, expect, it } from "vitest";
import type { TimeBinInfo } from "../src/api/types";
import { feature } from "../src/lib/features";
import { compareIndex, defaultDiffPair, nextFrame, playableBins, stepFrame } from "../src/lib/player";
import { validateMessage } from "../src/components/EmbedApp";
import { schemaCompatible } from "../src/api/formats";

const bin = (id: string, status: TimeBinInfo["status"], mjd: number): TimeBinInfo => ({
  id, band: 6, status, mjd_mean: mjd, mjd_min: mjd - 1, mjd_max: mjd + 1, surveys: [1], label: id, n_frames: status === "partial" ? 3 : 18, n_visit_frames: 100,
});
// WISE 0855 band 6 shape (validation/G1-time-model): partial · full · partial · full
const WISE = [bin("V3", "partial", 3), bin("V1", "partial", 1), bin("V2", "full", 2), bin("V4", "full", 4)];

describe("player rules", () => {
  it("skips partial visits unless partial=1, in time order", () => {
    expect(playableBins(WISE, false).map((b) => b.id)).toEqual(["V2", "V4"]);
    expect(playableBins(WISE, true).map((b) => b.id)).toEqual(["V1", "V2", "V3", "V4"]);
  });
  it("ping-pongs", () => {
    let p = { i: 0, dir: 1 as 1 | -1 };
    const seq: number[] = [];
    for (let k = 0; k < 8; k++) { p = nextFrame(p, 3); seq.push(p.i); }
    expect(seq).toEqual([1, 2, 1, 0, 1, 2, 1, 0]);
    expect(nextFrame({ i: 0, dir: 1 }, 1).i).toBe(0);
  });
  it("steps with wrap-around and compares with the previous frame", () => {
    expect(stepFrame(0, 3, -1)).toBe(2);
    expect(stepFrame(2, 3, 1)).toBe(0);
    expect(compareIndex(0, 3)).toBe(2);
  });
  it("default diff pair is first and last FULL visit", () => {
    expect(defaultDiffPair(WISE)).toEqual(["V2", "V4"]);
    expect(defaultDiffPair([bin("V1", "full", 1), bin("V2", "partial", 2)])).toBeNull();
  });
});

describe("feature flags (workflow.md §9.6)", () => {
  const rel = (features: Record<string, "off" | "dev" | "staging" | "on">, environment: "mock" | "staging" | "production" | "local") => ({ features, environment });
  it("a capability the backend does not list is off", () => {
    expect(feature(rel({}, "mock"), "diff").enabled).toBe(false);
    expect(feature(null, "diff").enabled).toBe(false);
  });
  it("production shows only accepted capabilities, whatever the level says", () => {
    expect(feature(rel({ diff: "staging" }, "production"), "diff").enabled).toBe(false);
    expect(feature(rel({ diff: "dev" }, "production"), "diff").enabled).toBe(false);
    expect(feature(rel({ diff: "on" }, "production"), "diff")).toEqual({ level: "on", enabled: true, unvalidated: false });
  });
  it("dev/staging levels are badged as unvalidated where visible", () => {
    expect(feature(rel({ diff: "staging" }, "staging"), "diff")).toEqual({ level: "staging", enabled: true, unvalidated: true });
    expect(feature(rel({ diff: "dev" }, "staging"), "diff").enabled).toBe(false);
    expect(feature(rel({ diff: "dev" }, "mock"), "diff").unvalidated).toBe(true);
  });
});

describe("embed postMessage validation (implementation.md §5.3)", () => {
  it("accepts well-formed messages only", () => {
    expect(validateMessage({ type: "parallax:goto", ra: 269.446, dec: 4.7707 })).toEqual({ type: "parallax:goto", ra: 269.446, dec: 4.7707 });
    expect(validateMessage({ type: "parallax:goto", ra: "269", dec: 4 })).toBeNull();
    expect(validateMessage({ type: "parallax:goto", ra: 400, dec: 4 })).toBeNull();
    expect(validateMessage({ type: "parallax:band", band: 7 })).toBeNull();
    expect(validateMessage({ type: "parallax:target", q: "x".repeat(101) })).toBeNull();
    expect(validateMessage({ type: "evil", payload: "<script>" })).toBeNull();
    expect(validateMessage("parallax:goto")).toBeNull();
    expect(validateMessage(null)).toBeNull();
  });
});

describe("schema versions (workflow.md §7.2)", () => {
  it("pre-1.0, a minor bump is breaking; from 1.0, only majors are", () => {
    expect(schemaCompatible("0.1.3", "0.1.0")).toBe(true);
    expect(schemaCompatible("0.2.0", "0.1.0")).toBe(false);
    expect(schemaCompatible("1.4.0", "1.0.0")).toBe(true);
    expect(schemaCompatible("2.0.0", "1.0.0")).toBe(false);
  });
});
