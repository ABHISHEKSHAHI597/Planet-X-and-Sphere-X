"""L1: λ-matched difference (G4a, implementation.md §10.1). Scene assumptions: tests/synthetic/scene.py.
Steep-spectrum static stars (×4 across band 4), peak S/N ≈ 45–150 per frame (bright, so that the naive
methods' false residuals clear 5σ and the teeth tests are stable), placed from −3.7′ to +3.7′ along the
LVF axis; visit B has the PA-flip gradient reversal AND the half-channel survey offset.
Static-star metric: method-induced residual = significance(scene) − significance(noise-only twin with the
same seed), peak in a 5×5 box per star, must stay ≤ 0.5σ; the absolute ≤ 3σ of implementation.md §10.1
is also asserted on one box per star."""
import numpy as np
import pytest

from spherex.cube import matched_difference, pair_frames, spectral_cube
from spherex.grid import significance
from spherex.stack import frame_weight, weighted_stack
from tests.synthetic.scene import Star, shifted, sky_mask, steep, visit

BAND = 4
SHAPE = (101, 101)
OFFSETS_PX = np.arange(-36, 37, 12)            # ±3.7′ at 6.15″/px
FLUX = 112.0


def _stars(flux=FLUX):
    a = steep(BAND, 4.0)
    return [Star(x=20 + 10 * k, y=50 + dy, flux=flux, alpha=a) for k, dy in enumerate(OFFSETS_PX)]


def _box_peak(sig, st, h=2):
    iy, ix = int(round(st.y)), int(round(st.x))
    return float(np.nanmax(np.abs(sig[iy - h:iy + h + 1, ix - h:ix + h + 1])))


def _cube(F, V, L, sky):
    w = [frame_weight(v, sky) for v in V]
    return spectral_cube(F, V, L, w, BAND)


def _visits(stars, seed):
    rng = np.random.default_rng(seed)
    A = visit(SHAPE, stars, BAND, rng, direction=+1, offset_ch=0.0, jitter_ch=0.1)
    B = visit(SHAPE, stars, BAND, rng, direction=-1, offset_ch=0.5, jitter_ch=0.1)
    return A, B


def _matched_sig(A, B, sky):
    d, v = matched_difference(_cube(*A[:3], sky), _cube(*B[:3], sky), BAND, sky)
    return significance(d, v, sky)


@pytest.fixture(scope="module")
def scene():
    stars = _stars()
    A, B = _visits(stars, 20261106)
    return stars, A, B, sky_mask(SHAPE, stars)


def test_synthetic_matched_difference_static_stars_cancel(scene):
    stars, A, B, sky = scene
    sig, k = _matched_sig(A, B, sky)
    sig0, _ = _matched_sig(*_visits(_stars(0.0), 20261106), sky)      # noise-only twin, same seed
    induced = [_box_peak(sig - sig0, st) for st in stars]
    assert max(induced) <= 0.5, induced
    assert all(abs(sig[int(st.y), int(st.x)]) <= 3.0 for st in stars)
    assert 0.8 < k < 1.3


def test_synthetic_naive_stack_difference_fails(scene):
    """Teeth: visit-stack A − visit-stack B (forbidden fallback, workflow.md §11.2) leaves false residuals."""
    stars, (Fa, Va, La, _), (Fb, Vb, Lb, _), sky = scene
    no = np.zeros_like(Fa, bool)
    ma, va, _ = weighted_stack(Fa, Va, [frame_weight(x, sky) for x in Va], no)
    mb, vb, _ = weighted_stack(Fb, Vb, [frame_weight(x, sky) for x in Vb], no)
    sig, _ = significance(ma - mb, va + vb, sky)
    assert max(_box_peak(sig, st) for st in stars) > 5.0


def test_synthetic_pairing_at_target_fails_off_centre(scene):
    """Teeth: pairing frames by λ at the target and differencing the whole field (forbidden for fields).
    The half-channel offset survives pairing at the target, and the gradient reversal grows off-centre."""
    stars, (Fa, Va, La, _), (Fb, Vb, Lb, _), sky = scene
    cy, cx = 50, 50
    ia, ib = pair_frames(La[:, cy, cx], Lb[:, cy, cx], BAND)
    assert ia.size >= 12
    d = np.nanmean(Fa[ia] - Fb[ib], axis=0)
    v = np.nanmean(Va[ia] + Vb[ib], axis=0) / ia.size
    sig, _ = significance(d, v, sky)
    peaks = [_box_peak(sig, st) for st in stars]
    assert max(peaks) > 5.0, peaks


def test_synthetic_mover_leaves_dipole():
    rng = np.random.default_rng(7)
    stars = _stars()
    mid = 3                                        # the star at the grid centre row
    A = visit(SHAPE, stars, BAND, rng, direction=+1)
    B = visit(SHAPE, shifted(stars, mid, 0.0, -1.7), BAND, rng, direction=-1, offset_ch=0.5)
    sky = sky_mask(SHAPE, stars)
    d, v = matched_difference(_cube(*A[:3], sky), _cube(*B[:3], sky), BAND, sky)
    sig, _ = significance(d, v, sky)
    st = stars[mid]
    box = sig[int(st.y) - 4:int(st.y) + 3, int(st.x) - 3:int(st.x) + 4]
    assert np.nanmax(box) >= 10 and np.nanmin(box) <= -10      # + at new (A) position, − at old (B)
    assert all(abs(sig[int(s.y), int(s.x)]) <= 3.0 for i, s in enumerate(stars) if i != mid)


def test_synthetic_pair_frames_half_channel_offsets_pair():
    from spherex.constants import BANDS
    from spherex.cube import CH_LN
    lo = BANDS[BAND][0]
    la = lo * np.exp((np.arange(17) + 0.5) * CH_LN[BAND])
    lb = la * np.exp(0.5 * CH_LN[BAND])                     # half a channel redder
    ia, ib = pair_frames(la, lb, BAND)
    assert ia.size == 17 and np.all(ia == ib)
    ia, ib = pair_frames(la, la * np.exp(0.8 * CH_LN[BAND]), BAND)   # beyond 0.75 channel
    assert ia.size == 0
