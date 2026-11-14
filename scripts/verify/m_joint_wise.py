"""Offline joint-visit experiment on retained WISE native frames and registrations.

Replay fails on any missing HTTP response; no fresh archive traffic or pixels.
Uses every registration retained by the production joint-fit run; the earlier
individual-fit experiment remains in superseded evidence.
"""

import asyncio
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "backend"), str(ROOT / "scripts")]
import numpy as np
from _m_evidence import record
from app.measurement import epsfs, inputs, target_from_manifest
from app.pipeline import plan_view, skeleton
from app.services import Services
from app.settings import Settings
from astropy import units as u
from astropy.coordinates import SkyCoord
from spherex.access.replay import ReplayTransport
from spherex.external.gaia import GaiaClient
from spherex.joint_astrometry import fit_visit, prepare_frame
from spherex.preprocess import calibrate
from spherex.targets import Target


async def main():
    path = ROOT / ".cache/m-acceptance/wise0855-astrometry.json"
    old = json.loads(path.read_text())
    svc = Services(
        Settings(
            cache_dir=ROOT / ".cache/m-acceptance",
            calib_root=ROOT / ".cache/calib",
            cpu_workers=0,
            run_watcher=False,
        ),
        transport=ReplayTransport(ROOT / ".cache/m-acceptance/http"),
    )
    try:
        plan = await plan_view(
            svc, {"q": "WISE 0855", "pin": old["pin"], "fov": "12", "px": "6.15"}
        )
        svc.store.put_manifest(plan.key, skeleton(svc, plan))
        ra, dec = old["tangent_origin"]
        m, raws, cal = await inputs(
            svc, ra, dec, key=plan.key, min_fov=30, detectors=(6,)
        )
        target = target_from_manifest(m, ra, dec, True)
        (neighbour,) = await GaiaClient(svc.client).by_id([5756956644387831296])
        neighbour = Target(
            "",
            "star",
            "neighbour",
            neighbour.ra,
            neighbour.dec,
            2016.0,
            neighbour.pmra,
            neighbour.pmdec,
            neighbour.parallax,
            neighbour.radial_velocity,
        )
        psf = epsfs(cal, [6])[6]
        registrations = {r["frame"]: r for r in old["registration"]}
        fbin = {r["id"]: r["bin"] for r in m["frames"]}
        full = {b["id"] for b in m["bins"]["6"] if b["status"] == "full"}
        groups, excluded = {}, []
        for raw in raws:
            fid = raw.ref.id
            if fbin[fid] not in full:
                continue
            if fid not in registrations:
                excluded.append([fid, "no retained registration; not silently imputed"])
                continue
            cf = calibrate(raw, cal, preset="photometry")
            rr = registrations[fid]
            a, d = target.pos([cf.mjd])
            na, nd = neighbour.pos([cf.mjd])

            frame = prepare_frame(
                cf,
                psf,
                (a[0], d[0]),
                (na[0], nd[0]),
                {"offset": rr["offset_arcsec"], "error": rr["error_arcsec"]},
            )
            groups.setdefault(fbin[fid], []).append((frame, cf.mjd, fid))
        output = []
        origin = SkyCoord(ra * u.deg, dec * u.deg)
        for visit, entries in groups.items():
            fit = fit_visit([e[0] for e in entries])
            epoch = float(np.mean([e[1] for e in entries]))
            a, d = target.pos([epoch])
            xi, eta = origin.spherical_offsets_to(SkyCoord(a[0] * u.deg, d[0] * u.deg))
            fit.update(
                visit=visit,
                mjd=epoch,
                position_arcsec=np.array([xi.arcsec, eta.arcsec])
                + fit["offset_arcsec"],
                frame_ids=[e[2] for e in entries],
            )
            output.append(fit)
            print(
                visit,
                fit["n_frames"],
                fit["offset_arcsec"],
                fit["chi2"] / fit["dof"],
                flush=True,
            )
        output.sort(key=lambda r: r["mjd"])
        delta = output[-1]["position_arcsec"] - output[0]["position_arcsec"]
        result = {
            "visits": output,
            "excluded": excluded,
            "displacement_px": float(np.linalg.norm(delta) / 6.15),
            "pa_deg": float(np.degrees(np.arctan2(*delta)) % 360),
        }
        body = json.dumps(result, indent=2, default=lambda v: v.tolist())
        record(
            "M-wise-joint",
            "L3",
            "inconclusive",
            {},
            "# Joint native WISE visit experiment\n```json\n"
            + body
            + "\n```\nReplays all retained production registrations; exclusions explicit. Three starts per visit check competing modes. This is not G3 acceptance. Conditional PSF/Gaussian registration errors and systematic coverage require independent review.",
            [
                {
                    "url": str(path),
                    "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                }
            ],
            author="M",
            pins=[old["pin"]],
            n_frames=sum(len(v) for v in groups.values()),
            code_paths=[
                "scripts/verify/m_joint_wise.py",
                "backend/spherex/joint_astrometry.py",
                "backend/spherex/epsf.py",
            ],
            extra_files={"joint-measurements.json": body},
        )
        print(result["displacement_px"], result["pa_deg"])
    finally:
        await svc.close()


if __name__ == "__main__":
    asyncio.run(main())
