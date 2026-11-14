"""Retain illustrative template overlays for existing real native measurements."""

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "backend"), str(ROOT / "scripts")]
from _m_evidence import record
from spherex.templates import template_overlays

path = ROOT / ".cache/m-acceptance/epsindb-spectrum.json"
measurements = json.loads(path.read_text())
overlays = template_overlays(measurements["rows"])
record(
    "M-template-overlay",
    "L3",
    "inconclusive",
    {},
    "# Observed template overlays of retained epsilon Indi native rows\n"
    + f"{len(overlays)} separately scaled visit/release overlays retained in overlays.json. "
    + "This replays existing native measurements, not a new native extraction or classification acceptance. CBAND boxcar approximation and template uncertainties limit scientific interpretation.",
    [{"url": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}],
    author="M",
    pins=[measurements["pin"]],
    n_frames=len(measurements.get("native_frames", [])),
    code_paths=["scripts/verify/m_template_overlay.py", "backend/spherex/templates.py"],
    extra_files={"overlays.json": json.dumps(overlays, indent=2)},
)
