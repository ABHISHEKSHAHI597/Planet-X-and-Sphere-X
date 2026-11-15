"""L0: flag parsing conventions, canonical layout, epochs labels and axes (implementation.md §4.2, §4.3)."""
import numpy as np
import pytest
from astropy.io import fits

from spherex.epochs import date_range, label, survey_number, time_bins
from spherex.flags import CANONICAL_BITS, CANONICAL_INFO, PRESETS, bad_mask, canonical, flag_bits


def test_flag_bits_both_header_conventions():
    h3 = fits.Header({"MSKN0000": "TRANSIENT", "MSKM0000": 1, "MSKN0021": "SOURCE", "MSKM0021": 1 << 21})
    h2 = fits.Header()
    h2["HIERARCH MP_TRANSIENT"] = 0
    h2["HIERARCH MP_SOURCE"] = 21
    assert flag_bits(h3) == flag_bits(h2) == {"TRANSIENT": 1, "SOURCE": 1 << 21}
    with pytest.raises(ValueError):
        flag_bits(fits.Header({"BITPIX": 32}))


def test_canonical_repack_from_a_different_layout():
    bits = {"SOURCE": 1 << 3, "TRANSIENT": 1 << 7, "WEIRD": 1 << 30}
    out = canonical(np.array([1 << 3 | 1 << 7 | 1 << 30]), bits)
    assert out[0] == (1 << CANONICAL_BITS["SOURCE"]) | (1 << CANONICAL_BITS["TRANSIENT"])
    assert CANONICAL_INFO & (1 << CANONICAL_BITS["SOURCE"])


def test_presets_policy():
    for p in PRESETS.values():
        assert "SOURCE" not in p and "OUTLIER" not in p and "REFERENCE" in p
    assert "STREAK" in PRESETS["imaging"] and "STREAK" not in PRESETS["discovery"]
    bits = {n: 1 << b for n, b in CANONICAL_BITS.items()}
    bloom = np.array([1 << CANONICAL_BITS["BLOOM"]])
    assert bad_mask(bloom, bits, "imaging")[0] and not bad_mask(bloom, bits, "bright")[0]


def test_survey_number_branches():
    assert survey_number(60790.0, 0.0) is None                 # IOC
    assert survey_number(60900.0, 0.0) == 1 and survey_number(60900.0, 180.0) == 2
    assert survey_number(61300.0, 0.0) == 3 and survey_number(61300.0, -179.0) == 4


def test_labels_and_date_ranges():
    assert date_range(60800.0, 60800.2) == "2025-05-05"
    assert date_range(60800.0, 60801.0) == "2025-05-05/06"
    assert date_range(61110.0, 61140.0) == "2026-03-11→04-10"
    assert date_range(61037.0, 61049.0) == "2025-12-28→2026-01-09"
    assert label("V2", "full", 61110, 61140, (1,), 18, 6, 113) == "V2 · 2026-03-11→04-10 · S1 · 113 frames"
    assert label("V1", "partial", 60800, 60801, (1,), 3, 6) == "V1 · 2025-05-05/06 · S1 · partial (3 in band 6)"
    assert label("B0", "bin", 60790, 60800, (None, 2), 5, 6).endswith("S2+IOC · 5 frames")


def test_time_bins_axes():
    mjd = np.r_[60900 + np.arange(12) * 0.5, 61076 + np.arange(4) * 0.1, 61096.5 + np.arange(12) * 0.04]
    det = np.full(mjd.size, 6)
    sv = [1] * 12 + [2] * 16
    v = time_bins(mjd, det, "visit", sv)[6]
    assert [(b.id, b.status) for b in v] == [("V1", "full"), ("V3", "full")]      # partial V2 merged (span ≤ 21 d)
    assert v[1].idx.size == 16
    assert len(time_bins(mjd, det, "bin:14d", sv)[6]) == 3
    assert [b.id for b in time_bins(mjd, det, "survey", sv)[6]] == ["S1", "S2"]
    assert len(time_bins(mjd, det, "exposure", sv)[6]) == 28
    assert time_bins(mjd, det, "auto", sv)[6][0].status == "full"
    with pytest.raises(ValueError):
        time_bins(mjd, det, "weekly")


def test_survey_axis_bin_ids_are_path_safe():
    """Planning has no headers, so every science frame is survey 0: its bin id used to be "S?", which the store
    rejected (UnsafePath) and which a URL reads as a query string, so axis=survey failed for every target."""
    import re

    tb = time_bins([60700.0, 60900.0, 60910.0, 61300.0], [6, 6, 6, 6], "survey")
    ids = [b.id for b in tb[6]]
    assert ids == ["IOC", "SU"] and all(re.match(r"^[A-Za-z0-9_.:+-]{1,64}$", i) for i in ids)
    assert "S?" in tb[6][1].label                       # the label still says the survey is unknown
