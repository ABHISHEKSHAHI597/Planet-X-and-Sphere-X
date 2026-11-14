"""Small real Pluto native-image diagnostic, separate from full G5.sso acceptance."""

import asyncio
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "backend"), str(ROOT / "scripts")]
import numpy as np
from _m_evidence import record
from app.services import Services
from app.settings import Settings
from astropy.io import fits
from astropy.wcs import WCS
from spherex.access.dedup import dedup
from spherex.access.frames import snap_box
from spherex.access.s3sections import S3SectionSource
from spherex.access.sources import build_source
from spherex.calib import Calib
from spherex.epsf import EPSF, fit_native
from spherex.external.horizons import positions
from spherex.preprocess import calibrate


async def main():
    svc = Services(
        Settings(
            cache_dir=ROOT / ".cache/m-pluto",
            calib_root=ROOT / ".cache/calib",
            cpu_workers=0,
            run_watcher=False,
        )
    )
    samples, inputs = [], []
    try:
        ((ra, dec),) = await positions(svc.client, "Pluto", [61000.0])
        rows = await svc.coverage.coverage(ra, dec, 0.15, svc.registry.collections())
        refs = dedup(rows, svc.registry).frames
        print(
            f"Pluto coverage: {len(rows)} rows, {len(refs)} deduplicated frames",
            flush=True,
        )
        selected = []
        rejected = []
        header_source = S3SectionSource(svc.client)
        for detector in range(1, 7):
            choices = sorted(
                [f for f in refs if f.detector == detector],
                key=lambda f: abs(f.t_min - 61000),
            )
            for candidate in choices[:12]:
                try:
                    headers = await header_source.headers(candidate.s3_key)
                    h = headers["IMAGE"].header
                    ((a, d),) = await positions(
                        svc.client, "Pluto", [float(h["MJD-AVG"])]
                    )
                    x, y = WCS(h).world_to_pixel_values(a, d)
                    if not (20 < x < h["NAXIS1"] - 20 and 20 < y < h["NAXIS2"] - 20):
                        rejected.append(
                            [candidate.id, "actual-epoch Pluto outside detector margin"]
                        )
                        continue
                    selected.append(candidate)
                    break
                except (ValueError, KeyError, TypeError) as ex:
                    rejected.append([candidate.id, str(ex)])
        cal = Calib(ROOT / ".cache/calib", verify=True)
        source = build_source(
            "irsa", client=svc.client, cache_root=ROOT / ".cache/m-pluto/frames"
        )
        for ref in selected:
            item = {"frame": ref.id, "detector": ref.detector}
            try:
                ((a, d),) = await positions(svc.client, "Pluto", [ref.t_min])
                raw = await source.fetch(ref, snap_box(a, d, 2.0))
                cf = calibrate(raw, cal, preset="photometry")
                ((a, d),) = await positions(svc.client, "Pluto", [cf.mjd])
                x, y = map(float, cf.wcs.world_to_pixel_values(a, d))
                psf = EPSF(fits.getdata(cal.path("epsf", cf.detector), "EPSF"))
                fit = fit_native(
                    cf.sci,
                    cf.var,
                    cf.bad_phot,
                    psf,
                    psf.zone(x + cf.origin[0], y + cf.origin[1]),
                    x,
                    y,
                )
                item.update(
                    mjd=cf.mjd,
                    predicted_pixel=[x, y],
                    native_shape=list(cf.sci.shape),
                    geometric_centre_distance_px=float(
                        np.hypot(
                            x - (cf.sci.shape[1] - 1) / 2, y - (cf.sci.shape[0] - 1) / 2
                        )
                    ),
                    native_array_sha256=hashlib.sha256(cf.sci.tobytes()).hexdigest(),
                    fit=None
                    if fit is None
                    else {
                        "centroid": fit.params[:2].tolist(),
                        "offset_px": float(np.linalg.norm(fit.params[:2] - [x, y])),
                        "snr": float(fit.params[2] / fit.errors[2]),
                        "rchi2": fit.rchi2,
                    },
                )
            except Exception as ex:
                import logging

                logging.getLogger(__name__).exception("Pluto native measurement failed")
                item["error"] = f"{type(ex).__name__}: {ex}"
            samples.append(item)
            inputs.append(ref.access_url)
    finally:
        await svc.close()
    record(
        "M-pluto-image-sample",
        "L3",
        "inconclusive",
        {},
        "# Pluto native diagnostic\n```json\n"
        + json.dumps({"samples": samples, "geometry_rejected": rejected}, indent=2)
        + "\n```\nAt most one available frame per detector nearest MJD61000; actual midpoint ephemerides used for cutouts. No every-frame or methane-ice acceptance inferred from this small sample.",
        inputs,
        n_frames=len(samples),
        author="M",
        code_paths=[
            "scripts/verify/m_pluto_image.py",
            "backend/spherex/epsf.py",
            "backend/spherex/ephem.py",
        ],
    )
    print(json.dumps(samples, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
