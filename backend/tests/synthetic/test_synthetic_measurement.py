"""M L1: 5x table PSF, native pixels, independent Gaussian noise; no real-file claim.

The shared generator is tested separately for PA/LVF traps; these tests exercise
native ePSF estimation and motion linear algebra with known injected truth.
"""

import numpy as np
import pytest

from spherex.astrometry import fit_pm, motion_fit, parallax_factors, registration
from spherex.epsf import EPSF, fit_blend, fit_native, fit_sources, fit_star


def psf():
    from .scene import table_epsf

    return EPSF(dict(XCENTER=[1020], YCENTER=[1020], EPSF=[table_epsf(fwhm_px=0.7 * 2.3548, ellip=0.0, coma=0.0)]))


def test_synthetic_300_edge_phase_fits():
    """Native table PSF, edge taper, 300 Gaussian draws; naive constant edge stalls (impl §10.1)."""
    p = psf()
    rng = np.random.default_rng(938)
    chi = []
    xy = []
    flux = []
    for _ in range(300):
        x, y = rng.uniform(-0.45, 0.45, 2)
        truth = 1200 * p.stamp(0, x, y) + 3
        noise = rng.normal(0, 0.7, truth.shape)
        data = truth + noise
        fit = fit_star(data, np.full_like(data, 0.49), np.zeros(data.shape, bool), p, 0, 3, 3, max_shift=1.0)
        assert fit is not None
        params, err, rc = fit
        chi.append(rc)
        xy.append((params[:2] - [3 + x, 3 + y]) / err[:2])
        flux.append(params[2])
        assert rc * 45 <= np.sum(noise**2 / 0.49) + 1e-5
    assert abs(np.median(chi) - 1) < 0.12
    assert abs(np.median(flux) / 1200 - 1) < 0.02
    assert 0.5 < np.std(xy) < 1.4
    assert fit_star(data, np.ones_like(data), np.ones(data.shape, bool), p, 0, 3, 3) is None
    assert fit_star(data, np.ones_like(data), np.zeros(data.shape, bool), p, 0, 0, 0) is None


def test_synthetic_blend_naive_bias_and_covariance():
    """Two stars 0.7 px apart, table PSF, white noise, native pixels, flat spectrum."""
    p = psf()
    yy, xx = np.indices((15, 15))
    xy = [(7.0, 7.0), (7.7, 7.1)]
    data = 500 * p.sample(0, xx - 7, yy - 7) + 180 * p.sample(0, xx - 7.7, yy - 7.1) + 2
    var = np.full_like(data, 0.01)
    bad = np.zeros(data.shape, bool)
    fit = fit_sources(data, var, bad, p, xy, [0, 0])
    assert np.allclose(fit["flux"], [500, 180], rtol=0.001)
    assert fit["covariance"][0, 1] < 0
    free = fit_blend(data, var, bad, p, [(7.05, 7.02), xy[1]], [0, 0])
    assert free is not None and np.allclose(free.params[:2], xy[0], atol=0.001)
    naive = fit_star(data, var, bad, p, 0, 7, 7)
    assert naive[0][0] - 7 > 0.1
    # An absolute WCS error must not create a spurious forced blue target signal.
    offset = np.array([0.12, -0.08])
    null = 180 * p.sample(0, xx - xy[1][0], yy - xy[1][1]) + 2
    common = fit_blend(null, var, bad, p, np.asarray(xy) + offset, [0, 0], shared_shift=True)
    assert common is not None
    assert abs(common.params[2]) < 1e-3
    assert np.allclose(common.params[:2], xy[0], atol=1e-4)
    assert common.errors[2] > 0


def test_plane_background_fitting_keeps_native_flux_and_covariance():
    p = psf()
    yy, xx = np.indices((15, 15))
    data = 500 * p.sample(0, xx - 7.1, yy - 6.9) + 2 + 0.4 * (xx - 7) - 0.2 * (yy - 7)
    fit = fit_native(data, np.full(data.shape, 0.01), np.zeros(data.shape, bool), p, 0, 7, 7, background_order=1)
    assert fit is not None
    assert np.allclose(fit.params, [7.1, 6.9, 500, 2, 0.4, -0.2], atol=1e-5)
    assert fit.dof == 49 - 6 and fit.covariance.shape == (6, 6)


def test_synthetic_pm_fixed_parallax_and_shared_errors():
    """Quadrature epochs with 439 mas parallax; PM-only fit biases the recovered motion."""
    t = np.array([2025.8, 2026.3, 2026.8, 2027.3])
    pa = np.array([1.0, -1.0, 1.0, -1.0])
    pd = 0.3 * pa
    x = 1 - 8.1237 * (t - 2026) + 0.439 * pa
    y = 2 + 0.6732 * (t - 2026) + 0.439 * pd
    e = np.full(4, 0.02)
    p, err, chi = fit_pm(t, x, y, e, e, pa, pd, 2026, 0.439)
    assert np.allclose(p, [1, 2, -8.1237, 0.6732])
    no, _, _ = fit_pm(t, x, y, e, e, pa, pd, 2026, 0.0)
    assert abs(no[2] + 8.1237) > 0.2
    with pytest.raises(ValueError):
        fit_pm(np.ones(4), x, y, e, e, pa, pd, 2026, 0.439)
    base = motion_fit(t, x, y, e, e, pa, pd, 2026, 0.439)
    shared = motion_fit(t, x, y, e, e, pa, pd, 2026, 0.439, visit_ids=["a", "a", "b", "b"], visit_floor=0.2)
    assert shared["errors"][2] > base["errors"][2]


def test_synthetic_registration_rejects_outlier():
    """Independent Gaia residuals with one artifact; no rotation or LVF involved."""
    r = np.tile([0.3, -0.4], (8, 1))
    r[-1] = [20, 20]
    out = registration(r, np.full((8, 2), 0.02))
    assert np.allclose(out["offset"], [0.3, -0.4]) and out["used"].sum() == 7


def test_parallax_sign_independent_vector():
    """1 pc source: subtract Earth vector geometrically, compare with linear factors."""
    from astropy import units as u
    from astropy.coordinates import SkyCoord, get_body_barycentric
    from astropy.time import Time

    c = SkyCoord(ra=133 * u.deg, dec=-7 * u.deg, distance=1 * u.pc)
    e = get_body_barycentric("earth", Time(61000, format="mjd"))
    q = c.cartesian.xyz.to_value(u.au) - e.xyz.to_value(u.au)
    apparent = SkyCoord(x=q[0] * u.au, y=q[1] * u.au, z=q[2] * u.au, representation_type="cartesian")
    out = SkyCoord(apparent.spherical.lon, apparent.spherical.lat)
    da, dd = SkyCoord(c.ra, c.dec).spherical_offsets_to(out)
    pa, pd = parallax_factors(61000, 133, -7)
    assert abs(da.arcsec - pa) < 1e-5 and abs(dd.arcsec - pd) < 1e-5
