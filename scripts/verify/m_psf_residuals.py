"""Offline F5 diagnostics: native residual structure, flux/phase/zone and blank sky.

All original accepted stars are retained, with no residual-based rejection. Blank
sky excludes every cached Gaia position by six pixels and uses 16-pixel tiles.
These are descriptive diagnostics, not an alternative acceptance statistic.
"""

import argparse
import gzip
import hashlib
import io
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "backend"), str(ROOT / "scripts")]
import numpy as np
from _m_evidence import record
from astropy.io import fits, votable
from astropy.wcs import WCS
from scipy.stats import spearmanr
from spherex.calib import Calib
from spherex.epsf import EPSF, fit_native
from spherex.preprocess import calibrate
from spherex.targets import Target
from spherex.types import RawFrame


def main(scalar_sky=False):
    cache = ROOT / ".cache/m-native"
    stars = {}
    for key, item in json.loads((cache / "catalogs/index.json").read_text()).items():
        if "gaia_dr3_source" not in key or item["status"] != 200:
            continue
        table = votable.parse_single_table(
            io.BytesIO(
                gzip.decompress((cache / "catalogs" / item["file"]).read_bytes())
            )
        ).to_table(use_names_over_ids=True)
        for row in table:

            def value(k, row=row):
                return None if np.ma.is_masked(row[k]) else float(row[k])

            stars[int(row["source_id"])] = Target(
                "",
                "star",
                str(row["source_id"]),
                value("ra"),
                value("dec"),
                2016.0,
                value("pmra"),
                value("pmdec"),
                value("parallax"),
                value("radial_velocity"),
            )
    paths = {
        json.loads(p.with_suffix(".json").read_text())["access_url"].rsplit("/", 1)[
            -1
        ]: p
        for p in (cache / "frames").rglob("*.fits")
    }
    cal = Calib(ROOT / ".cache/calib", verify=True)
    rows, sky, sources = [], [], []
    for frame in json.loads((cache / "results.json").read_text()):
        path = paths[frame["frame"]]
        meta = json.loads(path.with_suffix(".json").read_text())
        sources.append(
            {
                "url": meta["access_url"],
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "box": meta["box"],
            }
        )
        with fits.open(path, memmap=False) as hdus:
            data = {
                n: (hdus[n].header.copy(), np.array(hdus[n].data))
                for n in ("IMAGE", "VARIANCE", "FLAGS", "ZODI")
            }
        cf = calibrate(
            RawFrame(
                data,
                WCS(data["IMAGE"][0]),
                tuple(meta["origin"]),
                release=meta["release"],
            ),
            cal,
            preset="photometry",
            smooth_bkg=not scalar_sky,
        )
        psf = EPSF(fits.getdata(cal.path("epsf", cf.detector), "EPSF"))
        bad = cf.bad_phot | ((cf.flags & cf.bits.get("OVERFLOW", 0)) != 0)
        yy, xx = np.indices(cf.sci.shape)
        sky_ok = ~bad & np.isfinite(cf.sci) & np.isfinite(cf.var) & (cf.var > 0)
        for target in stars.values():
            a, d = target.pos([cf.mjd])
            x, y = cf.wcs.world_to_pixel_values(a[0], d[0])
            sky_ok &= (xx - x) ** 2 + (yy - y) ** 2 > 36
        tile_scatter, tile_rms, lag = [], [], []
        for iy in range(0, cf.sci.shape[0] - 15, 16):
            for ix in range(0, cf.sci.shape[1] - 15, 16):
                sl = np.s_[iy : iy + 16, ix : ix + 16]
                ok = sky_ok[sl]
                if ok.sum() < 50:
                    continue
                image, variance = cf.sci[sl], cf.var[sl]
                weight = 1 / variance[ok]
                centre = np.sum(image[ok] * weight) / weight.sum()
                z = (image - centre) / np.sqrt(variance)
                tile_rms.append(float(np.sqrt(np.sum(z[ok] ** 2) / (ok.sum() - 1))))
                tile_scatter.append(
                    float(1.4826 * np.median(abs(z[ok] - np.median(z[ok]))))
                )
                pair = ok[:, :-1] & ok[:, 1:]
                if pair.sum() > 20:
                    lag.append(float(np.mean((z[:, :-1] * z[:, 1:])[pair])))
        sky.append(
            {
                "frame": frame["frame"],
                "detector": cf.detector,
                "n_tiles": len(tile_rms),
                "median_rms": float(np.median(tile_rms)) if tile_rms else None,
                "median_mad": float(np.median(tile_scatter)) if tile_scatter else None,
                "median_horizontal_lag_product": float(np.median(lag)) if lag else None,
            }
        )
        for star in frame["stars"]:
            a, d = stars[star["id"]].pos([cf.mjd])
            x, y = map(float, cf.wcs.world_to_pixel_values(a[0], d[0]))
            iz = psf.zone(x + cf.origin[0], y + cf.origin[1])
            fit = fit_native(cf.sci, cf.var, bad, psf, iz, x, y)
            if fit is None:
                rows.append(
                    {
                        "frame": frame["frame"],
                        "source": star["id"],
                        "rejected": "native fitter unconstrained",
                    }
                )
                continue
            ix, iy = round(x), round(y)
            sl = np.s_[iy - 3 : iy + 4, ix - 3 : ix + 4]
            ok = (
                ~bad[sl]
                & np.isfinite(cf.sci[sl])
                & np.isfinite(cf.var[sl])
                & (cf.var[sl] > 0)
            )
            residual = cf.sci[sl] - fit.model
            pull = residual / np.sqrt(cf.var[sl])
            dy, dx = np.mgrid[-3:4, -3:4]
            radius = np.hypot(dx - fit.params[0] + ix, dy - fit.params[1] + iy)
            core, wing = ok & (radius < 1.5), ok & (radius >= 1.5)
            rows.append(
                {
                    "frame": frame["frame"],
                    "source": star["id"],
                    "detector": cf.detector,
                    "release": meta["release"],
                    "zone": iz,
                    "wavelength": star["lam"],
                    "flux": float(fit.params[2]),
                    "phase": (fit.params[:2] % 1).tolist(),
                    "rchi2": fit.rchi2,
                    "core_pull_rms": float(np.sqrt(np.mean(pull[core] ** 2))),
                    "wing_pull_rms": float(np.sqrt(np.mean(pull[wing] ** 2))),
                    "residual": np.where(ok, residual, np.nan).tolist(),
                    "pull": np.where(ok, pull, np.nan).tolist(),
                }
            )
        print(frame["frame"], len(rows), flush=True)
    summary = {}
    for det in range(1, 7):
        sample = [r for r in rows if r.get("detector") == det]
        blanks = [
            r for r in sky if r["detector"] == det and r["median_rms"] is not None
        ]
        summary[str(det)] = {
            "n": len(sample),
            "median_chi": float(np.median([r["rchi2"] for r in sample])),
            "core_rms": float(np.median([r["core_pull_rms"] for r in sample])),
            "wing_rms": float(np.median([r["wing_pull_rms"] for r in sample])),
            "blank_rms": float(np.median([r["median_rms"] for r in blanks]))
            if blanks
            else None,
            "blank_mad": float(np.median([r["median_mad"] for r in blanks]))
            if blanks
            else None,
            "chi_flux_spearman": float(
                spearmanr(
                    [r["flux"] for r in sample], [r["rchi2"] for r in sample]
                ).statistic
            ),
            "chi_wave_spearman": float(
                spearmanr(
                    [r["wavelength"] for r in sample], [r["rchi2"] for r in sample]
                ).statistic
            ),
        }
    body = json.dumps({"summary": summary, "samples": rows, "blank_sky": sky}, indent=2)
    record(
        "M-epsf-scalar-sky" if scalar_sky else "M-epsf-residuals",
        "L3",
        "inconclusive",
        {},
        f"# Native residual and blank-sky diagnostics (scalar_sky={scalar_sky})\n```json\n"
        + json.dumps(summary, indent=2)
        + "\n```\nAll retained field stars; raw residual/pull stamps in attachment. Correlations are descriptive, confounded by zone, brightness and wavelength. Sky tiles can contain unresolved objects, diffuse gradients, Gaia-invisible sources and PSF wings. They do not justify global variance rescaling or a new PSF. F5 remains failed; independent fields/model validation required.",
        sources,
        author="M",
        n_frames=len(sources),
        code_paths=[
            "scripts/verify/m_psf_residuals.py",
            "backend/spherex/epsf.py",
            "backend/spherex/preprocess.py",
        ],
        extra_files={"diagnostics.json": body},
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--scalar-sky",
        action="store_true",
        help="Controlled experiment: disable smooth Background2D, retain fitted constant sky",
    )
    main(parser.parse_args().scalar_sky)
