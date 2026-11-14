"""Role M synthetic verification, separate from all real-target evidence."""

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
        "-s",
        "tests/synthetic/test_synthetic_measurement.py",
        "tests/synthetic/test_joint_astrometry.py",
    ],
    cwd=ROOT / "backend",
    check=False,
    capture_output=True,
    text=True,
)
record(
    "G3-synthetic",
    "L1",
    "pass" if result.returncode == 0 else "fail",
    {
        "pytest_returncode": dict(
            value=result.returncode, threshold="0", **{"pass": result.returncode == 0}
        )
    },
    "# Synthetic native measurement\nShared-generator table PSF, Gaussian noise, 300 phase/edge trials; "
    "blend covariance and naive one-source bias; fixed catalogue parallax, shared covariance and rank rejection.\n"
    "```text\n" + result.stdout + result.stderr + "\n```",
    ["backend/tests/synthetic/test_synthetic_measurement.py"],
    author="M",
    code_paths=[
        "backend/spherex/targets.py",
        "backend/spherex/astrometry.py",
        "backend/spherex/joint_astrometry.py",
        "backend/spherex/epsf.py",
        "backend/tests/synthetic/scene.py",
        "backend/tests/synthetic/test_synthetic_measurement.py",
        "backend/tests/synthetic/test_joint_astrometry.py",
    ],
)
raise SystemExit(result.returncode)
