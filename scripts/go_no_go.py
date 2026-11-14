"""G6 go/no-go checklist (workflow.md §12.2; run by P with I, M and F).

  python scripts/go_no_go.py --rc RC0 --api https://parallax.example [--answers release/RC0/checklist.yaml]

Automated items are measured here; manual items are read from the answers file, which each named person
fills in (item: {ok: true, by: F, evidence: "..."}). Writes release/<RC>/go_no_go.md and exits 1 on NO-GO.
An item with no answer is NO-GO: nothing is assumed."""
from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

import httpx
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

MANUAL = {
    "pinned_links": ("All pinned links in README, slides and video resolve and render identically on production "
                     "and on both offline laptops", "P, F"),
    "device_matrix": ("Device matrix: current Chrome, Firefox, Safari; one Android, one iPhone; WebGL disabled", "F"),
    "credits": ("Credits and DOIs present; no NASA insignia; licensed images only", "F"),
    "rollback": ("Rollback rehearsed: previous RC redeploys in under 5 minutes (docs/deploy.md §Rollback drill)", "P"),
    "prewarm": ("Pre-warm complete on production (scripts/prewarm.py output attached)", "P"),
}


def automated(api: str | None) -> list[tuple[str, bool, str]]:
    import validate
    out = []
    rc = subprocess.call([sys.executable, str(ROOT / "scripts/check_flags.py")], stdout=subprocess.DEVNULL)
    out.append(("check_flags.py green: every enabled capability is accepted", rc == 0, f"exit {rc}"))
    _reg, cs, gs, caps = validate.compute()
    feats = yaml.safe_load((ROOT / "config/features.yaml").read_text(encoding="utf-8"))["flags"]
    stale = []
    for name, f in feats.items():
        if f.get("level") != "on":
            continue
        for dep in f.get("requires", []):
            for c in ([dep] if dep in cs else [x for cr in gs.get(dep, {}).get("criteria", []) for x in cr.get("checks", [])]):
                if cs.get(c) and cs[c].rec and cs[c].rec.stale:
                    stale.append(f"{name}:{c}")
    out.append(("No stale records for enabled capabilities", not stale, ", ".join(stale) or "none"))
    perf = cs.get("G2-perf")
    out.append(("Cold and warm performance recorded against the budgets", bool(perf and perf.rec),
                perf.rec.path.name if perf and perf.rec else "no G2-perf record"))
    if api:
        try:
            with httpx.Client(base_url=api, timeout=30) as c:
                h = c.get("/healthz").json()
                out.append(("Health check green", bool(h.get("ok")), f"mode {h.get('mode')}"))
                codes = []
                for _ in range(8):
                    codes.append(c.post("/api/v1/views", json={"q": "Barnard's Star", "fov": "7", "bands": "6"}).status_code)
                out.append(("Per-IP job rate limit active", 429 in codes, f"codes {codes}"))
                r = c.post("/api/v1/views", json={"q": "Barnard's Star", "fov": "500"})
                out.append(("FOV cap active (≤ 60′)", r.status_code == 400, f"HTTP {r.status_code}"))
        except Exception as e:  # noqa: BLE001
            out.append(("Production reachable", False, repr(e)[:120]))
    else:
        out.append(("Health checks, rate limits and time-outs verified on production", False, "--api not given"))
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--rc", required=True)
    ap.add_argument("--api")
    ap.add_argument("--answers", type=Path)
    a = ap.parse_args()
    answers = yaml.safe_load(a.answers.read_text(encoding="utf-8")) if a.answers and a.answers.exists() else {}
    rows = [(t, ok, d) for t, ok, d in automated(a.api)]
    for k, (text, who) in MANUAL.items():
        ans = (answers or {}).get(k) or {}
        rows.append((f"{text} [{who}]", bool(ans.get("ok")), f"by {ans.get('by', '—')}: {ans.get('evidence', 'no answer')}"))
    go = all(ok for _, ok, _ in rows)
    md = [f"# G6 go/no-go — {a.rc} — {'GO' if go else 'NO-GO'}", "", f"Generated {time.strftime('%Y-%m-%d %H:%M')} by "
          "scripts/go_no_go.py (workflow.md §12.2).", "", "| | Item | Detail |", "|---|---|---|"]
    md += [f"| {'✅' if ok else '❌'} | {t} | {d} |" for t, ok, d in rows]
    out = ROOT / "release" / a.rc
    out.mkdir(parents=True, exist_ok=True)
    (out / "go_no_go.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print("\n".join(md).encode("ascii", "replace").decode())
    return 0 if go else 1


if __name__ == "__main__":
    raise SystemExit(main())
