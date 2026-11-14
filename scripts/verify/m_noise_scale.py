"""F5 diagnosis: is the short-band ePSF failure a PSF error or a VARIANCE-plane error? (decision 0007)

Inputs: exactly the frames and isolated Gaia stars that `m_native.py` accepted (`.cache/m-native`), the locked
calibration (`.cache/calib`). Nothing is re-selected after seeing a residual. No noise scale ever reads a star pixel.

Revision history (all runs are kept as superseded records):
- r1 (pre-registered): one noise scale from the frame's own sky mask (16-px blocks), refit, F5's rule; antisymmetry
  judged against an analytic √(1/2N) noise level.
- r1b: the flag mask leaves < 3 sky blocks in some D1–D4 cutouts; a Gaia-only mask (G < 18) reads ≈2× higher because
  fainter sources stay in its "sky" — an upper bound, never used for the verdict.
- r2 (this version, after the reviewer aid `m_noise_scale_review.py`): the r1 outcome depended on analysis choices.
  D1's median χ²ᵣ moved from 2.08 to 3.98 with the block size (each size keeps a different subset of frames), and the
  analytic antisymmetry yardstick was miscalibrated (pulls inside a stamp are correlated): under a sign-flip
  permutation null D1's antisymmetry is not significant. r2 therefore evaluates FOUR noise estimators (blocks of 12,
  16, 24 px; adjacent-pixel differences, defined in every frame) and judges antisymmetry with the permutation test,
  separately in the two fields.

Decision rule (r2, conservative; F5's own rule — median χ²ᵣ > 3 fails — is applied inside it):
- fail         some detector has median χ²ᵣ > 3 under EVERY estimator that evaluates it (≥ 3 estimators, ≥ 5 stars);
- pass         no estimator gives any detector > 3, all six detectors are evaluated, and no detector shows an
               antisymmetric residual with permutation p < 0.01 in BOTH fields (a replicated PSF asymmetry);
- inconclusive otherwise.

    cd backend && uv run python ../scripts/verify/m_noise_scale.py [--no-record]
"""

import argparse
import gzip
import io
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "backend"), str(ROOT / "scripts")]
import numpy as np  # noqa: E402
from astropy.io import fits, votable  # noqa: E402
from astropy.wcs import WCS  # noqa: E402

from spherex.calib import Calib  # noqa: E402
from spherex.epsf import EPSF, fit_native  # noqa: E402
from spherex.preprocess import calibrate, sky_noise_scale  # noqa: E402
from spherex.targets import Target  # noqa: E402
from spherex.types import RawFrame  # noqa: E402

CACHE = ROOT / ".cache/m-native"
ESTIMATORS = ("block12", "block16", "block24", "diff")
FIELDS = ("Barnard's Star", "eps Ind B")
N_PERM = 4000
RNG = np.random.default_rng(20261108)


def gaia_targets():
    stars = {}
    for key, item in json.loads((CACHE / "catalogs/index.json").read_text()).items():
        if "gaia_dr3_source" not in key or item["status"] != 200:
            continue
        table = votable.parse_single_table(
            io.BytesIO(gzip.decompress((CACHE / "catalogs" / item["file"]).read_bytes()))
        ).to_table(use_names_over_ids=True)
        for row in table:

            def v(k, row=row):
                return None if np.ma.is_masked(row[k]) else float(row[k])

            stars[int(row["source_id"])] = Target(
                "", "star", str(row["source_id"]), v("ra"), v("dec"), 2016.0, v("pmra"), v("pmdec"),
                v("parallax"), v("radial_velocity"))
    return stars


def diff_scale(sci, var, sky):
    """Adjacent-pixel difference estimator: smooth sky structure cancels; positively correlated noise reads low."""
    ok = sky & np.isfinite(sci) & np.isfinite(var) & (var > 0)
    pair = ok[:, :-1] & ok[:, 1:]
    d = (sci[:, 1:] - sci[:, :-1])[pair] / np.sqrt((var[:, 1:] + var[:, :-1])[pair])
    return float(1.4826 * np.median(np.abs(d - np.median(d)))) if d.size > 200 else float("nan")


def stamp_stats(cf, fit, x, y, var):
    ix, iy = round(x), round(y)
    sl = np.s_[iy - 3 : iy + 4, ix - 3 : ix + 4]
    ok = ~cf.bad_phot[sl] & np.isfinite(cf.sci[sl]) & np.isfinite(var[sl]) & (var[sl] > 0)
    pull = np.where(ok, (cf.sci[sl] - fit.model) / np.sqrt(var[sl]), np.nan)
    dy, dx = np.mgrid[-3:4, -3:4]
    r = np.hypot(dx - fit.params[0] + ix, dy - fit.params[1] + iy)
    return pull, float(np.sqrt(np.nanmean(pull[ok & (r < 1.5)] ** 2))), float(np.sqrt(np.nanmean(pull[ok & (r >= 1.5)] ** 2)))


def antisym(stamps):
    mean = np.mean(stamps, axis=0)
    return float(np.sqrt(np.mean(((mean - mean[::-1, ::-1]) / 2) ** 2)))


def perm_p(stamps):
    """Sign-flip permutation p of the antisymmetric rms (each stamp rotated 180° with probability ½)."""
    stamps = np.asarray(stamps)
    obs, rot, hits = antisym(stamps), stamps[:, ::-1, ::-1], 0
    for _ in range(N_PERM):
        flip = RNG.random(len(stamps)) < 0.5
        hits += antisym(np.where(flip[:, None, None], rot, stamps)) >= obs
    return obs, (hits + 1) / (N_PERM + 1)


def main(write):
    stars = gaia_targets()
    paths = {json.loads(p.with_suffix(".json").read_text())["access_url"].rsplit("/", 1)[-1]: p
             for p in (CACHE / "frames").rglob("*.fits")}
    cal = Calib(ROOT / ".cache/calib", verify=True)
    rows, frames, inputs = [], [], []
    for frame in json.loads((CACHE / "results.json").read_text()):
        if frame.get("error") or not frame["stars"]:
            continue
        path = paths[frame["frame"]]
        meta = json.loads(path.with_suffix(".json").read_text())
        inputs.append(meta["access_url"])
        with fits.open(path, memmap=False) as h:
            data = {n: (h[n].header.copy(), np.array(h[n].data)) for n in ("IMAGE", "VARIANCE", "FLAGS", "ZODI")}
        cf = calibrate(RawFrame(data, WCS(data["IMAGE"][0]), tuple(meta["origin"]), release=meta["release"]), cal,
                       preset="photometry")
        psf = EPSF(fits.getdata(cal.path("epsf", cf.detector), "EPSF"))
        bad = cf.bad_phot | ((cf.flags & cf.bits.get("OVERFLOW", 0)) != 0)
        sky = cf.sky & ~bad
        scales = {f"block{t}": sky_noise_scale(cf.sci, cf.var, sky, tile=t) for t in (12, 16, 24)}
        scales["diff"] = diff_scale(cf.sci, cf.var, sky)
        frames.append(dict(frame=frame["frame"], field=frame["target"], detector=cf.detector, release=meta["release"],
                           **scales))
        for star in frame["stars"]:
            a, d = stars[star["id"]].pos([cf.mjd])
            x, y = map(float, cf.wcs.world_to_pixel_values(a[0], d[0]))
            iz = psf.zone(x + cf.origin[0], y + cf.origin[1])
            base = fit_native(cf.sci, cf.var, bad, psf, iz, x, y)
            if base is None:
                rows.append(dict(frame=frame["frame"], detector=cf.detector, source=star["id"], rejected="fit failed"))
                continue
            row = dict(frame=frame["frame"], field=frame["target"], detector=cf.detector, source=star["id"],
                       rchi2_variance=base.rchi2)
            for e, s in scales.items():
                if not np.isfinite(s):
                    continue
                fit = fit_native(cf.sci, cf.var * s**2, bad, psf, iz, x, y)
                if fit is None:
                    continue
                pull, core, wing = stamp_stats(cf, fit, x, y, cf.var * s**2)
                row[e] = dict(rchi2=fit.rchi2, core=core, wing=wing, pull=np.nan_to_num(pull))
            rows.append(row)
        print(frame["frame"], cf.detector, {k: round(v, 3) for k, v in scales.items()}, flush=True)

    summary: dict[int, dict] = {}
    for det in range(1, 7):
        rs = [r for r in rows if r.get("detector") == det and "rchi2_variance" in r]
        fs = [f for f in frames if f["detector"] == det]
        v: dict = dict(n=len(rs), frames=len(fs),
                       median_rchi2_variance=float(np.median([r["rchi2_variance"] for r in rs])) if rs else None)
        for e in ESTIMATORS:
            sc = [f[e] for f in fs if np.isfinite(f[e])]
            st = [r for r in rs if e in r]
            perm = {}
            for fld in FIELDS:
                ps = [r[e]["pull"] for r in st if r["field"] == fld]
                perm[fld] = dict(n=len(ps))
                if len(ps) >= 5:
                    perm[fld]["antisym_rms"], perm[fld]["p"] = perm_p(ps)
            v[e] = dict(scale=float(np.median(sc)) if sc else None, frames=len(sc), n=len(st),
                        median_rchi2=float(np.median([r[e]["rchi2"] for r in st])) if st else None, antisymmetry=perm)
        summary[det] = v

    def evaluated(v, e):
        return v[e]["n"] >= 5 and v[e]["median_rchi2"] is not None

    robust_fail = [d for d, v in summary.items()
                   if sum(evaluated(v, e) for e in ESTIMATORS) >= 3
                   and all(v[e]["median_rchi2"] > 3 for e in ESTIMATORS if evaluated(v, e))]
    any_fail = [d for d, v in summary.items() if any(evaluated(v, e) and v[e]["median_rchi2"] > 3 for e in ESTIMATORS)]
    all_eval = all(any(evaluated(v, e) for e in ESTIMATORS) for v in summary.values())
    replicated = [d for d, v in summary.items() if all(v["diff"]["antisymmetry"][f].get("p", 1) < 0.01 for f in FIELDS)]
    verdict = "fail" if robust_fail else ("pass" if not any_fail and all_eval and not replicated else "inconclusive")

    def f(x, n=2):
        return "—" if x is None else f"{x:.{n}f}"

    lines = ["# M-noise-scale (r2) — F5 with the VARIANCE plane calibrated on blank sky", "",
             f"Verdict **{verdict}** (rule in the module docstring). Robust F5 failure (every estimator > 3): "
             f"{robust_fail or 'none'}. Detectors > 3 under at least one estimator: {any_fail or 'none'}. "
             f"Antisymmetric residual replicated in both fields (p < 0.01, difference estimator): {replicated or 'none'}.", "",
             "## Noise scale s and median χ²ᵣ by estimator (stars judged)", "",
             "| D | χ²ᵣ VARIANCE | " + " | ".join(f"{e}: s / χ²ᵣ (n)" for e in ESTIMATORS) + " |",
             "|---|---|" + "---|" * len(ESTIMATORS)]
    for det, v in summary.items():
        cells = [f"{f(v[e]['scale'], 3)} / {f(v[e]['median_rchi2'])} ({v[e]['n']})" for e in ESTIMATORS]
        lines.append(f"| {det} | {f(v['median_rchi2_variance'])} | " + " | ".join(cells) + " |")
    lines += ["", "## Antisymmetric residual, sign-flip permutation (difference estimator)", "",
              "| D | " + " | ".join(FIELDS) + " |", "|---|---|---|"]
    for det, v in summary.items():
        cells = []
        for fld in FIELDS:
            a = v["diff"]["antisymmetry"][fld]
            cells.append(f"rms {a['antisym_rms']:.3f}, p = {a['p']:.4f} (n={a['n']})" if "p" in a else f"n={a['n']}")
        lines.append(f"| {det} | " + " | ".join(cells) + " |")
    table_end = len(lines)
    lines += ["", "```json", json.dumps(dict(summary=summary, frames=frames), indent=1, default=float), "```"]
    report = "\n".join(lines)
    print("\n".join(lines[:table_end]))
    if write:
        from _m_evidence import record

        metrics = {}
        for d, v in summary.items():
            vals = [v[e]["median_rchi2"] for e in ESTIMATORS if evaluated(v, e)]
            ok = None if not vals else (False if min(vals) > 3 else (True if max(vals) <= 3 else None))
            metrics[f"D{d}_median_rchi2_range"] = dict(value=[min(vals), max(vals)] if vals else None,
                                                       threshold="<= 3 under every estimator (m_native.py F5 rule)",
                                                       **{"pass": ok})
        metrics["replicated_antisymmetry_detectors"] = dict(value=replicated, threshold="none (p < 0.01 in both fields)",
                                                            **{"pass": not replicated})
        record("M-noise-scale", "L3", verdict, metrics, report, inputs, n_frames=len(frames), author="M",
               code_paths=["backend/spherex/preprocess.py", "backend/spherex/epsf.py", "scripts/verify/m_noise_scale.py"],
               caveats=["Revision 2 after a reviewer aid found the r1 verdict depended on the block size and on a "
                        "miscalibrated antisymmetry yardstick; the r1 record is kept as superseded.",
                        "Two fields only; D4 has few sky blocks in 12′ cutouts."])


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-record", action="store_true")
    main(not ap.parse_args().no_record)
