"""Regenerate golden payloads for mock mode and contract tests (workflow.md §8.5, §15). Owner P; the encoder is
I's (spherex/render.py), the consumers are F (frontend tests, mock API) and P (backend mock mode, contract tests).

  python scripts/make_goldens.py           write frontend/fixtures/golden/*
  python scripts/make_goldens.py --check   exit 1 if a committed golden differs (CI "Contract" stage)

Goldens:
  stack_F_121x121.f16        to_f16(golden_F(121)): orientation golden (F14)
  manifest_mock.json         the API's mock-mode manifest for the default Barnard request (shape of every field)
A changed golden is a contract change: bump the format id in render.py and record it in CONTRACTS.md."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
OUT = ROOT / "frontend" / "fixtures" / "golden"


def goldens() -> dict[Path, bytes]:
    from app import mock
    from app.pipeline import public
    from spherex.render import golden_F, to_f16
    m = mock.manifest(mock.mock_key("golden"), {"q": "Barnard's Star", "fov": "6", "px": "3", "bands": "6"},
                      None, 269.4461, 4.7707)
    for s in m["stacks"]:
        s["ready"] = True
    m = public(m)
    return {OUT / "stack_F_121x121.f16": to_f16(golden_F(121)),
            OUT / "manifest_mock.json": (json.dumps(m, indent=1, sort_keys=True, ensure_ascii=False) + "\n").encode()}


def main() -> int:
    want = goldens()
    if "--check" in sys.argv:
        stale = [p.relative_to(ROOT).as_posix() for p, b in want.items() if not p.exists() or p.read_bytes() != b]
        for s in stale:
            print("stale golden:", s)
        print("goldens fresh" if not stale else "run: python scripts/make_goldens.py")
        return 1 if stale else 0
    for p, b in want.items():
        p.write_bytes(b)
        print("wrote", p.relative_to(ROOT).as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
