"""Shared scene PSF, white native noise, north-up grid, fixed spectrum and known parallax.

This is simulated image recovery, not the TNO real-image acceptance experiment.
"""

import numpy as np
import pytest

from spherex.epsf import EPSF
from spherex.planetx import distant_body_offset, infer_distance, link_orphans, shift_and_stack


def test_orphan_queue_excludes_static_and_known_detections_without_fake_matches():
    from spherex.planetx import orphan_rows

    a = dict(id="a", xi=0.0, eta=0.0, mjd=61000.0, s_xi=0.1, s_eta=0.1)
    b = dict(a, id="b", mjd=61001.0, xi=0.02)
    mover = dict(a, id="mover", xi=8.0)
    known = dict(a, id="known", known="Gaia", xi=12.0)
    assert [r["id"] for r in orphan_rows([[a, mover, known], [b]])] == ["mover"]
    assert orphan_rows([[dict(a, s_xi=float("nan"))]]) == []


from .scene import table_epsf


def test_digital_tracking_recovers_native_injected_source_and_variance():
    times = np.arange(61000.0, 61010.0)
    dx, dy = distant_body_offset(times, np.median(times), 133.0, -7.0, 500.0)
    psf = EPSF(dict(XCENTER=[1020], YCENTER=[1020], EPSF=[table_epsf(fwhm_px=1.7)]))
    yy, xx = np.indices((41, 41))
    images = [100 * psf.sample(0, xx - 20 + a / 6.15, yy - 20 - d / 6.15) for a, d in zip(dx, dy, strict=True)]
    stack, variance = shift_and_stack(images, np.ones_like(images), times, 133.0, -7.0, 500.0)
    assert np.unravel_index(np.nanargmax(stack), stack.shape) == (20, 20)
    assert np.nansum(stack) == pytest.approx(100, rel=0.03)
    rng = np.random.default_rng(90125)
    values = [
        shift_and_stack(rng.normal(size=np.shape(images)), np.ones_like(images), times, 133.0, -7.0, 500.0)[0][20, 20]
        for _ in range(2000)
    ]
    assert np.var(values, ddof=1) == pytest.approx(variance[20, 20], rel=0.25)


def test_ambiguous_daily_orphans_do_not_greedily_discard_true_recovery():
    times = np.array([61000.0, 61004.0, 61008.0, 61180.0, 61184.0, 61188.0])
    x, y = distant_body_offset(times, times[0], 133.0, -7.0, 500.0)
    rows = [
        dict(
            id=str(i),
            day=int(t),
            mjd=t,
            xi=a,
            eta=d,
            visit="a" if i < 3 else "b",
            spectrum=[10.0, 20.0, 30.0],
            spectrum_err=[1.0, 1.0, 1.0],
        )
        for i, (t, a, d) in enumerate(zip(times, x, y, strict=True))
    ]
    wrong = dict(rows[1], id="distractor", xi=rows[1]["xi"] + 4)
    chains = link_orphans([wrong, *rows], 133.0, -7.0, distances=[500.0])
    good = next(c["chain"] for c in chains if len(c["chain"]) == 6 and all(r["id"] != "distractor" for r in c["chain"]))
    result = infer_distance(
        [r["mjd"] for r in good], [r["xi"] for r in good], [r["eta"] for r in good], np.full(6, 0.1), 133.0, -7.0
    )
    assert result["distance_au"] == pytest.approx(500.0, rel=0.001)
    assert link_orphans(rows[:3], 133.0, -7.0, distances=[500.0]) == []
    with pytest.raises(ValueError, match="budget"):
        link_orphans([wrong, *rows], 133.0, -7.0, distances=[500.0], max_chains=1)
