"""Which archive service failed, and how, in words a viewer can act on (instead of "GaveUp")."""
from __future__ import annotations

import httpx

from spherex.access.retry import GaveUp

SERVICE_HOSTS = (("irsa.ipac.caltech.edu", "IRSA (NASA's SPHEREx archive)"), ("simbad", "SIMBAD"),
                 ("esac.esa.int", "Gaia (ESA)"), ("ssd.jpl.nasa.gov", "JPL Horizons"), ("imcce.fr", "SkyBoT"),
                 ("amazonaws.com", "the SPHEREx bucket on AWS S3"))


def describe_upstream(e: BaseException) -> str | None:
    """'IRSA (NASA's SPHEREx archive) answered HTTP 502' from the httpx error behind `e` (GaveUp keeps the last
    one), or None when the failure carries no request to name."""
    inner: BaseException | None = e
    while isinstance(inner, GaveUp):
        inner = inner.last
    if not isinstance(inner, httpx.HTTPError):
        inner = inner.__cause__ if inner is not None and isinstance(inner.__cause__, httpx.HTTPError) else None
    if inner is None:
        return None
    try:
        host = inner.request.url.host
    except RuntimeError:                       # an httpx error raised without a request
        return None
    service = next((name for key, name in SERVICE_HOSTS if key in host), host)
    if isinstance(inner, httpx.HTTPStatusError):
        how = f"answered HTTP {inner.response.status_code}"
    elif isinstance(inner, httpx.TimeoutException):
        how = "did not answer in time"
    else:
        how = f"could not be reached ({type(inner).__name__})"
    return f"{service} {how}"
