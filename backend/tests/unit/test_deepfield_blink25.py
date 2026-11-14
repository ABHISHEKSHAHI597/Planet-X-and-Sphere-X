"""L0: deep-field volume and frame caps, per-frame inputs (replayed S3 headers), 25-year-blink planning
helpers and plan construction (recorded catalogue responses)."""
import asyncio
from pathlib import Path

import numpy as np
import pytest

from spherex.access.blink25 import fov_for_jump, linear_pos, plan, sep_arcmin
from spherex.access.deepfield import cap_frames, frame_inputs, is_deep, volume
from spherex.access.http import make_client
from spherex.access.replay import ReplayTransport
from spherex.constants import TEST_TARGETS
from spherex.external.twomass import TwoMassClient
from spherex.external.wise import WiseClient
from spherex.types import FrameRef

REAL = Path(__file__).parents[1] / "data/real"


def fr(i, det=1, coll="spherex_qr2_deep", t=61000.0):
    k = f"qr2/level2/P/x/{det}/level2_2026W12_1A_{i:04d}_1D{det}_spx_l2b-v24-2026-082.fits"
    return FrameRef("https://irsa.ipac.caltech.edu/ibe/data/spherex/" + k, k, coll, f"2026W12_1A_{i:04d}_1", det, t)


def test_volume_and_deep_flags():
    frames = [fr(i, coll="spherex_qr2_deep" if i % 3 else "spherex_qr2", t=61000 + i) for i in range(30)]
    v = volume(frames)
    assert v["frames"] == 30 and v["deep"] == 20 and v["wide"] == 10 and is_deep(frames[1])


def test_cap_frames_is_deterministic_spread_and_reported():
    frames = [fr(i, det=1 + i % 2, t=61000 + i * 0.5) for i in range(40)]
    kept, dropped = cap_frames(frames, lambda f: int((f.t_min - 61000) // 14), cap=5)
    per = {}
    for f in kept:
        b = (int((f.t_min - 61000) // 14), f.detector)
        per[b] = per.get(b, 0) + 1
    assert max(per.values()) <= 5 and len(kept) + len(dropped) == 40
    assert all(r.startswith("cap: 5 frames") for _, r in dropped)
    b0 = sorted(f.t_min for f in kept if f.detector == 1 and f.t_min < 61014)
    assert b0[0] == 61000.0 and b0[-1] >= 61012.0                      # spans the bin, not the first 5
    assert cap_frames(list(reversed(frames)), lambda f: int((f.t_min - 61000) // 14), 5)[0] == kept
    with pytest.raises(ValueError):
        cap_frames(frames, lambda f: 0, 0)


def test_frame_inputs_on_a_real_full_file_header():
    """The F2 Barnard frame's real full-file header (S3 range replay): Barnard's pixel and channel."""
    rec = REAL / "recorded/frame_headers"
    if not (rec / "index.json").exists():
        pytest.skip("frame header recording absent")
    from spherex.access.s3sections import S3SectionSource
    key = "qr3/level2/2026W33_2A/l2b-v27-2026-241/6/level2_2026W33_2A_0594_4D6_spx_l2b-v27-2026-241.fits"
    ref = FrameRef("https://irsa.ipac.caltech.edu/ibe/data/spherex/" + key, key, "spherex_qr3", "2026W33_2A_0594_4", 6, 0.0)

    class Cal:
        channel = np.full((2040, 2040), 7, np.uint8)
        cwave = {6: np.full((2040, 2040), 4.7, np.float32)}

    async def go():
        async with make_client(ReplayTransport(rec)) as c:
            return await frame_inputs(S3SectionSource(c), [ref, ref], 269.4461, 4.7707, Cal())
    rows = asyncio.run(go())
    r = rows[0]
    assert r.on_detector and r.error is None and abs(r.x - 651.67) < 0.05 and abs(r.y - 1932.78) < 0.05
    assert r.channel == 7 and r.cwave_um == pytest.approx(4.7) and r.version == "7.0.5"
    assert r.header["L2DQAFLG"] == "Pass"


def test_blink25_helpers():
    assert fov_for_jump(4.55) == pytest.approx(6.825) and fov_for_jump(0.5) == 3.0
    ra, dec, ep, pmra, pmdec = TEST_TARGETS["Barnard's Star"][:5]
    p = linear_pos(ra, dec, ep, pmra, pmdec)
    assert sep_arcmin(p(2000.405), p(2026.63)) == pytest.approx(10.39 * 26.225 / 60, rel=0.01)


def test_blink25_plan_from_recorded_responses():
    rec = REAL / "recorded/blink25"
    if not (rec / "index.json").exists():
        pytest.skip("blink25 recording absent")
    ra, dec, ep, pmra, pmdec = TEST_TARGETS["WISE 0855-0714"][:5]

    # This transport recording predates spherical M propagation. Replay the
    # original query coordinates exactly; propagation is tested independently
    # above and in test_measurement. Do not relabel these archive responses as
    # results of newly computed queries.
    def recorded_position(year):
        import math
        dt = year - ep
        d = dec + pmdec * dt / 3.6e6
        return (ra + pmra * dt / 3.6e6 / math.cos(math.radians(d))) % 360.0, d

    async def go():
        async with make_client(ReplayTransport(rec)) as c:
            return await plan("wise0855", recorded_position, 2026.63, TwoMassClient(c), WiseClient(c),
                              "linear", k_expected=23.0)
    p = asyncio.run(go())
    assert p.twomass_source is None and p.epochs[0].notes                  # no 2MASS epoch for WISE 0855
    assert any(e.label == "AllWISE W2" and e.images for e in p.epochs)
    assert all(i["url"].endswith("-int-3.fits") for e in p.epochs if e.label.startswith("AllWISE") for i in e.images)
    assert p.fov_arcmin >= 1.5 * 2.19
    assert sum(e.label.startswith("NEOWISE") for e in p.epochs) >= 15
