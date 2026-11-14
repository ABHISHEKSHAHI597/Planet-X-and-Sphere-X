"""L1: cross-release (QR2 − QR3) differences with the in-situ photometric match (decision record 0008,
workflow.md §11.2). F4 is inconclusive, so a QR2 visit is matched to a QR3 visit on the static sources they
share. Each test has teeth: the unmatched difference, or a naive fit, fails where the match must succeed.
Native chain as in test_synthetic_pipeline (PA flip, half-channel offset, steep spectra, SIP, dithers)."""
from dataclasses import replace

import numpy as np
import pytest

from spherex.cube import DIFF_ORDER, annotate, build_cube, diff, diff_fwhm_arcsec, fit_relative_scale, matched_pair
from spherex.epochs import time_bins
from spherex.grid import frame_to_grid, make_grid
from spherex.preprocess import calibrate
from spherex.stack import build_stack, sky_pixels
from tests.synthetic.scene import PIXEL_ARCSEC, Star, SynthCalib, field, native_visit, steep

RA0, DEC0, BAND = 150.0, 10.0, 4
CAL = SynthCalib((4, 6))
PX = PIXEL_ARCSEC / 3600
GAIN = 0.93                       # the uncorrected QR2/QR3 ratio measured in validation/F4


@pytest.fixture(scope="module")
def grid():
    return make_grid(RA0, DEC0, 8.6)


def _scene(seed=21, flux=(150.0, 600.0)):
    rng = np.random.default_rng(seed)
    st = field(RA0, DEC0, rng, n=16, radius_deg=0.045, flux=flux, alpha=steep(BAND, 2.0))
    return st


def _gain(stars, g0, beta=0.0):
    """B's release gain g(λ) = g0·(λ/λmin)^β on every star (a power law in λ, so α → α + β)."""
    return [replace(s, flux=s.flux * g0, alpha=s.alpha + beta) for s in stars]


def _pair(starsA, starsB, grid, seed=31, relA="qr3", relB="qr2"):
    rng = np.random.default_rng(seed)
    A, _ = native_visit(starsA, BAND, rng, RA0, DEC0, pa=0.0, calib=CAL, size=101, visit_tag="A", mjd0=61200,
                        release=relA)
    B, _ = native_visit(starsB, BAND, rng, RA0, DEC0, pa=180.0, offset_ch=0.5, calib=CAL, size=101, visit_tag="B",
                        mjd0=61020, release=relB)
    out = []
    for F in (A, B):
        gs = [frame_to_grid(calibrate(f, CAL), grid) for f in F]
        gd = [frame_to_grid(calibrate(f, CAL), grid, DIFF_ORDER) for f in F]
        out.append((build_stack(gs, time_bins([g.mjd for g in gs], [BAND] * len(gs), "visit")[BAND][0], grid), gd))
    (sa, ga), (sb, gb) = out
    fw = diff_fwhm_arcsec(ga, gb)
    ca = build_cube(ga, sa.bin, BAND, grid, homog_fwhm_arcsec=fw)
    cb = build_cube(gb, sb.bin, BAND, grid, homog_fwhm_arcsec=fw)
    return ca, cb, sky_pixels(sa) & sky_pixels(sb), fw


def _xy(grid, st):
    return tuple(float(v) for v in grid.wcs.world_to_pixel_values(st.x, st.y))


def _peak(sig, grid, stars, h=2):
    out = []
    for s in stars:
        x, y = _xy(grid, s)
        ix, iy = int(round(x)), int(round(y))
        if h <= ix < sig.shape[1] - h and h <= iy < sig.shape[0] - h:
            out.append(float(np.nanmax(np.abs(sig[iy - h:iy + h + 1, ix - h:ix + h + 1]))))
    return np.array(out)


def test_cross_release_difference_is_matched_and_static_stars_cancel(grid):
    """The reported bug: QR3 visit − QR2 visit. Teeth: the raw mixed difference leaves > 5σ residuals at
    the static stars (a 7 % gain at S/N ≫ 10); the matched one is < 3σ everywhere, and the recovered scale
    is 1/0.93 within 3 of its own bootstrap errors."""
    st = _scene()
    ca, cb, sky, _ = _pair(st, _gain(st, GAIN), grid)
    assert ca.photometric_scales == ("qr3",) and cb.photometric_scales == ("qr2",)
    raw = diff(ca, cb, sky, allow_mixed_scales=True)
    assert raw.photometric_match is not None and raw.photometric_match["applied"] is False
    assert np.max(_peak(raw.sig, grid, st)) > 5.0                        # the gain is visible at every star
    df = diff(ca, cb, sky)
    pm = df.photometric_match
    assert pm["applied"] and pm["cross_release"] and pm["n_sources"] >= 8
    assert abs(pm["scale"] - 1 / GAIN) < 2 * pm["scale_err"] and pm["scale_err"] < 0.01
    pk = _peak(df.sig, grid, st)
    # 16 stars × 25 box pixels ≈ 400 (correlated) samples: E[max |N(0,1)|] ≈ 3, so bound the max at 4σ and
    # the typical star at 2.5σ; the raw difference fails both by an order of magnitude
    assert np.max(pk) <= 4.0 and np.median(pk) <= 2.5, pk
    assert pm["static_z_after"] < 0.1 * pm["static_z_before"]
    assert "not interpreted" in pm["note"] and "QR2" in pm["note"]
    assert 0.9 < df.k < 1.3


def test_wavelength_dependent_gain_is_followed_per_bin(grid):
    """A chromatic release gain (−8 % to −2 % across the band): the per-bin scales follow it and the red and
    blue ends differ significantly; a single broadband scale (the bins forced to the global value) leaves the
    ends mis-scaled in opposite senses."""
    st = _scene(seed=22, flux=(300.0, 900.0))
    from spherex.constants import BANDS
    l0, l1, _ = BANDS[BAND]
    beta = np.log(0.98 / 0.92) / np.log(l1 / l0)                          # g: 0.92 at λmin → 0.98 at λmax
    ca, cb, sky, _ = _pair(st, _gain(st, 0.92, beta), grid, seed=32)
    df = diff(ca, cb, sky, photometric_match="force")
    bins = [b for b in df.photometric_match["bins"] if b["lam"] is not None and not b["pooled"]]
    assert len(bins) >= 12
    lam = np.array([b["lam"] for b in bins])
    s = np.array([b["scale"] for b in bins])
    e = np.array([b["err"] for b in bins])
    truth = 1 / (0.92 * (lam / l0) ** beta)
    assert np.median(np.abs(s - truth) / e) < 1.5                        # follows the chromatic gain
    blue, red = s[lam < np.percentile(lam, 25)].mean(), s[lam > np.percentile(lam, 75)].mean()
    assert blue - red > 0.03                                              # and resolves it
    assert df.photometric_match["tau"] > 0                                # bins not fully pooled
    assert np.max(_peak(df.sig, grid, st)) <= 4.0


def test_variable_star_and_mover_do_not_bias_the_scale(grid):
    """Two of 16 stars are not static: one brightens by 40 % in B (a variable), one moves 1.7 px (the
    target, excluded by position). The robust fit recovers the gain; the variable is the only static-position
    residual and is labelled as a cross-release residual, not 'brightened'; the mover is still a dipole
    'moved'. Teeth: an ordinary least-squares scale on the same pixels is pulled by the variable."""
    st = _scene(seed=23)
    stB = _gain(st, GAIN)
    stB[0] = replace(stB[0], flux=stB[0].flux * 1.4)                       # variable
    mover = Star(RA0 + 4 * PX, DEC0 - 6 * PX, 500.0, steep(BAND, 2.0))
    ca, cb, sky, fw = _pair(st + [mover], stB + [replace(_gain([mover], GAIN)[0], y=mover.y - 1.7 * PX)], grid, seed=33)
    xm, ym = _xy(grid, mover)
    df = diff(ca, cb, sky, exclude_xy=[(xm, ym), (xm, ym - 1.7)], exclude_r_px=3 * fw / grid.pix_arcsec)
    pm = df.photometric_match
    assert abs(pm["scale"] - 1 / GAIN) < 3 * pm["scale_err"]
    # OLS on the same calibration pixels is biased by the 40 % variable
    from spherex.cube import static_islands
    lab, _ = static_islands(ca.cube, ca.var, *_bat(ca, cb), sky, [(xm, ym)], 3 * fw / grid.pix_arcsec)
    A_, B_ = np.nanmean(ca.cube, 0)[lab > 0], np.nanmean(_bat(ca, cb)[0], 0)[lab > 0]
    ols = np.polyfit(B_[np.isfinite(A_ + B_)], A_[np.isfinite(A_ + B_)], 1)[0]
    assert abs(ols - 1 / GAIN) > abs(pm["scale"] - 1 / GAIN)
    peaks = _peak(df.sig, grid, st)
    far = np.array([np.hypot(*np.subtract(_xy(grid, s), (xm, ym))) > 3 * fw / grid.pix_arcsec for s in st])
    assert np.max(peaks[1:][far[1:]]) <= 4.0 and peaks[0] > 5.0           # only the variable remains
    assert pm["static_z_after"] < 0.1 * pm["static_z_before"]
    x0, y0 = _xy(grid, st[0])
    an = annotate(df, [(x0, y0), (xm, ym - 0.85)], fw / grid.pix_arcsec, grid.pix_arcsec, expected_pa=0.0,
                  pair=matched_pair(ca, cb))
    var_ann, mov_ann = an
    assert var_ann["kind"] == "monopole" and var_ann["label"].startswith("residual") and not var_ann["comparable"]
    assert mov_ann["kind"] == "dipole" and mov_ann["label"].startswith("moved")


def _bat(ca, cb):
    from spherex.cube import at_wavelengths
    fb, vb = at_wavelengths(ca.lam, cb.cube, cb.var, cb.lam, ca.band)
    return fb, vb


def test_same_release_reports_a_diagnostic_and_applies_nothing(grid):
    """Two QR3 visits: the match is computed as a calibration check (≈ 1) but never applied, so the
    difference is bit-identical to photometric_match='off', and monopoles keep their brightened/faded sign."""
    st = _scene(seed=24)
    ca, cb, sky, _ = _pair(st, st, grid, seed=34, relB="qr3")
    df, off = diff(ca, cb, sky), diff(ca, cb, sky, photometric_match="off")
    pm = df.photometric_match
    assert pm["applied"] is False and pm["cross_release"] is False and off.photometric_match is None
    assert abs(pm["scale"] - 1) < 3 * pm["scale_err"] and "consistent with 1" in pm["note"]
    assert np.array_equal(np.nan_to_num(df.sig), np.nan_to_num(off.sig))


def test_sparse_cross_release_field_is_refused_with_a_reason(grid):
    """No shared static sources → no match → no difference (never the raw QR2 − QR3)."""
    ca, cb, sky, _ = _pair([Star(RA0, DEC0, 200.0, 0.0)], [Star(RA0, DEC0, 186.0, 0.0)], grid, seed=35)
    with pytest.raises(ValueError, match="in-situ photometric match failed.*static sources"):
        diff(ca, cb, sky)
    with pytest.raises(ValueError, match="F4"):
        diff(ca, cb, sky, photometric_match="off")


def _islands_scene(rng, s_true, c_true, n_src=14, nb=4, ny=128, nx=128, fw=2.2, outliers=()):
    """Gaussian sources on a numpy grid: a = truth + noise, b = (truth − c)/s + noise; outliers: (k, factor)
    makes source k `factor`× brighter in B only."""
    yy, xx = np.mgrid[:ny, :nx]
    xs, ys = rng.uniform(6, nx - 6, n_src), rng.uniform(6, ny - 6, n_src)
    fl = rng.uniform(300, 3000, n_src)
    psf = [np.exp(-((xx - x) ** 2 + (yy - y) ** 2) / (2 * fw ** 2)) / (2 * np.pi * fw ** 2) for x, y in zip(xs, ys)]
    img = sum(f * p for f, p in zip(fl, psf))
    imgB = img + sum((fac - 1) * fl[k] * psf[k] for k, fac in outliers)
    sky = img < 0.05
    v = 1.0 + img / 50
    a = np.array([img + rng.normal(0, np.sqrt(v)) for _ in range(nb)])
    b = np.array([(imgB - c_true) / s_true + rng.normal(0, np.sqrt(v) / s_true) for _ in range(nb)])
    return a, np.array([v] * nb), b, np.array([v / s_true ** 2] * nb), np.full((nb, ny, nx), 2.0), sky


def test_bootstrap_errors_are_calibrated():
    """Research-grade check of the uncertainty: over 40 independent noise realisations the pulls
    (ŝ − s)/σ̂ have robust σ in [0.6, 1.6] and |mean| < 0.5 — the island bootstrap neither hides nor
    inflates the scale error (pixels of one PSF are correlated; a per-pixel formula would ignore that)."""
    pulls = []
    for seed in range(40):
        a, va, b, vb, lam, sky = _islands_scene(np.random.default_rng(1000 + seed), 1.075, 0.3)
        r = fit_relative_scale(a, va, b, vb, lam, sky, n_boot=80, seed=seed, scale_floor=0.0)   # the bootstrap alone
        pulls.append((r["scale"] - 1.075) / r["scale_err"])
    p = np.array(pulls)
    rs = 1.4826 * np.median(np.abs(p - np.median(p)))
    assert 0.6 < rs < 1.6 and abs(np.mean(p)) < 0.5, (rs, np.mean(p))


def test_breakdown_against_outlier_sources():
    """Three of 14 sources 2× brighter in B (variables, artefacts): the Tukey IRLS stays within 3σ of the
    truth. Teeth: one pass of weighted least squares on the same pixels is pulled > 5σ."""
    a, va, b, vb, lam, sky = _islands_scene(np.random.default_rng(7), 1.075, 0.0,
                                            outliers=((0, 2.0), (1, 2.0), (2, 2.0)))
    r = fit_relative_scale(a, va, b, vb, lam, sky, n_boot=80, scale_floor=0.0)
    assert abs(r["scale"] - 1.075) < 3 * r["scale_err"]
    from spherex.cube import _irls_scale, static_islands
    lab, _ = static_islands(a, va, b, vb, sky)
    m = lab > 0
    A_, B_, VA, VB = a.mean(0)[m], b.mean(0)[m], va.mean(0)[m] / 4, vb.mean(0)[m] / 4
    w = 1 / (VA + VB)
    mb, ma = (w * B_).sum() / w.sum(), (w * A_).sum() / w.sum()
    wls = (w * (B_ - mb) * (A_ - ma)).sum() / (w * (B_ - mb) ** 2).sum()
    assert abs(wls - 1.075) > 5 * r["scale_err"]
    del _irls_scale
