import numpy as np
import pytest

from spherex.astrometry import visit_centroid


def test_visit_mean_retains_covariance_and_does_not_use_arithmetic_weights():
    points = [
        dict(xi=1.0, eta=2.0, s_xi=1.0, s_eta=2.0, cov_xi_eta=0.5, mjd=61000.0),
        dict(xi=3.0, eta=4.0, s_xi=10.0, s_eta=20.0, cov_xi_eta=50.0, mjd=61001.0),
    ]
    fit = visit_centroid(points)
    assert np.allclose(fit["mean"], np.array([1.0, 2.0]) + np.array([2.0, 2.0]) / 101)
    assert np.isclose(fit["covariance"][0, 1], 0.5 / 1.01)
    assert fit["n"] == 2 and fit["dof"] == 2
    singleton = visit_centroid(points[:1])
    assert singleton["dof"] == 0 and np.allclose(singleton["mean"], [1, 2])
    with pytest.raises(ValueError):
        visit_centroid([])


def test_two_epoch_motion_uses_known_covariance_without_false_degrees_of_freedom():
    from spherex.astrometry import motion_fit
    result = motion_fit([2025.,2026.],[0.,-8.],[0.,.6],[.1,.1],[.2,.2],[0.,0.],[0.,0.],2025.,plx_fixed=.439)
    assert result["dof"] == 0
    assert np.allclose(result["params"][2:],[-8,.6])
    assert np.isclose(result["errors"][2],np.sqrt(.02))
    assert result["delta_chi2"] > 25
