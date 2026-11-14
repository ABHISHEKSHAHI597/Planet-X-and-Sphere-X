"""Server-rendered PNG frames (P0-8 fallback viewer, implementation.md §6.4) and animated exports (P2-7).

Same pixels as the WebGL viewer: I's `render.stretch` is the CPU twin of the shader, the colour LUTs are F's
`frontend/fixtures/colormaps.json` (rgba8-256@1, index = round(t·255), no-data RGB 46,26,56), and the limits
are the manifest's SHARED limits (never per frame, workflow.md §11.2). Payload rows run south → north;
PNG rows run top = north, so the array is flipped vertically, never horizontally (east stays left)."""
from __future__ import annotations

import io
import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray
from PIL import Image

from spherex.constants import NODATA_F16
from spherex.render import stretch as cpu_stretch

from .settings import REPO

COLORMAPS = REPO / "frontend" / "fixtures" / "colormaps.json"
CMAPS = ("gray", "magma", "cividis", "diverging")
_STRETCH = re.compile(r"^(lin|sqrt|log|asinh|diverging)(?::(\d+(?:\.\d+)?))?$")


class RenderError(ValueError):
    pass


@lru_cache(maxsize=1)
def colormaps(path: Path = COLORMAPS) -> tuple[dict[str, NDArray[np.uint8]], tuple[int, int, int]]:
    d = json.loads(path.read_text(encoding="utf-8"))
    if d.get("format") != "rgba8-256@1":
        raise RenderError(f"unknown colormap format {d.get('format')!r}")
    maps = {k: np.asarray(v, np.uint8).reshape(256, 4) for k, v in d["maps"].items()}
    r, g, b = d["nodata_rgb"]
    return maps, (int(r), int(g), int(b))


def parse_stretch(s: str) -> tuple[str, float]:
    m = _STRETCH.match(s or "asinh:8")
    if not m:
        raise RenderError(f"bad stretch {s!r}: lin | sqrt | log[:β] | asinh[:β]")
    return m[1], float(m[2]) if m[2] else 8.0


def parse_manual(lim: str) -> tuple[float, float] | None:
    if not lim or not lim.startswith("manual:"):
        return None
    try:
        lo, hi = (float(v) for v in lim[7:].split(","))
    except ValueError:
        raise RenderError(f"bad lim {lim!r}") from None
    if not (np.isfinite(lo) and np.isfinite(hi) and hi > lo):
        raise RenderError("manual limits need finite lo < hi")
    return lo, hi


def decode_f16(buf: bytes, shape: tuple[int, int]) -> NDArray[np.float64]:
    a = np.frombuffer(buf, "<f2").astype(float).reshape(shape)
    a[a == NODATA_F16] = np.nan
    return a


def rgba(img: NDArray[Any], lo: float, hi: float, stretch: str = "asinh:8", cmap: str = "gray") -> NDArray[np.uint8]:
    """(ny, nx) float (row 0 = south, NaN = no data) → (ny, nx, 4) uint8 with row 0 = NORTH."""
    if cmap not in CMAPS:
        raise RenderError(f"cmap must be one of {CMAPS}")
    mode, beta = parse_stretch(stretch)
    maps, nod = colormaps()
    t = cpu_stretch(img, lo, hi, mode, beta)
    fin = np.isfinite(t)
    idx = np.where(fin, np.round(np.nan_to_num(t) * 255), 0).astype(np.int64).clip(0, 255)
    out = maps[cmap][idx].copy()
    out[~fin] = (*nod, 255)
    return np.ascontiguousarray(np.flipud(out))


def png_bytes(img: NDArray[Any], lo: float, hi: float, stretch: str = "asinh:8", cmap: str = "gray") -> bytes:
    buf = io.BytesIO()
    Image.fromarray(rgba(img, lo, hi, stretch, cmap), "RGBA").save(buf, format="PNG", optimize=False)
    return buf.getvalue()


def animation_bytes(frames: list[NDArray[Any]], lo: float, hi: float, stretch: str, cmap: str, fmt: str,
                    fps: float = 2.0, labels: list[str] | None = None) -> bytes:
    """GIF or APNG of a blink with the shared stretch. Labels (bin labels) are burnt in when given."""
    if fmt not in ("gif", "apng"):
        raise RenderError("animated export formats: gif, apng (mp4 needs ffmpeg on the server)")
    if not frames:
        raise RenderError("nothing to export")
    ims = []
    for i, f in enumerate(frames):
        im = Image.fromarray(rgba(f, lo, hi, stretch, cmap), "RGBA")
        if labels:
            from PIL import ImageDraw
            d = ImageDraw.Draw(im)
            d.rectangle([0, 0, im.width, 11], fill=(0, 0, 0, 255))
            d.text((2, 0), labels[i][: max(4, im.width // 6)], fill=(255, 255, 255, 255))
        ims.append(im.convert("RGB") if fmt == "gif" else im)
    buf = io.BytesIO()
    ms = int(1000 / max(fps, 0.1))
    if fmt == "gif":
        ims[0].save(buf, format="GIF", save_all=True, append_images=ims[1:], duration=ms, loop=0)
    else:
        ims[0].save(buf, format="PNG", save_all=True, append_images=ims[1:], duration=ms, loop=0)
    return buf.getvalue()
