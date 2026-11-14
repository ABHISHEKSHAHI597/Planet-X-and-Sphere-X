"""Compare a provenance-bearing IRSA export with pinned native spectrum JSON.

Reference JSON: tool='IRSA Spectrophotometry Tool', source_url, units='uJy',
release, frame_ids, rows=[{frame_id,lam,dlam,flux,err}]. Preserve original export
alongside this normalized wrapper and cite its checksum in acquisition notes.
"""

import argparse
import base64
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "backend"), str(ROOT / "scripts")]
from _m_evidence import record
from spherex.reference import compare_reference, normalize_irsa_table

p = argparse.ArgumentParser(description=__doc__)
p.add_argument("--measurements", type=Path, required=True)
p.add_argument("--reference", type=Path, required=True)
p.add_argument(
    "--raw-export",
    action="store_true",
    help="Read original VOTable/FITS/CSV instead of normalized JSON",
)
p.add_argument(
    "--frame-map",
    type=Path,
    help="JSON lvf_id:det_id to pinned native frame ID mapping",
)
p.add_argument("--source-url", help="Original official IRSA job/export URL")
p.add_argument(
    "--export-flux-unit", help="Explicit unit only if export omits metadata, e.g. uJy"
)
p.add_argument(
    "--export-wave-unit", help="Explicit unit only if export omits metadata, e.g. um"
)
p.add_argument("--visit", required=True)
p.add_argument("--release", choices=["qr2", "qr3"], required=True)
args = p.parse_args()
measured = json.loads(args.measurements.read_text())
if args.raw_export:
    from astropy.table import Table

    if args.frame_map is None or not args.source_url:
        p.error("--raw-export requires --frame-map and --source-url")
    reference = normalize_irsa_table(
        Table.read(args.reference),
        json.loads(args.frame_map.read_text()),
        args.source_url,
        args.export_flux_unit,
        args.export_wave_unit,
    )
else:
    reference = json.loads(args.reference.read_text())
result = compare_reference(measured, reference, args.visit, args.release)
record(
    "G4b-sptool",
    "L4",
    "pass" if result["numerical_pass"] else "fail",
    {},
    "# Independent export numerical comparison\n```json\n"
    + json.dumps(result, indent=2)
    + "\n```\nReviewer must authenticate export provenance; this script cannot self-certify independence.",
    [
        {"url": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
        for path in [args.measurements, args.reference]
    ],
    author="M",
    pins=[measured["pin"]],
    n_frames=len(reference["frame_ids"]),
    code_paths=["backend/spherex/reference.py", "scripts/verify/m_irsa_compare.py"],
    extra_files={
        "reference.json": json.dumps(reference, indent=2),
        "original-export.json": json.dumps(
            {
                "filename": args.reference.name,
                "sha256": hashlib.sha256(args.reference.read_bytes()).hexdigest(),
                "base64": base64.b64encode(args.reference.read_bytes()).decode("ascii"),
                "frame_map": json.loads(args.frame_map.read_text())
                if args.frame_map
                else None,
            },
            indent=2,
        ),
        "comparison.json": json.dumps(result, indent=2),
    },
)
