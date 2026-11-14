"""Python boundary types (workflow.md §7.1). The code is the specification; changes are versioned in
CONTRACTS.md and land with their consumers.

Surfaces and owners (workflow.md §2.4):
  D -> I : FrameRef, RawFrame, Calib            (raw frames and calibration -> pixel pipeline)
  I -> M : CalFrame, Grid, Cube, PSFModel        (pixel pipeline -> measurements; PSFModel is M -> I)
  I -> P : Stack, Cube, Diff, TimeBin            (science -> API)
Arrays are numpy; image arrays are (ny, nx) with row 0 = south edge on a north-up Grid and the frame's
own pixel (0, 0) on native frames. Units: surface brightness MJy/sr, variance (MJy/sr)^2, lambda um.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

import numpy as np
from astropy.io.fits import Header
from astropy.wcs import WCS
from numpy.typing import NDArray

CONTRACT_VERSION = "0.1.0"

F64 = NDArray[np.float64]
I64 = NDArray[np.int64]
B = NDArray[np.bool_]
Status = Literal["full", "partial", "bin", "survey", "exposure"]


@dataclass(frozen=True)
class FrameRef:
    """One (exposure, detector) file as listed by coverage after dedup (D)."""
    access_url: str
    s3_key: str
    collection: str
    obs_id: str
    detector: int
    t_min: float                      # MJD

    @property
    def id(self) -> str:
        return self.s3_key.rsplit("/", 1)[-1]


@dataclass
class RawFrame:
    """What a FrameSource returns (implementation.md §3.4). `hdus` holds at least IMAGE, FLAGS,
    VARIANCE and ZODI as (header, data). `origin` is the 0-based parent-detector pixel of the frame's
    pixel (0, 0), supplied by the FrameSource (cutout: from CRPIXnA; S3 section: known directly)."""
    hdus: Mapping[str, tuple[Header, NDArray[Any]]]
    wcs: WCS
    origin: tuple[int, int]
    ref: FrameRef | None = None
    release: str = "qr3"              # release id from config/releases.yaml


class Calib(Protocol):
    """Per-detector parent-pixel maps (D, implementation.md §3.5), all in DETCOORD='sky' orientation.
    channel: the single CHANNEL_MAP (HDU 1 of spectral_channels, DETECTOR='ALL'; F3)."""
    cwave: Mapping[int, NDArray[Any]]
    cband: Mapping[int, NDArray[Any]]
    fluxcorr: Mapping[int, NDArray[Any]]
    channel: NDArray[Any]


@dataclass
class CalFrame:
    """A calibrated native frame (I -> M). `sci` has zodi and local background removed and NaN where
    `bad` (the requested mask preset). `bad_phot` is the photometry preset (implementation.md §4.3).
    Photometry must not mix `photometric_scale` values until F4 is resolved (workflow.md §11.2)."""
    sci: F64
    var: F64
    bad: B
    bad_phot: B
    lam: F64                          # CWAVE at each pixel (um)
    dlam: F64                         # CBAND at each pixel (um)
    flags: I64
    bits: dict[str, int]
    sky: B
    w_frame: float
    wcs: WCS
    origin: tuple[int, int]
    detector: int
    mjd: float                        # MJD-AVG
    obsid: str
    survey: int | None                # None = IOC (commissioning)
    header: Header
    qa: dict[str, Any]
    photometric_scale: str            # "qr3" or "qr2" (uncorrected)
    preset: str
    ref: FrameRef | None = None

    def flags_near(self, x: float, y: float, r: float = 2.5) -> list[str]:
        """Names of flag planes set within r pixels of (x, y), frame pixel coordinates."""
        yy, xx = np.indices(self.flags.shape)
        near = np.hypot(xx - x, yy - y) <= r
        acc = int(np.bitwise_or.reduce(self.flags[near])) if near.any() else 0
        return sorted(n for n, v in self.bits.items() if acc & v)


@dataclass(frozen=True)
class Grid:
    """Common north-up, east-left TAN grid. pix_arcsec < native means upsampled: display only,
    never for measurement or detection (implementation.md §4.4)."""
    wcs: WCS
    shape: tuple[int, int]
    pix_arcsec: float
    ra: float
    dec: float

    @property
    def native(self) -> bool:
        return self.pix_arcsec >= 6.15 * 0.999


@dataclass
class GridFrame:
    """One CalFrame reprojected to a Grid (sci bilinear; var, lam, flags nearest-neighbour)."""
    sci: F64
    var: F64
    lam: F64
    flags: NDArray[np.uint32]         # canonical bit layout (flags.CANONICAL_BITS)
    w_frame: float
    mjd: float
    detector: int
    survey: int | None
    frame_id: str
    psf_fwhm_arcsec: float = float("nan")   # PSF_FWHM header of the frame
    photometric_scale: str = "qr3"           # from CalFrame; differences refuse mixed scales (F4)


@dataclass
class TimeBin:
    """One entry of the time axis for one band (implementation.md §4.2)."""
    id: str                           # V1, V2… (same dates in every band), B0…, S1…, E0…
    band: int
    idx: NDArray[np.int64]            # indices into the frame list given to epochs.time_bins
    status: Status
    mjd_mean: float
    mjd_min: float
    mjd_max: float
    surveys: tuple[int | None, ...]
    label: str
    n_visit_frames: int = 0           # frames of this visit in all bands (label of full visits)


@dataclass
class Stack:
    """A (time-bin, band) stack (I -> P manifest/payloads, I -> M). `mean` is the measurement array;
    `display` (if set) may carry model-filled cores, marked by `filled`, and must never be measured."""
    bin: TimeBin
    grid: Grid
    mean: F64
    var: F64
    nhits: I64
    flag_or: NDArray[np.uint32]
    rej: B                            # (n, ny, nx) rejected transients, frame order = frame_ids
    frame_ids: list[str]
    skipped: list[tuple[str, str]]    # (frame id, reason): never dropped silently
    display: F64 | None = None
    filled: B | None = None
    transients: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class Cube:
    """Per-pixel spectral cube of one (time-bin, band) (implementation.md §4.6). `lam` is the mean
    wavelength each bin actually sampled at each pixel; `nhits` the samples per bin (F16)."""
    bin: TimeBin
    band: int
    grid: Grid
    cube: F64                         # (nb, ny, nx)
    var: F64
    lam: F64
    nhits: I64
    photometric_scales: tuple[str, ...] = ("qr3",)


@dataclass
class Diff:
    """lambda-matched difference A - B with its renormalised significance (I -> P)."""
    a: str
    b: str
    band: int
    d: F64
    var: F64
    sig: F64
    k: float                          # significance renormalisation factor (QA)
    annotations: list[dict[str, Any]] = field(default_factory=list)
    photometric_match: dict[str, Any] | None = None   # cube.fit_relative_scale report (decision 0008)


class PSFModel(Protocol):
    """M -> I: a fitted PSF model rendered on a Grid, used only for the bright-target display fill
    (P1-7). M's ePSF wing fit implements it; tests use a Gaussian stand-in."""
    def render(self, grid: Grid) -> F64: ...
