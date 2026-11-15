"""L0: what still works while IRSA or SIMBAD is down (stale frame lists, stale lookups) and the error that names
the failing service instead of "GaveUp"."""
import asyncio
import json
import types

import httpx
import pytest

from app import pipeline
from app.upstream import describe_upstream
from spherex.access import releases as R
from spherex.access.cache import CoverageCache
from spherex.access.coverage import CoverageClient
from spherex.access.retry import GaveUp
from spherex.targets import Target, UpstreamError

REG = R.load()
IBE = "https://irsa.ipac.caltech.edu/ibe/data/spherex/"


def rows(n=2):
    return [dict(collection="spherex_qr2", obs_id=f"o{i}", band="6", t_min=61000.0 + i,
                 access_url=f"{IBE}qr2/level2/x/{i}.fits", s3_key=f"qr2/level2/x/{i}.fits", service="sia2")
            for i in range(n)]


def irsa_down(status=502):
    return httpx.AsyncClient(transport=httpx.MockTransport(lambda req: httpx.Response(status, text="Proxy Error")))


def key(ra, dec, colls):
    return f"{ra:.5f},{dec:.5f},{0.001:.6f},{'|'.join(colls)}"


def test_get_stale_ignores_age_and_release_and_finds_a_nearby_entry(tmp_path):
    t = [1000.0]
    c = CoverageCache(tmp_path, clock=lambda: t[0])
    c.put(key(217.36754, -62.67359, ["a"]), rows(), "qr3=old")
    t[0] += 30 * 86400
    assert c.get(key(217.36754, -62.67359, ["a"]), "qr3=new") is None          # the normal path still refuses it
    hit = c.get_stale(key(217.36754, -62.67359, ["a"]))
    assert hit is not None and hit[1] == 1000.0 and len(hit[0]) == 2
    assert c.get_stale(key(217.36760, -62.67355, ["a"])) is not None            # the star moved a little
    assert c.get_stale(key(217.5, -62.67359, ["a"])) is None                   # ≈3.7′ away: too far
    assert c.get_stale(key(217.36754, -62.67359, ["b"])) is None               # other collections
    (tmp_path / "junk.json").write_text("{not json")
    assert c.get_stale(key(217.36760, -62.67355, ["a"])) is not None            # a corrupt file is skipped


def test_coverage_uses_the_saved_list_when_sia2_and_tap_both_fail(tmp_path):
    colls = REG.collections()
    cache = CoverageCache(tmp_path)
    cache.put(key(10.0, 20.0, colls), rows(3), "anything")

    async def go():
        async with irsa_down() as client:
            cov = CoverageClient(client, REG, cache=cache, tries=1)
            got = await cov.coverage(10.00001, 20.0, release_state="now")
            return got, cov.last
    got, last = asyncio.run(go())
    assert len(got) == 3 and last["service"] == "stale-cache" and "IRSA is not answering" in last["warning"]


def test_coverage_still_fails_for_a_place_never_opened(tmp_path):
    async def go():
        async with irsa_down() as client:
            await CoverageClient(client, REG, cache=CoverageCache(tmp_path), tries=1).coverage(10.0, 20.0)
    with pytest.raises((GaveUp, httpx.HTTPError, RuntimeError)):
        asyncio.run(go())


def test_cached_resolve_answers_from_the_last_lookup_while_simbad_is_down(tmp_path, monkeypatch):
    svc = types.SimpleNamespace(settings=types.SimpleNamespace(cache_dir=tmp_path))
    answer = Target("Wolf 359", "star", "* CN Leo", 164.1, 7.0, extra={"warning": "Gaia lookup failed"})

    async def ok(q, client):
        return answer

    async def down(q, client):
        raise UpstreamError("SIMBAD is not answering")

    monkeypatch.setattr(pipeline, "resolve_name", ok)
    asyncio.run(pipeline.cached_resolve(svc, "Wolf 359", object()))
    # A degraded answer is not cached as fresh, but it is kept as the last known one.
    files = sorted(p.name for p in (tmp_path / "resolve").iterdir())
    assert len(files) == 1 and files[0].endswith(".last.json")
    monkeypatch.setattr(pipeline, "resolve_name", down)
    t = asyncio.run(pipeline.cached_resolve(svc, "wolf 359", object()))
    assert t.name == "* CN Leo" and t.query == "wolf 359" and "SIMBAD is not answering" in t.extra["warning"]
    with pytest.raises(UpstreamError):
        asyncio.run(pipeline.cached_resolve(svc, "Ross 128", object()))         # never looked up: still an error
    json.loads((tmp_path / "resolve" / files[0]).read_text())                  # the file is plain JSON


def test_describe_upstream_names_the_service():
    req = httpx.Request("GET", "https://irsa.ipac.caltech.edu/SIA")
    e502 = httpx.HTTPStatusError("x", request=req, response=httpx.Response(502, request=req))
    assert describe_upstream(GaveUp(4, e502)) == "IRSA (NASA's SPHEREx archive) answered HTTP 502"
    slow = httpx.ReadTimeout("t", request=httpx.Request("GET", "https://gea.esac.esa.int/tap-server/tap/sync"))
    assert describe_upstream(slow) == "Gaia (ESA) did not answer in time"
    assert describe_upstream(GaveUp(4, EOFError())) is None
    assert describe_upstream(GaveUp(4, None)) is None
