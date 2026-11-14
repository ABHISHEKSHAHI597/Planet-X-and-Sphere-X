"""Comparison contracts, not evidence of real independent agreement."""

import copy

import pytest

from spherex.reference import compare_reference


def test_original_irsa_export_units_and_frame_provenance():
    from astropy import units as u
    from astropy.table import Table
    from spherex.reference import normalize_irsa_table

    table = Table(
        dict(
            lvf_id=["exposure"],
            det_id=[6],
            data_collection=["qr2"],
            wavelength=[4500.0] * u.nm,
            lambda_width=[0.1] * u.um,
            flux=[0.001] * u.Jy,
            flux_err=[0.00001] * u.Jy,
            flags=[0],
        )
    )
    out = normalize_irsa_table(table, {"exposure:6": "pinned.fits"}, "https://irsa.ipac.caltech.edu/job")
    assert out["rows"][0]["flux"] == pytest.approx(1000.0)
    assert out["rows"][0]["lam"] == pytest.approx(4.5)
    assert out["frame_ids"] == ["pinned.fits"]
    with pytest.raises(ValueError, match="mapping"):
        normalize_irsa_table(table, {}, out["source_url"])
    with pytest.raises(ValueError, match="conflict"):
        normalize_irsa_table(table, {"exposure:6": "pinned.fits"}, out["source_url"], flux_unit="uJy")


def inputs():
    rows = [
        dict(
            frame_id=str(j),
            lam=1 + j * 0.1,
            dlam=0.03,
            flux=100.0,
            err=1.0,
            visit="V1",
            release="qr2",
            contaminated=False,
        )
        for j in range(3)
    ]
    return dict(rows=rows), dict(
        tool="IRSA Spectrophotometry Tool",
        source_url="https://irsa.ipac.caltech.edu/test",
        units="uJy",
        release="qr2",
        frame_ids=["0", "1", "2"],
        rows=[{k: r[k] for k in ["frame_id", "lam", "dlam", "flux", "err"]} for r in rows],
    )


def test_independent_comparison_preserves_failures():
    measured, ref = inputs()
    assert compare_reference(measured, ref, "V1", "qr2")["numerical_pass"]
    ref["rows"][0]["flux"] = 80
    result = compare_reference(measured, ref, "V1", "qr2")
    assert not result["numerical_pass"]
    assert result["max_absolute_fractional_difference"] == 0.25


def test_mismatched_data_cannot_satisfy_comparison():
    measured, ref = inputs()
    for key, value in [
        ("release", "qr3"),
        ("units", "Jy"),
        ("frame_ids", ["unrelated"]),
        ("source_url", "https://example.com/self"),
    ]:
        changed = copy.deepcopy(ref)
        changed[key] = value
        with pytest.raises(ValueError):
            compare_reference(measured, changed, "V1", "qr2")
    ref["rows"][0]["lam"] += 0.1
    with pytest.raises(ValueError):
        compare_reference(measured, ref, "V1", "qr2")
