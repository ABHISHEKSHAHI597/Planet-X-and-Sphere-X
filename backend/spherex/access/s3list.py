"""Anonymous S3 ListObjectsV2 over HTTPS with pagination (implementation.md §3.6).

IRSA's browsable directories are JS-rendered; the bucket listing is the reliable index. A listing is
complete only after following every NextContinuationToken (1,000 entries per page)."""
from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass, field

import httpx

from .http import S3_HTTPS, HostLimiter
from .retry import with_retry

_NS = "{http://s3.amazonaws.com/doc/2006-03-01/}"


@dataclass
class S3Object:
    key: str
    size: int
    etag: str
    last_modified: str


@dataclass
class Listing:
    prefixes: list[str] = field(default_factory=list)
    objects: list[S3Object] = field(default_factory=list)
    pages: int = 0


def parse_page(xml: bytes) -> tuple[list[str], list[S3Object], str | None]:
    root = ET.fromstring(xml)
    if root.tag != f"{_NS}ListBucketResult":
        raise ValueError(f"not an S3 listing: {root.tag}")
    prefixes = [e.findtext(f"{_NS}Prefix") or "" for e in root.findall(f"{_NS}CommonPrefixes")]
    objs = [S3Object(e.findtext(f"{_NS}Key") or "", int(e.findtext(f"{_NS}Size") or 0),
                     (e.findtext(f"{_NS}ETag") or "").strip('"'), e.findtext(f"{_NS}LastModified") or "")
            for e in root.findall(f"{_NS}Contents")]
    truncated = (root.findtext(f"{_NS}IsTruncated") or "false") == "true"
    token = root.findtext(f"{_NS}NextContinuationToken") if truncated else None
    if truncated and not token:
        raise ValueError("truncated listing without a continuation token")
    return prefixes, objs, token


async def list_s3(client: httpx.AsyncClient, prefix: str = "", delimiter: str | None = "/",
                  limiter: HostLimiter | None = None, base: str = S3_HTTPS, max_pages: int = 10_000,
                  max_keys: int | None = None) -> Listing:
    lim = limiter or HostLimiter()
    out = Listing()
    token: str | None = None
    while True:
        params = {"list-type": "2", "prefix": prefix}
        if delimiter:
            params["delimiter"] = delimiter
        if token:
            params["continuation-token"] = token
        if max_keys:
            params["max-keys"] = str(max_keys)

        async def once(params: dict[str, str] = params) -> bytes:   # bound per page (awaited at once anyway)
            async with lim.slot(base):
                r = await client.get(base, params=params, timeout=60)
            r.raise_for_status()
            return r.content
        prefixes, objs, token = parse_page(await with_retry(once))
        out.prefixes += prefixes
        out.objects += objs
        out.pages += 1
        if token is None:
            return out
        if out.pages >= max_pages:
            raise RuntimeError("S3 listing exceeded max_pages")
