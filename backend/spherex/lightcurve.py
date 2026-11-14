"""Spectrally normalized curves and same-channel/region annulus ratios (§4.9)."""

from __future__ import annotations

from typing import Any

import numpy as np
from astropy.timeseries import LombScargle


def annulus_measure(
    img: Any, var: Any, bad: Any, x: float, y: float, r_in: float = 3.0, r_out: float = 6.0
) -> tuple[float, float]:
    if not 0 < r_in < r_out:
        raise ValueError("invalid annulus")
    if x - r_out < 0 or y - r_out < 0 or x + r_out >= img.shape[1] or y + r_out >= img.shape[0]:
        raise ValueError("annulus clipped by frame edge")
    yy, xx = np.indices(img.shape)
    r = np.hypot(xx - x, yy - y)
    ok = (r >= r_in) & (r < r_out) & ~bad & np.isfinite(img) & np.isfinite(var) & (var > 0)
    if ok.sum() < 10:
        raise ValueError("fewer than ten usable annulus pixels")
    area = np.pi * (r_out * r_out - r_in * r_in)
    return float(np.mean(img[ok]) * area), float(np.sqrt(var[ok].sum()) / ok.sum() * area)


def annulus_flux(img: Any, bad: Any, x: float, y: float, r_in: float = 3.0, r_out: float = 6.0) -> float:
    try:
        return annulus_measure(img, np.ones_like(img), bad, x, y, r_in, r_out)[0]
    except ValueError:
        return float("nan")


def relative_curve(rows: list[dict[str, Any]], width_days: float = 14.0, method: str = "psf") -> dict[str, Any]:
    return dict(normalized_curve(rows, width_days, method)["bands"])


def normalized_curve(rows: list[dict[str, Any]], width_days: float = 14.0, method: str = "psf") -> dict[str, Any]:
    """Rows carry detector, channel, region, mjd, flux, err, scale; no raw-channel LC.

    Region is mandatory for annulus ratios: detector+channel alone does not cancel
    spatially varying far wings. Reference error is a shared calibration limitation.
    """
    if method not in ("psf", "annulus") or not np.isfinite(width_days) or width_days <= 0 or not rows:
        raise ValueError("valid method, bin width and observations required")
    if len({r["scale"] for r in rows}) > 1:
        raise ValueError("F4 unresolved: mixed-release light curve forbidden; select release=qr2 or release=qr3")
    groups: dict[Any, list[dict[str, Any]]] = {}
    for row in rows:
        if not np.isfinite(row["flux"]) or not np.isfinite(row["err"]) or row["err"] <= 0:
            continue
        if method == "annulus" and "region" not in row:
            raise ValueError("annulus needs parent-detector region")
        if not 1 <= row["channel"] <= 17:
            continue
        group = (row["detector"], row["channel"], row.get("region") if method == "annulus" else None)
        groups.setdefault(group, []).append(row)
    t0 = min(r["mjd"] for r in rows)
    groups = {k: v for k, v in groups.items() if len({int((r["mjd"] - t0) // width_days) for r in v}) >= 2}
    flat = [r for v in groups.values() for r in v]
    if not flat:
        return dict(bands={}, covariance=[], covariance_order=[], reference=[])
    flux = np.array([r["flux"] for r in flat])
    variance = np.array([r["err"] ** 2 for r in flat])
    # Local derivative of the median: one middle order statistic, or the mean
    # of two. Ties share the derivative symmetrically. Smoothing never crosses
    # a detector boundary and never bridges an unobserved channel gap.
    keys = list(groups)
    med = np.zeros((len(keys), len(flat)))
    start = 0
    for j, vals in enumerate(groups.values()):
        f = flux[start : start + len(vals)]
        order = np.sort(f)
        for value in (order[(len(f) - 1) // 2], order[len(f) // 2]):
            equal = np.flatnonzero(f == value) + start
            med[j, equal] += 0.5 / len(equal)
        start += len(vals)
    smooth = np.eye(len(keys))
    if method == "psf":
        for j, key in enumerate(keys):
            weights = np.array([max(0, 2 - abs(k[1] - key[1])) if k[0] == key[0] else 0 for k in keys], float)
            smooth[j] = weights / weights.sum()
    reference_map = smooth @ med
    group_ref = reference_map @ flux
    refs = []
    derivatives = []
    for j, vals in enumerate(groups.values()):
        refs.extend([group_ref[j]] * len(vals))
        derivatives.extend([reference_map[j]] * len(vals))
    ref = np.asarray(refs)
    rmap = np.asarray(derivatives)
    ref_error = np.sqrt((rmap**2) @ variance)
    usable = (ref > 5 * ref_error) & np.isfinite(ref)
    ratio = np.divide(flux, ref, out=np.zeros_like(flux), where=usable)
    jac = np.diag(np.divide(1.0, ref, out=np.zeros_like(ref), where=usable))
    jac -= np.divide(flux, ref**2, out=np.zeros_like(flux), where=usable)[:, None] * rmap
    bins: dict[Any, list[int]] = {}
    for i, r in enumerate(flat):
        if usable[i]:
            bins.setdefault((r["detector"], int((r["mjd"] - t0) // width_days)), []).append(i)
    out: dict[str, Any] = {}
    combine = np.zeros((len(bins), len(flat)))
    ordering = []
    for j, ((d, b), indices) in enumerate(sorted(bins.items())):
        w = ref[indices] ** 2 / variance[indices]
        combine[j, indices] = w / w.sum()
        ordering.append([str(d), f"B{b}"])
        out.setdefault(str(d), []).append(
            dict(
                mjd=float(w @ np.array([flat[i]["mjd"] for i in indices]) / w.sum()),
                rel=float(combine[j] @ ratio),
                err=0.0,
                bin=f"B{b}",
            )
        )
    propagated = combine @ jac
    covariance = (propagated * variance) @ propagated.T
    for j, (d, b) in enumerate(ordering):
        next(p for p in out[d] if p["bin"] == b)["err"] = float(np.sqrt(max(0.0, covariance[j, j])))
    return dict(
        bands=out,
        covariance=covariance.tolist(),
        covariance_order=ordering,
        reference=[dict(detector=k[0], channel=k[1], flux=float(group_ref[j])) for j, k in enumerate(keys)],
        uncertainty="First-order measurement-noise propagation through sample medians and [1,2,1] channel smoothing; includes shared reference covariance. Conditional on median ordering; not temporal sampling or PSF systematics.",
    )


def periodogram(mjd: Any, flux: Any, err: Any, min_days: float = 30.0, max_days: float = 500.0) -> dict[str, Any]:
    t, f, e = map(lambda a: np.asarray(a, float), (mjd, flux, err))
    if len(t) < 20 or np.any(e <= 0) or not np.all(np.isfinite(np.r_[t, f, e])) or np.ptp(t) <= 2 * min_days:
        raise ValueError(
            "period acceptance requires >=20 bins, finite errors and a baseline exceeding two minimum periods"
        )
    # Do not search periods longer than the actual baseline. The governing acceptance
    # requires >=20 bins, not an arbitrary 500-day baseline for every period search.
    max_days = min(max_days, float(np.ptp(t)))
    ls = LombScargle(t, f, e)
    freq, power = ls.autopower(minimum_frequency=1 / max_days, maximum_frequency=1 / min_days, samples_per_peak=15)
    k = int(np.argmax(power))
    return dict(
        period_days=(1 / freq).tolist(),
        power=power.tolist(),
        best_days=float(1 / freq[k]),
        fap=float(ls.false_alarm_probability(power[k])),
    )


def phase_fold(mjd: Any, period: float, epoch: float) -> Any:
    if period <= 0:
        raise ValueError("positive period required")
    return ((np.asarray(mjd) - epoch) / period) % 1


def correlated_periodogram(
    mjd: Any, flux: Any, covariance: Any, trials: int = 1024, seed: int = 163182
) -> dict[str, Any]:
    """GLS sinusoid search with a parametric maximum-over-grid null experiment.

    Conditions on supplied Gaussian covariance and its stochastic subspace;
    singular reference-normalization directions carry no independent information.
    FAP is not an analytic independent-error approximation or a PSF-systematic test.
    """
    t, f, c = np.asarray(mjd, float), np.asarray(flux, float), np.asarray(covariance, float)
    if t.ndim != 1 or f.shape != t.shape or len(t) < 20 or np.ptp(t) <= 60 or trials < 128:
        raise ValueError("correlated periodogram requires >=20 bins, >60 days and >=128 null trials")
    if c.shape != (len(t), len(t)) or not np.all(np.isfinite(c)) or not np.all(np.isfinite(t + f)):
        raise ValueError("finite times, fluxes and matching covariance required")
    if not np.allclose(c, c.T, rtol=1e-8, atol=1e-14):
        raise ValueError("covariance must be symmetric")
    eigen, vectors = np.linalg.eigh(c)
    if eigen[-1] <= 0 or eigen[0] < -1e-10 * eigen[-1]:
        raise ValueError("covariance must be positive semidefinite")
    keep = eigen > eigen[-1] * 1e-10
    if keep.sum() < 6:
        raise ValueError("fewer than six stochastic covariance directions")
    whiten = vectors[:, keep].T / np.sqrt(eigen[keep])[:, None]
    intercept = whiten @ np.ones(len(t))
    norm = np.linalg.norm(intercept)
    # A fitted normalization can put the constant vector exactly in the null
    # space. Test variations about relative flux=1 in that case.
    q0 = intercept[:, None] / norm if norm > np.linalg.norm(whiten) * 1e-10 else np.zeros((keep.sum(), 0))
    observed = whiten @ (f - 1)
    noise = np.random.default_rng(seed).normal(size=(int(keep.sum()), trials))
    samples = np.column_stack((observed, noise))
    samples -= q0 @ (q0.T @ samples)
    chi0 = np.sum(samples**2, axis=0)
    if chi0[0] <= np.finfo(float).eps:
        raise ValueError("no stochastic variability to fit")
    freq = LombScargle(t, f).autofrequency(
        minimum_frequency=1 / min(500.0, float(np.ptp(t))), maximum_frequency=1 / 30.0, samples_per_peak=15
    )
    powers = []
    maxima = np.zeros(trials)
    for frequency in freq:
        phase = 2 * np.pi * frequency * (t - t.mean())
        design = whiten @ np.column_stack((np.sin(phase), np.cos(phase)))
        design -= q0 @ (q0.T @ design)
        left, singular, _ = np.linalg.svd(design, full_matrices=False)
        basis = left[:, singular > singular[0] * 1e-10]
        gain = np.sum((basis.T @ samples) ** 2, axis=0) / np.maximum(chi0, np.finfo(float).tiny)
        powers.append(float(gain[0]))
        maxima = np.maximum(maxima, gain[1:])
    best = int(np.argmax(powers))
    exceed = int(np.sum(maxima >= powers[best]))
    fap = (exceed + 1) / (trials + 1)
    return dict(
        period_days=(1 / freq).tolist(),
        power=powers,
        best_days=float(1 / freq[best]),
        fap=fap,
        fap_trials=trials,
        fap_exceedances=exceed,
        fap_seed=seed,
        covariance_rank=int(keep.sum()),
        fap_resolution=1 / (trials + 1),
        method="GLS; maximum-over-identical-frequency-grid Gaussian covariance null; conditional on estimated reference covariance",
    )
