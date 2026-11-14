"""Strict external spectrum comparison; independent provenance is reviewed separately."""

from typing import Any

import numpy as np


def normalize_irsa_table(
    table: Any, frame_map: dict[str, str], source_url: str, flux_unit: str | None = None, wave_unit: str | None = None
) -> dict[str, Any]:
    """Normalize original IRSA tables with explicit units and lvf_id:det_id frame mapping."""
    from astropy import units as u

    required = {"lvf_id", "det_id", "data_collection", "wavelength", "lambda_width", "flux", "flux_err"}
    if not required.issubset(table.colnames) or len(table) == 0:
        raise ValueError("nonempty original IRSA table with documented provenance columns required")
    releases = {str(r["data_collection"]).strip().lower() for r in table}
    if len(releases) != 1 or not releases.issubset({"qr2", "qr3"}):
        raise ValueError("select exactly one explicit IRSA release before comparison")
    rows = []
    for row in table:
        key = f"{str(row['lvf_id']).strip()}:{int(row['det_id'])}"
        if key not in frame_map:
            raise ValueError(f"explicit pinned-frame mapping missing for {key}")
        item: dict[str, Any] = {"frame_id": frame_map[key], "export_key": key}
        for original, normalized, declared, desired in [
            ("wavelength", "lam", wave_unit, u.um),
            ("lambda_width", "dlam", wave_unit, u.um),
            ("flux", "flux", flux_unit, u.uJy),
            ("flux_err", "err", flux_unit, u.uJy),
        ]:
            unit = getattr(table[original], "unit", None) or declared
            if unit is None or np.ma.is_masked(row[original]):
                raise ValueError("explicit export units and unmasked measurements required")
            if declared is not None and getattr(table[original], "unit", None) is not None:
                if u.Unit(declared) != u.Unit(table[original].unit):
                    raise ValueError("declared units conflict with export metadata")
            item[normalized] = float((float(row[original]) * u.Unit(unit)).to_value(desired))
        if (
            not np.all(np.isfinite([item[k] for k in ("lam", "dlam", "flux", "err")]))
            or item["dlam"] <= 0
            or item["err"] <= 0
        ):
            raise ValueError("finite export measurements with positive width/error required")
        if "flags" in table.colnames:
            item["flags"] = int(row["flags"])
        rows.append(item)
    return dict(
        tool="IRSA Spectrophotometry Tool",
        source_url=source_url,
        units="uJy",
        release=releases.pop(),
        frame_ids=sorted({r["frame_id"] for r in rows}),
        rows=rows,
    )


def compare_reference(measured: dict[str, Any], reference: dict[str, Any], visit: str, release: str) -> dict[str, Any]:
    if reference.get("units") != "uJy" or reference.get("release") != release:
        raise ValueError("reference must declare microJy and the same release")
    if reference.get("tool") != "IRSA Spectrophotometry Tool" or not reference.get("source_url", "").startswith(
        "https://irsa.ipac.caltech.edu/"
    ):
        raise ValueError("independent IRSA export provenance required")
    expected = set(reference.get("frame_ids", []))
    rows = [r for r in measured["rows"] if r["visit"] == visit and r["release"] == release and not r["contaminated"]]
    actual = {r["frame_id"] for r in rows}
    if not actual or expected != actual:
        raise ValueError("reference and selected native frame sets must match exactly")
    pairs = []
    used = set()
    for r in rows:
        matches = [
            (j, p)
            for j, p in enumerate(reference["rows"])
            if p["frame_id"] == r["frame_id"] and abs(p["lam"] - r["lam"]) <= 0.1 * min(p["dlam"], r["dlam"])
        ]
        if len(matches) != 1:
            raise ValueError("one unambiguous same-frame, same-channel reference point required")
        j, p = matches[0]
        if j in used:
            raise ValueError("reference point reused")
        used.add(j)
        if not np.all(np.isfinite([p["flux"], p["err"], r["flux"], r["err"]])) or min(p["err"], r["err"]) <= 0:
            raise ValueError("finite fluxes and positive uncertainties required")
        if min(p["flux"] / p["err"], r["flux"] / r["err"]) < 5:
            raise ValueError("bright-star comparison requires five-sigma measurements in both methods")
        fraction = (r["flux"] - p["flux"]) / p["flux"]
        pairs.append(
            dict(
                frame_id=r["frame_id"],
                lam=r["lam"],
                fractional_difference=fraction,
                difference_sigma=(r["flux"] - p["flux"]) / np.hypot(r["err"], p["err"]),
            )
        )
    if len(pairs) < 3 or len(used) != len(reference["rows"]):
        raise ValueError("at least three matched points, with no unmatched reference rows required")
    return dict(
        pairs=pairs,
        max_absolute_fractional_difference=max(abs(p["fractional_difference"]) for p in pairs),
        numerical_pass=all(abs(p["fractional_difference"]) <= 0.10 for p in pairs),
        note="All matched bright channels must agree within 10%; independent provenance and scientific sign-off remain reviewer responsibilities. Shared native-image noise makes difference_sigma descriptive, not an independent chi-square test.",
    )
