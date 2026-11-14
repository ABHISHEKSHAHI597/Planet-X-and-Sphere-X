"""Collect Role D's real-response fixtures (workflow.md §8.2), recorded through the real clients with
`RecordingTransport`, so offline tests replay genuine archive answers.

  catalogs   SIMBAD (names incl. the traps), Gaia DR3 (targets + a WISE 0855 cone), 2MASS epochs and an
             image search, AllWISE + NEOWISE SIA2, CatWISE2020, SkyBoT (RW Aur, -loc=500)
  listings   S3 listings: top level, qr2/qr3 planning periods, a paginated calibration listing
  calheaders every HDU header of every file in config/calibration.lock (headers only; F1, F3, F4, F5, F13)
  frameheaders  the S3 header walk of one QR3 L2 file (deepfield tests)
  blink25    the responses behind the WISE 0855 25-year-blink plan

Output: backend/tests/data/real/recorded/<group>/ (gzip bodies + index.json) and a provenance sidecar.
Run from a machine with network access (ideally the VM); each group is resumable and small.
"""
import asyncio
import datetime
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from spherex.access.http import make_client  # noqa: E402
from spherex.access.replay import RecordingTransport  # noqa: E402

OUT = ROOT / "backend/tests/data/real/recorded"

SIMBAD_NAMES = ["Barnard's Star", "NAME Barnard's Star", "* eps Ind B", "WISE J085510.83-071442.5",
                "WISE 0855-0714", "V* RW Aur", "V* R Dra"]
GAIA_IDS = [4472832130942575872, 6412596012146801152, 156430822114424576, 156430817820015232,
            1648328016354496384, 5756956644387831296]
# Positions near each target's 2MASS epoch (≈2000): SIMBAD J2000 (understanding.md §8.1)
TWOMASS_AT_2000 = {"barnard": (269.45208, 4.69336), "epsindb": (331.04415, -56.78284),
                   "wise0855": (133.81891, -7.24705), "rwaur": (76.95653, 30.40144), "rdra": (248.16761, 66.75498)}
WISE0855_2010 = (133.795129, -7.245147)    # the challenge coordinate = WISE discovery epoch ≈2010.45
WISE0855_2015 = (133.78391, -7.24417)      # linear PM to CatWISE's epoch 2015.4 (search centre only)
WISE0855_2026 = (133.7578, -7.2420)


def provenance(group, content, needed_by):
    d = OUT / group
    idx = json.loads((d / "index.json").read_text())
    files = {e["file"]: dict(bytes_gz=(d / e["file"]).stat().st_size, sha256_body=e["sha256"], request=k,
                             status=e["status"], retrieved=e["retrieved"]) for k, e in idx.items()}
    (OUT / f"{group}.provenance.json").write_text(json.dumps(dict(
        source="live services, recorded by spherex.access.replay.RecordingTransport", group=group,
        retrieved=datetime.date.today().isoformat(), content=content, needed_by=needed_by,
        collected_by="D (scripts/collect_d_fixtures.py)", files=files), indent=1))


async def catalogs():
    from spherex.external.catwise import CatwiseClient
    from spherex.external.gaia import GaiaClient
    from spherex.external.simbad import SimbadClient
    from spherex.external.skybot import SkybotClient
    from spherex.external.twomass import TwoMassClient
    from spherex.external.wise import WiseClient
    rec = RecordingTransport(OUT / "catalogs")
    async with make_client(rec) as c:
        s = SimbadClient(c)
        res = {}
        for n in SIMBAD_NAMES:
            o = await s.by_identifier(n)
            res[n] = o.main_id if o else None
            print("SIMBAD", n, "→", res[n])
        b = await s.by_identifier("NAME Barnard's Star")
        print("Gaia id of Barnard via SIMBAD:", await s.gaia_dr3_id(b.oid))
        print("high-PM cone at the challenge WISE 0855 coordinate:",
              [o.main_id for o in await s.high_pm_cone(*WISE0855_2010)])
        g = GaiaClient(c)
        print("Gaia by id:", len(await g.by_id(GAIA_IDS)))
        print("Gaia cone WISE 0855 (0.02°):", len(await g.cone(*WISE0855_2026, 0.02)))
        t = TwoMassClient(c)
        for k, (ra, dec) in TWOMASS_AT_2000.items():
            src = await t.epoch_of(ra, dec, 0.01)
            print("2MASS", k, None if src is None else (src.designation, src.k_m, src.date, round(src.epoch, 3)))
        print("2MASS Ks images at Barnard:", len(await t.images(269.452, 4.6946, "k")))
        w = WiseClient(c)
        print("AllWISE W1/W2 at WISE 0855 (2010):", len(await w.allwise(*WISE0855_2010)))
        print("NEOWISE W1/W2 at WISE 0855 (2010):", len(await w.neowise(*WISE0855_2010)))
        print("CatWISE near WISE 0855 (2015.4):", [(x.source_name, x.pmra, x.pmdec) for x in
                                                    await CatwiseClient(c).cone(*WISE0855_2015, 0.01)])
        sk = await SkybotClient(c).cone(2460928.5, 76.9565, 30.4013, 0.25)
        print("SkyBoT RW Aur 2025-09-10:", [(o.name, o.mv) for o in sk])
    provenance("catalogs", "SIMBAD, Gaia DR3, 2MASS PSC + IBE image search, AllWISE/NEOWISE SIA2, CatWISE2020, "
               "SkyBoT responses for the acceptance targets", "tests/unit/test_external_clients.py")


async def listings():
    from spherex.access.s3list import list_s3
    rec = RecordingTransport(OUT / "listings")
    async with make_client(rec) as c:
        print("top", (await list_s3(c, "", "/")).prefixes)
        for r in ("qr3/", "qr2/"):
            lst = await list_s3(c, r + "level2/", "/")
            print(r, len(lst.prefixes), lst.prefixes[-1])
        lst = await list_s3(c, "qr3/epsf/", None, max_keys=3)
        print("paginated epsf listing:", lst.pages, "pages", len(lst.objects), "objects")
        for prod in ("spectral_wcs", "spectral_channels", "epsf", "l3_flux_corrections", "solid_angle_pixel_map"):
            await list_s3(c, f"qr3/{prod}/", None)
    provenance("listings", "S3 ListObjectsV2 pages (top level, level2 planning periods, calibration products; "
               "qr3/epsf/ with max-keys=3 for real pagination)", "tests/unit/test_watcher_calib_replay.py")


async def calheaders():
    from spherex.access.fitsio import data_bytes, extname, header_end, padded, parse_header
    from spherex.access.http import HostLimiter, TransferStats
    from spherex.access.s3sections import RangeReader
    from spherex.calib import CalibrationLock
    lock = CalibrationLock.load()
    out = {}
    async with make_client() as c:
        rr = RangeReader(c, HostLimiter(), TransferStats())
        for e in lock.entries:
            hdrs, off = [], 0
            while off < e.size:
                raw = b""
                end = None
                while end is None:
                    raw += await rr.get(e.s3_key, off + len(raw), min(off + len(raw) + 64 * 1024, e.size))
                    end = header_end(raw)
                h = parse_header(raw[:end])
                hdrs.append(dict(extname=extname(h), offset=off, data_bytes=data_bytes(h), header=h.tostring(sep="\n")))
                off += end + padded(data_bytes(h))
            out[e.s3_key] = dict(product=e.product, detector=e.detector, size=e.size, hdus=hdrs)
            print(e.s3_key, [x["extname"] for x in hdrs])
    p = ROOT / "backend/tests/data/real/calib_headers.json"
    p.write_text(json.dumps(out, indent=0))
    (ROOT / "backend/tests/data/real/calib_headers.provenance.json").write_text(json.dumps(dict(
        source="https://nasa-irsa-spherex.s3.amazonaws.com/<s3_key> byte ranges (headers only)",
        retrieved=datetime.date.today().isoformat(), calibration_lock=lock.lock_hash(),
        content="every HDU header (text), data offset and size of every file in config/calibration.lock",
        bytes=p.stat().st_size, sha256=hashlib.sha256(p.read_bytes()).hexdigest(),
        collected_by="D (scripts/collect_d_fixtures.py calheaders)",
        needed_by="tests/unit/test_watcher_calib_replay.py; F1, F3 (I); F4, F5, F13 (M)"), indent=1))


async def frameheaders():
    """Full-file header walk (S3 ranges) of the F2 Barnard frame, for deepfield.frame_inputs tests."""
    from spherex.access.s3sections import S3SectionSource
    key = "qr3/level2/2026W33_2A/l2b-v27-2026-241/6/level2_2026W33_2A_0594_4D6_spx_l2b-v27-2026-241.fits"
    async with make_client(RecordingTransport(OUT / "frame_headers")) as c:
        m = await S3SectionSource(c).headers(key)
        print({k: (v.data_offset, v.nbytes) for k, v in m.items()})
    provenance("frame_headers", "S3 byte ranges covering the PRIMARY..ZODI headers of one QR3 L2 file",
               "tests/unit/test_deepfield_blink25.py")


async def blink25():
    """Every response the WISE 0855 25-year-blink plan needs (fp_psc, IBE, AllWISE, NEOWISE)."""
    from spherex.access.blink25 import linear_pos, plan
    from spherex.constants import TEST_TARGETS
    from spherex.external.twomass import TwoMassClient
    from spherex.external.wise import WiseClient
    ra, dec, ep, pmra, pmdec = TEST_TARGETS["WISE 0855-0714"][:5]
    async with make_client(RecordingTransport(OUT / "blink25"), timeout=300) as c:
        p = await plan("wise0855", linear_pos(ra, dec, ep, pmra, pmdec), 2026.63, TwoMassClient(c), WiseClient(c),
                       "linear", k_expected=23.0)
        print(p.fov_arcmin, [(e.label, len(e.images)) for e in p.epochs][:4])
    provenance("blink25", "fp_psc, AllWISE and NEOWISE SIA2 responses for the WISE 0855 25-year-blink plan",
               "tests/unit/test_deepfield_blink25.py")


if __name__ == "__main__":
    asyncio.run({"catalogs": catalogs, "listings": listings, "calheaders": calheaders, "frameheaders": frameheaders,
                 "blink25": blink25}[sys.argv[1]]())
