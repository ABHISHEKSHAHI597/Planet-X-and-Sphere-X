"""MOCK=1 (workflow.md §8.5): golden manifests and payloads with realistic delays and SSE progress, so the
frontend works without a backend and the contract tests run against every endpoint. Never used in a demo:
`environment` is "mock" and every manifest says `data_source: "mock"`, which the UI shows as a MOCK badge.

Payloads are the contract golden `frontend/fixtures/golden/stack_F_121x121.f16` (regenerated from the real
encoder by scripts/make_goldens.py), so mock and real share the binary format bit for bit."""
from __future__ import annotations

import asyncio
import hashlib
from typing import Any

import numpy as np

from spherex.flags import CANONICAL_BITS, FLAG_INFO
from spherex.render import FORMAT_F16, FORMAT_F32, FORMAT_U32_FLAGS, to_f32, to_u32_flags

from .jobs import Job
from .render_png import decode_f16
from .settings import API_VERSION, REPO

GOLDEN = REPO / "frontend" / "fixtures" / "golden" / "stack_F_121x121.f16"
N = 121
PIX = 3.0
BINS = (("V1", "full", 60900.2, 60913.8, (2,)), ("V2", "full", 61080.4, 61096.1, (1,)),
        ("V3", "partial", 61262.0, 61263.1, (4,)))
MOCK_RELEASE = {"release_state": {"qr2": "2026W17_1B", "qr3": "2026W40_2A"}, "newest_period": "2026W40_2A",
                "checked_at": "2026-11-07T00:00:00+00:00"}


def golden_bytes() -> bytes:
    return GOLDEN.read_bytes()


def mock_key(request_canon: str) -> str:
    return "0000" + hashlib.sha256(("mock\n" + request_canon).encode()).hexdigest()[:20]


def manifest(key: str, params: dict[str, str], target: dict[str, Any] | None, ra: float, dec: float) -> dict[str, Any]:
    bins: dict[str, list[dict[str, Any]]] = {}
    stacks, frames = [], []
    for band in range(1, 7):
        bins[str(band)] = []
        for bid, status, t0, t1, surveys in BINS:
            n = 3 if status == "partial" else 12
            label = (f"{bid} · MOCK · S{surveys[0]} · partial ({n} in band {band})" if status == "partial"
                     else f"{bid} · MOCK · S{surveys[0]} · {n * 6} frames")
            bins[str(band)].append(dict(id=bid, band=band, status=status, mjd_mean=(t0 + t1) / 2, mjd_min=t0,
                                        mjd_max=t1, surveys=list(surveys), label=label, n_frames=n,
                                        n_visit_frames=n * 6))
            ids = [f"mock_{bid}_D{band}_{i:02d}.fits" for i in range(n)]
            skipped = [[ids[-1], "MOCK: fetch failed: HTTP 503 after 4 tries"]] if status == "full" else []
            stacks.append(dict(bin=bid, band=band, ready=False, format=FORMAT_F16, nhits_max=n, filled=False,
                               skipped=skipped, frame_ids=ids[:-1] if skipped else ids))
            for i, fid in enumerate(ids):
                frames.append(dict(id=fid, band=band, detector=band, bin=bid, mjd=t0 + i * (t1 - t0) / max(n - 1, 1),
                                   survey=surveys[0], obsid=f"mock{bid}{i:02d}", release="qr3", collection="spherex_qr3",
                                   pipeline="v27", qa={"L1DQAFLG": "Pass", "L2DQAFLG": "Pass", "FINAST": 0},
                                   skipped=skipped[0][1] if skipped and fid == skipped[0][0] else None))
    return dict(schema_version=API_VERSION, key=key, pin="000000000000", newer_pin=None, params=params, target=target,
                grid=dict(ctype=["RA---TAN", "DEC--TAN"], crval=[ra, dec], crpix=[(N + 1) / 2, (N + 1) / 2],
                          cdelt=[-PIX / 3600, PIX / 3600], shape=[N, N], pix_arcsec=PIX, native=False),
                axis="visit", bands=list(range(1, 7)), bins=bins, stacks=stacks,
                limits={str(b): dict(lo=0.0, hi=100.0, lim="zscale") for b in range(1, 7)}, frames=frames, track=[],
                flags=dict(bits=dict(CANONICAL_BITS), info=dict(FLAG_INFO), format=FORMAT_U32_FLAGS),
                formats=dict(stack=FORMAT_F16, science=FORMAT_F32, flags=FORMAT_U32_FLAGS), release=MOCK_RELEASE,
                warnings=[dict(code="mock", severity="warn", message="MOCK data: the golden test pattern, not the sky")],
                data_source="mock", _complete=False, _request="mock")


async def run(svc: Any, m: dict[str, Any], job: Job, delay_s: float = 0.03) -> None:
    """Simulated job: selected band first, then the rest, with the real event sequence."""
    key = m["key"]
    sel = int((m["params"].get("bands", "6").removeprefix("rgb:").split(",")[0]) or 6) \
        if m["params"].get("bands", "6")[-1].isdigit() else 4
    g = golden_bytes()
    img = decode_f16(g, (N, N))
    payloads = {"f16": g, "f32": to_f32(img), "var.f32": to_f32(np.ones((N, N))),
                "flags.u32": to_u32_flags(np.where(img > 90, 1 << CANONICAL_BITS["SOURCE"], 0))}
    n = len(m["frames"])
    job.emit({"type": "planned", "n": n})
    i = 0
    order = sorted(m["stacks"], key=lambda s: (s["band"] != sel, s["band"]))
    for s in order:
        await asyncio.sleep(delay_s)
        i = min(n, i + len(s["frame_ids"]) + len(s["skipped"]))
        job.emit({"type": "fetched", "i": i, "n": n})
        for fid, why in s["skipped"]:
            job.emit({"type": "warning", "code": "frame_skipped", "message": f"{fid}: {why}"})
        svc.store.put_stack(key, s["bin"], s["band"], payloads)
        s["ready"] = True
        svc.store.put_manifest(key, m)
        job.emit({"type": "stack_ready", "bin": s["bin"], "band": s["band"]})
    m["_complete"] = True
    svc.store.put_manifest(key, m)


MOCK_SCIENCE: dict[str, Any] = {
    "spectrum": dict(rows=[dict(lam=4.6, dlam=0.04, flux=12.0, err=1.0, mjd=60907.0, visit="V1", detector=6, flags=[],
                                rchi2=1.0, contaminated=False, release="qr3")],
                     indices=None, validity="unvalidated", notes=["MOCK spectrum: not a measurement"]),
    "astrometry": dict(points=[], fit=None, catalogue=None, validity="unvalidated"),
    "lightcurve": dict(bands={}, periodogram=None, method="psf", label="MOCK", validity="unvalidated"),
}
