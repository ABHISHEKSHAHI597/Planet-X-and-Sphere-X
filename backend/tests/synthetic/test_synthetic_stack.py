"""L1: transient rejection, stacking, significance and detection (implementation.md §10.1, G2).
Scene assumptions: tests/synthetic/scene.py."""
import numpy as np
from astropy.wcs import WCS

from spherex.grid import significance, to_grid
from spherex.movers import detect
from spherex.stack import frame_weight, reject_transients, weighted_stack
from tests.synthetic.scene import Star, sky_mask, steep, visit

SHAPE = (61, 61)


def test_synthetic_reject_transients_moving_point_on_dark_sky():
    rng = np.random.default_rng(1)
    n = 20
    F = rng.normal(size=(n,) + SHAPE)
    V = np.ones_like(F)
    for i in range(n):                                     # asteroid: one pixel per frame, moving
        F[i, 30, 5 + 2 * i] += 20.0
    rej = reject_transients(F, V)
    assert all(rej[i, 30, 5 + 2 * i] for i in range(n))
    assert rej.mean() < 1e-3


def test_synthetic_reject_transients_keeps_skewed_bright_source():
    """A T-dwarf-like source varying ×5 across frames with one bright channel is never clipped."""
    rng = np.random.default_rng(2)
    n = 20
    F = rng.normal(size=(n,) + SHAPE)
    V = np.ones_like(F)
    amp = np.full(n, 20.0)
    amp[7] = 100.0                                         # one bright channel: ×5
    F[:, 30, 30] += amp
    assert not reject_transients(F, V)[:, 30, 30].any()


def test_synthetic_weighted_stack_unbiased_bright_star():
    """Per-frame weights keep a bright star's stacked flux unbiased (< 1%) despite its shot noise."""
    rng = np.random.default_rng(3)
    st = [Star(30, 30, 5000.0, steep(6, 1.0))]
    F, V, _, M = visit(SHAPE, st, 6, rng, nframes=20, gain=5.0)
    sky = sky_mask(SHAPE, st)
    w = [frame_weight(v, sky) for v in V]
    mean, var, nh = weighted_stack(F, V, w, reject_transients(F, V))
    box = np.s_[25:36, 25:36]
    assert abs(np.sum(mean[box]) / np.mean(M, axis=0)[box].sum() - 1) < 0.01
    assert nh.min() == 20


def test_synthetic_cosmic_rays_rejected_on_sky():
    rng = np.random.default_rng(4)
    F, V, _, _ = visit(SHAPE, [], 6, rng, nframes=20, n_cr=30, cr_amp=40.0)
    rej = reject_transients(F, V)
    mean, var, _ = weighted_stack(F, V, np.ones(20), rej)
    sig, k = significance(mean, var, np.ones(SHAPE, bool))
    assert rej.sum() >= 25 and np.nanmax(np.abs(sig)) < 5.5


def _wcs(n, pix_deg, pa180=False):
    w = WCS(naxis=2)
    w.wcs.ctype = ["RA---TAN", "DEC--TAN"]
    w.wcs.crval = [150.0, 10.0]
    w.wcs.crpix = [(n + 1) / 2, (n + 1) / 2]
    s = -1 if pa180 else 1
    w.wcs.cdelt = [-pix_deg * s, pix_deg * s]
    return w


def test_synthetic_significance_unit_sigma_native_and_upsampled():
    rng = np.random.default_rng(5)
    n, pix = 81, 6.15 / 3600
    img, var = rng.normal(size=(n, n)), np.ones((n, n))
    src = _wcs(n, pix)
    for factor in (1, 2):                                  # native and 2× upsampled (3.075″)
        m = n * factor
        a, v = to_grid(img, var, src, _wcs(m, pix / factor), (m, m))
        sky = np.isfinite(a)
        sig, k = significance(a, v, sky)
        ss = sig[sky]
        assert abs(1.4826 * np.median(np.abs(ss - np.median(ss))) - 1) < 0.02
        if factor == 2:
            assert k < 0.95                                # bilinear resampling shrinks raw σ


def test_synthetic_to_grid_undoes_pa180_rotation():
    """An 'F' marker north-east in a PA 180° frame lands north-east on the north-up grid."""
    n, pix = 41, 6.15 / 3600
    img = np.zeros((n, n))
    img[5, n - 1 - 5] = 1.0  # PA 180 frame: row 0 is north and the last column is east → near NE
    a, _ = to_grid(img, np.ones((n, n)), _wcs(n, pix, pa180=True), _wcs(n, pix), (n, n), order="nearest-neighbor")
    y, x = np.unravel_index(np.nanargmax(a), a.shape)
    assert (y, x) == (n - 1 - 5, 5)                        # north-up grid: last row north, column 0 east


def test_synthetic_detect_recovers_injected_source_only():
    rng = np.random.default_rng(6)
    st = [Star(20.3, 40.7, 40.0)]
    F, V, _, _ = visit(SHAPE, st, 6, rng, nframes=20)
    mean, var, _ = weighted_stack(F, V, np.ones(20), np.zeros_like(F, bool))
    sig, _ = significance(mean, var, sky_mask(SHAPE, st))
    cat = detect(sig)
    assert cat.size == 1
    assert abs(cat["x"][0] - 20.3) < 0.3 and abs(cat["y"][0] - 40.7) < 0.3


def test_synthetic_red_sum_catches_cold_dwarf():
    """Each band alone is below 5σ; the band 5+6 red-sum is above it."""
    from spherex.movers import red_sum
    rng = np.random.default_rng(8)
    st = [Star(30, 30, 7.0)]
    stacks = []
    for b in (5, 6):
        F, V, _, _ = visit(SHAPE, st, b, rng, nframes=4)
        stacks += list(weighted_stack(F, V, np.ones(4), np.zeros_like(F, bool))[:2])
    sky = sky_mask(SHAPE, st)
    s5 = significance(stacks[0], stacks[1], sky)[0][30, 30]
    s6 = significance(stacks[2], stacks[3], sky)[0][30, 30]
    m, v = red_sum(*stacks)
    sr = significance(m, v, sky)[0][30, 30]
    assert sr > max(s5, s6) and sr > 5
