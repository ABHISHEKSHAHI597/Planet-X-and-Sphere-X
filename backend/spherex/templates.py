"""Observed IRTF template assets; verified bytes and explicit F_lambda to F_nu."""

import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
from astropy.io import fits


def load_template(name: str) -> dict[str, Any]:
    root = Path(__file__).with_name("data") / "templates"
    manifest = json.loads((root / "provenance.json").read_text())
    if name not in manifest:
        raise ValueError("unknown observed template")
    provenance = manifest[name]
    path = root / name
    if hashlib.sha256(path.read_bytes()).hexdigest() != provenance["sha256"]:
        raise ValueError("template checksum mismatch")
    if provenance.get("format") == "pickles-stsci-flambda":
        with fits.open(path) as hdus:
            if (
                hdus[1].columns["WAVELENGTH"].unit.lower() != "angstroms"
                or hdus[1].columns["FLUX"].unit.lower() != "flam"
            ):
                raise ValueError("unsupported Pickles table units")
            wave = np.asarray(hdus[1].data["WAVELENGTH"], float) * 1e-4
            flux = np.asarray(hdus[1].data["FLUX"], float)
        if not np.all(np.diff(wave) > 0):
            raise ValueError("invalid Pickles wavelength sampling")
        return dict(
            wavelength_um=wave,
            flux_uJy=flux * wave**2 * 1e27 / 299792458.0,
            error_uJy=np.full_like(wave, np.nan),
            spectral_type=provenance["spectral_type"],
            provenance=provenance,
        )
    if provenance.get("format") == "splat-flambda-model":
        if provenance.get("units") != "um; erg/s/cm2/um (surface F_lambda)":
            raise ValueError("unsupported model units")
        wave, flux = np.loadtxt(path, unpack=True)
        if not np.all(np.diff(wave) > 0) or not np.all(np.isfinite(flux)):
            raise ValueError("invalid model sampling")
        # cgs per micron -> W/m2/micron is 1e-3; normalization is the
        # unknown dilution (R/d)^2, not an observed flux or temperature.
        return dict(
            wavelength_um=wave,
            flux_uJy=flux * wave**2 * 1e23 / 299792458.0,
            error_uJy=np.full_like(wave, np.nan),
            spectral_type=provenance["spectral_type"],
            provenance=provenance,
        )
    with fits.open(path) as hdus:
        h = hdus[0].header
        relative = provenance.get("format") == "relative-splat-flambda"
        unit_factor = {"Wm-2um-1": 1.0, "ergss-1cm-2A-1": 10.0}.get(h.get("YUNITS"))
        if not relative and (h["XUNITS"] != "um" or unit_factor is None):
            raise ValueError("unsupported template units")
        wave, flux, error = np.asarray(hdus[0].data, float)
        spectral_type = provenance.get("spectral_type") or h["SPTYPE"]
    if not np.all(np.diff(wave) > 0):
        raise ValueError("template wavelength order invalid")
    # F_lambda per micron -> per metre; lambda in metres; W/m2/Hz -> microJy.
    factor = wave**2 * 1e26 / 299792458.0 * (unit_factor or 1.0)
    valid = np.isfinite(flux) & np.isfinite(error) & (error > 0)
    if relative:
        shape = np.where(valid, flux * wave**2, np.nan)
        normalization = float(np.nanmedian(shape))
        if normalization <= 0:
            raise ValueError("template relative normalization not positive")
        return dict(
            wavelength_um=wave,
            flux_fnu=shape / normalization,
            flux_unit="relative",
            spectral_type=spectral_type,
            provenance=provenance,
        )
    return dict(
        wavelength_um=wave,
        flux_uJy=np.where(valid, flux * factor, np.nan),
        error_uJy=np.where(valid, error * factor, np.nan),
        spectral_type=spectral_type,
        provenance=provenance,
    )


def channel_template(template: dict[str, Any], wavelength: Any, width: Any) -> Any:
    """Illustrative boxcar Fnu averages; reject incomplete coverage and gaps.

    CBAND supplies a width, not a measured throughput curve. These are labelled
    approximate overlays and cannot be used as spectral-type likelihoods.
    """
    wave = template["wavelength_um"]
    flux = template["flux_fnu"] if "flux_fnu" in template else template["flux_uJy"]
    result = []
    for centre, span in zip(wavelength, width, strict=True):
        lo, hi = centre - span / 2, centre + span / 2
        indices = np.flatnonzero((wave >= lo) & (wave <= hi))
        if span <= 0 or lo < wave[0] or hi > wave[-1] or len(indices) < 3:
            result.append(np.nan)
            continue
        a, b = max(0, indices[0] - 1), min(len(wave) - 1, indices[-1] + 1)
        x, y = wave[a : b + 1], flux[a : b + 1]
        # Never join telluric/order gaps or missing flux values.
        if not np.all(np.isfinite(y)) or np.max(np.diff(x)) > 4 * np.median(np.diff(x)):
            result.append(np.nan)
            continue
        grid = np.r_[lo, wave[indices], hi]
        result.append(float(np.trapezoid(np.interp(grid, x, y), grid) / span))
    return np.asarray(result)


def template_overlays(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Separate scale per visit/release; no classifier or cross-release fit."""
    root = Path(__file__).with_name("data") / "templates"
    manifest = json.loads((root / "provenance.json").read_text())
    overlays = []
    groups: dict[Any, list[Any]] = {}
    for row in rows:
        if not row["contaminated"]:
            groups.setdefault(
                (row["visit"], row.get("quality", {}).get("photometric_scale", row["release"])), []
            ).append(row)
    for name in manifest:
        template = load_template(name)
        for (visit, release), points in groups.items():
            model = channel_template(template, [p["lam"] for p in points], [p["dlam"] for p in points])
            f, e = np.array([p["flux"] for p in points]), np.array([p["err"] for p in points])
            ok = np.isfinite(model) & np.isfinite(f) & np.isfinite(e) & (e > 0)
            if ok.sum() < 3:
                continue
            w = 1 / e[ok] ** 2
            normal = float(w @ model[ok] ** 2)
            if normal <= 0:
                continue
            scale = float(w @ (f[ok] * model[ok]) / normal)
            if scale <= 0:
                continue
            chi = float(np.sum(w * (f[ok] - scale * model[ok]) ** 2))
            overlays.append(
                dict(
                    name=name,
                    spectral_type=template["spectral_type"],
                    visit=visit,
                    release=release,
                    scale=scale,
                    scale_error=float(np.sqrt(max(1.0, chi / (ok.sum() - 1)) / normal)),
                    chi2=chi,
                    dof=int(ok.sum() - 1),
                    samples=[
                        dict(lam=p["lam"], flux=float(scale * m))
                        for p, m, use in zip(points, model, ok, strict=True)
                        if use
                    ],
                    provenance=template["provenance"],
                    scale_units="uJy per relative Fnu unit"
                    if template.get("flux_unit") == "relative"
                    else "dimensionless normalization/dilution",
                    label="Illustrative "
                    + template["provenance"].get("kind", "observed spectrum")
                    + "; approximate CBAND boxcar average; target-noise-only scale uncertainty, not a spectral classification.",
                )
            )
    return overlays
