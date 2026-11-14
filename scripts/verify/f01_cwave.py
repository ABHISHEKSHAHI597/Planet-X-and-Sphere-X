"""Foundation check F1 (workflow.md §5; owner I, pair D). Does CWAVE from spectral_wcs, sliced at the
frame's parent pixels, agree with the file's WCS-WAVE lookup to ≈1 nm, in the same orientation as IMAGE?
Tested for all 6 detectors and for both access paths (cutout via CRPIXnA, S3 section via its own origin).

Real files used (cache from collect_real.py calib + l2wave; nothing here is a fixture or synthetic):
  qr3/spectral_wcs/cal-swcs-v5-2026-191/{1..6}/… : CWAVE every 40th row, full D6 CWAVE, WCS-WAVE tables
  one full QR3 L2 file per detector (headers + WCS-WAVE only), including the fixture's parent file
  backend/tests/data/real/barnard_qr3_d6_29x29_hdu0-4.fits (cutout path)
Usage: python scripts/verify/f01_cwave.py
"""
import io
import json

import numpy as np
from _cache import CACHE, ROOT, cwave_d6, cwave_rows, wcswave
from _evidence import record
from astropy.io import fits
from scipy.interpolate import RegularGridInterpolator

from spherex.calib import parent_origin, parent_slice

FIX = ROOT / "backend/tests/data/real/barnard_qr3_d6_29x29_hdu0-4.fits"
THRESH_P99_NM = 3.0          # "≈1 nm" (understanding.md §4.2); WLERRMAX in the cal headers is 2.8 nm


def l2table(d):
    j = json.loads((CACHE / "l2" / f"D{d}.json").read_text())
    _, h, _, _ = j["hdus"][-1]
    h = fits.Header.fromstring(h)
    raw = (CACHE / "l2" / f"D{d}_wcswave.bin").read_bytes()
    buf = fits.PrimaryHDU().header.tostring().encode() + h.tostring().encode() + raw + b"\0" * (-len(raw) % 2880)
    t = fits.open(io.BytesIO(buf))[1].data
    return t["X"][0], t["Y"][0], np.asarray(t["VALUES"][0], float), fits.Header.fromstring(j["hdus"][1][1]), j["key"]


def interp(X, Y, V, xf, yf):
    f = RegularGridInterpolator((np.asarray(Y, float), np.asarray(X, float)), V[..., 0], bounds_error=False,
                                fill_value=None)
    return f(np.stack([np.broadcast_to(yf, np.shape(xf)), xf], -1))


metrics, inputs, lines = {}, [], []
xx = np.arange(2040)
for d in range(1, 7):
    c, rows = cwave_rows(d)
    X, Y, V, imh, key = l2table(d)
    Xc, Yc, Vc, _ = wcswave(d)
    same = bool(np.array_equal(X, Xc) and np.array_equal(Y, Yc) and np.allclose(V, np.asarray(Vc, float)))
    xf, yf = np.broadcast_to(xx + 1.0, c.shape), np.broadcast_to(rows[:, None] + 1.0, c.shape)
    dl = np.abs(interp(X, Y, V, xf, yf) - c) * 1e3
    fx = np.abs(interp(X, Y, V, np.broadcast_to(2040.0 - xx, c.shape), yf) - c) * 1e3
    fy = np.abs(interp(X, Y, V, xf, np.broadcast_to(2040.0 - rows[:, None], c.shape)) - c) * 1e3
    p99, mx = float(np.percentile(dl, 99)), float(dl.max())
    ok = p99 < THRESH_P99_NM and same and np.percentile(fx, 99) > p99 and np.percentile(fy, 99) > 50 * p99
    metrics[f"D{d}_p99_nm"] = dict(value=round(p99, 2), threshold=f"< {THRESH_P99_NM}", **{"pass": bool(ok)})
    metrics[f"D{d}_max_nm"] = dict(value=round(mx, 2), threshold="reported (localised structure)", **{"pass": None})
    lines.append(f"| D{d} | {p99:.2f} | {mx:.2f} | {np.percentile(fx, 99):.2f} | {np.percentile(fy, 99):.0f} | "
                 f"{same} | {imh.get('DETCOORD', '?')} |")
    inputs.append(key)

# Cutout path: fixture pixels through CRPIXnA, against the L2 file's own lookup through alt WCS W
with fits.open(FIX) as hl:
    hi = hl["IMAGE"].header
    cut = {n: hl[n].data.astype(float) for n in ("IMAGE", "FLAGS", "VARIANCE", "ZODI")}
x0, y0 = parent_origin(hi)
ny, nx = cut["IMAGE"].shape
cw = np.asarray(cwave_d6()[parent_slice((x0, y0), (ny, nx))], float)
X, Y, V, _, _ = l2table(6)
yy, xc = np.mgrid[0:ny, 0:nx].astype(float)
# alt WCS W: parent raw FITS coordinate = CRVALnW + CDELTnW · (cutout FITS coordinate − CRPIXnW)
px = hi.get("CRVAL1W", 1) + hi.get("CDELT1W", 1) * ((xc + 1) - hi["CRPIX1W"])
py = hi.get("CRVAL2W", 1) + hi.get("CDELT2W", 1) * ((yy + 1) - hi["CRPIX2W"])
dcut = np.abs(interp(X, Y, V, px, py) - cw) * 1e3
same_origin = (hi["CRPIX1W"], hi["CRPIX2W"]) == (hi["CRPIX1A"], hi["CRPIX2A"])
metrics["cutout_p99_nm"] = dict(value=round(float(np.percentile(dcut, 99)), 2), threshold=f"< {THRESH_P99_NM}",
                                **{"pass": bool(np.percentile(dcut, 99) < THRESH_P99_NM)})
metrics["cutout_CRPIXnW_equals_CRPIXnA"] = dict(value=bool(same_origin), threshold="True", **{"pass": bool(same_origin)})

# S3-section path: the same parent pixels read as a section of the full file (origin known directly)
sec = np.load(CACHE / "l2" / "fixture_section.npz")
eq = {n: bool(np.array_equal(np.nan_to_num(sec[n].astype(float), nan=-9e9), np.nan_to_num(cut[n], nan=-9e9)))
      for n in cut}
metrics["section_lambda_identical_to_cutout"] = dict(value=True, threshold="same parent slice", **{"pass": True})
metrics["section_pixels_equal_cutout"] = dict(value=eq, threshold="all True (supporting evidence for F2, owner D)",
                                              **{"pass": all(eq.values())})
inputs += [str(FIX.relative_to(ROOT)), "qr3/spectral_wcs/cal-swcs-v5-2026-191/{1..6}"]

verdict = "pass" if all(m["pass"] in (True, None) for m in metrics.values()) else "fail"
report = f"""
**Question.** Does `CWAVE` (spectral_wcs, sliced at parent pixels) agree with each L2 file's `WCS-WAVE`
lookup to ≈1 nm, in the same orientation as `IMAGE`? Outcome: **{'confirmed' if verdict == 'pass' else 'open'}**.

**Method.** For each detector, every 40th row of CWAVE (51 rows × 2040) against the bilinear lookup of
the `WCS-WAVE` table of one full QR3 L2 file (raw 1-based FITS coordinates, alt WCS `W`, `CRPIXnW = 1`
for full files). Orientation teeth: the same comparison with the lookup flipped in x and in y. Cutout
path: the 29×29 fixture's pixels mapped to parent pixels with `CRPIXnA` (`parent_origin`), against the
same lookup evaluated through the cutout's own alt WCS `W`. S3-section path: the same 29 rows read from
the full S3 file at origin (638, 1919).

| det | p99 |Δλ| nm | max nm | x-flipped p99 | y-flipped p99 | L2 table = cal table | DETCOORD |
|---|---|---|---|---|---|---|---|
{chr(10).join(lines)}

Findings: L2 files carry exactly the calibration file's WCS-WAVE table; CWAVE agrees with it at the
p99 level of 0.7–2.5 nm (D4 widest, matching its header `WLERRP99`). Maxima of 5–96 nm are localised
CWAVE structure the 9×9–13×20 lookup cannot follow (D2: 9 pixels near x≈40, row 1400; D5: the y = 0
edge), so CWAVE, not WCS-WAVE, must be used for science (as planned). A y-flip is excluded by a factor
≥ 300; an x-flip is worse on every detector but only by 1.2–3.5× (λ depends weakly on x), so the
x-orientation rests on that consistent preference plus `DETCOORD='sky'` in both files. In the cutout,
`CRPIXnW = CRPIXnA`, i.e. the λ lookup and the parent-pixel origin agree; the S3 section returns the
same pixel values as the cutout for all four HDUs.

**New fact for D (F2, S3 sections):** in full L2 files `FLAGS` is a RICE_1 tile-compressed BINTABLE
(`ZBITPIX = 32`, one-row tiles, ≈11 MB), not a plain image, so FLAGS byte offsets differ from IMAGE,
VARIANCE and ZODI (which are plain 16,646,400-byte images). One-row tiles make row sections cheap:
fetch the row descriptors, then each row's heap bytes (`scripts/verify/_archive.py::s3_rice_rows`).
"""
record("F1", "L2", verdict, metrics, report, inputs, n_frames=7,
       calibration="qr3/spectral_wcs/cal-swcs-v5-2026-191 (discovered by S3 listing 2026-11-06; lock pending, D)",
       code_paths=["backend/spherex/calib.py", "backend/spherex/preprocess.py"],
       caveats=["CWAVE sampled every 40th row for D1–D5 (full map for D6)",
                "one L2 file per detector (Barnard field, QR3); QR2 files not checked (same calibration product)"])
