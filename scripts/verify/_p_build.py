"""Shared in-process view builder for P's checks (p_platform.py, p_repro.py). Runs the real FastAPI app with
TestClient, so the evidence exercises exactly the code that serves users: plan → fetch → stack → payloads."""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from fastapi.testclient import TestClient  # noqa: E402

from app.main import create_app  # noqa: E402
from app.services import Services  # noqa: E402
from app.settings import Settings  # noqa: E402

REAL = ROOT / "backend" / "tests" / "data" / "real"


def fixture_services(cache: Path) -> Services:
    from spherex.access.replay import ReplayTransport
    s = Settings(environment="local", framesource="fixture", cache_dir=cache, cpu_workers=0, job_timeout_s=300.0)
    return Services(s, transport=ReplayTransport(REAL / "recorded" / "coverage"))


def live_services(cache: Path, calib_root: Path | None, timeout_s: float = 1800.0) -> Services:
    s = Settings(environment="local", framesource="auto", cache_dir=cache, cpu_workers=0, job_timeout_s=timeout_s,
                 calib_root=calib_root, jobs_per_minute_per_ip=1000)
    return Services(s)


def build(svc: Services, body: dict[str, Any], fetch_payloads: bool = True) -> dict[str, Any]:
    """POST /views, follow SSE to the end, fetch manifest, every stack payload and one PNG. Returns timings,
    events, manifest and {stack-path: bytes}."""
    out: dict[str, Any] = {"events": [], "payloads": {}}
    with TestClient(create_app(services=svc)) as c:
        t0 = time.monotonic()
        r = c.post("/api/v1/views", json=body)
        r.raise_for_status()
        d = r.json()
        first_stack = None
        if d["status"] == "queued":
            with c.stream("GET", f"/api/v1/jobs/{d['job_id']}/events") as s:
                name = None
                for line in s.iter_lines():
                    if line.startswith("event: "):
                        name = line[7:]
                    elif line.startswith("data: ") and name:
                        ev = {"type": name, **json.loads(line[6:])}
                        out["events"].append(ev)
                        if name == "stack_ready" and first_stack is None:
                            first_stack = time.monotonic() - t0
                        if name in ("done", "error"):
                            break
            key = d["key"]
        else:
            key = d["manifest"]["key"]
        out["cold_s"] = time.monotonic() - t0
        out["first_stack_s"] = first_stack
        m = c.get(f"/api/v1/views/{key}/manifest")
        m.raise_for_status()
        out["manifest"] = m.json()
        t1 = time.monotonic()
        again = c.post("/api/v1/views", json=body)
        out["warm_status"] = again.json().get("status")
        out["warm_s"] = time.monotonic() - t1
        if fetch_payloads:
            for st in out["manifest"]["stacks"]:
                if st["ready"] and st["frame_ids"]:
                    for ext in ("f16", "f32"):
                        p = f"/api/v1/views/{key}/stack/{st['bin']}/{st['band']}.{ext}"
                        rr = c.get(p)
                        rr.raise_for_status()
                        out["payloads"][f"{st['bin']}/{st['band']}.{ext}"] = rr.content
            ready = [st for st in out["manifest"]["stacks"] if st["ready"] and st["frame_ids"]]
            if ready:
                st = ready[0]
                png = c.get(f"/api/v1/views/{key}/png/{st['bin']}/{st['band']}.png")
                out["png_status"] = png.status_code
                out["png_bytes"] = len(png.content)
        out["metrics_text"] = c.get("/metrics").text
    return out
