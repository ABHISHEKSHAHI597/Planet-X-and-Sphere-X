"""Exposure flipbook route (P2-2, G5.flip) on the fixture-backed real pipeline (L2: committed real frame +
the committed calibration slices). Engineering evidence only; G5.flip's L3 criterion needs real pins."""

import numpy as np
import pytest

from spherex.cube import SPECTRAL_LABEL
from spherex.render import FORMAT_F16

from .conftest import BARNARD_PIN, wait_view


def test_flipbook_sorted_by_measured_lambda_and_payloads_decode(fixture_client):
    c = fixture_client
    m = wait_view(c, {"q": "Barnard's Star", "pin": BARNARD_PIN, "bands": "6", "fov": "6", "px": "6.15"})["manifest"]
    r = c.get(f"/api/v1/views/{m['key']}/frames", params={"band": 6, "sort": "lambda"})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["label"] == SPECTRAL_LABEL and d["format"] == FORMAT_F16 and d["sort"] == "lambda"
    assert len(d["frames"]) >= 1
    lams = [f["lam_um"] for f in d["frames"]]
    assert all(lam is not None and 4.40 < lam < 5.01 for lam in lams), lams  # band 6 is 4.412–5.002 µm
    assert lams == sorted(lams)
    ny, nx = m["grid"]["shape"]
    p = c.get(d["frames"][0]["url"])
    assert p.status_code == 200 and len(p.content) == ny * nx * 2
    a = np.frombuffer(p.content, "<f2")
    assert (a != -65504).sum() > 0.3 * a.size
    # time order is offered but labelled as mixing wavelength with time; cached index is reused
    t = c.get(f"/api/v1/views/{m['key']}/frames", params={"band": 6, "sort": "time"}).json()
    assert "not variability" in t["label"] and {f["id"] for f in t["frames"]} >= {f["id"] for f in d["frames"]}


def test_flipbook_payload_names_are_validated(fixture_client):
    c = fixture_client
    m = wait_view(c, {"q": "Barnard's Star", "pin": BARNARD_PIN, "bands": "6", "fov": "6", "px": "6.15"})["manifest"]
    assert c.get(f"/api/v1/views/{m['key']}/frames/6/..%2Fmanifest.json").status_code in (400, 404)
    assert c.get(f"/api/v1/views/{m['key']}/frames/6/index.json").status_code == 404
    assert c.get(f"/api/v1/views/{m['key']}/frames/6/0123456789abcdef.f16").status_code == 404


def test_rgb_preset_composite_shape_and_no_invented_channels(fixture_client):
    """methane needs bands 4–5; the fixture pin has only the band-6 frame, so every channel must be
    no-data (never filled from another wavelength)."""
    c = fixture_client
    m = wait_view(c, {"q": "Barnard's Star", "pin": BARNARD_PIN, "bands": "6", "fov": "6", "px": "6.15"})["manifest"]
    ny, nx = m["grid"]["shape"]
    bin_id = m["bins"]["4"][0]["id"]
    r = c.get(f"/api/v1/views/{m['key']}/rgb/{bin_id}/methane.f16")
    assert r.status_code == 200, r.text
    a = np.frombuffer(r.content, "<f2")
    assert a.size == 3 * ny * nx and np.all(a == -65504)
    assert c.get(f"/api/v1/views/{m['key']}/rgb/{bin_id}/pah.f16").status_code == 404
    assert c.get(f"/api/v1/views/{m['key']}/rgb/{bin_id}/ice.png").status_code == 400


def test_blink25_route_grids_every_epoch_and_reports_positions(fixture_client, monkeypatch):
    """Server-side 25-year blink on the fixture-backed pipeline; the archive (2MASS/WISE searches and cutouts) is
    stubbed with synthetic FITS holding one star at the target's pos(t) for that epoch. L1 for the archival side,
    L2 for the SPHEREx side (the committed Barnard frame)."""
    import spherex.access.blink25 as acc
    from app.settings import Settings
    from spherex.access.blink25 import Blink25Plan, Epoch
    from spherex.render import BLINK25_LABEL
    from tests.unit.test_blink25_grid import fake_image

    from .conftest import BARNARD_PIN, wait_view

    c = fixture_client
    m = wait_view(c, {"q": "Barnard's Star", "pin": BARNARD_PIN, "bands": "6", "fov": "6", "px": "6.15"})["manifest"]
    star_at: dict[str, tuple[float, float]] = {}

    async def fake_plan(name, pos, now_year, tm, wi, pos_source, neowise=True, k_expected=None):
        # Barnard recognised by position, Ks checked. The pinned view carries its frozen target
        # (config/pins/targets.json), whose K is SIMBAD's float (4.524), not the offline table's 4.52.
        assert k_expected == pytest.approx(4.52, abs=0.01)
        old, now = pos(2000.4), pos(now_year)
        eps = []
        for label, year in (("2MASS Ks", 2000.4), ("AllWISE W2", 2010.5), ("NEOWISE W2", 2018.0)):
            url = f"https://archive.test/{label.replace(' ', '_')}.fits"
            star_at[url] = pos(year)
            eps.append(Epoch(label, year, str(int(year)), pos(year), 0.1, images=[dict(url=url)]))
        return Blink25Plan(name, now_year, now, 6.8, eps, pos_source,
                           dict(designation="17574849+0441405", ra=old[0], dec=old[1], k_m=4.52, date="2000-05-28"),
                           {"2MASS→now": 4.54})

    async def fake_fetch(client, url, limiter=None):
        base = url.split("?")[0]
        return fake_image(star_at[base], 1.0, n=500, centre=star_at[base])

    monkeypatch.setattr(acc, "plan", fake_plan)
    monkeypatch.setattr(acc, "fetch_cutout", fake_fetch)
    monkeypatch.setattr(Settings, "network", property(lambda self: True))
    r = c.get(f"/api/v1/views/{m['key']}/blink25")
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["label"] == BLINK25_LABEL and d["fov_needed_arcmin"] == 6.8
    assert [e["label"] for e in d["epochs"]][:3] == ["2MASS Ks", "AllWISE W2", "NEOWISE W2"]
    assert d["epochs"][-1]["label"].startswith("SPHEREx")
    assert d["twomass_match"].startswith("2MASS 17574849+0441405")
    ny, nx = d["grid"]["shape"]
    from astropy.wcs import WCS

    from spherex.grid import centroids

    w = WCS(naxis=2)
    g = d["grid"]
    w.wcs.ctype, w.wcs.crval, w.wcs.crpix, w.wcs.cdelt = g["ctype"], g["crval"], g["crpix"], g["cdelt"]
    for e in d["epochs"][:3]:
        p = c.get(e["url"])
        assert p.status_code == 200 and len(p.content) == ny * nx * 2
        img = np.frombuffer(p.content, "<f2").astype(float)
        img[img == -65504] = np.nan
        img = img.reshape(ny, nx)
        x, y = w.wcs_world2pix(e["ra"], e["dec"], 0)
        cx, cy = centroids(np.nan_to_num(img), [(float(x), float(y))], half=2)[0]
        assert np.hypot(cx - x, cy - y) < 0.5, e["label"]          # the star sits at pos(t) of its epoch
    # Barnard moved ≈4.5′ between the 2MASS and SPHEREx epochs: the epoch positions say so
    from spherex.targets import sep_arcsec

    first, last = d["epochs"][0], d["epochs"][-1]
    assert 4.3 < sep_arcsec(first["ra"], first["dec"], last["ra"], last["dec"]) / 60 < 4.8
    # cached: a second request answers from the index without touching the archive
    monkeypatch.setattr(acc, "plan", None)
    assert c.get(f"/api/v1/views/{m['key']}/blink25").json() == d
    assert c.get(f"/api/v1/views/{m['key']}/blink25/../x").status_code in (400, 404)


def test_blink25_refuses_offline_and_for_non_movers(fixture_client):
    from .conftest import BARNARD_PIN, wait_view

    c = fixture_client
    m = wait_view(c, {"q": "Barnard's Star", "pin": BARNARD_PIN, "bands": "6", "fov": "6", "px": "6.15"})["manifest"]
    r = c.get(f"/api/v1/views/{m['key']}/blink25")
    assert r.status_code == 409 and "offline" in r.json()["detail"]


def test_blink25_cold_builds_are_rate_limited_shared_and_polite(fixture_client, monkeypatch):
    """P review items: a cold build counts against the per-IP job limit, concurrent requests for one view run ONE
    archive build, and cutouts go through the shared per-host limiter."""
    import asyncio

    import spherex.access.blink25 as acc
    from app import science
    from app.settings import Settings
    from spherex.access.blink25 import Blink25Plan, Epoch
    from tests.unit.test_blink25_grid import fake_image

    from .conftest import BARNARD_PIN, wait_view

    c = fixture_client
    m = wait_view(c, {"q": "Barnard's Star", "pin": BARNARD_PIN, "bands": "6", "fov": "6", "px": "6.15"})["manifest"]
    calls = {"plan": 0, "limited": 0}

    async def fake_plan(name, pos, now_year, tm, wi, pos_source, neowise=True, k_expected=None):
        calls["plan"] += 1
        await asyncio.sleep(0.05)
        p0 = pos(2010.5)
        return Blink25Plan(name, now_year, pos(now_year), 6.8,
                           [Epoch("AllWISE W2", 2010.5, "2010", p0, 0.1, images=[dict(url="https://archive.test/w2.fits")])],
                           pos_source, None, {"AllWISE→now": 2.8})

    async def fake_fetch(client, url, limiter=None):
        calls["limited"] += limiter is not None
        p0 = (m["grid"]["crval"][0], m["grid"]["crval"][1])
        return fake_image(p0, 1.0, n=500, centre=p0)

    monkeypatch.setattr(acc, "plan", fake_plan)
    monkeypatch.setattr(acc, "fetch_cutout", fake_fetch)
    monkeypatch.setattr(Settings, "network", property(lambda self: True))
    svc = c.app.state.svc
    full = svc.store.manifest(m["key"])                        # the stored manifest keeps the internal plan

    async def two():
        return await asyncio.gather(science.blink25(svc, full), science.blink25(svc, full))

    a, b = asyncio.run(two())
    assert a == b and calls["plan"] == 1 and calls["limited"] == 1
    # rate limit: only cold builds count
    other = wait_view(c, {"q": "Barnard's Star", "pin": BARNARD_PIN, "bands": "6", "fov": "7", "px": "6.15"})["manifest"]
    monkeypatch.setattr(c.app.state.view_limiter, "allow", lambda who: False)
    assert c.get(f"/api/v1/views/{m['key']}/blink25").status_code == 200            # cached: not limited
    assert c.get(f"/api/v1/views/{other['key']}/blink25").status_code == 429        # cold: limited
