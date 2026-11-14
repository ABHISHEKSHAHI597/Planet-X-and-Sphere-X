"""L0/L2: calibration discovery, lock and bootstrap; release watcher; all on replayed real S3 listings
(tests/data/real/recorded/listings) and real calibration headers (tests/data/real/calib_headers.json)."""
import asyncio
import hashlib
import io
import json
from pathlib import Path

import httpx
import numpy as np
import pytest
from astropy.io import fits

from spherex.access.http import make_client
from spherex.access.releases import load as load_registry
from spherex.access.replay import ReplayTransport
from spherex.access.s3list import list_s3
from spherex.access.watcher import ReleaseState, check, current_state
from spherex.calib import (LOCK_PATH, CalibIntegrityError, Calib, CalibrationLock, LockEntry, SlicedCalib, bootstrap,
                           discover, parent_slice, select_files, version_key)

REAL = Path(__file__).parents[1] / "data/real"
LIST = REAL / "recorded/listings"
REG = load_registry()


def replay():
    return make_client(ReplayTransport(LIST))


def test_real_listing_pagination_follows_tokens():
    async def go():
        async with replay() as c:
            return await list_s3(c, "qr3/epsf/", None, max_keys=3)
    lst = asyncio.run(go())
    assert lst.pages == 3 and len(lst.objects) == 7
    assert any("cal-epsf-v2" in o.key for o in lst.objects)


def test_discovery_on_real_listings_matches_committed_lock():
    async def go():
        async with replay() as c:
            return await discover(c, "qr3")
    lock = asyncio.run(go())
    committed = CalibrationLock.load()
    assert {(e.s3_key, e.size, e.etag_md5) for e in lock.entries} == \
        {(e.s3_key, e.size, e.etag_md5) for e in committed.entries}
    assert lock.get("epsf", 3).version_dir == "cal-epsf-v2-2026-191"          # D3's extra version
    assert lock.get("epsf", 1).version_dir == "cal-epsf-v1-2026-191"
    assert lock.get("spectral_wcs", 6).version_dir == "cal-swcs-v5-2026-191"   # not the documented cal-wcs
    assert lock.get("spectral_channels").detector is None
    assert len(lock.entries) == 25


def test_version_key_and_selection_rules():
    assert version_key("cal-swcs-v5-2026-191") > version_key("cal-swcs-v4-2026-300")
    assert version_key("cal-epsf-v2-2026-191") > version_key("cal-epsf-v1-2026-191")
    with pytest.raises(ValueError):
        version_key("cal-wcs")
    objs = [(f"qr3/spectral_wcs/cal-swcs-v5-2026-191/{d}/spectral_wcs_D{d}_spx_cal-swcs-v5-2026-191.fits", 1, "a")
            for d in range(1, 6)]
    with pytest.raises(ValueError):                                    # D6 missing → refuse
        select_files("spectral_wcs", objs, "qr3")


def test_lock_hash_detects_hand_edits():
    lock = CalibrationLock.load(LOCK_PATH)
    d = json.loads(lock.to_json())
    d["files"][0]["size"] += 1
    with pytest.raises(ValueError):
        CalibrationLock.from_json(json.dumps(d))


def test_calib_headers_fixture_matches_lock_and_conventions():
    h = json.loads((REAL / "calib_headers.json").read_text())
    lock = CalibrationLock.load()
    assert set(h) == {e.s3_key for e in lock.entries}
    for key, d in h.items():
        names = [x["extname"] for x in d["hdus"]]
        if d["product"] == "spectral_wcs":
            assert names[1:4] == ["CWAVE", "CBAND", "WCS-WAVE"]
        if d["product"] == "spectral_channels":
            assert names[1] == "CHANNEL_MAP"                                   # F3: HDU 1
        if d["product"] in ("l3_flux_corrections", "solid_angle_pixel_map"):
            assert "IMAGE" in names
        last = d["hdus"][-1]
        assert last["offset"] < d["size"]


def _bootstrap_run(tmp_path, content, md5=None, sha=None, freeze=False):
    key = "qr3/spectral_channels/cal-sch-v2-2026-229/x.fits"
    e = LockEntry("spectral_channels", None, key, "cal-sch-v2-2026-229", len(content),
                  md5 or hashlib.md5(content).hexdigest(), sha)
    lock = CalibrationLock("qr3", [e])

    def handler(req):
        a, b = (int(x) for x in req.headers["Range"].removeprefix("bytes=").split("-"))
        return httpx.Response(206, content=content[a:b + 1], headers={"Content-Range": f"bytes {a}-{b}/{len(content)}"})

    async def go():
        async with make_client(httpx.MockTransport(handler)) as c:
            return await bootstrap(c, lock, tmp_path, freeze=freeze)
    return asyncio.run(go())


def test_bootstrap_verifies_md5_and_sha256(tmp_path):
    content = b"SIMPLE" + bytes(range(256)) * 50
    lock = _bootstrap_run(tmp_path, content, freeze=True)
    assert lock.entries[0].sha256 == hashlib.sha256(content).hexdigest() and lock.complete
    with pytest.raises(CalibIntegrityError):
        _bootstrap_run(tmp_path / "b", content, md5="0" * 32, freeze=True)
    with pytest.raises(CalibIntegrityError):
        _bootstrap_run(tmp_path / "c", content, sha="f" * 64)
    with pytest.raises(CalibIntegrityError):                            # no sha and no freeze
        _bootstrap_run(tmp_path / "d", content)


def test_calib_loader_reads_named_hdus_and_verifies(tmp_path):
    cw = np.linspace(4.4, 5.0, 16).reshape(4, 4).astype(np.float32)
    entries = []
    for prod, det, hdus in (("spectral_wcs", 6, [fits.ImageHDU(cw, name="CWAVE"), fits.ImageHDU(cw / 128, name="CBAND")]),
                            ("spectral_channels", None, [fits.ImageHDU(np.ones((4, 4), np.uint8), name="CHANNEL_MAP")]),
                            ("l3_flux_corrections", 6, [fits.ImageHDU(np.full((4, 4), 1.1, np.float32), name="IMAGE")])):
        b = io.BytesIO()
        fits.HDUList([fits.PrimaryHDU(), *hdus]).writeto(b)
        key = f"qr3/{prod}/v/{det}/f.fits"
        (tmp_path / key).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / key).write_bytes(b.getvalue())
        entries.append(LockEntry(prod, det, key, "v", len(b.getvalue()), hashlib.md5(b.getvalue()).hexdigest(),
                                 hashlib.sha256(b.getvalue()).hexdigest()))
    lock = CalibrationLock("qr3", entries)
    c = Calib(tmp_path, lock)
    assert np.allclose(c.cwave[6], cw) and c.channel.dtype == np.uint8 and float(c.fluxcorr[6][0, 0]) == pytest.approx(1.1)
    (tmp_path / entries[0].s3_key).write_bytes(b"tampered")
    with pytest.raises(CalibIntegrityError):
        Calib(tmp_path, lock)


def test_sliced_calib_supports_parent_slice_lookups():
    cw = np.load(REAL / "cwave_D6_fixture_slice.npy")
    ch = np.load(REAL / "channel_map_fixture_slice.npy")
    c = SlicedCalib((638, 1919), {6: cw}, ch)
    ps = parent_slice((638, 1919), cw.shape)
    assert np.array_equal(c.cwave[6][ps], cw) and np.array_equal(c.channel[ps], ch)
    assert np.isnan(c.cwave[6][0, 0])                                   # outside the window: unknown


def test_watcher_on_real_listings(tmp_path):
    async def go():
        async with replay() as c:
            st = await current_state(c, REG)
            path = tmp_path / "release_state.json"
            ReleaseState(latest={"qr3": "2026W38_1A"}, top_prefixes=["qr2/", "qr3/"]).save(path)
            rep = await check(c, REG, path)
            return st, rep, ReleaseState.load(path)
    st, rep, saved = asyncio.run(go())
    assert st.top_prefixes == ["qr2/", "qr3/"] and st.latest["qr3"] == "2026W40_2A" and st.periods["qr3"] == 22
    assert rep["new_periods"]["qr3"] == ("2026W38_1A", "2026W40_2A") and not rep["dr1_detected"]
    assert saved.latest == st.latest
