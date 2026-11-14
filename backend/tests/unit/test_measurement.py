"""M L0: units, epochs, invalid data, normalization, observer and linking contracts."""

import numpy as np
import pytest
from astropy.coordinates import SkyCoord
from astropy.time import Time

from spherex.targets import Target, epoch_of_match, offline_target, parse_coords, propagate
from spherex.lightcurve import relative_curve, periodogram, phase_fold, annulus_measure
from spherex.photometry import ab_mag, to_uJy, methane_index, require_common_scale
from spherex.ephem import cached_position, verify_observer, topocentric_offset
from spherex.external.horizons import parse_table
from spherex.linking import link_detections, score_chain
from spherex.planetx import infer_distance, distant_body_offset


def test_propagation_catalogue_epoch_and_guard():
    t = offline_target("NAME Barnard's Star", "barnard")
    c = propagate(t.ra, t.dec, t.pmra, t.pmdec, t.plx, t.rv, Time(2016, format="jyear"), Time(2026.87, format="jyear"))
    assert c.separation(SkyCoord("17h57m47.06s +04d46m14.6s")).arcsec < 0.2
    w = offline_target("WISE J085510.83-071442.5", "wise")
    yr, sep = epoch_of_match(133.7951292, -7.2451472, w)
    assert abs(yr - 2010.46) < 0.1 and sep < 1
    pole = Target("", "star", "pole", 359.9, 89.999, 2016.0, 100.0, 100.0, 100.0)
    a, d = pole.pos([61000])
    assert np.isfinite(a[0]) and -90 <= d[0] <= 90
    for q in ["12:61:00 +01:00:00", "12:00:00 +01:00:60", "360 0"]:
        with pytest.raises(LookupError):
            parse_coords(q)


def test_units_indices_and_scale_guard():
    assert to_uJy(1, 1) == pytest.approx(23.50443, rel=1e-5)
    assert ab_mag(1) == 23.9 and np.isnan(ab_mag(-1))
    pts = [
        dict(lam=3.3, flux_uJy=2.0, err_uJy=0.1, photometric_scale="qr2"),
        dict(lam=4.1, flux_uJy=10.0, err_uJy=0.1, photometric_scale="qr2"),
    ]
    assert methane_index(pts, [1.5, 1.6, 1.4])["methane_rel"] < 0.5
    pts[0]["photometric_scale"] = "qr3"
    with pytest.raises(ValueError):
        require_common_scale(pts)
    from spherex.photometry import wise_colour
    flat=[dict(lam=float(l),flux_uJy=1.,err_uJy=.01,photometric_scale='qr2') for l in np.linspace(.75,5.,200)]
    assert wise_colour(flat)==pytest.approx(.640,abs=1e-10)


def test_lightcurve_channel_mixing_and_region():
    rows = [
        dict(
            detector=6,
            channel=ch,
            region=(0, 0),
            mjd=60000 + t,
            flux=(ch * 20.0) * (1 + 0.2 * np.sin(t / 40)),
            err=1.0,
            scale="qr2",
        )
        for t in range(0, 520, 7)
        for ch in (2, 15)
    ]
    curves = relative_curve(rows, 14, "annulus")["6"]
    assert len(curves) >= 20 and all(p["err"] > 0 for p in curves)
    del rows[0]["region"]
    with pytest.raises(ValueError):
        relative_curve(rows, 14, "annulus")
    t = np.arange(0, 550, 14)
    f = 1 + 0.5 * np.sin(2 * np.pi * t / 245)
    pg = periodogram(t, f, np.full(t.shape, 0.02))
    assert abs(pg["best_days"] - 245) < 10
    assert np.all((phase_fold(t, 245, 0) >= 0) & (phase_fold(t, 245, 0) < 1))
    with pytest.raises(ValueError):
        periodogram(t[:16], f[:16], np.ones(16))
    with pytest.raises(ValueError):
        annulus_measure(np.ones((10, 10)), np.ones((10, 10)), np.zeros((10, 10), bool), 1, 1)


def test_horizons_csv_and_observer_contract():
    assert parse_table("header\n$$SOE\n2450000, x, 1, 2, 3\n$$EOE")[0][2] == "1"
    with pytest.raises(ValueError):
        parse_table("No ephemeris for observer interval")
    with pytest.raises(ValueError):
        cached_position({}, [61000])
    h = np.zeros((3, 3))
    j = np.ones((3, 3))
    assert verify_observer(h, j, "ICRF")["passed"]
    with pytest.raises(ValueError):
        verify_observer(h, j, "GEOCENTER")
    a, d = topocentric_offset(0, 0, 1, [0, 7000, 0])
    assert a > 359.99 and abs(d) < 1e-9


def test_link_score_vetting_and_rank():
    epoch = []
    for i in range(4):
        epoch.append(
            [
                dict(
                    id=str(i),
                    xi=i * 5.0,
                    eta=0.0,
                    mjd=60000 + i * 365.25,
                    s_xi=0.05,
                    s_eta=0.05,
                    p_a=(-1.0) ** i,
                    p_d=0.0,
                    visit=str(i),
                    flags=[],
                    rchi2=1.0,
                    bright_neighbours=[],
                )
            ]
        )
    chain = max(link_detections(epoch), key=len)
    r = score_chain(chain, 0.0, 3.0)
    assert r["candidate"] and r["mu"] == pytest.approx(5)
    chain[1]["flags"] = ["PERSIST"]
    assert not score_chain(chain, 0.0, 3.0)["candidate"]
    t = np.array([60000, 60180, 60365, 60545, 60730.0])
    x, y = distant_body_offset(t, t[0], 133, -7, 500.0)
    result = infer_distance(t, x, y, np.full(5, 0.1), 133, -7)
    assert abs(result["distance_au"] - 500) < 1
