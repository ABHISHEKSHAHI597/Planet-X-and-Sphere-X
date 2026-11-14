"""L0 tests of P's platform modules (workflow.md §4.1): view keys (implementation.md §10.1 `view_key`),
parameter canonicalisation, PNG orientation against the contract golden, feature-flag levels, rate limits,
job time-outs and SSE replay, candidate safety, and the frame cap."""
import asyncio
import io
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from app.candidates import clean_note
from app.jobs import JobRegistry, sse
from app.pipeline import apply_cap, request_canonical
from app.ratelimit import RateLimiter
from app.render_png import RenderError, decode_f16, parse_stretch, png_bytes, rgba
from app.settings import FlagSpec, effective_level, load_features
from app.viewkey import ParamError, canonical, normalize, selected_band, view_key
from spherex.access.pins import frame_list_digest
from spherex.access.pins import load as load_pin
from spherex.render import golden_F, to_f16
from spherex.types import FrameRef

REPO = Path(__file__).parents[3]
U = "https://irsa.ipac.caltech.edu/ibe/data/spherex/qr3/level2/2026W33_2A/l2b-v27-2026-241/6/"


def _url(i: int, det: int = 6) -> str:
    return f"{U}level2_2026W33_2A_{i:04d}_4D{det}_spx_l2b-v27-2026-241.fits"


# ---------------------------------------------------------------------------------------------- keys
def test_view_key_frame_list_semantics():
    """§10.1: unchanged when frames elsewhere change, changed when a covering frame is added; pin freezes F."""
    canon = canonical({"target": "NAME Barnard's Star", "fov": "6", "px": "3"})
    here = [_url(i) for i in range(5)]
    k1 = view_key(canon, here)
    assert len(k1) == 24
    assert view_key(canon, list(reversed(here))) == k1                       # order-free (sorted F)
    assert view_key(canon, here + [_url(99)]) != k1                           # a new covering frame
    assert view_key(canonical({"target": "NAME Barnard's Star", "fov": "12", "px": "3"}), here) != k1
    pin = load_pin("21a7689afc4b", REPO / "config" / "pins")                 # pins hash F exactly like D
    urls = [f.access_url for f in pin.frames]
    assert frame_list_digest(urls)[:12] == "21a7689afc4b"
    assert view_key(canon, urls) == view_key(canon, list(urls))               # frozen F → frozen key


def test_normalize_defaults_and_validation():
    p = normalize({"q": "Barnard's Star", "unknown": "x"})
    assert p["fov"] == "6" and p["px"] == "3" and p["axis"] == "auto" and "unknown" not in p
    for bad in ({"q": "x", "fov": "61"}, {"q": "x", "bands": "7"}, {"q": "x", "pin": "XYZ"},
                {"q": "x", "lim": "drop table"}, {"q": "x", "center": "moon"}):
        with pytest.raises(ParamError):
            normalize(bad)
    assert selected_band("3") == 3
    # display-only params don't change the request key
    a = request_canonical(normalize({"q": "Barnard's Star", "bands": "6"}))
    b = request_canonical(normalize({"q": "Barnard's Star", "bands": "3", "partial": "1"}))
    assert a == b


# ----------------------------------------------------------------------------------------------- PNG
def test_png_orientation_against_golden():
    """Contract golden F (row 0 = south): the PNG must show it upright — top row = north."""
    img = decode_f16(to_f16(golden_F(121)), (121, 121))
    px = np.asarray(Image.open(io.BytesIO(png_bytes(img, 0.0, 1.0, "lin", "gray"))).convert("RGBA"))
    assert px.shape == (121, 121, 4)
    flipped = np.flipud(np.where(np.isfinite(img), img, np.nan))
    lum = px[..., 0].astype(float)
    finite = np.isfinite(flipped)
    # brightness ordering of PNG rows equals the data flipped north-up
    assert np.corrcoef(lum[finite], np.clip(flipped[finite], 0, 1))[0, 1] > 0.99
    nod = ~finite
    if nod.any():
        assert tuple(px[nod][0][:3]) == (46, 26, 56)                           # no-data tint


def test_png_rejects_bad_parameters():
    with pytest.raises(RenderError):
        parse_stretch("cubic")
    with pytest.raises(RenderError):
        rgba(np.zeros((2, 2)), 0, 1, "lin", "rainbow")
    assert parse_stretch("asinh:12") == ("asinh", 12.0)


# --------------------------------------------------------------------------------------------- flags
def test_feature_levels_per_environment():
    s = FlagSpec(level="staging", capability="x")
    assert effective_level(s, "local") == "staging" and effective_level(s, "staging") == "staging"
    assert effective_level(s, "production") == "off" and effective_level(s, "snapshot") == "off"
    assert effective_level(FlagSpec(level="dev", capability="x"), "staging") == "off"
    assert effective_level(FlagSpec(level="on", capability="x"), "production") == "on"
    cfg = load_features(REPO / "config" / "features.yaml")
    assert all(f.level != "on" for f in cfg.flags.values())                   # nothing accepted yet
    assert {"F1", "F2", "F3", "F16", "G4a"} <= set(cfg.flags["diff"].requires)
    with pytest.raises(Exception):
        FlagSpec(level="on", capability="x", requires=["X9"])


# ------------------------------------------------------------------------------------- rate, jobs, sse
def test_rate_limiter_window():
    t = [0.0]
    rl = RateLimiter(2, 60.0, clock=lambda: t[0])
    assert rl.allow("a") and rl.allow("a") and not rl.allow("a") and rl.allow("b")
    t[0] = 61.0
    assert rl.allow("a")


def test_job_timeout_dedup_and_replay():
    async def go():
        reg = JobRegistry(timeout_s=0.2)

        async def slow(job):
            job.emit({"type": "planned", "n": 3})
            await asyncio.sleep(5)
        j = reg.start("k1", slow)
        assert reg.start("k1", slow) is j                                     # deduplicated by view key
        await asyncio.sleep(0.5)
        evs = [e async for e in j.stream(heartbeat_s=0.05) if e is not None]
        assert [e["type"] for e in evs] == ["planned", "error"]
        assert "time" in evs[-1]["message"].lower()

        async def ok(job):
            job.emit({"type": "stack_ready", "bin": "V1", "band": 6})
        j2 = reg.start("k2", ok)
        await asyncio.sleep(0.1)
        evs = [e async for e in j2.stream() if e is not None]                  # late subscriber replays
        assert [e["type"] for e in evs] == ["stack_ready", "done"] and evs[-1]["key"] == "k2"
    asyncio.run(go())
    out = sse({"type": "fetched", "i": 1, "n": 2})
    assert out.startswith("event: fetched\ndata: ") and out.endswith("\n\n") and '"i"' in out and "type" not in out
    assert sse(None).startswith(":")


def test_candidate_note_is_plain_text():
    cleaned = clean_note("a\x00b\x1b\n<script>")
    assert "\x00" not in cleaned and "\x1b" not in cleaned and "<script>" in cleaned   # stored as text only
    assert len(clean_note("x" * 5000)) <= 1000


# ------------------------------------------------------------------------------------------------ cap
def test_frame_cap_lists_every_dropped_frame():
    refs = [FrameRef(_url(i, 1 + i % 6), f"k{i}", "spherex_qr3", f"o{i}", 1 + i % 6, 61000.0 + i * 0.01)
            for i in range(700)]
    kept, dropped = apply_cap(refs, "visit", 600)
    assert len(kept) <= 600 and len(kept) + len(dropped) == 700
    assert all(why.startswith("cap") for why in dropped.values())
    assert apply_cap(refs[:10], "visit", 600) == (refs[:10], {})
