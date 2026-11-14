"""Build the FrameSource a deployment asks for (implementation.md §3.4 "Which source by default?"; workflow.md
§8.5 FRAMESOURCE=fixture). Configuration arrives as arguments; P's settings map env vars onto them.

  kind="auto"     in AWS us-east-1: S3 sections preferred, IRSA cutouts as failover; elsewhere both at once
                  (PooledSource: IRSA cutouts and S3 sections share the queue; decision record 0009)
  kind="s3" | "irsa"   that source, with the other as failover (failover=False: alone)
  kind="fixture"  committed real fixtures only, no network
Every network source sits behind the shared per-host limiter and, if cache_root is set, the frame cache."""
from __future__ import annotations

import logging
from pathlib import Path

import httpx

from .cache import FrameCache
from .failover import CachedSource, FailoverSource, PooledSource
from .fitsstream import IrsaCutoutSource
from .fixture import FixtureSource
from .frames import FrameSource
from .http import HostLimiter
from .releases import Registry
from .s3sections import S3SectionSource

KINDS = ("auto", "s3", "irsa", "fixture")
POOL_IRSA_FRAMES = 4
POOL_S3_FRAMES = 12
log = logging.getLogger("parallax.access")


def build_source(kind: str, client: httpx.AsyncClient | None = None, registry: Registry | None = None,
                 in_aws_us_east_1: bool = False, failover: bool = True, fixture_root: Path | str | None = None,
                 cache_root: Path | str | None = None, limiter: HostLimiter | None = None) -> FrameSource:
    if kind not in KINDS:
        raise ValueError(f"FRAMESOURCE must be one of {KINDS}, not {kind!r}")
    if kind == "fixture":
        if fixture_root is None:
            raise ValueError("FRAMESOURCE=fixture needs fixture_root")
        return FixtureSource(fixture_root)
    if client is None:
        raise ValueError(f"FRAMESOURCE={kind} needs an HTTP client")
    lim = limiter or HostLimiter()
    s3 = S3SectionSource(client, limiter=lim, registry=registry)
    irsa = IrsaCutoutSource(client, limiter=lim, registry=registry)
    first: FrameSource
    second: FrameSource
    src: FrameSource
    if kind == "auto" and not in_aws_us_east_1 and failover:
        # IRSA: ≤ 4 in flight (its limit, http.DEFAULT_LIMITS); S3: a frame is ≈ 9 range requests, so 12 frames
        # keep the 32 S3 slots busy. Priors are seconds per frame from a home link; the EWMA corrects them.
        src = PooledSource([irsa, s3], capacity=[POOL_IRSA_FRAMES, POOL_S3_FRAMES], prior_s=[4.0, 8.0])
        return CachedSource(src, FrameCache(cache_root)) if cache_root is not None else src
    if kind == "s3" and not in_aws_us_east_1:
        log.warning("FRAMESOURCE=s3 outside AWS us-east-1: S3 sections read whole detector rows (about 16x the "
                    "bytes of a cutout for a 6' view), so cold views are slow on a home link. FRAMESOURCE=auto "
                    "uses IRSA cutouts and S3 sections together (decision record 0009).")
    if kind == "auto":
        first, second = (s3, irsa) if in_aws_us_east_1 else (irsa, s3)
    else:
        first, second = (s3, irsa) if kind == "s3" else (irsa, s3)
    src = FailoverSource(first, second) if failover else first
    return CachedSource(src, FrameCache(cache_root)) if cache_root is not None else src
