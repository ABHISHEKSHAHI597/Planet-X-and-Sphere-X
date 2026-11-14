"""Deep-field data volume and per-frame inputs (owner D; workflow.md §2.1 "R Dra's scale problem",
§10.2 "R Dra frame volume (caps, deep collections); light-curve input plumbing for M").

R Draconis lies in the NEP deep field: ≈2,480 frames, ≈1,950 of them from the `_deep` collections
(understanding.md §3.4, §8.6). This module provides the data side only:
  * `volume`: frame counts by collection (wide vs deep), detector, release and month;
  * `cap_frames`: a deterministic per-(time-bin, detector) cap for imaging views, spreading the kept
    frames evenly in time and listing every dropped frame with the reason "cap", so the manifest shows
    them (workflow.md §11.2); light curves never use a capped list;
  * `frame_inputs`: for every frame, the target's parent-detector pixel (through the frame's own full
    WCS, read from one S3 header range), the CHANNEL_MAP channel and CWAVE λ at that pixel, plus the
    header QA and timing keywords M's annulus light curve needs (same channel and detector region,
    implementation.md §4.9). Binning, normalisation and the periodogram stay M's.
"""
from __future__ import annotations

import asyncio
from collections import Counter
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass
from typing import Any

import numpy as np
from astropy.wcs import WCS

from ..types import FrameRef
from .frames import world_to_pixel
from .s3sections import S3SectionSource

HDR_KEYS = ("MJD-BEG", "MJD-AVG", "MJD-END", "SPS_EPA", "FINAST", "L1DQAFLG", "L2DQAFLG", "PSF_FWHM",
            "OMEGA_MEDIAN", "PXSRCMSK", "HE_AIRGLOW_CONT", "AURORA_CONT", "SHUTTLE_GLOW_CONT", "NBLMSRCS")


def is_deep(f: FrameRef) -> bool:
    return f.collection.endswith("_deep")


def volume(frames: Sequence[FrameRef], release_of: Callable[[str], str | None] | None = None) -> dict[str, Any]:
    from astropy.time import Time
    months = Counter(Time(f.t_min, format="mjd").to_value("iso", subfmt="date")[:7] for f in frames)
    return dict(frames=len(frames), deep=sum(map(is_deep, frames)), wide=sum(not is_deep(f) for f in frames),
                by_collection=dict(sorted(Counter(f.collection for f in frames).items())),
                by_detector={str(k): v for k, v in sorted(Counter(f.detector for f in frames).items())},
                by_release=dict(sorted(Counter((release_of or (lambda c: c))(f.collection) for f in frames).items())),
                by_month=dict(sorted(months.items())),
                mjd_span=[min(f.t_min for f in frames), max(f.t_min for f in frames)] if frames else None)


def cap_frames(frames: Sequence[FrameRef], bin_of: Callable[[FrameRef], Any],
               cap: int) -> tuple[list[FrameRef], list[tuple[str, str]]]:
    """Keep at most `cap` frames per (bin, detector), evenly spaced in time (ties broken by obs id), so a
    capped bin still spans its dates. Returns (kept, [(frame id, "cap: …")]). Deterministic."""
    if cap <= 0:
        raise ValueError("cap must be positive")
    groups: dict[tuple[Any, int], list[FrameRef]] = {}
    for f in frames:
        groups.setdefault((bin_of(f), f.detector), []).append(f)
    kept: list[FrameRef] = []
    dropped: list[tuple[str, str]] = []
    for (b, det), fs in sorted(groups.items(), key=lambda kv: (str(kv[0][0]), kv[0][1])):
        fs = sorted(fs, key=lambda f: (f.t_min, f.obs_id))
        if len(fs) <= cap:
            kept += fs
            continue
        idx = set(np.unique(np.round(np.linspace(0, len(fs) - 1, cap)).astype(int)).tolist())
        for i, f in enumerate(fs):
            if i in idx:
                kept.append(f)
            else:
                dropped.append((f.id, f"cap: {cap} frames per (bin {b}, D{det}); {len(fs)} available"))
    return sorted(kept, key=lambda f: (f.t_min, f.obs_id, f.detector)), dropped


@dataclass
class FrameInput:
    s3_key: str
    collection: str
    deep: bool
    detector: int
    obs_id: str
    t_min: float
    x: float | None          # target's 0-based parent-detector pixel (full-file WCS)
    y: float | None
    on_detector: bool
    channel: int | None      # CHANNEL_MAP at the rounded pixel (0 / 18 = outside the band)
    cwave_um: float | None
    version: str | None
    header: dict[str, Any]
    error: str | None = None


async def frame_inputs(src: S3SectionSource, frames: Sequence[FrameRef], ra: float, dec: float,
                       calib: Any | None = None, concurrency: int = 16,
                       progress: Callable[[int, int], None] | None = None) -> list[FrameInput]:
    """One S3 header walk per frame (≈30 KB; headers are cached per key). `calib` (types.Calib) adds the
    channel and λ at the target pixel; without it those fields stay None."""
    sem = asyncio.Semaphore(concurrency)
    done = 0

    async def one(f: FrameRef) -> FrameInput:
        nonlocal done
        async with sem:
            try:
                m = await src.headers(f.s3_key)
                hi = m["IMAGE"].header
                nx, ny = int(hi["NAXIS1"]), int(hi["NAXIS2"])
                xy = world_to_pixel(WCS(hi), ra, dec, nx, ny)
                x, y = xy if xy is not None else (None, None)
                on = bool(xy is not None and -0.5 <= xy[0] < nx - 0.5 and -0.5 <= xy[1] < ny - 0.5)
                ch = lam = None
                if on and calib is not None and xy is not None:
                    ix, iy = int(round(xy[0])), int(round(xy[1]))
                    ch = int(np.asarray(calib.channel)[iy, ix])
                    lam = float(np.asarray(calib.cwave[f.detector])[iy, ix])
                fi = FrameInput(f.s3_key, f.collection, is_deep(f), f.detector, f.obs_id, f.t_min, x, y, on, ch, lam,
                                str(m["PRIMARY"].header.get("VERSION", "")).strip() or None,
                                {k: hi.get(k) for k in HDR_KEYS})
            except Exception as e:  # noqa: BLE001 — recorded per frame, never silently dropped
                fi = FrameInput(f.s3_key, f.collection, is_deep(f), f.detector, f.obs_id, f.t_min, None, None, False,
                                None, None, None, {}, error=repr(e)[:200])
        done += 1
        if progress:
            progress(done, len(frames))
        return fi

    return list(await asyncio.gather(*(one(f) for f in frames)))


def inputs_table(rows: Sequence[FrameInput]) -> dict[str, Any]:
    cols = [k for k in asdict(rows[0]) if k != "header"] + [f"hdr_{k}" for k in HDR_KEYS] if rows else []
    data = []
    for r in rows:
        d = asdict(r)
        h = d.pop("header")
        data.append([d[k] for k in cols if not k.startswith("hdr_")] + [h.get(k) for k in HDR_KEYS])
    return {"columns": cols, "rows": data}
