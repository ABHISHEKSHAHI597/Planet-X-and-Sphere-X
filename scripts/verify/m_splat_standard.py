"""Inspect one immutable author-maintained SpeX standard before grid acquisition."""

import base64
import hashlib
import json
from pathlib import Path

import httpx
from astropy.io import fits

root = Path(__file__).resolve().parents[2]
tree = json.loads((root/".cache/m-splat/tree.json").read_text())["tree"]
entry = next(p for p in tree if p["path"].endswith("/10767_10591.fits.gz"))
response = httpx.get(entry["url"],timeout=60)
response.raise_for_status()
body = base64.b64decode(response.json()["content"])
if hashlib.sha1(b"blob "+str(len(body)).encode()+b"\0"+body).hexdigest() != entry["sha"]:
    raise ValueError("standard blob mismatch")
path = root/".cache/m-splat/10767_10591.fits.gz"
path.write_bytes(body)
print(str(fits.getheader(path)))
print(fits.getdata(path).shape, fits.getdata(path)[:,:3])
