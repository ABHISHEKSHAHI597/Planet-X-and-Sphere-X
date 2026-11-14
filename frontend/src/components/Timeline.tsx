/**
 * Timeline (implementation.md §6.1, §4.2): full visits solid, partial visits hatched, fixed bins as
 * thin bars; labels show date range, survey(s), frame count and status. Click to jump.
 */
import { useEffect, useRef, useState } from "react";
import { useCurrent } from "../hooks/useCurrent";
import { mjdToDate } from "../lib/time";
import { useApp } from "../state/store";
import { FreshnessBadge } from "./Badges";

export function Timeline() {
  const m = useApp((s) => s.manifest);
  const view = useApp((s) => s.view);
  const setFrame = useApp((s) => s.setFrame);
  const setPlaying = useApp((s) => s.setPlaying);
  const cur = useCurrent();
  const list = useRef<HTMLOListElement>(null);
  const [overflowing, setOverflowing] = useState(false);
  const curId = cur.bin?.id;
  // Keep the current visit's button in view while playing: scroll the row only, never the page.
  useEffect(() => {
    const ol = list.current;
    if (!ol) return;
    setOverflowing(ol.scrollWidth > ol.clientWidth + 1);
    const el = ol.querySelector<HTMLElement>('[aria-current="true"]');
    if (!el) return;
    const left = el.getBoundingClientRect().left - ol.getBoundingClientRect().left + ol.scrollLeft, right = left + el.offsetWidth;
    if (left < ol.scrollLeft) ol.scrollLeft = left - 24;
    else if (right > ol.scrollLeft + ol.clientWidth) ol.scrollLeft = right - ol.clientWidth + 24;
  }, [curId, cur.allBins.length]);
  if (!m || !cur.allBins.length) return null;
  const all = cur.allBins;
  const t0 = Math.min(...all.map((b) => b.mjd_min)) - 10, t1 = Math.max(...all.map((b) => b.mjd_max)) + 10;
  const W = 1000, H = 46;
  const x = (t: number) => ((t - t0) / (t1 - t0)) * W;
  const years: number[] = [];
  for (let y = mjdToDate(t0).getUTCFullYear(); y <= mjdToDate(t1).getUTCFullYear() + 1; y++) years.push(y);
  const yMjd = (y: number) => Date.UTC(y, 0, 1) / 86400000 + 40587;

  return (
    <section className="timeline" aria-label="Timeline" data-band={cur.band}>
      <header className="timeline-head">
        <span className="group-label">Timeline</span>
        <span className="timeline-meta">{cur.bins.length} of {all.length} {m.axis === "visit" ? "visits" : "time bins"} in the blink · band {cur.band}</span>
        <FreshnessBadge />
      </header>
      <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" role="presentation">
        <defs>
          <pattern id="hatch" patternUnits="userSpaceOnUse" width="6" height="6" patternTransform="rotate(45)">
            <line x1="0" y1="0" x2="0" y2="6" className="hatch-line" />
          </pattern>
        </defs>
        <line x1={0} x2={W} y1={30} y2={30} className="axis" />
        {years.filter((y) => yMjd(y) > t0 && yMjd(y) < t1).map((y) => (
          <line key={y} x1={x(yMjd(y))} x2={x(yMjd(y))} y1={22} y2={38} className="tick" />
        ))}
        {all.map((b) => {
          const playIdx = cur.bins.findIndex((p) => p.id === b.id);
          const isCur = cur.bin?.id === b.id;
          const w = Math.max(4, x(b.mjd_max) - x(b.mjd_min));
          return (
            <rect key={b.id} x={x(b.mjd_min)} y={18} width={w} height={24}
              className={`bin ${b.status}${isCur ? " current" : ""}${playIdx < 0 ? " skipped" : ""}${cur.isReady(b.id) ? "" : " loading"}`}
              fill={b.status === "partial" ? "url(#hatch)" : undefined}
              onClick={() => { if (playIdx >= 0) { setPlaying(false); setFrame(playIdx); } }}>
              <title>{b.label}{playIdx < 0 ? " — hidden (partial visits off)" : ""}</title>
            </rect>
          );
        })}
      </svg>
      {/* year labels in HTML: the svg stretches (preserveAspectRatio="none"), which would distort text */}
      <div className="timeline-years" aria-hidden="true">
        {years.filter((y) => yMjd(y) > t0 && yMjd(y) < t1).map((y) => <span key={y} style={{ left: `${(x(yMjd(y)) / W) * 100}%` }}>{y}</span>)}
      </div>
      <ol className={`bin-list${overflowing ? " overflowing" : ""}`} ref={list}>
        {all.map((b) => {
          const playIdx = cur.bins.findIndex((p) => p.id === b.id);
          return (
            <li key={b.id}>
              <button className={`bin-chip ${b.status}${cur.bin?.id === b.id ? " current" : ""}`} disabled={playIdx < 0}
                aria-current={cur.bin?.id === b.id ? "true" : undefined}
                title={playIdx < 0 ? "Partial visit: turn on “partial visits” to include it" : b.label}
                onClick={() => { setPlaying(false); setFrame(playIdx); }}>
                {b.label}{!cur.isReady(b.id) && " (loading)"}
              </button>
            </li>
          );
        })}
      </ol>
      {!view.partial && all.some((b) => b.status === "partial") && (
        <p className="hint">Hatched: partial visits (few frames), hidden from the blink.</p>
      )}
    </section>
  );
}
