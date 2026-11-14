"""L1: the full Role I chain on native synthetic frames: RawFrame → calibrate → QA → reproject (TAN-SIP,
PA 0°/180°) → stacks / cubes / λ-matched difference. Scene assumptions: tests/synthetic/scene.py (part B).
Band 4 steep spectra (×4 across the band) for the difference tests; band 6 elsewhere. Each trap has a
test in which the naive method fails (workflow.md §4.2)."""
from dataclasses import replace

import numpy as np
import pytest

from spherex.cube import DIFF_ORDER, annotate, build_cube, diff, diff_fwhm_arcsec, matched_pair, null_halves, shift_pa
from spherex.epochs import time_bins
from spherex.grid import frame_to_grid, make_grid, registration_offsets, significance
from spherex.movers import detect
from spherex.preprocess import calibrate
from spherex.stack import bright_display, build_stack, sky_pixels
from tests.synthetic.scene import (
    DET,
    PIXEL_ARCSEC,
    Star,
    SynthCalib,
    native_frame,
    native_visit,
    pipeline,
    steep,
    table_epsf,
    visit_mjds,
)

RA0, DEC0, BAND = 150.0, 10.0, 4
CAL = SynthCalib((4, 6))
PX = PIXEL_ARCSEC / 3600


def _stars(flux, alpha=None):
    a = steep(BAND, 4.0) if alpha is None else alpha
    offs = np.arange(-36, 37, 12) * PX                                  # ±3.7′ along the LVF axis
    return [Star(RA0 + (k - 3) * 10 * PX / np.cos(np.radians(DEC0)), DEC0 + o, flux, a) for k, o in enumerate(offs)]


def _tb(gs, band=BAND):
    return time_bins([g.mjd for g in gs], [band] * len(gs), "visit")[band][0]


def _diff_pair(starsA, starsB, seed, grid, order=DIFF_ORDER, homog=True, sysd=True, **kw):
    rng = np.random.default_rng(seed)
    A, _ = native_visit(starsA, BAND, rng, RA0, DEC0, pa=0.0, calib=CAL, size=101, visit_tag="A", mjd0=61200, **kw)
    B, _ = native_visit(starsB, BAND, rng, RA0, DEC0, pa=180.0, offset_ch=0.5, calib=CAL, size=101, visit_tag="B",
                        mjd0=61020, **kw)
    out = []
    for F in (A, B):
        gs = [frame_to_grid(calibrate(f, CAL), grid) for f in F]                      # stacks: bilinear
        gd = [frame_to_grid(calibrate(f, CAL), grid, order) for f in F]               # difference path
        out.append((build_stack(gs, _tb(gs), grid), gd))
    (sa, ga), (sb, gb) = out
    fw = diff_fwhm_arcsec(ga, gb) if homog else None
    ca, cb = build_cube(ga, sa.bin, BAND, grid, homog_fwhm_arcsec=fw), build_cube(gb, sb.bin, BAND, grid, homog_fwhm_arcsec=fw)
    sky = sky_pixels(sa) & sky_pixels(sb)
    df = diff(ca, cb, sky, **({} if sysd else dict(sys_frac=0.0, sys_shift_px=0.0)))
    return sa, sb, ca, cb, df, sky, fw


def _box(img, x, y, h=2):
    return float(np.nanmax(np.abs(img[int(round(y)) - h:int(round(y)) + h + 1, int(round(x)) - h:int(round(x)) + h + 1])))


def _xy(grid, st):
    return tuple(float(v) for v in grid.wcs.world_to_pixel_values(st.x, st.y))


@pytest.fixture(scope="module")
def grid():
    return make_grid(RA0, DEC0, 8.6)


@pytest.mark.parametrize("flux", [25.0, 400.0])
def test_synthetic_native_matched_difference_static_stars_cancel(grid, flux):
    """G4a L1 through the real chain: PA flip + half-channel offset + steep spectra + SIP + dithers.
    Peak S/N per frame ≈ 6 (flux 25) to ≈ 90 (flux 400)."""
    st = _stars(flux)
    *_, df, sky, _ = _diff_pair(st, st, 11, grid)
    assert max(_box(df.sig, *_xy(grid, s)) for s in st) <= 3.0
    assert 0.9 < df.k < 1.3


def test_synthetic_resampling_trap_teeth(grid):
    """Teeth: the documented path (bilinear, no PSF homogenisation, no resampling systematics) leaves
    static-star residuals ≫ 3σ at peak S/N ≈ 90 per frame, because each cube bin holds one resampled
    frame of an undersampled PSF (decision record 0003)."""
    st = _stars(400.0)
    *_, df, _, _ = _diff_pair(st, st, 11, grid, order="bilinear", homog=False, sysd=False)
    assert max(_box(df.sig, *_xy(grid, s)) for s in st) > 10.0


def test_synthetic_native_naive_stack_difference_fails(grid):
    st = _stars(400.0)
    sa, sb, *_, sky, _ = _diff_pair(st, st, 11, grid)
    sig, _ = significance(sa.mean - sb.mean, sa.var + sb.var, sky)
    assert max(_box(sig, *_xy(grid, s)) for s in st) > 5.0


def test_synthetic_native_mover_dipole_and_template_shift(grid):
    """A 1.7 px northward mover (A is the later visit): ≥ 10σ lobes, the template shift recovers
    1.7 px at PA 0°, the label says 'moved', and other stars stay < 3σ."""
    st = _stars(100.0)
    stB = list(st); stB[3] = replace(st[3], y=st[3].y - 1.7 * PX)
    sa, sb, ca, cb, df, sky, fw = _diff_pair(st, stB, 12, grid)
    x, y = _xy(grid, st[3])
    box = df.sig[int(y) - 4:int(y) + 4, int(x) - 4:int(x) + 4]
    assert np.nanmax(box) >= 10 and np.nanmin(box) <= -10
    an = annotate(df, [(x, y - 0.85)], fw / PIXEL_ARCSEC, PIXEL_ARCSEC, expected_pa=0.0, pair=matched_pair(ca, cb))[0]
    assert an["kind"] == "dipole" and abs(an["shift_px"] - 1.7) < 0.15 and abs((an["pa_deg"] + 180) % 360 - 180) < 8
    assert an["label"].startswith("moved")
    assert an["y2"] - an["y1"] == pytest.approx(an["dy"]) and an["x2"] - an["x1"] == pytest.approx(an["dx"])  # arrow B → A
    assert annotate(df, [(x, y - 0.85)], fw / PIXEL_ARCSEC, PIXEL_ARCSEC, expected_pa=180.0,
                    pair=matched_pair(ca, cb))[0]["label"].startswith("dipole (not")  # A → B is the wrong prediction
    assert all(_box(df.sig, *_xy(grid, s)) <= 3.0 for i, s in enumerate(st) if i != 3)


def test_synthetic_native_variable_monopole(grid):
    st = _stars(100.0)
    stA = list(st); stA[3] = replace(st[3], flux=150.0)
    sa, sb, ca, cb, df, sky, fw = _diff_pair(stA, st, 13, grid)
    x, y = _xy(grid, st[3])
    an = annotate(df, [(x, y)], fw / PIXEL_ARCSEC, PIXEL_ARCSEC)[0]
    assert an["kind"] == "monopole" and an["label"] == "brightened"


def test_synthetic_stack_unbiased_through_pipeline(grid):
    """G2 'stack flux unbiasedness' (L1) with zodi, flags, SIP and PA 180: stacked surface brightness
    integrated over the star equals the noiseless truth within 1%."""
    rng = np.random.default_rng(5)
    st = [Star(RA0, DEC0, 2000.0, 0.0)]
    F, models = native_visit(st, 6, rng, RA0, DEC0, pa=180.0, calib=CAL, size=61, gain=5.0, visit_tag="U")
    g = make_grid(RA0, DEC0, 4.0)
    gs, _ = pipeline(F, CAL, g)
    s = build_stack(gs, _tb(gs, 6), g)
    truth = np.mean([np.nansum(m) for m in models])                     # total flux per native frame
    x, y = _xy(g, st[0])
    yy, xx = np.indices(g.shape)
    flux = np.nansum(np.where(np.hypot(xx - x, yy - y) < 8, s.mean, 0.0))
    assert abs(flux / truth - 1) < 0.01


def test_synthetic_registration_offsets_between_pa_flipped_visits():
    """The G2 registration check's machinery: static stars between PA 0° and PA 180° visits (SIP,
    dithers, ±1° roll) on the common grid show a median offset < 0.1 px."""
    rng = np.random.default_rng(6)
    from tests.synthetic.scene import field
    st = field(RA0, DEC0, rng, n=25, radius_deg=0.03, flux=(60.0, 300.0))
    g = make_grid(RA0, DEC0, 4.0)
    S = []
    for pa, tag in ((0.0, "R0"), (180.0, "R1")):
        F, _ = native_visit(st, 6, rng, RA0, DEC0, pa=pa, calib=CAL, size=61, visit_tag=tag)
        gs, _ = pipeline(F, CAL, g)
        S.append(build_stack(gs, _tb(gs, 6), g))
    xy = [_xy(g, s) for s in st]
    xy = [p for p in xy if 5 < p[0] < g.shape[1] - 6 and 5 < p[1] < g.shape[0] - 6]
    d = registration_offsets(S[0].mean, S[1].mean, xy)
    assert len(d) >= 8 and np.hypot(*np.median(d, 0)) < 0.1


def test_synthetic_bright_target_presets_fill_and_masked_core_shift():
    """Saturated core (NaN + OVERFLOW|SUR_ERROR) with a BLOOM/HALO footprint. Teeth: the imaging preset
    masks the whole star; the bright preset keeps its wings. The display fill fills only the core and
    never touches the measurement array; the template shift still measures a mover with a masked core."""
    rng = np.random.default_rng(7)
    st = [Star(RA0, DEC0, 4000.0, 0.0)]
    g = make_grid(RA0, DEC0, 4.0)
    F, _ = native_visit(st, 6, rng, RA0, DEC0, calib=CAL, size=61, sat_nan=600.0, sat_flag=150.0, visit_tag="S")
    x, y = _xy(g, st[0])
    yy, xx = np.indices(g.shape)
    ring = (np.hypot(xx - x, yy - y) > 1.5) & (np.hypot(xx - x, yy - y) < 2.5)
    gi, _ = pipeline(F, CAL, g, preset="imaging")
    gb, _ = pipeline(F, CAL, g, preset="bright")
    si, sb = build_stack(gi, _tb(gi, 6), g), build_stack(gb, _tb(gb, 6), g)
    assert np.isnan(si.mean[ring]).mean() > 0.9 and np.isfinite(sb.mean[ring]).mean() > 0.6
    assert np.isnan(sb.mean[int(round(y)), int(round(x))])                       # the hole stays in `mean`

    class Gauss:                                                                  # stand-in for M's ePSF fit
        def render(self, grid):
            s = 1.46 / 2.3548
            return 4000.0 * np.exp(-((xx - x) ** 2 + (yy - y) ** 2) / (2 * s * s)) / (2 * np.pi * s * s)
    bright_display(sb, Gauss(), x, y, 2.5)
    assert sb.filled.any() and np.isfinite(sb.display[sb.filled]).all() and np.isnan(sb.mean[sb.filled]).all()

    stB = [replace(st[0], y=st[0].y - 1.7 * PX)]
    gds = []
    for stars, pa, tag, m0 in ((st, 0.0, "SA", 61200), (stB, 180.0, "SB", 61020)):
        Fv, _ = native_visit(stars, 6, rng, RA0, DEC0, pa=pa, calib=CAL, size=61, sat_nan=600.0, visit_tag=tag, mjd0=m0)
        gds.append([frame_to_grid(calibrate(f, CAL, "bright"), g, DIFF_ORDER) for f in Fv])
    fw = diff_fwhm_arcsec(*gds)
    ca, cb = (build_cube(gd, _tb(gd, 6), 6, g, homog_fwhm_arcsec=fw) for gd in gds)
    from spherex.cube import fit_shift
    t = fit_shift(*matched_pair(ca, cb), x, y - 0.85)
    assert abs(t["shift_px"] - 1.7) < 0.2 and abs((shift_pa(t["dx"], t["dy"]) + 180) % 360 - 180) < 10


def test_synthetic_null_test_and_occupancy(grid):
    """G4a null test (L1): two halves of one visit (alternating in λ) → k ≈ 1, stars < 3σ (needs
    max_interp_ch = 3 to bridge each half's missing channels). F16 (L1): ≈1 sample per cube bin."""
    rng = np.random.default_rng(8)
    st = _stars(100.0)
    F, _ = native_visit(st, BAND, rng, RA0, DEC0, nframes=34, calib=CAL, size=101, visit_tag="N")
    gd = [frame_to_grid(calibrate(f, CAL), grid, DIFF_ORDER) for f in F]
    tb = _tb(gd)
    c = grid.shape[0] // 2
    ia, ib = null_halves([np.nanmedian(g.lam[c - 1:c + 2, c - 1:c + 2]) for g in gd])
    assert set(ia).isdisjoint(ib) and len(ia) + len(ib) == 34
    fw = diff_fwhm_arcsec(gd, gd)
    A = build_cube([gd[i] for i in ia], tb, BAND, grid, homog_fwhm_arcsec=fw)
    B = build_cube([gd[i] for i in ib], tb, BAND, grid, homog_fwhm_arcsec=fw)
    gs = [frame_to_grid(calibrate(f, CAL), grid) for f in F]
    df = diff(A, B, sky_pixels(build_stack(gs, tb, grid)), max_interp_ch=3.0)
    assert 0.8 < df.k < 1.3 and max(_box(df.sig, *_xy(grid, s)) for s in st) <= 3.0
    one = build_cube(gd[:17], tb, BAND, grid).nhits[:, c, c]
    assert (one == 1).mean() >= 0.8 and one.max() <= 2


def test_synthetic_partial_visit_trap():
    """Partial visits (3 · 16 · 3 · 21 frames in band 6, WISE-0855-like dates): classified 2 full + 2
    partial. Teeth: treating every cluster as a blink epoch shows 4 'full' epochs, two of them ≈1 mag
    shallower (√(16/3) ≈ 2.3× noisier)."""
    mjd, det = visit_mjds([3, 16, 3, 21], [60800.0, 60980.0, 61021.0, 61152.0], spacing_days=0.6)
    b6 = time_bins(mjd, det, "visit")[6]
    assert [(b.status, b.idx.size) for b in b6] == [("partial", 3), ("full", 16), ("partial", 3), ("full", 21)]
    naive = [b for b in b6]                                           # all clusters as epochs
    assert len(naive) == 4 and 2.5 * np.log10(np.sqrt(16 / 3)) > 0.9


def test_synthetic_qr2_scale_guard():
    """No QR2/QR3 photometry mixing before F4 (workflow.md §11.2): QR2 frames stay labelled 'qr2' and
    unscaled unless F4's direction is passed explicitly."""
    rng = np.random.default_rng(9)
    cal = SynthCalib((6,), fluxcorr=1.25)
    f, _ = native_frame([Star(RA0, DEC0, 500.0)], 6, rng, RA0, DEC0, 8.5, calib=cal, release="qr2")
    cf0, cfm, cfd = (calibrate(f, cal, fluxcorr_op=op) for op in (None, "multiply", "divide"))
    assert cf0.photometric_scale == "qr2" and cfm.photometric_scale == cfd.photometric_scale == "qr3"
    peak = lambda c: np.nanmax(c.sci)
    assert np.isclose(peak(cfm) / peak(cf0), 1.25, rtol=0.02) and np.isclose(peak(cfd) / peak(cf0), 0.8, rtol=0.02)


def test_synthetic_detection_native_only_and_transients():
    rng = np.random.default_rng(10)
    g = make_grid(RA0, DEC0, 4.0)
    F, _ = native_visit([Star(RA0, DEC0, 60.0)], 6, rng, RA0, DEC0, calib=CAL, size=61, visit_tag="D")
    for i, f in enumerate(F[:8]):                                   # an asteroid: 2-pixel blob, one per frame
        img = f.hdus["IMAGE"][1]
        img[10 + 2 * i, 12:14] += 40.0
    gs, _ = pipeline(F, CAL, g)
    s = build_stack(gs, _tb(gs, 6), g)
    sig, _ = significance(s.mean, s.var, sky_pixels(s))
    cat = detect(sig, pix_arcsec=g.pix_arcsec)
    assert cat.size >= 1 and min(np.hypot(cat["x"] - (g.shape[1] - 1) / 2, cat["y"] - (g.shape[0] - 1) / 2)) < 1.0
    with pytest.raises(ValueError):
        detect(sig, pix_arcsec=3.0)
    assert len(s.transients) >= 6                                    # rejected blobs → asteroid queue (P2-5)


def test_synthetic_qa_rejects_and_lists_skipped():
    rng = np.random.default_rng(11)
    g = make_grid(RA0, DEC0, 4.0)
    F, _ = native_visit([], 6, rng, RA0, DEC0, nframes=3, calib=CAL, size=61, visit_tag="Q")
    F[1] = native_frame([], 6, rng, RA0, DEC0, 5.5, calib=CAL, size=61, finast=3, obsid="SYNTHQ_9999_1")[0]
    gs, skipped = pipeline(F, CAL, g)
    s = build_stack(gs, _tb(gs, 6), g, skipped)
    assert len(gs) == 2 and s.skipped == [("SYNTHQ_9999_1D6.fits", "FINAST=3")]


def test_synthetic_generator_produces_the_traps():
    """G0 (L0): the generator really produces each declared trap."""
    rng = np.random.default_rng(12)
    lam = CAL.cwave[4]
    assert lam[DET - 1, DET // 2] > lam[0, DET // 2]                          # LVF along parent y
    a, _ = native_frame([], 4, rng, RA0, DEC0, 8.5, pa=0.0, calib=CAL)
    b, _ = native_frame([], 4, rng, RA0, DEC0, 8.5, pa=180.0, calib=CAL)
    north = lambda f: f.wcs.world_to_pixel_values(RA0, DEC0 + 10 * PX)[1] - f.wcs.world_to_pixel_values(RA0, DEC0)[1]
    assert north(a) > 0 > north(b)                                            # PA flip reverses the gradient on the sky
    c, _ = native_frame([], 4, rng, RA0, DEC0, 9.0, calib=CAL)
    # half a channel = 60 parent rows: the target moves 60 rows up the LVF (CRPIX2A = 1 − origin y)
    assert abs((a.hdus["IMAGE"][0]["CRPIX2A"] - c.hdus["IMAGE"][0]["CRPIX2A"]) - 60) <= 1
    assert a.hdus["IMAGE"][0]["CTYPE1"].endswith("SIP") and "A_2_0" in a.hdus["IMAGE"][0]
    t = table_epsf()
    assert not np.allclose(t, t[::-1, ::-1])                                 # asymmetric table PSF
    s, _ = native_frame([Star(RA0, DEC0, 5000.0)], 6, rng, RA0, DEC0, 8.5, calib=CAL, sat_nan=600.0, n_cr=10)
    img, flg = s.hdus["IMAGE"][1], s.hdus["FLAGS"][1]
    assert np.isnan(img).any() and (flg & 2).any() and (flg & 1).any()      # NaN core, OVERFLOW, TRANSIENT
    mjd, det = visit_mjds([3, 16], [60800.0, 60980.0])
    assert np.sum(det == 6) == 19


def test_synthetic_difference_refuses_mixed_photometric_scales(grid):
    """Forbidden fallback (workflow.md §11.2): never a *raw* QR2 − QR3 difference before F4. Mixed scales need
    the in-situ photometric match (decision record 0008); an empty field cannot be matched, so it is refused.
    allow_mixed_scales=True is the validation-only raw path."""
    rng = np.random.default_rng(14)
    out = []
    for rel, tag in (("qr3", "M3"), ("qr2", "M2")):
        F, _ = native_visit([], 6, rng, RA0, DEC0, nframes=3, calib=CAL, size=61, visit_tag=tag, release=rel)
        gd = [frame_to_grid(calibrate(f, CAL), grid) for f in F]
        out.append(build_cube(gd, _tb(gd, 6), 6, grid))
    with pytest.raises(ValueError, match="F4"):
        diff(out[0], out[1], np.ones(grid.shape, bool))
    assert diff(out[0], out[1], np.ones(grid.shape, bool), allow_mixed_scales=True).band == 6


def test_synthetic_smooth_background_for_large_boxes():
    """implementation.md §4.3: boxes > 10′ get a 2-D background (atmospheric lines vary along the LVF);
    a scalar median leaves the gradient in."""
    rng = np.random.default_rng(15)
    f, _ = native_frame([], 6, rng, RA0, DEC0, 8.5, calib=CAL, size=121, zodi=(5.0, 0.0))
    img = f.hdus["IMAGE"][1]
    img += np.linspace(-3, 3, 121)[:, None].astype(np.float32)          # residual line gradient along y
    auto, flat = calibrate(f, CAL), calibrate(f, CAL, smooth_bkg=False)   # 121 px ≈ 12.4′ → auto smooth
    rows = lambda c: np.nanmedian(c.sci, axis=1)
    assert np.ptp(rows(flat)) > 5.0 and np.ptp(rows(auto)[10:-10]) < 1.0
