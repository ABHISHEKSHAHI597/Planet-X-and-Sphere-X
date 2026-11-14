"""L2/L3 on committed real data (no network): the F2 cutout/S3-section pairs, the fixture FrameSource,
the D → I contract through I's `calibrate`, the recorded SIA2/TAP responses (F11) and the pins."""
import asyncio
import hashlib
import json
from pathlib import Path

import numpy as np
import pytest

from spherex.access import pins
from spherex.access.coverage import CoverageClient
from spherex.access.dedup import dedup
from spherex.access.fixture import FixtureSource
from spherex.access.frames import FrameBox, FrameUnavailable
from spherex.access.http import make_client
from spherex.access.releases import load as load_registry
from spherex.access.replay import ReplayTransport
from spherex.calib import SlicedCalib, parent_origin
from spherex.types import FrameRef

REAL = Path(__file__).parents[1] / "data/real"
REPO = Path(__file__).parents[3]
F2_KEY = "qr3/level2/2026W33_2A/l2b-v27-2026-241/6/level2_2026W33_2A_0594_4D6_spx_l2b-v27-2026-241.fits"
W_KEY = "qr2/level2/2026W17_1B/l2b-v24-2026-115/6/level2_2026W17_1B_0634_4D6_spx_l2b-v24-2026-115.fits"
REG = load_registry()
TARGETS = {"barnard": (269.4461, 4.7707), "epsindb": (331.0918, -56.7966), "wise0855": (133.7578, -7.2420),
           "rwaur": (76.95654, 30.40130), "rdra": (248.16733, 66.75502)}


def fixture_root():
    return REAL / "f2"


@pytest.mark.parametrize("key", [F2_KEY, W_KEY])
def test_f2_pairs_identical_origin_wcs_pixels(key):
    src = FixtureSource(fixture_root())
    c, s = src.load(key), src.load(key + "#s3section")
    assert c.origin == s.origin == parent_origin(c.hdus["IMAGE"][0]) == parent_origin(s.hdus["IMAGE"][0])
    for n in ("IMAGE", "FLAGS", "VARIANCE", "ZODI"):
        assert np.array_equal(c.hdus[n][1], s.hdus[n][1], equal_nan=True), n
    assert c.hdus["FLAGS"][1].dtype == np.int64
    ny, nx = c.hdus["IMAGE"][1].shape
    yy, xx = np.mgrid[0:ny:7, 0:nx:7]
    a = np.array(c.wcs.all_pix2world(xx.ravel(), yy.ravel(), 0))
    b = np.array(s.wcs.all_pix2world(xx.ravel(), yy.ravel(), 0))
    assert np.abs(a - b).max() < 1e-10


def test_fixture_index_hashes_and_provenance():
    idx = json.loads((fixture_root() / "index.json").read_text())
    for key, e in idx.items():
        p = fixture_root() / e["file"]
        assert hashlib.sha256(p.read_bytes()).hexdigest() == e["sha256"] and p.stat().st_size == e["bytes"] < 5e6
        assert e["retrieved"] and e["source_url"].startswith("https://") and e["release"] in ("qr2", "qr3")


def test_fixture_source_serves_only_real_bytes():
    src = FixtureSource(fixture_root())
    ref = FrameRef("https://irsa.ipac.caltech.edu/ibe/data/spherex/" + F2_KEY, F2_KEY, "spherex_qr3", "x", 6, 0.0)
    f = asyncio.run(src.fetch(ref, FrameBox(269.4461, 4.7707, 0.05)))
    assert f.release == "qr3" and f.origin == (607, 1888)
    with pytest.raises(FrameUnavailable):
        asyncio.run(src.fetch(ref, FrameBox(10.0, 10.0, 0.05)))     # box off this frame
    with pytest.raises(FrameUnavailable):
        asyncio.run(src.fetch(FrameRef("u", "qr3/none.fits", "spherex_qr3", "x", 6, 0.0), FrameBox(0, 0, 0.1)))


def test_d_to_i_contract_both_sources_calibrate_identically():
    """RawFrame from either FrameSource goes through I's calibrate() to the same CalFrame."""
    pytest.importorskip("astropy")
    from spherex.preprocess import calibrate
    cw = np.load(REAL / "cwave_D6_fixture_slice.npy")
    ch = np.load(REAL / "channel_map_fixture_slice.npy")
    cal = SlicedCalib((638, 1919), {6: cw}, ch, cband={6: cw / 128.0})
    src = FixtureSource(fixture_root())
    a = calibrate(src.load(F2_KEY), cal)
    b = calibrate(src.load(F2_KEY + "#s3section"), cal)
    for k in ("sci", "var", "lam", "flags"):
        assert np.array_equal(getattr(a, k), getattr(b, k), equal_nan=True), k
    assert a.origin == b.origin == (607, 1888) and a.detector == 6 and a.photometric_scale == "qr3"
    ps = (slice(1919 - 1888, 1948 - 1888), slice(638 - 607, 667 - 607))   # the window with known λ
    assert np.isfinite(a.lam[ps]).all() and np.allclose(a.lam[ps], cw)


def _replayed_sia2(name):
    async def go():
        async with make_client(ReplayTransport(REAL / "recorded/coverage")) as c:
            cov = CoverageClient(c, REG)
            ra, dec = TARGETS[name]
            return await cov.sia2(ra, dec, 0.001, REG.collections()), await cov.tap(ra, dec, REG.collections())
    return asyncio.run(go())


@pytest.mark.parametrize("name,expected", [("barnard", 359), ("epsindb", 447), ("wise0855", 256), ("rwaur", 333),
                                           ("rdra", 2483)])
def test_f11_replay_sia2_equals_tap_and_matches_pin(name, expected):
    sia, tap = _replayed_sia2(name)
    a, b = dedup(sia, REG), dedup(tap, REG)
    assert {f.access_url for f in a.frames} == {f.access_url for f in b.frames}
    assert len(a.frames) == expected
    idx = json.loads((REPO / "config/pins/index.json").read_text())
    p = pins.load(idx[name]["pin"])
    assert [f.access_url for f in p.frames] == [f.access_url for f in a.frames]


def test_pins_target_specific_facts():
    idx = json.loads((REPO / "config/pins/index.json").read_text())
    w = pins.load(idx["wise0855"]["pin"])
    assert {f["release"] for f in w.doc["frames"]} == {"qr2"}              # WISE 0855: QR2 only
    det6 = sorted(f.t_min for f in w.frames if f.detector == 6)
    assert len(det6) == 3 + 16 + 3 + 21                                     # understanding.md §3.4
    r = pins.load(idx["rdra"]["pin"])
    deep = sum(f.collection.endswith("_deep") for f in r.frames)
    assert len(r.frames) == 2483 and 1900 < deep < 2000                     # ≈1,950 deep
    b = pins.load(idx["barnard"]["pin"])
    by_obs = {}
    for f in b.frames:
        by_obs.setdefault(f.obs_id, set()).add(f.detector)
    pairs = sum(v in ({1, 4}, {2, 5}, {3, 6}) for v in by_obs.values())
    assert pairs >= 0.95 * len(by_obs)                                      # co-aligned pairs kept
    retry = sum(f["retry"] for name in idx for f in pins.load(idx[name]["pin"]).doc["frames"])
    assert retry == 11                                                      # the `_retry` files survive dedup
