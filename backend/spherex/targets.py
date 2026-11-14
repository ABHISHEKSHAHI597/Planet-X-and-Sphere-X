"""Catalogue resolution and common stellar position model (impl. ?4.1)."""

from __future__ import annotations

import math
import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from spherex.constants import TEST_TARGETS

from .astrometry import parallax_factors

ALIASES = {  # implementation.md §4.1 (what people type → an identifier SIMBAD resolves)
    "barnard's star": "NAME Barnard's Star",
    "barnards star": "NAME Barnard's Star",
    "barnard": "NAME Barnard's Star",
    "eps ind b": "* eps Ind B",
    "eps indi b": "* eps Ind B",
    "epsilon indi b": "* eps Ind B",
    "ε indi b": "* eps Ind B",
    "ε ind b": "* eps Ind B",
    "wise 0855": "WISE J085510.83-071442.5",
    "wise0855": "WISE J085510.83-071442.5",
    "wise0855-0714": "WISE J085510.83-071442.5",
    "wise 0855-07": "WISE J085510.83-071442.5",
    "w0855": "WISE J085510.83-071442.5",
    "barnards": "NAME Barnard's Star",
    "barnard star": "NAME Barnard's Star",
    "gj 699": "NAME Barnard's Star",
    "gl 699": "NAME Barnard's Star",
    "eps indi ba": "* eps Ind B",
    "epsilon indi ba": "* eps Ind B",
    "epsilon ind b": "* eps Ind B",
    "wise 0855-0714": "WISE J085510.83-071442.5",
    "wise j0855-0714": "WISE J085510.83-071442.5",
    "wise j085510.83-071442.5": "WISE J085510.83-071442.5",
    "rw aur": "V* RW Aur",
    "rw aurigae": "V* RW Aur",
    "r dra": "V* R Dra",
    "r draconis": "V* R Dra",
}
# SIMBAD identifier → TEST_TARGETS key (offline fallback) and the display name
OFFLINE = {
    "NAME Barnard's Star": ("Barnard's Star", "Barnard's Star", "BY*", "M4V"),
    "* eps Ind B": ("eps Ind B", "eps Ind B", "BD*", "T1+T6"),
    "WISE J085510.83-071442.5": ("WISE 0855-0714", "WISE 0855−0714", "BD*", "Y4"),
    "V* RW Aur": ("RW Aur", "RW Aur", "Or*", "K1/5"),
    "V* R Dra": ("R Dra", "R Dra", "Mi*", "M5e-M9e"),
}
BRIGHT_TARGETS = {"NAME Barnard's Star", "V* RW Aur", "V* R Dra"}  # fallback when no K magnitude is known
# K (Vega) of the offline targets (understanding.md §8.1); WISE 0855 is undetected in 2MASS (J ≈ 25).
OFFLINE_K = {"NAME Barnard's Star": 4.52, "* eps Ind B": 11.21, "V* RW Aur": 7.02, "V* R Dra": 2.23}
# F7 (validation/F7): OVERFLOW sets in at K ≈ 9–9.5 in bands 2–4, so brighter targets get the `bright` preset.
BRIGHT_K_MAG = 9.0


def is_bright(t: Target) -> bool:
    """`mask=auto` rule for any target (§4.3): bright preset when its K magnitude says it overflows the detectors."""
    k = t.extra.get("k_mag")
    if k is not None:
        return float(k) < BRIGHT_K_MAG
    return t.main_id in BRIGHT_TARGETS


class ResolveError(LookupError):
    pass


class NeedsUpstream(RuntimeError):
    """The request needs a module another role owns (M's ephem.py for Solar System bodies)."""


class UpstreamError(RuntimeError):
    """A catalogue or ephemeris service needed for this request did not answer (HTTP 502/503 for the API)."""


# Stellar catalogue designations: a name that starts like this is never sent to JPL Horizons when SIMBAD does not
# know it (audit B-01: every unknown name cost a Horizons round trip, and its errors surfaced as HTTP 500).
_STELLAR_PREFIX = re.compile(
    r"^(name |v\* |\* |\*\* |wise|wisea|2mass|hd |hd\d|hip |hip\d|gaia|gj |gl |tyc|lhs|ross |wolf |bd[+-]|cd-|"
    r"ucac|sdss|ps1|psos|ulas|cwise|lp |lspm|g \d|ngc|ic |m \d|m\d)", re.I)


def not_found(query: str) -> ResolveError:
    return ResolveError(f'"{query}" was not found in SIMBAD or JPL Horizons. Check the spelling, or enter RA and Dec '
                        "(for example 269.4461 4.7707). Solar System bodies can be typed as sso:<name>.")


def normalize_query(q: str) -> str:
    q = unicodedata.normalize("NFC", q)
    q = q.replace("−", "-").replace("–", "-").replace("’", "'").replace("′", "'").replace("″", '"')
    return re.sub(r"\s+", " ", q).strip()


_SEX = re.compile(
    r"^\s*(\d{1,2})[h: ]\s*(\d{1,2})[m: ]\s*(\d{1,2}(?:\.\d*)?)s?\s*[, ]?\s*"
    r"([+-]?)\s*(\d{1,2})[d°: ]\s*(\d{1,2})['m: ]\s*(\d{1,2}(?:\.\d*)?)\"?s?\s*$"
)
_DEC = re.compile(r"^\s*([+-]?\d+(?:\.\d+)?)\s*[, ]\s*([+-]?\d+(?:\.\d+)?)\s*$")


def parse_coords(q: str) -> tuple[float, float] | None:
    """Decimal degrees ("269.4461 4.7707", "269.4461,4.7707") or sexagesimal ("08:55:10.831 -07:14:42.53",
    "08h55m10.831s -07d14m42.53s"), Unicode minus allowed. Returns (ra, dec) in degrees, or None."""
    s = normalize_query(q)
    # "269.4461° +4.7707°": a degree sign that ends a decimal number is only a unit (audit K-31)
    s = re.sub(r"(\d)°(?=[\s,]|$)", r"\1 ", s).strip()
    m = _DEC.match(s)
    if m:
        ra, dec = float(m[1]), float(m[2])
    else:
        m = _SEX.match(s)
        if not m:
            return None
        if int(m[2]) >= 60 or float(m[3]) >= 60 or int(m[6]) >= 60 or float(m[7]) >= 60:
            raise ResolveError("sexagesimal minutes and seconds must be below 60")
        ra = 15.0 * (int(m[1]) + int(m[2]) / 60 + float(m[3]) / 3600)
        dec = (int(m[5]) + int(m[6]) / 60 + float(m[7]) / 3600) * (-1 if m[4] == "-" else 1)
    if not (0.0 <= ra < 360.0 and -90.0 <= dec <= 90.0):
        raise ResolveError(f"coordinates out of range: RA {ra}, Dec {dec}")
    return ra, dec


def parse_coord_pair(ra: str, dec: str) -> tuple[float, float]:
    """URL form ra=08:55:10.831&dec=-07:14:42.53 or decimal degrees."""
    r = parse_coords(f"{ra} {dec}")
    if r is None:
        raise ResolveError(f"cannot read coordinates ra={ra!r} dec={dec!r}")
    return r


# --------------------------------------------------------------------------------- astrometry (§4.1)


def _time(mjd: Any) -> Any:
    from astropy.time import Time

    return Time(np.asarray(mjd, float), format="mjd")


@dataclass
class Target:
    """A resolved source with everything pos(t) needs. epoch: decimal Julian year of (ra, dec)."""

    query: str
    kind: str  # star | coords | sso
    name: str
    ra: float
    dec: float
    epoch: float = 2016.0
    pmra: float | None = None  # mas/yr (pmra* = μα cos δ)
    pmdec: float | None = None
    plx: float | None = None  # mas
    rv: float | None = None  # km/s, only with Gaia's own epoch
    main_id: str | None = None
    otype: str | None = None
    spt: str | None = None
    astrometry_source: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def moving(self) -> bool:
        return self.kind == "sso" or (self.kind == "star" and bool(self.pmra or self.pmdec or self.plx))

    def pos(self, mjd: Any) -> tuple[Any, Any]:
        """pos(t) as seen by SPHEREx (implementation.md §4.1). Arrays in, arrays out (deg)."""
        mjd = np.atleast_1d(np.asarray(mjd, float))
        if self.kind == "sso":
            from .ephem import cached_position

            return cached_position(self.extra.get("ephemeris", {}), mjd)
        if not self.moving:
            return np.full(mjd.shape, self.ra), np.full(mjd.shape, self.dec)
        return seen_by_spherex(self, mjd)


def propagate(
    ra: float,
    dec: float,
    pmra_masyr: float | None,
    pmdec_masyr: float | None,
    plx_mas: float | None,
    rv_kms: float | None,
    epoch_from: Any,
    epoch_to: Any,
) -> Any:
    import astropy.units as u
    from astropy.coordinates import Distance, SkyCoord

    kw: dict[str, Any] = {}
    if plx_mas is not None and plx_mas > 0:
        kw["distance"] = Distance(parallax=plx_mas * u.mas)
        if rv_kms is not None:
            kw["radial_velocity"] = rv_kms * u.km / u.s
    c = SkyCoord(
        ra=ra * u.deg,
        dec=dec * u.deg,
        pm_ra_cosdec=(pmra_masyr or 0) * u.mas / u.yr,
        pm_dec=(pmdec_masyr or 0) * u.mas / u.yr,
        obstime=epoch_from,
        **kw,
    )
    return c.apply_space_motion(new_obstime=epoch_to)


def seen_by_spherex(src: Target, mjd: Any, sc_geo_km: Any = None) -> tuple[Any, Any]:
    import astropy.units as u
    from astropy.coordinates import SkyCoord
    from astropy.time import Time

    c = propagate(src.ra, src.dec, src.pmra, src.pmdec, src.plx, src.rv, Time(src.epoch, format="jyear"), _time(mjd))
    pa, pd = parallax_factors(mjd, c.ra.deg, c.dec.deg, sc_geo_km)
    # Spherical offset avoids division by cos(dec) at the poles, wraps RA correctly.
    p = max(src.plx or 0.0, 0.0) / 1000.0
    shifted = SkyCoord(c.ra, c.dec).spherical_offsets_by(p * pa * u.arcsec, p * pd * u.arcsec)
    return shifted.ra.deg, shifted.dec.deg


def mjd_now() -> float:
    from astropy.time import Time

    return float(Time.now().mjd)


def decimal_year(mjd: float) -> float:
    return float(_time(mjd).jyear)


def sep_arcsec(ra1: float, dec1: float, ra2: float, dec2: float) -> float:
    r1, d1, r2, d2 = map(math.radians, (ra1, dec1, ra2, dec2))
    c = math.sin(d1) * math.sin(d2) + math.cos(d1) * math.cos(d2) * math.cos(r1 - r2)
    return math.degrees(math.acos(max(-1.0, min(1.0, c)))) * 3600


def pa_deg(ra1: float, dec1: float, ra2: float, dec2: float) -> float:
    r1, d1, r2, d2 = map(math.radians, (ra1, dec1, ra2, dec2))
    y = math.sin(r2 - r1) * math.cos(d2)
    x = math.cos(d1) * math.sin(d2) - math.sin(d1) * math.cos(d2) * math.cos(r2 - r1)
    return math.degrees(math.atan2(y, x)) % 360


def compass(pa: float) -> str:
    names = ["north", "north-east", "east", "south-east", "south", "south-west", "west", "north-west"]
    return names[int(((pa + 22.5) % 360) // 45)]


def epoch_of_match(ra_in: float, dec_in: float, t: Target) -> tuple[float, float]:
    """implementation.md §4.1: the decimal year at which t's track passes closest to the input."""
    years = np.arange(1990.0, 2031.0, 0.02)
    from astropy.time import Time

    mjd = Time(years, format="jyear").mjd
    track = propagate(t.ra, t.dec, t.pmra, t.pmdec, t.plx, None, Time(t.epoch, format="jyear"), Time(mjd, format="mjd"))
    ra, dec = track.ra.deg, track.dec.deg
    seps = np.array([sep_arcsec(ra_in, dec_in, a, b) for a, b in zip(ra, dec, strict=True)])
    i = int(np.argmin(seps))
    return float(years[i]), float(seps[i])


# ------------------------------------------------------------------------------------------ resolver


def offline_target(ident: str, query: str) -> Target | None:
    if ident not in OFFLINE:
        return None
    key, name, otype, spt = OFFLINE[ident]
    ra, dec, ep, pmra, pmdec, plx, rv, src = TEST_TARGETS[key]
    return Target(
        query=query,
        kind="star",
        name=name,
        ra=ra,
        dec=dec,
        epoch=ep,
        pmra=pmra,
        pmdec=pmdec,
        plx=plx,
        rv=rv,
        main_id=ident,
        otype=otype,
        spt=spt,
        astrometry_source=f"{src} (offline table)",
        extra={"k_mag": OFFLINE_K[ident]} if ident in OFFLINE_K else {},
    )


def identifier(query: str) -> str:
    """The catalogue identifier a typed name stands for: normalised, aliases applied ("barnards star" and
    "Barnard's Star" give the same one). Also the key of a frozen pin target (config/pins/targets.json)."""
    q = normalize_query(query)
    return ALIASES.get(q.lower(), q)


async def resolve_name(query: str, client: Any | None) -> Target:
    """Name → Target. client=None means offline: only the acceptance targets resolve."""
    q = normalize_query(query)
    if q.lower().startswith("sso:"):
        return await resolve_sso(q[4:], client)
    ident = identifier(query)
    if client is None:
        t = offline_target(ident, query)
        if t is None:
            raise ResolveError(
                f'"{query}" is not in the offline target table. Try RA/Dec, or one of: '
                "Barnard's Star, eps Ind B, WISE 0855-0714, RW Aur, R Dra."
            )
        return t
    from spherex.external.gaia import GaiaClient
    from spherex.external.simbad import SimbadClient

    sim = SimbadClient(client)
    try:
        o = await sim.by_identifier(ident)
    except Exception as e:  # SIMBAD down: degrade to the offline table
        t = offline_target(ident, query)
        if t is None:
            raise UpstreamError(
                f"SIMBAD is not answering ({type(e).__name__}), and {query!r} is not one of the offline targets. "
                "Try again in a minute, or enter RA and Dec."
            ) from e
        t.extra["warning"] = "SIMBAD unreachable: catalogue values from the offline table"
        return t
    if o is None or o.ra is None or o.dec is None:
        if _STELLAR_PREFIX.match(q) or "'" in q or '"' in q:
            raise not_found(query)
        try:
            return await resolve_sso(q, client)
        except ResolveError:
            raise not_found(query) from None
    t = Target(
        query=query,
        kind="star",
        name=o.main_id,
        ra=o.ra,
        dec=o.dec,
        epoch=2000.0,
        pmra=o.pmra,
        pmdec=o.pmdec,
        plx=o.plx,
        rv=None,
        main_id=o.main_id,
        otype=o.otype,
        spt=o.sp_type,
        astrometry_source="SIMBAD J2000 (linear)",
    )
    try:
        k_mag = await sim.k_mag(o.oid)
    except Exception:  # missing flux table answer: brightness unknown, the named fallback applies
        k_mag = None
    try:
        gid = await sim.gaia_dr3_id(o.oid)
        if gid is not None:
            g = await GaiaClient(client).by_id([gid])
            if g and g[0].pmra is not None:
                s = g[0]
                t = Target(
                    query=query,
                    kind="star",
                    name=o.main_id,
                    ra=s.ra,
                    dec=s.dec,
                    epoch=2016.0,
                    pmra=s.pmra,
                    pmdec=s.pmdec,
                    plx=s.parallax,
                    rv=s.radial_velocity,
                    main_id=o.main_id,
                    otype=o.otype,
                    spt=o.sp_type,
                    astrometry_source=f"Gaia DR3 {gid}",
                )
                if s.ruwe is not None and s.ruwe > 1.4 and o.main_id != "V* RW Aur":
                    t.extra["quality_warning"] = (f"Gaia DR3 {gid} has RUWE {s.ruwe:.1f} (> 1.4): its astrometry may be "
                                                  "unreliable (unresolved binary?), so the predicted track can be off.")
    except Exception:  # Gaia down: SIMBAD values stand, labelled and marked degraded
        # Without the mark this answer looked final: it was cached for a week and a pinned view built from it got a
        # different key from the same link built an hour later with Gaia back (found 2026-11-14 on Barnard's Star).
        t.extra["warning"] = "Gaia lookup failed: position and motion are SIMBAD's J2000 values, not Gaia DR3"
    if k_mag is not None:
        t.extra["k_mag"] = k_mag
    if o.main_id == "V* RW Aur":
        try:
            b = await GaiaClient(client).by_id([156430822114424576])
        except Exception:  # Gaia down: B's kinematics from the verified offline table (never A's RUWE-16 values)
            b = []
        if b and b[0].pmra is not None:
            t.pmra, t.pmdec, t.plx, t.rv = b[0].pmra, b[0].pmdec, b[0].parallax, None
            t.astrometry_source = "Gaia DR3 A position; B PM/parallax (A RUWE=16)"
        else:
            off = offline_target("V* RW Aur", query)
            assert off is not None
            off.otype, off.spt = t.otype or off.otype, t.spt or off.spt
            off.extra.update(t.extra)
            off.extra["warning"] = "Gaia unreachable: RW Aur B kinematics from the offline table"
            t = off
    return t


async def epoch_guard(
    ra: float, dec: float, client: Any | None
) -> tuple[Target | None, dict[str, Any] | None, str | None]:
    """Typed coordinates: is this a high-PM object at another epoch (P0-1)? Returns (object, hint, label)."""
    cands: list[Target] = []
    if client is not None:
        try:
            from spherex.external.simbad import SimbadClient

            for o in await SimbadClient(client).high_pm_cone(ra, dec, 0.1):
                if o.ra is not None and o.dec is not None:
                    cands.append(
                        Target(
                            query="",
                            kind="star",
                            name=o.main_id,
                            ra=o.ra,
                            dec=o.dec,
                            epoch=2000.0,
                            pmra=o.pmra,
                            pmdec=o.pmdec,
                            plx=o.plx,
                            main_id=o.main_id,
                            otype=o.otype,
                            spt=o.sp_type,
                            astrometry_source="SIMBAD J2000 (linear)",
                        )
                    )
        except Exception:
            cands = []
    if not cands:
        for ident in OFFLINE:
            t = offline_target(ident, "")
            if t is not None and sep_arcsec(ra, dec, t.ra, t.dec) < 0.1 * 3600 * 3:  # cheap prefilter (18′)
                cands.append(t)
    now = mjd_now()
    best: tuple[Target, float, float] | None = None
    for t in cands:
        yr, sep = epoch_of_match(ra, dec, t)
        if sep < 3.0 and (best is None or sep < best[2]):
            best = (t, yr, sep)
    if best is None:
        return None, None, None
    t, yr, sep = best
    nra, ndec = (float(v[0]) for v in t.pos([now]))
    if abs(yr - decimal_year(now)) <= 1.0:
        return t, None, f"{t.name} ({int(decimal_year(now))} position)"
    pa = pa_deg(ra, dec, nra, ndec)
    hint = dict(
        object=t.name,
        epoch=round(yr, 2),
        sep_arcsec=round(sep, 2),
        now_ra=nra,
        now_dec=ndec,
        moved_arcmin=round(sep_arcsec(ra, dec, nra, ndec) / 60, 2),
        direction=compass(pa),
    )
    return t, hint, None


def coords_target(query: str, ra: float, dec: float) -> Target:
    return Target(
        query=query, kind="coords", name=f"{ra:.5f} {dec:+.5f}", ra=ra, dec=dec, epoch=decimal_year(mjd_now())
    )


def to_result(t: Target, hint: dict[str, Any] | None = None, label: str | None = None) -> dict[str, Any]:
    now = mjd_now()
    if t.kind == "sso":
        nra, ndec = t.ra, t.dec
        now = float(_time(now).mjd)
    else:
        nra, ndec = (float(v[0]) for v in t.pos([now]))
    return dict(
        query=t.query,
        kind=t.kind,
        name=t.name,
        main_id=t.main_id,
        ra=t.ra,
        dec=t.dec,
        epoch=t.epoch,
        pm=(t.pmra, t.pmdec) if t.pmra is not None and t.pmdec is not None else None,
        plx=t.plx,
        rv=t.rv,
        otype=t.otype,
        spt=t.spt,
        astrometry_source=t.astrometry_source,
        propagated_now=dict(ra=nra, dec=ndec, epoch=round(decimal_year(now), 3)),
        epoch_hint=hint,
        label_hint=label,
    )


async def resolve_sso(name: str, client: Any) -> Target:
    if client is None:
        raise NeedsUpstream("Horizons ephemerides require a recorded or live Horizons client")
    from .external.horizons import positions

    mjd = mjd_now()
    try:
        rows = await positions(client, name, [mjd])
    except ValueError as e:     # not a body Horizons knows (or several match): a lookup failure, not a crash
        raise ResolveError(f"JPL Horizons could not identify {name!r}: {e}"[:300]) from None
    except Exception as e:  # retries exhausted, HTTP error, transport error
        raise UpstreamError(f"JPL Horizons is not answering ({type(e).__name__})") from None
    return Target(
        query="sso:" + name,
        kind="sso",
        name=name,
        ra=rows[0][0],
        dec=rows[0][1],
        epoch=decimal_year(mjd),
        extra={"ephemeris": {str(mjd): rows[0]}, "command": name},
    )
