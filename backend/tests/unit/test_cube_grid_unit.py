"""L0: cube, grid and stack helpers (implementation.md §4.4–§4.6, §7)."""
import numpy as np
import pytest

from spherex.constants import BANDS
from spherex.cube import CH_LN, at_wavelengths, fit_dipole, lambda_slice, null_halves, psf_match, scrubber, shift_pa
from spherex.grid import grid_centres, make_grid, pixel_scale_for, to_grid
from spherex.stack import build_stack, transient_candidates
from spherex.types import Cube, Grid, TimeBin


def _doc_at_wavelengths(lam_t, cube, cvar, clam, band, max_gap_ch=0.75):
    """implementation.md §4.6 as written (adjacent-bin version), kept as the reference."""
    nb = len(cube)
    with np.errstate(invalid="ignore", divide="ignore"):
        lt, ls = np.log(lam_t), np.log(clam)
    k = np.broadcast_to(np.arange(nb)[:, None, None], cube.shape)
    with np.errstate(invalid="ignore"):
        j0 = np.where(lt >= ls, k, k - 1).clip(0, nb - 1)
    j1 = (j0 + 1).clip(0, nb - 1)
    take = lambda a, j: np.take_along_axis(a, j, axis=0)
    f0, f1, l0, l1 = take(cube, j0), take(cube, j1), take(ls, j0), take(ls, j1)
    with np.errstate(invalid="ignore", divide="ignore"):
        t = (lt - l0) / (l1 - l0)
        good = np.isfinite(f0) & np.isfinite(f1) & (j1 > j0) & (t >= 0) & (t <= 1)
        f = np.where(good, f0 * (1 - t) + f1 * t, np.nan)
    return f


def test_at_wavelengths_matches_documented_version_where_it_is_defined():
    rng = np.random.default_rng(0)
    band, nb, shape = 4, 17, (6, 6)
    lo = BANDS[band][0]
    cen = lo * np.exp((np.arange(nb) + 0.5)[:, None, None] * CH_LN[band])
    clam = cen * np.exp(rng.uniform(-0.4, 0.4, (nb,) + shape) * CH_LN[band])
    cube = (clam / lo) ** 2.0 + 0 * rng.normal(size=clam.shape)
    clam[rng.random(clam.shape) < 0.15] = np.nan                       # empty bins, as on real visits (F16)
    cube[~np.isfinite(clam)] = np.nan
    lam_t = cen * np.exp(rng.uniform(-0.45, 0.45, clam.shape) * CH_LN[band])
    ref = _doc_at_wavelengths(lam_t, cube, np.ones_like(cube), clam, band)
    new, _ = at_wavelengths(lam_t, cube, np.ones_like(cube), clam, band, max_gap_ch=0.0)
    both = np.isfinite(ref)
    assert both.sum() > 300 and np.allclose(new[both], ref[both])
    truth = (lam_t / lo) ** 2.0
    assert np.nanmax(np.abs(new / truth - 1)) < 0.01                  # linear in ln λ, power-law spectrum


def test_shift_pa_convention_and_dipole_fit():
    assert shift_pa(0, 1) == 0.0 and shift_pa(-1, 0) == 90.0 and shift_pa(1, 0) == 270.0   # north, east, west
    yy, xx = np.indices((31, 31), float)
    s = 2.2 / 2.3548
    g = lambda x, y: np.exp(-((xx - x) ** 2 + (yy - y) ** 2) / (2 * s * s)) / (2 * np.pi * s * s)
    d = 500 * (g(15, 16.0) - g(15, 14.5)) + np.random.default_rng(1).normal(size=xx.shape)
    r = fit_dipole(d, np.ones_like(d), 15, 15, 2.2)
    assert r["kind"] == "dipole" and abs(r["dy"] - 1.5) < 0.1 and abs(r["dx"]) < 0.1
    m = fit_dipole(500 * g(15, 15) + np.random.default_rng(2).normal(size=xx.shape), np.ones_like(d), 15, 15, 2.2)
    assert m["kind"] == "monopole" and m["flux"] > 0
    assert fit_dipole(d, np.ones_like(d), 1, 1, 2.2) is None


def _cube(band, lamval, val, bid="V1"):
    tb = TimeBin(bid, band, np.arange(1), "full", 0, 0, 0, (1,), "")
    lam = np.full((2, 3, 3), np.nan); lam[0], lam[1] = lamval
    c = np.full((2, 3, 3), np.nan); c[0], c[1] = val
    return Cube(bin=tb, band=band, grid=None, cube=c, var=np.ones_like(c), lam=lam, nhits=np.ones(c.shape, np.int64))


def test_scrubber_sorted_by_measured_lambda_and_lambda_slice():
    a, b = _cube(5, (4.0, 4.3), (1.0, 2.0)), _cube(4, (3.3, 3.7), (3.0, 4.0))
    planes, lam, band = scrubber([a, b])
    assert list(lam) == [3.3, 3.7, 4.0, 4.3] and list(band) == [4, 4, 5, 5] and planes[0][0, 0] == 3.0
    img, var = lambda_slice([a, b], 3.25, 3.40)
    assert img[0, 0] == 3.0 and var[0, 0] == 1.0
    img, _ = lambda_slice([a, b], 3.6, 4.1)                       # two bins, equal weights
    assert img[0, 0] == 2.5


def test_null_halves_disjoint_and_alternate_in_lambda():
    ia, ib = null_halves([3.0, 2.5, 3.5, 2.7, 3.1])
    assert set(ia) | set(ib) == set(range(5)) and not set(ia) & set(ib)
    order = np.argsort([3.0, 2.5, 3.5, 2.7, 3.1])                 # 1, 3, 0, 4, 2
    assert list(ia) == sorted(order[0::2]) and list(ib) == sorted(order[1::2])


def test_psf_match_variance_of_white_noise():
    rng = np.random.default_rng(3)
    img = rng.normal(size=(200, 200))
    out, v = psf_match(img, np.ones_like(img), 1.46, 2.2)
    inner = np.s_[20:-20, 20:-20]
    assert abs(np.std(out[inner]) ** 2 / np.median(v[inner]) - 1) < 0.1
    same, vs = psf_match(img, np.ones_like(img), 2.2, 2.2)
    assert same is img


def test_grid_helpers():
    assert pixel_scale_for(6) == 6.15 and pixel_scale_for(6, 3.0) == 3.0
    assert abs(pixel_scale_for(60) - 11.96) < 0.01                  # 60′ binned to ≈12″ pixels
    g = make_grid(10.0, 20.0, 2.0)
    assert isinstance(g, Grid) and g.shape == (19, 19) and g.native and not make_grid(10, 20, 2, 3.0).native
    pos = lambda m: (10.0 + 0.001 * (m - 60000), np.full(np.shape(m), 20.0))
    ra, _ = grid_centres(pos, [60000, 60010, 60020], "fixed")
    assert np.allclose(ra, 10.01)
    ra, _ = grid_centres(pos, [60000, 60010, 60020], "track")
    assert np.allclose(ra, [10.0, 10.01, 10.02])
    with pytest.raises(ValueError):
        grid_centres(pos, [1], "wobble")


def test_bicubic_resampling_is_nan_safe():
    g = make_grid(150, 10, 4.0)
    w2 = make_grid(150.0003, 9.9998, 4.0).wcs
    img = np.ones(g.shape); img[17:22, 17:22] = np.nan
    a, _ = to_grid(img, np.ones(g.shape), g.wcs, w2, g.shape, "bicubic")
    assert np.isnan(a).sum() < 120 and np.nanmax(np.abs(a - 1)) < 0.02


def test_transients_and_empty_stack():
    rej = np.zeros((2, 10, 10), bool); rej[0, 3, 3:5] = True; rej[1, 7, 7] = True
    t = transient_candidates(rej, ["a", "b"])
    assert t == [dict(frame="a", x=3.5, y=3.0, npix=2)]
    g = make_grid(0, 0, 1.0)
    tb = TimeBin("V1", 6, np.arange(0), "full", 0, 0, 0, (), "")
    s = build_stack([], tb, g, [("f.fits", "FINAST=1")])
    assert np.isnan(s.mean).all() and s.skipped == [("f.fits", "FINAST=1")] and s.nhits.sum() == 0
