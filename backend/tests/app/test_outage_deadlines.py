"""Archive hangs (IRSA TAP recovering from an outage, 2026-11-15) never hold a request for minutes: the Gaia step of a
name lookup falls back to SIMBAD's values, and a catalogue overlay answers a clear 503, each on a deadline."""
import asyncio
import types

import httpx

from app import science
from spherex import targets
from tests.app.test_audit_2026_11_10 import _client, no_backoff  # noqa: F401  (fixture)


def test_overlay_gives_up_on_its_deadline(tmp_path, monkeypatch):
    import app.main as main

    async def hang(*a, **k):
        await asyncio.sleep(30)

    monkeypatch.setattr(science, "overlay", hang)
    monkeypatch.setattr(main, "OVERLAY_DEADLINE_S", 0.05)
    with _client(tmp_path, lambda req: httpx.Response(200)) as c:
        r = c.get("/api/v1/overlays/gaia", params={"ra": 10.0, "dec": 20.0, "mjd": 61000})
    assert r.status_code == 503
    assert "gaia catalogue (via IRSA) did not answer" in r.json()["detail"]


def test_gaia_step_of_a_lookup_is_bounded_and_falls_back_to_simbad(monkeypatch):
    from spherex.external import gaia, simbad

    obj = types.SimpleNamespace(ra=161.088, dec=-61.21, pmra=-346.2, pmdec=1611.1, plx=207.0, main_id="L  143-23",
                                otype="PM*", sp_type="M5.5V", oid=1)

    async def by_identifier(self, ident):
        return obj

    async def k_mag(self, oid):
        return 7.5

    async def gaia_id(self, oid):
        return 5254061535052907008

    async def hang(self, ids):
        await asyncio.sleep(30)

    monkeypatch.setattr(simbad.SimbadClient, "by_identifier", by_identifier)
    monkeypatch.setattr(simbad.SimbadClient, "k_mag", k_mag)
    monkeypatch.setattr(simbad.SimbadClient, "gaia_dr3_id", gaia_id)
    monkeypatch.setattr(gaia.GaiaClient, "by_id", hang)
    monkeypatch.setattr(targets, "GAIA_STEP_S", 0.05)
    t = asyncio.run(targets.resolve_name("LHS 288", object()))
    assert t.astrometry_source == "SIMBAD J2000 (linear)" and t.pmdec == 1611.1
    assert "Gaia lookup failed" in t.extra["warning"] and t.extra["k_mag"] == 7.5


def test_coverage_gives_up_on_its_deadline(tmp_path, monkeypatch):
    import app.main as main

    async def hang(*a, **k):
        await asyncio.sleep(30)

    monkeypatch.setattr(main, "PLAN_DEADLINE_S", 0.05)
    with _client(tmp_path, lambda req: httpx.Response(200)) as c:
        monkeypatch.setattr(c.app.state.svc.coverage, "coverage", hang)
        r = c.get("/api/v1/coverage", params={"ra": 10.0, "dec": 20.0})
    assert r.status_code == 503
    assert "coverage took longer than" in r.json()["detail"]
