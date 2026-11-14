"""sky_noise_scale (spherex.preprocess). L1. Assumptions: Gaussian sky noise with a known true σ, a VARIANCE plane
that understates it by a known factor, bright stars and a few hot pixels inside the sky mask's holes or not."""
import numpy as np

from spherex.preprocess import sky_noise_scale


def scene(factor, seed=0, n=128):
    rng = np.random.default_rng(seed)
    var = np.full((n, n), 4.0)
    sci = 10.0 + rng.normal(0, 2.0 * factor, (n, n))
    sky = np.ones((n, n), bool)
    yy, xx = np.indices((n, n))
    for x, y in [(20, 30), (90, 100), (64, 64)]:
        star = 5000 * np.exp(-((xx - x) ** 2 + (yy - y) ** 2) / 2.0)
        sci += star
        sky &= np.hypot(xx - x, yy - y) > 6
    return sci, var, sky, rng


def test_recovers_the_understatement_factor():
    for f in (1.0, 2.25, 0.8):
        sci, var, sky, _ = scene(f)
        assert abs(sky_noise_scale(sci, var, sky) / f - 1) < 0.05


def test_robust_to_unmasked_sources_and_hot_pixels():
    sci, var, sky, rng = scene(2.0, seed=1)
    hot = rng.integers(0, 128, (40, 2))
    sci[hot[:, 0], hot[:, 1]] += 1e4                       # cosmic rays inside the sky mask
    yy, xx = np.indices(sci.shape)
    sci += 60 * np.exp(-((xx - 40) ** 2 + (yy - 90) ** 2) / 2.0)   # a faint source the mask missed
    assert abs(sky_noise_scale(sci, var, sky) / 2.0 - 1) < 0.07


def test_ignores_star_pixels_entirely():
    """Only `sky` pixels enter: changing every star pixel cannot change the scale."""
    sci, var, sky, _ = scene(1.5, seed=2)
    a = sky_noise_scale(sci, var, sky)
    sci2 = sci.copy()
    sci2[~sky] *= 37.0
    assert sky_noise_scale(sci2, var, sky) == a


def test_too_little_sky_is_nan():
    sci, var, sky, _ = scene(1.0)
    assert np.isnan(sky_noise_scale(sci, var, np.zeros_like(sky)))
