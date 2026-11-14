"""Record synthetic reference-covariance validation separately from real G5.lc."""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
from _m_evidence import record

result = subprocess.run(
    [
        sys.executable,
        "-m",
        "pytest",
        "-q",
        "tests/synthetic/test_lightcurve_covariance.py",
    ],
    cwd=ROOT / "backend",
    check=False,
    capture_output=True,
    text=True,
)
record(
    "M-lightcurve-covariance",
    "L1",
    "pass" if result.returncode == 0 else "fail",
    {
        "noise_trials": {
            "value": 500,
            "threshold": "variances agree within 20%, PSD and no detector leakage",
            "pass": result.returncode == 0,
        }
    },
    "# Synthetic covariance validation\n```\n"
    + result.stdout
    + result.stderr
    + "\n```\nNot real-data acceptance or a calibrated periodogram FAP.",
    [],
    author="M",
    code_paths=[
        "backend/spherex/lightcurve.py",
        "backend/tests/synthetic/test_lightcurve_covariance.py",
        "scripts/verify/m_lightcurve.py",
    ],
)
