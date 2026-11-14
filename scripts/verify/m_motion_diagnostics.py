"""Offline audit of retained native WISE centroids, not an acceptance rerun."""

import hashlib
import json
import sys
from pathlib import Path

import numpy as np
from astropy import units as u
from astropy.coordinates import SkyCoord

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "backend"), str(ROOT / "scripts")]
from _m_evidence import record
from m_acceptance import metadata_evidence
from spherex.targets import offline_target

path = ROOT / ".cache/m-acceptance/wise0855-individual-astrometry.json"
out = json.loads(path.read_text())
origin = SkyCoord(*out["tangent_origin"], unit="deg")
target = offline_target("WISE J085510.83-071442.5", "wise")
visits = {}
for p in out["points"]:
    if p.get("fit_included"):
        visits.setdefault(p["visit"], []).append(p)
summary = []
for visit, points in visits.items():
    precision = []
    measured = []
    predicted = []
    for p in points:
        c = np.array(
            [
                [p["s_xi"] ** 2, p.get("cov_xi_eta", 0)],
                [p.get("cov_xi_eta", 0), p["s_eta"] ** 2],
            ]
        )
        precision.append(np.linalg.inv(c))
        measured.append([p["xi"], p["eta"]])
        a, d = target.pos([p["mjd"]])
        dx, dy = origin.spherical_offsets_to(SkyCoord(a[0] * u.deg, d[0] * u.deg))
        predicted.append([dx.arcsec, dy.arcsec])
    w = np.array(precision)
    cov = np.linalg.inv(w.sum(axis=0))
    mean = cov @ np.einsum("nij,nj->i", w, measured)
    prediction = cov @ np.einsum("nij,nj->i", w, predicted)
    residual = np.array(measured) - mean
    chi = float(np.einsum("ni,nij,nj", residual, w, residual))
    if len(points) > 1:
        cov *= max(1.0, chi / (2 * len(points) - 2))
    summary.append(
        {
            "visit": visit,
            "n": len(points),
            "mjd": float(np.mean([p["mjd"] for p in points])),
            "mean": mean.tolist(),
            "predicted": prediction.tolist(),
            "covariance": cov.tolist(),
            "chi2": chi,
            "dof": 2 * len(points) - 2,
            "arithmetic": np.mean(measured, axis=0).tolist(),
        }
    )
summary.sort(key=lambda p: p["mjd"])
delta = np.subtract(summary[-1]["mean"], summary[0]["mean"])
predicted_delta = np.subtract(summary[-1]["predicted"], summary[0]["predicted"])
cov = np.array(summary[-1]["covariance"]) + summary[0]["covariance"]
gradient = np.array([delta[1], -delta[0]]) / (delta @ delta)
result = {
    "visits": summary,
    "delta_arcsec": delta.tolist(),
    "displacement_px": float(np.linalg.norm(delta) / 6.15),
    "pa_deg": float(np.degrees(np.arctan2(*delta)) % 360),
    "pa_error_deg": float(np.degrees(np.sqrt(gradient @ cov @ gradient))),
    "predicted_delta_arcsec": predicted_delta.tolist(),
    "predicted_pa_deg": float(np.degrees(np.arctan2(*predicted_delta)) % 360),
    "convention": "xi east, eta north; atan2(east,north), later minus earlier. Visit covariances inflated for excess scatter; not shared systematics.",
}
record(
    "M-wise-motion-diagnostic",
    "L3",
    "inconclusive",
    {},
    "# Retained native WISE motion audit\n```json\n"
    + json.dumps(result, indent=2)
    + "\n```\nNo coordinate flip, epoch swap, new rejection or threshold change. Not a fresh native extraction. F5/F15 and visit-correlated systematic uncertainties remain open.",
    [{"url": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}],
    author="M",
    pins=[out["pin"]],
    code_paths=[
        "scripts/verify/m_motion_diagnostics.py",
        "backend/spherex/targets.py",
        "backend/spherex/astrometry.py",
    ],
)
print(json.dumps(result, indent=2))
record(
    "M-wise-individual-reanalysis",
    "L3",
    "pass"
    if abs(result["displacement_px"] - 0.78) <= 0.3
    and abs((result["pa_deg"] - 277 + 180) % 360 - 180) <= 20
    else "fail",
    {
        "displacement_px": dict(
            value=result["displacement_px"],
            threshold="0.78 +/-0.3",
            **{"pass": abs(result["displacement_px"] - 0.78) <= 0.3},
        ),
        "pa_deg": dict(
            value=result["pa_deg"],
            threshold="277 +/-20",
            **{"pass": abs((result["pa_deg"] - 277 + 180) % 360 - 180) <= 20},
        ),
    },
    "# Covariance-aware reanalysis of retained native WISE centroids\n```json\n"
    + json.dumps(result, indent=2)
    + "\n```\nSupersedes arithmetic visit means. No new native extraction; the input measurement JSON checksum is retained. No threshold/epoch/order/convention change.",
    [{"url": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}],
    author="M",
    pins=[out["pin"]],
    n_frames=sum(p["n"] for p in summary),
    extra_files={**metadata_evidence(), "native-measurements.json": path.read_text()},
    code_paths=[
        "scripts/verify/m_motion_diagnostics.py",
        "backend/spherex/astrometry.py",
        "scripts/verify/m_acceptance.py",
    ],
)
