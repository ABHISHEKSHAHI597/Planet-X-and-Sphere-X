"""Load-speed behaviour of a view build (decision record 0009), on the committed fixtures."""
import asyncio
import time
import types

from fastapi.testclient import TestClient

import app.pipeline as P
from app.main import create_app
from app.services import Services
from spherex.access.replay import ReplayTransport

from .conftest import BARNARD_PIN, REAL, make_settings, wait_view


def test_selected_band_is_stacked_and_shown_first(fixture_client):
    out = wait_view(fixture_client, {"q": "Barnard's Star", "pin": BARNARD_PIN, "bands": "3", "px": "6.15"})
    ready = [e["band"] for e in out["events"] if e["type"] == "stack_ready"]
    m = out["manifest"]
    assert len(ready) == len(m["stacks"]) and all(s["ready"] for s in m["stacks"])   # every bin, once
    n3 = sum(1 for s in m["stacks"] if s["band"] == 3)
    assert ready[:n3] == [3] * n3                                     # the band on screen comes first
    assert set(m["limits"]) == {str(b) for b in m["bands"]}


def test_slow_newer_data_check_does_not_hold_up_a_pinned_view(tmp_path, monkeypatch):
    state = {"started": 0, "finished": 0}

    async def slow_coverage(*a, **k):
        state["started"] += 1
        await asyncio.sleep(1.5)                                      # a cold IRSA SIA2 answer: 4-30 s
        state["finished"] += 1
        return []

    monkeypatch.setattr(P, "NEWER_CHECK_S", 0.05)
    svc = Services(make_settings(tmp_path), transport=ReplayTransport(REAL / "recorded" / "coverage"))
    svc.coverage = types.SimpleNamespace(coverage=slow_coverage)
    with TestClient(create_app(services=svc)) as c:
        r = c.post("/api/v1/views", json={"q": "Barnard's Star", "pin": BARNARD_PIN, "bands": "6", "px": "6.15"})
        assert r.status_code == 202, r.text
        assert state == {"started": 1, "finished": 0}                 # answered before the check came back
        out = wait_view(c, {"q": "Barnard's Star", "pin": BARNARD_PIN, "bands": "6", "px": "6.15"})
        codes = {w["code"] for w in out["manifest"].get("warnings", [])}
        assert "newer_check_failed" not in codes                      # a slow check is not a failed one
        t = time.monotonic()
        while not state["finished"] and time.monotonic() - t < 5:     # it still completes in the background
            c.get("/healthz")
            time.sleep(0.05)
        assert state["finished"] == 1
