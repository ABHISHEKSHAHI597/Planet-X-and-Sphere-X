"""Acquire only the public SPLAT catalogue tables needed to identify Y templates."""

import base64
import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import httpx

sys.stdout.reconfigure(encoding="utf-8")
root = Path(__file__).resolve().parents[2] / ".cache/m-splat"
tree = json.loads((root / "tree.json").read_text())["tree"]
names = [
    "src/splat/resources/Libraries/STANDARDS_DWARF_SPEX-PRISM.csv",
    "src/splat/db/source_data.csv",
    "src/splat/db/spectral_data.csv",
]
for name in names:
    item = next(p for p in tree if p["path"] == name)
    if item["size"] > 4_000_000:
        raise ValueError("metadata unexpectedly large")
    path = root / name.rsplit("/", 1)[-1]
    if path.exists():
        body = path.read_bytes()
    else:
        response = httpx.get(item["url"], timeout=60)
        response.raise_for_status()
        body = base64.b64decode(response.json()["content"])
    if (
        hashlib.sha1(b"blob " + str(len(body)).encode() + b"\0" + body).hexdigest()
        != item["sha"]
    ):
        raise ValueError("catalogue Git blob mismatch")
    path.write_bytes(body)
    path.with_suffix(".provenance.json").write_text(
        json.dumps(
            {
                "url": item["url"],
                "path": name,
                "git_blob": item["sha"],
                "sha256": hashlib.sha256(body).hexdigest(),
                "retrieved": datetime.now(UTC).isoformat(),
            },
            indent=2,
        )
    )
    lines = body.decode().splitlines()
    print(name, len(body), lines[0])
    print(
        chr(10).join(
            line
            for line in lines
            if any(word in line for word in ["Y0", "Y1", "1738+27"])
        )
    )
