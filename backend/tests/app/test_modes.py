"""Snapshot/offline mode, security headers, health and metrics, flag gating, candidates and exports
(workflow.md §8.5, §9.6, §13.5; implementation.md §5.3, §8, §9). Fixture-backed: L2 plumbing evidence only."""
import importlib.util
import io
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import create_app
from app.services import Services
from spherex.access.replay import ReplayTransport

from .conftest import BARNARD_PIN, REAL, make_settings, wait_view

REPO = Path(__file__).parents[3]
BODY = {"q": "Barnard's Star", "pin": BARNARD_PIN, "px": "6.15"}


def _load_script(name: str):
    spec = importlib.util.spec_from_file_location(name, REPO / "scripts" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_offline_snapshot_serves_pinned_view_without_network(tmp_path):
    s = make_settings(tmp_path / "live")
    svc = Services(s, transport=ReplayTransport(REAL / "recorded" / "coverage"))
    with TestClient(create_app(services=svc)) as c:
        m = wait_view(c, BODY)["manifest"]
    snap = tmp_path / "snap"
    idx = _load_script("make_snapshot").package(s.cache_dir, snap, [m["key"]])
    assert idx["keys"] == [m["key"]] and idx["pins"][BARNARD_PIN] == m["key"]

    off = make_settings(tmp_path / "offline", environment="snapshot", offline=True, snapshot_dir=snap,
                        framesource="auto")
    assert not off.network
    with TestClient(create_app(settings=off)) as c:
        rel = c.get("/api/v1/releases").json()
        assert rel["snapshot"] is True and rel["environment"] == "snapshot"
        r = c.post("/api/v1/views", json=BODY)
        assert r.status_code == 200, r.text
        mm = r.json()["manifest"]
        assert mm["key"] == m["key"] and mm["data_source"] == "snapshot"
        s6 = next(x for x in mm["stacks"] if x["frame_ids"])
        assert c.get(f"/api/v1/views/{mm['key']}/stack/{s6['bin']}/{s6['band']}.f16").status_code == 200
        assert c.get(f"/api/v1/views/{mm['key']}/png/{s6['bin']}/{s6['band']}.png").status_code == 200
        miss = c.post("/api/v1/views", json={"q": "R Dra"})
        assert miss.status_code == 404 and "snapshot" in miss.json()["detail"]
        assert c.get("/api/v1/resolve", params={"q": "eps Ind B"}).status_code == 200   # offline table
        h = c.get("/healthz").json()
        assert h["mode"] == "snapshot"


def test_security_headers_health_metrics(fixture_client):
    c = fixture_client
    r = c.get("/api/v1/releases")
    assert r.headers["x-frame-options"] == "SAMEORIGIN"
    assert r.headers["x-content-type-options"] == "nosniff"
    e = c.get("/embed")
    assert e.headers["content-security-policy"] == "frame-ancestors *" and "x-frame-options" not in e.headers
    h = c.get("/healthz").json()
    assert h["mode"] == "fixture"
    assert {p["name"] for p in h["probes"]} >= {"snapshot"}
    assert "parallax_" in c.get("/metrics").text


def test_gating_and_upstream_owners(fixture_client):
    c = fixture_client
    rel = c.get("/api/v1/releases").json()
    # 2026-11-08: every built capability is `dev` (local laptop shows it, labelled unvalidated); none is `on`.
    assert rel["environment"] == "local" and rel["features"]["diff"] == "dev" and rel["features"]["spectrum"] == "dev"
    # dev-level measurement routes refuse honestly without the locked calibration (fixture slices only)
    assert c.get("/api/v1/spectrum", params={"ra": 1, "dec": 1}).status_code == 409


def test_staging_hides_dev_capabilities(tmp_path):
    s = make_settings(tmp_path, environment="staging")
    with TestClient(create_app(settings=s)) as c:
        for route in ("spectrum", "astrometry", "lightcurve"):
            assert c.get(f"/api/v1/{route}", params={"ra": 1, "dec": 1}).status_code == 404


def test_production_never_serves_unaccepted_capabilities(tmp_path):
    s = make_settings(tmp_path, environment="production")
    with TestClient(create_app(settings=s)) as c:
        feats = c.get("/api/v1/releases").json()["features"]
        assert set(feats.values()) == {"off"}                     # no gate accepted yet (validation/STATUS.md)
        body = {"ra": 1.0, "dec": 1.0, "view_key": "0" * 24, "kind": "mover"}
        assert c.post("/api/v1/candidates", json=body).status_code == 404


def test_candidates_rate_limit_and_moderation(tmp_path):
    s = make_settings(tmp_path, candidates_per_hour_per_ip=2)
    body = {"ra": 10.0, "dec": 5.0, "view_key": "0" * 24, "visits": ["V1"], "kind": "other",
            "note": "<img onerror=x>"}
    with TestClient(create_app(settings=s)) as c:
        r = c.post("/api/v1/candidates", json=body)
        assert r.status_code == 200, r.text
        names = {x["name"]: x for x in r.json()["auto_checks"]}
        assert names["Seen in ≥ 2 visits?"]["passed"] is False
        assert c.post("/api/v1/candidates", json=body).status_code == 200
        assert c.post("/api/v1/candidates", json=body).status_code == 429
        assert c.get("/api/v1/candidates").status_code == 403                    # gallery is moderated
    with TestClient(create_app(settings=make_settings(tmp_path, environment="local"))) as c:
        assert c.post("/api/v1/candidates", json={**body, "note": "x" * 1001}).status_code == 422
    with TestClient(create_app(settings=make_settings(tmp_path, public_gallery=True))) as c:
        g = c.get("/api/v1/candidates").json()
        assert g["banner"] and g["candidates"][0]["note"] == "<img onerror=x>"   # stored verbatim as text


def test_exports_from_a_built_view(fixture_client):
    c = fixture_client
    m = wait_view(c, BODY)["manifest"]
    s6 = next(x for x in m["stacks"] if x["frame_ids"])
    q = {"key": m["key"], "band": s6["band"], "bins": s6["bin"]}
    for fmt, ctype in (("gif", "image/gif"), ("apng", "image/apng"), ("fits", "application/fits"), ("csv", "text/csv")):
        r = c.get(f"/api/v1/export/{fmt}", params=q)
        assert r.status_code == 200 and r.headers["content-type"].startswith(ctype), (fmt, r.text[:200])
    assert c.get("/api/v1/export/mp4", params=q).status_code == 501
    from astropy.io import fits
    hl = fits.open(io.BytesIO(c.get("/api/v1/export/fits", params=q).content))
    assert any("RA---TAN" in str(h.header.get("CTYPE1", "")) for h in hl)


def test_reproducible_cold_builds(tmp_path):
    """G2 criterion "two cold builds give identical stacks" — here on the committed fixture frames (L2)."""
    out = []
    for i in range(2):
        s = make_settings(tmp_path / f"run{i}")
        svc = Services(s, transport=ReplayTransport(REAL / "recorded" / "coverage"))
        with TestClient(create_app(services=svc)) as c:
            m = wait_view(c, BODY)["manifest"]
            s6 = next(x for x in m["stacks"] if x["frame_ids"])
            out.append((m["key"], c.get(f"/api/v1/views/{m['key']}/stack/{s6['bin']}/{s6['band']}.f16").content,
                        c.get(f"/api/v1/views/{m['key']}/stack/{s6['bin']}/{s6['band']}.f32").content))
    assert out[0] == out[1]
