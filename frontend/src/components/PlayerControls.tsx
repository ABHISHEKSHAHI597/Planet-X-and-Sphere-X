/**
 * Player and display controls (implementation.md §6.1/§6.3). Keyboard: space play/pause, ←/→ step,
 * 1–6 bands, D diff, S side-by-side, O onion-skin, hold B to compare (see App.tsx).
 */
import { selectBands, useCurrent, useFeature } from "../hooks/useCurrent";
import { BAND_IDS, BANDS } from "../lib/constants";
import { stepFrame } from "../lib/player";
import { useApp } from "../state/store";
import type { Mode } from "../state/url";
import { CANONICAL_BITS, FLAG_INFO, INFO_FLAGS } from "../content/flags";
import { UnvalidatedBadge } from "./Badges";
import { Icon } from "./Icon";

export function PlayerControls({ compact = false }: { compact?: boolean }) {
  const view = useApp((s) => s.view);
  const setView = useApp((s) => s.setView);
  const playing = useApp((s) => s.playing);
  const setPlaying = useApp((s) => s.setPlaying);
  const setFrame = useApp((s) => s.setFrame);
  const m = useApp((s) => s.manifest);
  const cur = useCurrent();
  const fDiff = useFeature("diff");
  const fTrack = useFeature("track");
  const fOver = useFeature("overlays");
  const fWise = useFeature("wise_layer");
  const fAstro = useFeature("astrometry");
  const fFlip = useFeature("flip");
  const fScrub = useFeature("scrubber");
  const fRgb = useFeature("rgb");
  const n = cur.bins.length;
  const available = new Set(m?.bands ?? []);
  const toggle = (list: string[], x: string) => (list.includes(x) ? list.filter((y) => y !== x) : [...list, x]);
  const modes: { id: Mode; label: string; hidden?: boolean; unvalidated?: boolean }[] = [
    { id: "blink", label: "Blink" }, { id: "onion", label: "Onion-skin" }, { id: "side", label: "Side by side" },
    { id: "diff", label: "Difference", hidden: !fDiff.enabled, unvalidated: fDiff.unvalidated },
    { id: "flip", label: "Spectral flipbook", hidden: !fFlip.enabled && !fScrub.enabled, unvalidated: fFlip.unvalidated || fScrub.unvalidated },
  ];
  const flagNames = Object.keys(m?.flags.bits ?? CANONICAL_BITS);
  const offered = view.ui === "expert" ? flagNames : (INFO_FLAGS as readonly string[]).filter((f) => flagNames.includes(f));

  const flagsOn = view.flags.filter((f) => offered.includes(f)).length;
  // The flipbook has its own player above the image; here the group only picks the visit (cube planes use it) and the speed.
  const flip = view.mode === "flip";

  return (
    <div className={`controls rail${compact ? " compact" : ""}`} role="toolbar" aria-label="Blink controls">
      <div className="group transport">
        <span className="group-label">{flip ? <>Visit <span className="lam">flipbook plays above</span></> : "Playback"}</span>
        <div className="transport-row">
          <button className="icon-btn" aria-label={flip ? "Previous visit" : "Previous frame (←)"} title={flip ? "Previous visit" : "Previous frame (←)"} onClick={() => { setPlaying(false); setFrame(stepFrame(cur.index, n, -1)); }} disabled={n < 2}><Icon name="prev" size={15} /></button>
          {!flip && (
            <button className="play" aria-label={playing ? "Pause (space)" : "Play (space)"} title={playing ? "Pause (space)" : "Play (space)"} aria-pressed={playing} onClick={() => setPlaying(!playing)} disabled={n < 2}>
              <Icon name={playing ? "pause" : "play"} size={18} />
            </button>
          )}
          <button className="icon-btn" aria-label={flip ? "Next visit" : "Next frame (→)"} title={flip ? "Next visit" : "Next frame (→)"} onClick={() => { setPlaying(false); setFrame(stepFrame(cur.index, n, 1)); }} disabled={n < 2}><Icon name="next" size={15} /></button>
          <span className="counter" aria-live="polite"><b>{n ? cur.index + 1 : 0}</b><span>/{n}</span></span>
          <label className="fps"><span className="micro">fps</span>
            <select value={view.fps} onChange={(e) => setView({ fps: Number(e.target.value) })}>
              {[...new Set([0.5, 1, 2, 4, 8, view.fps])].sort((x, y) => x - y).map((f) => <option key={f} value={f}>{f}</option>)}
            </select>
          </label>
        </div>
      </div>

      <div className="group">
        <span className="group-label" id="mode-label">Mode</span>
        <div className="modes segmented" role="radiogroup" aria-labelledby="mode-label">
          {modes.filter((x) => !x.hidden).map((x) => (
            <button key={x.id} role="radio" aria-checked={view.mode === x.id} className={view.mode === x.id ? "on" : ""}
              onClick={() => setView({ mode: x.id })}>
              <span>{x.label}</span>{x.unvalidated && <UnvalidatedBadge />}
            </button>
          ))}
        </div>
      </div>

      <div className="group">
        <span className="group-label" id="band-label">Band <span className="lam">{BANDS[cur.band]![0]}–{BANDS[cur.band]![1]} µm</span></span>
        <div className="bands" role="radiogroup" aria-labelledby="band-label">
          {BAND_IDS.map((b) => (
            <button key={b} role="radio" aria-checked={cur.band === b} className={cur.band === b ? "on" : ""} data-band={b}
              disabled={m ? !available.has(b) : false}
              title={`Band ${b}: ${BANDS[b]![0]}–${BANDS[b]![1]} µm${m && !available.has(b) ? " (no frames)" : ""}`}
              onClick={() => selectBands(String(b))}>
              <b>{b}</b><span className="sr-only"> ({BANDS[b]![0]}–{BANDS[b]![1]} µm)</span>
            </button>
          ))}
        </div>
        <div className="band-scale" aria-hidden="true"><span>0.75 µm</span><span>5.0 µm</span></div>
        {fRgb.enabled && (
          <label className="rgb" title="Colour composites: three band stacks, or wavelength-range presets built from the per-pixel cube">
            <span className="micro">RGB</span>
            <select value={view.bands.startsWith("rgb:") ? view.bands : ""} onChange={(e) => selectBands(e.target.value || String(cur.band))}>
              <option value="">off</option>
              <option value="rgb:4,5,6">bands 4,5,6 (thermal)</option>
              <option value="rgb:1,2,3">bands 1,2,3</option>
              <option value="rgb:methane">methane</option>
              <option value="rgb:ice">ice</option>
            </select>
            {fRgb.unvalidated && <UnvalidatedBadge />}
          </label>
        )}
      </div>

      {!compact && (
        <>
          <div className="group display">
            <span className="group-label">Display</span>
            <div className="field-row">
              <label><span className="micro">stretch</span>
                <select value={view.stretch} onChange={(e) => setView({ stretch: e.target.value })}>
                  <option value="asinh:8">asinh</option><option value="lin">linear</option>
                  <option value="sqrt">sqrt</option><option value="log:100">log</option>
                  {!["asinh:8", "lin", "sqrt", "log:100"].includes(view.stretch) && <option value={view.stretch}>{view.stretch}</option>}
                </select>
              </label>
              <label><span className="micro">colours</span>
                <select value={view.cmap} onChange={(e) => setView({ cmap: e.target.value as typeof view.cmap })}>
                  <option value="gray">gray</option><option value="magma">magma</option><option value="cividis">cividis</option>
                </select>
              </label>
            </div>
            <label className="check" title="Partial visits have only a few frames; they are shallower and shown hatched on the timeline.">
              <input type="checkbox" checked={view.partial} onChange={(e) => setView({ partial: e.target.checked })} /> partial visits
            </label>
          </div>

          <div className="group overlays" aria-label="Overlays">
            <span className="group-label">Overlays</span>
            {fTrack.enabled && (
              <label className="check" title="Where the catalogue says the target is at each visit (proper motion + parallax).">
                <input type="checkbox" checked={view.ov.includes("track")} onChange={() => setView({ ov: toggle(view.ov, "track") })} />
                predicted track{fTrack.unvalidated && <UnvalidatedBadge />}
              </label>
            )}
            {fAstro.enabled && (
              <label className="check" title="Drawn ×10 from the Astrometry card's fit: run “Measure proper motion” there first."><input type="checkbox" checked={view.ov.includes("vec")} onChange={() => setView({ ov: toggle(view.ov, "vec") })} />
                fitted motion{fAstro.unvalidated && <UnvalidatedBadge />}</label>
            )}
            {fOver.enabled && (["gaia", "simbad"] as const).map((c) => (
              <label key={c} className="check"><input type="checkbox" checked={view.ov.includes(c)} onChange={() => setView({ ov: toggle(view.ov, c) })} />
                {c === "gaia" ? "Gaia DR3" : "SIMBAD"}</label>
            ))}
            {fWise.enabled && (
              <label className="check" title="AllWISE catalogue positions as WISE measured them around 2010, not moved to this visit. A source that has moved since then sits away from its square.">
                <input type="checkbox" checked={view.ov.includes("wise")} onChange={() => setView({ ov: toggle(view.ov, "wise") })} />
                WISE (2010){fWise.unvalidated && <UnvalidatedBadge />}</label>
            )}
            {fOver.enabled && (
              <label className="check" title="Known asteroids (SkyBoT, refined with Horizons for SPHEREx) and unvetted single-exposure transients.">
                <input type="checkbox" checked={view.ov.includes("sso")} onChange={() => setView({ ov: toggle(view.ov, "sso") })} />
                asteroids<UnvalidatedBadge /></label>
            )}
            <label className="check"><input type="checkbox" checked={view.ov.includes("crosshair")} onChange={() => setView({ ov: toggle(view.ov, "crosshair") })} /> crosshair</label>
          </div>

          {view.ui === "expert" && (
            <div className="group advanced" title="These change what the server computes: a new view is built (minutes the first time).">
              <span className="group-label">Time axis and limits</span>
              <div className="field-row">
                <label><span className="micro">axis</span>
                  <select value={view.axis} onChange={(e) => setView({ axis: e.target.value, t: null })} aria-label="Time axis">
                    {[...new Set(["auto", "visit", "survey", "bin:14d", "bin:7d", "bin:1d", view.axis])].map((a) => (
                      <option key={a} value={a}>{a === "auto" ? `auto (${m?.axis ?? "…"})` : a}</option>
                    ))}
                  </select>
                </label>
                <label><span className="micro">limits</span>
                  <select value={view.lim} onChange={(e) => setView({ lim: e.target.value })} aria-label="Shared display limits">
                    {[...new Set(["zscale", "p99.5", "p99", view.lim])].map((l) => <option key={l} value={l}>{l}</option>)}
                  </select>
                </label>
              </div>
              {view.axis === "bin:1d" && <p className="small hint">Per-day bins with a field of at least 30′ are what the distant-body search needs.</p>}
            </div>
          )}

          <details className="group flags" aria-label="Flag layers" open={offered.length <= 6 || undefined}>
            <summary className="group-label">
              <Icon name="chevron" size={12} className="disclosure" />Flag layers
              <span className="count">{flagsOn ? `${flagsOn} on` : `${offered.length}`}</span>
            </summary>
            <div className="flag-list">
              {offered.map((f) => (
                <label key={f} className="check" title={m?.flags.info[f] ?? FLAG_INFO[f] ?? f}>
                  <input type="checkbox" checked={view.flags.includes(f)} onChange={() => setView({ flags: toggle(view.flags, f) })} /> {f}
                </label>
              ))}
            </div>
          </details>
        </>
      )}
    </div>
  );
}
