"""L0/L2: FITS primitives and both FrameSources against mocked transports, fed with the committed real
29×29 QR3 cutout (tests/data/real/barnard_qr3_d6_29x29_hdu0-4.fits, 89,280 B = HDUs 0–4)."""
import asyncio
import hashlib
from pathlib import Path

import httpx
import numpy as np
import pytest
from astropy.io import fits

from spherex.access.fitsio import (BLOCK, CorruptResponse, data_bytes, decode_hdu, decode_image, padded,
                                   shift_wcs_header)
from spherex.access.fitsstream import IrsaCutoutSource, read_hdus
from spherex.access.frames import FrameBox, FrameUnavailable, SourceFailure, cutout_size_deg, snap_box
from spherex.access.http import HostLimiter, make_client
from spherex.access.s3sections import RangeReader, S3SectionSource, irsa_bounds
from spherex.calib import parent_origin
from spherex.types import FrameRef

REAL = Path(__file__).parents[1] / "data/real"
CUT = REAL / "barnard_qr3_d6_29x29_hdu0-4.fits"
KEY = "qr3/level2/2026W33_2A/l2b-v27-2026-241/6/level2_2026W33_2A_0594_4D6_spx_l2b-v27-2026-241.fits"
REF = FrameRef("https://irsa.ipac.caltech.edu/ibe/data/spherex/" + KEY, KEY, "spherex_qr3", "2026W33_2A_0594_4", 6, 61268.0)


def run(c):
    return asyncio.run(c)


async def _chunks(b, n=7001):
    for i in range(0, len(b), n):
        yield b[i:i + n]


def test_data_bytes_is_fits_standard():
    h = fits.Header({"NAXIS": 2, "BITPIX": -32, "NAXIS1": 29, "NAXIS2": 29})
    assert data_bytes(h) == 29 * 29 * 4
    t = fits.Header({"NAXIS": 2, "BITPIX": 8, "NAXIS1": 8, "NAXIS2": 2040, "PCOUNT": 1000, "GCOUNT": 1})
    assert data_bytes(t) == 8 * 2040 + 1000                       # PCOUNT (heap) included
    assert data_bytes(fits.Header({"NAXIS": 0, "BITPIX": 8})) == 0
    assert padded(1) == BLOCK and padded(BLOCK) == BLOCK


def test_decode_keeps_integers_and_applies_bzero():
    h = fits.Header({"NAXIS": 1, "BITPIX": 32, "NAXIS1": 3, "BZERO": 2147483648})
    raw = np.array([0, -1, 5], ">i4").tobytes()
    a = decode_image(h, raw)
    assert a.dtype == np.int64 and a.tolist() == [2147483648, 2147483647, 2147483653]
    f = decode_image(fits.Header({"NAXIS": 1, "BITPIX": -32, "NAXIS1": 2}), np.array([1.5, np.nan], ">f4").tobytes())
    assert f.dtype == np.float32 and f.dtype.byteorder in "=<|"


def test_stream_parse_matches_astropy_and_stops_before_epsf():
    raw = CUT.read_bytes()
    poison = b"X" * BLOCK                                          # bytes after ZODI must never be read

    async def gen():
        async for c in _chunks(raw):
            yield c
        raise AssertionError("reader consumed bytes past ZODI")
        yield poison
    hdus, prim, n = run(read_hdus(gen()))
    assert n == 89_280 < 120_000
    with fits.open(CUT) as hl:
        for name in ("IMAGE", "FLAGS", "VARIANCE", "ZODI"):
            assert np.array_equal(hdus[name][1], hl[name].data, equal_nan=True)
            assert hdus[name][0]["NAXIS1"] == 29
    assert hdus["FLAGS"][1].dtype == np.int64
    assert prim["VERSION"].strip() == "7.0.5"


def test_truncated_stream_raises_eof_and_html_raises_corrupt():
    raw = CUT.read_bytes()
    with pytest.raises(EOFError):
        run(read_hdus(_chunks(raw[:60_000])))
    with pytest.raises(CorruptResponse):
        run(read_hdus(_chunks(b"<html>503 Service Unavailable</html>" + b" " * 3000)))


def _cutout_transport(script):
    """script: list of callables(request) -> httpx.Response, consumed in order."""
    calls = []

    def handler(req):
        calls.append(str(req.url))
        return script[min(len(calls) - 1, len(script) - 1)](req)
    return httpx.MockTransport(handler), calls


def test_cutout_source_retries_truncation_and_503_then_succeeds():
    raw = CUT.read_bytes() + b"\0" * (3 * BLOCK)                   # pretend EPSF follows
    script = [lambda r: httpx.Response(503),
              lambda r: httpx.Response(200, content=raw[:40_000]),  # truncated after 200
              lambda r: httpx.Response(200, content=raw)]
    tr, calls = _cutout_transport(script)

    async def go():
        async with make_client(tr) as c:
            src = IrsaCutoutSource(c, tries=4)
            import spherex.access.retry as rt
            orig = rt.backoff
            rt.backoff = lambda k, cap=30.0, rng=None: 0.0
            try:
                return await src.fetch(REF, FrameBox(269.4461, 4.7707, 0.05)), src
            finally:
                rt.backoff = orig
    f, src = run(go())
    assert len(calls) == 3 and "center=269.4461000,4.7707000deg&size=0.05000" in calls[0]
    assert f.origin == (638, 1919) == parent_origin(f.hdus["IMAGE"][0])
    assert f.release == "qr3" and src.stats.failures == 2


def test_cutout_source_4xx_is_unavailable_and_exhaustion_is_source_failure():
    tr, _ = _cutout_transport([lambda r: httpx.Response(404)])

    async def go(t, tries=2):
        async with make_client(t) as c:
            import spherex.access.retry as rt
            rt_b = rt.backoff
            rt.backoff = lambda k, cap=30.0, rng=None: 0.0
            try:
                return await IrsaCutoutSource(c, tries=tries).fetch(REF, FrameBox(1, 1, 0.05))
            finally:
                rt.backoff = rt_b
    with pytest.raises(FrameUnavailable):
        run(go(tr))
    tr2, calls = _cutout_transport([lambda r: httpx.Response(503)])
    with pytest.raises(SourceFailure):
        run(go(tr2, tries=3))
    assert len(calls) == 3


def test_shift_wcs_header_keeps_world_coordinates_and_origin_rule():
    with fits.open(CUT) as hl:
        h = hl["IMAGE"].header
    from astropy.wcs import WCS
    sub = shift_wcs_header(h, 5, 7, 10, 12)
    w0, w1 = WCS(h), WCS(sub)
    a = w0.all_pix2world([[5 + 3, 7 + 4]], 0)
    b = w1.all_pix2world([[3, 4]], 0)
    assert np.allclose(a, b, atol=1e-10)
    assert parent_origin(sub) == (638 + 5, 1919 + 7)


def test_cutout_size_and_snapping():
    assert cutout_size_deg(6.0) == pytest.approx((6 * 2 ** 0.5 + 8 * 6.15 / 60) / 60)
    a, b = snap_box(269.4461, 4.7707, 5.0), snap_box(269.4462, 4.7708, 6.0)
    assert a == b                                                  # small pans reuse the same cutout
    assert snap_box(10, 0, 7).size_deg == cutout_size_deg(12.5)
    c = snap_box(359.99999, 0.0, 3)
    assert 0 <= c.ra < 360


def _full_file_bytes():
    """A synthetic full-size L2-like file built from the real fixture's headers: IMAGE/VARIANCE/ZODI as
    plain 64×64 images and FLAGS as a one-row-tile RICE_1 table (the real full-file layout, F1)."""
    rng = np.random.default_rng(3)
    with fits.open(CUT) as hl:
        hi = hl["IMAGE"].header.copy()
    hi["CRPIX1A"], hi["CRPIX2A"] = 1.0, 1.0
    hi["CRPIX1W"], hi["CRPIX2W"] = 1, 1
    hi["CRPIX1"] += 638
    hi["CRPIX2"] += 1919
    img = rng.normal(size=(64, 64)).astype(np.float32)
    flg = rng.integers(0, 2 ** 31 - 1, size=(64, 64)).astype(np.int32)
    prim = fits.PrimaryHDU()
    prim.header["VERSION"] = "7.0.5"
    hl = fits.HDUList([prim, fits.ImageHDU(img, header=hi, name="IMAGE"),
                       fits.CompImageHDU(flg, name="FLAGS", compression_type="RICE_1", tile_shape=(1, 64)),
                       fits.ImageHDU(img * 2, name="VARIANCE"), fits.ImageHDU(img * 3, name="ZODI")])
    import io
    buf = io.BytesIO()
    hl.writeto(buf)
    return buf.getvalue(), img, flg


def _range_transport(blob, log):
    def handler(req):
        rng = req.headers.get("Range")
        if not rng:
            return httpx.Response(200, content=blob)
        a, b = (int(x) for x in rng.removeprefix("bytes=").split("-"))
        log.append((a, b))
        b = min(b, len(blob) - 1)
        return httpx.Response(206, content=blob[a:b + 1], headers={"Content-Range": f"bytes {a}-{b}/{len(blob)}"})
    return httpx.MockTransport(handler)


def test_s3_section_reads_rows_and_compressed_flags():
    blob, img, flg = _full_file_bytes()
    log = []

    async def go():
        async with make_client(_range_transport(blob, log)) as c:
            src = S3SectionSource(c)
            return await src.fetch_pixels(REF, 10, 30, 20, 41), src
    f, src = run(go())
    assert f.origin == (10, 20) == parent_origin(f.hdus["IMAGE"][0])
    assert np.array_equal(f.hdus["IMAGE"][1], img[20:41, 10:30])
    assert np.array_equal(f.hdus["FLAGS"][1], flg[20:41, 10:30]) and f.hdus["FLAGS"][1].dtype == np.int64
    assert np.array_equal(f.hdus["ZODI"][1], img[20:41, 10:30] * 3)
    assert f.hdus["FLAGS"][0]["NAXIS1"] == 20 and "ZCMPTYPE" not in f.hdus["FLAGS"][0]
    assert all(b - a + 1 < len(blob) for a, b in log)              # never the whole file


def test_range_reader_refuses_ignored_range_and_short_body():
    blob = b"x" * 10_000

    async def go(handler, tries=1):
        async with make_client(httpx.MockTransport(handler)) as c:
            from spherex.access.http import TransferStats
            return await RangeReader(c, HostLimiter(), TransferStats(), tries=tries).get("k", 0, 100)
    with pytest.raises(Exception) as e:
        run(go(lambda r: httpx.Response(200, content=blob)))
    assert "206" in str(e.value) or "gave up" in str(e.value)
    with pytest.raises(Exception):
        run(go(lambda r: httpx.Response(206, content=blob[:50], headers={"Content-Range": "bytes 0-99/10000"})))
    assert run(go(lambda r: httpx.Response(206, content=blob[:100],
                                           headers={"Content-Range": "bytes 0-99/10000"}))) == blob[:100]


def test_irsa_bounds_rule_reproduces_the_fixture_cutout_box():
    """The committed cutout came from center=269.4461,4.7707 size=0.05 and starts at parent (638, 1919)."""
    with fits.open(CUT) as hl:
        h = hl["IMAGE"].header.copy()
    full = h.copy()
    for k, o in (("CRPIX1", 638), ("CRPIX2", 1919)):
        full[k] = h[k] + o
    full["NAXIS1"] = full["NAXIS2"] = 2040
    assert irsa_bounds(full, FrameBox(269.4461, 4.7707, 0.05)) == (638, 667, 1919, 1948)


def test_decode_hdu_handles_compressed_table_whole():
    blob, img, flg = _full_file_bytes()
    with fits.open(__import__("io").BytesIO(blob), disable_image_compression=True) as hl:
        h = hl["FLAGS"].header
        raw = blob[hl["FLAGS"]._data_offset:hl["FLAGS"]._data_offset + data_bytes(h)]
    ih, a = decode_hdu(h, raw)
    assert np.array_equal(a, flg) and ih["NAXIS1"] == 64


def test_fixture_hash_is_the_committed_one():
    assert hashlib.sha256(CUT.read_bytes()).hexdigest() == \
        "cfd160e4830aca985e556017b9ed7abad074d5f0f4f3e53a1fca6e9ebb0af653"
