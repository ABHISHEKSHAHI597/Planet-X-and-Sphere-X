"""End-to-end offline (workflow.md §8.5, §9.5 "End-to-end offline"): POST /views on a real pin → recorded
coverage → FixtureSource (real SPHEREx bytes) → I's calibrate → reproject → stack → manifest → PNG.
Level L2: real files, but only the committed fixture frames; every other frame of the pin must appear as
skipped with a reason (no silent drops). Not evidence about the science targets (that needs L3 pins)."""
import io

import numpy as np
from PIL import Image

from spherex.flags import CANONICAL_BITS
from spherex.render import FORMAT_F16

from .conftest import BARNARD_PIN, wait_view


def test_pinned_barnard_view_end_to_end(fixture_client):
    c = fixture_client
    out = wait_view(c, {"q": "Barnard's Star", "pin": BARNARD_PIN, "bands": "6", "fov": "6", "px": "6.15"})
    ev, m = out["events"], out["manifest"]
    types = [e["type"] for e in ev]
    assert types[0] == "planned" and types[-1] == "done", types
    assert ev[0]["n"] == 359                                     # the whole pin is planned
    assert "stack_ready" in types and "fetched" in types
    first_ready = next(e for e in ev if e["type"] == "stack_ready")
    assert first_ready["band"] == 6                              # band-first planning (§2.3)
    assert m["schema_version"] == "0.1.0" and m["pin"] == BARNARD_PIN and m["data_source"] == "live"
    assert m["formats"]["stack"] == FORMAT_F16 and m["flags"]["bits"] == CANONICAL_BITS
    assert m["bands"] == [1, 2, 3, 4, 5, 6]
    # every frame either stacked or skipped with a reason (workflow.md §11.2)
    stacked = {i for s in m["stacks"] for i in s["frame_ids"]}
    skipped = {i: why for s in m["stacks"] for i, why in s["skipped"]}
    assert stacked | set(skipped) == {f["id"] for f in m["frames"]}
    assert all(why for why in skipped.values())
    assert len(stacked) == 1                                     # the one committed Barnard D6 fixture
    fid = next(iter(stacked))
    assert "2026W33_2A_0594_4D6" in fid
    assert any("no fixture" in w for w in skipped.values())
    f = next(x for x in m["frames"] if x["id"] == fid)
    assert f["skipped"] is None and f["qa"]["FINAST"] == 0 and f["survey"] in (1, 2, 3, 4)
    # shared limits exist for every band; the stack with the frame is ready and decodes
    s = next(x for x in m["stacks"] if fid in x["frame_ids"])
    assert s["ready"] and s["nhits_max"] >= 1 and str(s["band"]) in m["limits"]
    ny, nx = m["grid"]["shape"]
    raw = c.get(f"/api/v1/views/{m['key']}/stack/{s['bin']}/{s['band']}.f16")
    assert raw.status_code == 200 and len(raw.content) == ny * nx * 2
    a = np.frombuffer(raw.content, "<f2")
    assert (a != -65504).sum() > 0.3 * a.size                  # the frame covers most of the 6′ grid
    for ext, nbytes in (("f32", 4), ("var.f32", 4), ("flags.u32", 4)):
        r = c.get(f"/api/v1/views/{m['key']}/stack/{s['bin']}/{s['band']}.{ext}")
        assert r.status_code == 200 and len(r.content) == ny * nx * nbytes, ext
    lim = m["limits"][str(s["band"])]
    png = c.get(f"/api/v1/views/{m['key']}/png/{s['bin']}/{s['band']}.png",
                params={"stretch": "asinh:8", "lim": f"manual:{lim['lo']},{lim['hi']}", "cmap": "gray"})
    assert png.status_code == 200 and png.headers["content-type"] == "image/png"
    im = Image.open(io.BytesIO(png.content))
    assert im.size == (nx, ny)
    # bins carry survey labels from the frames' own headers after the run
    b6 = {b["id"]: b for b in m["bins"]["6"]}
    assert b6[s["bin"]]["label"].startswith(s["bin"] + " · ")
    # a second request is warm: 200 with the same manifest, no new job
    again = c.post("/api/v1/views", json={"q": "barnards star", "pin": BARNARD_PIN, "bands": "3", "px": "6.15"})
    assert again.status_code == 200 and again.json()["manifest"]["key"] == m["key"]


def test_unknown_pin_and_bad_params(fixture_client):
    c = fixture_client
    assert c.post("/api/v1/views", json={"q": "Barnard's Star", "pin": "ffffffffffff"}).status_code == 404
    assert c.post("/api/v1/views", json={"q": "Barnard's Star", "fov": "500"}).status_code == 400
    assert c.post("/api/v1/views", json={"fov": "6"}).status_code == 400
    assert c.post("/api/v1/views", json=[1, 2]).status_code == 400
    assert c.post("/api/v1/views", json={"q": "sso:Pluto"}).status_code == 501
    assert c.get("/api/v1/views/0123456789abcdef01234567/manifest").status_code == 404
    assert c.get("/api/v1/views/..%2f..%2fetc/manifest").status_code in (400, 404)
