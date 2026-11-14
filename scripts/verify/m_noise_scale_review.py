"""Reviewer aid for M-noise-scale / decision 0007 (not an evidence record). Tries to break the conclusion:

1. Noise scale by an independent estimator: adjacent-pixel differences of sky pixels, 1.4826·MAD(Δ)/√2 with each
   difference normalised by √(var_i + var_j). Smooth sky structure and extended faint light cancel in Δ; positively
   correlated pixel noise would make this estimator read LOW, so it is reported beside the block estimator.
2. Block-size sensitivity of `sky_noise_scale` (12, 16, 24 px).
3. Antisymmetric residual: a sign-flip permutation null. Each star's pull stamp is rotated by 180° with probability
   ½ (which makes the antisymmetric part zero-mean under "the PSF is symmetric"); p = fraction of 4000 trials whose
   antisymmetric rms reaches the observed one.
4. Replication: the same statistics separately in the Barnard and ε Ind B fields.
5. D1's χ²ᵣ with the flag-mask scale under each block size (does the F5 failure depend on that choice?).

    cd backend && uv run python ../scripts/verify/m_noise_scale_review.py
"""
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "backend"), str(ROOT / "scripts"), str(ROOT / "scripts/verify")]
from astropy.io import fits  # noqa: E402
from astropy.wcs import WCS  # noqa: E402
from m_noise_scale import CACHE, gaia_targets, stamp_stats  # noqa: E402

from spherex.calib import Calib  # noqa: E402
from spherex.epsf import EPSF, fit_native  # noqa: E402
from spherex.preprocess import calibrate, sky_noise_scale  # noqa: E402
from spherex.types import RawFrame  # noqa: E402

RNG = np.random.default_rng(20261108)


def diff_scale(sci, var, sky):
    ok = sky & np.isfinite(sci) & np.isfinite(var) & (var > 0)
    pair = ok[:, :-1] & ok[:, 1:]
    d = (sci[:, 1:] - sci[:, :-1])[pair] / np.sqrt((var[:, 1:] + var[:, :-1])[pair])
    return float(1.4826 * np.median(np.abs(d - np.median(d)))) if d.size > 200 else float("nan")


def antisym(stamps):
    mean = np.mean(stamps, axis=0)
    return float(np.sqrt(np.mean(((mean - mean[::-1, ::-1]) / 2) ** 2)))


def perm_p(stamps, n=4000):
    obs = antisym(stamps)
    rot = stamps[:, ::-1, ::-1]
    hits = 0
    for _ in range(n):
        flip = RNG.random(len(stamps)) < 0.5
        hits += antisym(np.where(flip[:, None, None], rot, stamps)) >= obs
    return obs, (hits + 1) / (n + 1)


def main():
    stars = gaia_targets()
    paths = {json.loads(p.with_suffix(".json").read_text())["access_url"].rsplit("/", 1)[-1]: p
             for p in (CACHE / "frames").rglob("*.fits")}
    cal = Calib(ROOT / ".cache/calib", verify=True)
    frames, stamps = [], []
    for frame in json.loads((CACHE / "results.json").read_text()):
        if frame.get("error") or not frame["stars"]:
            continue
        path = paths[frame["frame"]]
        meta = json.loads(path.with_suffix(".json").read_text())
        with fits.open(path, memmap=False) as h:
            data = {n: (h[n].header.copy(), np.array(h[n].data)) for n in ("IMAGE", "VARIANCE", "FLAGS", "ZODI")}
        cf = calibrate(RawFrame(data, WCS(data["IMAGE"][0]), tuple(meta["origin"]), release=meta["release"]), cal,
                       preset="photometry")
        bad = cf.bad_phot | ((cf.flags & cf.bits.get("OVERFLOW", 0)) != 0)
        sky = cf.sky & ~bad
        sc = {t: sky_noise_scale(cf.sci, cf.var, sky, tile=t) for t in (12, 16, 24)}
        frames.append(dict(frame=frame["frame"], field=frame["target"], detector=cf.detector,
                           diff=diff_scale(cf.sci, cf.var, sky), **{f"block{t}": v for t, v in sc.items()}))
        psf = EPSF(fits.getdata(cal.path("epsf", cf.detector), "EPSF"))
        for star in frame["stars"]:
            a, d = stars[star["id"]].pos([cf.mjd])
            x, y = map(float, cf.wcs.world_to_pixel_values(a[0], d[0]))
            iz = psf.zone(x + cf.origin[0], y + cf.origin[1])
            row = dict(field=frame["target"], detector=cf.detector)
            for t, s in sc.items():
                if np.isfinite(s):
                    f = fit_native(cf.sci, cf.var * s**2, bad, psf, iz, x, y)
                    row[f"rchi2_block{t}"] = f.rchi2 if f else None
                    if t == 16 and f is not None:
                        row["pull"] = np.nan_to_num(stamp_stats(cf, f, x, y, cf.var * s**2)[0])
            stamps.append(row)
    print("## 1–2. Noise scale by estimator (median over frames)\n")
    print("| D | frames | block 12 | block 16 | block 24 | adjacent-difference |")
    print("|---|---|---|---|---|---|")
    for det in range(1, 7):
        fs = [f for f in frames if f["detector"] == det]

        def m(k, fs=fs):
            v = [f[k] for f in fs if np.isfinite(f[k])]
            return f"{np.median(v):.3f} ({len(v)})" if v else "—"
        print(f"| {det} | {len(fs)} | {m('block12')} | {m('block16')} | {m('block24')} | {m('diff')} |")
    print("\n## 3–4. Antisymmetric residual (flag-mask scale, 16-px blocks): observed rms, permutation p\n")
    print("| D | all fields | Barnard field | ε Ind B field |")
    print("|---|---|---|---|")
    for det in range(1, 7):
        cells = []
        for fld in (None, "Barnard's Star", "eps Ind B"):
            st = [r["pull"] for r in stamps if r["detector"] == det and "pull" in r and (fld is None or r["field"] == fld)]
            if len(st) < 5:
                cells.append(f"n={len(st)}")
                continue
            o, p = perm_p(np.array(st))
            cells.append(f"{o:.3f}, p={p:.4f} (n={len(st)})")
        print(f"| {det} | " + " | ".join(cells) + " |")
    print("\n## 5. Median χ²ᵣ with the flag-mask scale, by block size\n")
    print("| D | block 12 | block 16 | block 24 |")
    print("|---|---|---|---|")
    for det in range(1, 7):
        out = []
        for t in (12, 16, 24):
            v = [r[f"rchi2_block{t}"] for r in stamps if r["detector"] == det and r.get(f"rchi2_block{t}") is not None]
            out.append(f"{np.median(v):.2f} (n={len(v)})" if v else "—")
        print(f"| {det} | " + " | ".join(out) + " |")


if __name__ == "__main__":
    main()
