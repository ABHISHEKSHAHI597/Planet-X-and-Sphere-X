"""Evidence record for Role I's L1 (synthetic) and L0 suites: runs pytest and records every test's result.
Covers G0 (generator traps), G2 "stack flux unbiasedness" (L1), G4a's synthetic criterion (L1) and the
trap teeth of workflow.md §4.2. A synthetic pass is quoted only as "in simulation" (workflow.md §4.1).
Usage: python scripts/verify/l1_synthetic.py
"""
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET

from _cache import ROOT
from _evidence import record

with tempfile.NamedTemporaryFile(suffix=".xml") as tf:
    subprocess.run([sys.executable, "-m", "pytest", "-q", "tests/synthetic", "tests/unit", f"--junitxml={tf.name}"],
                   cwd=ROOT / "backend", check=False)
    tree = ET.parse(tf.name)
metrics = {}
for tc in tree.iter("testcase"):
    ok = not any(c.tag in ("failure", "error") for c in tc)
    metrics[f"{tc.get('classname').split('.')[-1]}::{tc.get('name')}"] = dict(value="passed" if ok else "FAILED",
                                                                               threshold="pass", **{"pass": ok})
key = {"G2 stack flux unbiasedness": "test_synthetic_stack_unbiased_through_pipeline",
       "G4a synthetic (static < 3σ, both S/N)": "test_synthetic_native_matched_difference_static_stars_cancel",
       "G4a synthetic (dipole)": "test_synthetic_native_mover_dipole_and_template_shift",
       "G4a naive method fails": "test_synthetic_native_naive_stack_difference_fails",
       "resampling trap teeth": "test_synthetic_resampling_trap_teeth",
       "G0 generator traps": "test_synthetic_generator_produces_the_traps"}
lines = [f"- {k}: " + ", ".join(v["value"] for n, v in metrics.items() if key[k] in n) for k in key]
allok = all(m["pass"] for m in metrics.values())
report = f"""
Role I L0 + L1 suites ({len(metrics)} tests; assumptions in each test's docstring and in
backend/tests/synthetic/scene.py). Gate-relevant results:
{chr(10).join(lines)}

L1 establishes that the algorithms recover the truth *when the world matches the scene's assumptions*;
it never raises a capability above `synthetic` (workflow.md §4.2).
"""
record("I-L1-synthetic", "L1", "pass" if allok else "fail", metrics, report, ["backend/tests/synthetic", "backend/tests/unit"],
       code_paths=["backend/spherex/" + m for m in ("flags.py", "preprocess.py", "epochs.py", "grid.py", "stack.py", "cube.py", "render.py", "movers.py")])
