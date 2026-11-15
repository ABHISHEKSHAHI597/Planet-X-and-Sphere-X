"""Regressions for the 2026-11-10 audit (audit/03-confirmed-bugs.md). Each test is the repro script of its bug
(audit/repro/), turned into an assertion of the fixed behaviour. Offline: fixtures, recorded or mocked HTTP."""
import asyncio
import time

import httpx
import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.services import Services
from spherex.access.fixture import FixtureSource
from spherex.access.frames import snap_box
from spherex.access.replay import ReplayTransport

from .conftest import BARNARD_PIN, REAL, make_settings, wait_view

EMPTY_VOTABLE = b"""<?xml version="1.0"?><VOTABLE version="1.4" xmlns="http://www.ivoa.net/xml/VOTable/v1.3">
<RESOURCE type="results"><INFO name="QUERY_STATUS" value="OK"/><TABLE><FIELD name="oid" datatype="long"/>
<DATA><TABLEDATA></TABLEDATA></DATA></TABLE></RESOURCE></VOTABLE>"""


@pytest.fixture
def no_backoff(monkeypatch):
    """Retries keep their count but not their sleeps, so outage tests run in milliseconds."""
    import spherex.access.retry as retry

    async def nosleep(_s):
        return None

    monkeypatch.setattr(retry.asyncio, "sleep", nosleep)


def _client(tmp_path, handler, **kw):
    s = make_settings(tmp_path, framesource="auto", **kw)
    return TestClient(create_app(services=Services(s, transport=httpx.MockTransport(handler))),
                      raise_server_exceptions=False)


# ------------------------------------------------------------------------------------------- B-01


def test_b01_unknown_name_is_404_with_a_helpful_message(tmp_path, no_backoff):
    hosts: list[str] = []

    def handler(req: httpx.Request) -> httpx.Response:
        hosts.append(req.url.host)
        if "simbad" in req.url.host:
            return httpx.Response(200, content=EMPTY_VOTABLE)
        if "ssd.jpl.nasa.gov" in req.url.host:
            return httpx.Response(200, json={"result": "No matches found."})
        return httpx.Response(503)

    with _client(tmp_path, handler) as c:
        for q in ("Bernards Star", "asdfgh"):
            for r in (c.post("/api/v1/views", json={"q": q}), c.get("/api/v1/resolve", params={"q": q})):
                assert r.status_code == 404, (q, r.text)
                assert "not found in SIMBAD or JPL Horizons" in r.json()["detail"]
        hosts.clear()
        r = c.post("/api/v1/views", json={"q": "Bernard's star"})       # quote: never sent to Horizons
        assert r.status_code == 404 and "ssd.jpl.nasa.gov" not in hosts
        hosts.clear()
        r = c.post("/api/v1/views", json={"q": "2MASS J12345678+1234567"})   # stellar designation: no Horizons
        assert r.status_code == 404 and "ssd.jpl.nasa.gov" not in hosts


def test_b01_aliases_people_type():
    from spherex.targets import ALIASES

    for q in ("wise0855", "wise0855-0714", "w0855", "barnards", "gj 699"):
        assert q in ALIASES, q


# ------------------------------------------------------------------------------------------- B-03


def test_b03_band_switches_during_a_cold_load_share_the_job_and_never_hit_the_limit(tmp_path):
    class Slow:
        name = "slow-fixture"

        def __init__(self, inner):
            self.inner = inner

        async def fetch(self, ref, box):
            await asyncio.sleep(0.5)
            return await self.inner.fetch(ref, box)

    s = make_settings(tmp_path)
    svc = Services(s, transport=ReplayTransport(REAL / "recorded" / "coverage"), source=Slow(FixtureSource(s.fixture_root)))
    with TestClient(create_app(services=svc)) as c:
        codes, keys = [], set()
        for band in (6, 5, 4, 3, 2, 1, 6, 5, 4):
            r = c.post("/api/v1/views", json={"q": "Barnard's Star", "pin": BARNARD_PIN, "bands": str(band)})
            codes.append(r.status_code)
            keys.add(r.json().get("key"))
        assert set(codes) <= {200, 202}, codes
        assert len(keys - {None}) == 1 and svc.jobs.counters["started"] == 1


# ------------------------------------------------------------------------------------------- B-05


def test_b05_a_shared_pinned_link_works_for_any_view(fixture_client, tmp_path):
    """The Share dialog writes manifest.pin. For a view outside config/pins that pin used to be unknown (404)."""
    from spherex.access.pins import load

    c = fixture_client
    svc = c.app.state.svc
    out = wait_view(c, {"q": "Barnard's Star", "pin": BARNARD_PIN})
    m = out["manifest"]
    # Build the runtime pin of a non-committed frame list (a subset), as planning does for any un-pinned view.
    from app.pipeline import find_pin, runtime_pins_dir, save_runtime_pin
    from spherex.access.pins import Pin

    pin = load(BARNARD_PIN, svc.settings.pins_dir)
    refs = pin.frames[:40]

    class P:
        pinned = False
        key = m["key"]
        params = {"fov": "6", "center": "fixed", "rel": "auto"}
        target = type("T", (), {"main_id": "NAME Barnard's Star", "name": "Barnard's Star"})()
        coverage_query = {"ra": 269.4461, "dec": 4.7707, "radius_deg": 0.001}

    P.refs = refs
    from spherex.access.pins import frame_list_digest

    P.pin = frame_list_digest(f.access_url for f in refs)[:12]
    save_runtime_pin(svc, P)
    assert (runtime_pins_dir(svc) / f"{P.pin}.json").exists()
    assert isinstance(find_pin(svc, P.pin), Pin)
    r = c.post("/api/v1/views", json={"q": "Barnard's Star", "pin": P.pin})
    assert r.status_code in (200, 202), r.text
    assert c.post("/api/v1/views", json={"q": "Barnard's Star", "pin": "0123456789ab"}).status_code == 404


# ------------------------------------------------------------------------------------------- B-06


def test_b06_a_30_arcmin_view_fetches_a_32_not_a_48_arcmin_box():
    side = snap_box(269.45, 4.69, 30).size_deg * 60
    assert side < 47.0, side                              # was 69.4′ (the 48′ preset with its rotation margin)
    assert snap_box(269.45, 4.69, 6).size_deg * 60 == pytest.approx(10.0, abs=0.1)   # small views unchanged


def test_b06_fov_is_capped_at_30_by_default(fixture_client):
    r = fixture_client.post("/api/v1/views", json={"q": "Barnard's Star", "pin": BARNARD_PIN, "fov": "45"})
    assert r.status_code == 400


# ------------------------------------------------------------------------------------------- B-07, B-08, B-10


def test_b07_malformed_paths_are_400_not_500(fixture_client):
    c = fixture_client
    key = wait_view(c, {"q": "Barnard's Star", "pin": BARNARD_PIN})["manifest"]["key"]
    bad = "x" * 70
    for path, params in ((f"/api/v1/views/{bad}/png/V1/6.png", {}),
                         (f"/api/v1/views/{bad}/diff", {"a": "V1", "b": "V3", "band": 6}),
                         ("/api/v1/views/a b/frames", {"band": 6}),
                         ("/api/v1/views/a b/blink25", {}),
                         ("/api/v1/export/csv", {"key": "a b", "band": 6}),
                         (f"/api/v1/views/{key}/cube/V1/abc.f16", {}),
                         (f"/api/v1/views/{key}/png/V1/9.png", {}),
                         (f"/api/v1/views/{key}/diff", {"a": "V 1", "b": "V3", "band": 6})):
        r = c.get(path, params=params)
        assert r.status_code == 400, (path, r.status_code, r.text)
    r = c.post("/api/v1/candidates", json={"ra": 1, "dec": 2, "view_key": "a" * 70, "kind": "mover"})
    assert r.status_code == 422


def test_b08_a_pin_of_another_field_is_refused(fixture_client):
    r = fixture_client.post("/api/v1/views", json={"q": "R Dra", "pin": BARNARD_PIN})
    assert r.status_code == 409 and "another field" in r.json()["detail"]


def test_b10_bin_width_must_be_1_to_365_days(fixture_client):
    for axis in ("bin:0d", "bin:400d"):
        r = fixture_client.post("/api/v1/views", json={"q": "Barnard's Star", "pin": BARNARD_PIN, "axis": axis})
        assert r.status_code == 400, axis


# ------------------------------------------------------------------------------------------- B-09


def test_b09_archive_outage_is_a_clear_503(tmp_path, no_backoff):
    with _client(tmp_path, lambda req: httpx.Response(503, text="Service Unavailable")) as c:
        for r in (c.post("/api/v1/views", json={"ra": "269.4461", "dec": "4.7707"}),
                  c.get("/api/v1/coverage", params={"ra": 269.4461, "dec": 4.7707}),
                  c.get("/api/v1/overlays/gaia", params={"ra": 269.4461, "dec": 4.7707, "mjd": 61000})):
            assert r.status_code == 503, r.text
            # names the service and what it did, not "GaveUp"
            assert "IRSA (NASA's SPHEREx archive) answered HTTP 503" in r.json()["detail"]


# ------------------------------------------------------------------------------------------- K-01


def test_k01_one_failed_probe_does_not_switch_to_the_snapshot(tmp_path):
    from app.main import HEALTH_FAILS_TO_DOWN, health

    snap = tmp_path / "snap"
    (snap / "views").mkdir(parents=True)
    s = make_settings(tmp_path, framesource="auto", snapshot_dir=snap)
    svc = Services(s, transport=httpx.MockTransport(lambda req: httpx.Response(503)))

    async def probe_n(n: int) -> bool:
        for _ in range(n):
            svc.health_cache = None
            await health(svc)
        return svc.irsa_down

    assert asyncio.run(probe_n(1)) is False
    assert asyncio.run(probe_n(HEALTH_FAILS_TO_DOWN - 1)) is True


def test_cached_health_answers_do_not_grow(tmp_path):
    """Found 2026-11-14 in the browser test: every /healthz inside the 60 s cache window appended its snapshot and
    jobs rows to the cached probe list, so the answer grew by two rows per call."""
    from app.main import health

    s = make_settings(tmp_path, framesource="auto")
    svc = Services(s, transport=httpx.MockTransport(lambda req: httpx.Response(200)))

    async def three() -> list[list[str]]:
        return [[p["name"] for p in (await health(svc))["probes"]] for _ in range(3)]

    names = asyncio.run(three())
    assert names[0] == names[1] == names[2] == ["sia2", "s3", "snapshot", "jobs"]


# ------------------------------------------------------------------------------------------- K-16, K-20


def test_k16_view_keys_carry_the_pipeline_version(fixture_client, monkeypatch):
    import app.pipeline as pipeline

    c = fixture_client
    k1 = c.post("/api/v1/views", json={"q": "Barnard's Star", "pin": BARNARD_PIN}).json()["key"]
    monkeypatch.setattr(pipeline, "PIPELINE_VERSION", "test-bump")
    k2 = c.post("/api/v1/views", json={"q": "Barnard's Star", "pin": BARNARD_PIN}).json()["key"]
    assert k1 != k2


def test_k20_solar_system_targets_track_without_being_asked(monkeypatch):
    from types import SimpleNamespace

    from app import pipeline
    from spherex.access.releases import load as load_registry
    from spherex.targets import Target

    async def resolve(svc, params):
        return Target("sso:Pluto", "sso", "Pluto", 10.0, 0.0, extra={"command": "999", "ephemeris": {}})

    seen = {}

    async def frame_list(svc, params, target):
        seen["center"] = params["center"]
        raise pipeline.PlanError("stop here", 418)

    monkeypatch.setattr(pipeline, "resolve_target", resolve)
    monkeypatch.setattr(pipeline, "frame_list", frame_list)
    svc = SimpleNamespace(settings=SimpleNamespace(max_fov_arcmin=30.0), registry=load_registry())
    with pytest.raises(pipeline.PlanError) as e:
        asyncio.run(pipeline.plan_view(svc, {"q": "Pluto"}))
    assert e.value.status == 418 and seen["center"] == "track"


# ------------------------------------------------------------------------------------------- K-39


def test_k39_candidate_report_answers_quickly_without_a_cached_measurement(fixture_client):
    c = fixture_client
    key = wait_view(c, {"q": "Barnard's Star", "pin": BARNARD_PIN})["manifest"]["key"]
    t0 = time.perf_counter()
    r = c.post("/api/v1/candidates", json={"ra": 269.4461, "dec": 4.7707, "view_key": key, "visits": ["V1"],
                                           "kind": "mover"})
    assert r.status_code == 200, r.text
    assert time.perf_counter() - t0 < 30
    check = next(x for x in r.json()["auto_checks"] if x["name"] == "PM significance and colour")
    assert check["passed"] is None


def test_measurements_need_a_view_key(tmp_path):
    s = make_settings(tmp_path)
    svc = Services(s, transport=ReplayTransport(REAL / "recorded" / "coverage"))
    svc.calib_spec = ("locked", "/nonexistent")            # past the calibration refusal, to reach the key check
    with TestClient(create_app(services=svc), raise_server_exceptions=False) as c:
        r = c.get("/api/v1/spectrum", params={"ra": 1, "dec": 1})
        assert r.status_code == 400 and "view key" in r.json()["detail"]


def test_k31_decimal_degrees_with_degree_signs_parse():
    from spherex.targets import parse_coords

    assert parse_coords("269.4461° +4.7707°") == (269.4461, 4.7707)
    assert parse_coords("269.4461°, -4.7707°") == (269.4461, -4.7707)
    assert parse_coords("Barnard's Star") is None


def test_o13_cache_budget_deletes_least_recently_used_and_keeps_demo_views(tmp_path):
    import json
    import os

    from app import cachegc

    s = make_settings(tmp_path)
    svc = Services(s, transport=ReplayTransport(REAL / "recorded" / "coverage"))
    root = s.cache_dir
    for i in range(10):                                 # 10 frames of 1 MB, oldest first
        f = root / "frames" / "ab" / f"f{i}.fits"
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_bytes(b"\0" * (1 << 20))
        os.utime(f, (1000 + i, 1000 + i))
    for key, pin, used in (("demo", BARNARD_PIN, 500), ("old", "0123456789ab", 900), ("new", "0123456789ac", 5000)):
        d = root / "views" / key
        d.mkdir(parents=True)
        (d / "manifest.json").write_text(json.dumps({"pin": pin}))
        (d / "stack.bin").write_bytes(b"\0" * (1 << 20))
        os.utime(d / "manifest.json", (used, used))
    out = cachegc.prune(svc, budget_bytes=8 << 20)
    assert out["total_bytes"] <= int((8 << 20) * cachegc.TARGET_FRACTION)
    assert (root / "views" / "demo").exists()          # a committed demo pin is never evicted
    assert not (root / "views" / "old").exists()       # least recently used goes first
    assert (root / "frames" / "ab" / "f9.fits").exists() and not (root / "frames" / "ab" / "f0.fits").exists()
    assert cachegc.prune(svc, budget_bytes=1 << 40)["deleted_frames"] == 0   # under budget: nothing deleted


def test_k41_vectorised_field_stars_select_exactly_what_the_loop_did():
    from types import SimpleNamespace

    import numpy as np
    from astropy import units as u
    from astropy.coordinates import SkyCoord

    from app.measurement import isolated_field_stars

    rng = np.random.default_rng(3)
    ra0, dec0 = 133.79, -7.24
    cands = [SimpleNamespace(source_id=i, ra=ra0 + rng.uniform(-0.1, 0.1), dec=dec0 + rng.uniform(-0.1, 0.1),
                             ruwe=None if i % 17 == 0 else float(rng.uniform(0.8, 2.0))) for i in range(300)]

    def loop(candidates):                               # the code this replaced, verbatim in logic
        field = []
        for g in candidates:
            c = SkyCoord(g.ra * u.deg, g.dec * u.deg)
            if g.ruwe is None or g.ruwe > 1.5 or c.separation(SkyCoord(ra0 * u.deg, dec0 * u.deg)).arcsec < 20:
                continue
            if any(c.separation(SkyCoord(o.ra * u.deg, o.dec * u.deg)).arcsec < 18 for o in candidates
                   if o.source_id != g.source_id):
                continue
            field.append(g)
            if len(field) >= 8:
                break
        return field

    assert [g.source_id for g in isolated_field_stars(cands, ra0, dec0)] == [g.source_id for g in loop(cands)]
    assert isolated_field_stars([], ra0, dec0) == []
