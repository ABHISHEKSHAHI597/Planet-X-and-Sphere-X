"""Public observed spectra are assets, not SPHEREx validation substitutes."""

import numpy as np
from astropy import units as u
from astropy.io import fits

from spherex.templates import channel_template, load_template, template_overlays


def test_observed_templates_have_verified_units_and_preserve_gaps():
    from pathlib import Path

    root = Path(__file__).parents[2] / "spherex/data/templates"
    for name in ["M0V_HD19305.fits", "L1_2MASSJ1439+1929.fits", "T4.5_2MASSJ0559-1404.fits"]:
        result = load_template(name)
        data = fits.getdata(root / name)
        j = int(np.flatnonzero(np.isfinite(result["flux_uJy"]))[0])
        expected = (data[1, j] * u.W / u.m**2 / u.um).to_value(
            u.uJy, equivalencies=u.spectral_density(data[0, j] * u.um)
        )
        assert np.isclose(result["flux_uJy"][j], expected)
        assert result["provenance"]["url"].startswith("https://irsa.ipac.caltech.edu/")
        assert np.all(np.diff(result["wavelength_um"]) > 0)


def test_template_channels_recover_scale_and_preserve_missing_coverage():
    template = load_template("M0V_HD19305.fits")
    wave = [1.05, 1.2, 1.6, 2.2]
    width = [0.025] * 4
    values = channel_template(template, wave, width)
    assert np.all(np.isfinite(values))
    rows = [
        dict(lam=w, dlam=d, flux=float(v * 2), err=float(v * 0.01), visit="V1", release="qr2", contaminated=False)
        for w, d, v in zip(wave, width, values)
    ]
    overlays = template_overlays(rows)
    chosen = next(o for o in overlays if o["name"] == "M0V_HD19305.fits")
    assert np.isclose(chosen["scale"], 2)
    assert chosen["chi2"] < 1e-12
    assert np.isnan(channel_template(template, [10.0], [0.1])[0])
    missing = dict(wavelength_um=np.array([1.0, 1.01, 1.02, 1.5, 1.51]), flux_uJy=np.ones(5))
    assert np.isnan(channel_template(missing, [1.25], [0.5])[0])
    # Release labels remain separate even when source/epochs are identical.
    split = template_overlays(rows + [dict(r, release="qr3", flux=r["flux"] * 3) for r in rows])
    scales = {o["release"]: o["scale"] for o in split if o["name"] == chosen["name"]}
    assert np.isclose(scales["qr2"], 2) and np.isclose(scales["qr3"], 6)


def test_complete_standard_grid_model_and_pickles_have_explicit_units():
    import json
    from pathlib import Path

    root = Path(__file__).parents[2] / "spherex/data/templates"
    manifest = json.loads((root / "provenance.json").read_text())
    standards = [name for name in manifest if name.startswith("splat_")]
    assert {load_template(n)["spectral_type"] for n in standards} == {
        f"{letter}{i}.0" for letter in "MLT" for i in range(10)
    }
    assert len(standards) == 30
    for name in standards:
        value = load_template(name)
        assert np.all(np.diff(value["wavelength_um"]) > 0)
        if value.get("flux_unit") == "relative":
            assert "flux_uJy" not in value
            assert np.isclose(np.nanmedian(value["flux_fnu"]), 1)
    model = load_template("btsettl500K_g4.5.txt.gz")
    raw = np.loadtxt(root / "btsettl500K_g4.5.txt.gz")
    expected = (raw[0, 1] * u.erg / u.s / u.cm**2 / u.um).to_value(
        u.uJy, equivalencies=u.spectral_density(raw[0, 0] * u.um)
    )
    assert np.isclose(model["flux_uJy"][0], expected)
    assert model["provenance"]["temperature_K"] == 500
    assert np.isnan(channel_template(model, [5.0], [0.03])[0])
    for name in ["pickles_uk_9.fits", "pickles_uk_26.fits"]:
        result = load_template(name)
        table = fits.getdata(root / name)
        expected = (table["FLUX"][0] * u.erg / u.s / u.cm**2 / u.AA).to_value(
            u.uJy, equivalencies=u.spectral_density(table["WAVELENGTH"][0] * u.AA)
        )
        assert np.isclose(result["flux_uJy"][0], expected)
    # The T3 original explicitly uses per-Angstrom cgs rather than W/m2/micron.
    name = "splat_10034_10874.fits.gz"
    data = fits.getdata(root / name)
    expected = (data[1, 0] * u.erg / u.s / u.cm**2 / u.AA).to_value(
        u.uJy, equivalencies=u.spectral_density(data[0, 0] * u.um)
    )
    assert np.isclose(load_template(name)["flux_uJy"][0], expected)
