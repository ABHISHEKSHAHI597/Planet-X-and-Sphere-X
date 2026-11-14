"""G5.25yr-jumps (owner I, reviewer M; workflow.md G5.25yr; implementation.md §4.13, §10.2), level L3.

For Barnard's Star, ε Indi B and WISE 0855: put the archival reference epoch (2MASS Ks; AllWISE W2 for WISE 0855,
which 2MASS did not detect) and the latest full band-6 SPHEREx visit of the target's pin on ONE grid, each on its
own sky σ, through the production code (D's `access.blink25.plan` + `fetch_cutout`, I's `spherex.blink25`,
`preprocess.calibrate`, `grid.frame_to_grid`, `stack.build_stack`). Then MEASURE the target's position in both
images and compare the measured jump with implementation.md:
  Barnard  2MASS (2000.41) → SPHEREx: 4.55′ ± 0.1′ (§10.2)
  ε Ind B  2MASS → SPHEREx:          ≈ 2.1′  (§4.13; ± 0.1′ as in scripts/blink25_acquire.py)
  WISE 0855 AllWISE → SPHEREx:       ≈ 2.2′  (§4.13; ± 0.1′ likewise)
The §4.13 numbers were computed for Aug 2026; the jump predicted by pos(t) for the *actual* epochs is reported beside
them, so a date difference is visible rather than hidden.

Measurement: the brightest smoothed peak within SEARCH_ARCSEC of pos(t) at that epoch, then a background-subtracted
first moment over finite pixels within APERTURE_PX (NaN cores of saturated stars are excluded, not filled). The
search radius only selects which source to measure; the reported positions are the image centroids.

Run from the repo root (network: IRSA SIA2/TAP/IBE and SPHEREx cutouts, ≈ 10–30 MB):
    cd backend && uv run python ../scripts/verify/g5_25yr_jumps.py [--no-record]
"""
import argparse
import asyncio
import json
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).parents[2]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "scripts/verify"))

from astropy.time import Time  # noqa: E402
from scipy.ndimage import gaussian_filter  # noqa: E402

from app.calibration import UnknownLambda  # noqa: E402
from spherex.access import pins as pinmod  # noqa: E402
from spherex.access.blink25 import KS_EXPECTED, fetch_cutout, plan, sep_arcmin  # noqa: E402
from spherex.access.failover import fetch_frames  # noqa: E402
from spherex.access.frames import snap_box  # noqa: E402
from spherex.access.http import make_client  # noqa: E402
from spherex.access.releases import load as load_registry  # noqa: E402
from spherex.access.sources import build_source  # noqa: E402
from spherex.blink25 import epoch_on_grid, spherex_epoch  # noqa: E402
from spherex.constants import TEST_TARGETS  # noqa: E402
from spherex.epochs import time_bins  # noqa: E402
from spherex.external.twomass import TwoMassClient  # noqa: E402
from spherex.external.wise import WiseClient  # noqa: E402
from spherex.grid import frame_to_grid, make_grid  # noqa: E402
from spherex.preprocess import calibrate  # noqa: E402
from spherex.stack import build_stack  # noqa: E402
from spherex.targets import Target, sep_arcsec  # noqa: E402

PIX_ARCSEC = 3.0
SEARCH_ARCSEC = 15.0
APERTURE_PX = 4
TARGETS = {  # key: (TEST_TARGETS name, pin key, reference epoch label, expected jump ′, tolerance ′, doc source)
    "barnard": ("Barnard's Star", "barnard", "2MASS Ks", 4.55, 0.1, "implementation.md §10.2"),
    "epsindb": ("eps Ind B", "epsindb", "2MASS Ks", 2.1, 0.1, "implementation.md §4.13 (≈)"),
    "wise0855": ("WISE 0855-0714", "wise0855", "AllWISE W2", 2.2, 0.1, "implementation.md §4.13 (≈)"),
}


def f(v):
    return f"{v:.3f}" if isinstance(v, float) else "—"


def measure(img, grid, radec):
    """(ra, dec, peak σ, offset from the prediction ″) of the source nearest pos(t) — see module docstring."""
    x0, y0 = (float(v) for v in grid.wcs.world_to_pixel_values(*radec))
    ny, nx = img.shape
    yy, xx = np.indices(img.shape)
    r_search = SEARCH_ARCSEC / grid.pix_arcsec
    sm = gaussian_filter(np.nan_to_num(img, nan=0.0), 1.0)
    win = np.hypot(xx - x0, yy - y0) <= r_search
    if not win.any():
        return None
    k = np.argmax(np.where(win, sm, -np.inf))
    py, px = divmod(int(k), nx)
    cx, cy = float(px), float(py)
    for _ in range(10):  # re-centre: a NaN (saturated) core makes the first peak sit on the ring
        r = np.hypot(xx - cx, yy - cy)
        ann = (r >= APERTURE_PX + 2) & (r <= APERTURE_PX + 6) & np.isfinite(img)
        bg = float(np.median(img[ann])) if ann.sum() > 5 else 0.0
        ap = (r <= APERTURE_PX) & np.isfinite(img)
        w = np.clip(img[ap] - bg, 0, None)
        if w.sum() <= 0:
            return None
        nx_, ny_ = float((w * xx[ap]).sum() / w.sum()), float((w * yy[ap]).sum() / w.sum())
        done = np.hypot(nx_ - cx, ny_ - cy) < 0.01
        cx, cy = nx_, ny_
        if done:
            break
    ra, dec = (float(v) for v in grid.wcs.pixel_to_world_values(cx, cy))
    return dict(ra=ra, dec=dec, peak_sigma=float(sm[py, px]), offset_from_prediction_arcsec=sep_arcsec(ra, dec, *radec),
                n_nan_in_aperture=int(((np.hypot(xx - cx, yy - cy) <= APERTURE_PX) & np.isnan(img)).sum()))


async def one(c, key, name, pin_key, ref_label, registry, source):
    t = Target("", "star", name, *TEST_TARGETS[name][:7])

    def pos(year):
        a, d = t.pos([float(Time(year, format="jyear").mjd)])
        return float(a[0]), float(d[0])

    index = json.loads((ROOT / "config/pins/index.json").read_text())
    pin_id = index[pin_key]["pin"]
    refs = [r for r in pinmod.load(pin_id).frames if r.detector == 6]
    bins = time_bins([r.t_min for r in refs], [6] * len(refs), "visit")[6]
    full = [b for b in bins if b.status == "full"]
    last = max(full, key=lambda b: b.mjd_mean)
    now_year = float(Time(last.mjd_mean, format="mjd").jyear)
    p = await plan(name, pos, now_year, TwoMassClient(c), WiseClient(c), "spherex.targets.Target.pos (TEST_TARGETS)",
                   neowise=False, k_expected=KS_EXPECTED.get(name))
    d = p.as_dict()
    ref = next((e for e in d["epochs"] if e["label"] == ref_label and e["images"]), None)
    if ref is None:
        return dict(target=name, error=f"no {ref_label} epoch with images"), 0
    old_pred = pos(float(ref["year"]))
    now_pred = pos(now_year)
    centre = ((old_pred[0] + now_pred[0]) / 2, (old_pred[1] + now_pred[1]) / 2)
    fov = max(float(d["fov_arcmin"]), 1.5 * sep_arcmin(old_pred, now_pred) + 1.0)
    grid = make_grid(*centre, fov, PIX_ARCSEC)
    size = fov * 1.5 / 60
    raws = []
    for im in ref["images"][:3]:
        try:
            raws.append(await fetch_cutout(c, f"{im['url'].split('?')[0]}?center={centre[0]:.6f},{centre[1]:.6f}&size={size:.5f}"))
        except Exception as e:  # noqa: BLE001 — listed in the report
            print(f"  {name}: archival image failed: {e!r}"[:200])
    old_img, n_old = epoch_on_grid(raws, grid)
    vrefs = [refs[i] for i in last.idx]
    outs = await fetch_frames(source, vrefs, snap_box(*centre, fov * 1.45), band=6, concurrency=4)
    cal = UnknownLambda()
    gframes, skipped = [], []
    for o in outs:
        if o.frame is None:
            skipped.append((o.ref.id, o.skipped_reason or "fetch failed"))
            continue
        cf = calibrate(o.frame, cal, preset="discovery")
        if not cf.qa["ok"]:
            skipped.append((o.ref.id, ";".join(cf.qa["reasons"])))
            continue
        gframes.append(frame_to_grid(cf, grid))
    st = build_stack(gframes, last, grid, skipped=skipped)
    new_img = spherex_epoch(st.mean)
    mo, mn = measure(old_img, grid, old_pred), measure(new_img, grid, now_pred)
    out = dict(
        target=name, pin=pin_id, reference_epoch=ref_label, reference_year=float(ref["year"]), reference_date=ref["date"],
        reference_images=n_old, twomass_match=d["twomass_source"], spherex_visit=last.id,
        spherex_year=now_year, spherex_frames_stacked=len(gframes), spherex_frames_skipped=len(skipped),
        grid=dict(centre=centre, fov_arcmin=fov, pix_arcsec=PIX_ARCSEC, shape=list(grid.shape)),
        predicted_jump_arcmin=sep_arcmin(old_pred, now_pred), old=mo, new=mn,
    )
    if mo and mn:
        out["measured_jump_arcmin"] = sep_arcmin((mo["ra"], mo["dec"]), (mn["ra"], mn["dec"]))
    return out, len(gframes)


async def main(write: bool):
    t0 = time.time()
    registry = load_registry()
    results, nframes = {}, 0
    async with make_client(timeout=300) as c:
        source = build_source("irsa", client=c, registry=registry, failover=False)
        for key, (name, pin_key, ref_label, *_rest) in TARGETS.items():
            print(f"== {name}", flush=True)
            try:
                r, n = await one(c, key, name, pin_key, ref_label, registry, source)
            except Exception as e:  # noqa: BLE001 — a failed target is recorded as such
                r, n = dict(target=name, error=f"{type(e).__name__}: {e}"[:300]), 0
            results[key], nframes = r, nframes + n
            print(json.dumps(r, indent=1, default=float)[:1500], flush=True)
    metrics, ok_all, any_missing = {}, True, False
    for key, (_name, _p, ref_label, exp, tol, doc) in TARGETS.items():
        r = results[key]
        mj = r.get("measured_jump_arcmin")
        passed = mj is not None and abs(mj - exp) <= tol
        any_missing |= mj is None
        ok_all &= bool(passed)
        metrics[f"{key}_jump_arcmin"] = dict(value=mj, threshold=f"{exp} ± {tol} ({doc}, {ref_label} → SPHEREx)",
                                             pass_=passed)
        metrics[f"{key}_predicted_jump_arcmin"] = dict(value=r.get("predicted_jump_arcmin"),
                                                       threshold="pos(t) at the actual epochs (informational)", pass_=None)
    for m in metrics.values():
        m["pass"] = m.pop("pass_")
    verdict = "pass" if ok_all else ("inconclusive" if any_missing else "fail")
    lines = ["# G5.25yr-jumps — measured archival → SPHEREx jumps", "",
             f"Verdict **{verdict}**. Runtime {time.time() - t0:.0f} s. Label shown in the product: "
             "\"different telescopes, positions only\".", "",
             "| Target | Ref. epoch | SPHEREx visit | Measured jump ′ | Predicted (pos(t)) ′ | Doc expectation | "
             "Old offset from pos(t) ″ | New offset ″ |", "|---|---|---|---|---|---|---|---|"]
    for key, (name, _p, ref_label, exp, tol, doc) in TARGETS.items():
        r = results[key]
        if "error" in r:
            lines.append(f"| {name} | {ref_label} | — | error: {r['error']} | | {exp} ± {tol} | | |")
            continue
        lines.append(f"| {name} | {ref_label} {r['reference_date']} ({r['reference_images']} img) | {r['spherex_visit']} "
                     f"{r['spherex_year']:.2f} ({r['spherex_frames_stacked']} fr) | {f(r.get('measured_jump_arcmin'))} | "
                     f"{f(r['predicted_jump_arcmin'])} | {exp} ± {tol} ({doc}) | "
                     f"{f((r['old'] or {}).get('offset_from_prediction_arcsec'))} | "
                     f"{f((r['new'] or {}).get('offset_from_prediction_arcsec'))} |")
    lines += ["", "Method: module docstring of `scripts/verify/g5_25yr_jumps.py`. Calibration: none needed (positions "
              "only; λ unknown). Saturated cores are NaN and excluded from the centroid (count in the JSON).", "",
              "```json", json.dumps(results, indent=1, default=float), "```"]
    report = "\n".join(lines)
    print(report[:3000])
    if write:
        from _evidence import record

        pins = [results[k].get("pin") for k in TARGETS if results[k].get("pin")]
        rec = record("G5.25yr-jumps", "L3", verdict, metrics, report, inputs=[str(ROOT / "config/pins/index.json")],
                     n_frames=nframes, calibration="none (positions only)", pins=pins,
                     code_paths=[str(ROOT / p) for p in ("backend/spherex/blink25.py", "backend/spherex/access/blink25.py",
                                                         "backend/spherex/grid.py", "backend/spherex/stack.py",
                                                         "scripts/verify/g5_25yr_jumps.py")],
                     caveats=["Archival and SPHEREx fluxes are not compared (positions only).",
                              "The §4.13 ε Ind B and WISE 0855 expectations are approximate (≈) and computed for Aug 2026; "
                              "the predicted jump at the actual epochs is listed beside each measurement."],
                     author="I")
        print("record:", rec)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-record", action="store_true")
    asyncio.run(main(not ap.parse_args().no_record))
