"""Nightly live checks (`pytest -m network`, workflow.md §9.5): the services D depends on still answer the
way the recorded fixtures say. Never run in offline CI."""
import asyncio

import pytest

from spherex.access.coverage import CoverageClient
from spherex.access.dedup import dedup
from spherex.access.fitsstream import IrsaCutoutSource
from spherex.access.frames import FrameBox
from spherex.access.http import IBE_PREFIX, make_client
from spherex.access.releases import load as load_registry
from spherex.access.s3list import list_s3
from spherex.external.simbad import SimbadClient
from spherex.types import FrameRef

pytestmark = pytest.mark.network
REG = load_registry()
KEY = "qr3/level2/2026W33_2A/l2b-v27-2026-241/6/level2_2026W33_2A_0594_4D6_spx_l2b-v27-2026-241.fits"


def run(f):
    async def go():
        async with make_client() as c:
            return await f(c)
    return asyncio.run(go())


def test_live_sia2_barnard_at_least_pinned():
    rows = run(lambda c: CoverageClient(c, REG).sia2(269.4461, 4.7707))
    assert len(dedup(rows, REG).frames) >= 359


def test_live_s3_has_registered_releases_only_or_reports():
    top = run(lambda c: list_s3(c, "", "/"))
    assert {"qr2/", "qr3/"} <= set(top.prefixes)


def test_live_cutout_stream_abort():
    ref = FrameRef(IBE_PREFIX + KEY, KEY, "spherex_qr3", "x", 6, 0.0)
    f = run(lambda c: IrsaCutoutSource(c).fetch(ref, FrameBox(269.4461, 4.7707, 0.05)))
    assert f.origin == (638, 1919)


def test_live_simbad_alias_trap_still_holds():
    out = run(lambda c: SimbadClient(c).by_identifier("WISE 0855-0714"))
    assert out is None
