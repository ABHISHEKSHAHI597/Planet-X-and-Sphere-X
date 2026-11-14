"""Independent pixels/registration draws for a shared visit centroid."""

import numpy as np

from spherex.epsf import EPSF
from spherex.joint_astrometry import JointFrame, fit_visit

from .scene import table_epsf


def test_joint_native_centroid_with_colour_rotation_and_registration_noise():
    psf = EPSF(dict(XCENTER=[1020], YCENTER=[1020], EPSF=[table_epsf(fwhm_px=1.7, ellip=0.1, coma=0.02)]))
    yy, xx = np.indices((17, 17))
    true = np.array([0.7, -0.5])
    rng = np.random.default_rng(18235)
    errors = []
    for _ in range(12):
        frames = []
        for j in range(6):
            angle = j * np.pi / 3
            transform = np.array([[np.cos(angle), -np.sin(angle)], [np.sin(angle), np.cos(angle)]]) / 6.15
            xy = np.array([[8.0, 8.0], [8.9, 8.2]])
            shift = transform @ rng.normal(0, 0.05, 2)
            target, neighbour = xy + shift
            target += transform @ true
            image = (
                (30 + 5 * j) * psf.sample(0, xx - target[0], yy - target[1])
                + (60 - 5 * j) * psf.sample(0, xx - neighbour[0], yy - neighbour[1])
                + 4
                + rng.normal(0, 0.5, xx.shape)
            )
            frames.append(
                JointFrame(
                    image,
                    np.full(xx.shape, 0.25),
                    np.zeros(xx.shape, bool),
                    psf,
                    xy,
                    (0, 0),
                    transform,
                    np.full(2, 0.05),
                )
            )
        result = fit_visit(frames)
        covariance = result["covariance"]
        assert np.min(np.linalg.eigvalsh(covariance)) > 0
        residual = result["offset_arcsec"] - true
        errors.append(np.linalg.solve(np.linalg.cholesky(covariance), residual))
        assert 0.5 < result["chi2"] / result["dof"] < 1.6
        assert np.all(result["fluxes"] >= 0)
    assert np.linalg.norm(np.mean(errors, axis=0)) < 1
    assert 0.25 < np.sqrt(np.mean(np.array(errors) ** 2)) < 1.8


def test_low_snr_joint_centroid_empirical_uncertainty_coverage():
    # Predeclared 100 independent realizations: nominal 95% 2-D ellipses
    # must cover >=90%; no individual-frame S/N selection is applied.
    psf = EPSF(dict(XCENTER=[1020], YCENTER=[1020], EPSF=[table_epsf(fwhm_px=1.7, ellip=0.1, coma=0.02)]))
    yy, xx = np.indices((17, 17))
    truth = np.array([0.7, -0.5])
    transform = np.eye(2) / 6.15
    rng = np.random.default_rng(128499)
    chi, errors = [], []
    for _ in range(100):
        frames = []
        for j in range(16):
            xy = np.array([[8.0, 8.0], [8.9, 8.2]])
            shift = transform @ rng.normal(0, 0.05, 2)
            target, neighbour = xy + shift
            target += transform @ truth
            image = (
                (6 + 1.5 * (j % 4)) * psf.sample(0, xx - target[0], yy - target[1])
                + (10 + 3 * np.sin(j)) * psf.sample(0, xx - neighbour[0], yy - neighbour[1])
                + 4
                + rng.normal(0, 0.5, xx.shape)
            )
            frames.append(
                JointFrame(
                    image,
                    np.full(xx.shape, 0.25),
                    np.zeros(xx.shape, bool),
                    psf,
                    xy,
                    (0, 0),
                    transform,
                    np.full(2, 0.05),
                )
            )
        result = fit_visit(frames)
        delta = result["offset_arcsec"] - truth
        pull = np.linalg.solve(np.linalg.cholesky(result["covariance"]), delta)
        chi.append(pull @ pull)
        errors.append(pull)
    coverage = np.mean(np.array(chi) < 5.991464547)
    rms = np.sqrt(np.mean(np.array(errors) ** 2))
    print(
        "joint_low_snr",
        dict(trials=100, coverage95=float(coverage), pull_rms=float(rms), mean_pull=np.mean(errors, axis=0).tolist()),
    )
    assert coverage >= 0.90
    assert 0.7 < rms < 1.4
    assert np.linalg.norm(np.mean(errors, axis=0)) < 0.5
