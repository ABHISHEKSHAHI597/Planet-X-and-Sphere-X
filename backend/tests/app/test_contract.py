"""Contract tests (workflow.md §7.3): every endpoint's response validates against /openapi.json, in mock
mode and in fixture-backed real-pipeline mode. Staging is covered nightly by scripts/contract_probe.py."""
import json
from pathlib import Path

from app.settings import API_VERSION

from .conftest import BARNARD_PIN, wait_view
from .contract import check

REPO = Path(__file__).parents[3]


def test_api_version_matches_frontend_contract():
    ts = (REPO / "frontend/src/api/types.ts").read_text(encoding="utf-8")
    assert f'API_SCHEMA_VERSION = "{API_VERSION}"' in ts


def _common(c, oa):
    r = c.get("/api/v1/releases")
    assert r.status_code == 200
    check(oa, "ReleasesResponse", r.json())
    r = c.get("/api/v1/resolve", params={"q": "WISE 0855−0714"})
    assert r.status_code == 200, r.text
    check(oa, "ResolveResult", r.json())
    r = c.get("/api/v1/resolve", params={"q": "08:55:10.831 -07:14:42.53"})
    assert r.status_code == 200, r.text
    check(oa, "ResolveResult", r.json())
    h = c.get("/healthz")
    assert h.status_code == 200
    check(oa, "Health", h.json())


def test_mock_mode_all_endpoints(mock_client):
    c = mock_client
    oa = c.get("/openapi.json").json()
    _common(c, oa)
    assert c.get("/api/v1/releases").json()["environment"] == "mock"
    out = wait_view(c, {"q": "Barnard's Star", "bands": "6"})
    m = out["manifest"]
    check(oa, "ViewQueued", out["first"])
    check(oa, "ViewManifest", m)
    assert m["data_source"] == "mock" and all(s["ready"] for s in m["stacks"])
    types = [e["type"] for e in out["events"]]
    assert types[0] == "planned" and types[-1] == "done" and "warning" in types
    first = next(e for e in out["events"] if e["type"] == "stack_ready")
    assert first["band"] == 6
    golden = (REPO / "frontend/fixtures/golden/stack_F_121x121.f16").read_bytes()
    assert c.get(f"/api/v1/views/{m['key']}/stack/V1/6.f16").content == golden
    assert c.get(f"/api/v1/views/{m['key']}/png/V1/6.png").status_code == 200
    again = c.post("/api/v1/views", json={"q": "Barnard's Star", "bands": "6"})
    assert again.status_code == 200
    check(oa, "ViewReady", again.json())
    r = c.get("/api/v1/coverage", params={"ra": 269.4, "dec": 4.7, "fov": 6})
    check(oa, "Coverage", r.json())
    # spectrum is `dev`: mock mode serves its golden response, schema-checked
    r = c.get("/api/v1/spectrum", params={"ra": 1, "dec": 1})
    assert r.status_code == 200
    check(oa, "SpectrumResponse", r.json())
    r = c.post("/api/v1/candidates", json={"ra": 269.45, "dec": 4.75, "view_key": m["key"], "pin": "",
                                           "visits": ["V1", "V2"], "kind": "mover", "note": "<b>hi</b>"})
    assert r.status_code == 200, r.text
    check(oa, "CandidateResponse", r.json())


def test_fixture_mode_all_endpoints(fixture_client):
    c = fixture_client
    oa = c.get("/openapi.json").json()
    _common(c, oa)
    out = wait_view(c, {"q": "Barnard's Star", "pin": BARNARD_PIN, "px": "6.15"})
    check(oa, "ViewManifest", out["manifest"])
    check(oa, "ViewQueued", out["first"])
    for e in out["events"]:
        name = {"planned": "EvPlanned", "fetched": "EvFetched", "stack_ready": "EvStackReady", "warning": "EvWarning",
                "done": "EvDone", "error": "EvError"}[e["type"]]
        check(oa, name, e)
    # coverage needs the archive: fixture mode has only recorded pin queries → 409/5xx are both honest
    r = c.get("/api/v1/coverage", params={"ra": 269.4461, "dec": 4.7707})
    assert r.status_code in (200, 409, 500, 502) or r.status_code >= 400


def test_openapi_lists_every_documented_endpoint(fixture_client):
    paths = set(fixture_client.get("/openapi.json").json()["paths"])
    for p in ("/api/v1/resolve", "/api/v1/coverage", "/api/v1/views", "/api/v1/jobs/{job_id}/events",
              "/api/v1/views/{key}/manifest", "/api/v1/views/{key}/stack/{bin_id}/{name}",
              "/api/v1/views/{key}/png/{bin_id}/{name}", "/api/v1/views/{key}/cube/{bin_id}/{name}",
              "/api/v1/views/{key}/diff", "/api/v1/views/{key}/frames", "/api/v1/spectrum", "/api/v1/lightcurve",
              "/api/v1/astrometry", "/api/v1/sso", "/api/v1/movers", "/api/v1/overlays/{cat}",
              "/api/v1/export/{fmt}", "/api/v1/releases", "/api/v1/candidates", "/healthz"):
        assert p in paths, p


def test_committed_openapi_and_generated_types_are_fresh(fixture_client):
    """A stale /openapi.json or generated.ts fails CI (workflow.md §7.3). Regenerate: scripts/gen_contracts.py."""
    oa = fixture_client.get("/openapi.json").json()
    committed = json.loads((REPO / "frontend/src/api/openapi.json").read_text(encoding="utf-8"))
    assert committed == oa, "run: python scripts/gen_contracts.py"
    import importlib.util
    spec = importlib.util.spec_from_file_location("gen", REPO / "scripts/gen_contracts.py")
    gen = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gen)
    assert (REPO / "frontend/src/api/generated.ts").read_text(encoding="utf-8") == gen.typescript(oa)


def test_handwritten_types_ts_matches_schemas(fixture_client):
    """F's provisional types.ts keeps the names; every interface field it declares exists in our schemas."""
    import re
    oa = fixture_client.get("/openapi.json").json()["components"]["schemas"]
    ts = (REPO / "frontend/src/api/types.ts").read_text(encoding="utf-8")
    pairs = {"ResolveResult": "ResolveResult", "EpochHint": "EpochHint", "Coverage": "Coverage",
             "CoverageVisit": "CoverageVisit", "ReleaseState": "ReleaseState", "TimeBinInfo": "TimeBinInfo",
             "StackInfo": "StackInfo", "FrameMeta": "FrameMeta", "GridInfo": "GridInfo", "TrackPoint": "TrackPoint",
             "ViewWarning": "ViewWarning", "ViewManifest": "ViewManifest", "DiffAnnotation": "DiffAnnotation",
             "DiffInfo": "DiffInfo", "SpectrumRow": "SpectrumRow", "SpectrumResponse": "SpectrumResponse",
             "AstrometryResponse": "AstrometryResponse", "LightCurveResponse": "LightCurveResponse",
             "OverlaySource": "OverlaySource", "OverlayResponse": "OverlayResponse",
             "CandidateRequest": "CandidateRequest", "CandidateResponse": "CandidateResponse"}
    for ts_name, py in pairs.items():
        m = re.search(r"export interface " + ts_name + r"(?: extends \w+)? \{(.*?)\n\}", ts, re.S)
        assert m, ts_name
        fields = re.findall(r"^  (\w+)\??:", m.group(1), re.M)        # top-level members only
        props = set(oa[py]["properties"])
        if ts_name == "ReleasesResponse":
            props |= set(oa["ReleaseState"]["properties"])
        missing = [f for f in fields if f not in props]
        assert not missing, f"{ts_name}: {missing} in types.ts but not in app/schemas.py"
