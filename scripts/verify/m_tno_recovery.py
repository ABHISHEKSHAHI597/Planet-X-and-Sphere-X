"""Small real-image blind-peak TNO recovery experiment; not full orphan-gate acceptance.

Six epochs per body are selected by date/coverage, never by measured S/N. All
misses are retained. Horizons selects footprints and evaluates recovery only;
the detector and native fitter are seeded by blind peaks, not ephemerides.
"""

import asyncio
import hashlib
import json
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "backend"), str(ROOT / "scripts")]
import numpy as np
from _m_evidence import record
from app.services import Services
from app.settings import Settings
from astropy import units as u
from astropy.coordinates import SkyCoord
from astropy.io import fits
from astropy.wcs import WCS
from spherex.access.dedup import dedup
from spherex.access.frames import snap_box
from spherex.access.replay import RecordingTransport
from spherex.access.s3sections import S3SectionSource
from spherex.access.sources import build_source
from spherex.calib import Calib
from spherex.epsf import EPSF, fit_native
from spherex.external.horizons import positions
from spherex.grid import significance
from spherex.movers import detect
from spherex.planetx import infer_distance
from spherex.preprocess import calibrate


async def main():
    cache = ROOT / ".cache/m-tno"
    svc = Services(
        Settings(
            cache_dir=cache,
            calib_root=ROOT / ".cache/calib",
            cpu_workers=0,
            run_watcher=False,
        ),
        transport=RecordingTransport(cache / "http"),
    )
    output, inputs = {}, []
    cal = Calib(ROOT / ".cache/calib", verify=True)
    source = build_source("irsa", client=svc.client, cache_root=cache / "frames")
    headers = S3SectionSource(svc.client)
    try:
        for name in ("Makemake", "Haumea", "Eris"):
            result = {"samples": [], "rejected": [], "errors": []}
            output[name] = result
            try:
                coords = await positions(svc.client, name, [60900.0, 61200.0])
                rows = []
                for a, d in coords:
                    rows.extend(
                        await svc.coverage.coverage(
                            a, d, 0.25, svc.registry.collections()
                        )
                    )
                refs = [f for f in dedup(rows, svc.registry).frames if f.detector == 6]
                selected, used = [], set()
                if refs:
                    for epoch in np.linspace(
                        min(f.t_min for f in refs), max(f.t_min for f in refs), 6
                    ):
                        choices = sorted(
                            [f for f in refs if int(f.t_min) not in used],
                            key=lambda f: abs(f.t_min - epoch),
                        )
                        for candidate in choices[:8]:
                            h = (await headers.headers(candidate.s3_key))[
                                "IMAGE"
                            ].header
                            mjd = float(h["MJD-AVG"])
                            ((a, d),) = await positions(svc.client, name, [mjd])
                            x, y = WCS(h).world_to_pixel_values(a, d)
                            if not (
                                35 < x < h["NAXIS1"] - 35 and 35 < y < h["NAXIS2"] - 35
                            ):
                                result["rejected"].append(
                                    [
                                        candidate.id,
                                        "actual epoch outside detector margin",
                                    ]
                                )
                                continue
                            selected.append((candidate, a, d))
                            used.add(int(candidate.t_min))
                            break
                psf = EPSF(fits.getdata(cal.path("epsf", 6), "EPSF"))
                measured = []
                for ref, a, d in selected:
                    sample = {"frame": ref.id, "url": ref.access_url}
                    result["samples"].append(sample)
                    try:
                        raw = await source.fetch(ref, snap_box(a, d, 6.0))
                        cf = calibrate(raw, cal, preset="discovery")
                        sample.update(
                            mjd=cf.mjd,
                            native_sha256=hashlib.sha256(cf.sci.tobytes()).hexdigest(),
                            qa=cf.qa,
                        )
                        inputs.append(ref.access_url)
                        if not cf.qa["ok"]:
                            sample["reason"] = "frame QA"
                            continue
                        ((a, d),) = await positions(svc.client, name, [cf.mjd])
                        x, y = cf.wcs.world_to_pixel_values(a, d)
                        valid = (
                            ~cf.bad_phot
                            & np.isfinite(cf.sci)
                            & np.isfinite(cf.var)
                            & (cf.var > 0)
                        )
                        image = cf.sci - np.median(cf.sci[valid])
                        sig, scale = significance(image, cf.var, valid)
                        peaks = detect(sig, mask=~valid)
                        sample.update(
                            sky_scale=float(scale),
                            n_peaks=len(peaks),
                            predicted_pixel=[float(x), float(y)],
                            recovered=[],
                        )
                        for peak in peaks:
                            px, py = float(peak["x"]), float(peak["y"])
                            z = psf.zone(px + cf.origin[0], py + cf.origin[1])
                            fit = fit_native(
                                cf.sci, cf.var, cf.bad_phot, psf, z, px, py
                            )
                            if fit is None:
                                continue
                            distance = float(np.linalg.norm(fit.params[:2] - [x, y]))
                            if distance > 1:
                                continue
                            aa, dd = cf.wcs.pixel_to_world_values(*fit.params[:2])
                            item = {
                                "ra": float(aa),
                                "dec": float(dd),
                                "offset_px": distance,
                                "snr": float(fit.params[2] / fit.errors[2]),
                                "rchi2": fit.rchi2,
                            }
                            sample["recovered"].append(item)
                        if len(sample["recovered"]) == 1:
                            measured.append(dict(mjd=cf.mjd, **sample["recovered"][0]))
                        print(
                            name,
                            ref.id,
                            "matches",
                            len(sample["recovered"]),
                            flush=True,
                        )
                    except Exception as ex:
                        logging.getLogger(__name__).exception("Native TNO sample failed")
                        sample["error"] = f"{type(ex).__name__}: {ex}"
                result["distance"] = None
                if len(measured) >= 4:
                    sky = SkyCoord(
                        [m["ra"] for m in measured] * u.deg,
                        [m["dec"] for m in measured] * u.deg,
                    )
                    xi, eta = sky[0].spherical_offsets_to(sky)
                    # Explicit exploratory 1-arcsec errors; cannot certify
                    # distance uncertainty until registration is validated.
                    result["distance"] = infer_distance(
                        [m["mjd"] for m in measured],
                        xi.arcsec,
                        eta.arcsec,
                        np.ones(len(measured)),
                        sky[0].ra.deg,
                        sky[0].dec.deg,
                    )
                result["n_recovered_days"] = len(measured)
            except Exception as ex:
                logging.getLogger(__name__).exception("TNO experiment failed")
                result["errors"].append(f"{type(ex).__name__}: {ex}")
            (cache / "progress.json").write_text(
                json.dumps(output, indent=2, default=str)
            )
    finally:
        await svc.close()
    record(
        "M-tno-image-recovery",
        "L3",
        "inconclusive",
        {},
        "# Blind native TNO sample experiment\n```json\n"
        + json.dumps(output, indent=2, default=str)
        + "\n```\nSingle-frame detection misses do not imply an all-day stack non-detection. This tests a small available sample, not the complete daily orphan linker, spectral compatibility or independent distance gate. No unavailable/faint body is counted as recovered. Full recording and FITS cache: .cache/m-tno; progress is resumable evidence, not acceptance.",
        inputs,
        author="M",
        n_frames=len(inputs),
        code_paths=[
            "scripts/verify/m_tno_recovery.py",
            "backend/spherex/epsf.py",
            "backend/spherex/planetx.py",
            "backend/spherex/movers.py",
        ],
        extra_files={"samples.json": json.dumps(output, indent=2, default=str)},
    )


if __name__ == "__main__":
    asyncio.run(main())
