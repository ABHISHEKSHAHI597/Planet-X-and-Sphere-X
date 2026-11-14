"""F2 (owner D, pair I): do the cutout path (CRPIXnA) and the S3-section path give the same parent-pixel
origin, the same WCS and identical IMAGE, FLAGS, VARIANCE and ZODI values for the same sky pixels?

Real frames, three different cases: QR3 7.0.5 (Barnard D6), QR2 6.x (WISE 0855 D6, `PSF` not `EPSF`,
`MP_` flag names) and a QR2 deep-field frame (R Dra). For each, a 6′-view cutout box:
  1. IRSA cutout, stream-aborted after ZODI (`IrsaCutoutSource`) → origin from CRPIXnA;
  2. S3 section of the same sky box (`S3SectionSource`, IRSA box rule + 1 px) → must contain the
     cutout's box (IRSA's exact sizing is not public; the edge offsets are reported);
  3. S3 section of exactly the cutout's parent-pixel box → every pixel of all four HDUs must be
     identical (NaN-aware, integers as integers), and the WCSs must agree at every pixel;
  4. the S3 "cover" box must contain the cutout box.
The Barnard and WISE 0855 pairs are committed as fixtures (backend/tests/data/real/f2/) for offline tests.

Usage: python scripts/verify/f02_sections_vs_cutouts.py
"""
import asyncio
import datetime
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).parents[2]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(Path(__file__).parent))

from astropy.wcs import WCS  # noqa: E402

from spherex.access.fitsio import WANTED  # noqa: E402
from spherex.access.fitsstream import IrsaCutoutSource, cutout_url  # noqa: E402
from spherex.access.fixture import write_fixture  # noqa: E402
from spherex.access.frames import FrameBox, cutout_size_deg  # noqa: E402
from spherex.access.http import IBE_PREFIX, make_client  # noqa: E402
from spherex.access.releases import load as load_registry  # noqa: E402
from spherex.access.s3sections import S3SectionSource, pixel_bounds  # noqa: E402
from spherex.calib import parent_origin  # noqa: E402
from spherex.types import FrameRef  # noqa: E402

FIXDIR = ROOT / "backend/tests/data/real/f2"
FRAMES = [  # (label, s3_key, collection, centre) — keys from the committed coverage fixture
    ("barnard_qr3_d6", "qr3/level2/2026W33_2A/l2b-v27-2026-241/6/level2_2026W33_2A_0594_4D6_spx_l2b-v27-2026-241.fits",
     "spherex_qr3", (269.4461, 4.7707), True),
    ("wise0855_qr2_d6", None, "spherex_qr2", (133.7578, -7.2420), True),
    ("rdra_qr2deep", None, "spherex_qr2_deep", (248.16733, 66.75502), False),
]
WCS_KEYS = ("CTYPE1", "CTYPE2", "CRVAL1", "CRVAL2", "CRPIX1", "CRPIX2", "CD1_1", "CD1_2", "CD2_1", "CD2_2",
            "PC1_1", "PC1_2", "PC2_1", "PC2_2", "CDELT1", "CDELT2", "A_ORDER", "B_ORDER", "AP_ORDER", "BP_ORDER",
            "CRPIX1A", "CRPIX2A", "CRVAL1A", "CRVAL2A", "CRPIX1W", "CRPIX2W", "NAXIS1", "NAXIS2")


def pick(target, coll, det):
    d = json.loads((ROOT / "backend/tests/data/real/frames_5targets.json").read_text())
    for r in d["rows"]:
        r = dict(zip(d["columns"], r))
        if r["target"] == target and r["collection"] == coll and int(r["DETECTOR"]) == det:
            return r["s3_key"]
    raise LookupError((target, coll, det))


def header_diff(ha, hb):
    out = {}
    keys = [k for k in WCS_KEYS] + [k for k in ha if k.startswith(("A_", "B_", "AP_", "BP_")) and k[-1].isdigit()]
    for k in keys:
        a, b = ha.get(k), hb.get(k)
        if a is None and b is None:
            continue
        same = (a == b) if not (isinstance(a, float) or isinstance(b, float)) else \
            (a is not None and b is not None and abs(float(a) - float(b)) <= 1e-9 * max(1.0, abs(float(a))))
        if not same:
            out[k] = (a, b)
    return out


async def one(c, s3, cut, s3cover, label, key, coll, centre):
    ref = FrameRef(IBE_PREFIX + key, key, coll, "", int(key.rsplit("/", 2)[-2]), 0.0)   # …/<det>/<file>
    box = FrameBox(*centre, cutout_size_deg(6.0))
    fc = await cut.fetch(ref, box)
    fs_box = await s3.fetch(ref, box)
    ny, nx = fc.hdus["IMAGE"][1].shape
    x0, y0 = fc.origin
    fs = await s3.fetch_pixels(ref, x0, x0 + nx, y0, y0 + ny)
    m = await s3.headers(key)
    cover = pixel_bounds(m["IMAGE"].header, box)
    res = dict(label=label, s3_key=key, release=fc.release, version=str(fc.hdus["PRIMARY"][0].get("VERSION")).strip(),
               cutout_url=cutout_url(ref.access_url, box), box_deg=box.size_deg,
               cutout_origin=list(fc.origin), cutout_origin_from_crpixa=list(parent_origin(fc.hdus["IMAGE"][0])),
               cutout_shape=[ny, nx], s3_box_origin=list(fs_box.origin), s3_box_shape=list(fs_box.hdus["IMAGE"][1].shape),
               s3_section_header_origin=list(parent_origin(fs.hdus["IMAGE"][0])),
               cover_box=cover, cover_contains_cutout=bool(cover and cover[0] <= x0 and cover[2] <= y0 and
                                                           cover[1] >= x0 + nx and cover[3] >= y0 + ny),
               hdu_after_zodi=None, pixels={}, header_diffs={}, flags_compressed_in_s3=None)
    # Origin semantics: the S3 section of the cutout's exact box reports the cutout's origin, both through
    # RawFrame.origin and through parent_origin() of its shifted header.
    res["same_origin"] = res["cutout_origin"] == list(fs.origin) == res["s3_section_header_origin"]
    sb0, (sny, snx) = fs_box.origin, fs_box.hdus["IMAGE"][1].shape
    res["s3_box_edges_minus_cutout"] = [sb0[0] - x0, sb0[1] - y0, sb0[0] + snx - (x0 + nx), sb0[1] + sny - (y0 + ny)]
    res["s3_box_contains_cutout"] = sb0[0] <= x0 and sb0[1] <= y0 and sb0[0] + snx >= x0 + nx and sb0[1] + sny >= y0 + ny
    res["same_shape"] = res["s3_box_contains_cutout"]
    for n in WANTED:
        a, b = fc.hdus[n][1], fs.hdus[n][1]
        same = a.shape == b.shape and a.dtype == b.dtype and np.array_equal(a, b, equal_nan=True)
        fin = np.isfinite(a) if a.dtype.kind == "f" else np.ones(a.shape, bool)
        res["pixels"][n] = dict(identical=bool(same), dtype=[str(a.dtype), str(b.dtype)], n=int(a.size),
                                nan=int((~fin).sum()),
                                max_abs_diff=float(np.nanmax(np.abs(a.astype(float) - b.astype(float)))) if a.shape == b.shape else None)
        res["header_diffs"][n] = {k: [str(v[0]), str(v[1])] for k, v in header_diff(fc.hdus[n][0], fs.hdus[n][0]).items()}
    res["flags_compressed_in_s3"] = bool(m["FLAGS"].header.get("ZIMAGE", False))
    wa, wb = WCS(fc.hdus["IMAGE"][0]), WCS(fs.hdus["IMAGE"][0])
    yy, xx = np.mgrid[0:ny, 0:nx]
    ra_a, de_a = wa.all_pix2world(xx.ravel(), yy.ravel(), 0)
    ra_b, de_b = wb.all_pix2world(xx.ravel(), yy.ravel(), 0)
    sep = np.hypot((ra_a - ra_b) * np.cos(np.radians(de_a)), de_a - de_b) * 3600
    res["wcs_max_sep_arcsec"] = float(sep.max())
    full = WCS(m["IMAGE"].header)
    ra_f, de_f = full.all_pix2world(xx.ravel() + x0, yy.ravel() + y0, 0)
    res["wcs_vs_fullfile_max_sep_arcsec"] = float((np.hypot((ra_a - ra_f) * np.cos(np.radians(de_a)), de_a - de_f) * 3600).max())
    res["bytes_cutout"] = cut.last_timing.get("bytes")
    res["bytes_s3_exact"] = s3.last_timing.get("bytes")
    res["ok"] = bool(res["same_origin"] and res["same_shape"] and res["cover_contains_cutout"]
                     and all(p["identical"] for p in res["pixels"].values())
                     and res["wcs_max_sep_arcsec"] < 1e-6 and res["wcs_vs_fullfile_max_sep_arcsec"] < 1e-6)
    return res, fc, fs


async def main():
    from _evidence import record
    reg = load_registry()
    frames = []
    for label, key, coll, centre, keep in FRAMES:
        if key is None:
            key = pick("wise0855" if "wise" in label else "rdra", coll, 6 if "wise" in label else 3)
        frames.append((label, key, coll, centre, keep))
    results = []
    async with make_client() as c:
        s3 = S3SectionSource(c, registry=reg)
        cut = IrsaCutoutSource(c, registry=reg)
        for label, key, coll, centre, keep in frames:
            r, fc, fs = await one(c, s3, cut, None, label, key, coll, centre)
            results.append(r)
            print(label, "ok" if r["ok"] else "MISMATCH", r["cutout_origin"], r["s3_box_origin"], r["cutout_shape"],
                  {n: p["identical"] for n, p in r["pixels"].items()}, flush=True)
            if keep:
                prov = dict(source_url=r["cutout_url"], retrieved=datetime.date.today().isoformat(),
                            needed_by="F2; tests/real/test_real_access.py")
                write_fixture(FIXDIR, fc, f"{label}_cutout.fits", "crpixa",
                              dict(prov, path="irsa-cutout (stream-aborted after ZODI)", pipeline_version=r["version"]))
                fs.ref = FrameRef(fs.ref.access_url, fs.ref.s3_key + "#s3section", fs.ref.collection, "", fs.ref.detector, 0.0)
                write_fixture(FIXDIR, fs, f"{label}_s3section.fits", "section",
                              dict(prov, source_url="https://nasa-irsa-spherex.s3.amazonaws.com/" + key,
                                   path=("s3 byte-range rows (IMAGE/VARIANCE/ZODI) + RICE_1 row heap (FLAGS)"
                                         if r["flags_compressed_in_s3"] else "s3 byte-range rows of all four HDUs"),
                                   pipeline_version=r["version"]))
    ok = all(r["ok"] for r in results)
    metrics = {}
    for r in results:
        L = r["label"]
        metrics[f"{L}_origin"] = {"value": f"cutout {r['cutout_origin']} / s3 {r['s3_box_origin']} / section hdr {r['s3_section_header_origin']}",
                                  "threshold": "equal", "pass": r["same_origin"]}
        metrics[f"{L}_s3_box_contains_cutout"] = {"value": f"cutout {r['cutout_origin']} {r['cutout_shape']}; S3 box {r['s3_box_origin']} "
                                                  f"{r['s3_box_shape']}; edge offsets (x0, y0, x1, y1) {r['s3_box_edges_minus_cutout']}",
                                         "threshold": "S3 box ⊇ cutout box (failover never loses pixels)", "pass": r["s3_box_contains_cutout"]}
        for n, p in r["pixels"].items():
            metrics[f"{L}_{n}"] = {"value": f"identical={p['identical']} dtypes={p['dtype']} n={p['n']} nan={p['nan']}",
                                   "threshold": "bit-identical", "pass": p["identical"]}
        metrics[f"{L}_wcs_max_sep_arcsec"] = {"value": r["wcs_max_sep_arcsec"], "threshold": "< 1e-6", "pass": r["wcs_max_sep_arcsec"] < 1e-6}
        metrics[f"{L}_header_wcs_diffs"] = {"value": r["header_diffs"]["IMAGE"] or "none", "threshold": "none", "pass": not r["header_diffs"]["IMAGE"]}
    rows = "\n".join(f"| {r['label']} | {r['release']} {r['version']} | {r['cutout_origin']} | {r['s3_box_origin']} | "
                     f"{r['cutout_shape']} | {'/'.join(str(int(p['identical'])) for p in r['pixels'].values())} | "
                     f"{r['wcs_max_sep_arcsec']:.1e} | {r['flags_compressed_in_s3']} | {r['bytes_cutout']} / {r['bytes_s3_exact']} |"
                     for r in results)
    report = f"""
**Question (F2).** Do the cutout path (origin from `CRPIXnA`) and the S3-section path (origin known)
produce the same parent-pixel origin, the same WCS and identical pixel values for the same sky pixels?
Outcome: **{'confirmed' if ok else 'open — see mismatches'}**.

**Method.** Three real frames covering QR3, QR2 and a QR2 deep collection, each with a 6′-view box
(`cutout_size_deg(6) = {cutout_size_deg(6.0):.4f}°`). Cutout: IRSA, stream-aborted after ZODI. S3: anonymous
byte ranges; IMAGE/VARIANCE/ZODI as whole rows, FLAGS from the RICE_1 one-row-tile heap. Origins compared
three ways (cutout `CRPIXnA`; the S3 box computed from the sky box with the IRSA rule; `parent_origin` of the
shifted section header). Pixels compared bit for bit on the cutout's exact parent box; WCS compared at every
pixel, and against the full-file WCS offset by the origin. The S3 box computed from the *sky* box uses an
empirical copy of IRSA's sizing (pixel centres within c ± size/2) padded by 1 px, because IRSA's exact rule
is not public (an unpadded run, `-superseded-1`, was 1 px short on one axis): it must contain the cutout box.

| frame | release | cutout origin | S3 box origin | cutout shape | IMAGE/FLAGS/VAR/ZODI identical | WCS max Δ (″) | FLAGS RICE in S3 | bytes cutout / S3 |
|---|---|---|---|---|---|---|---|---|
{rows}

Consequences: either FrameSource can serve any frame (failover is transparent), every per-pixel calibration
lookup can use `RawFrame.origin` from either source, and S3 section headers obey `calib.parent_origin` just
like cutout headers.
"""
    d = record("F2", "L2", "pass" if ok else "fail", metrics, report,
               inputs={"frames": [r["s3_key"] for r in results], "fixtures": str(FIXDIR.relative_to(ROOT))},
               n_frames=len(results), code_paths=["backend/spherex/access/fitsstream.py",
                                                  "backend/spherex/access/s3sections.py",
                                                  "backend/spherex/access/fitsio.py", "backend/spherex/calib.py"],
               author="D")
    (d / "frames.json").write_text(json.dumps(results, indent=1, default=str))


if __name__ == "__main__":
    asyncio.run(main())
