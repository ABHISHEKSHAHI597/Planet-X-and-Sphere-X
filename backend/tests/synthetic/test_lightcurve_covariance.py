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


def test_joint_fit_errors_against_noise_trials():
    rows = observations()
    result = normalized_curve(rows)
    covariance = np.array(result["covariance"])
    assert np.min(np.linalg.eigvalsh(covariance)) > -1e-15
    assert np.any(covariance[:4, :4] < 0)  # shared fitted normalization
    assert np.allclose(covariance[:4, 4:], 0)  # detectors are independent curves
    # The truth is recovered exactly without noise: relative brightness (1 + 0.2 t) at geometric mean 1.
    truth = 1 + 0.2 * np.arange(4)
    assert np.allclose(values(result)[:4], truth / np.exp(np.mean(np.log(truth))))
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


def mira_rows(t_step=4.0, noise=0.01, seed=7):
    """A 245-d Mira (±50 %) with a curved spectrum, each 14-d bin seeing only 3 of 17 channels and every channel
    recurring only a few bins later: the LVF sampling under which per-channel median normalisation erases the curve."""
    rng = np.random.default_rng(seed)
    rows = []
    for t in np.arange(0, 540, t_step):
        b = int(t // 14)
        level = 1 + 0.5 * np.sin(2 * np.pi * (14 * b + 7) / 245)
        for c in (1 + ((b // 2) * 3 + k) % 17 for k in range(3)):
            true = 100 * level * (1 + 0.3 * ((c - 9) / 8) ** 2)
            rows.append(dict(detector=3, channel=c, mjd=60000 + t, flux=true * (1 + rng.normal(0, noise)),
                             err=true * noise, scale="qr2"))
    return rows


def test_slow_variable_survives_sparse_channel_sampling():
    result = normalized_curve(mira_rows())
    pts = result["bands"]["3"]
    t = np.array([p["mjd"] for p in pts]) - 60000
    level = 1 + 0.5 * np.sin(2 * np.pi * ((t // 14) * 14 + 7) / 245)
    truth = level / np.exp(np.mean(np.log(level)))
    rel = np.array([p["rel"] for p in pts])
    assert len(pts) >= 30
    assert np.max(abs(rel - truth)) < 0.03          # amplitude kept, not high-pass filtered
    pg = correlated_periodogram(t, rel, np.array(result["covariance"]), trials=256)
    assert abs(pg["best_days"] - 245) < 15 and pg["fap"] < 0.01


def test_constant_source_with_curved_spectrum_stays_flat():
    rows = []
    for t in np.arange(0, 300, 4.0):
        chans = (6, 7, 8) if int(t // 14) % 2 else (8, 9, 10)   # alternate bins see different channels
        rows += [dict(detector=1, channel=c, mjd=60000 + t, flux=100 * (1 + 0.3 * ((c - 9) / 8) ** 2), err=0.3,
                      scale="qr2") for c in chans]
    rel = np.array([p["rel"] for p in normalized_curve(rows)["bands"]["1"]])
    assert np.allclose(rel, 1, atol=1e-9)


def test_annulus_groups_by_region_and_rejects_low_snr():
    rows = [dict(r, region=(0, 0)) for r in observations()]
    result = normalized_curve(rows, method="annulus")
    assert np.isclose(result["reference"][0]["flux"], 110 * np.exp(np.mean(np.log(1 + 0.2 * np.arange(4)))))
    low = [dict(r, flux=0.01, err=1) for r in rows]
    assert normalized_curve(low)["bands"] == {}


def test_bins_sharing_no_channel_are_not_chained():
    rows = [dict(detector=2, channel=c, mjd=60000 + t, flux=100.0, err=1.0, scale="qr2")
            for t, chans in ((0, (1, 2)), (14, (1, 2)), (100, (9, 10)), (114, (9, 10)), (128, (9, 10)))
            for c in chans]
    result = normalized_curve(rows)
    assert [p["bin"] for p in result["bands"]["2"]] == ["B7", "B8", "B9"]   # the larger component
    assert any("shares no channel" in why for _, why in result["dropped"])


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
