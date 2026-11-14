"""L2: real calibration conventions (F1, F3) on committed slices of the QR3 calibration products
(tests/data/real/calib_fixture_slices.provenance.json) and the Barnard QR3 cutout fixture."""
import io
from pathlib import Path

import numpy as np
from astropy.io import fits
from scipy.interpolate import RegularGridInterpolator

from spherex.calib import parent_origin, parent_slice
from spherex.constants import BANDS
from spherex.cube import CH_LN

D = Path(__file__).parents[1] / "data/real"


def _table(stem):
    h = fits.Header.fromstring((D / f"cal_{stem}.hdr").read_text())
    raw = (D / f"cal_{stem}.bin").read_bytes()
    buf = fits.PrimaryHDU().header.tostring().encode() + h.tostring().encode() + raw + b"\0" * (-len(raw) % 2880)
    with fits.open(io.BytesIO(buf)) as hl:
        return hl[1].data.copy()


def _lookup(xf, yf):
    t = _table("wcswave_D6")
    f = RegularGridInterpolator((t["Y"][0].astype(float), t["X"][0].astype(float)),
                                np.asarray(t["VALUES"][0], float)[..., 0], bounds_error=False, fill_value=None)
    return f(np.stack([yf, xf], -1))


def test_real_f1_cwave_matches_wcswave_through_cutout_origin():
    """F1 on the cutout path: CWAVE[parent_slice(CRPIXnA)] vs the WCS-WAVE lookup through alt WCS W."""
    with fits.open(D / "barnard_qr3_d6_29x29_hdu0-4.fits") as hl:
        hi = hl["IMAGE"].header
    cw = np.load(D / "cwave_D6_fixture_slice.npy").astype(float)
    assert parent_slice(parent_origin(hi), cw.shape) == np.s_[1919:1948, 638:667]
    yy, xx = np.mgrid[0:29, 0:29].astype(float)
    px = hi["CRVAL1W"] + hi["CDELT1W"] * (xx + 1 - hi["CRPIX1W"])
    py = hi["CRVAL2W"] + hi["CDELT2W"] * (yy + 1 - hi["CRPIX2W"])
    d = np.abs(_lookup(px, py) - cw) * 1e3
    assert np.percentile(d, 99) < 3.0                               # nm
    flipped = np.abs(_lookup(px, 2041.0 - py) - cw) * 1e3            # teeth: a y-flip is far off
    assert np.percentile(flipped, 1) > 50.0


def test_real_f3_channel_map_meaning():
    """F3: CHANNEL_MAP (HDU 1) holds 0 (blueward), 1–17, 18 (redward); it matches CWAVE's channel."""
    ch = np.load(D / "channel_map_fixture_slice.npy")
    cw = np.load(D / "cwave_D6_fixture_slice.npy")
    t = _table("spectral_channels")
    t6 = t[t["DETECTOR"] == 6]
    from_cw = np.searchsorted(t6["WL_MAX"], cw) + 1
    assert set(np.unique(ch)) <= set(range(19))
    assert (np.abs(from_cw.astype(int) - ch.astype(int)) <= 1).all()
    lo = BANDS[6][0]
    dev = np.log(t6["WAVELENGTH"] / (lo * np.exp((np.arange(17) + 0.5) * CH_LN[6]))) / CH_LN[6]
    assert np.abs(dev).max() < 0.5                                  # equal-ln bins are within ½ channel
