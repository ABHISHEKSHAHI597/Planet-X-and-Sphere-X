"""L0 of P's temporary targets adapter (app/adapters/targets.py; M's targets.py replaces it). These are
plumbing checks; G1's resolver and epoch-guard acceptance (owner M) is a separate record."""
import asyncio

import pytest

from app.adapters.targets import NeedsUpstream, ResolveError, epoch_guard, parse_coords, resolve_name


def test_coordinate_formats():
    assert parse_coords("269.4461 4.7707") == pytest.approx((269.4461, 4.7707))
    ra, dec = parse_coords("08:55:10.831 −07:14:42.53")                 # U+2212 minus
    assert abs(ra - 133.7951292) < 1e-5 and abs(dec + 7.2451472) < 1e-5
    assert parse_coords("Barnard's Star") is None


def test_offline_names_and_upstream_refusals():
    for q in ("Barnard's Star", "WISE 0855−0714", "eps Ind B", "RW Aur", "R Dra"):
        t = asyncio.run(resolve_name(q, None))
        assert t.kind == "star", q
    with pytest.raises(NeedsUpstream):
        asyncio.run(resolve_name("sso:Pluto", None))
    with pytest.raises(ResolveError):
        asyncio.run(resolve_name("definitely not a star 12345", None))


def test_challenge_coordinate_epoch_hint():
    """implementation.md §10.1 / P0-1: the challenge's WISE 0855 coordinate is ≈2010 epoch, ≈2.2′ from now."""
    ra_in, dec_in = parse_coords("08:55:10.831 -07:14:42.53")
    obj, hint, _label = asyncio.run(epoch_guard(ra_in, dec_in, None))
    assert obj is not None and hint is not None
    assert abs(hint["epoch"] - 2010.4) < 0.5
    assert 1.8 < hint["moved_arcmin"] < 2.6
