"""ParallaX Lite: the exporter names files exactly as the browser asks for them (frontend/tests/lite.test.ts)."""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
_spec = importlib.util.spec_from_file_location("make_lite", REPO / "scripts" / "make_lite.py")
assert _spec and _spec.loader
make_lite = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(make_lite)

# The same pairs as FILES in frontend/tests/lite.test.ts.
FILES = [
    ("/views/abc123/manifest", "api/views/abc123/manifest.json"),
    ("/views/abc123/stack/V1/6.f16", "api/views/abc123/stack/V1/6.f16"),
    ("/views/abc123/stack/V1/6.f16?raw=1", "api/views/abc123/stack/V1/6.f16"),
    ("/views/abc123/stack/B2026-01-05%3A14d/3.flags.u32", "api/views/abc123/stack/B2026-01-05_14d/3.flags.u32"),
    ("/views/abc123/frames?sort=time&band=4", "api/views/abc123/frames@band_4_sort_time.json"),
    ("/views/abc123/blink25", "api/views/abc123/blink25.json"),
    ("/views/abc123/blink25/2mass_ks.f16", "api/views/abc123/blink25/2mass_ks.f16"),
]


@pytest.mark.parametrize(("url", "name"), FILES)
def test_file_names_match_the_browser(url: str, name: str) -> None:
    assert make_lite.lite_file(url) == name


def test_payload_urls_are_found_at_any_depth() -> None:
    body = {"url": "/api/v1/views/k/blink25/a.f16", "epochs": [{"url": "/api/v1/views/k/blink25/b.f16"}, {"url": None}],
            "label": "/not/ours"}
    assert sorted(make_lite._payload_urls(body)) == ["/api/v1/views/k/blink25/a.f16", "/api/v1/views/k/blink25/b.f16"]


def test_a_static_copy_never_offers_what_needs_the_server() -> None:
    for cap in ("spectrum", "astrometry", "lightcurve", "export", "candidates", "movers", "diff"):
        assert cap not in make_lite.STATIC_CAPABLE
