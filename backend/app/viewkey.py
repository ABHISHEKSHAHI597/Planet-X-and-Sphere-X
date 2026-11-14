"""View parameters, canonicalisation and view keys (implementation.md §2.3, §5.3).

* `normalize` validates a POST /views body (the frontend's `viewParams`, url.ts) and fills defaults that
  mirror `frontend/src/state/url.ts` DEFAULTS. Unknown parameters are ignored (URL schema is additive).
* The view key is `sha256(canonical compute-params + "\n" + frame_list_digest(F))`, F = sorted frame access
  URLs hashed exactly like D's `access/pins.py`, so the key changes only when frames covering *this* view
  change. Display-only parameters (stretch, cmap, mode, a/b, fps, overlays, flags, partial, bands, t, ui,
  sel) don't enter the key: identical computations share one cache entry whatever the display.
  Deviation recorded in implementation.md §5.3 (2026-11-07, P): `bands` selects the band computed *first*
  (band-first planning) but every view computes all bands, so it is not part of the key.
* `pin` freezes F (config/pins/<pin>.json) and is part of the key through F itself.
* `pv` (PIPELINE_VERSION) and `cal` (calibration lock) are part of the canonical string, so a code change that
  alters pixels, or a new calibration lock, gives new keys instead of serving cached stacks that the current code
  would not produce (audit K-16). Bump PIPELINE_VERSION in any change that alters stack, cube or diff pixels.
* `fill` (1 when the `bright_fill` capability is shown here, else 0) is part of it too: the shown stack of a view
  built where model-filled cores are allowed differs from one built where they are not. Without it a laptop build
  (fill on) was served unchanged by a staging host (fill off), unvalidated filled cores included (browser test
  2026-11-14)."""
from __future__ import annotations

import hashlib
import re
from typing import Any

from spherex.access.pins import frame_list_digest

DEFAULTS: dict[str, str] = {"fov": "6", "px": "3", "axis": "auto", "partial": "0", "bands": "6", "center": "fixed",
                            "mask": "auto", "rel": "auto", "lim": "zscale"}
VIEW_PARAMS = ("q", "ra", "dec", "fov", "px", "axis", "partial", "bands", "center", "mask", "rel", "pin", "lim")
COMPUTE_PARAMS = ("target", "ra", "dec", "fov", "px", "axis", "center", "mask", "rel", "lim", "pv", "cal", "fill")
# 2: 2026-11-10 audit pass (per-frame error isolation, frames freed per bin, 32' fetch preset, axis rule).
PIPELINE_VERSION = "2"
MAX_BIN_DAYS = 365

_AXIS = re.compile(r"^(auto|visit|survey|exposure|multi|bin:\d{1,3}d)$")
_BANDS = re.compile(r"^([1-6](,[1-6]){0,5}|rgb:[1-6],[1-6],[1-6]|rgb:(ice|methane|thermal))$")
_LIM = re.compile(r"^(zscale|p\d{2}(\.\d+)?|manual:-?[\d.e+-]+,-?[\d.e+-]+)$")
_PIN = re.compile(r"^[0-9a-f]{12}$")
MASKS = ("auto", "discovery", "bright", "imaging", "photometry")
RGB_BANDS = {"ice": 4, "methane": 4, "thermal": 4}   # presets live in band 4 (cube.RGB_PRESETS)


class ParamError(ValueError):
    pass


def normalize(raw: dict[str, Any], max_fov: float = 60.0) -> dict[str, str]:
    p = {k: str(v).strip() for k, v in raw.items() if k in VIEW_PARAMS and v is not None and str(v).strip() != ""}
    if "q" not in p and not ("ra" in p and "dec" in p):
        raise ParamError("give a target name (q) or both ra and dec")
    out = {**DEFAULTS, **p}
    try:
        fov = float(out["fov"])
        px = float(out["px"])
    except ValueError as e:
        raise ParamError(f"fov and px must be numbers: {e}") from None
    if not 2.0 <= fov <= max_fov:
        raise ParamError(f"fov must be between 2 and {max_fov:g} arcmin (implementation.md §9)")
    if not 1.0 <= px <= 60.0:
        raise ParamError("px must be between 1 and 60 arcsec")
    out["fov"], out["px"] = f"{fov:g}", f"{px:g}"
    for k, rx in (("axis", _AXIS), ("bands", _BANDS), ("lim", _LIM)):
        if not rx.match(out[k]):
            raise ParamError(f"bad {k}={out[k]!r}")
    if out["axis"].startswith("bin:") and not 1 <= int(out["axis"][4:-1]) <= MAX_BIN_DAYS:
        raise ParamError(f"axis=bin:<N>d needs 1 ≤ N ≤ {MAX_BIN_DAYS} days")
    if out["center"] not in ("fixed", "track"):
        raise ParamError("center must be fixed or track")
    if out["mask"] not in MASKS:
        raise ParamError(f"mask must be one of {MASKS}")
    if out["partial"] not in ("0", "1"):
        raise ParamError("partial must be 0 or 1")
    if "pin" in out and not _PIN.match(out["pin"]):
        raise ParamError("pin must be 12 lowercase hex digits")
    if not re.match(r"^[a-z][a-z0-9_]*$", out["rel"]):
        raise ParamError("bad rel")
    return out


def selected_band(bands: str) -> int:
    if bands.startswith("rgb:"):
        rest = bands[4:]
        return int(rest.split(",")[0]) if rest[0].isdigit() else RGB_BANDS.get(rest, 4)
    return int(bands.split(",")[0])


def canonical(compute: dict[str, Any]) -> str:
    """Sorted key=value pairs; floats as given (callers round coordinates to 1e-5°)."""
    return "&".join(f"{k}={compute[k]}" for k in sorted(compute) if compute[k] not in (None, ""))


def view_key(canon: str, frame_urls: list[str]) -> str:
    return hashlib.sha256((canon + "\n" + frame_list_digest(frame_urls)).encode()).hexdigest()[:24]


def round_deg(x: float) -> str:
    return f"{round(float(x), 5):.5f}"
