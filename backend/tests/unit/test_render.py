"""L0: display encoding, stretch, fill, flipbook, contract golden (implementation.md §5.2, §6.3, §4.3, §7)."""
from pathlib import Path

import numpy as np

from spherex.cube import flipbook_order
from spherex.render import (
    FORMAT_F16,
    blink25_plan,
    golden_F,
    normalise_epoch,
    rgb,
    shared_limits,
    stretch,
    to_f16,
    to_f32,
    to_u8,
    to_u32_flags,
)
from spherex.stack import display_fill

GOLD = Path(__file__).parents[3] / "frontend/fixtures/golden/stack_F_121x121.f16"


def test_to_f16_sentinel_and_clip():
    a = np.array([np.nan, np.inf, -np.inf, 1.5, 1e6, -1e6])
    out = np.frombuffer(to_f16(a), "<f2")
    assert list(out[:3]) == [-65504.0] * 3
    assert out[3] == 1.5 and out[4] == np.float16(6.5e4) and out[5] == np.float16(-5e4)
    assert np.all(np.isfinite(out))


def test_science_payloads_keep_nan_and_flags_are_u32le():
    a = np.array([[1.0, np.nan]])
    f = np.frombuffer(to_f32(a), "<f4")
    assert f[0] == 1.0 and np.isnan(f[1])
    assert np.frombuffer(to_u32_flags(np.array([1 << 29, 3], np.uint32)), "<u4").tolist() == [1 << 29, 3]


def test_golden_F_contract_file_and_orientation():
    """workflow.md §7.3: the committed golden equals the encoder's output bit for bit, and the F sits in
    the north-east (high rows = north, low columns = east) of the row-0-south layout."""
    g = golden_F(121)
    assert GOLD.read_bytes() == to_f16(g) and FORMAT_F16.startswith("f16le-row0south")
    f = np.nan_to_num(g) == 100
    ys, xs = np.nonzero(f)
    assert ys.min() > 60 and xs.max() < 60                      # NE quadrant
    top = f[ys.max()]                                           # top bar extends west (to higher columns)
    assert np.nonzero(top)[0].max() - np.nonzero(top)[0].min() >= 15
    raw = np.frombuffer(GOLD.read_bytes(), "<f2").reshape(121, 121)
    assert (raw[:3, 118:] == -65504).all() and raw[60, 60] == -65504
    assert raw[0, 100] > raw[0, 10]                             # ramp brightens westward along the south edge


def test_shared_limits_from_median_stack_ignore_one_bright_frame():
    rng = np.random.default_rng(0)
    stacks = rng.normal(size=(4, 50, 50))
    stacks[2] += 100                                   # one frame much brighter: limits must not follow it
    lo, hi = shared_limits(stacks)
    assert -5 < lo < hi < 5
    assert shared_limits(stacks, "manual:-1,2") == (-1.0, 2.0)
    lo, hi = shared_limits(stacks, "p99.5")
    assert lo < hi


def test_per_frame_stretch_flickers_teeth():
    """Teeth (workflow.md §11.2): per-frame limits make an unchanged star look variable; shared don't."""
    rng = np.random.default_rng(3)
    frames = rng.normal(size=(2, 40, 40))
    frames[:, 20, 20] = 30.0                               # same star brightness in both frames
    frames[1, :5, :5] = 400.0                              # unrelated bright artifact in frame 2 only
    per = [stretch(f, *shared_limits([f], "p99.5"), "lin")[20, 20] for f in frames]
    lo, hi = shared_limits(frames, "p99.5")
    shared = [stretch(f, lo, hi, "lin")[20, 20] for f in frames]
    assert abs(per[0] - per[1]) > 0.1 and abs(shared[0] - shared[1]) < 1e-9


def test_stretch_matches_shader_endpoints():
    for mode in ("lin", "asinh", "log", "sqrt"):
        t = stretch(np.array([-1.0, 0.0, 10.0, 20.0, np.nan]), 0.0, 10.0, mode)
        assert t[0] == 0 and t[1] == 0 and np.isclose(t[2], 1) and t[3] == 1 and np.isnan(t[4])
    assert np.allclose(stretch(np.array([-5.0, 0.0, 5.0]), 0, 5, "diverging"), [0, 0.5, 1])
    assert list(to_u8(np.array([0.0, 1.0, np.nan]))) == [0, 255, 0]
    c = rgb(np.ones((2, 2)), np.zeros((2, 2)), np.full((2, 2), np.nan), [(0, 1)] * 3, "lin")
    assert c.shape == (2, 2, 3) and c[0, 0, 0] == 1 and c[0, 0, 1] == 0 and np.isnan(c[0, 0, 2])


def test_display_fill_only_fills_core_holes():
    mean = np.ones((5, 5)); mean[2, 2] = np.nan; mean[0, 0] = np.nan
    model = np.full((5, 5), 7.0)
    core = np.zeros((5, 5), bool); core[1:4, 1:4] = True
    out, filled = display_fill(mean, model, core)
    assert out[2, 2] == 7.0 and np.isnan(out[0, 0]) and filled.sum() == 1
    assert np.isnan(mean[2, 2])                        # the measurement array is untouched


def test_flipbook_sorted_by_lambda_and_decimated():
    lam = np.array([3.0, 2.5, 3.5, 2.7])
    assert list(flipbook_order(lam, mjd=[1, 2, 3, 4])) == [1, 3, 0, 2]
    assert list(flipbook_order(lam, mjd=[4, 3, 2, 1], sort="time")) == [3, 2, 1, 0]
    assert flipbook_order(np.arange(200.0), np.arange(200.0)).size == 64


def test_normalise_epoch_unit_sky_sigma_and_blink25_plan():
    rng = np.random.default_rng(1)
    img = 50 + 3 * rng.normal(size=(60, 60))
    z = normalise_epoch(img, np.ones(img.shape, bool))
    assert abs(np.median(z)) < 0.05 and abs(np.std(z) - 1) < 0.05
    assert np.isnan(normalise_epoch(img, np.zeros(img.shape, bool))).all()
    assert np.allclose(blink25_plan(4.55, 1.0), (6.825, 6.15))                 # Barnard 2MASS → SPHEREx: FOV ≥ 1.5 × jump
    assert blink25_plan(2.2, 1.375, fov_arcmin=6.0) == (6.0, 6.15)
