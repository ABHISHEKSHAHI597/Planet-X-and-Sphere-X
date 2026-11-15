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


MIN_SNR = 5.0     # ln f is linear in the noise only while σ_f/f is small


def normalized_curve(rows: list[dict[str, Any]], width_days: float = 14.0, method: str = "psf") -> dict[str, Any]:
    """Rows carry detector, channel, region, mjd, flux, err, scale; no raw-channel LC.

    Joint relative photometry. A linear-variable filter samples a given channel at a fixed sky position only
    within short windows (a visit, a 6-month repeat), so dividing each channel by its own temporal median turns the
    curve into a high-pass filter: a slow variable (a Mira) normalises itself away, and a curved spectrum sampled by
    different channels in different bins leaves fake steps. Instead, per detector,

        ln f_i = s_g(i) + a_b(i) + ε_i,     σ(ε_i) = err_i / f_i,

    with one level s_g per (channel[, region]) group and one brightness a_b per time bin, fitted by weighted least
    squares. Bins are compared through every channel they share, directly or through chains of bins. The model has
    one degenerate direction per connected component of the bin–channel graph (s + c, a − c); each component is
    normalised to a geometric-mean brightness of 1, and components that share no channel are separate curves whose
    relative level is unknown (only the largest is returned; the others are reported in `dropped`).

    Region is mandatory for annulus ratios: detector+channel alone does not cancel spatially varying far wings.
    """
    if method not in ("psf", "annulus") or not np.isfinite(width_days) or width_days <= 0 or not rows:
        raise ValueError("valid method, bin width and observations required")
    if len({r["scale"] for r in rows}) > 1:
        raise ValueError("F4 unresolved: mixed-release light curve forbidden; select release=qr2 or release=qr3")
    t0 = min(r["mjd"] for r in rows)
    by_detector: dict[int, list[dict[str, Any]]] = {}
    dropped: list[list[str]] = []
    for row in rows:
        if method == "annulus" and "region" not in row:
            raise ValueError("annulus needs parent-detector region")
        if not (np.isfinite(row["flux"]) and np.isfinite(row["err"]) and row["err"] > 0):
            continue
        if not 1 <= row["channel"] <= 17:
            continue
        if row["flux"] < MIN_SNR * row["err"]:
            dropped.append([f"D{row['detector']} mjd {row['mjd']:.3f}", f"S/N < {MIN_SNR:g}"])
            continue
        by_detector.setdefault(int(row["detector"]), []).append(row)
    out: dict[str, Any] = {}
    ordering: list[list[str]] = []
    blocks: list[Any] = []
    reference: list[dict[str, Any]] = []
    for det in sorted(by_detector):
        fit = _joint_fit(by_detector[det], t0, width_days, method, dropped, det)
        if fit is None:
            continue
        points, cov, levels = fit
        out[str(det)] = points
        ordering.extend([str(det), p["bin"]] for p in points)
        blocks.append(cov)
        reference.extend(dict(detector=det, channel=k[0], flux=float(v)) for k, v in levels)
    n = sum(len(b) for b in blocks)
    covariance = np.zeros((n, n))
    i = 0
    for b in blocks:
        covariance[i : i + len(b), i : i + len(b)] = b
        i += len(b)
    return dict(
        bands=out,
        covariance=covariance.tolist(),
        covariance_order=ordering,
        reference=reference,
        dropped=dropped,
        uncertainty="Joint log-linear fit of per-channel levels and per-bin brightness; first-order (delta-method) "
        "propagation of the measurement noise, including the correlation every bin shares through the fitted channel "
        "levels and the normalisation. Not temporal sampling or PSF systematics.",
    )


def _joint_fit(
    rows: list[dict[str, Any]], t0: float, width_days: float, method: str, dropped: list[list[str]], det: int
) -> tuple[list[dict[str, Any]], Any, list[Any]] | None:
    gkey = [(r["channel"], r.get("region") if method == "annulus" else None) for r in rows]
    bkey = [int((r["mjd"] - t0) // width_days) for r in rows]
    # Groups seen in a single bin constrain nothing about time (their level absorbs them): drop, and say so.
    seen: dict[Any, set[int]] = {}
    for g, b in zip(gkey, bkey, strict=True):
        seen.setdefault(g, set()).add(b)
    keep = [i for i, g in enumerate(gkey) if len(seen[g]) >= 2]
    for i in set(range(len(rows))) - set(keep):
        dropped.append([f"D{det} B{bkey[i]}", "channel not repeated in another bin"])
    if not keep:
        return None
    # Connected components of the bipartite bin–group graph (union-find over bins through shared groups).
    parent: dict[int, int] = {}

    def root(b: int) -> int:
        while parent.setdefault(b, b) != b:
            parent[b] = parent[parent[b]]
            b = parent[b]
        return b

    first: dict[Any, int] = {}
    for i in keep:
        g, b = gkey[i], bkey[i]
        if g in first:
            parent[root(b)] = root(first[g])
        else:
            first[g] = b
            root(b)
    comps: dict[int, set[int]] = {}
    for b in {bkey[i] for i in keep}:
        comps.setdefault(root(b), set()).add(b)
    main = max(comps.values(), key=lambda c: (len(c), -min(c)))
    for c in comps.values():
        if c is not main:
            dropped.extend([f"D{det} B{b}", "shares no channel with the main curve"] for b in sorted(c))
    keep = [i for i in keep if bkey[i] in main]
    if len(main) < 2:
        return None
    bins = sorted(main)
    groups = sorted({gkey[i] for i in keep}, key=str)
    bi = {b: j for j, b in enumerate(bins)}
    gi = {g: j for j, g in enumerate(groups)}
    nb, ng = len(bins), len(groups)
    f = np.array([rows[i]["flux"] for i in keep], float)
    e = np.array([rows[i]["err"] for i in keep], float)
    y, sigma = np.log(f), e / f
    a = np.zeros((len(keep), ng + nb))
    for k, i in enumerate(keep):
        a[k, gi[gkey[i]]] = 1.0
        a[k, ng + bi[bkey[i]]] = 1.0
    w = 1 / sigma**2
    normal = a.T @ (a * w[:, None])
    # One connected component → exactly one null direction (s + c, a − c); the pseudo-inverse gives the
    # minimum-norm solution and its covariance, and the gauge map G (centre a, i.e. geometric mean 1) removes it.
    ninv = np.linalg.pinv(normal, rcond=1e-12, hermitian=True)
    x = ninv @ (a.T @ (w * y))
    gauge = np.eye(nb) - np.ones((nb, nb)) / nb
    abin = gauge @ x[ng:]
    cov_a = gauge @ ninv[ng:, ng:] @ gauge.T
    # Residual scatter beyond the stated errors (PSF or calibration systematics) widens every error alike.
    dof = len(keep) - (ng + nb - 1)
    chi2 = float(np.sum(w * (y - a @ x) ** 2))
    if dof > 0:
        cov_a *= max(1.0, chi2 / dof)
    rel = np.exp(abin)
    cov = cov_a * np.outer(rel, rel)
    points = []
    for j, b in enumerate(bins):
        idx = [k for k, i in enumerate(keep) if bkey[i] == b]
        points.append(dict(
            mjd=float(np.sum(w[idx] * np.array([rows[keep[k]]["mjd"] for k in idx])) / np.sum(w[idx])),
            rel=float(rel[j]),
            err=float(np.sqrt(max(0.0, cov[j, j]))),
            bin=f"B{b}",
        ))
    # Group levels in flux units at the curve's geometric-mean brightness (the gauge moved a by −mean, s by +mean).
    levels = [(g, np.exp(x[gi[g]] + np.mean(x[ng:]))) for g in groups]
    return points, cov, levels


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
