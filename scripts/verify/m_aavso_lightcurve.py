"""Attempt the public VSX metadata API; preserve exact response and provenance."""

import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
from _m_evidence import record

url = "https://vsx.aavso.org/index.php?view=api.object&ident=000-BBX-660&data=50000&fromjd=2460796&tojd=2461350&csv&band=Vis.,V&mtype=std"
response = httpx.get(url, timeout=60, follow_redirects=True)
meta = {
    "url": url,
    "final_url": str(response.url),
    "status": response.status_code,
    "acquired": datetime.now(UTC).isoformat(),
    "sha256": hashlib.sha256(response.content).hexdigest(),
    "content_type": response.headers.get("content-type"),
}
record(
    "M-aavso-lightcurve",
    "L4",
    "inconclusive",
    {},
    "# Public VSX R Dra reference request\n```json\n"
    + json.dumps(meta, indent=2)
    + "\n```\nMetadata retrieval alone is not a coherent phase comparison or an AAVSO observation light curve. No G5.lc acceptance inferred.",
    [meta],
    author="M",
    code_paths=["scripts/verify/m_aavso_lightcurve.py"],
    extra_files={
        "reference-response.txt": response.text,
        "acquisition.json": json.dumps(meta, indent=2),
    },
)
print(json.dumps(meta, indent=2))
print(response.text[:2000])
