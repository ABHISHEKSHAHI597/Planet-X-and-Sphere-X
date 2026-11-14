"""Which `types.Calib` the pipeline uses (D's `spherex.calib`), chosen from settings.

  CALIB_ROOT set      → `calib.Calib(root)`: the locked, sha256-verified files (config/calibration.lock).
  FRAMESOURCE=fixture → `calib.SlicedCalib` from the committed calibration slices (tests/data/real).
  neither             → `UnknownLambda`: every λ lookup is NaN. Visit stacks don't read λ, so the P0 blink is
                        unaffected; cubes, the λ-matched difference, flipbook and spectra refuse to run
                        (HTTP 409) and the manifest carries a `calibration_missing` warning. This is a refusal,
                        not a fallback: nothing is computed from a made-up wavelength (workflow.md §11.2).

Specs are plain tuples so process-pool workers can rebuild the same Calib (spawn on Windows/macOS)."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np

from .settings import BACKEND

FIXTURE_DIR = BACKEND / "tests" / "data" / "real"
_CACHE: dict[tuple[str, str], Any] = {}


class UnknownLambda:
    """types.Calib with NaN λ everywhere. QR2 flux corrections are absent too (F4 is open anyway)."""
    kind = "missing"

    class _NaNMaps(dict[int, Any]):
        def __missing__(self, det: int) -> Any:
            return _NaNMap()

    def __init__(self) -> None:
        self.cwave = self._NaNMaps()
        self.cband = self._NaNMaps()
        self.fluxcorr: dict[int, Any] = {}
        self.channel = _NaNMap()


class _NaNMap:
    """A parent-detector map whose every slice is NaN of the sliced shape."""
    def __getitem__(self, sl: Any) -> Any:
        ys, xs = sl
        return np.full((ys.stop - ys.start, xs.stop - xs.start), np.nan)


def spec_for(framesource: str, calib_root: Path | None) -> tuple[str, str]:
    if calib_root is not None:
        return ("locked", str(calib_root))
    if framesource == "fixture":
        return ("fixture", str(FIXTURE_DIR))
    return ("missing", "")


def load(spec: tuple[str, str], verify: bool = False) -> Any:
    if spec in _CACHE:
        return _CACHE[spec]
    kind, root = spec
    if kind == "locked":
        from spherex.calib import Calib
        c: Any = Calib(Path(root), verify=verify)
        c.kind = "locked"
    elif kind == "fixture":
        from spherex.calib import SlicedCalib
        r = Path(root)
        cw = np.load(r / "cwave_D6_fixture_slice.npy")
        ch = np.load(r / "channel_map_fixture_slice.npy")
        c = SlicedCalib((638, 1919), {6: cw}, ch, cband={6: cw / 128.0})   # window of the 29×29 QR3 cutout
        c.kind = "fixture"
    else:
        c = UnknownLambda()
    _CACHE[spec] = c
    return c


def tag(spec: tuple[str, str]) -> str:
    """Short identity of the calibration for view keys: `locked-<lock hash>`, `fixture` or `missing`."""
    kind, _ = spec
    if kind == "locked":
        try:
            from spherex.calib import CalibrationLock
            return f"locked-{CalibrationLock.load().lock_hash()}"
        except Exception:                            # unreadable lock: still distinct from fixture/missing
            return "locked-unknown"
    return kind


def describe(spec: tuple[str, str]) -> str:
    kind, root = spec
    if kind == "locked":
        try:
            from spherex.calib import CalibrationLock
            return f"locked {CalibrationLock.load().lock_hash()} at {root}"
        except Exception as e:                       # lock missing or unreadable: say so, don't guess
            return f"locked (lock unreadable: {e}) at {root}"
    if kind == "fixture":
        return "fixture slices (committed; λ known only in the 29×29 QR3 window)"
    return "missing: λ unknown; cubes, differences and spectra disabled"
