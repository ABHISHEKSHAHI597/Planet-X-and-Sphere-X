"""TEMPORARY ADAPTER (owner I; D's pins, coverage and fixture pipeline replace it): collect the small
real-archive inputs Role I's checks need when run from a laptop. Resumable; everything big stays in the
cache directory ($PARALLAX_CACHE, default ~/.cache/parallax-verify), never in git.

  coverage   SIA2 rows (QR2+QR3, deep collections included) for the 5 acceptance targets
  headers    PRIMARY+IMAGE header summary of every covering frame, via one S3 byte range each (F8, G1)
  calib      CHANNEL_MAP + SPECTRAL_CHANNELS (F3), spectral_wcs WCS-WAVE tables, CWAVE rows (F1), full D6 CWAVE
  cutouts    stream-aborted cutouts for F6 part 2, F7, F16 and the G2/G4a real-target checks

Usage: python scripts/verify/collect_real.py coverage|headers|calib|cutouts
"""
import json
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from _archive import cutout, s3_hdu_map, s3_header_at, s3_image_rows, s3_range, s3_rice_rows, sia2

CACHE = Path(os.environ.get("PARALLAX_CACHE", Path.home() / ".cache/parallax-verify"))
COLL = ["spherex_qr2", "spherex_qr2_deep", "spherex_qr3", "spherex_qr3_deep"]
# Positions at ≈2026.0 (implementation.md §14.2 for Barnard/WISE; others propagated from §14.1)
TARGETS = {"barnard": (269.4461, 4.7707), "epsindb": (331.0918, -56.7966), "wise0855": (133.7578, -7.2420),
           "rwaur": (76.95654, 30.40130), "rdra": (248.16733, 66.75502)}
HDR_KEYS = ("DETECTOR", "OBSID", "EXPIDN", "MJD-BEG", "MJD-AVG", "MJD-END", "SPS_ELON", "SPS_ELAT", "SPS_EPA",
            "FINAST", "L1DQAFLG", "L2DQAFLG", "PSF_FWHM", "OMEGA_MEDIAN", "PXSRCMSK", "HE_AIRGLOW_CONT",
            "AURORA_CONT", "SHUTTLE_GLOW_CONT", "NBLMSRCS", "NSNOWSRC", "KOVR_A")
CAL = "qr3/spectral_wcs/cal-swcs-v5-2026-191/{d}/spectral_wcs_D{d}_spx_cal-swcs-v5-2026-191.fits"
CHMAP = "qr3/spectral_channels/cal-sch-v2-2026-229/spectral_channels_spx_cal-sch-v2-2026-229.fits"


def coverage():
    CACHE.mkdir(parents=True, exist_ok=True)
    for name, (ra, dec) in TARGETS.items():
        p = CACHE / f"sia2_{name}.json"
        if not p.exists():
            rows = sia2(ra, dec, 0.001, COLL)
            p.write_text(json.dumps(rows))
        print(name, len(json.loads(p.read_text())))


def _hdr(key):
    p = CACHE / "headers" / (key.replace("/", "__") + ".json")
    if p.exists():
        return
    hp, off = s3_header_at(key, 0, chunk=10 * 2880)
    hi, _ = s3_header_at(key, off, chunk=10 * 2880)
    d = {k: hi.get(k) for k in HDR_KEYS}
    d["VERSION"] = hp.get("VERSION")
    p.write_text(json.dumps(d, default=str))


def headers():
    (CACHE / "headers").mkdir(parents=True, exist_ok=True)
    keys = sorted({r["s3_key"] for n in TARGETS for r in json.loads((CACHE / f"sia2_{n}.json").read_text())})
    print(len(keys), "frames")
    done = 0
    with ThreadPoolExecutor(8) as ex:
        for fut in [ex.submit(_hdr, k) for k in keys]:
            try:
                fut.result()
            except Exception as e:
                print("FAIL", e)
            done += 1
            if done % 200 == 0:
                print(done, flush=True)


def calib():
    c = CACHE / "calib"
    c.mkdir(parents=True, exist_ok=True)
    if not (c / "channel_map.npy").exists():
        m = {n: (h, o, nb) for n, h, o, nb in s3_hdu_map(CHMAP)}
        h, o, _ = m["CHANNEL_MAP"]
        np.save(c / "channel_map.npy", s3_image_rows(CHMAP, h, o, 0, 2040))
        h, o, nb = m["SPECTRAL_CHANNELS"]
        (c / "spectral_channels.bin").write_bytes(s3_range(CHMAP, o, o + nb))
        (c / "spectral_channels.hdr").write_text(h.tostring())
    rows = np.arange(0, 2040, 40)
    for d in range(1, 7):
        key = CAL.format(d=d)
        if (c / f"cwave_rows_D{d}.npy").exists():
            continue
        m = {n: (h, o, nb) for n, h, o, nb in s3_hdu_map(key)}
        h, o, nb = m["WCS-WAVE"]
        (c / f"wcswave_D{d}.bin").write_bytes(s3_range(key, o, o + nb))
        (c / f"wcswave_D{d}.hdr").write_text(h.tostring())
        h, o, _ = m["CWAVE"]
        np.save(c / f"cwave_rows_D{d}.npy", np.stack([s3_image_rows(key, h, o, y, y + 1)[0] for y in rows]))
        h2, o2, _ = m["CBAND"]
        np.save(c / f"cband_rows_D{d}.npy", np.stack([s3_image_rows(key, h2, o2, y, y + 1)[0] for y in rows]))
        print("D", d, "done", flush=True)
    np.save(c / "cwave_rows_index.npy", rows)
    if not (c / "cwave_D6.npy").exists():
        key = CAL.format(d=6)
        m = {n: (h, o, nb) for n, h, o, nb in s3_hdu_map(key, stop_after="CWAVE")}
        h, o, _ = m["CWAVE"]
        parts = [s3_image_rows(key, h, o, y, min(y + 102, 2040)) for y in range(0, 2040, 102)]
        np.save(c / "cwave_D6.npy", np.concatenate(parts))
        print("D6 CWAVE full done")


FNAME = re.compile(r"level2_(?P<obsid>\w+?)D(?P<det>\d)_spx_l2b(?:_retry)?-v(?P<ver>\d+)-(?P<y>\d{4})-(?P<doy>\d{3})")
PRIO = {"spherex_qr3": 30, "spherex_qr3_deep": 30, "spherex_qr2": 20, "spherex_qr2_deep": 20}


def dedup(rows):
    """Copy of implementation.md §3.3 (D owns the real one): one frame per (obsid, detector)."""
    best = {}
    for r in rows:
        m = FNAME.search(r["access_url"])
        if m is None or r["collection"] not in PRIO:
            continue
        key = (m["obsid"], int(m["det"]))
        rank = (PRIO[r["collection"]], int(m["ver"]), int(m["y"]) * 1000 + int(m["doy"]))
        if key not in best or rank > best[key][0]:
            best[key] = (rank, dict(r, detector=int(m["det"])))
    return sorted((v[1] for v in best.values()), key=lambda r: r["t_min"])


def rows(name):
    return dedup(json.loads((CACHE / f"sia2_{name}.json").read_text()))


# Cutout plan: (target, centre, size_deg, row filter). WISE: centred between its 2026 and WISE-era
# (challenge) positions so both lie in every cutout (F6 part 2).
WISE_MID = (133.7765, -7.2436)
BARNARD = (269.4461, 4.7707)


def plan():
    sys.path.insert(0, str(Path(__file__).parents[2] / "backend"))
    from spherex.epochs import classify_visits
    out = []
    w = rows("wise0855")
    _, vis = classify_visits([r["t_min"] for r in w], [r["detector"] for r in w])
    full = {i for b, vs in vis.items() for v in vs if v["status"] == "full" for i in v["idx"]}
    out += [("wise0855", WISE_MID, 0.1, w[i]) for i in sorted(full)]
    b = rows("barnard")
    out += [("barnard", BARNARD, 0.1, r) for r in b if r["detector"] == 6]
    # Static-field checks (G2 registration, G4a null / PA-flip): same band-6 frames, 7.2′ east of Barnard,
    # beyond the reach of its band-6 wings
    off = (BARNARD[0] + 0.12 / np.cos(np.radians(BARNARD[1])), BARNARD[1])
    out += [("barnard_off", off, 0.1, r) for r in b if r["detector"] == 6]
    # F7: crowded 12-arcmin field, 2 QR3 frames per detector
    q3 = [r for r in b if r["collection"].startswith("spherex_qr3")]
    for d in range(1, 7):
        out += [("barnard12", BARNARD, 0.2, r) for r in [r for r in q3 if r["detector"] == d][:2]]
    return out


def _cut(item):
    tag, (ra, dec), size, r = item
    p = CACHE / "cutouts" / tag / (r["s3_key"].split("/")[-1].replace(".fits", ".npz"))
    if p.exists():
        return 0
    hdus, prim, nread = cutout(r["access_url"], ra, dec, size)
    np.savez_compressed(p, **{n: d for n, (h, d) in hdus.items()},
                        **{n + "_hdr": np.array(h.tostring()) for n, (h, d) in hdus.items()},
                        PRIMARY_hdr=np.array(prim.tostring()), meta=np.array(json.dumps(dict(r, size=size, ra=ra, dec=dec, bytes=nread))))
    return nread


def cutouts():
    items = plan()
    for t in {i[0] for i in items}:
        (CACHE / "cutouts" / t).mkdir(parents=True, exist_ok=True)
    print(len(items), "cutouts planned", flush=True)
    total = 0
    with ThreadPoolExecutor(2) as ex:           # IRSA returned 503 at 4 parallel from our network
        for k, fut in enumerate([ex.submit(_cut, it) for it in items]):
            try:
                total += fut.result()
            except Exception as e:
                print("SKIP", items[k][3]["s3_key"], e, flush=True)
            if k % 20 == 0:
                print(k, total, flush=True)
    print("bytes", total)


FIXTURE_KEY = "qr3/level2/2026W33_2A/l2b-v27-2026-241/6/level2_2026W33_2A_0594_4D6_spx_l2b-v27-2026-241.fits"


def l2wave():
    """F1: the WCS-WAVE table and headers of one full QR3 L2 file per detector (header walking only),
    plus the IMAGE rows of the fixture cutout's parent pixels (S3-section path; also evidence for F2)."""
    c = CACHE / "l2"
    c.mkdir(parents=True, exist_ok=True)
    b = [r for r in rows("barnard") if r["collection"] == "spherex_qr3"]
    keys = {6: FIXTURE_KEY} | {d: next(r["s3_key"] for r in b if r["detector"] == d) for d in range(1, 6)}
    for d, key in keys.items():
        p = c / f"D{d}.json"
        if p.exists():
            continue
        m = s3_hdu_map(key, stop_after="WCS-WAVE")
        out = {"key": key, "hdus": [(n, h.tostring(), o, nb) for n, h, o, nb in m]}
        n, h, o, nb = m[-1]
        (c / f"D{d}_wcswave.bin").write_bytes(s3_range(key, o, o + nb))
        p.write_text(json.dumps(out))
        print(d, [x[0] for x in m], flush=True)
    if not (c / "fixture_section.npz").exists():
        m = {n: (h, o) for n, h, o, nb in json_hdus(c / "D6.json")}
        y0, x0, n = 1919, 638, 29                    # fixture parent origin (CRPIXnA = −637, −1918)
        sec = {k: s3_image_rows(FIXTURE_KEY, m[k][0], m[k][1], y0, y0 + n)[:, x0:x0 + n]
               for k in ("IMAGE", "VARIANCE", "ZODI")}
        sec["FLAGS"] = s3_rice_rows(FIXTURE_KEY, m["FLAGS"][0], m["FLAGS"][1], y0, y0 + n)[:, x0:x0 + n]
        np.savez_compressed(c / "fixture_section.npz", **sec)


def json_hdus(p):
    from astropy.io import fits
    return [(n, fits.Header.fromstring(h), o, nb) for n, h, o, nb in json.loads(Path(p).read_text())["hdus"]]


if __name__ == "__main__":
    {"coverage": coverage, "headers": headers, "calib": calib, "cutouts": cutouts, "l2wave": l2wave}[sys.argv[1]]()
