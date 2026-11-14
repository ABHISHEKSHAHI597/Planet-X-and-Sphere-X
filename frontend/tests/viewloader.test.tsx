import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { cleanup, renderHook } from "@testing-library/react";
import { api } from "../src/api/client";
import type { ViewManifest } from "../src/api/types";
import { MANIFEST_REFRESH_MS, useViewLoader } from "../src/hooks/useViewLoader";
import { useApp } from "../src/state/store";
import { DEFAULTS } from "../src/state/url";

type Ev = Record<string, unknown> & { type: string };
let emit: (e: Ev) => void = () => {};
const closed = vi.fn();

beforeEach(() => {
  vi.useFakeTimers();
  useApp.setState({ manifest: null, view: { ...DEFAULTS, q: "Barnard's Star" }, ready: new Set() });
  vi.spyOn(api, "createView").mockResolvedValue({ status: "queued", job_id: "j", key: "k" } as never);
  vi.spyOn(api, "manifest").mockResolvedValue({ key: "k", stacks: [], bins: {}, limits: {} } as unknown as ViewManifest);
  vi.spyOn(api, "jobEvents").mockImplementation(((_id: string, on: (e: Ev) => void) => {
    emit = on;
    return { close: closed };
  }) as never);
});
afterEach(() => { cleanup(); vi.useRealTimers(); vi.restoreAllMocks(); useApp.setState({ manifest: null, view: DEFAULTS, ready: new Set() }); });

it("re-reads the manifest while stacks land, throttled, so first visits get real display limits", async () => {
  renderHook(() => useViewLoader());
  await vi.advanceTimersByTimeAsync(0);
  const reads = () => vi.mocked(api.manifest).mock.calls.length;
  emit({ type: "planned", n: 10 });
  expect(reads()).toBe(1);
  for (const bin of ["V1", "V2", "V3"]) emit({ type: "stack_ready", bin, band: 6 });   // a burst
  expect(reads()).toBe(1);
  expect(useApp.getState().ready.has("V3|6")).toBe(true);                               // drawable at once
  await vi.advanceTimersByTimeAsync(MANIFEST_REFRESH_MS);
  expect(reads()).toBe(2);                                                               // one trailing read
  emit({ type: "stack_ready", bin: "V4", band: 6 });
  emit({ type: "done", key: "k" });
  expect(reads()).toBe(3);                                                               // done reads at once
  await vi.advanceTimersByTimeAsync(MANIFEST_REFRESH_MS * 2);
  expect(reads()).toBe(3);                                                               // and cancels the pending one
  expect(closed).toHaveBeenCalled();
});

it("does not re-post the view when only the band or partial visits change (audit B-03)", async () => {
  renderHook(() => useViewLoader());
  await vi.advanceTimersByTimeAsync(0);
  expect(vi.mocked(api.createView)).toHaveBeenCalledTimes(1);
  for (const bands of ["5", "4", "3", "2", "1", "6", "rgb:4,5,6"]) {
    useApp.getState().setView({ bands });
    await vi.advanceTimersByTimeAsync(0);
  }
  useApp.getState().setView({ partial: true });
  await vi.advanceTimersByTimeAsync(0);
  expect(vi.mocked(api.createView)).toHaveBeenCalledTimes(1);
  useApp.getState().setView({ fov: 12 });                                                // a compute parameter
  await vi.advanceTimersByTimeAsync(0);
  expect(vi.mocked(api.createView)).toHaveBeenCalledTimes(2);
  expect(vi.mocked(api.createView).mock.calls[1]![0]).toMatchObject({ bands: "rgb:4,5,6", partial: "1", fov: "12" });
});

it("keeps a failed job's message and closes the stream instead of letting it replay (audit B-04)", async () => {
  renderHook(() => useViewLoader());
  await vi.advanceTimersByTimeAsync(0);
  closed.mockClear();
  emit({ type: "planned", n: 3 });
  emit({ type: "error", message: "job timed out after 300 s" });
  expect(closed).toHaveBeenCalled();
  expect(useApp.getState().error).toBe("job timed out after 300 s");
  expect(useApp.getState().progress.phase).toBe("error");
});
