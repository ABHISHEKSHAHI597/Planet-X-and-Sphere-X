"""PooledSource, source attribution and the threaded frame cache (decision record 0009)."""
import asyncio

from spherex.access.cache import FrameCache
from spherex.access.failover import CachedSource, PooledSource, fetch_frames
from spherex.access.frames import SERVED_BY, FrameBox, FrameUnavailable, SourceFailure
from spherex.types import FrameRef

BOX = FrameBox(0.0, 0.0, 0.1)


def refs(n, det=6):
    return [FrameRef(f"https://x/{det}/{i}.fits", f"qr3/{det}/level2_{i:04d}_D{det}.fits", "spherex_qr3",
                     f"o{i}", det, 61000.0 + i) for i in range(n)]


class Slow:
    """A source that takes `delay` seconds per frame and records the most frames it ever had in flight."""

    def __init__(self, name, delay, fail=None, sets_served_by=False):
        self.name, self.delay, self.fail, self.sets = name, delay, fail or (lambda ref: None), sets_served_by
        self.calls = self.in_flight = self.peak = 0

    async def fetch(self, ref, box):
        self.calls += 1
        self.in_flight += 1
        self.peak = max(self.peak, self.in_flight)
        try:
            await asyncio.sleep(self.delay)
            e = self.fail(ref)
            if e:
                raise e
        finally:
            self.in_flight -= 1
        if self.sets:
            SERVED_BY.set(self.name)
        return f"{self.name}:{ref.obs_id}"


def test_pool_uses_both_sources_within_capacity_and_favours_the_faster():
    fast, slow = Slow("fast", 0.01), Slow("slow", 0.05)
    pool = PooledSource([fast, slow], capacity=[2, 3], prior_s=[1.0, 1.0])
    outs = asyncio.run(fetch_frames(pool, refs(60), BOX))
    assert all(o.frame is not None for o in outs)
    assert fast.peak <= 2 and slow.peak <= 3                          # per-source capacity respected
    assert fast.calls > 0 and slow.calls > 0                          # throughputs add
    assert fast.calls > slow.calls                                    # routed by measured speed
    assert pool.ewma[0] < pool.ewma[1]
    # attribution is per frame even with many frames in flight on a shared PooledSource
    for o in outs:
        assert o.source == o.frame.split(":")[0]
    st = pool.stats()
    assert st["fast"]["served"] + st["slow"]["served"] == 60 and pool.concurrency == 5


def test_pool_retries_on_the_other_source_and_rests_a_failing_one():
    t = [0.0]
    down = [True]
    bad = Slow("bad", 0.0, lambda r: SourceFailure("503") if down[0] else None)
    good = Slow("good", 0.0)
    pool = PooledSource([bad, good], capacity=[1, 1], prior_s=[0.1, 5.0], clock=lambda: t[0], rest_s=60)
    for r in refs(3):                                                 # bad looks faster, so it is tried first
        assert asyncio.run(pool.fetch(r, BOX)).startswith("good")
    assert bad.calls == 3 and pool.rest_until[0] == 60                # rested after 3 in a row
    asyncio.run(pool.fetch(refs(1)[0], BOX))
    assert bad.calls == 3                                             # not tried while resting
    t[0] = 61
    down[0] = False
    pool.ewma[0] = 0.1
    assert asyncio.run(pool.fetch(refs(1)[0], BOX)).startswith("bad")  # back after the rest


def test_pool_passes_frame_unavailable_through_without_counting_it():
    a = Slow("a", 0.0, lambda r: FrameUnavailable("off the frame"))
    b = Slow("b", 0.0)
    pool = PooledSource([a, b], capacity=[1, 1], prior_s=[0.1, 5.0])
    outs = asyncio.run(fetch_frames(pool, refs(4), BOX))
    assert all(o.frame is None and o.skipped_reason.startswith("unavailable") for o in outs)
    assert b.calls == 0 and pool.fails == [0, 0]                      # not a source failure: no retry, no rest


def test_pool_with_every_source_resting_still_tries_and_reports_the_failure():
    t = [0.0]
    a = Slow("a", 0.0, lambda r: SourceFailure("down a"))
    b = Slow("b", 0.0, lambda r: SourceFailure("down b"))
    pool = PooledSource([a, b], capacity=[1, 1], prior_s=[1.0, 1.0], threshold=1, rest_s=60,
                        clock=lambda: t[0])
    outs = asyncio.run(fetch_frames(pool, refs(3), BOX, concurrency=1))
    assert all(o.frame is None for o in outs)
    assert a.calls == 3 and b.calls == 3                              # resting never means "give up"


def test_served_by_from_inner_source_wins_and_does_not_leak_between_frames():
    a = Slow("inner-a", 0.0, sets_served_by=True)
    pool = PooledSource([a], capacity=[4], prior_s=[1.0])
    plain = Slow("plain", 0.0)
    outs = asyncio.run(fetch_frames(pool, refs(5), BOX))
    assert {o.source for o in outs} == {"inner-a"}
    outs = asyncio.run(fetch_frames(plain, refs(5), BOX))
    assert {o.source for o in outs} == {"plain"}                      # no stale value from earlier fetches


class MemCache:
    """FrameCache stand-in: records the source of each put; put can fail like a full disk."""

    def __init__(self, put_error=None):
        self.store, self.put_error, self.sources = {}, put_error, []

    def get(self, ref, box):
        return self.store.get(ref.id)

    def put(self, ref, box, frame, source=""):
        if self.put_error:
            raise self.put_error
        self.store[ref.id] = frame
        self.sources.append(source)


def test_cached_source_attributes_hits_and_records_the_pool_member():
    cache = MemCache()
    pool = PooledSource([Slow("irsa-cutout", 0.0)], capacity=[2], prior_s=[1.0])
    cs = CachedSource(pool, cache)
    first = asyncio.run(fetch_frames(cs, refs(3), BOX))
    again = asyncio.run(fetch_frames(cs, refs(3), BOX))
    assert {o.source for o in first} == {"irsa-cutout"} and cache.sources == ["irsa-cutout"] * 3
    assert {o.source for o in again} == {"cache"}


def test_cached_source_survives_a_failing_cache_write():
    cs = CachedSource(Slow("s", 0.0), MemCache(put_error=OSError("disk full")))
    outs = asyncio.run(fetch_frames(cs, refs(2), BOX))
    assert all(o.frame is not None for o in outs)


def test_frame_cache_contains_matches_get(tmp_path):
    fc = FrameCache(tmp_path)
    r = refs(1)[0]
    assert not fc.contains(r, BOX) and fc.get(r, BOX) is None
    key_dir = next(tmp_path.iterdir())                                # get() made the shard dir
    from spherex.access.cache import frame_key
    k = frame_key(r.access_url, BOX)
    (key_dir / f"{k}.fits").write_bytes(b"")
    assert not fc.contains(r, BOX)                                    # both files are needed
    (key_dir / f"{k}.json").write_text("{}")
    assert fc.contains(r, BOX)


def test_s3_outside_aws_warns_once(caplog):
    import httpx

    from spherex.access.sources import build_source

    async def go():
        async with httpx.AsyncClient() as c:
            return (build_source("s3", c, in_aws_us_east_1=False), build_source("s3", c, in_aws_us_east_1=True),
                    build_source("auto", c, in_aws_us_east_1=False))
    with caplog.at_level("WARNING", logger="parallax.access"):
        asyncio.run(go())
    warned = [r for r in caplog.records if "FRAMESOURCE=s3 outside AWS" in r.getMessage()]
    assert len(warned) == 1                                           # only the out-of-region s3 build


def _fixture_frame():
    from spherex.access.fixture import FixtureSource
    from tests.real.test_real_access import F2_KEY, fixture_root
    ref = FrameRef("https://irsa/x.fits", F2_KEY, "spherex_qr3", "x", 6, 0.0)
    return asyncio.run(FixtureSource(fixture_root()).fetch(ref, FrameBox(269.4461, 4.7707, 0.05)))


def _trim(f, left, bottom, right, top):
    """The same frame as a source with a 1-px-smaller window would return it (IRSA vs the padded S3 section)."""
    from dataclasses import replace

    import numpy as np

    from spherex.access.fitsio import shift_wcs_header
    ny, nx = f.hdus["IMAGE"][1].shape
    sl = np.s_[bottom:ny - top, left:nx - right]
    hdus = {n: ((shift_wcs_header(h, left, bottom, nx - left - right, ny - bottom - top), a[sl])
                if np.ndim(a) == 2 and a.shape == (ny, nx) else (h, a)) for n, (h, a) in f.hdus.items()}
    return replace(f, hdus=hdus, wcs=f.wcs[sl], origin=(f.origin[0] + left, f.origin[1] + bottom))


def test_canonical_crop_makes_the_window_independent_of_the_source():
    import numpy as np
    from astropy.wcs import WCS
    from astropy.wcs.utils import proj_plane_pixel_scales

    from spherex.access.window import canonical_bounds, canonical_crop
    from spherex.calib import parent_origin

    full = _fixture_frame()
    ny, nx = full.hdus["IMAGE"][1].shape
    ra, dec = (float(v) for v in full.wcs.all_pix2world([[nx / 2, ny / 2]], 0)[0])
    scale = float(np.mean(proj_plane_pixel_scales(full.wcs.celestial)))
    box = FrameBox(ra, dec, (min(nx, ny) - 4) * scale)                 # IRSA's rule ≈ the frame minus a ring
    a = canonical_crop(full, box)
    for trimmed in (_trim(full, 1, 1, 1, 1), _trim(full, 1, 0, 0, 1), _trim(full, 0, 1, 1, 0)):
        b = canonical_crop(trimmed, box)
        assert b.origin == a.origin and canonical_bounds(b, box) == canonical_bounds(a, box)
        for n in ("IMAGE", "FLAGS", "VARIANCE", "ZODI"):
            assert np.array_equal(a.hdus[n][1], b.hdus[n][1], equal_nan=True), n
            assert a.hdus[n][0]["CRPIX1"] == b.hdus[n][0]["CRPIX1"]
    # headers and WCS stay exact: the cutout origin rule and a WCS rebuilt from the header agree with the crop
    assert parent_origin(a.hdus["IMAGE"][0]) == a.origin
    p = np.array([[2.5, 3.5], [20.0, 11.0]])
    assert np.allclose(a.wcs.all_pix2world(p, 0), WCS(a.hdus["IMAGE"][0]).all_pix2world(p, 0), rtol=0, atol=1e-10)
    assert canonical_crop(a, box) is a                                # idempotent
    assert canonical_crop(full, FrameBox(ra + 90, dec, 0.05)) is full  # box off the frame: unchanged


def test_canonical_crop_in_place_matches_the_copying_crop():
    import numpy as np

    from spherex.access.window import canonical_crop
    f = _fixture_frame()
    ny, nx = f.hdus["IMAGE"][1].shape
    ra, dec = (float(v) for v in f.wcs.all_pix2world([[nx / 2, ny / 2]], 0)[0])
    box = FrameBox(ra, dec, 0.04)
    a = canonical_crop(f, box)
    assert f.hdus["IMAGE"][0]["NAXIS1"] == nx                         # the copying crop leaves its input alone
    b = canonical_crop(_fixture_frame(), box, in_place=True)
    assert a.origin == b.origin
    for n in ("IMAGE", "FLAGS", "VARIANCE", "ZODI"):
        assert dict(a.hdus[n][0]) == dict(b.hdus[n][0]) and np.array_equal(a.hdus[n][1], b.hdus[n][1], equal_nan=True)
