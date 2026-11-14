"""Audit retained native target measurements against catalogue tracks, without refitting pixels.

Historical extraction provenance/limitations remain explicit. This does not turn
an offline catalogue model into a new independently acquired L4 comparison.
"""

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "backend"), str(ROOT / "scripts")]
import numpy as np
from _m_evidence import record
from astropy import units as u
from astropy.coordinates import SkyCoord
from spherex.astrometry import visit_centroid
from spherex.targets import offline_target

results, inputs, snapshots = {}, [], {}
for name, ident in [
    ("barnard", "NAME Barnard's Star"),
    ("epsindb", "* eps Ind B"),
    ("wise0855", "WISE J085510.83-071442.5"),
]:
    path = ROOT / f".cache/m-acceptance/{name}-astrometry.json"
    data = json.loads(path.read_text())
    inputs.append(
        {"url": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
    )
    snapshots[path.name] = path.read_text()
    target = offline_target(ident, name)
    origin = (
        SkyCoord(*data["tangent_origin"], unit="deg")
        if data.get("tangent_origin")
        else None
    )
    visits = {}
    for p in data["points"]:
        if origin is None:
            continue  # Never guess a missing historical tangent origin.
        if not p.get("fit_included", True):
            continue
        a, d = target.pos([p["mjd"]])
        xi, eta = origin.spherical_offsets_to(SkyCoord(a[0] * u.deg, d[0] * u.deg))
        visits.setdefault(p["visit"], []).append(
            dict(p, xi=p["xi"] - xi.arcsec, eta=p["eta"] - eta.arcsec)
        )
    summaries = []
    for visit, points in visits.items():
        r = visit_centroid(points)
        cov, delta = r["covariance"], r["mean"]
        summaries.append(
            {
                "visit": visit,
                "n": len(points),
                "offset_arcsec": delta.tolist(),
                "covariance": cov.tolist(),
                "normalized_axes": (delta / np.sqrt(np.diag(cov))).tolist(),
                "mahalanobis2": float(delta @ np.linalg.solve(cov, delta)),
                "excess_chi2": r["chi2"],
                "dof": r["dof"],
            }
        )
    fit, catalogue = data.get("fit"), data.get("catalogue")
    comparison = None
    if fit and catalogue:
        comparison = {
            "measured_mu": fit["mu"],
            "catalogue_mu": catalogue["mu"],
            "measured_pa": fit["pa_deg"],
            "catalogue_pa": catalogue["pa_deg"],
            "mu_difference": fit["mu"] - catalogue["mu"],
            "pa_difference": (fit["pa_deg"] - catalogue["pa_deg"] + 180) % 360 - 180,
            "fit_chi2": fit["chi2"],
            "fit_dof": fit["dof"],
            "catalogue_source": catalogue["source"],
        }
    results[name] = {
        "track_block": "Historical extraction lacks tangent_origin; rerun native API"
        if origin is None
        else None,
        "reference_name": target.name,
        "extraction": "retained JSON; not a fresh pixel extraction",
        "visits": summaries,
        "catalogue_comparison": comparison,
    }
body = json.dumps(results, indent=2)
record(
    "G3-track",
    "L3",
    "fail"
    if any(v["mahalanobis2"] > 1 for r in results.values() for v in r["visits"])
    else "inconclusive",
    {},
    "# Catalogue-track residual audit\n```json\n"
    + body
    + "\n```\nPer-visit means of measured-minus-predicted residuals at the actual contributing epochs, full xy covariance and excess scatter. Reports standardized axes and 2D ellipse radius explicitly. Any >1 ellipse radius prevents a within-one-error claim; no acceptance inferred from sparse or high-chi-square measurements. Catalogue parameters are the documented model, not a new external export. WISE within-visit motion is catalogue-conditioned; independent offsets were fitted.",
    inputs,
    author="M",
    code_paths=[
        "scripts/verify/m_motion_reference.py",
        "backend/spherex/targets.py",
        "backend/spherex/astrometry.py",
    ],
    extra_files={"comparisons.json": body, **snapshots},
)
record(
    "G3-gaia",
    "L3",
    "inconclusive",
    {},
    "# Three-target retained catalogue comparison\n```json\n"
    + body
    + "\n```\nThis is a retained-output comparison, not a fresh independent L4 catalogue acquisition. Barnard central PM mismatch/excess chi-square and F5/F15 failures prevent acceptance; epsilon Indi central agreement alone does not validate errors. I review and an authentic provenance-bearing external astrometric comparison remain required.",
    inputs,
    author="M",
    code_paths=[
        "scripts/verify/m_motion_reference.py",
        "backend/spherex/targets.py",
        "backend/spherex/astrometry.py",
    ],
    extra_files={"comparisons.json": body},
)
print(body)
