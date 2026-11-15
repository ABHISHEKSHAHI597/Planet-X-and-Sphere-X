"""Release flag guard (workflow.md §9.6, §4.3, §11.2; owner P).

  python scripts/check_flags.py                          check config/features.yaml
  python scripts/check_flags.py --config release.yaml    check a release configuration

Fails (exit 1) when:
- a flag is `on` but any of its `requires` (foundation check or gate) is not accepted in the evidence records
  (computed by scripts/validate.py from validation/, exactly what STATUS.md shows);
- `diff` is `on` without G4a accepted, or any QR2/QR3-mixing capability (spectrum, lightcurve) is `on` without F4
  confirmed (§11.2 forbidden fallbacks);
- a flag names an unknown requirement, or the frontend's capability list lacks a flag that is not `off`
  (a missing name is OFF in the UI, so the two would disagree). `core: true` flags are the P0 product the
  UI always shows; the API still gates them by level.
`staging` is allowed for synthetic/real capabilities: the badge covers UX immaturity only (§9.6)."""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import validate  # noqa: E402

ORDER = {"off": 0, "dev": 1, "staging": 2, "on": 3}
SECTION_11_2 = {"diff": ["G4a"], "spectrum": ["F4"], "lightcurve": ["F4"]}


def problems(cfg: dict, frontend_caps: set[str] | None = None) -> list[str]:
    reg, cs, gs, _caps = validate.compute()
    out: list[str] = []

    def accepted(dep: str) -> bool:
        if dep in gs:
            return gs[dep]["state"] == "accepted"
        return dep in cs and cs[dep].accepted

    for name, f in cfg["flags"].items():
        lvl = str(f.get("level"))
        if lvl not in ORDER:
            out.append(f"{name}: unknown level {lvl!r}")
            continue
        for dep in f.get("requires", []):
            if dep not in gs and dep not in reg["checks"]:
                out.append(f"{name}: unknown requirement {dep} (not in validation/registry.yaml)")
        if lvl == "on":
            bad = [d for d in f.get("requires", []) if not accepted(d)]
            if bad:
                out.append(f"{name}: level 'on' but not accepted: {', '.join(bad)} (validation/STATUS.md)")
            if not f.get("requires"):
                out.append(f"{name}: level 'on' with no requirements listed")
        # Release decision (2026-11-15): `staging` capabilities ship; only `on` (validity "accepted") needs the gate.
        for dep in SECTION_11_2.get(name, []):
            if ORDER[lvl] > ORDER["staging"] and not accepted(dep):
                out.append(f"{name}: level '{lvl}' violates workflow.md §11.2 until {dep} is accepted")
        if frontend_caps is not None and lvl != "off" and not f.get("core") and name not in frontend_caps:
            out.append(f"{name}: not in frontend/src/lib/features.ts CAPABILITIES (UI would show it OFF)")
    return out


def frontend_capabilities() -> set[str] | None:
    p = ROOT / "frontend" / "src" / "lib" / "features.ts"
    if not p.exists():
        return None
    txt = p.read_text(encoding="utf-8")
    m = re.search(r"CAPABILITIES\s*=\s*\{(.*?)\n\}", txt, re.S)
    return set(re.findall(r"^\s+([a-z0-9_]+)\s*:", m.group(1), re.M)) if m else None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", type=Path, default=ROOT / "config" / "features.yaml")
    ap.add_argument("--no-frontend", action="store_true")
    a = ap.parse_args()
    cfg = yaml.safe_load(a.config.read_text(encoding="utf-8"))
    errs = problems(cfg, None if a.no_frontend else frontend_capabilities())
    for e in errs:
        print("FAIL", e)
    on = [k for k, f in cfg["flags"].items() if f.get("level") == "on"]
    print(f"{a.config.name}: {len(cfg['flags'])} flags, {len(on)} on, {len(errs)} problems")
    return 1 if errs else 0


if __name__ == "__main__":
    raise SystemExit(main())
