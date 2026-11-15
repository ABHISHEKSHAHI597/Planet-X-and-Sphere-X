"""Run M target acceptance through the production API integration on pinned real frames.

Examples: python scripts/verify/m_acceptance.py --target epsindb --product spectrum
          python scripts/verify/m_acceptance.py --target barnard --product astrometry
Outputs include native rows, failed frames, independent catalogue parameters, hashes,
and a plot. This script never substitutes simulated measurements for archive data.
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "backend"), str(ROOT / "scripts")]
import numpy as np
from _m_evidence import record
from app.measurement import astrometry_api, lightcurve_api, spectrum_api
from app.pipeline import plan_view, skeleton
from app.services import Services
from app.settings import Settings
from PIL import Image, ImageDraw
from spherex.access.replay import RecordingTransport


def metadata_evidence():
    """Retain public catalogue/ephemeris exchanges; native FITS stay in cache."""
    root = ROOT / ".cache/m-acceptance/http"
    path = root / "index.json"
    if not path.exists():
        return {}
    entries = json.loads(path.read_text())
    kept = {
        k: v
        for k, v in entries.items()
        if "/TAP/" in k or "simbad" in k.lower() or "horizons" in k.lower()
    }
    # The evidence writer accepts flat UTF-8 attachments. Retain gzip bytes
    # losslessly in base64 rather than passing binary or nested file names.
    bodies = {
        item["file"]: base64.b64encode((root / item["file"]).read_bytes()).decode(
            "ascii"
        )
        for item in kept.values()
    }
    return {
        "http-recordings.json": json.dumps(
            {"index": kept, "gzip_bodies_base64": bodies}, indent=2
        )
    }


async def main(args):
    sys.stdout.reconfigure(encoding="utf-8")
    pin = next(
        json.loads(p.read_text())
        for p in (ROOT / "config/pins").glob("*.json")
        if p.stem != "index"
        and json.loads(p.read_text())["params"]["target"] == args.target
    )
    names = {
        "barnard": "Barnard's Star",
        "epsindb": "eps Ind B",
        "wise0855": "WISE 0855",
        "rwaur": "RW Aur",
        "rdra": "R Dra",
    }
    svc = Services(
        Settings(
            cache_dir=ROOT / ".cache/m-acceptance",
            calib_root=ROOT / ".cache/calib",
            environment="local",
            cpu_workers=0,
            run_watcher=False,
        ),
        transport=RecordingTransport(ROOT / ".cache/m-acceptance/http"),
    )
    try:
        plan = await plan_view(
            svc, {"q": names[args.target], "pin": pin["pin"], "fov": "12", "px": "6.15"}
        )
        m = skeleton(svc, plan)
        svc.store.put_manifest(plan.key, m)
        a, d = plan.target.pos([float(np.median([r.t_min for r in plan.refs]))])
        ra, dec = float(a[0]), float(d[0])
        if args.product == "spectrum":
            out = await spectrum_api(svc, ra, dec, key=plan.key)
        elif args.product == "astrometry":
            out = await astrometry_api(svc, ra, dec, names[args.target], key=plan.key)
        else:
            out = await lightcurve_api(
                svc,
                ra,
                dec,
                method="annulus" if args.target == "rdra" else "psf",
                release=args.release,
                key=plan.key,
            )
        dest = ROOT / ".cache/m-acceptance" / f"{args.target}-{args.product}.json"
        dest.write_text(
            json.dumps(
                out,
                indent=2,
                default=lambda o: o.item() if hasattr(o, "item") else str(o),
            )
        )
        # Show actual points, preserving signed non-detections. No template figure.
        pairs = (
            [(r["lam"], r["flux"]) for r in out.get("rows", [])]
            if args.product == "spectrum"
            else [(r["xi"], r["eta"]) for r in out.get("points", [])]
        )
        img = Image.new("RGB", (800, 480), "white")
        draw = ImageDraw.Draw(img)
        draw.text(
            (20, 12),
            f"{args.target} {args.product}: native real measurements; unaccepted",
            fill="black",
        )
        if pairs:
            x, y = np.asarray(pairs).T
            dx = max(float(np.ptp(x)), 1e-9)
            dy = max(float(np.ptp(y)), 1e-9)
            for a, b in zip(x, y, strict=True):
                px = 40 + 700 * (a - x.min()) / dx
                py = 440 - 380 * (b - y.min()) / dy
                draw.ellipse((px - 2, py - 2, px + 2, py + 2), fill="navy")
        import io

        buf = io.BytesIO()
        img.save(buf, format="PNG")
        metrics = {}
        verdict = "inconclusive"
        if args.target == "epsindb" and args.product == "spectrum":
            detected = {
                d: any(
                    r["flux"] > 5 * r["err"]
                    for r in out["rows"]
                    if r["detector"] == d and not r["contaminated"]
                )
                for d in range(1, 7)
            }
            methane = [
                v["methane_rel"]
                for v in out["indices_by_visit"].values()
                if "methane_rel" in v
            ]
            ok = (
                all(detected.values())
                and bool(methane)
                and all(v < 0.5 for v in methane)
            )
            metrics = {
                "detected": dict(
                    value=detected,
                    threshold="all six detectors",
                    **{"pass": all(detected.values())},
                ),
                "methane_relative": dict(
                    value=methane,
                    threshold="<0.5",
                    **{"pass": bool(methane) and all(v < 0.5 for v in methane)},
                ),
            }
            verdict = "pass" if ok else "fail"
        if args.target == "wise0855" and args.product == "spectrum":
            metrics = {}
            ok = True
            full = [b["id"] for b in m["bins"]["6"] if b["status"] == "full"]
            for visit in full:
                for band in [1, 2, 3, 6]:
                    rows = [
                        r
                        for r in out["rows"]
                        if r["visit"] == visit
                        and r["detector"] == band
                        and not r["contaminated"]
                    ]
                    if not rows:
                        metrics[f"{visit}_D{band}"] = dict(
                            value=None,
                            threshold="native blend S/N; missing clean fits",
                            **{"pass": False},
                        )
                        ok = False
                        continue
                    f = np.array([r["flux"] for r in rows])
                    e = np.array([r["quality"]["stat_err_uJy"] for r in rows])
                    w = 1 / e**2
                    mean = float(w @ f / w.sum())
                    err = float(np.hypot(1 / np.sqrt(w.sum()), 0.03 * abs(mean)))
                    snr = mean / err
                    passed = snr >= 5 if band == 6 else abs(snr) < 3
                    metrics[f"{visit}_D{band}"] = dict(
                        value=snr,
                        threshold=">=5"
                        if band == 6
                        else "abs(S/N)<3 (signed blend flux must be consistent with zero)",
                        **{"pass": passed},
                    )
                    ok &= passed
            verdict = "pass" if ok and len(full) == 2 else "fail"
        if args.product == "astrometry" and out.get("fit"):
            f = out["fit"]
            cat = out.get("catalogue")
            tolerance = 1.0 if args.target == "barnard" else 1.5
            pa_tol = 6.0 if args.target == "barnard" else 20.0
            if cat:
                dp = abs((f["pa_deg"] - cat["pa_deg"] + 180) % 360 - 180)
                # |μ_fit − μ_cat| as vectors (law of cosines), not the difference of magnitudes: a fit with the right
                # speed in the wrong direction must not pass the speed tolerance.
                dm = float(np.sqrt(max(0.0, f["mu"] ** 2 + cat["mu"] ** 2
                                       - 2 * f["mu"] * cat["mu"] * np.cos(np.radians(dp)))))
                metrics = {
                    "pm_error_arcsec_yr": dict(
                        value=dm, threshold=f"<{tolerance} (vector difference)", **{"pass": dm < tolerance}
                    ),
                    "pm_magnitude_error_arcsec_yr": dict(
                        value=abs(f["mu"] - cat["mu"]), threshold="reported", **{"pass": None}
                    ),
                    "pa_error_deg": dict(
                        value=dp, threshold=f"<{pa_tol}", **{"pass": dp < pa_tol}
                    ),
                }
                verdict = "pass" if dm < tolerance and dp < pa_tol else "fail"
            if args.target == "wise0855":
                # A 10.2 specifies full-visit displacement, not a newly invented
                # proper-motion tolerance. Use the same native two-source points.
                visits = {}
                for point in out.get("points", []):
                    if point.get("fit_included", False):
                        visits.setdefault(point["visit"], []).append(point)
                centres = []
                from spherex.astrometry import visit_centroid

                for points in visits.values():
                    summary = visit_centroid(points)
                    centres.append(
                        (
                            summary["mjd"],
                            *summary["mean"],
                        )
                    )
                centres.sort()
                if len(centres) == 2:
                    delta = np.asarray(centres[1][1:]) - np.asarray(centres[0][1:])
                    displacement = float(np.hypot(*delta) / 6.15)
                    pa = float(np.degrees(np.arctan2(*delta)) % 360)
                    pa_error = abs((pa - 277 + 180) % 360 - 180)
                    ok = abs(displacement - 0.78) <= 0.3 and pa_error <= 20
                    metrics = {
                        "displacement_px": dict(
                            value=displacement,
                            threshold="0.78 +/-0.3",
                            **{"pass": abs(displacement - 0.78) <= 0.3},
                        ),
                        "pa_deg": dict(
                            value=pa, threshold="277 +/-20", **{"pass": pa_error <= 20}
                        ),
                    }
                    verdict = "pass" if ok else "fail"
                else:
                    metrics = {
                        "full_visits": dict(
                            value=len(centres),
                            threshold="exactly two full band-6 visits",
                            **{"pass": False},
                        )
                    }
                    verdict = "fail"
        if args.target == "rdra" and args.product == "lightcurve":
            bins = {p["bin"] for rows in out["bands"].values() for p in rows}
            period = out.get("periodogram")
            best = period["best_days"] if period else None
            metrics = {
                "independent_bins": dict(
                    value=len(bins), threshold=">=20", **{"pass": len(bins) >= 20}
                ),
                "period_days": dict(
                    value=best,
                    threshold="245 +/-30 days",
                    **{"pass": best is not None and abs(best - 245) <= 30},
                ),
            }
            verdict = (
                "pass"
                if len(bins) >= 20 and best is not None and abs(best - 245) <= 30
                else "fail"
            )
        if args.target == "rwaur" and args.product == "lightcurve":
            counts = {d: len(points) for d, points in out["bands"].items()}
            # Bins are not visits. This reports coverage without promoting a
            # same-release subset to the required three-visit result.
            metrics = {
                "points_by_band": dict(
                    value=counts,
                    threshold="at least three visits per band, not just time bins",
                    **{"pass": None},
                )
            }
            verdict = "inconclusive"
        check = {
            "spectrum": {"epsindb": "G4b-epsind", "wise0855": "G4b-wise-stacks"},
            "astrometry": {},
            "lightcurve": {"rdra": "G5.lc-rdra", "rwaur": "G5.lc-rwaur"},
        }[args.product].get(
            args.target,
            f"G3-pm-{args.target}"
            if args.product == "astrometry"
            else "M-rwaur-spectrum",
        )
        record(
            check,
            "L3",
            verdict,
            metrics,
            "# Native target acceptance\nComplete measurements and rejected frames:\n```json\n"
            + dest.read_text()
            + "\n```\n"
            "A passing numerical sample is still subject to foundations, external comparison and I review.",
            [
                r.access_url
                for r in plan.refs
                if r.id in set(out.get("native_frames", [f.id for f in plan.refs]))
            ],
            n_frames=len(out.get("native_frames", plan.refs)),
            pins=[pin["pin"]],
            author="M",
            code_paths=[
                "backend/app/measurement.py",
                "backend/spherex/photometry.py",
                "backend/spherex/astrometry.py",
                "backend/spherex/joint_astrometry.py",
                "backend/spherex/epsf.py",
                "scripts/verify/m_acceptance.py",
            ],
            figures={"measurements.png": buf.getvalue()},
            extra_files=metadata_evidence(),
        )
    except Exception as ex:
        check = (
            "G5.lc-rdra"
            if args.target == "rdra"
            else f"M-{args.target}-{args.product}-failure"
        )
        record(
            check,
            "L3" if "plan" in locals() else "L0",
            "fail",
            {},
            "# Native acceptance failed\n"
            + f"{type(ex).__name__}: {ex}\nNo replacement data or relaxed criterion used.",
            [r.access_url for r in plan.refs] if "plan" in locals() else [],
            pins=[pin["pin"]],
            author="M",
            code_paths=[
                "backend/app/measurement.py",
                "backend/spherex/lightcurve.py",
                "scripts/verify/m_acceptance.py",
            ],
        )
        raise
    finally:
        await svc.close()


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument(
        "--target",
        choices=["barnard", "epsindb", "wise0855", "rwaur", "rdra"],
        required=True,
    )
    p.add_argument(
        "--product", choices=["spectrum", "astrometry", "lightcurve"], required=True
    )
    p.add_argument("--release", choices=["", "qr2", "qr3"], default="")
    asyncio.run(main(p.parse_args()))
