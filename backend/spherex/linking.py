"""Mover chains, motion scores and mandatory artifact vetting (impl. §4.10)."""

from __future__ import annotations

from typing import Any

import numpy as np
from scipy.spatial import cKDTree

from .astrometry import motion_fit


def link_detections(
    epochs: list[list[dict[str, Any]]],
    mu_max: float = 10.0,
    plx_max: float = 1.0,
    pixel_arcsec: float = 6.15,
    max_chains: int = 100000,
) -> list[list[dict[str, Any]]]:
    """All plausible adjacent-epoch links in tangent-plane arcsec; no greedy nearest bias.

    Ambiguous branches remain distinct; exceeding the budget refuses the search.
    One-bin orphans are returned for SSO queues, but never given a motion score.
    """
    chains: list[list[dict[str, Any]]] = []
    for detections in sorted(epochs, key=lambda e: min((d["mjd"] for d in e), default=np.inf)):
        if not detections:
            continue
        tree = cKDTree([[d["xi"], d["eta"]] for d in detections])
        next_chains = []
        used = set()
        for chain in chains:
            last = chain[-1]
            dt = (detections[0]["mjd"] - last["mjd"]) / 365.25
            rad = max(1.5 * pixel_arcsec, mu_max * abs(dt) + 2 * plx_max)
            idx = tree.query_ball_point([last["xi"], last["eta"]], rad)
            if not idx:
                next_chains.append(chain)
            for i in idx:
                used.add(i)
                next_chains.append(chain + [detections[i]])
        next_chains += [[d] for i, d in enumerate(detections) if i not in used]
        if len(next_chains) > max_chains:
            raise ValueError("ambiguous field exceeds chain budget; narrow field or motion prior")
        chains = next_chains
    return chains


def vet_detection(d: dict[str, Any], max_rchi2: float) -> list[str]:
    """Missing vetting is a failure, never a clean candidate."""
    why = []
    if "flags" not in d or "rchi2" not in d or "bright_neighbours" not in d:
        why.append("incomplete native-frame vetting")
    if d.get("catalogue_complete") is False:
        why.append("incomplete catalogue checks")
    why += sorted(set(d.get("flags", [])) & {"GHOST", "GHOST_FPA", "GHOST_EXT", "CROSSTALK", "PERSIST", "BLOOM"})
    if not np.isfinite(d.get("rchi2", np.nan)) or d.get("rchi2", np.inf) > max_rchi2:
        why.append("PSF residuals")
    for dx, dy in d.get("bright_neighbours", []):
        if (abs(abs(dy) - 32) < 1 and abs(dx) < 1) or (
            abs(dy) < 1 and abs(dx) >= 63 and abs(dx / 64 - round(dx / 64)) < 1 / 64
        ):
            why.append("detector echo geometry")
    return why


def score_chain(
    chain: list[dict[str, Any]], plx_fixed: float | None, max_rchi2: float, pixel_arcsec: float = 6.15
) -> dict[str, Any]:
    t = np.array([d["mjd"] for d in chain]) / 365.25
    r = motion_fit(
        t,
        [d["xi"] for d in chain],
        [d["eta"] for d in chain],
        [d["s_xi"] for d in chain],
        [d["s_eta"] for d in chain],
        [d["p_a"] for d in chain],
        [d["p_d"] for d in chain],
        float(np.mean(t)),
        plx_fixed,
    )
    pm = r["params"][2:4]
    c = r["covariance"][2:4, 2:4]
    mu = float(np.linalg.norm(pm))
    emu = float(np.sqrt(pm @ c @ pm) / mu) if mu else float(np.sqrt(np.trace(c)))
    shift = mu * np.ptp(t) / pixel_arcsec
    why = sorted({w for d in chain for w in vet_detection(d, max_rchi2)})
    if len({d["known"] for d in chain if d.get("known")}) > 1:
        why.append("inconsistent catalogue identifiers")
    accepted = r["delta_chi2"] > 25 and mu > 3 * emu and shift > 0.3 and not why
    return dict(
        score=r["delta_chi2"],
        mu=mu,
        e_mu=emu,
        shift_px=float(shift),
        pa_deg=float(np.degrees(np.arctan2(pm[0], pm[1])) % 360),
        candidate=bool(accepted),
        vetoes=why,
        known=next((d.get("known") for d in chain if d.get("known")), None),
        fit=r,
    )
