"""25-year blink: data acquisition (owner D; implementation.md §4.13, workflow.md G5.25yr).

D finds and fetches the archival epochs; normalisation and display are I's and F's, positions are M's.

| epoch | source | paired SPHEREx band |
| per target, 1997–2001 (`fp_psc.jdate`) | 2MASS Atlas Ks (IBE) | 3 |
| ≈2010.5 | AllWISE Atlas W1/W2 (SIA2 wise_allwise) | 4 (W1), 6 (W2) |
| 2014–2024 | NEOWISE W2 single exposures (SIA2 neowiser), grouped in ≈6-month epochs | 6 |

The FOV is auto-sized to ≥ 1.5 × the expected jump; a 2MASS Atlas image is 8.5′ × 17′, so the plan
says when a cutout would clip and which second image to mosaic. `pos(year)` is M's position function
(targets.pos); `linear_pos` remains a compatibility signature and delegates to that model."""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from typing import Any

from ..external.twomass import TwoMassClient
from ..external.wise import WiseClient, group_epochs

PosFn = Callable[[float], tuple[float, float]]
TWOMASS_IMAGE_ARCMIN = (8.5, 17.0)
BAND_PAIRING = {"2MASS Ks": 3, "AllWISE W1": 4, "AllWISE W2": 6, "NEOWISE W2": 6}


def linear_pos(ra: float, dec: float, epoch: float, pmra: float, pmdec: float) -> PosFn:
    """Compatibility for callers that only supply PM; M owns the spherical propagation."""
    from astropy.time import Time
    from ..targets import Target

    target = Target("", "star", "legacy PM-only input", ra, dec, epoch, pmra, pmdec)

    def f(year: float) -> tuple[float, float]:
        a, d = target.pos([float(Time(year, format="jyear").mjd)])
        return float(a[0]), float(d[0])

    return f


def sep_arcmin(a: tuple[float, float], b: tuple[float, float]) -> float:
    ra1, d1, ra2, d2 = map(math.radians, (*a, *b))
    c = math.sin(d1) * math.sin(d2) + math.cos(d1) * math.cos(d2) * math.cos(ra1 - ra2)
    return math.degrees(math.acos(max(-1.0, min(1.0, c)))) * 60


def fov_for_jump(jump_arcmin: float, minimum: float = 3.0) -> float:
    return max(minimum, 1.5 * jump_arcmin)


@dataclass
class Epoch:
    label: str
    year: float
    date: str
    centre: tuple[float, float]
    size_deg: float
    images: list[dict[str, Any]] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


@dataclass
class Blink25Plan:
    target: str
    now_year: float
    now_pos: tuple[float, float]
    fov_arcmin: float
    epochs: list[Epoch]
    pos_source: str
    twomass_source: dict[str, Any] | None
    expected_jumps_arcmin: dict[str, float]
    pairing: dict[str, int] = field(default_factory=lambda: dict(BAND_PAIRING))
    label: str = "different telescopes, positions only"

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


async def plan(
    name: str,
    pos: PosFn,
    now_year: float,
    twomass: TwoMassClient,
    wise: WiseClient,
    pos_source: str,
    neowise: bool = True,
    k_expected: float | None = None,
) -> Blink25Plan:
    """k_expected: the target's catalogue Ks (understanding.md §8.1), used to confirm the 2MASS match;
    pass a value fainter than the 2MASS limit (e.g. 23 for WISE 0855) for targets 2MASS cannot see."""
    now = pos(now_year)
    epochs: list[Epoch] = []
    src = await twomass.epoch_of(*pos(2000.0), k_expected=k_expected)
    jumps: dict[str, float] = {}
    tm_dict = None
    if src is not None:
        tm_dict = dict(
            designation=src.designation,
            ra=src.ra,
            dec=src.dec,
            k_m=src.k_m,
            jdate=src.jdate,
            date=src.date,
            epoch=round(src.epoch, 3),
        )
        jumps["2MASS→now (catalogue position → pos(now))"] = sep_arcmin((src.ra, src.dec), now)
    a10 = pos(2010.5)
    jumps["AllWISE→now (pos)"] = sep_arcmin(a10, now)
    fov = fov_for_jump(max(jumps.values()))
    size = fov / 60
    if src is not None:
        old = (src.ra, src.dec)
        mid = ((src.ra + now[0]) / 2, (src.dec + now[1]) / 2)  # covers both positions
        ep = Epoch("2MASS Ks", src.epoch, src.date, mid, size)
        seen: dict[str, dict[str, Any]] = {}
        for lab, pt in (("archival", old), ("mid", mid), ("now", now)):
            for im in await twomass.images(*pt, band="k"):  # IBE: images containing this point
                e = seen.setdefault(
                    im.fname,
                    dict(
                        url=im.url(),
                        cutout=im.cutout_url(*mid, size),
                        ordate=im.ordate,
                        hemisphere=im.hemisphere,
                        scanno=im.scanno,
                        fname=im.fname,
                        contains=[],
                    ),
                )
                e["contains"].append(lab)
        ep.images = sorted(seen.values(), key=lambda e: (-len(e["contains"]), e["fname"]))
        both = [e for e in ep.images if {"archival", "now"} <= set(e["contains"])]
        if not both:
            ep.notes.append(
                "no single Atlas image holds both positions: mosaic the images listed (implementation.md §4.13)"
            )
        if not ep.images:
            ep.notes.append("no 2MASS Atlas image overlaps the target")
        epochs.append(ep)
    else:
        epochs.append(
            Epoch(
                "2MASS Ks",
                2000.0,
                "",
                pos(2000.0),
                size,
                notes=["not detected in the 2MASS PSC (e.g. WISE 0855, J ≈ 25): no 2MASS epoch"],
            )
        )
    mid10 = ((a10[0] + now[0]) / 2, (a10[1] + now[1]) / 2)
    aw = await wise.allwise(*mid10)
    for band in ("W1", "W2"):
        ep = Epoch(f"AllWISE {band}", 2010.5, "2010-01..2011-02", mid10, size)
        for wi in (i for i in aw if i.band == band):
            ep.images.append(dict(url=wi.access_url, cutout=wi.cutout_url(*mid10, size), obs_id=wi.obs_id))
        epochs.append(ep)
    if neowise:
        p17 = pos(2019.0)
        nw = await wise.neowise(
            *p17, radius_deg=max(sep_arcmin(pos(2014.0), pos(2024.0)) / 60 / 2, 0.0005), bands=("W2",)
        )
        for grp in group_epochs(nw):
            from astropy.time import Time

            t = sum(i.t_min for i in grp) / len(grp)
            yr = float(Time(t, format="mjd").decimalyear)
            c = pos(yr)
            epochs.append(
                Epoch(
                    "NEOWISE W2",
                    yr,
                    Time(t, format="mjd").to_value("iso", subfmt="date"),
                    c,
                    size,
                    images=[
                        dict(url=i.access_url, cutout=i.cutout_url(*c, size), obs_id=i.obs_id, t_min=i.t_min)
                        for i in grp
                    ],
                )
            )
    return Blink25Plan(name, now_year, now, fov, epochs, pos_source, tm_dict, jumps)


# Catalogue Ks used to confirm the 2MASS match of the acceptance targets (scripts/blink25_acquire.py,
# understanding.md §8.1). 23.0 = fainter than the 2MASS limit: WISE 0855 must NOT match the K = 15.8 neighbour.
KS_EXPECTED = {"Barnard's Star": 4.52, "eps Ind B": 11.21, "WISE 0855-0714": 23.0}


async def fetch_cutout(client: Any, url: str, limiter: Any = None) -> bytes:
    """Bytes of one archival cutout (possibly gzipped FITS), with the shared retry policy. A body that is not
    FITS (an HTML error page behind HTTP 200, seen from IRSA on 2026-11-07) is a retryable CorruptResponse.
    `limiter`: the process-wide `http.HostLimiter`, so these requests share IRSA's per-host budget with the
    FrameSources (implementation.md §3.7)."""
    import gzip

    from .fitsio import CorruptResponse
    from .retry import with_retry

    async def once() -> bytes:
        if limiter is not None:
            async with limiter.slot(url):
                r = await client.get(url, timeout=180)
        else:
            r = await client.get(url, timeout=180)
        r.raise_for_status()
        raw = r.content
        head = gzip.decompress(raw)[:9] if raw[:2] == b"\x1f\x8b" else raw[:9]
        if head != b"SIMPLE  =":
            raise CorruptResponse(f"not FITS ({len(raw)} B): {raw[:60]!r}")
        return bytes(raw)

    return await with_retry(once)
