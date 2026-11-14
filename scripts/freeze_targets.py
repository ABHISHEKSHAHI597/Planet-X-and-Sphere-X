"""Freeze the resolved target of every pinned demo view (optimisation.md IMP-2; advanced_research.md A2). Owner D.

  python scripts/freeze_targets.py            resolve live and rewrite config/pins/targets.json
  python scripts/freeze_targets.py --check    exit 1 unless every named, pinned view in config/demo_views.yaml is frozen

A pin freezes a frame list. The view key also depends on the resolved position and motion, which come from
SIMBAD and Gaia at request time: when Gaia was down the same pinned link built a different view, and Gaia DR4
(2026-12-02) will move every Gaia-based answer. With the target stored next to the pin, `backend/app/pipeline.py`
(`frozen_target`) uses it for that pin and never asks the resolver.

Run it with the archives reachable, read the printed sources (a star that normally has Gaia astrometry must say
"Gaia DR3 …"), then rebuild the demo views (scripts/prewarm.py) and commit the file. A degraded answer (a
resolver warning) is refused, not written."""
from __future__ import annotations

import argparse
import asyncio
import datetime
import json
import sys
from pathlib import Path
from typing import Any

import yaml

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "backend"))

from spherex.targets import identifier, parse_coords, resolve_name  # noqa: E402

VIEWS = REPO / "config" / "demo_views.yaml"
OUT = REPO / "config" / "pins" / "targets.json"


def wanted() -> list[tuple[str, str]]:
    """(pin, query) of every demo view opened by name with a pin; coordinate views need no resolver."""
    views = yaml.safe_load(VIEWS.read_text(encoding="utf-8"))["views"]
    pairs = {(str(v["body"]["pin"]), str(v["body"]["q"])) for v in views
             if v["body"].get("pin") and v["body"].get("q") and parse_coords(str(v["body"]["q"])) is None}
    return sorted(pairs)


async def freeze() -> tuple[dict[str, Any], list[str]]:
    from spherex.access.http import make_client

    targets: dict[str, dict[str, Any]] = {}
    refused: list[str] = []
    async with make_client() as client:
        for pin, q in wanted():
            t = await resolve_name(q, client)
            note = t.extra.get("warning")
            print(f"{'REFUSED' if note else 'ok':<8}{pin}  {q:<18} {t.astrometry_source}{'  — ' + note if note else ''}")
            if note:
                refused.append(q)
                continue
            targets.setdefault(pin, {})[identifier(q).lower()] = t.__dict__
    doc = dict(schema="parallax-pin-targets@1", created=datetime.date.today().isoformat(),
               note="Written by scripts/freeze_targets.py; reviewed like a pin (owner D). Do not edit by hand.",
               targets=targets)
    return doc, refused


def check() -> int:
    try:
        have = json.loads(OUT.read_text(encoding="utf-8"))["targets"]
    except (OSError, ValueError, KeyError):
        have = {}
    missing = [f"{pin} {q!r}" for pin, q in wanted() if identifier(q).lower() not in have.get(pin, {})]
    for m in missing:
        print(f"not frozen: {m}")
    print(f"{len(wanted()) - len(missing)} of {len(wanted())} pinned demo targets are frozen in {OUT.relative_to(REPO)}")
    return 1 if missing else 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    if a.check:
        return check()
    doc, refused = asyncio.run(freeze())
    if refused:
        print(f"not written: {len(refused)} degraded answer(s); try again when the archives answer")
        return 1
    OUT.write_text(json.dumps(doc, indent=1, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {OUT.relative_to(REPO)}: rebuild the demo views now (their keys follow the frozen targets)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
