"""L0 on recorded real responses (tests/data/real/recorded/catalogs, collected 2026-11-07 through these
very clients): SIMBAD, Gaia DR3, 2MASS, AllWISE/NEOWISE, CatWISE2020, SkyBoT. No network."""
import asyncio
from pathlib import Path

import pytest

from spherex.access.http import make_client
from spherex.access.replay import ReplayTransport
from spherex.external import tap
from spherex.external.allwise import AllwiseSource, cone_sql as allwise_cone_sql
from spherex.external.catwise import CatwiseClient
from spherex.external.gaia import GaiaClient
from spherex.external.simbad import SimbadClient, by_identifier_sql, high_pm_cone_sql
from spherex.external.skybot import SkybotClient, params as skybot_params, parse_text
from spherex.external.twomass import TwoMassClient
from spherex.external.wise import WiseClient, group_epochs

REC = Path(__file__).parents[1] / "data/real/recorded/catalogs"


def run(coro_fn):
    async def go():
        async with make_client(ReplayTransport(REC)) as c:
            return await coro_fn(c)
    return asyncio.run(go())


def test_adql_escaping_and_injection():
    assert tap.adql_literal("Barnard's Star") == "'Barnard''s Star'"
    q = by_identifier_sql("x' OR '1'='1")
    assert "i.id = 'x'' OR ''1''=''1'" in q                          # quoted harmlessly
    with pytest.raises(ValueError):
        tap.adql_number(float("nan"))
    assert "> 250000.0" in high_pm_cone_sql(1, 2)                     # 0.5″/yr²


def test_simbad_names_and_traps():
    async def f(c):
        s = SimbadClient(c)
        out = {n: await s.by_identifier(n) for n in ["Barnard's Star", "* eps Ind B", "WISE J085510.83-071442.5",
                                                      "WISE 0855-0714", "V* RW Aur", "V* R Dra"]}
        b = await s.by_identifier("NAME Barnard's Star")
        return out, await s.gaia_dr3_id(b.oid), await s.high_pm_cone(133.795129, -7.245147), s.last_mirror
    out, gaia_id, cone, mirror = run(f)
    assert out["Barnard's Star"].main_id == "NAME Barnard's star"
    assert out["WISE J085510.83-071442.5"].main_id == "WISEA J085510.74-071442.5"
    assert out["WISE 0855-0714"] is None                              # needs M's alias table
    assert out["V* RW Aur"].plx == pytest.approx(15.42, abs=0.01)     # the Hipparcos-2007 trap
    assert "2007" in (out["V* RW Aur"].plx_bibcode or "")
    assert gaia_id == 4472832130942575872
    assert [o.main_id for o in cone] == ["WISEA J085510.74-071442.5"]
    assert "harvard" in mirror                                        # CfA mirror first


def test_gaia_targets_and_cone():
    async def f(c):
        g = GaiaClient(c)
        return await g.by_id([4472832130942575872, 6412596012146801152, 156430822114424576, 156430817820015232,
                              1648328016354496384, 5756956644387831296]), await g.cone(133.7578, -7.2420, 0.02)
    ids, cone = run(f)
    by = {s.source_id: s for s in ids}
    b = by[4472832130942575872]
    assert b.pmdec == pytest.approx(10362.394, abs=0.01) and b.radial_velocity == pytest.approx(-110.47, abs=0.1)
    assert by[156430822114424576].parallax == pytest.approx(6.41, abs=0.05)      # RW Aur B
    assert by[156430817820015232].ruwe > 10                                     # RW Aur A: unusable
    assert 5756956644387831296 in {s.source_id for s in cone}                   # the G = 16.3 neighbour of WISE 0855


def test_twomass_per_target_epochs_and_non_detection():
    pos2000 = {"barnard": (269.45208, 4.69336), "epsindb": (331.04415, -56.78284), "wise0855": (133.81891, -7.24705),
               "rwaur": (76.95653, 30.40144)}

    async def f(c):
        t = TwoMassClient(c)
        kexp = {"barnard": 4.52, "epsindb": 11.21, "wise0855": 23.0, "rwaur": 7.02}       # understanding.md §8.1
        naive = await t.epoch_of(*pos2000["wise0855"], 0.01)
        return ({k: await t.epoch_of(*v, 0.01, k_expected=kexp[k]) for k, v in pos2000.items()},
                await t.images(269.452, 4.6946, "k"), naive)
    ep, imgs, naive = run(f)
    assert naive is not None and naive.designation == "08551654-0714457"   # the positional trap (K = 15.8)
    assert ep["barnard"].epoch == pytest.approx(2000.405, abs=0.002) and ep["barnard"].date == "2000-05-28"
    assert ep["epsindb"].epoch == pytest.approx(1999.851, abs=0.002)
    assert ep["rwaur"].epoch == pytest.approx(1999.904, abs=0.002)
    assert ep["wise0855"] is None                                     # not detected (J ≈ 25): brightness check
    assert imgs and imgs[0].url().startswith("https://irsa.ipac.caltech.edu/ibe/data/twomass/allsky/allsky/000528n/")


def test_wise_sia_and_epoch_grouping():
    async def f(c):
        w = WiseClient(c)
        return await w.allwise(133.795129, -7.245147), await w.neowise(133.795129, -7.245147)
    aw, nw = run(f)
    assert {i.band for i in aw} <= {"W1", "W2"} and aw and all(i.collection == "wise_allwise" for i in aw)
    groups = group_epochs([i for i in nw if i.band == "W2"])
    spans = [g[-1].t_min - g[0].t_min for g in groups]
    assert len(groups) >= 15 and max(spans) < 30                      # ≈6-month NEOWISE visits of a few days
    assert "center=" in aw[0].cutout_url(1, 2, 0.1)


def test_catwise_finds_wise0855_motion():
    cw = run(lambda c: CatwiseClient(c).cone(133.78391, -7.24417, 0.01))
    fast = [s for s in cw if s.pmra is not None and s.pmra < -7000]
    assert fast and all(abs(s.pmra + 8100) < 300 for s in fast)       # mas/yr after the arcsec→mas conversion


def test_skybot_uses_loc_and_parses():
    p = skybot_params(2460928.5, 76.9565, 30.4013, 0.25)
    assert p["-loc"] == "500" and "-observer" not in p
    objs = run(lambda c: SkybotClient(c).cone(2460928.5, 76.9565, 30.4013, 0.25))
    assert objs and min(o.mv for o in objs) > 19                      # faint traffic only (understanding.md §8.5)
    assert all(abs(o.dec_deg - 30.4) < 0.3 for o in objs)
    with pytest.raises(ValueError):
        parse_text("1 | short | line")


def test_votable_overflow_is_an_error():
    raw = b"""<?xml version="1.0"?><VOTABLE version="1.3" xmlns="http://www.ivoa.net/xml/VOTable/v1.3">
    <RESOURCE type="results"><INFO name="QUERY_STATUS" value="OVERFLOW"/><TABLE><FIELD name="a" datatype="int"/>
    <DATA><TABLEDATA><TR><TD>1</TD></TR></TABLEDATA></DATA></TABLE></RESOURCE></VOTABLE>"""
    with pytest.raises(tap.QueryOverflow):
        tap.parse_votable(raw)


def test_allwise_rows_and_query():
    # Row as IRSA returned it for WISE 0855 on 2026-11-14 (cone 133.78391 -7.24417 r=0.02°, table allwise_p3as_psd).
    row = {"designation": "J085510.74-071442.5 ", "ra": 133.7947597, "dec": -7.2451456, "w1mpro": 16.231, "w2mpro": 13.704}
    s = AllwiseSource.from_row(row)
    assert s.designation == "J085510.74-071442.5" and s.w2mpro == pytest.approx(13.704)
    assert AllwiseSource.from_row({**row, "w1mpro": None}).w1mpro is None
    q = allwise_cone_sql(133.78391, -7.24417, 0.02)
    assert "FROM allwise_p3as_psd" in q and "CIRCLE('ICRS', 133.78391, -7.24417, 0.02)" in q
    with pytest.raises(ValueError):
        allwise_cone_sql(float("nan"), 0, 0.1)
