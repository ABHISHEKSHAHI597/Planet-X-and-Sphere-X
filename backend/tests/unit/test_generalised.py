"""Rules that used to be hard-coded for named targets now work for any object (2026-11-08)."""
from types import SimpleNamespace

from app.measurement import blend_neighbours, red_only
from spherex.targets import BRIGHT_K_MAG, Target, is_bright


def test_bright_preset_follows_k_magnitude_for_any_star():
    assert is_bright(Target("x", "star", "any star", 10, 10, extra={"k_mag": BRIGHT_K_MAG - 1}))
    assert not is_bright(Target("x", "star", "any star", 10, 10, extra={"k_mag": BRIGHT_K_MAG + 1}))
    # unknown brightness: only the documented fallback list
    assert not is_bright(Target("x", "star", "unknown", 10, 10))
    assert is_bright(Target("x", "star", "R Dra", 10, 10, main_id="V* R Dra"))


def test_red_only_is_any_gaia_invisible_brown_dwarf():
    assert red_only(dict(kind="star", otype="BD*", spt="Y4", astrometry_source="SIMBAD J2000 (linear)"))
    assert red_only(dict(kind="star", otype="*", spt="T8", astrometry_source="SIMBAD J2000 (linear)"))
    assert not red_only(dict(kind="star", otype="BD*", spt="T1+T6", astrometry_source="Gaia DR3 6412596012146801152"))
    assert not red_only(dict(kind="star", otype="BY*", spt="M4V", astrometry_source="SIMBAD J2000 (linear)"))
    assert not red_only(dict(kind="coords"))


def test_blend_neighbours_meets_the_star_a_fast_mover_crosses_now():
    """A 8″/yr mover 80″ from a static star in 2016 is on top of it ten years later (WISE 0855's case)."""
    mjd_2026 = 57388.5 + 10 * 365.25
    mover = Target("", "star", "mover", 10.0 + 80 / 3600, 0.0, 2016.0, pmra=-8000.0, pmdec=0.0)
    star = SimpleNamespace(source_id=1, ra=10.0 + 4 / 3600, dec=0.0, pmra=0.0, pmdec=0.0, parallax=None)
    far = SimpleNamespace(source_id=2, ra=10.0 + 80 / 3600, dec=0.0, pmra=0.0, pmdec=0.0, parallax=None)
    assert [g.source_id for g in blend_neighbours(mover, [star, far], mjd_2026)] == [1]
    assert blend_neighbours(mover, [star], 57388.5) == []          # in 2016 they were 76″ apart
