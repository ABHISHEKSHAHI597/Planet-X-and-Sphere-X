"""Record synthetic digital tracking/ambiguous-orphan recovery separately from real data."""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
from _m_evidence import record

test = "tests/synthetic/test_planetx_recovery.py"
result = subprocess.run(
    [sys.executable, "-m", "pytest", "-q", test],
    cwd=ROOT / "backend",
    capture_output=True,
    text=True,
    check=False,
)
record(
    "M-planetx-synthetic",
    "L1",
    "pass" if result.returncode == 0 else "fail",
    {},
    "# Synthetic image tracking and orphan recovery\n```text\n"
    + result.stdout
    + result.stderr
    + "\n```\nShared table PSF, fixed spectrum, native white noise; 2000 independent noise draws check bilinear variance, centroid/total flux and ambiguous daily branch recovery at known distance. Initial 200-draw seed produced empirical variance .02974 vs .04180 prediction, outside unchanged 25% tolerance; increased Monte Carlo sample to 2000 to resolve sampling variability, with no formula/tolerance adjustment. Not proof of real TNO detection or false-positive rates.",
    ["backend/" + test],
    author="M",
    code_paths=[
        "scripts/verify/m_planetx.py",
        "backend/spherex/planetx.py",
        "backend/tests/synthetic/test_planetx_recovery.py",
        "backend/tests/synthetic/scene.py",
    ],
)
raise SystemExit(result.returncode)
