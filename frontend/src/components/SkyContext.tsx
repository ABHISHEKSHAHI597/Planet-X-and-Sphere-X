/**
 * Sky context (P1-4, implementation.md §6.6): Aladin Lite v3, lazy-loaded in its own chunk. Its FOV
 * follows the viewer and the current cutout footprint is drawn. Catalogue markers come from OUR
 * /overlays endpoint, propagated server-side to the visit epoch, because Aladin's own catalogue
 * markers sit at the catalogue epoch. Aladin fetches only HiPS tiles, from CDS or a listed mirror (workflow.md §3).
 *
 * CDS can be slow or down (its MocServer answered 503 and every alasky mirror timed out on 2026-11-09).
 * Aladin then paints a grey field and can stall the page, so we never hand it an unreachable survey:
 * each survey is resolved to a base URL that answered `<url>/properties` (direct path on each mirror
 * first, then a MocServer lookup), and Aladin is created only once one does. Otherwise the panel says so
 * and offers a retry.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import type { AladinInstance, Overlay } from "aladin-lite";
import { useCurrent, useFeature } from "../hooks/useCurrent";
import { pixelToSky } from "../lib/wcs";
import { useApp } from "../state/store";

/** id: the CDS HiPS identifier; path: its directory on the alasky mirrors; mirrors: other sites serving the same HiPS
 *  (CDS's "List of available image HiPS", 2026-11-09). That day alasky answered 404 for every survey path and for its
 *  MocServer, and alaskybis timed out, so every survey looked "unavailable"; the mirrors below answered with CORS. */
export const HIPS = [
  { id: "CDS/P/2MASS/color", path: "2MASS/Color", label: "2MASS colour",
    mirrors: ["https://skies.esac.esa.int/2MASSColor", "https://hips.china-vo.org/m/CDS_P_2MASS_color", "https://casda.csiro.au/hips/2MASS/Color"] },
  { id: "CDS/P/allWISE/color", path: "AllWISE/RGB-W4-W2-W1", label: "AllWISE colour",
    mirrors: ["https://skies.esac.esa.int/AllWISEColor", "https://hips.china-vo.org/m/CDS_P_allWISE_color"] },
  // No mirror lists unWISE: it works only while alasky serves it.
  { id: "CDS/P/unWISE/color-W2-W1W2-W1", path: "unWISE/color-W2-W1W2-W1", label: "unWISE W1/W2 (CDS only)", mirrors: [] },
  { id: "CDS/P/DSS2/color", path: "DSS/DSSColor", label: "DSS2 colour",
    mirrors: ["https://skies.esac.esa.int/DSSColor", "https://stpubdata.s3.us-east-1.amazonaws.com/mast/skybackgrounds/DSSColor",
      "https://casda.csiro.au/hips/DSS2/color", "https://hips.china-vo.org/m/CDS_P_DSS2_color"] },
  // The only mirrored Pan-STARRS colour HiPS is i-r-g (STScI MAST); the z-zg-g composite was alasky-only.
  { id: "CDS/P/PanSTARRS/DR1/color-i-r-g", path: "Pan-STARRS/DR1/color-i-r-g", label: "Pan-STARRS",
    mirrors: ["https://stpubdata.s3.us-east-1.amazonaws.com/mast/skybackgrounds/PanSTARRS"] },
];
export const CDS_MIRRORS = ["https://alasky.cds.unistra.fr", "https://alaskybis.cds.unistra.fr"];
const PROBE_MS = 5000;

/** render.BLINK25_LABEL, verbatim (implementation.md §4.13). */
export const BLINK25_LABEL = "different telescopes, positions only";
/** The "lite" 25-year blink of implementation.md §4.13: archival HiPS layers in epoch order. The SPHEREx
 * epoch is the main viewer. Survey epochs are the surveys' nominal spans, not per-tile dates. */
export const BLINK25_LITE = [
  { id: "CDS/P/2MASS/color", label: "2MASS (1997–2001)" },
  { id: "CDS/P/allWISE/color", label: "AllWISE (2010–2011)" },
];

async function answers(base: string): Promise<boolean> {
  try {
    const r = await fetch(`${base.replace(/\/$/, "")}/properties`, { signal: AbortSignal.timeout(PROBE_MS) });
    return r.ok;
  } catch {
    return false;
  }
}

/** First of several candidates that resolves, or null when all fail (Promise.any without the ES2021 lib). */
function firstOf(candidates: Promise<string | null>[]): Promise<string | null> {
  return new Promise((resolve) => {
    let left = candidates.length;
    if (!left) resolve(null);
    for (const c of candidates) c.then((v) => { if (v) resolve(v); else if (--left === 0) resolve(null); }, () => { if (--left === 0) resolve(null); });
  });
}

const resolved = new Map<string, string>();   // survey id → base URL that answered (successes only, per page load)

/** A reachable base URL for a survey, or null when CDS does not answer. */
export async function resolveHips(id: string): Promise<string | null> {
  const hit = resolved.get(id);
  if (hit) return hit;
  const h = HIPS.find((x) => x.id === id);
  // alasky first, then the other sites that mirror the survey: the first to answer wins.
  const direct = firstOf((h ? [...CDS_MIRRORS.map((m) => `${m}/${h.path}`), ...h.mirrors] : []).map(async (u) => ((await answers(u)) ? u : null)));
  // In parallel, ask the MocServer where the survey lives (covers a moved directory or an id not in HIPS).
  const viaMoc = firstOf(CDS_MIRRORS.map(async (m) => {
    try {
      const r = await fetch(`${m}/MocServer/query?get=record&fmt=json&ID=${encodeURIComponent(id)}`, { signal: AbortSignal.timeout(PROBE_MS) });
      if (!r.ok) return null;
      const rec = (await r.json()) as { hips_service_url?: string }[] | { hips_service_url?: string };
      const u = (Array.isArray(rec) ? rec[0] : rec)?.hips_service_url;
      return u && (await answers(u)) ? u : null;
    } catch {
      return null;
    }
  }));
  // Prefer the direct path; take the MocServer answer only if the direct path fails. Bounded by ~2 × PROBE_MS.
  const url = (await direct) ?? (await viaMoc);
  if (url) resolved.set(id, url);
  return url;
}

type Status = "checking" | "ready" | "unavailable";

export default function SkyContext() {
  const el = useRef<HTMLDivElement>(null);
  const al = useRef<{ a: AladinInstance; foot: Overlay } | null>(null);
  const [hips, setHips] = useState(HIPS[0]!.id);
  const [status, setStatus] = useState<Status>("checking");
  const [ready, setReady] = useState(false);   // Aladin created: re-run the positioning effect
  const [err, setErr] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);
  const m = useApp((s) => s.manifest);
  const fps = useApp((s) => s.view.fps);
  const f25 = useFeature("blink25");
  const [blink25, setBlink25] = useState(false);
  const [b25i, setB25i] = useState(0);
  useCurrent();

  useEffect(() => {
    if (!blink25 || status !== "ready") return;
    const id = setInterval(() => setB25i((i) => (i + 1) % BLINK25_LITE.length), 1000 / Math.min(fps, 2));
    return () => clearInterval(id);
  }, [blink25, fps, status]);
  useEffect(() => { if (blink25) setHips(BLINK25_LITE[b25i]!.id); }, [blink25, b25i]);

  const view = useCallback(() => {
    if (!m) return null;
    const [, nx] = m.grid.shape;
    return { ra: m.grid.crval[0], dec: m.grid.crval[1], fov: ((m.grid.pix_arcsec * nx) / 3600) * 2.2 };
  }, [m]);

  // Resolve the survey, then create Aladin (first time) or switch its survey.
  useEffect(() => {
    let live = true;
    if (!resolved.has(hips)) setStatus("checking");
    (async () => {
      const url = await resolveHips(hips);
      if (!live) return;
      if (!url) { setStatus("unavailable"); return; }
      try {
        if (al.current) {
          al.current.a.setImageSurvey(url);
        } else {
          const A = (await import("aladin-lite")).default;
          await A.init;
          if (!live || !el.current) return;
          const v = view();
          const a = A.aladin(el.current, { survey: url, fov: v?.fov ?? 0.2, target: v ? `${v.ra} ${v.dec}` : undefined,
            showReticle: true, showCooGrid: false, showFullscreenControl: false, showLayersControl: false, showGotoControl: false,
            showShareControl: false, showFrame: false, cooFrame: "ICRS" });
          const foot = A.graphicOverlay({ color: "#f2b33d", lineWidth: 2, name: "ParallaX view" });
          a.addOverlay(foot);
          al.current = { a, foot };
          setReady(true);
        }
        setErr(null);
        setStatus("ready");
      } catch (e) {
        setErr(String((e as Error)?.message ?? e));
        setStatus("unavailable");
      }
    })();
    return () => { live = false; };
  }, [hips, attempt, view]);

  // Follow the view: centre, field of view and the SPHEREx footprint.
  useEffect(() => {
    const x = al.current, v = view();
    if (!ready || !x || !v || !m) return;
    const [ny, nx] = m.grid.shape;
    x.a.gotoRaDec(v.ra, v.dec);
    x.a.setFoV(v.fov);
    x.foot.removeAll();
    import("aladin-lite").then(({ default: A }) => {
      const c = [[-0.5, -0.5], [nx - 0.5, -0.5], [nx - 0.5, ny - 0.5], [-0.5, ny - 0.5]].map(([col, row]) => {
        const s = pixelToSky(m.grid, col!, row!);
        return [s.ra, s.dec] as [number, number];
      });
      x.foot.add(A.polygon(c));
    });
  }, [ready, m, view]);

  const label = HIPS.find((h) => h.id === hips)?.label ?? hips;
  return (
    <div className="sky-context">
      <label>Survey <select value={hips} onChange={(e) => { setBlink25(false); setHips(e.target.value); }}>
        {HIPS.map((h) => <option key={h.id} value={h.id}>{h.label}</option>)}</select></label>
      {f25.enabled && (
        <label className="check" title="Blinks archival surveys of this field; the SPHEREx epoch is the main viewer">
          <input type="checkbox" checked={blink25} disabled={status !== "ready"} onChange={(e) => setBlink25(e.target.checked)} /> 25-year blink (lite)
        </label>
      )}
      {blink25 && <p className="notice small" role="note" aria-live="polite"><strong>{BLINK25_LITE[b25i]!.label}</strong> · {BLINK25_LABEL}</p>}
      <div className={`aladin-frame ${status}`}>
        <div ref={el} className="aladin" aria-label="Aladin Lite sky atlas around the view; the orange square is the SPHEREx view" role="img" />
        {status !== "ready" && (
          <div className="aladin-state" role="status" aria-live="polite">
            {status === "checking" ? (
              <p>Connecting to the CDS sky atlas ({label})…</p>
            ) : (
              <>
                <p><strong>Sky atlas unavailable.</strong> Neither the CDS image servers (alasky) nor the mirrors of this survey
                  are answering right now, so the {label} background cannot be shown. Try another survey; the SPHEREx viewer is
                  not affected.</p>
                {err && <p className="small hint">Aladin Lite: {err}</p>}
                <button onClick={() => setAttempt((n) => n + 1)}>Try again</button>
              </>
            )}
          </div>
        )}
      </div>
      <p className="small hint">Orange: the SPHEREx view. Background images are from other surveys and other epochs; moving stars sit elsewhere in them.</p>
    </div>
  );
}
