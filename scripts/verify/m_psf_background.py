"""Offline diagnostic of ePSF broadening on genuine cached field stars.

No production calibration change or F5 pass is inferred from this experiment.
"""

from __future__ import annotations

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
from spherex.calib import Calib
from spherex.epsf import EPSF, fit_native
from spherex.preprocess import calibrate
from spherex.targets import Target
from spherex.types import RawFrame


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    cache = ROOT / ".cache/m-native"
    entries = json.loads((cache / "catalogs/index.json").read_text())
    stars = {}
    for key, item in entries.items():
        if "gaia_dr3_source" not in key or item["status"] != 200:
            continue
        table = votable.parse_single_table(
            io.BytesIO(
                gzip.decompress((cache / "catalogs" / item["file"]).read_bytes())
            )
        ).to_table(use_names_over_ids=True)
        for s in table:

            def get(k, s=s):
                return None if np.ma.is_masked(s[k]) else float(s[k])

            stars[int(s["source_id"])] = Target(
                "",
                "star",
                str(s["source_id"]),
                get("ra"),
                get("dec"),
                2016.0,
                get("pmra"),
                get("pmdec"),
                get("parallax"),
                get("radial_velocity"),
            )
    cal = Calib(ROOT / ".cache/calib", verify=True)
    results = json.loads((cache / "results.json").read_text())
    paths = {
        json.loads(p.with_suffix(".json").read_text())["access_url"].rsplit("/", 1)[
            -1
        ]: p
        for p in (cache / "frames").rglob("*.fits")
    }
    output = []
    inputs = []
    for frame in results:
        path = paths[frame["frame"]]
        meta = json.loads(path.with_suffix(".json").read_text())
        inputs.append(
            {
                "url": meta["access_url"],
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "box": meta["box"],
            }
        )
        with fits.open(path, memmap=False) as hl:
            hdus = {
                n: (hl[n].header.copy(), np.array(hl[n].data))
                for n in ("IMAGE", "VARIANCE", "FLAGS", "ZODI")
            }
        cf = calibrate(
            RawFrame(
                hdus,
                WCS(hdus["IMAGE"][0]),
                tuple(meta["origin"]),
                release=meta["release"],
            ),
            cal,
            preset="photometry",
        )
        psf = EPSF(fits.getdata(cal.path("epsf", cf.detector), "EPSF"))
        base = psf.psf.copy()
        bad = cf.bad_phot | ((cf.flags & cf.bits.get("OVERFLOW", 0)) != 0)
        for star in sorted(frame["stars"], key=lambda s: s["id"])[:5]:
            t = stars[star["id"]]
            a, d = t.pos([cf.mjd])
            x, y = map(float, cf.wcs.world_to_pixel_values(a[0], d[0]))
            z = psf.zone(x + cf.origin[0], y + cf.origin[1])
            chi = {}
            snr = None
            for sigma in (0, 1):
                psf.psf = base
                fit = fit_native(cf.sci, cf.var, bad, psf, z, x, y, background_order=sigma)
                chi[str(sigma)] = None if fit is None else fit.rchi2
                if sigma == 0 and fit is not None:
                    snr = float(fit.params[2] / fit.errors[2])
            output.append(
                {
                    "frame": frame["frame"],
                    "target": frame["target"],
                    "source_id": star["id"],
                    "detector": cf.detector,
                    "snr": snr,
                    "rchi2": chi,
                }
            )
        print(frame["target"], cf.detector, len(output), flush=True)
    medians = {
        str(d): {
            k: float(
                np.median(
                    [
                        s["rchi2"][k]
                        for s in output
                        if s["detector"] == d and s["rchi2"][k] is not None
                    ]
                )
            )
            for k in output[0]["rchi2"]
        }
        for d in range(1, 7)
    }
    training = set(sorted({s["source_id"] for s in output})[::2])
    holdout = {}
    for detector in range(1, 7):
        train = [
            s
            for s in output
            if s["detector"] == detector and s["source_id"] in training
        ]
        test = [
            s
            for s in output
            if s["detector"] == detector and s["source_id"] not in training
        ]
        if not train or not test:
            continue
        scores = {
            k: np.median([s["rchi2"][k] for s in train if s["rchi2"][k] is not None])
            for k in output[0]["rchi2"]
        }
        selected = min(scores, key=scores.get)
        holdout[detector] = {
            "selected_sigma": selected,
            "n_train": len(train),
            "n_test": len(test),
            "baseline_median": float(
                np.median(
                    [s["rchi2"]["0"] for s in test if s["rchi2"]["0"] is not None]
                )
            ),
            "broadened_median": float(
                np.median(
                    [
                        s["rchi2"][selected]
                        for s in test
                        if s["rchi2"][selected] is not None
                    ]
                )
            ),
        }
    record(
        "M-epsf-background",
        "L3",
        "inconclusive",
        {},
        "# Local background diagnostic (not foundation acceptance)\nConstant (0) vs plane (1) skies, with correct parameter counts. Alternating unique source identifiers separate training and holdout. selected_sigma below identifies background order, not PSF width.\n```json\n"
        + json.dumps(
            {"medians": medians, "holdout": holdout, "samples": output}, indent=2
        )
        + "\n```\nF5 remains unaccepted; model mismatch is not repaired by inflating input noise.",
        inputs,
        n_frames=len(results),
        author="M",
        code_paths=[
            "scripts/verify/m_psf_background.py",
            "backend/spherex/epsf.py",
            "backend/spherex/preprocess.py",
        ],
        pins=[
            p.stem
            for p in (ROOT / "config/pins").glob("*.json")
            if p.stem != "index"
            and json.loads(p.read_text())["params"]["target"] in ("barnard", "epsindb")
        ],
    )


if __name__ == "__main__":
    main()
