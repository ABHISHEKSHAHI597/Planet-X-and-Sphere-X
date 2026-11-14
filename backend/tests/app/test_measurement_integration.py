"""M↔P route integration: unavailable real calibration is an explicit 409, not a placeholder."""

import asyncio

import httpx
import numpy as np

from app.schemas import AstrometryResponse, SpectrumResponse
from spherex.external.horizons import positions, spacecraft_vectors


def test_horizons_returns_requested_order_and_duplicates():
    def handler(req):
        if req.url.params["EPHEM_TYPE"] == "'VECTORS'":
            text = "$$SOE\n2460000,a,1,2,3,0,0,0\n2460001,b,4,5,6,0,0,0\n$$EOE"
        else:
            text = "$$SOE\na,,,20,-10,\nb,,,30,-20,\n$$EOE"
        return httpx.Response(200, json={"result": text})

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            out = await positions(client, "Pluto", [60001, 60000, 60001])
            assert out == [(30, -20), (20, -10), (30, -20)]
            vec = await spacecraft_vectors(client, [60001, 60000, 60001])
            assert np.array_equal(vec, [[4, 5, 6], [1, 2, 3], [4, 5, 6]])

    asyncio.run(run())


def test_science_route_modules_are_implemented():
    from app import measurement

    for name in ["spectrum_api", "astrometry_api", "lightcurve_api", "sso_api", "movers_api"]:
        assert callable(getattr(measurement, name))


def test_native_input_selection_avoids_other_detectors_and_capped_frames(monkeypatch):
    from dataclasses import asdict
    from types import SimpleNamespace

    import pytest
    from fastapi import HTTPException

    from app import measurement
    from spherex.types import FrameRef

    refs = [
        FrameRef("https://example.invalid/" + name, name, "spherex_qr2", name, band, 61000.0)
        for name, band in [("short.fits", 1), ("long.fits", 6), ("capped.fits", 6)]
    ]
    manifest = dict(
        _plan=dict(grid_args=[1.0, 2.0, 6.0, 6.15]),
        _refs=[asdict(r) for r in refs],
        frames=[dict(id=r.id, skipped="cap" if r.id == "capped.fits" else None) for r in refs],
    )
    captured = []

    async def fetch(svc, m, selected):
        captured.extend(selected)
        assert m["_plan"]["grid_args"][2] == 30
        return []

    monkeypatch.setattr(measurement, "_raws", fetch)
    svc = SimpleNamespace(calib_spec=("locked",), store=SimpleNamespace(manifest=lambda key: manifest))
    with pytest.raises(HTTPException, match="No native frames"):
        asyncio.run(measurement.inputs(svc, 1, 2, key="fixed", detectors=(6,), min_fov=30))
    assert [r.id for r in captured] == ["long.fits"]
    assert manifest["_plan"]["grid_args"][2] == 6  # displayed grid stays immutable


def test_sso_measurement_uses_exact_ephemeris_not_fixed_display_position():
    from app.measurement import target_from_manifest

    m = dict(
        target=dict(kind="sso"),
        _plan=dict(
            target=dict(
                query="sso:Pluto",
                kind="sso",
                name="Pluto",
                ra=1.0,
                dec=2.0,
                extra=dict(ephemeris={"60000.0": [20.0, -10.0], "60001.0": [21.0, -11.0]}),
            )
        ),
    )
    t = target_from_manifest(m, 1.0, 2.0, True)
    ra, dec = t.pos([60001.0, 60000.0])
    assert np.array_equal(ra, [21.0, 20.0]) and np.array_equal(dec, [-11.0, -10.0])
    fixed = target_from_manifest(m, 1.0, 2.0, False)
    assert fixed.kind == "coords"


def test_measurement_contracts_keep_quality_and_failures():
    spectrum = SpectrumResponse(
        ra=1,
        dec=2,
        rows=[],
        indices=None,
        validity="unvalidated",
        notes=[],
        skipped=[["frame", "unconstrained"]],
        photometric_scales=["qr2"],
    )
    assert spectrum.skipped[0][1] == "unconstrained"
    astro = AstrometryResponse(
        name="test",
        points=[],
        fit=None,
        catalogue=None,
        validity="unvalidated",
        registration=[dict(before=[0.5, 0.5], after=[0.1, 0.1])],
    )
    assert astro.registration[0]["after"] == [0.1, 0.1]
    joint = AstrometryResponse.model_validate(
        dict(
            astro.model_dump(),
            joint_fits=[dict(visit="V2", n_frames=16)],
            notes=["Conditional native visit covariance"],
        )
    )
    assert joint.model_dump()["joint_fits"][0]["n_frames"] == 16
    assert joint.notes == ["Conditional native visit covariance"]


def test_planetx_invalid_time_axis_rejected_before_native_acquisition(monkeypatch):
    from types import SimpleNamespace

    import pytest
    from fastapi import HTTPException

    from app import measurement

    async def no_fetch(*args):
        pytest.fail("invalid Planet X view must not acquire expensive native frames")

    monkeypatch.setattr(measurement, "native_detections", no_fetch)
    svc = SimpleNamespace(store=SimpleNamespace(manifest=lambda key: dict(axis="band-first", params=dict(fov=12))))
    with pytest.raises(HTTPException, match="per-day"):
        asyncio.run(measurement.movers_api(svc, "fixed", "planetx"))


def test_raw_stack_and_png_share_science_pixels(fixture_client):
    # Filled display cores are allowed only in f16; ?raw=1 always re-encodes science f32.
    from spherex.render import to_f16

    from .conftest import BARNARD_PIN, wait_view

    result = wait_view(fixture_client, dict(q="Barnard's Star", pin=BARNARD_PIN, bands="6"))
    m = result["manifest"]
    st = next(s for s in m["stacks"] if s["ready"] and s["nhits_max"] > 0)
    base = f"/api/v1/views/{m['key']}/stack/{st['bin']}/{st['band']}"
    science = fixture_client.get(base + ".f32")
    raw = fixture_client.get(base + ".f16?raw=1")
    assert science.status_code == 200 and raw.status_code == 200
    assert raw.content == to_f16(np.frombuffer(science.content, "<f4"))
    png = fixture_client.get(f"/api/v1/views/{m['key']}/png/{st['bin']}/{st['band']}.png?raw=1")
    assert png.status_code == 200 and png.content.startswith(b"\x89PNG")
