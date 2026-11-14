"""Fold retained R Dra native annulus bins against acquired AAVSO observations.

No optical-to-infrared amplitude equivalence or phase-lag threshold is invented.
The original >=20 independent SPHEREx-bin requirement remains mandatory.
"""

import csv
import hashlib
import io
import json
import os
import sys
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
os.environ.setdefault("MPLCONFIGDIR", str(ROOT / ".cache/matplotlib"))
import matplotlib

matplotlib.use("Agg")
from matplotlib import pyplot as plt

sys.path.insert(0, str(ROOT / "scripts"))
from _m_evidence import record

reference = (
    ROOT / "validation/M-aavso-lightcurve/2026-11-08-d6d2e45/reference-response.txt"
)
metadata = (
    ROOT / "validation/M-aavso-reference/2026-11-08-d6d2e45/reference-response.txt"
)
native = ROOT / ".cache/m-acceptance/rdra-lightcurve.json"
catalogue = json.loads(metadata.read_text())["VSXObject"]
period, epoch = float(catalogue["Period"]), float(catalogue["Epoch"])
table = ET.fromstring(reference.read_text()).findtext("Data")
if table is None:
    raise ValueError("VSX response has no observation data")
observations = []
for row in csv.DictReader(io.StringIO(table, newline=None)):
    if row.get("fainterThan") == "0" and row.get("band") in ("V", "Vis."):
        observations.append(
            {
                "jd": float(row["JD"]),
                "magnitude": float(row["mag"]),
                "band": row["band"],
                "uncertainty": row["uncert"],
                "validation": row.get("val"),
                "phase": ((float(row["JD"]) - epoch) / period) % 1,
            }
        )
data = json.loads(native.read_text())
infrared = [
    dict(p, band=band, phase=((p["mjd"] + 2400000.5 - epoch) / period) % 1)
    for band, points in data["bands"].items()
    for p in points
]
bins = {p["bin"] for p in infrared}
result = {
    "period_days": period,
    "epoch_hjd": epoch,
    "observations_by_band": dict(Counter(p["band"] for p in observations)),
    "spherex_points_by_detector": {k: len(v) for k, v in data["bands"].items()},
    "independent_spherex_bins": len(bins),
    "criterion_met": len(bins) >= 20,
    "timing_note": "JD/UTC phase used at plotting precision; heliocentric correction bounded by 8.4 minutes (phase <0.000024), negligible relative to 14-day bins. No sub-minute phase comparison claimed.",
    "comparison_note": "AAVSO V/visual magnitudes and SPHEREx IR relative flux are separate observables; phase lag and wavelength-dependent amplitude are not assumed zero. Visual uncertainties missing in archive remain missing. Figure is for independent coherence review, not an automatic pass.",
}
figure, axes = plt.subplots(2, 1, figsize=(10, 7), sharex=True, layout="constrained")
for band in ("V", "Vis."):
    points = [p for p in observations if p["band"] == band]
    axes[0].scatter(
        [p["phase"] for p in points],
        [p["magnitude"] for p in points],
        s=9,
        label=band,
        alpha=0.65,
    )
axes[0].invert_yaxis()
axes[0].set_ylabel("AAVSO magnitude")
axes[0].legend()
for band in data["bands"]:
    points = [p for p in infrared if p["band"] == band]
    axes[1].errorbar(
        [p["phase"] for p in points],
        [p["rel"] for p in points],
        yerr=[p["err"] for p in points],
        fmt="o",
        ms=4,
        label="D" + band,
    )
axes[1].set_ylabel("SPHEREx relative annulus flux")
axes[1].set_xlabel("Phase at VSX period 246.12 d / epoch HJD 2457370")
axes[1].legend()
axes[1].set_xlim(0, 1)
figure.suptitle(
    "R Dra independent phase comparison; only 18 SPHEREx time bins, unaccepted"
)
result["matplotlib_version"] = matplotlib.__version__
buf = io.BytesIO()
figure.savefig(buf, format="png", dpi=160)
plt.close(figure)
record(
    "M-aavso-phase",
    "L4",
    "inconclusive",
    {},
    "# Independent R Dra phase comparison\n```json\n"
    + json.dumps(result, indent=2)
    + "\n```\nThanks to AAVSO and its worldwide contributing observers for these public observations. This comparison does not pass G5.lc without sufficient SPHEREx bins, a successful periodogram, and independent coherence review.",
    [
        {"url": str(p), "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}
        for p in [reference, metadata, native]
    ],
    author="M",
    code_paths=["scripts/verify/m_aavso_phase.py"],
    extra_files={
        "reference-points.json": json.dumps(observations, indent=2),
        "spherex-phase-points.json": json.dumps(infrared, indent=2),
    },
    figures={"phase-comparison.png": buf.getvalue()},
)
print(json.dumps(result, indent=2))
