"""Record and replay HTTP exchanges (owner D), so offline tests and FRAMESOURCE=fixture runs exercise the
real client code on genuine archive responses with no network (workflow.md §8.2, §8.5).

A recording directory holds `index.json` (canonical request → file, status, headers, retrieval time)
and one gzip file per response body. Replay matches on the canonical request (method, URL with sorted
query, sorted form body, Range header); an unrecorded request fails loudly instead of inventing data."""
from __future__ import annotations

import datetime
import gzip
import hashlib
import json
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import httpx

KEEP_HEADERS = ("content-type", "content-range", "content-length", "etag")


def canonical(req: httpx.Request, body: bytes | None = None) -> str:
    u = urlsplit(str(req.url))
    q = urlencode(sorted(parse_qsl(u.query, keep_blank_values=True)))
    key = f"{req.method} {urlunsplit((u.scheme, u.netloc, u.path, q, ''))}"
    b = body if body is not None else (req.content or b"")
    if b:
        try:
            key += " BODY " + urlencode(sorted(parse_qsl(b.decode(), keep_blank_values=True)))
        except UnicodeDecodeError:
            key += " BODY sha256:" + hashlib.sha256(b).hexdigest()
    if "range" in req.headers:
        key += " RANGE " + req.headers["range"]
    return key


class RecordingTransport(httpx.AsyncBaseTransport):
    def __init__(self, root: Path | str, inner: httpx.AsyncBaseTransport | None = None) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.inner = inner or httpx.AsyncHTTPTransport(retries=0)
        self.idx_path = self.root / "index.json"
        self.index = json.loads(self.idx_path.read_text()) if self.idx_path.exists() else {}

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        body = await request.aread()
        request.headers["Accept-Encoding"] = "identity"       # record bodies exactly as decoded bytes
        resp = await self.inner.handle_async_request(request)
        content = await resp.aread()
        if resp.headers.get("content-encoding", "identity") not in ("identity", ""):
            raise RuntimeError(f"server ignored Accept-Encoding: identity for {request.url}")
        key = canonical(request, body)
        fname = hashlib.sha256(key.encode()).hexdigest()[:24] + ".gz"
        (self.root / fname).write_bytes(gzip.compress(content, 9, mtime=0))
        self.index[key] = dict(file=fname, status=resp.status_code, bytes=len(content),
                               sha256=hashlib.sha256(content).hexdigest(),
                               headers={k: v for k, v in resp.headers.items() if k.lower() in KEEP_HEADERS},
                               retrieved=datetime.datetime.now(datetime.UTC).isoformat(timespec="seconds"))
        self.idx_path.write_text(json.dumps(self.index, indent=1, sort_keys=True))
        return httpx.Response(resp.status_code, headers=resp.headers, content=content, request=request)

    async def aclose(self) -> None:
        await self.inner.aclose()


class ReplayTransport(httpx.AsyncBaseTransport):
    def __init__(self, root: Path | str) -> None:
        self.root = Path(root)
        self.index = json.loads((self.root / "index.json").read_text())
        self.used: set[str] = set()

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        body = await request.aread()
        key = canonical(request, body)
        if key not in self.index:
            raise LookupError(f"no recorded response for: {key}")
        e = self.index[key]
        content = gzip.decompress((self.root / e["file"]).read_bytes())
        if hashlib.sha256(content).hexdigest() != e["sha256"]:
            raise LookupError(f"recorded body for {key} fails its sha256")
        self.used.add(key)
        h = {k: v for k, v in e["headers"].items() if k.lower() != "content-length"}
        return httpx.Response(e["status"], headers=h, content=content, request=request)
