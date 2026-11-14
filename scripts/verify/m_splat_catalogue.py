"""Discover public author-maintained SPLAT Y-dwarf assets without cloning the archive."""

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import httpx

root = Path(__file__).resolve().parents[2] / ".cache/m-splat"
root.mkdir(parents=True, exist_ok=True)
repo = httpx.get(
    "https://api.github.com/repos/aburgasser/splat", timeout=60, follow_redirects=True
)
(root / "repository-response.json").write_bytes(repo.content)
repo.raise_for_status()
branch = repo.json()["default_branch"]
url = (
    "https://api.github.com/repos/aburgasser/splat/git/trees/" + branch + "?recursive=1"
)
response = httpx.get(url, timeout=60, follow_redirects=True)
response.raise_for_status()
(root / "tree.json").write_bytes(response.content)
items = response.json()["tree"]
selected = [
    p
    for p in items
    if any(word in p["path"].lower() for word in ["y0", "y1", "1738", "1828"])
    and p["path"].lower().endswith((".fits", ".txt", ".csv"))
]
(root / "provenance.json").write_text(
    json.dumps(
        {
            "url": url,
            "retrieved": datetime.now(UTC).isoformat(),
            "sha256": hashlib.sha256(response.content).hexdigest(),
            "selected": selected,
        },
        indent=2,
    )
)
print(json.dumps(selected, indent=2))
