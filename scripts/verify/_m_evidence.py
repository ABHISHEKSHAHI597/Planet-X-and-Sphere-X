"""M evidence wrapper: retain sources as executed, including a dirty working tree.

An edit during a long real-data run must not be attested as the executed source.
P's schema/status/review machinery remains authoritative; this adds an immutable
source snapshot and refuses a passing verdict if those sources changed mid-run.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from validate import record as _record

ROOT = Path(__file__).resolve().parents[2]
_sources = {
    p.relative_to(ROOT).as_posix(): p.read_text(encoding="utf-8")
    for base in (
        ROOT / "backend/app",
        ROOT / "backend/spherex",
        ROOT / "scripts/verify",
    )
    for p in base.rglob("*.py")
}


def record(*args: Any, **kwargs: Any) -> Path:
    paths = list(kwargs.get("code_paths", []))
    paths.append("scripts/verify/_m_evidence.py")
    selected = {
        p: text
        for p, text in _sources.items()
        if any(p == base or p.startswith(base.rstrip("/") + "/") for base in paths)
    }
    changed = [
        p
        for p, text in selected.items()
        if not (ROOT / p).exists() or (ROOT / p).read_text(encoding="utf-8") != text
    ]
    kwargs["code_paths"] = paths
    extras = dict(kwargs.get("extra_files") or {})
    extras["executed-sources.json"] = json.dumps(
        {
            p: {"sha256": hashlib.sha256(text.encode()).hexdigest(), "source": text}
            for p, text in selected.items()
        },
        indent=1,
    )
    kwargs["extra_files"] = extras
    if changed:
        args = list(args)
        if len(args) >= 3 and args[2] == "pass":
            args[2] = "inconclusive"
        elif len(args) < 3 and kwargs.get("verdict") == "pass":
            kwargs["verdict"] = "inconclusive"
        note = (
            "Sources changed during execution: "
            + ", ".join(changed)
            + ". Executed snapshot retained; rerun before acceptance."
        )
        kwargs["caveats"] = list(kwargs.get("caveats", [])) + [note]

    # P's fallback stringifies unknown values; numpy booleans must remain JSON booleans.
    def native(v: Any) -> Any:
        if isinstance(v, dict):
            return {k: native(x) for k, x in v.items()}
        if isinstance(v, (list, tuple)):
            return [native(x) for x in v]
        return v.item() if hasattr(v, "item") else v

    args = list(args)
    if len(args) >= 4:
        args[3] = native(args[3])
    elif "metrics" in kwargs:
        kwargs["metrics"] = native(kwargs["metrics"])
    return _record(*args, **kwargs)
