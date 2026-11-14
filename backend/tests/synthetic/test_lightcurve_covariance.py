"""Independent noise trials for the shared spectral-reference uncertainty."""

import numpy as np

from spherex.lightcurve import correlated_periodogram, normalized_curve


def observations():
    return [
        dict(
            detector=d, channel=c, mjd=60000 + 20 * t, flux=scale * (1 + 0.1 * c) * (1 + 0.2 * t), err=0.02, scale="qr2"
        )
        for d, scale in [(1, 100.0), (2, 500.0)]
        for c in range(1, 5)
        for t in range(4)
    ]


def values(result):
    return np.array(
        [next(p["rel"] for p in result["bands"][d] if p["bin"] == b) for d, b in result["covariance_order"]]
    )


def test_reference_smoothing_and_correlated_errors_against_noise_trials():
    rows = observations()
    result = normalized_curve(rows)
    covariance = np.array(result["covariance"])
    assert np.min(np.linalg.eigvalsh(covariance)) > -1e-15
    assert np.any(covariance[:4, :4] < 0)  # shared fitted normalization
    assert np.allclose(covariance[:4, 4:], 0)  # no cross-detector smoothing
    # Channel 1: [2,1] endpoint kernel, applied to temporal medians.
    ref = result["reference"][0]["flux"]
    assert np.isclose(ref, (2 * 110 * 1.3 + 120 * 1.3) / 3)
    rng = np.random.default_rng(395)
    trials = []
    for _ in range(500):
        noisy = [dict(r, flux=r["flux"] + rng.normal(0, r["err"])) for r in rows]
        trials.append(values(normalized_curve(noisy)))
    empirical = np.cov(trials, rowvar=False)
    assert np.allclose(np.diag(empirical), np.diag(covariance), rtol=0.2, atol=0)
    for j, (d, b) in enumerate(result["covariance_order"]):
        p = next(p for p in result["bands"][d] if p["bin"] == b)
        assert np.isclose(p["err"] ** 2, covariance[j, j])


def test_annulus_does_not_smooth_channels_and_rejects_uncertain_reference():
    rows = [dict(r, region=(0, 0)) for r in observations()]
    result = normalized_curve(rows, method="annulus")
    assert np.isclose(result["reference"][0]["flux"], 110 * 1.3)
    low = [dict(r, flux=0.01, err=1) for r in rows]
    assert normalized_curve(low)["bands"] == {}


def test_correlated_period_search_and_singular_reference_null():
    t = np.arange(0, 700, 14.0)
    c = 0.01**2 * (np.eye(len(t)) - np.ones((len(t), len(t))) / len(t))
    flux = 1 + 0.2 * np.sin(2 * np.pi * t / 245)
    result = correlated_periodogram(t, flux, c, trials=256)
    assert abs(result["best_days"] - 245) < 10
    assert result["covariance_rank"] == len(t) - 1
    assert result["fap"] == result["fap_resolution"]
    assert result == correlated_periodogram(t, flux, c, trials=256)
    # A covariance-preserving rotation of observations must preserve inference.
    idx = np.random.default_rng(2).permutation(len(t))
    shuffled = correlated_periodogram(t[idx], flux[idx], c[np.ix_(idx, idx)], trials=256)
    assert np.isclose(shuffled["best_days"], result["best_days"])


def test_correlated_null_false_alarm_rates_and_invalid_covariance():
    import pytest

    t = np.arange(0, 600, 14.0)
    c = 0.01**2 * (np.eye(len(t)) + 0.6 * np.exp(-abs(t[:, None] - t[None, :]) / 40))
    rng = np.random.default_rng(38)
    faps = [
        correlated_periodogram(t, 1 + rng.multivariate_normal(np.zeros(len(t)), c), c, trials=128, seed=j)["fap"]
        for j in range(30)
    ]
    assert sum(p < 0.05 for p in faps) <= 5
    assert 0.25 < np.mean(faps) < 0.75
    with pytest.raises(ValueError):
        correlated_periodogram(t, np.ones(len(t)), -c)
