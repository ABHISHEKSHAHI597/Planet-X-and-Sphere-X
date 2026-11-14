/**
 * Blink player rules (implementation.md §6.3): visit stacks by default; partial visits skipped
 * unless partial=1 (workflow.md §11.2: never show partial visits as full epochs); ping-pong at 2 fps.
 */
import type { TimeBinInfo } from "../api/types";

export function playableBins(bins: TimeBinInfo[] | undefined, includePartial: boolean): TimeBinInfo[] {
  if (!bins) return [];
  return [...bins].filter((b) => includePartial || b.status !== "partial").sort((a, b) => a.mjd_mean - b.mjd_mean);
}

export interface PlayerPos { i: number; dir: 1 | -1 }

/** Next frame: ping-pong (1 2 3 2 1 2 …). With 1 frame, stays put. */
export function nextFrame(p: PlayerPos, n: number): PlayerPos {
  if (n <= 1) return { i: 0, dir: 1 };
  let { i, dir } = p;
  if (i + dir >= n || i + dir < 0) dir = (dir === 1 ? -1 : 1);
  i = Math.min(n - 1, Math.max(0, i + dir));
  return { i, dir };
}

/** Manual stepping wraps around (← / →). */
export function stepFrame(i: number, n: number, delta: number): number {
  if (n <= 0) return 0;
  return ((i + delta) % n + n) % n;
}

/** Index of a bin id in a list, or 0. */
export function indexOfBin(list: TimeBinInfo[], id: string | null): number {
  if (!id) return 0;
  const k = list.findIndex((b) => b.id === id);
  return k < 0 ? 0 : k;
}

/** The previous frame for "hold B to compare": the one before the current, wrapping. */
export function compareIndex(i: number, n: number): number {
  return n <= 1 ? i : stepFrame(i, n, -1);
}

/** Default (a, b) pair for the difference view: first and last full visits. */
export function defaultDiffPair(bins: TimeBinInfo[]): [string, string] | null {
  const full = bins.filter((b) => b.status === "full").sort((a, b) => a.mjd_mean - b.mjd_mean);
  return full.length >= 2 ? [full[0]!.id, full[full.length - 1]!.id] : null;
}
