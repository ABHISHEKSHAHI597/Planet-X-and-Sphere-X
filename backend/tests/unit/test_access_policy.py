"""L0: dedup and version policy, release registry, pins, caches, failover, retries, release watcher."""
import asyncio
import json

import httpx
import pytest
import yaml

from spherex.access import releases as R
from spherex.access.cache import CoverageCache, FrameCache
from spherex.access.dedup import FileInfo, dedup
from spherex.access.failover import CachedSource, FailoverSource, band_first, fetch_frames
from spherex.access.frames import FrameBox, FrameUnavailable, SourceFailure
from spherex.access.pins import PinError, diff, load, make_pin, pin_of, save
from spherex.access.retry import GaveUp, is_retryable, with_retry
from spherex.access.s3list import parse_page
from spherex.access.watcher import ReleaseState, compare, period_week_start, pp_key
from spherex.types import FrameRef

REG = R.load()
IBE = "https://irsa.ipac.caltech.edu/ibe/data/spherex/"


def row(coll, name, t=61000.0, rel="qr3"):
    key = f"{rel}/level2/2026W33_2A/x/6/{name}"
    return dict(collection=coll, access_url=IBE + key, s3_key=key, obs_id="?", t_min=t)


def test_registry_loads_and_ranks():
    assert REG.collection_priority()["spherex_qr3_deep"] > REG.collection_priority()["spherex_qr2"]
    assert REG.collections()[:2] == ["spherex_qr3", "spherex_qr3_deep"]
    assert "spherex_qr2_deep" in REG.collections()                     # deep included (R Dra)
    assert "spherex_qr2_deep" not in REG.collections(include_deep=False)
    assert REG.is_forbidden("spherex_qr1") and not REG.is_forbidden("spherex_qr2")
    assert REG.release_for_collection("spherex_qr2_deep").photometric_scale == "qr2"


@pytest.mark.parametrize("mut", [
    lambda d: d["releases"][1].update(priority=30),                     # duplicate priority
    lambda d: d["releases"].append(dict(id="qr1", collections=["spherex_qr1"], s3_prefix="qr1/",
                                        pipeline_family="x", photometric_scale="qr2", priority=5)),
    lambda d: d["releases"][0].update(s3_prefix="qr3"),
    lambda d: d.update(include_deep="sometimes"),
    lambda d: d["releases"][1].update(collections=["spherex_qr3"]),
])
def test_registry_rejects_bad_configs(mut):
    d = yaml.safe_load(R.DEFAULT_PATH.read_text())
    mut(d)
    with pytest.raises(R.RegistryError):
        R.parse(d)


def test_filename_parse_retry_and_psffix():
    a = FileInfo.parse("level2_2026W33_2A_0594_4D6_spx_l2b_retry-v27-2026-250.fits")
    assert a and a.retry and a.version == 27 and a.detector == 6 and a.obsid == "2026W33_2A_0594_4"
    b = FileInfo.parse("level2_2025W33_1A_0100_2D3_spx_l2b-v20-2025-300+psffix1.fits")
    assert b and b.psffix and not b.retry and b.proc_date == 2025300
    assert FileInfo.parse("level2_bad.fits") is None


def test_dedup_policy():
    rows = [
        row("spherex_qr2", "level2_2026W12_1A_0311_3D2_spx_l2b-v24-2026-082.fits", rel="qr2"),
        row("spherex_qr3", "level2_2026W12_1A_0311_3D2_spx_l2b-v27-2026-241.fits"),    # QR3 beats QR2
        row("spherex_qr3", "level2_2026W12_1A_0311_3D5_spx_l2b-v27-2026-241.fits"),    # partner: kept
        row("spherex_qr3", "level2_2026W12_1A_0400_1D6_spx_l2b-v27-2026-241.fits"),
        row("spherex_qr3", "level2_2026W12_1A_0400_1D6_spx_l2b_retry-v27-2026-250.fits"),  # newer date
        row("spherex_qr2", "level2_2025W30_1A_0001_1D1_spx_l2b-v20-2025-300.fits", rel="qr2"),
        row("spherex_qr2", "level2_2025W30_1A_0001_1D1_spx_l2b-v20-2025-300+psffix1.fits", rel="qr2"),
        row("spherex_qr2", "level2_2025W30_1A_0002_1D1_spx_l2b-v21-2025-301.fits", rel="qr2"),
        row("spherex_qr2", "level2_2025W30_1A_0002_1D1_spx_l2b-v20-2025-310.fits", rel="qr2"),  # older ver
        row("spherex_dr1", "level2_2025W30_1A_0002_1D1_spx_l2b-v30-2026-320.fits", rel="dr1"),  # unknown
        row("spherex_qr1", "level2_2025W30_1A_0003_1D1_spx_l2b-v10-2025-200.fits", rel="qr1"),  # never_use
        row("spherex_qr3", "weird_name.fits"),
    ]
    res = dedup(rows, REG)
    names = {f.access_url.rsplit("/", 1)[1] for f in res.frames}
    assert names == {
        "level2_2026W12_1A_0311_3D2_spx_l2b-v27-2026-241.fits",
        "level2_2026W12_1A_0311_3D5_spx_l2b-v27-2026-241.fits",
        "level2_2026W12_1A_0400_1D6_spx_l2b_retry-v27-2026-250.fits",
        "level2_2025W30_1A_0001_1D1_spx_l2b-v20-2025-300+psffix1.fits",
        "level2_2025W30_1A_0002_1D1_spx_l2b-v21-2025-301.fits"}
    reasons = sorted(r for _, r in res.skipped)
    assert any("never_use" in r for r in reasons) and any("not in config" in r for r in reasons)
    assert any("unrecognised" in r for r in reasons)
    assert res.n_in == len(rows)
    assert len({(f.obs_id, f.detector) for f in res.frames}) == len(res.frames)


def test_dedup_order_independent_and_sorted():
    rows = [row("spherex_qr3", f"level2_2026W12_1A_{i:04d}_1D{d}_spx_l2b-v27-2026-241.fits", t=61000 + i)
            for i in range(5) for d in (1, 4)]
    a = dedup(rows, REG).frames
    b = dedup(list(reversed(rows)), REG).frames
    assert a == b and [f.t_min for f in a] == sorted(f.t_min for f in a)


def refs(n, det=6, base=0):
    return [FrameRef(IBE + f"qr3/level2/P/x/{det}/level2_2026W12_1A_{base + i:04d}_1D{det}_spx_l2b-v27-2026-241.fits",
                     f"qr3/level2/P/x/{det}/level2_2026W12_1A_{base + i:04d}_1D{det}_spx_l2b-v27-2026-241.fits",
                     "spherex_qr3", f"2026W12_1A_{base + i:04d}_1", det, 61000.0 + i) for i in range(n)]


def test_pins_are_order_free_immutable_and_verified(tmp_path):
    fr = refs(4)
    assert pin_of(fr) == pin_of(list(reversed(fr))) and len(pin_of(fr)) == 12
    p = make_pin(fr, REG, {"target": "x"}, {"note": "test"})
    path = save(p, tmp_path)
    assert load(p.pin, tmp_path).frames == p.frames
    doc = json.loads(path.read_text())
    doc["frames"][0]["access_url"] += "x"
    path.write_text(json.dumps(doc))
    with pytest.raises(PinError):
        load(p.pin, tmp_path)
    with pytest.raises(PinError):
        pin_of(fr + fr[:1])


def test_pin_diff_reports_added_removed_replaced():
    old = refs(3)
    new = refs(2) + refs(1, base=10)
    newer = FrameRef(old[0].access_url.replace("2026-241", "2026-300"), old[0].s3_key, old[0].collection,
                     old[0].obs_id, 6, old[0].t_min)
    d = diff(old, [newer] + new[1:])
    assert not d["same"] and len(d["added"]) == 1 and len(d["removed"]) == 1 and len(d["replaced"]) == 1
    assert diff(old, old)["same"]


def test_coverage_cache_ttl_and_release_state_but_pins_untouched(tmp_path):
    t = [1000.0]
    c = CoverageCache(tmp_path / "cov", clock=lambda: t[0])
    c.put("k", [{"a": 1}], "qr3=2026W40_2A")
    assert c.get("k", "qr3=2026W40_2A") == [{"a": 1}]
    assert c.get("k", "qr3=2026W41_1A") is None                      # watcher moved → stale
    t[0] += 24 * 3600 + 1
    assert c.get("k", "qr3=2026W40_2A") is None                      # 24 h TTL
    p = make_pin(refs(2), REG, {}, {})
    save(p, tmp_path / "pins")
    c.invalidate_all()
    assert load(p.pin, tmp_path / "pins").frames == p.frames         # pinned view unchanged


class FakeSource:
    def __init__(self, name, fail=None):
        self.name, self.fail, self.calls = name, fail or (lambda ref: None), 0

    async def fetch(self, ref, box):
        self.calls += 1
        e = self.fail(ref)
        if e:
            raise e
        return f"{self.name}:{ref.obs_id}"


def test_failover_after_three_and_reprobe():
    t = [0.0]
    down = [True]
    a = FakeSource("s3", lambda r: SourceFailure("503") if down[0] else None)
    b = FakeSource("irsa")
    fo = FailoverSource(a, b, clock=lambda: t[0])
    box = FrameBox(0, 0, 0.1)
    out = [asyncio.run(fo.fetch(r, box)) for r in refs(4)]
    assert all(o.startswith("irsa") for o in out)                    # each failed frame retried on b
    assert fo.active is b and a.calls == 3                           # switched after 3 consecutive
    asyncio.run(fo.fetch(refs(1)[0], box))
    assert a.calls == 3                                              # no probe before 5 min
    t[0] = 301
    down[0] = False
    assert asyncio.run(fo.fetch(refs(1)[0], box)).startswith("s3") and fo.active is a


def test_failover_ignores_unavailable_and_fetch_frames_reports_skips():
    a = FakeSource("s3", lambda r: FrameUnavailable("off") if r.obs_id == "2026W12_1A_0000_1" else None)
    b = FakeSource("irsa", lambda r: SourceFailure("down"))
    fo = FailoverSource(a, b)
    fr = refs(3, det=6) + refs(2, det=3, base=50)
    outs = asyncio.run(fetch_frames(fo, fr, FrameBox(0, 0, 0.1), band=3))
    assert [o.ref.detector for o in outs][:2] == [3, 3]               # band first
    skipped = [o for o in outs if o.frame is None]
    assert len(skipped) == 1 and skipped[0].skipped_reason.startswith("unavailable")
    assert fo.consecutive == 0 and fo.active is a
    assert band_first(fr, None) == fr


def test_cached_source_hits(tmp_path):
    from spherex.access.fixture import FixtureSource
    from tests.real.test_real_access import fixture_root, F2_KEY
    src = FixtureSource(fixture_root())
    ref = refs(1)[0]
    ref = FrameRef(ref.access_url, F2_KEY, "spherex_qr3", "x", 6, 0.0)
    cs = CachedSource(src, FrameCache(tmp_path))
    box = FrameBox(269.4461, 4.7707, 0.05)
    a = asyncio.run(cs.fetch(ref, box))
    b = asyncio.run(cs.fetch(ref, box))
    assert cs.cache.hits == 1 and a.origin == b.origin
    import numpy as np
    for n in ("IMAGE", "FLAGS", "VARIANCE", "ZODI"):
        assert np.array_equal(a.hdus[n][1], b.hdus[n][1], equal_nan=True)


def test_retry_classification_and_giveup():
    req = httpx.Request("GET", "http://x")
    assert is_retryable(httpx.HTTPStatusError("x", request=req, response=httpx.Response(503, request=req)))
    assert is_retryable(httpx.HTTPStatusError("x", request=req, response=httpx.Response(429, request=req)))
    assert not is_retryable(httpx.HTTPStatusError("x", request=req, response=httpx.Response(404, request=req)))
    assert is_retryable(EOFError()) and not is_retryable(KeyError())
    n = [0]

    async def f():
        n[0] += 1
        raise EOFError("short")

    async def nosleep(s):
        pass
    with pytest.raises(GaveUp):
        asyncio.run(with_retry(f, tries=4, sleep=nosleep))
    assert n[0] == 4


def test_planning_period_order_and_watcher_never_adopts():
    ps = ["qr3/level2/2026W40_2A/", "qr3/level2/2026W9_1A/".replace("W9", "W09"), "qr3/level2/2026W40_1B/",
          "qr3/level2/2025W52_2A/"]
    assert [p.split("/")[2] for p in sorted(ps, key=pp_key)] == ["2025W52_2A", "2026W09_1A", "2026W40_1B", "2026W40_2A"]
    old = ReleaseState(latest={"qr3": "2026W40_2A", "qr2": "2026W28_1A"}, top_prefixes=["qr2/", "qr3/"])
    new = ReleaseState(latest={"qr3": "2026W41_1A", "qr2": "2026W28_1A"}, top_prefixes=["dr1/", "qr2/", "qr3/"])
    before = R.DEFAULT_PATH.read_text()
    rep = compare(old, new, REG)
    assert rep["dr1_detected"] and rep["adopted"] == [] and "qr3" in rep["new_periods"]
    assert any("NOT adopted" in e for e in rep["events"])
    assert R.DEFAULT_PATH.read_text() == before
    assert old.token() != new.token()
    assert period_week_start("2026W40_2A").isoformat() == "2026-09-28"


def test_s3_listing_page_parse_and_pagination_token():
    xml = b"""<?xml version="1.0" encoding="UTF-8"?><ListBucketResult xmlns="http://s3.amazonaws.com/doc/2006-03-01/">
    <Name>b</Name><Prefix>qr3/level2/</Prefix><IsTruncated>true</IsTruncated>
    <NextContinuationToken>tok==</NextContinuationToken>
    <CommonPrefixes><Prefix>qr3/level2/2026W30_1B/</Prefix></CommonPrefixes>
    <Contents><Key>a.fits</Key><Size>5</Size><ETag>"abc"</ETag><LastModified>t</LastModified></Contents>
    </ListBucketResult>"""
    p, o, tok = parse_page(xml)
    assert p == ["qr3/level2/2026W30_1B/"] and o[0].etag == "abc" and tok == "tok=="
    with pytest.raises(ValueError):
        parse_page(xml.replace(b"<NextContinuationToken>tok==</NextContinuationToken>", b""))


def test_watcher_first_run_is_a_baseline():
    rep = compare(ReleaseState(), ReleaseState(latest={"qr3": "2026W40_2A"}, top_prefixes=["qr2/", "qr3/", "dr1/"]), REG)
    assert rep["baseline"] and not rep["new_periods"] and rep["adopted"] == []
    assert rep["dr1_detected"] and rep["changed"]                     # a DR1 prefix is never hidden by a baseline
    rep2 = compare(ReleaseState(), ReleaseState(latest={"qr3": "2026W40_2A"}, top_prefixes=["qr2/", "qr3/"]), REG)
    assert rep2["baseline"] and not rep2["changed"]


def test_build_source_defaults_by_region(tmp_path):
    from spherex.access.failover import CachedSource, FailoverSource, PooledSource
    from spherex.access.fixture import FixtureSource
    from spherex.access.sources import build_source

    async def go():
        async with httpx.AsyncClient() as c:
            a = build_source("auto", c, REG, in_aws_us_east_1=True)
            b = build_source("auto", c, REG, in_aws_us_east_1=False)
            d = build_source("irsa", c, REG, failover=False, cache_root=tmp_path)
            return a, b, d
    a, b, d = asyncio.run(go())
    assert isinstance(a, FailoverSource) and a.preferred.name == "s3-section" and a.fallback.name == "irsa-cutout"
    # outside AWS both sources work the queue together (decision record 0009), IRSA within its 4-in-flight policy
    assert isinstance(b, PooledSource) and [x.name for x in b.sources] == ["irsa-cutout", "s3-section"]
    assert b.capacity[0] <= 4 and b.concurrency == sum(b.capacity)
    assert isinstance(d, CachedSource) and d.inner.name == "irsa-cutout"
    assert isinstance(build_source("fixture", fixture_root=tmp_path), FixtureSource)
    with pytest.raises(ValueError):
        build_source("ftp")
