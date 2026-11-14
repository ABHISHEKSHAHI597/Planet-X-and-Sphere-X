"""Reviewer aid for G5.25yr-jumps (not an evidence record): are the measured jumps robust to the measurement choices?

Fetches each archival cutout and SPHEREx frame once (memoised), then re-runs `g5_25yr_jumps.one()` for every
combination of grid pixel scale (2, 3, 4″), centroid aperture (3, 4, 6 px) and source-search radius (10, 15, 25″),
and adds an independent position method: a 2-D elliptical Gaussian + plane fit (NaN pixels excluded) at the grid
pixel scale of the record (3″). Prints the spread of every jump against the record's value and tolerance.

    cd backend && uv run python ../scripts/verify/g5_25yr_sensitivity.py
"""
import asyncio
import itertools
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).parents[2]
sys.path.insert(0, str(ROOT / "scripts/verify"))
sys.path.insert(0, str(ROOT / "backend"))

import g5_25yr_jumps as J  # noqa: E402
from scipy.optimize import least_squares  # noqa: E402

_cut: dict[str, bytes] = {}
_frames: dict[str, object] = {}
_plans: dict[str, object] = {}


def memo_plan(orig):
    async def f(name, *a, **k):
        if name not in _plans:
            _plans[name] = await orig(name, *a, **k)
        return _plans[name]
    return f


def memo_fetch(orig):
    async def f(c, url, *a, **k):
        if url not in _cut:
            _cut[url] = await orig(c, url, *a, **k)
        return _cut[url]
    return f


def memo_frames(orig):
    async def f(source, refs, box, **k):
        key = json.dumps([r.id for r in refs]) + repr(box)
        if key not in _frames:
            _frames[key] = await orig(source, refs, box, **k)
        return _frames[key]
    return f


def gauss_measure(img, grid, radec):
    """Independent method: elliptical Gaussian + plane least squares around the brightest pixel near pos(t)."""
    m = J._orig_measure(img, grid, radec)
    if m is None:
        return None
    x0, y0 = (float(v) for v in grid.wcs.world_to_pixel_values(m["ra"], m["dec"]))
    h = 8
    ix, iy = int(round(x0)), int(round(y0))
    sub = img[iy - h: iy + h + 1, ix - h: ix + h + 1]
    yy, xx = np.mgrid[iy - h: iy + h + 1, ix - h: ix + h + 1]
    ok = np.isfinite(sub)

    def model(p):
        a, x, y, sx, sy, b0, bx, by = p
        return a * np.exp(-0.5 * (((xx - x) / sx) ** 2 + ((yy - y) / sy) ** 2)) + b0 + bx * (xx - ix) + by * (yy - iy)

    p0 = [float(np.nanmax(sub)), x0, y0, 1.5, 1.5, 0.0, 0.0, 0.0]
    r = least_squares(lambda p: (model(p) - sub)[ok], p0)
    ra, dec = (float(v) for v in grid.wcs.pixel_to_world_values(r.x[1], r.x[2]))
    return dict(m, ra=ra, dec=dec)


async def main():
    J._orig_measure = J.measure
    J.fetch_cutout = memo_fetch(J.fetch_cutout)
    J.fetch_frames = memo_frames(J.fetch_frames)
    J.plan = memo_plan(J.plan)
    registry = J.load_registry()
    out: dict[str, list] = {k: [] for k in J.TARGETS}
    async with J.make_client(timeout=300) as c:
        source = J.build_source("irsa", client=c, registry=registry, failover=False)
        variants = list(itertools.product([2.0, 3.0, 4.0], [3, 4, 6], [10.0, 15.0, 25.0]))
        for key, (name, pin_key, ref_label, *_r) in J.TARGETS.items():
            for pix, ap, srch in variants + [("gauss", None, None)]:
                if pix == "gauss":
                    J.PIX_ARCSEC, J.APERTURE_PX, J.SEARCH_ARCSEC, J.measure = 3.0, 4, 15.0, gauss_measure
                else:
                    J.PIX_ARCSEC, J.APERTURE_PX, J.SEARCH_ARCSEC, J.measure = pix, ap, srch, J._orig_measure
                r, _ = await J.one(c, key, name, pin_key, ref_label, registry, source)
                out[key].append(dict(pix=pix, aperture=ap, search=srch, jump=r.get("measured_jump_arcmin"),
                                     predicted=r.get("predicted_jump_arcmin")))
            print(name, "done", flush=True)
    print("\n| Target | variants | jump min | jump max | spread ″ | Gaussian-fit jump | record tolerance |")
    print("|---|---|---|---|---|---|---|")
    for key, (name, _p, _l, exp, tol, _d) in J.TARGETS.items():
        js = [v["jump"] for v in out[key] if v["pix"] != "gauss" and v["jump"] is not None]
        g = next(v["jump"] for v in out[key] if v["pix"] == "gauss")
        print(f"| {name} | {len(js)}/27 | {min(js):.4f} | {max(js):.4f} | {60 * (max(js) - min(js)):.2f} | "
              f"{g:.4f} | {exp} ± {tol} |")
    print("\n```json\n" + json.dumps(out, indent=1, default=float) + "\n```")


if __name__ == "__main__":
    asyncio.run(main())
