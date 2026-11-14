/**
 * Proof page (optimisation.md VAL-2, VAL-6): each claim beside our number, a reference and its evidence record;
 * then, in the same form, what is not proven yet. The data is generated from validation/ by scripts/make_proof.py
 * (content/proof.json); nothing here is typed by hand, so the page cannot claim more than the records hold
 * (workflow.md §4.1).
 */
import proof from "../content/proof.json";

export interface ProofRow {
  id: string; claim: string; detail: string; check: string;
  ours: string | null; ours_label: string | null; reference: string | null;
  state: string; verdict: string; level: string; date: string; record: string; record_url: string;
}

/** What each state means, in the words a visitor needs. */
export const STATE_HELP: Record<string, string> = {
  "accepted": "Passes, was run on the current code, and a second team member reproduced and approved it.",
  "passed, review pending": "Passes on the current code. The independent review by a second team member is not recorded yet.",
  "passed, re-run pending": "Passed when it ran. The code it measures has changed since, so it must be run again before we rely on it.",
  "changes requested": "A second team member reviewed this and did not accept it as it stands.",
  "inconclusive": "The check ran and could not decide.",
  "failed": "The check ran and did not pass.",
};

const tone = (state: string) => (state === "accepted" ? "ok" : state.startsWith("passed") ? "pending" : "warn");

function Row({ r }: { r: ProofRow }) {
  return (
    <li className="proof-row">
      <div className="proof-claim">
        <h3>{r.claim}</h3>
        <p>{r.detail}</p>
      </div>
      <dl className="proof-numbers">
        {r.ours && <div><dt>{r.ours_label ?? "measured"}</dt><dd>{r.ours}</dd></div>}
        {r.reference && <div><dt>compared with</dt><dd>{r.reference}</dd></div>}
      </dl>
      <p className="proof-state">
        <span className={`badge ${tone(r.state)}`} title={STATE_HELP[r.state]}>{r.state}</span>
        <a href={r.record_url} target="_blank" rel="noreferrer">record {r.check}</a>
        <span className="proof-meta">level {r.level} · {r.date}</span>
      </p>
    </li>
  );
}

export function ProofPage() {
  const claims = proof.claims as ProofRow[];
  const open = proof.open as ProofRow[];
  const states = [...new Set([...claims, ...open].map((r) => r.state))];
  return (
    <div className="proof">
      <p className="proof-lead">Every number ParallaX shows is meant to be checkable. Each line below is one claim, the number
        we measured, what we compared it with, and a link to the record that holds the script, the inputs and the result.</p>

      <section aria-labelledby="proof-checked">
        <h2 id="proof-checked">What we have checked</h2>
        <ol className="proof-list">{claims.map((r) => <Row key={r.id} r={r} />)}</ol>
      </section>

      <section aria-labelledby="proof-open">
        <h2 id="proof-open">What is not proven yet</h2>
        <p className="proof-note">These are the tool's known limits: checks that fail, could not decide, or that a reviewer
          sent back for more work. Features that depend on them are marked <em>unvalidated</em> or are switched off until
          the check passes.</p>
        <ol className="proof-list">{open.map((r) => <Row key={r.id} r={r} />)}</ol>
      </section>

      <section aria-labelledby="proof-states">
        <h2 id="proof-states">How to read the states</h2>
        <dl className="proof-legend">
          {states.map((s) => <div key={s}><dt><span className={`badge ${tone(s)}`}>{s}</span></dt><dd>{STATE_HELP[s]}</dd></div>)}
        </dl>
        <p className="proof-note">Levels: L1 a synthetic sky with known answers · L2 real SPHEREx files kept in the repository ·
          L3 the pinned real targets · L4 agreement with an independent source. A team member never reviews their own science.</p>
      </section>
    </div>
  );
}
