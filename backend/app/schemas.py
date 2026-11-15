"""HTTP API schemas (workflow.md §7.1): `app/schemas.py` → `/openapi.json` → generated
`frontend/src/api/generated.ts` (scripts/gen_ts_types.py). Names follow F's provisional
`frontend/src/api/types.ts` 0.1.0 (CONTRACTS.md "HTTP API"), which P approves with the amendments recorded
there. Every response model is validated against /openapi.json in CI (tests/contract).

Rules: binary payloads are not modelled here (implementation.md §5.2, `format` ids in render.py); errors are
FastAPI's `{detail: string}`; additive changes only from RC1 (workflow.md §7.2)."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from .settings import API_VERSION

BinStatus = Literal["full", "partial", "bin", "survey", "exposure"]
TargetKind = Literal["star", "sso", "coords"]
FlagLevel = Literal["off", "dev", "staging", "on"]
Validity = Literal["accepted", "unvalidated"]


class _M(BaseModel):
    model_config = ConfigDict(extra="forbid")


# ------------------------------------------------------------------------------------------- /resolve


class EpochHint(_M):
    object: str
    epoch: float
    sep_arcsec: float
    now_ra: float
    now_dec: float
    moved_arcmin: float
    direction: str


class PropagatedNow(_M):
    ra: float
    dec: float
    epoch: float


class ResolveResult(_M):
    query: str
    kind: TargetKind
    name: str
    main_id: str | None = None
    ra: float
    dec: float
    epoch: float
    pm: tuple[float, float] | None = None
    plx: float | None = None
    rv: float | None = None
    otype: str | None = None
    spt: str | None = None
    astrometry_source: str | None = None
    propagated_now: PropagatedNow
    epoch_hint: EpochHint | None = None
    label_hint: str | None = None


# ------------------------------------------------------------------------------------------ /releases


class ReleaseState(_M):
    release_state: dict[str, str]
    newest_period: str
    checked_at: str


class ReleasesResponse(ReleaseState):
    features: dict[str, FlagLevel]
    environment: Literal["local", "staging", "production", "snapshot", "mock"]
    snapshot: bool
    api_version: str = API_VERSION


# ------------------------------------------------------------------------------------------ /coverage


class CoverageVisit(_M):
    id: str
    status: BinStatus
    mjd_min: float
    mjd_max: float
    surveys: list[int | None]
    frames_per_band: dict[str, int]
    releases: list[str]


class Coverage(_M):
    ra: float
    dec: float
    fov: float
    n_frames: int
    axis: str
    visits: list[CoverageVisit]
    releases: list[str]
    freshness: ReleaseState


# --------------------------------------------------------------------------------------------- /views


class TimeBinInfo(_M):
    id: str
    band: int
    status: BinStatus
    mjd_mean: float
    mjd_min: float
    mjd_max: float
    surveys: list[int | None]
    label: str
    n_frames: int
    n_visit_frames: int


class Transient(_M):
    """A per-exposure transient on empty sky (implementation.md §4.5: asteroid candidate before vetting, P2-5).
    Grid pixel position (0-based) and sky position; `frame` is the exposure it appeared in."""
    frame: str
    x: float
    y: float
    ra: float
    dec: float
    npix: int


class StackInfo(_M):
    bin: str
    band: int
    ready: bool
    format: str
    nhits_max: int
    filled: bool
    skipped: list[tuple[str, str]]
    frame_ids: list[str]
    transients: list[Transient] = []


class FrameMeta(_M):
    id: str
    band: int
    detector: int
    bin: str
    mjd: float
    survey: int | None
    obsid: str
    release: str
    collection: str
    pipeline: str
    qa: dict[str, str | float | int | bool | None]
    skipped: str | None


class GridInfo(_M):
    ctype: tuple[str, str]
    crval: tuple[float, float]
    crpix: tuple[float, float]
    cdelt: tuple[float, float]
    shape: tuple[int, int]
    pix_arcsec: float
    native: bool


class TrackPoint(_M):
    bin: str
    band: int
    mjd: float
    ra: float
    dec: float


class ViewWarning(_M):
    code: str
    message: str
    severity: Literal["info", "warn"]


class Limits(_M):
    lo: float
    hi: float
    lim: str


class FlagsInfo(_M):
    bits: dict[str, int]
    info: dict[str, str]
    format: str


class Formats(_M):
    stack: str
    science: str
    flags: str


class ViewManifest(_M):
    schema_version: str = API_VERSION
    key: str
    pin: str
    newer_pin: str | None = None
    params: dict[str, str]
    target: ResolveResult | None
    grid: GridInfo
    axis: str
    bands: list[int]
    bins: dict[str, list[TimeBinInfo]]
    stacks: list[StackInfo]
    limits: dict[str, Limits]
    frames: list[FrameMeta]
    track: list[TrackPoint]
    flags: FlagsInfo
    formats: Formats
    release: ReleaseState
    warnings: list[ViewWarning]
    data_source: Literal["live", "snapshot", "mock"]


class ViewReady(_M):
    status: Literal["ready"]
    manifest: ViewManifest


class ViewQueued(_M):
    status: Literal["queued"]
    job_id: str
    key: str


# ------------------------------------------------------------------------------------------ SSE events
# Event name = `type`; data = JSON of the other fields (CONTRACTS.md). Modelled for /openapi.json only.


class EvPlanned(_M):
    type: Literal["planned"] = "planned"
    n: int


class EvFetched(_M):
    type: Literal["fetched"] = "fetched"
    i: int
    n: int


class EvStackReady(_M):
    type: Literal["stack_ready"] = "stack_ready"
    bin: str
    band: int


class EvDiffReady(_M):
    type: Literal["diff_ready"] = "diff_ready"
    a: str
    b: str
    band: int


class EvWarning(_M):
    type: Literal["warning"] = "warning"
    code: str
    message: str


class EvDone(_M):
    type: Literal["done"] = "done"
    key: str


class EvError(_M):
    type: Literal["error"] = "error"
    message: str


JobEvent = EvPlanned | EvFetched | EvStackReady | EvDiffReady | EvWarning | EvDone | EvError


class JobEventDoc(BaseModel):
    """Documents the SSE event payloads in /openapi.json (each SSE `data:` is one of these minus `type`)."""

    event: JobEvent


# ---------------------------------------------------------------------------------------------- /diff


class DiffAnnotation(_M):
    kind: Literal["dipole", "monopole"]
    ra: float
    dec: float
    to_ra: float | None = None
    to_dec: float | None = None
    shift_px: float | None = None
    shift_arcsec: float | None = None
    pa_deg: float | None = None
    sign: Literal["brightened", "faded"] | None = None
    agrees_with_track: bool | None = None
    label: str


class PhotometricMatchBin(_M):
    """One λ bin of the in-situ photometric match (spherex.cube.fit_relative_scale): B·scale + offset ≈ A."""
    lam: float | None = None
    scale: float
    err: float
    raw: float | None = None          # this bin's own fit, before shrinkage toward the broadband scale
    raw_err: float | None = None
    shrink: float                     # empirical-Bayes weight on the broadband scale (1 = fully pooled)
    offset: float
    n_pix: int
    n_sources: int
    pooled: bool                      # too little data in this bin: broadband scale used


class PhotometricMatch(_M):
    """How visit B was put on visit A's photometric scale (decision record 0008, workflow.md §11.2).
    applied=False on a same-release pair: the numbers are a calibration diagnostic only. cross_release=True:
    positions and motions are valid, brightness changes are not interpreted until F4 is resolved."""
    applied: bool
    cross_release: bool
    scales_a: list[str]
    scales_b: list[str]
    method: str
    note: str
    scale: float | None = None
    scale_err: float | None = None
    offset: float | None = None
    offset_err: float | None = None
    n_sources: int | None = None
    n_pix: int | None = None
    residual_scale: float | None = None
    tau: float | None = None          # between-bin scatter of the scale beyond noise (chromatic gain)
    q_flat: float | None = None       # Cochran Q of the per-bin scales about a flat gain
    dof_flat: int | None = None
    static_z_before: float | None = None   # median |static-source residual| (σ) without / with the match
    static_z_after: float | None = None
    bins: list[PhotometricMatchBin] = []


class DiffInfo(_M):
    a: str
    b: str
    band: int
    format: str
    k: float
    clip_sigma: float
    annotations: list[DiffAnnotation]
    validity: Validity
    url: str
    photometric_match: PhotometricMatch | None = None


# ------------------------------------------------------------------------- science routes (M → P)


class SpectrumRow(_M):
    lam: float
    dlam: float
    flux: float
    err: float
    mjd: float
    visit: str
    detector: int
    flags: list[str]
    rchi2: float
    contaminated: bool
    release: str
    quality: dict[str, Any] | None = None
    frame_id: str | None = None


class SpectrumIndices(_M):
    methane_rel: float | None = None
    w1w2_syn: float | None = None


class SpectrumResponse(_M):
    ra: float
    dec: float
    rows: list[SpectrumRow]
    templates: list[dict[str, Any]] = Field(default_factory=list)
    indices: SpectrumIndices | None = None
    validity: Validity
    notes: list[str]
    skipped: list[list[str]] = Field(default_factory=list)
    photometric_scales: list[str] = Field(default_factory=list)
    pin: str | None = None
    indices_by_visit: dict[str, dict[str, Any]] = Field(default_factory=dict)
    native_frames: list[str] = Field(default_factory=list)


class AstroPoint(_M):
    visit: str
    mjd: float
    xi: float
    eta: float
    s_xi: float
    s_eta: float
    band: int
    frame_id: str | None = None
    native_xy: list[float] | None = None
    flux_snr: float | None = None
    rchi2: float | None = None
    cov_xi_eta: float = 0
    fit_included: bool = True
    excluded: str | None = Field(None, description="Why a measured point is left out of the motion fit")
    method: str = "native-frame"


class AstroFit(_M):
    pmra: float
    pmdec: float
    e_pmra: float
    e_pmdec: float
    mu: float
    e_mu: float
    pa_deg: float
    plx_fixed: float | None = Field(
        description="Fixed catalogue parallax in milliarcseconds; internal motion fitting uses arcseconds"
    )
    chi2: float
    dof: int
    delta_chi2: float
    visit_floor_arcsec: float = Field(0.0, description="Visit-shared positional error added per axis (arcsec)")
    n_visits: int | None = Field(None, description="Independent visits in the fit (frames within a visit correlate)")


class AstroCatalogue(_M):
    source: str
    mu: float
    pa_deg: float
    pmra: float
    pmdec: float


class AstrometryResponse(_M):
    name: str
    points: list[AstroPoint]
    fit: AstroFit | None
    catalogue: AstroCatalogue | None
    validity: Validity
    skipped: list[list[str]] = Field(default_factory=list)
    registration: list[dict[str, Any]] = Field(default_factory=list)
    joint_fits: list[dict[str, Any]] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    tangent_origin: list[float] | None = None
    pin: str | None = None
    native_frames: list[str] = Field(default_factory=list)


class LCPoint(_M):
    mjd: float
    rel: float
    err: float
    bin: str


class Periodogram(_M):
    period_days: list[float]
    power: list[float]
    best_days: float
    fap: float | None
    fap_trials: int | None = None
    fap_exceedances: int | None = None
    fap_seed: int | None = None
    fap_resolution: float | None = None
    covariance_rank: int | None = None
    method: str = ""


class LightCurveResponse(_M):
    bands: dict[str, list[LCPoint]]
    covariance: list[list[float]] = Field(default_factory=list)
    covariance_order: list[list[str]] = Field(default_factory=list)
    reference_spectrum: list[dict[str, Any]] = Field(default_factory=list)
    uncertainty: str = ""
    periodogram: Periodogram | None = None
    method: Literal["psf", "annulus"]
    label: str
    validity: Validity
    photometric_scales: list[str] = Field(default_factory=list)
    pin: str | None = None
    native_frames: list[str] = Field(default_factory=list)
    skipped: list[list[str]] = Field(default_factory=list)


class OverlaySource(_M):
    id: str
    ra: float
    dec: float
    label: str | None = None
    mag: float | None = None


class OverlayResponse(_M):
    catalogue: Literal["gaia", "catwise", "allwise", "simbad", "sso"]
    mjd: float
    sources: list[OverlaySource]
    # Set when the positions are NOT at `mjd` but as catalogued at this epoch (decimal year): the AllWISE layer.
    epoch: float | None = None
    skipped: list[list[str]] = Field(default_factory=list)


class SsoPoint(_M):
    mjd: float
    ra: float
    dec: float


class SsoResponse(_M):
    name: str
    observer: str
    points: list[SsoPoint]


class MoverCandidate(_M):
    id: str
    ra: float
    dec: float
    pm_arcsec_yr: float | None = None
    pa_deg: float | None = None
    visits: list[str]
    known: str | None = None
    score: float | None = None
    distance_au: float | None = None
    distance_error_au: float | None = None
    why: list[str] = Field(default_factory=list)


class MoversResponse(_M):
    key: str
    candidates: list[MoverCandidate]
    orphans: list[dict[str, Any]] = Field(default_factory=list)
    validity: Validity
    skipped: list[list[str]] = Field(default_factory=list)
    tracked: list[dict[str, Any]] = Field(default_factory=list)   # Planet X digital tracking (shift-and-stack)


class FlipFrame(_M):
    id: str
    mjd: float
    lam_um: float | None
    url: str


class FramesResponse(_M):
    key: str
    band: int
    sort: Literal["time", "lambda"]
    label: str
    format: str
    frames: list[FlipFrame]


# ------------------------------------------------------------------------------- /views/{key}/blink25


class Blink25Epoch(_M):
    label: str
    year: float
    date: str
    pairs_with_band: int | None
    n_images: int
    ra: float
    dec: float
    url: str | None
    note: str | None = None


class Blink25Response(_M):
    key: str
    label: str
    format: str
    grid: GridInfo
    view_fov_arcmin: float
    fov_needed_arcmin: float
    view_fov_for_full_coverage_arcmin: float
    expected_jumps_arcmin: dict[str, float]
    twomass_match: str | None
    pos_source: str
    epochs: list[Blink25Epoch]


# ----------------------------------------------------------------------------------------- /candidates

CandidateKind = Literal["mover", "variable", "transient", "artifact", "other"]


class CandidateRequest(_M):
    ra: float = Field(ge=0.0, lt=360.0)
    dec: float = Field(ge=-90.0, le=90.0)
    view_key: str = Field(min_length=8, max_length=64, pattern=r"^[0-9a-f]+$")
    pin: str = Field(default="", pattern=r"^([0-9a-f]{12})?$")
    visits: list[str] = Field(default_factory=list, max_length=64)
    kind: CandidateKind
    note: str = Field(default="", max_length=1000)


class AutoCheck(_M):
    name: str
    passed: bool | None
    detail: str


class CandidateResponse(_M):
    id: str
    auto_checks: list[AutoCheck]


class CandidateRecord(_M):
    id: str
    created_at: str
    ra: float
    dec: float
    view_key: str
    pin: str
    visits: list[str]
    kind: CandidateKind
    note: str
    auto_checks: list[AutoCheck]
    votes: int
    status: str


class CandidateGallery(_M):
    banner: str
    candidates: list[CandidateRecord]


# --------------------------------------------------------------------------------------------- health


class HealthProbe(_M):
    name: str
    ok: bool
    seconds: float | None = None
    detail: str = ""


class Health(_M):
    ok: bool
    mode: Literal["live", "snapshot", "mock", "fixture"]
    environment: str
    api_version: str = API_VERSION
    git_sha: str
    calibration: str
    probes: list[HealthProbe]
