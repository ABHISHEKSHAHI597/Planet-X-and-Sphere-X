"""Fixtures for P's API tests. Three modes (workflow.md §8.5): fixture-backed real pipeline (committed real
SPHEREx bytes + recorded archive responses, no network), MOCK=1, and snapshot/offline."""
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.services import Services
from app.settings import Settings
from spherex.access.replay import ReplayTransport

REAL = Path(__file__).parents[1] / "data" / "real"
BARNARD_PIN = "21a7689afc4b"
WISE_PIN = "325c57328320"


def make_settings(tmp: Path, **kw) -> Settings:
    base = dict(environment="local", framesource="fixture", cache_dir=tmp / "cache", cpu_workers=0,
                job_timeout_s=120.0)
    base.update(kw)
    return Settings(**base)


@pytest.fixture
def fixture_client(tmp_path):
    """Real pipeline on committed fixtures; coverage answered from D's recorded SIA2 responses."""
    s = make_settings(tmp_path)
    svc = Services(s, transport=ReplayTransport(REAL / "recorded" / "coverage"))
    with TestClient(create_app(services=svc)) as c:
        yield c


@pytest.fixture
def mock_client(tmp_path):
    s = make_settings(tmp_path, environment="mock", mock=True, framesource="auto")
    with TestClient(create_app(settings=s)) as c:
        yield c


def wait_view(c: TestClient, body: dict, timeout_s: float = 120.0) -> dict:
    """POST /views, follow the SSE stream to the end, return (events, manifest)."""
    r = c.post("/api/v1/views", json=body)
    assert r.status_code in (200, 202), r.text
    d = r.json()
    if d["status"] == "ready":
        return {"events": [], "manifest": d["manifest"], "first": d}
    events = []
    with c.stream("GET", f"/api/v1/jobs/{d['job_id']}/events") as s:
        name = None
        for line in s.iter_lines():
            if line.startswith("event: "):
                name = line[7:]
            elif line.startswith("data: ") and name:
                import json
                events.append({"type": name, **json.loads(line[6:])})
                if name in ("done", "error"):
                    break
    m = c.get(f"/api/v1/views/{d['key']}/manifest")
    assert m.status_code == 200, m.text
    return {"events": events, "manifest": m.json(), "first": d}
