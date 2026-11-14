"""F4 empirical matched-wavelength, native-frame field-star QR2/QR3 comparison.

Uses already collected pinned epsilon Indi fields; no Rayleigh-Jeans colour model
and no interpolation across a different wavelength is used to decide direction.
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
from astropy.io import fits
from astropy.wcs import WCS
from spherex.access.http import make_client
from spherex.access.replay import ReplayTransport
from spherex.calib import Calib
from spherex.epsf import EPSF, fit_native
from spherex.external.gaia import GaiaClient
from spherex.photometry import to_uJy
from spherex.preprocess import calibrate
from spherex.targets import Target
from spherex.types import RawFrame


def measure(sample, cal, psf, release):
    _lam, _dl, path, h, origin, x, y = sample
    with fits.open(path, memmap=False) as hl:
        hdus = {
            n: (hl[n].header.copy(), np.array(hl[n].data))
            for n in ("IMAGE", "VARIANCE", "FLAGS", "ZODI")
        }
    cf = calibrate(
        RawFrame(hdus, WCS(h), origin, release=release), cal, preset="photometry"
    )
    fit = fit_native(
        cf.sci,
        cf.var,
        cf.bad_phot | ((cf.flags & cf.bits.get("OVERFLOW", 0)) != 0),
        psf,
        psf.zone(origin[0] + x, origin[1] + y),
        x,
        y,
        fixed_xy=True,
    )
    if fit is None or fit.wing_fit or not cf.qa["ok"]:
        return None
    xp, yp = round(x + origin[0]), round(y + origin[1])
    area = float(cal.solid_angle[6][yp, xp])
    return tuple(float(to_uJy(f, area)) for f in (fit.params[0], fit.errors[0]))


def provenance(sample):
    p = sample[2]
    meta = json.loads(p.with_suffix(".json").read_text())
    return {
        "url": meta["access_url"],
        "box": meta["box"],
        "sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
    }


async def main():
    sys.stdout.reconfigure(encoding="utf-8")
    results = json.loads((ROOT / ".cache/m-native/results.json").read_text())
    ids = sorted(
        {
            s["id"]
            for r in results
            if r["target"] == "eps Ind B" and r["detector"] == 6
            for s in r["stars"]
        }
    )
    cal = Calib(ROOT / ".cache/calib", verify=True)
    psf = EPSF(fits.getdata(cal.path("epsf", 6), "EPSF"))
    async with make_client(ReplayTransport(ROOT / ".cache/m-f4/catalogs")) as client:
        stars = await GaiaClient(client).by_id(ids)
    frames = []
    for path in (ROOT / ".cache/m-acceptance").rglob("*.fits"):
        h = fits.getheader(path, "IMAGE")
        if int(h["DETECTOR"]) != 6:
            continue
        meta = json.loads(path.with_suffix(".json").read_text())
        if "331." not in meta.get("box", "") and not (
            320 < float(h.get("CRVAL1", 0)) < 340
        ):
            continue
        frames.append((path, h, meta))
    pairs = []
    repeats = []
    for s in stars:
        target = Target(
            "",
            "star",
            str(s.source_id),
            s.ra,
            s.dec,
            2016.0,
            s.pmra,
            s.pmdec,
            s.parallax,
            s.radial_velocity,
        )
        samples = {"qr2": [], "qr3": []}
        for path, h, meta in frames:
            rel = meta["release"]
            a, d = target.pos([h["MJD-AVG"]])
            w = WCS(h)
            x, y = map(float, w.world_to_pixel_values(a[0], d[0]))
            origin = tuple(meta["origin"])
            xp, yp = round(x + origin[0]), round(y + origin[1])
            if not (
                4 < x < int(h["NAXIS1"]) - 4
                and 4 < y < int(h["NAXIS2"]) - 4
                and 0 <= xp < 2040
                and 0 <= yp < 2040
            ):
                continue
            samples[rel].append(
                (
                    float(cal.cwave[6][yp, xp]),
                    float(cal.cband[6][yp, xp]),
                    path,
                    h,
                    origin,
                    x,
                    y,
                )
            )
        for release, values in samples.items():
            candidates = [
                (a, b)
                for a in values
                for b in values
                if b[3]["MJD-AVG"] - a[3]["MJD-AVG"] > 60
            ]
            if candidates:
                c, d = min(
                    candidates,
                    key=lambda pair: abs(pair[0][0] - pair[1][0]) / pair[0][1],
                )
                gap = abs(c[0] - d[0]) / c[1]
                if gap <= 0.1:
                    f, g = measure(c, cal, psf, release), measure(d, cal, psf, release)
                    if f and g and min(f[0] / f[1], g[0] / g[1]) >= 5:
                        variance = (
                            f[1] ** 2
                            + g[1] ** 2
                            + (0.03 * f[0]) ** 2
                            + (0.03 * g[0]) ** 2
                        )
                        repeats.append(
                            {
                                "source_id": s.source_id,
                                "release": release,
                                "channel_gap": gap,
                                "fluxes": [f, g],
                                "chi2": (f[0] - g[0]) ** 2 / variance,
                                "dof": 1,
                                "inputs": [provenance(c), provenance(d)],
                            }
                        )
        if not samples["qr2"] or not samples["qr3"]:
            continue
        a, b = min(
            ((a, b) for a in samples["qr2"] for b in samples["qr3"]),
            key=lambda pair: abs(pair[0][0] - pair[1][0]) / pair[0][1],
        )
        gap = abs(a[0] - b[0]) / a[1]
        if gap > 0.1:
            continue
        flux = []
        for sample, release in ((a, "qr2"), (b, "qr3")):
            measurement = measure(sample, cal, psf, release)
            if measurement is None:
                break
            flux.append(measurement)
        if len(flux) != 2 or min(f[0] for f in flux) <= 0:
            continue
        xp, yp = round(a[5] + a[4][0]), round(a[6] + a[4][1])
        fc = float(cal.fluxcorr[6][yp, xp])
        ratio = flux[0][0] / flux[1][0]
        pairs.append(
            {
                "source_id": s.source_id,
                "channel_gap": gap,
                "qr2_flux": flux[0],
                "qr3_flux": flux[1],
                "factor": fc,
                "uncorrected_ratio": ratio,
                "multiplied_ratio": ratio * fc,
                "divided_ratio": ratio / fc,
                "qr2_path": str(a[2]),
                "qr3_path": str(b[2]),
                "inputs": [provenance(a), provenance(b)],
            }
        )
    improve = bool(pairs) and bool(
        np.median([abs(p["multiplied_ratio"] - 1) for p in pairs])
        < np.median([abs(p["uncorrected_ratio"] - 1) for p in pairs])
    )
    record(
        "F4",
        "L3",
        "pass" if improve else "inconclusive",
        {
            "matched_pairs": dict(
                value=len(pairs),
                threshold="at least one isolated star at matching wavelength",
                **{"pass": bool(pairs)},
            ),
            "multiplication_improves": dict(
                value=improve,
                threshold="corrected QR2 agrees better with QR3",
                **{"pass": improve},
            ),
        },
        "# F4 empirical comparison\nHeader states multiplicative. Native D6 Fnu (microJy, position-dependent pixel area), wavelengths within 0.1 CBAND; no spectral colour correction.\n"
        "```json\n"
        + json.dumps(pairs, indent=2)
        + "\n```\nF5 residual failure and independent I review remain separate gate dependencies.",
        [i for p in pairs for i in p["inputs"]],
        author="M",
        n_frames=2 * len(pairs),
        pins=["3addc0f80339"],
        code_paths=[
            "backend/spherex/photometry.py",
            "backend/spherex/epsf.py",
            "backend/spherex/preprocess.py",
            "scripts/verify/m_f4.py",
        ],
    )
    record(
        "G4b-repeat",
        "L3",
        "inconclusive",
        {
            "matched_same_scale_pairs": dict(
                value=len(repeats),
                threshold="same release, matching wavelength, >60 days apart",
                **{"pass": bool(repeats)},
            )
        },
        "# Dedicated field-star repeatability experiment\nNative D6 field stars, same release, 3% floor per measurement. Each pair fits its own unknown constant flux (one residual degree of freedom). All eligible pairs retained.\n```json\n"
        + json.dumps(repeats, indent=2)
        + "\n```\nThese are candidate controls, not catalog-certified nonvariables. Sparse one-channel pairs cannot establish full-spectrum reduced chi-square approximately one. No acceptance inferred.",
        [i for p in repeats for i in p["inputs"]],
        n_frames=2 * len(repeats),
        pins=["3addc0f80339"],
        author="M",
        code_paths=[
            "scripts/verify/m_f4.py",
            "backend/spherex/epsf.py",
            "backend/spherex/photometry.py",
        ],
    )


if __name__ == "__main__":
    asyncio.run(main())
