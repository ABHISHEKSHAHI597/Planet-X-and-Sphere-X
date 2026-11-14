"""Public Gaia/Horizons responses retained with hashes, genuine mission epochs."""

import asyncio
import gzip
import hashlib
import json
from pathlib import Path

import numpy as np
from astropy.io import fits

from spherex.access.http import make_client
from spherex.access.pins import load
from spherex.access.replay import ReplayTransport
from spherex.access.s3sections import S3SectionSource
from spherex.ephem import verify_observer
from spherex.external.horizons import spacecraft_vectors

DATA = Path(__file__).parents[1] / "data/real"
ROOT = Path(__file__).resolve().parents[3]


def test_measurement_reference_recording_hashes():
    for p in (DATA / "recorded/measurement").glob("*/index.json"):
        for meta in json.loads(p.read_text()).values():
            body = gzip.decompress((p.parent / meta["file"]).read_bytes())
            assert len(body) == meta["bytes"]
            assert hashlib.sha256(body).hexdigest() == meta["sha256"]
            assert meta["retrieved"]
            assert meta["status"] in (200, 206)


def test_recorded_three_epoch_observer_against_horizons():
    async def run():
        headers = [fits.getheader(p, "IMAGE") for p in (DATA / "f2").glob("*cutout.fits")]
        rdra = load("152b410215da", ROOT / "config/pins")
        third = min(rdra.frames, key=lambda f: f.t_min)
        async with make_client(ReplayTransport(DATA / "recorded/measurement/references")) as client:
            doc = await S3SectionSource(client).headers(third.s3_key)
            headers.append(doc["IMAGE"].header)
            vectors = await spacecraft_vectors(client, [h["MJD-AVG"] for h in headers])
        actual = np.array([[h[k] for k in ("X_SC", "Y_SC", "Z_SC")] for h in headers])
        result = verify_observer(actual, vectors, "ICRF")
        assert len(headers) >= 3 and result["passed"]
        assert max(result["delta_km"]) < 10

    asyncio.run(run())
