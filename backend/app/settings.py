"""Deployment settings and config-file schemas (workflow.md §7.1 "Config files", §8.5, §9.6; implementation.md §9).

Configuration arrives from environment variables here and is passed into `spherex/` as arguments: science
and data modules never read settings themselves (workflow.md §3, enforced by import-linter).

Environment variables (all optional):
  ENVIRONMENT   local | staging | production | snapshot | mock      (default local; MOCK=1 forces mock)
  MOCK=1        serve golden payloads from frontend/fixtures (workflow.md §8.5); never used in a demo
  FRAMESOURCE   auto | s3 | irsa | fixture                           (default auto)
  IN_AWS_US_EAST_1=1   the API runs next to the bucket (S3 sections preferred)
  FIXTURE_ROOT  directory for FRAMESOURCE=fixture (default the committed F2 fixtures)
  OFFLINE=1     no network at all: serve the snapshot only (demo laptop)
  SNAPSHOT_DIR  pre-warmed views (implementation.md §9 snapshot mode)
  CACHE_DIR     disk cache root (frames, coverage, views, candidates, release state)
  CALIB_ROOT    bootstrapped calibration files (scripts/bootstrap_calib.py fetch). Unset: $PARALLAX_CALIB or
                ~/.cache/parallax/calib when every locked file is there; empty (CALIB_ROOT=): none
  CPU_WORKERS   process-pool size for numpy/astropy work (0 = threads; default 0 on Windows, else cpu − 1, at most 8)
  JOB_TIMEOUT_S, MAX_FOV_ARCMIN, MAX_FRAMES_PER_VIEW, JOBS_PER_MINUTE_PER_IP, CANDIDATES_PER_HOUR_PER_IP,
  LOOKUPS_PER_MINUTE_PER_IP, MEASUREMENTS_PER_MINUTE_PER_IP
  FEATURES_PATH config/features.yaml;  STATUS from validation/ (workflow.md §4.3)
  PUBLIC_GALLERY=1    show the candidate gallery (moderation flag, implementation.md §8; default off)
  CACHE_MAX_GB  disk budget for frames + views; least recently used deleted past it (0 = unlimited, the default)
"""
from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator

REPO = Path(__file__).resolve().parents[2]
BACKEND = REPO / "backend"

Environment = Literal["local", "staging", "production", "snapshot", "mock"]
FlagLevel = Literal["off", "dev", "staging", "on"]
API_VERSION = "0.1.0"          # HTTP schema version; equals frontend/src/api/types.ts API_SCHEMA_VERSION


def _flag(name: str, default: bool = False) -> bool:
    v = os.environ.get(name)
    return default if v is None else v.strip().lower() in ("1", "true", "yes", "on")


def _int(name: str, default: int) -> int:
    v = os.environ.get(name)
    return default if v in (None, "") else int(v)


def _float(name: str, default: float) -> float:
    v = os.environ.get(name)
    return default if v in (None, "") else float(v)


def _path(name: str, default: Path | None) -> Path | None:
    v = os.environ.get(name)
    return Path(v) if v else default


def _default_calib_root() -> Path | None:
    """Where `scripts/bootstrap_calib.py fetch` puts the files ($PARALLAX_CALIB, else ~/.cache/parallax/calib), when
    every locked file is there. Without this a laptop that has bootstrapped still served "calibration missing" unless
    CALIB_ROOT was exported, and spectra, astrometry, light curves and differences all refused (409). Presence only:
    Services.start() verifies sha256 against the lock and refuses to start on a mismatch."""
    root = Path(os.environ.get("PARALLAX_CALIB") or Path.home() / ".cache" / "parallax" / "calib")
    try:
        lock = json.loads((REPO / "config" / "calibration.lock").read_text(encoding="utf-8"))
        keys = [f["s3_key"] for f in lock["files"]]
    except Exception:
        return None
    return root if keys and all((root / k).is_file() for k in keys) else None


@dataclass
class Settings:
    environment: Environment = "local"
    mock: bool = False
    framesource: str = "auto"
    in_aws_us_east_1: bool = False
    fixture_root: Path = BACKEND / "tests" / "data" / "real" / "f2"
    offline: bool = False
    snapshot_dir: Path | None = None
    cache_dir: Path = REPO / ".cache" / "parallax"
    calib_root: Path | None = None
    cpu_workers: int = 0
    job_timeout_s: float = 300.0                 # implementation.md §9: jobs time out after 5 min
    max_fov_arcmin: float = 30.0                 # implementation.md §9 allows ≤ 60′ binned; 30′ until measured (B-06)
    max_frames_per_view: int = 600               # implementation.md §9: ≤ 600 frames, decimated (listed)
    jobs_per_minute_per_ip: int = 6
    lookups_per_minute_per_ip: int = 60           # resolve, coverage, overlays, ephemerides, view planning (K-03)
    measurements_per_minute_per_ip: int = 20      # spectra, astrometry, light curves, movers, diff/cube/RGB, exports
    candidates_per_hour_per_ip: int = 10
    features_path: Path = REPO / "config" / "features.yaml"
    releases_path: Path = REPO / "config" / "releases.yaml"
    pins_dir: Path = REPO / "config" / "pins"
    validation_dir: Path = REPO / "validation"
    public_gallery: bool = False
    cache_max_gb: float = 0.0                    # 0 = no budget; on a public host set it (app/cachegc.py, O-13)
    watcher_interval_s: float = 3600.0           # implementation.md §3.6: hourly
    run_watcher: bool = False
    git_sha: str = field(default_factory=lambda: os.environ.get("GIT_SHA", "unknown"))

    @classmethod
    def from_env(cls) -> Settings:
        mock = _flag("MOCK")
        env = os.environ.get("ENVIRONMENT", "mock" if mock else "local")
        if mock:
            env = "mock"
        if env not in ("local", "staging", "production", "snapshot", "mock"):
            raise ValueError(f"ENVIRONMENT must be local|staging|production|snapshot|mock, not {env!r}")
        offline = _flag("OFFLINE")
        snap = _path("SNAPSHOT_DIR", None)
        if offline and snap is None:
            raise ValueError("OFFLINE=1 needs SNAPSHOT_DIR (implementation.md §9)")
        framesource = os.environ.get("FRAMESOURCE", "auto")
        # Unset → the bootstrapped default if complete; set but empty (CALIB_ROOT=) → explicitly no calibration.
        # Mock and fixture modes keep their own calibration (none / committed slices).
        calib_root = _path("CALIB_ROOT", None)
        if "CALIB_ROOT" not in os.environ and not mock and framesource != "fixture":
            calib_root = _default_calib_root()
        s = cls(environment=env, mock=mock,                                 # type: ignore[arg-type]
                framesource=framesource,
                in_aws_us_east_1=_flag("IN_AWS_US_EAST_1"),
                fixture_root=_path("FIXTURE_ROOT", cls.fixture_root) or cls.fixture_root,
                offline=offline, snapshot_dir=snap,
                cache_dir=_path("CACHE_DIR", cls.cache_dir) or cls.cache_dir,
                calib_root=calib_root,
                cpu_workers=_int("CPU_WORKERS", 0 if sys.platform == "win32" else max(1, min(8, (os.cpu_count() or 3) - 1))),
                job_timeout_s=_float("JOB_TIMEOUT_S", 300.0),
                max_fov_arcmin=_float("MAX_FOV_ARCMIN", 30.0),
                max_frames_per_view=_int("MAX_FRAMES_PER_VIEW", 600),
                jobs_per_minute_per_ip=_int("JOBS_PER_MINUTE_PER_IP", 6),
                lookups_per_minute_per_ip=_int("LOOKUPS_PER_MINUTE_PER_IP", 60),
                measurements_per_minute_per_ip=_int("MEASUREMENTS_PER_MINUTE_PER_IP", 20),
                candidates_per_hour_per_ip=_int("CANDIDATES_PER_HOUR_PER_IP", 10),
                features_path=_path("FEATURES_PATH", cls.features_path) or cls.features_path,
                public_gallery=_flag("PUBLIC_GALLERY"),
                cache_max_gb=_float("CACHE_MAX_GB", 0.0),
                run_watcher=_flag("RUN_WATCHER", env in ("staging", "production")))
        if s.framesource not in ("auto", "s3", "irsa", "fixture"):
            raise ValueError(f"FRAMESOURCE must be auto|s3|irsa|fixture, not {s.framesource!r}")
        return s

    @property
    def network(self) -> bool:
        """May this process talk to IRSA, S3 or catalogue services?"""
        return not (self.offline or self.mock or self.framesource == "fixture")


# --------------------------------------------------------------------------------------------- features.yaml

class FlagSpec(BaseModel):
    """One capability flag (workflow.md §9.6). `level` is the most public environment it may appear in:
    off (nowhere) · dev (developer machines) · staging (dev + staging, "unvalidated" badge) · on (release)."""
    model_config = ConfigDict(extra="forbid")
    level: FlagLevel
    requires: list[str] = Field(default_factory=list)
    capability: str
    note: str = ""
    core: bool = False                 # P0 product: always shown by the UI; the API still gates it by level

    @field_validator("requires")
    @classmethod
    def _ids(cls, v: list[str]) -> list[str]:
        for x in v:
            if not (x.startswith("F") or x.startswith("G")):
                raise ValueError(f"requirement {x!r} is neither a foundation check (F…) nor a gate (G…)")
        return v


class FeaturesConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_: str = Field(alias="schema")
    flags: dict[str, FlagSpec]

    @field_validator("schema_")
    @classmethod
    def _schema(cls, v: str) -> str:
        if v != "parallax-features@1":
            raise ValueError(f"features.yaml schema must be parallax-features@1, not {v!r}")
        return v


def load_features(path: Path) -> FeaturesConfig:
    return FeaturesConfig.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))


# Release decision (2026-11-15): "staging" capabilities ship in production and snapshot builds too; "dev" stays local.
_VISIBLE = {"local": ("dev", "staging", "on"), "mock": ("dev", "staging", "on"),
            "staging": ("staging", "on"), "production": ("staging", "on"), "snapshot": ("staging", "on")}


def effective_level(spec: FlagSpec, environment: str) -> FlagLevel:
    """The level served in /releases: the flag's level where this environment may show it, else "off"."""
    return spec.level if spec.level in _VISIBLE.get(environment, ()) else "off"


def effective_features(cfg: FeaturesConfig, environment: str) -> dict[str, FlagLevel]:
    return {name: effective_level(spec, environment) for name, spec in sorted(cfg.flags.items())}
