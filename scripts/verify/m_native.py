"""Collect real native 12 arcmin fields and measure F5/F15 without synthetic substitutes.

Uses two pinned fields, one QR2 + QR3 frame per detector per field; failures retained.
Calibration files must already be bootstrapped. Never declares G3 or G4b from these
sparse samples. Native pixels + genuine Gaia references test orientation/registration.
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "backend"), str(ROOT / "scripts")]
import numpy as np
from _m_evidence import record
from astropy import units as u
from astropy.coordinates import SkyCoord
from astropy.io import fits
from spherex.access.frames import snap_box
from spherex.access.http import make_client
from spherex.access.pins import load
from spherex.access.replay import RecordingTransport
from spherex.access.sources import build_source
from spherex.astrometry import isolated, registration, sky_covariance
from spherex.calib import Calib
from spherex.epsf import EPSF, fit_native
from spherex.external.gaia import GaiaClient
from spherex.preprocess import calibrate
from spherex.targets import Target, offline_target


async def main():
    cal = Calib(ROOT / ".cache/calib", verify=True)
    json.loads((ROOT / "config/pins/index.json").read_text())
    sys.stdout.reconfigure(encoding="utf-8")
    # Discover pins by target name, not insertion order or a guessed pin hash.
    pins = [
        load(p.stem, ROOT / "config/pins")
        for p in (ROOT / "config/pins").glob("*.json")
        if p.stem != "index"
    ]
    selected = []
    for key, ident in [("barnard", "NAME Barnard's Star"), ("epsindb", "* eps Ind B")]:
        pin = next(p for p in pins if key in str(p.doc).lower())
        target = offline_target(ident, key)
        refs = []
        for det in range(1, 7):
            for rel in ["qr2", "qr3"]:
                options = [
                    f for f in pin.frames if f.detector == det and rel in f.collection
                ]
                if options:
                    refs.append(options[len(options) // 2])
        selected.append((pin, target, refs))
    output = []
    inputs = []
    async with make_client(
        RecordingTransport(ROOT / ".cache/m-native/catalogs"), timeout=180
    ) as client:
        source = build_source(
            "irsa", client=client, cache_root=ROOT / ".cache/m-native/frames"
        )
        for pin, target, refs in selected:
            a, d = target.pos([np.median([f.t_min for f in refs])])
            ra, dec = float(a[0]), float(d[0])
            stars = await GaiaClient(client).cone(ra, dec, 0.1, g_max=18)
            keep = isolated([s.ra for s in stars], [s.dec for s in stars])
            stars = [s for s, k in zip(stars, keep, strict=True) if k]
            print("field", target.name, "isolated stars", len(stars), flush=True)
            for ref in refs:
                row = {
                    "target": target.name,
                    "frame": ref.id,
                    "detector": ref.detector,
                    "release": "qr3" if "qr3" in ref.collection else "qr2",
                    "stars": [],
                }
                try:
                    raw = await source.fetch(ref, snap_box(ra, dec, 12))
                    cf = calibrate(raw, cal, preset="photometry")
                    psf = EPSF(fits.getdata(cal.path("epsf", ref.detector), "EPSF"))
                    residuals = []
                    errors = []
                    for star in stars:
                        if star.ruwe is None or star.ruwe > 1.5 or star.pmra is None:
                            continue
                        SkyCoord(star.ra * u.deg, star.dec * u.deg)
                        t = Target(
                            "",
                            "star",
                            str(star.source_id),
                            star.ra,
                            star.dec,
                            2016.0,
                            star.pmra,
                            star.pmdec,
                            star.parallax,
                            star.radial_velocity,
                        )
                        a, d = t.pos([cf.mjd])
                        x, y = map(float, cf.wcs.world_to_pixel_values(a[0], d[0]))
                        try:
                            iz = psf.zone(x + cf.origin[0], y + cf.origin[1])
                        except ValueError:
                            continue
                        fit = fit_native(
                            cf.sci,
                            cf.var,
                            cf.bad_phot
                            | ((cf.flags & cf.bits.get("OVERFLOW", 0)) != 0),
                            psf,
                            iz,
                            x,
                            y,
                        )
                        if (
                            fit is None
                            or fit.wing_fit
                            or fit.params[2] < 10 * fit.errors[2]
                        ):
                            continue
                        ar, dr = cf.wcs.pixel_to_world_values(*fit.params[:2])
                        dx, dy = SkyCoord(
                            a[0] * u.deg, d[0] * u.deg
                        ).spherical_offsets_to(SkyCoord(ar * u.deg, dr * u.deg))
                        residuals.append([dx.arcsec, dy.arcsec])
                        errors.append(
                            np.sqrt(
                                np.diag(
                                    sky_covariance(
                                        cf.wcs,
                                        float(fit.params[0]),
                                        float(fit.params[1]),
                                        fit.covariance[:2, :2],
                                    )
                                )
                            )
                        )
                        row["stars"].append(
                            {
                                "id": star.source_id,
                                "rchi2": fit.rchi2,
                                "offset": [dx.arcsec, dy.arcsec],
                                "zone": iz,
                                "flux": float(fit.params[2]),
                                "lam": float(cf.lam[round(y), round(x)]),
                                "dlam": float(cf.dlam[round(y), round(x)]),
                                "correction": float(
                                    cal.fluxcorr[ref.detector][
                                        round(y + cf.origin[1]),
                                        round(x + cf.origin[0]),
                                    ]
                                ),
                            }
                        )
                    try:
                        reg = registration(residuals, errors)
                        row["registration"] = {
                            k: v.tolist() if isinstance(v, np.ndarray) else v
                            for k, v in reg.items()
                        }
                    except (ValueError, IndexError) as ex:
                        row["registration_error"] = str(ex)
                except Exception as ex:
                    logging.getLogger(__name__).exception(
                        "Native frame validation failed"
                    )
                    row["error"] = f"{type(ex).__name__}: {ex}"
                output.append(row)
                inputs.append(ref.access_url)
                print(
                    target.name,
                    ref.detector,
                    row.get("release"),
                    len(row["stars"]),
                    row.get("error", ""),
                    flush=True,
                )
    out = ROOT / ".cache/m-native/results.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(output, indent=2))
    counts = {
        d: sum(len(r["stars"]) for r in output if r["detector"] == d)
        for d in range(1, 7)
    }
    metrics = {
        f"D{d}_isolated_stars": dict(
            value=n,
            threshold=">=5 plus symmetric residuals and chi2 approximately 1",
            **{"pass": None},
        )
        for d, n in counts.items()
    }
    report = (
        "# Native real fields\n```json\n" + json.dumps(output, indent=2) + "\n```\n"
    )
    report += "Counts alone do not approve ePSF symmetry or reduced chi-square. Sparse fields do not prove target PM/spectra."
    medchi = {
        d: float(
            np.median(
                [s["rchi2"] for r in output if r["detector"] == d for s in r["stars"]]
            )
        )
        for d in range(1, 7)
    }
    report += "\nMedian reduced chi-square by detector: " + str(medchi)
    report += "\nThe short-band medians substantially exceed the required approximately unity behavior. "
    report += "Do not accept F5 or turn on measurement science from counts alone."
    for check in ["F5", "F15", "G3-rereg"]:
        record(
            check,
            "L3",
            "fail"
            if check == "F5" and any(v > 3 for v in medchi.values())
            else "inconclusive",
            metrics,
            report,
            inputs,
            n_frames=len(output),
            pins=[p.pin for p, _, _ in selected],
            author="M",
            code_paths=[
                "backend/spherex/epsf.py",
                "backend/spherex/astrometry.py",
                "scripts/verify/m_native.py",
            ],
        )


if __name__ == "__main__":
    asyncio.run(main())
