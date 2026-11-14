"""DiffInfo.photometric_match contract (decision record 0008, CONTRACTS.md 2026-11-09): the report that
cube.diff produces for a cross-release pair survives the JSON cache (strict JSON: no numpy scalars, no NaN) and
validates against the response model, as do the annotations built from it."""
import json

import numpy as np

from app.schemas import DiffAnnotation, PhotometricMatch
from spherex.cube import annotate, diff
from spherex.grid import make_grid
from tests.synthetic.test_synthetic_photmatch import DEC0, GAIN, RA0, _gain, _pair, _scene


def test_cross_release_report_is_strict_json_and_matches_the_schema():
    grid = make_grid(RA0, DEC0, 8.6)
    st = _scene(seed=25)
    ca, cb, sky, fw = _pair(st, _gain(st, GAIN), grid, seed=36)
    df = diff(ca, cb, sky, n_boot=40)
    pm = df.photometric_match
    text = json.dumps(pm, allow_nan=False)                 # science.diff_info caches exactly this
    m = PhotometricMatch.model_validate(json.loads(text))
    assert m.applied and m.cross_release and m.scales_b == ["qr2"] and len(m.bins) == len(ca.cube)
    assert "arrays" not in pm                              # internal arrays never leak into the API
    x, y = (float(v) for v in grid.wcs.world_to_pixel_values(st[0].x, st[0].y))
    r = annotate(df, [(x, y)], fw / grid.pix_arcsec, grid.pix_arcsec)[0]
    if r["kind"] == "monopole":                            # what science.diff_info sends for it
        a = DiffAnnotation(kind="monopole", ra=0.0, dec=0.0, label=r["label"],
                           sign=("brightened" if r["flux"] > 0 else "faded") if r.get("comparable", True) else None)
        assert a.sign is None
    assert np.isfinite(m.scale) and m.scale_err > 0
