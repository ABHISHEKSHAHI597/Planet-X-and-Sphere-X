"""Evidence writer used by the check scripts. Originally I's temporary writer; since P's harness landed it
delegates to `scripts/validate.py:record` (workflow.md §4.5), which writes parallax-evidence@1 records with a
code digest (exact staleness even on a dirty tree), supersedes same-day reruns instead of overwriting, and
honours PARALLAX_VALIDATION_DIR for reviewer reproductions that must not touch validation/.
The call signature is unchanged, so no check script needs editing."""
import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "backend"))

from validate import record as _record  # noqa: E402


def sha_of(paths):
    h = hashlib.sha256()
    for p in sorted(str(x) for x in paths):
        h.update(Path(p).read_bytes() if Path(p).is_file() else p.encode())
    return h.hexdigest()[:16]


def record(check_id, level, verdict, metrics, report, inputs, n_frames=0, calibration=None, pins=None,
           code_paths=(), caveats=(), author="I", **kw):
    """metrics: {name: {"value": v, "threshold": "...", "pass": bool|None}}. verdict: pass|fail|inconclusive."""
    return _record(check_id, level, verdict, metrics, report, inputs, n_frames=n_frames, calibration=calibration,
                   pins=pins, code_paths=code_paths, caveats=caveats, author=author, **kw)
