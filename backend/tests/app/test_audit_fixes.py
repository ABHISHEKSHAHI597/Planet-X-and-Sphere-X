"""Regressions from the 2026-11-08 pipeline audit (improvements.md D1, D3)."""
import asyncio
from types import SimpleNamespace

from app import pipeline
from app.settings import REPO
from spherex.access.coverage import CoverageRow
from spherex.access.releases import load as load_registry
from spherex.targets import Target

from .conftest import WISE_PIN, make_settings


def test_view_manifest_carries_epoch_banner_for_challenge_coordinate(fixture_client):
    """D1: the UI reads the banner from the manifest, so POST /views must carry the epoch hint."""
    r = fixture_client.post("/api/v1/views", json={"ra": "08:55:10.831", "dec": "-07:14:42.53", "pin": WISE_PIN})
    assert r.status_code in (200, 202), r.text
    d = r.json()
    key = d.get("key") or d["manifest"]["key"]
    t = fixture_client.get(f"/api/v1/views/{key}/manifest").json()["target"]
    assert t["kind"] == "coords"
    h = t["epoch_hint"]
    assert h is not None and abs(h["epoch"] - 2010.46) < 0.1 and h["direction"] == "west"
    assert 2.0 < h["moved_arcmin"] < 2.4


def test_sso_frame_list_reads_coverage_rows_as_objects(monkeypatch):
    """D3: coverage returns CoverageRow dataclasses; the SSO path used to subscript them (TypeError)."""
    url = "https://irsa.ipac.caltech.edu/ibe/data/spherex/qr3/level2/2026W33_2A/l2b-v27-2026-241/6/" \
          "level2_2026W33_2A_0594_4D6_spx_l2b-v27-2026-241.fits"
    row = CoverageRow("spherex_qr3", "2026W33_2A_0594_4", "D6", 60800.0, url, url.split("spherex/", 1)[1], "sia2")

    class Cov:
        last: dict = {}

        async def coverage(self, *a, **kw):
            return [row]

    async def fake_positions(client, name, times):
        return [(10.0, 0.0) for _ in times]

    monkeypatch.setattr("spherex.external.horizons.positions", fake_positions)
    monkeypatch.setattr(pipeline, "_mjd_now", lambda: 60830.0)
    svc = SimpleNamespace(coverage=Cov(), client=None, registry=load_registry(),
                          settings=SimpleNamespace(offline=False), release_state=lambda: SimpleNamespace(token=lambda: ""))
    t = Target("sso:Pluto", "sso", "Pluto", 10.0, 0.0, extra={"command": "999", "ephemeris": {}})
    frames, *_ = asyncio.run(pipeline.frame_list(svc, {"fov": "6", "rel": "auto"}, t))
    assert [f.access_url for f in frames] == [url]


def test_science_results_are_plain_python():
    """Live spectrum returned HTTP 500: numpy.bool in the result could not be serialised."""
    import numpy as np

    from app.main import _plain

    out = _plain({"a": np.bool_(True), "b": [np.float64(1.5), (np.int64(2),)], "c": np.arange(2)})
    assert out == {"a": True, "b": [1.5, [2]], "c": [0, 1]}
    assert type(out["a"]) is bool and type(out["b"][0]) is float


# ------------------------------------------------------------------- frozen pin targets (optimisation.md IMP-2)


def test_a_pinned_name_uses_its_frozen_target_and_never_asks_the_resolver(tmp_path, monkeypatch):
    """advanced_research.md A2: the same pinned link must give the same view whatever SIMBAD or Gaia answer today."""
    import asyncio
    import json
    from types import SimpleNamespace

    from app import pipeline
    from spherex.targets import identifier

    assert identifier("barnards star") == identifier("  Barnard's   Star ")       # aliases share one frozen entry
    frozen = dict(query="Barnard's Star", kind="star", name="NAME Barnard's star", ra=269.448, dec=4.739, epoch=2016.0,
                  pmra=-801.5, pmdec=10362.4, plx=546.9, rv=-110.5, main_id="NAME Barnard's star", otype="BY*", spt="M4V",
                  astrometry_source="Gaia DR3 4472832130942575872", extra={"k_mag": 4.5})
    (tmp_path / pipeline.FROZEN_TARGETS).write_text(json.dumps({"targets": {"21a7689afc4b": {identifier("Barnard's Star").lower(): frozen}}}))
    svc = SimpleNamespace(settings=SimpleNamespace(pins_dir=tmp_path, network=True, cache_dir=tmp_path), client=object())

    async def resolver_must_not_run(*a, **k):
        raise AssertionError("the resolver was asked for a frozen, pinned target")

    monkeypatch.setattr(pipeline, "cached_resolve", resolver_must_not_run)
    t = asyncio.run(pipeline.resolve_target(svc, {"q": "  barnard's   STAR ", "pin": "21a7689afc4b"}))
    assert t.astrometry_source == "Gaia DR3 4472832130942575872" and t.pmdec == 10362.4 and t.moving
    assert t.query == "  barnard's   STAR "

    # Another pin, no pin, or a missing file: the resolver answers as before.
    seen = []

    async def resolver(svc, q, client):
        seen.append(q)
        return pipeline.Target(q, "star", q, 1.0, 2.0)

    monkeypatch.setattr(pipeline, "cached_resolve", resolver)
    asyncio.run(pipeline.resolve_target(svc, {"q": "Barnard's Star", "pin": "000000000000"}))
    asyncio.run(pipeline.resolve_target(svc, {"q": "Barnard's Star"}))
    (tmp_path / pipeline.FROZEN_TARGETS).unlink()
    asyncio.run(pipeline.resolve_target(svc, {"q": "Barnard's Star", "pin": "21a7689afc4b"}))
    assert len(seen) == 3


def test_every_pinned_demo_target_is_frozen():
    """config/pins/targets.json covers each named, pinned view of config/demo_views.yaml (scripts/freeze_targets.py)."""
    import importlib.util
    from pathlib import Path

    spec = importlib.util.spec_from_file_location("freeze_targets", Path(__file__).parents[3] / "scripts" / "freeze_targets.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert mod.check() == 0


def test_the_wise_layer_has_its_own_capability(tmp_path, monkeypatch):
    """optimisation.md REL-5: AllWISE is drawn as catalogued, never propagated, so it has its own capability
    (`wise_layer`); switching the propagated Gaia/SIMBAD markers (`overlays`) off leaves it on."""
    from fastapi.testclient import TestClient

    from app import science
    from app.main import create_app

    async def fake_overlay(svc, cat, ra, dec, r_deg, mjd):
        return dict(catalogue=cat, mjd=mjd, sources=[], epoch=2010.5)

    monkeypatch.setattr(science, "overlay", fake_overlay)
    features = tmp_path / "features.yaml"
    cfg = __import__("yaml").safe_load((REPO / "config" / "features.yaml").read_text(encoding="utf-8"))
    cfg["flags"]["overlays"]["level"] = "off"
    features.write_text(__import__("yaml").safe_dump(cfg), encoding="utf-8")
    q = {"ra": 133.79, "dec": -7.25, "r": 0.05, "mjd": 61000.0}
    settings = make_settings(tmp_path, environment="staging", mock=True, features_path=features)
    with TestClient(create_app(settings=settings)) as c:
        assert c.get("/api/v1/overlays/gaia", params=q).status_code == 404
        r = c.get("/api/v1/overlays/allwise", params=q)
        assert r.status_code == 200 and r.json()["epoch"] == 2010.5


def test_a_view_built_with_filled_cores_is_never_served_where_filling_is_off(tmp_path):
    """Browser test 2026-11-14: views built on a laptop (bright_fill shown) were served unchanged by a staging host
    (bright_fill off), model-filled cores included, because the view key ignored the capability. Since the
    2026-11-15 release decision bright_fill is `staging` (shown everywhere), so the test pins it to `dev`."""
    from fastapi.testclient import TestClient

    from app.main import create_app
    from app.services import Services
    from spherex.access.replay import ReplayTransport

    from .conftest import BARNARD_PIN, REAL

    features = tmp_path / "features.yaml"
    cfg = __import__("yaml").safe_load((REPO / "config" / "features.yaml").read_text(encoding="utf-8"))
    cfg["flags"]["bright_fill"]["level"] = "dev"
    features.write_text(__import__("yaml").safe_dump(cfg), encoding="utf-8")
    keys = {}
    for env in ("local", "staging"):
        svc = Services(make_settings(tmp_path / env, environment=env, features_path=features),
                       transport=ReplayTransport(REAL / "recorded" / "coverage"))
        with TestClient(create_app(services=svc)) as c:
            keys[env] = c.post("/api/v1/views", json={"q": "Barnard's Star", "pin": BARNARD_PIN}).json()["key"]
    assert keys["local"] != keys["staging"]


def test_the_wise_layer_shows_only_sources_bright_enough_to_see(monkeypatch):
    """Browser test 2026-11-14: all 215 AllWISE sources of a 6' field buried the image. The layer keeps W2 <= 14,
    which still includes WISE 0855 (W2 13.70)."""
    from types import SimpleNamespace

    from app import science
    from spherex.external.allwise import AllwiseSource

    rows = [AllwiseSource("J085510.74-071442.5", 133.79, -7.24, None, 13.70),
            AllwiseSource("faint", 133.80, -7.25, 17.0, 16.2), AllwiseSource("no-w2", 133.81, -7.26, 15.0, None)]

    async def fake_cone(*a, **k):
        return rows

    monkeypatch.setattr(science, "cached_cone", fake_cone)
    svc = SimpleNamespace(client=object(), settings=SimpleNamespace(network=True))
    out = asyncio.run(science.overlay(svc, "allwise", 133.79, -7.24, 0.1, 61000.0))
    assert [s["id"] for s in out["sources"]] == ["WISEA J085510.74-071442.5"] and out["epoch"] == 2010.5
