"""L2: real headers. Fixtures (see provenance sidecars): barnard_qr3_d6_29x29_hdu0-4.fits (QR3 7.0.5 cutout,
HDUs 0–4), flags_headers_by_version.json (FLAGS headers of real QR2 6.4+psffix1, 6.5.6 and QR3 7.0.5 frames)."""
import json
from pathlib import Path

import numpy as np
import pytest
from astropy.io import fits
from astropy.wcs import WCS

from spherex.calib import parent_origin
from spherex.epochs import survey_number
from spherex.flags import CANONICAL_BITS, PRESETS, bad_mask, canonical, flag_bits
from spherex.preprocess import calibrate, frame_qa
from spherex.types import CalFrame, RawFrame

D = Path(__file__).parents[1] / "data/real"
FIX = D / "barnard_qr3_d6_29x29_hdu0-4.fits"


def _hdus():
    with fits.open(FIX) as hl:
        return {n: (hl[n].header.copy(), hl[n].data.copy()) for n in ("IMAGE", "FLAGS", "VARIANCE", "ZODI")}


def _versions():
    return {v: fits.Header.fromstring(d["flags_header"]) for v, d in json.loads((D / "flags_headers_by_version.json").read_text()).items()}


def test_real_flag_bits_match_documented_table():
    bits = flag_bits(_hdus()["FLAGS"][0])
    for name, value in bits.items():
        assert value == 1 << CANONICAL_BITS[name], name     # every header plane agrees with the doc
    # R7 7.0.5 file: SATELLITE_HALO (bit 29) is absent from the header (foundation check F6 finding)
    assert set(CANONICAL_BITS) - set(bits) == {"SATELLITE_HALO", "PHANTOM", "REFERENCE"}


def test_real_qr2_flags_use_mp_convention():
    """F6: QR2 (6.x) headers declare planes as HIERARCH MP_<NAME> = <bit>; the MSKN-only parser saw none."""
    hv = _versions()
    assert set(hv) == {"6.4+psffix1", "6.5.6", "7.0.5"}
    for v, h in hv.items():
        bits = flag_bits(h)
        assert all(b == 1 << CANONICAL_BITS[n] for n, b in bits.items()), v
        assert {"TRANSIENT", "SOURCE", "OUTLIER", "OVERFLOW"} <= set(bits), v
    assert not any(k.startswith("MSKN") for k in hv["6.4+psffix1"])
    assert "STREAK" not in flag_bits(hv["6.4+psffix1"]) and "BLOOM" not in flag_bits(hv["6.4+psffix1"])
    assert {"PHANTOM", "REFERENCE"} <= set(flag_bits(hv["6.4+psffix1"]))


def test_real_header_without_planes_raises():
    h = _hdus()["FLAGS"][0].copy()
    for k in [k for k in h if k.startswith(("MSKN", "MSKM"))]:
        del h[k]
    with pytest.raises(ValueError):
        flag_bits(h)


def test_real_no_preset_masks_source_or_outlier():
    for p in PRESETS.values():
        assert "SOURCE" not in p and "OUTLIER" not in p


def test_real_bad_mask_canonical_and_survey_number():
    h = _hdus()
    bits = flag_bits(h["FLAGS"][0])
    flg = np.asarray(h["FLAGS"][1], np.int64)
    assert bad_mask(flg, bits, "bright").sum() <= bad_mask(flg, bits, "discovery").sum()
    assert np.array_equal(canonical(flg, bits).astype(np.int64), flg)        # QR3 layout is canonical
    hi = h["IMAGE"][0]
    assert survey_number(hi["MJD-AVG"], hi["SPS_EPA"]) == 4   # Barnard Aug 2026, SPS_EPA = 180


class _FixtureCalib:
    """Real D6 CWAVE/CHANNEL_MAP at the fixture's parent slice, embedded in a 2040² frame (NaN elsewhere)."""
    def __init__(self):
        cw = np.full((2040, 2040), np.nan, np.float32)
        cw[1919:1948, 638:667] = np.load(D / "cwave_D6_fixture_slice.npy")
        self.cwave = {6: cw}
        self.cband = {6: cw / 128.0}
        ch = np.zeros((2040, 2040), np.uint8)
        ch[1919:1948, 638:667] = np.load(D / "channel_map_fixture_slice.npy")
        self.channel = ch
        self.fluxcorr = {}


def test_real_calframe_contract_from_fixture():
    """Contract test (workflow.md §7.3): RawFrame → CalFrame built from a real file; every field fills."""
    h = _hdus()
    origin = parent_origin(h["IMAGE"][0])
    assert origin == (638, 1919)                               # CRPIXnA = −637, −1918
    raw = RawFrame(hdus=h, wcs=WCS(h["IMAGE"][0]), origin=origin)
    cf = calibrate(raw, _FixtureCalib())
    assert isinstance(cf, CalFrame)
    assert cf.sci.shape == cf.lam.shape == cf.dlam.shape == cf.bad_phot.shape == (29, 29)
    assert np.isfinite(cf.lam).all() and 4.4 < np.nanmedian(cf.lam) < 5.01
    assert cf.detector == 6 and cf.survey == 4 and cf.photometric_scale == "qr3"
    assert cf.w_frame > 0 and np.isfinite(np.nanmedian(cf.sci))
    assert cf.qa["ok"] and cf.qa["badges"] == {"L1DQAFLG": "Pass", "L2DQAFLG": "Pass"}
    assert "SOURCE" in cf.flags_near(14, 14, 3)                 # 81% SOURCE field
    assert frame_qa(h["IMAGE"][0], np.ones((29, 29), bool))["reasons"] == ["bad=100%"]


def test_real_stack_and_cube_contract_from_fixture():
    """Contract test: Stack and Cube built from the real frame (one frame, so no science claim)."""
    from spherex.cube import build_cube
    from spherex.epochs import time_bins
    from spherex.grid import frame_to_grid, make_grid
    from spherex.stack import build_stack
    from spherex.types import Cube, Stack
    h = _hdus()
    raw = RawFrame(hdus=h, wcs=WCS(h["IMAGE"][0]), origin=parent_origin(h["IMAGE"][0]))
    cf = calibrate(raw, _FixtureCalib(), "bright")
    ra, dec = raw.wcs.pixel_to_world_values(14, 14)
    g = make_grid(float(ra), float(dec), 1.5)
    gf = frame_to_grid(cf, g)
    tb = time_bins([cf.mjd], [cf.detector], "visit", [cf.survey])[6][0]
    st = build_stack([gf], tb, g)
    cb = build_cube([gf], tb, 6, g)
    assert isinstance(st, Stack) and isinstance(cb, Cube)
    assert st.bin.status == "partial" and st.bin.surveys == (4,) and np.isfinite(st.mean).mean() > 0.5
    assert cb.photometric_scales == ("qr3",) and cb.nhits.sum(0).max() == 1
    assert (st.flag_or & (1 << 21)).any()                       # SOURCE propagated in the canonical layout
