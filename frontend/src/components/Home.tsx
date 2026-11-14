/** Landing view: the pitch, the six bands, and one-click missions for the five acceptance targets (implementation.md §1.2). */
import { CHALLENGE, MISSIONS, missionFor, type Mission } from "../content/missions";
import { HOME_TEXT, missionText } from "../content/translations";
import { href } from "../lib/base";
import { LANGS, setLang, useLang } from "../lib/lang";
import { BAND_IDS, BANDS } from "../lib/constants";
import { useApp } from "../state/store";
import { Icon } from "./Icon";
import { TargetSearch, targetPatch } from "./TargetBar";

/** Decorative star field for the hero's blink demo: a fixed pseudo-random field (same on every load) with a
 * realistic spread of brightness — many faint stars, a few bright ones. Percent positions, size in px. */
const FIELD: [number, number, number, number][] = (() => {
  let seed = 7;
  const rnd = () => ((seed = (seed * 16807) % 2147483647) - 1) / 2147483646;
  return Array.from({ length: 74 }, () => {
    const b = Math.pow(rnd(), 3.2);            // brightness: mostly faint
    return [3 + rnd() * 94, 3 + rnd() * 94, 1.2 + b * 4.2, 0.35 + b * 0.65] as [number, number, number, number];
  });
})();

function BlinkDemo() {
  return (
    <figure className="blink-demo" aria-hidden="true">
      <div className="plate">
        {FIELD.map(([x, y, sz, o], i) => <i key={i} style={{ left: `${x}%`, top: `${y}%`, width: sz, height: sz, opacity: o }} />)}
        <i className="mover" />
        <span className="reticle" />
      </div>
      <figcaption className="plate-log">
        <span className="plate-a"><b>A</b>1930-01-23</span>
        <span className="plate-b"><b>B</b>1930-01-29</span>
        <span className="plate-dt">Δt 6 d · one dot moves</span>
      </figcaption>
    </figure>
  );
}

/** The six SPHEREx bands on a linear wavelength axis. Ranges and resolving power come from lib/constants. */
function BandAxis() {
  const lo = 0.6, hi = 5.2;
  const x = (um: number) => `${((um - lo) / (hi - lo)) * 100}%`;
  return (
    <figure className="band-axis">
      <div className="band-track" role="img" aria-label="SPHEREx bands 1 to 6 cover 0.75 to 5.0 micrometres">
        {BAND_IDS.map((b) => {
          const [a, z, r] = BANDS[b]!;
          return (
            <div key={b} className="band-seg" data-band={b} style={{ left: x(a), width: `calc(${x(z)} - ${x(a)})` }}>
              <b>{b}</b>
              <span>{a.toFixed(2)}–{z.toFixed(2)}</span>
              <small>R≈{r}</small>
            </div>
          );
        })}
        {[1, 2, 3, 4, 5].map((t) => <span key={t} className="band-tick" style={{ left: x(t) }}>{t} µm</span>)}
      </div>
    </figure>
  );
}

/** Example queries in each accepted input form: a name, a catalogue designation, sexagesimal coordinates.
 *  The last is Barnard's Star's J2000 position, so it also shows the epoch banner. Each opens a pinned, prewarmed
 *  view (config/demo_views.yaml), never a cold live build (audit F-04). */
const EXAMPLES: { text: string; pin: string }[] = [
  { text: "Barnard's Star", pin: "21a7689afc4b" },
  { text: "WISE 0855-0714", pin: "325c57328320" },
  { text: "17:57:48.5 +04:41:36", pin: "21a7689afc4b" },
];

function go(text: string, pin?: string) {
  const r = targetPatch(text);
  if ("error" in r) return;
  const m = r.patch.q ? missionFor([r.patch.q]) : null;
  useApp.setState({ frame: 0, transform: null, dismissedHint: null });
  useApp.getState().setView({ ...r.patch, pin: pin ?? m?.pin ?? null, ...(m ? { bands: m.bands, fov: m.fov } : { fov: 6 }) }, { push: true });
}

function open(m: Pick<Mission, "q" | "bands" | "fov" | "pin">) {
  useApp.setState({ frame: 0, transform: null });
  useApp.getState().setView({ q: m.q, ra: null, dec: null, bands: m.bands, fov: m.fov, pin: m.pin ?? null, t: null, sel: null }, { push: true });
}

export function Home() {
  const setView = useApp((s) => s.setView);
  const lang = useLang();
  const T = HOME_TEXT[lang];
  return (
    <main className="home">
      <section className="pitch">
        <div className="pitch-text">
          <div className="lang-switch" role="group" aria-label="Language">
            {LANGS.map((l) => <button key={l.id} lang={l.id} className={l.id === lang ? "on" : ""} aria-pressed={l.id === lang} onClick={() => setLang(l.id)}>{l.name}</button>)}
          </div>
          <h1>{T.title}</h1>
          <p>{T.pitch}</p>
          <TargetSearch variant="hero" />
          <p className="examples">
            <span>{T.tryIt}</span>
            {EXAMPLES.map((e) => <button key={e.text} className="link" onClick={() => go(e.text, e.pin)}>{e.text}</button>)}
          </p>
        </div>
        <BlinkDemo />
      </section>

      <section className="bands-intro" aria-labelledby="bands-title">
        <div className="section-head">
          <h2 id="bands-title">{T.bandsTitle}</h2>
          <p>{T.bandsText}</p>
        </div>
        <BandAxis />
      </section>

      <section className="observing" aria-labelledby="missions-title">
        <div className="section-head row">
          <h2 id="missions-title">{T.missionsTitle}</h2>
          <p className="hint">{T.missionsHint}</p>
        </div>
        <ol className="missions" aria-label="Missions">
          {MISSIONS.map((m, i) => {
            const b = Number(m.bands.split(",")[0]) || 6;
            const r = BANDS[b];
            const text = missionText(m, lang);
            return (
              <li key={m.id}>
                <button className="mission" data-band={b} onClick={() => open(m)}>
                  <span className="mission-no">{String(i + 1).padStart(2, "0")}</span>
                  <span className="mission-main">
                    <strong>{text.title}</strong>
                    <small>{text.hook}</small>
                  </span>
                  <span className="mission-id">{m.q}</span>
                  <span className="band-chip"><i />{T.band} {b}{r ? ` · ${r[0].toFixed(1)}–${r[1].toFixed(1)} µm` : ""}</span>
                  <Icon name="arrow" size={18} className="mission-go" />
                </button>
              </li>
            );
          })}
          <li>
            <button className="mission challenge" onClick={() => { useApp.setState({ frame: 0, transform: null, dismissedHint: null }); setView({ q: null, ra: CHALLENGE.ra, dec: CHALLENGE.dec, fov: CHALLENGE.fov, bands: CHALLENGE.bands, pin: CHALLENGE.pin, t: null, sel: null }, { push: true }); }}>
              <span className="mission-no"><Icon name="target" size={16} /></span>
              <span className="mission-main">
                <strong>{T.challengeTitle}</strong>
                <small>{T.challengeHook}</small>
              </span>
              <span className="mission-id">08h55m10.831s −07°14′42.53″</span>
              <span className="band-chip epoch">{T.oldEpoch}</span>
              <Icon name="arrow" size={18} className="mission-go" />
            </button>
          </li>
        </ol>
      </section>

      <footer className="home-foot">
        <span>ParallaX · NASA Space Apps 2026 · <i>Planet X and SPHEREx</i></span>
        <a href={href("proof")}>{T.proofLink}</a>
        <a href={href("about")} onClick={(e) => { e.preventDefault(); useApp.getState().setDialog("about"); }}>{T.creditsLink}</a>
      </footer>
    </main>
  );
}
