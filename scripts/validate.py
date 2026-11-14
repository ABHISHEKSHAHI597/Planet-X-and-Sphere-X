"""Evidence harness (workflow.md §4.5; owner P). Checks are owned by the scientists and D; this file owns how
records are written, validated, reviewed, invalidated and summarised.

  python scripts/validate.py run <check-id> [-- args]   run the check's script (validation/registry.yaml)
  python scripts/validate.py status [--write]           print / regenerate validation/STATUS.md
  python scripts/validate.py check                      every record validates against validation/schema.json
  python scripts/validate.py stale                      list records whose code_paths changed since they ran
  python scripts/validate.py review <record-dir> --role P --verdict approve|changes --notes "..." [--reproduced]
  python scripts/validate.py list                       latest record per check

Library: `from validate import record` (scripts/verify/_evidence.py delegates here).

Rules implemented (workflow.md §4.3–§4.5):
- A record is never deleted; a rerun the same day and sha supersedes in place, the old one is renamed `-superseded-N`.
- A record is **stale** when a file in its code_paths changed after it ran: by content digest for @1 records
  (exact even on a dirty tree), by git history + working-tree status for legacy @0-temporary records.
  A stale record counts one level lower (§4.5); a stale L2 foundation check therefore cannot unblock anything.
- A record counts toward acceptance only when reviewed (review.json, verdict approve) by someone other than
  the author with the reviewer role registry.yaml names (§9.4).
- A gate is `accepted` only when its requirements are accepted, every criterion has a fresh reviewed passing
  record at the required level (or a recorded manual item), and the §2.3 sign-off is recorded.
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
REGDIR = ROOT / "validation"                                   # registry.yaml and schema.json always live here
VAL = Path(os.environ.get("PARALLAX_VALIDATION_DIR") or REGDIR)  # records (override for reviewer reproductions)
LEVELS = ("L0", "L1", "L2", "L3", "L4")
SCHEMA_V = "parallax-evidence@1"
CODE_SUFFIXES = (".py", ".ts", ".tsx", ".yaml", ".yml", ".json", ".lock", ".glsl", ".toml")
_T0 = time.time()


# ------------------------------------------------------------------------------------------- helpers
def git(*a: str) -> str:
    try:
        return subprocess.run(["git", *a], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()
    except Exception:
        return ""


def portable(p: str) -> str:
    """A code path as a repo-relative string, whatever machine wrote it. Some records carry absolute paths of the
    author's checkout (`/home/<user>/…/Nasa-Space-Apps-2026/backend/../backend/x.py`), which only resolve, and only
    digest the same, on that machine: in CI (`/home/runner/work/…`) such a record was always stale. The repo-relative
    part starts at the first component that is a top-level entry of this repository, and keeps its spelling
    (`backend/../backend/x.py`), which is exactly the string the author's machine hashed."""
    if not os.path.isabs(p):
        return p
    pp = Path(p)
    if pp.is_relative_to(ROOT):
        return pp.relative_to(ROOT).as_posix()
    parts = pp.parts
    top = {x.name for x in ROOT.iterdir()}
    for i, part in enumerate(parts[1:], 1):
        if part in top:
            return Path(*parts[i:]).as_posix()
    return p


def code_digest(paths: list[str] | tuple[str, ...]) -> str:
    """sha256 over (path, bytes) of every file under code_paths, sorted. Missing paths hash as '<missing>'.
    Paths are taken repo-relative (`portable`), so the digest is the same on every checkout."""
    h = hashlib.sha256()
    files: list[Path] = []
    for p in sorted({portable(str(x)) for x in paths}):
        q = ROOT / p
        if q.is_dir():
            files += sorted(x for x in q.rglob("*") if x.is_file() and x.suffix in CODE_SUFFIXES
                            and "__pycache__" not in x.parts)
        else:
            files.append(q)
    for f in files:
        h.update(f.relative_to(ROOT).as_posix().encode() if f.is_relative_to(ROOT) else str(f).encode())
        h.update(b"\0")
        h.update(f.read_bytes().replace(b"\r\n", b"\n") if f.exists() else b"<missing>")
        h.update(b"\0")
    return h.hexdigest()


def rel(p: Path) -> str:
    try:
        return p.relative_to(ROOT).as_posix()
    except ValueError:
        return p.as_posix()


def registry() -> dict[str, Any]:
    return yaml.safe_load((REGDIR / "registry.yaml").read_text(encoding="utf-8"))


def _contract_versions() -> dict[str, str]:
    out: dict[str, str] = {}
    try:
        sys.path.insert(0, str(ROOT / "backend"))
        from spherex.types import CONTRACT_VERSION
        out["spherex.types"] = CONTRACT_VERSION
        from app.settings import API_VERSION
        out["http-api"] = API_VERSION
    except Exception:
        pass
    return out


def _calibration_lock() -> str:
    p = ROOT / "config" / "calibration.lock"
    if not p.exists():
        return "none: config/calibration.lock missing"
    try:
        return str(yaml.safe_load(p.read_text(encoding="utf-8")).get("lock_hash", "unknown"))
    except Exception:
        return "unreadable"


# -------------------------------------------------------------------------------------------- record
def record(check_id: str, level: str, verdict: str, metrics: dict[str, Any], report: str, inputs: list[Any],
           n_frames: int = 0, calibration: str | None = None, pins: Any = None, code_paths: Any = (),
           caveats: Any = (), author: str = "?", figures: dict[str, bytes] | None = None,
           threshold_changes: Any = (), environment: str | None = None, extra_files: dict[str, str] | None = None
           ) -> Path:
    """Write validation/<check-id>/<date>-<sha>/{record.json, report.md, figures/}. Same signature as I's
    interim writer plus `figures`, `threshold_changes`, `environment`, `extra_files`."""
    assert verdict in ("pass", "fail", "inconclusive"), verdict
    assert level in LEVELS, level
    reg = registry()["checks"].get(check_id, {})
    sha = git("rev-parse", "--short", "HEAD") or "nogit"
    dirty = bool(git("status", "--porcelain"))
    day = datetime.date.today().isoformat()
    d = VAL / check_id / f"{day}-{sha}"
    supersedes = None
    if (d / "record.json").exists():
        n = 1
        while (d.parent / f"{d.name}-superseded-{n}").exists():
            n += 1
        old = d.parent / f"{d.name}-superseded-{n}"
        d.rename(old)
        supersedes = old.name
    d.mkdir(parents=True, exist_ok=True)
    cps = [portable(str(p)) for p in code_paths]      # repo-relative in the record, never this machine's path
    rec = dict(schema=SCHEMA_V, check_id=check_id, level=level, verdict=verdict, metrics=metrics, git_sha=sha,
               git_dirty=dirty, contract_versions=_contract_versions(),
               calibration_lock=calibration or _calibration_lock(), pins=pins or "none", inputs=list(inputs),
               input_frame_count=int(n_frames), runtime_s=round(time.time() - _T0, 1), author=author,
               reviewer=f"pending ({reg.get('reviewer', 'other scientist or P')}, workflow.md §9.4)",
               code_paths=cps, code_digest=code_digest(cps), caveats=list(caveats),
               threshold_changes=list(threshold_changes),
               environment=environment or os.environ.get("PARALLAX_ENVIRONMENT", f"{sys.platform} local"),
               supersedes=supersedes, date=day)
    if dirty:
        rec["caveats"].append("recorded on a dirty working tree: code_digest identifies the exact code")
    (d / "record.json").write_text(json.dumps(rec, indent=1, default=str), encoding="utf-8")
    if figures:
        (d / "figures").mkdir(exist_ok=True)
        for name, data in figures.items():
            (d / "figures" / name).write_bytes(data)
    for name, text in (extra_files or {}).items():
        (d / name).write_text(text, encoding="utf-8")
    lines = [f"# {check_id} — {verdict.upper()} ({level})", "", report.strip(), "", "## Metrics", "",
             "| metric | value | threshold | pass |", "|---|---|---|---|"]
    for k, m in metrics.items():
        lines.append(f"| {k} | {m.get('value')} | {m.get('threshold', '')} | {m.get('pass', '')} |")
    if rec["caveats"]:
        lines += ["", "## Caveats", ""] + [f"- {c}" for c in rec["caveats"]]
    if figures:
        lines += ["", "## Figures", ""] + [f"![{n}](figures/{n})" for n in figures]
    lines += ["", f"git {sha}{' (dirty)' if dirty else ''} · contracts {rec['contract_versions']} · "
              f"calibration {rec['calibration_lock']} · author {author} · reviewer pending"]
    (d / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"[{verdict}] {check_id} -> {rel(d)}")
    return d


# ------------------------------------------------------------------------------------------- reading
@dataclass
class Rec:
    path: Path
    data: dict[str, Any]
    review: dict[str, Any] | None
    stale: bool
    stale_why: str

    @property
    def check_id(self) -> str:
        return str(self.data["check_id"])

    @property
    def level(self) -> str:
        return str(self.data["level"])

    @property
    def effective_level(self) -> str:
        """§4.5: a stale record counts one level lower."""
        i = LEVELS.index(self.level)
        return LEVELS[max(0, i - 1)] if self.stale else self.level

    @property
    def reviewed(self) -> bool:
        return bool(self.review and self.review.get("verdict") == "approve")


def _stale(data: dict[str, Any]) -> tuple[bool, str]:
    cps = data.get("code_paths") or []
    if not cps:
        return False, ""
    if data.get("code_digest"):
        now = code_digest(cps)
        return (now != data["code_digest"]), ("code_paths changed since the record (digest)"
                                               if now != data["code_digest"] else "")
    sha = data.get("git_sha", "")
    changed = git("log", "--format=%h", f"{sha}..HEAD", "--", *cps) if sha else "?"
    wt = git("status", "--porcelain", "--", *cps)
    if changed or wt:
        # One wording whatever changed (commits or the working tree): listing commit hashes here made the committed
        # STATUS.md go stale with every merge or commit that touched these paths (audit O-09, B-11).
        # `validate.py stale` prints the same; `git log <sha>..HEAD -- <code_paths>` lists the commits.
        return True, "legacy record (no code_digest): code_paths changed since it ran"
    if data.get("git_dirty"):
        return True, "legacy record made on a dirty tree without code_digest: re-run under the harness"
    return False, ""


def load_records() -> list[Rec]:
    out: list[Rec] = []
    for p in sorted(VAL.glob("*/*/record.json")):
        data = json.loads(p.read_text(encoding="utf-8"))
        rv = p.parent / "review.json"
        review = json.loads(rv.read_text(encoding="utf-8")) if rv.exists() else None
        st, why = _stale(data)
        out.append(Rec(p.parent, data, review, st, why))
    return out


def _is_ancestor(a: str, b: str) -> bool | None:
    """True if commit a is an ancestor of commit b (a != b), False if not, None if git cannot tell."""
    if not a or not b or a == b:
        return None
    try:
        r = subprocess.run(["git", "merge-base", "--is-ancestor", a, b], cwd=ROOT, capture_output=True)
    except OSError:
        return None
    return {0: True, 1: False}.get(r.returncode)


def _newer(r: Rec, cur: Rec) -> bool:
    """Is record r newer than cur? By date; on the same date by commit ancestry (a record made on a later commit
    wins), and only when git cannot order the two commits, by directory name. Directory names carry the short sha,
    so comparing them alone ranked e.g. `…-3ae8487` below an older `…-d6d2e45`."""
    if r.data["date"] != cur.data["date"]:
        return bool(r.data["date"] > cur.data["date"])
    ra, ca = str(r.data.get("git_sha", "")), str(cur.data.get("git_sha", ""))
    if _is_ancestor(ca, ra):
        return True
    if _is_ancestor(ra, ca):
        return False
    return r.path.name > cur.path.name


def latest(records: list[Rec]) -> dict[str, Rec]:
    """Latest non-superseded record per check id (see `_newer`)."""
    best: dict[str, Rec] = {}
    for r in records:
        if "-superseded-" in r.path.name:
            continue
        cur = best.get(r.check_id)
        if cur is None or _newer(r, cur):
            best[r.check_id] = r
    return best


# --------------------------------------------------------------------------------------------- state
@dataclass
class CheckState:
    id: str
    spec: dict[str, Any]
    rec: Rec | None
    state: str = "open"            # open | failed | inconclusive | passing | confirmed
    notes: list[str] = field(default_factory=list)

    def meets(self, level: str) -> bool:
        return bool(self.rec and self.rec.data["verdict"] == "pass"
                    and LEVELS.index(self.rec.effective_level) >= LEVELS.index(level))

    @property
    def accepted(self) -> bool:
        """Counts toward a gate / flag: passing at the required level, fresh, reviewed."""
        return self.meets(self.spec.get("level", "L2")) and bool(self.rec and self.rec.reviewed)


def check_states(reg: dict[str, Any], recs: dict[str, Rec]) -> dict[str, CheckState]:
    out: dict[str, CheckState] = {}
    for cid, spec in reg["checks"].items():
        r = recs.get(cid)
        cs = CheckState(cid, spec, r)
        if r is None:
            cs.state, cs.notes = "open", ["no record"]
        else:
            v = r.data["verdict"]
            if v == "fail":
                cs.state = "failed"
            elif v == "inconclusive":
                cs.state = "inconclusive"
            elif cs.meets(spec.get("level", "L2")):
                cs.state = "confirmed" if r.reviewed else "passing (unreviewed)"
            else:
                cs.state = "passing below required level"
            if r.stale:
                cs.notes.append(f"STALE: {r.stale_why}")
            if not r.reviewed:
                cs.notes.append(f"review pending ({spec.get('reviewer', '?')})")
        out[cid] = cs
    for cid, r in recs.items():                 # records for checks the registry doesn't know yet
        if cid not in out:
            out[cid] = CheckState(cid, {"kind": "unregistered", "level": r.level}, r, "unregistered",
                                  ["add to validation/registry.yaml"])
    return out


def gate_states(reg: dict[str, Any], cs: dict[str, CheckState]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}

    def accepted(dep: str) -> bool:
        if dep in reg["gates"]:
            return solve(dep)["state"] == "accepted"
        return dep in cs and cs[dep].accepted

    def solve(gid: str) -> dict[str, Any]:
        if gid in out:
            return out[gid]
        g = reg["gates"][gid]
        missing: list[str] = []
        crit_rows = []
        n_ok = 0
        for c in g.get("criteria", []):
            if c.get("checks"):
                ok = all(cs[x].meets(c["level"]) and cs[x].rec is not None and cs[x].rec.reviewed
                         for x in c["checks"])
                passing = all(cs[x].meets(c["level"]) for x in c["checks"])
                st = "met" if ok else ("passing, review pending" if passing else "not met")
            else:
                ok = bool(c.get("met"))
                st = "met (manual)" if ok else "not met"
            n_ok += ok
            crit_rows.append(dict(c, status=st))
            if not ok:
                missing.append(c["id"])
        reqs_missing = [d for d in g.get("requires", []) if not accepted(d)]
        signed = bool(g.get("signoff"))
        if not reqs_missing and not missing and signed:
            state = "accepted"
        elif any(cs[d].state in ("failed",) for d in g.get("requires", []) if d in cs):
            state = "blocked"
        else:
            state = "open"
        out[gid] = dict(state=state, requires_missing=reqs_missing, criteria=crit_rows, met=n_ok,
                        total=len(crit_rows), signoff=g.get("signoff"))
        return out[gid]

    for gid in reg["gates"]:
        solve(gid)
    return out


def capability_states(reg: dict[str, Any], cs: dict[str, CheckState], gs: dict[str, dict[str, Any]],
                      features: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """workflow.md §4.3 states from the flag's `requires` list."""
    out = {}
    for name, f in features["flags"].items():
        reqs = list(f.get("requires", []))
        f_reqs = [r for r in reqs if r in cs and reg["checks"].get(r, {}).get("kind") == "foundation"]
        g_reqs = [r for r in reqs if r in gs]
        if any(cs[r].state in ("failed", "open", "inconclusive") or (cs[r].rec and cs[r].rec.stale)
               for r in f_reqs):
            state = "blocked"
        elif g_reqs and all(gs[g]["state"] == "accepted" for g in g_reqs) and all(cs[r].accepted for r in f_reqs):
            state = "accepted"
        else:
            levels = []
            for g in g_reqs:
                for c in gs[g]["criteria"]:
                    for x in c.get("checks", []):
                        if cs[x].rec and cs[x].rec.data["verdict"] == "pass":
                            levels.append(cs[x].rec.effective_level)
            best = max(levels, key=LEVELS.index) if levels else "L0"
            state = "real" if best in ("L2", "L3", "L4") and all(
                all(cs[x].meets(c["level"]) for x in c.get("checks", []))
                for g in g_reqs for c in gs[g]["criteria"] if c.get("checks")) else (
                "synthetic" if best == "L1" else "draft")
        out[name] = dict(state=state, level=f.get("level"), requires=reqs)
    return out


def compute() -> tuple[dict[str, Any], dict[str, CheckState], dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    reg = registry()
    recs = latest(load_records())
    cs = check_states(reg, recs)
    gs = gate_states(reg, cs)
    features = yaml.safe_load((ROOT / "config" / "features.yaml").read_text(encoding="utf-8"))
    caps = capability_states(reg, cs, gs, features)
    return reg, cs, gs, caps


# -------------------------------------------------------------------------------------------- STATUS
def status_md() -> str:
    reg, cs, gs, caps = compute()
    head = git("rev-parse", "--short", "HEAD") or "nogit"
    L = ["# Validation status", "",
         f"GENERATED by `python scripts/validate.py status --write` at git {head}. Do not edit. "
         "Authority: the records under `validation/` (workflow.md §4.5).", "",
         "States: foundation checks are *confirmed* only with a fresh, reviewed, passing record at the required "
         "level. A **stale** record (its code changed after it ran) counts one level lower. Gates are *accepted* "
         "only with every criterion met, every requirement accepted and the §2.3 sign-off recorded.", ""]
    L += ["## Foundation checks (§5)", "", "| Check | Owner | Required | Latest record | Verdict | Level (eff.) | State | Notes |",
          "|---|---|---|---|---|---|---|---|"]
    for cid, c in cs.items():
        if c.spec.get("kind") != "foundation":
            continue
        r = c.rec
        L.append(f"| {cid} | {c.spec.get('owner')}{'+' + c.spec['pair'] if c.spec.get('pair') else ''} | "
                 f"{c.spec.get('level')} | {r.path.relative_to(VAL).as_posix() if r else '—'} | "
                 f"{r.data['verdict'] if r else '—'} | {(r.level + ' (' + r.effective_level + ')') if r else '—'} | "
                 f"**{c.state}** | {'; '.join(c.notes) or ''} |")
    L += ["", "## Gates (§6)", "", "| Gate | State | Criteria met | Missing requirements | Sign-off |", "|---|---|---|---|---|"]
    for gid, g in gs.items():
        L.append(f"| {gid} | **{g['state']}** | {g['met']}/{g['total']} | {', '.join(g['requires_missing']) or '—'} | "
                 f"{g['signoff'] or 'not recorded'} |")
    for gid, g in gs.items():
        L += ["", f"### {gid}", "", "| Criterion | Owner | Level | Evidence | Status |", "|---|---|---|---|---|"]
        for c in g["criteria"]:
            ev = ", ".join(c.get("checks", [])) or (c.get("met") or "—")
            L.append(f"| {c['id']}: {c['text']} | {c['owner']} | {c.get('level', '—')} | {ev} | {c['status']} |")
    L += ["", "## Other records", "", "| Check | Kind | Owner | Latest | Verdict | Level (eff.) | State | Notes |",
          "|---|---|---|---|---|---|---|---|"]
    for cid, c in cs.items():
        if c.spec.get("kind") in ("foundation",) or c.rec is None:
            continue
        r = c.rec
        L.append(f"| {cid} | {c.spec.get('kind')} | {c.spec.get('owner', '?')} | {r.path.relative_to(VAL).as_posix()} | "
                 f"{r.data['verdict']} | {r.level} ({r.effective_level}) | {c.state} | {'; '.join(c.notes)} |")
    L += ["", "## Capabilities (§4.3) and flags (§9.6)", "",
          "| Capability | State | Flag level | Requires |", "|---|---|---|---|"]
    for name, c in caps.items():
        L.append(f"| {name} | **{c['state']}** | {c['level']} | {', '.join(c['requires'])} |")
    L += ["", "A flag may be `on` only when every requirement is accepted (`scripts/check_flags.py`).", ""]
    return "\n".join(L)


# ----------------------------------------------------------------------------------------- commands
def cmd_check() -> int:
    import jsonschema
    schema = json.loads((REGDIR / "schema.json").read_text(encoding="utf-8"))
    v = jsonschema.Draft202012Validator(schema)
    bad = 0
    for r in load_records():
        errs = sorted(v.iter_errors(r.data), key=lambda e: list(e.path))
        if r.data.get("check_id") != r.path.parent.name:
            errs.append(jsonschema.ValidationError(f"check_id {r.data.get('check_id')} != directory {r.path.parent.name}"))
        if r.review is not None:
            author = str(r.data.get("author", "")).strip().upper()
            if str(r.review.get("role", "")).strip().upper() == author:
                errs.append(jsonschema.ValidationError("review by the author is not allowed (§9.4)"))
        for e in errs:
            bad += 1
            print(f"{rel(r.path)}: {e.message}")
    print(f"{len(load_records())} records checked, {bad} problems")
    return 1 if bad else 0


def cmd_review(path: str, role: str, verdict: str, notes: str, reproduced: bool, name: str) -> int:
    d = (ROOT / path).resolve() if not Path(path).is_absolute() else Path(path)
    data = json.loads((d / "record.json").read_text(encoding="utf-8"))
    spec = registry()["checks"].get(data["check_id"], {})
    if role.upper() == str(data.get("author", "")).upper():
        print("refused: the author cannot review their own record (workflow.md §9.4)")
        return 2
    want = str(spec.get("reviewer", "")).upper()
    if want and role.upper() != want:
        print(f"refused: {data['check_id']} needs review by {want} (validation/registry.yaml)")
        return 2
    rv = dict(schema="parallax-review@1", check_id=data["check_id"], record=d.name, role=role.upper(),
              reviewer=name, verdict="approve" if verdict == "approve" else "changes", reproduced=reproduced,
              notes=notes, date=datetime.date.today().isoformat(),
              code_digest_at_review=code_digest(data.get("code_paths") or []))
    (d / "review.json").write_text(json.dumps(rv, indent=1), encoding="utf-8")
    print(f"review {rv['verdict']} by {role} -> {rel(d / 'review.json')}")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("check_id")
    r.add_argument("rest", nargs=argparse.REMAINDER)
    s = sub.add_parser("status")
    s.add_argument("--write", action="store_true")
    s.add_argument("--check", action="store_true", help="exit 1 if the committed STATUS.md is stale")
    sub.add_parser("check")
    sub.add_parser("stale")
    sub.add_parser("list")
    v = sub.add_parser("review")
    v.add_argument("record")
    v.add_argument("--role", required=True)
    v.add_argument("--verdict", choices=["approve", "changes"], required=True)
    v.add_argument("--notes", required=True)
    v.add_argument("--reproduced", action="store_true")
    v.add_argument("--name", default="")
    a = ap.parse_args(argv)
    if a.cmd == "run":
        spec = registry()["checks"].get(a.check_id)
        if not spec or not spec.get("script"):
            print(f"{a.check_id}: no script registered in validation/registry.yaml")
            return 2
        rest = [x for x in a.rest if x != "--"]
        return subprocess.call([sys.executable, str(ROOT / spec["script"]), *rest], cwd=ROOT)
    if a.cmd == "status":
        txt = status_md()
        target = VAL / "STATUS.md"
        if a.check:
            def body(t: str) -> str:
                return "\n".join(x for x in t.splitlines() if not x.startswith("GENERATED by"))
            ok = target.exists() and body(target.read_text(encoding="utf-8")) == body(txt)
            print("STATUS.md is fresh" if ok else "STATUS.md is stale: run python scripts/validate.py status --write")
            return 0 if ok else 1
        if a.write:
            target.write_text(txt, encoding="utf-8", newline="\n")
            print(f"wrote {target.relative_to(ROOT).as_posix()}")
        else:
            print(txt)
        return 0
    if a.cmd == "check":
        return cmd_check()
    if a.cmd == "stale":
        n = 0
        for rr in latest(load_records()).values():
            if rr.stale:
                n += 1
                print(f"STALE {rr.path.relative_to(VAL).as_posix()}: {rr.stale_why}")
        print(f"{n} stale")
        return 0
    if a.cmd == "list":
        for cid, rr in sorted(latest(load_records()).items()):
            print(f"{cid:<20} {rr.data['verdict']:<13} {rr.level} {'stale' if rr.stale else 'fresh':<6} "
                  f"{'reviewed' if rr.reviewed else 'unreviewed':<10} {rr.path.relative_to(VAL).as_posix()}")
        return 0
    if a.cmd == "review":
        return cmd_review(a.record, a.role, a.verdict, a.notes, a.reproduced, a.name)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
