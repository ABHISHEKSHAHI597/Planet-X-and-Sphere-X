"""Pure ephemeris and observer verification functions (§4.11, F10)."""

from __future__ import annotations

from typing import Any

import numpy as np

SPHEREX_CENTER = "500@-163182"


def cached_position(ephemeris: dict[str, Any], mjd: Any) -> tuple[Any, Any]:
    """No interpolation across uncomputed SSO motion; require requested frame times."""
    times = np.atleast_1d(np.asarray(mjd, float))
    rows = []
    for t in times:
        if str(t) not in ephemeris:
            raise ValueError(f"Horizons position not cached at MJD {t}; query exact frame time")
        rows.append(ephemeris[str(t)])
    a = np.asarray(rows, float)
    return a[:, 0], a[:, 1]


def verify_observer(header_xyz_km: Any, horizons_xyz_km: Any, frame: str, tolerance_km: float = 10.0) -> dict[str, Any]:
    """F10 needs >=3 epochs, verified header axes, matching midpoint and time scale."""
    h, j = np.asarray(header_xyz_km, float), np.asarray(horizons_xyz_km, float)
    if h.shape != j.shape or h.ndim != 2 or h.shape[1] != 3 or len(h) < 3:
        raise ValueError("at least three paired observer vectors required")
    if frame.upper() not in ("ICRS", "ICRF", "J2000"):
        raise ValueError("GEOCENTER specifies origin, not axes; establish header reference frame first")
    delta = np.linalg.norm(h - j, axis=1)
    return dict(
        delta_km=delta.tolist(),
        passed=bool(np.all(np.isfinite(delta)) and np.all(delta < tolerance_km)),
        tolerance_km=tolerance_km,
        frame=frame,
    )


def topocentric_offset(ra: Any, dec: Any, distance_au: Any, sc_geo_icrs_km: Any) -> tuple[Any, Any]:
    """Geocentric asteroid direction to spacecraft, vector subtraction (no Earth term)."""
    import astropy.units as u
    from astropy.coordinates import SkyCoord

    from .astrometry import AU_KM

    c = SkyCoord(ra=np.asarray(ra) * u.deg, dec=np.asarray(dec) * u.deg, distance=np.asarray(distance_au) * u.au)
    xyz = c.cartesian.xyz.to_value(u.au) - np.asarray(sc_geo_icrs_km) / AU_KM
    q = SkyCoord(x=xyz[0] * u.au, y=xyz[1] * u.au, z=xyz[2] * u.au, representation_type="cartesian")
    return q.spherical.lon.deg, q.spherical.lat.deg
