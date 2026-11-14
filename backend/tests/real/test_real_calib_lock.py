"""L2: the locked QR3 calibration files themselves (needs `scripts/bootstrap_calib.py fetch`; skipped where
they are not bootstrapped, e.g. offline CI without the ≈450 MB cache). Cross-checks the locked full maps
against the slices I committed for F1/F3 (tests/data/real/*_fixture_slice.npy)."""
import os
from pathlib import Path

import numpy as np
import pytest

from spherex.calib import Calib, CalibrationLock, parent_slice

REAL = Path(__file__).parents[1] / "data/real"
ROOT = Path(os.environ.get("PARALLAX_CALIB", Path.home() / ".cache/parallax/calib"))
LOCK = CalibrationLock.load()
pytestmark = pytest.mark.skipif(not all((ROOT / e.s3_key).exists() for e in LOCK.entries),
                                reason="locked calibration not bootstrapped (scripts/bootstrap_calib.py fetch)")


@pytest.fixture(scope="module")
def cal():
    return Calib(ROOT, verify=True)                      # sha256 of all 25 files against the lock


def test_lock_complete_and_verified(cal):
    assert LOCK.complete and len(LOCK.entries) == 25


def test_locked_maps_match_committed_slices(cal):
    ps = parent_slice((638, 1919), (29, 29))
    assert np.array_equal(np.asarray(cal.cwave[6][ps]), np.load(REAL / "cwave_D6_fixture_slice.npy"))
    assert np.array_equal(np.asarray(cal.channel[ps]), np.load(REAL / "channel_map_fixture_slice.npy"))


def test_map_shapes_types_and_ranges(cal):
    from spherex.constants import BANDS
    assert cal.channel.shape == (2040, 2040) and cal.channel.dtype == np.uint8 and int(cal.channel.max()) <= 18
    for d in range(1, 7):
        cw = np.asarray(cal.cwave[d])
        lo, hi = BANDS[d][:2]
        fin = cw[np.isfinite(cw)]
        assert cw.shape == (2040, 2040) and np.percentile(fin, 1) > lo - 0.05 and np.percentile(fin, 99) < hi + 0.05
        assert np.asarray(cal.cband[d]).shape == (2040, 2040)
        assert np.asarray(cal.fluxcorr[d]).shape == (2040, 2040)
        assert np.asarray(cal.solid_angle[d]).shape == (2040, 2040)
