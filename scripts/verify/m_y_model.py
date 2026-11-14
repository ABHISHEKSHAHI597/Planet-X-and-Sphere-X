"""Acquire one immutable public SPLAT-distributed 500 K BT-Settl model."""

import base64
import gzip
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import httpx

root = Path(__file__).resolve().parents[2]
tree = json.loads((root / ".cache/m-splat/tree.json").read_text())["tree"]
entry = next(
    p
    for p in tree
    if p["path"].endswith("btsettl08_t500_g4.50_z-0.00_en-0.00_SPEX-PRISM.txt.gz")
)
folder = root / "backend/spherex/data/templates"
name = "btsettl500K_g4.5.txt.gz"
if (folder / name).exists():
    body = (folder / name).read_bytes()
else:
    response = httpx.get(entry["url"], timeout=60)
    response.raise_for_status()
    body = base64.b64decode(response.json()["content"])
if (
    hashlib.sha1(b"blob " + str(len(body)).encode() + b"\0" + body).hexdigest()
    != entry["sha"]
):
    raise ValueError("model Git blob mismatch")
(folder / name).write_bytes(body)
meta = {
    "url": entry["url"],
    "source_path": entry["path"],
    "git_blob": entry["sha"],
    "sha256": hashlib.sha256(body).hexdigest(),
    "retrieved": datetime.now(UTC).isoformat(),
    "format": "splat-flambda-model",
    "spectral_type": "500 K BT-Settl model",
    "temperature_K": 500,
    "log_g_cgs": 4.5,
    "units": "um; erg/s/cm2/um (surface F_lambda)",
    "kind": "atmosphere model",
    "units_source": "https://raw.githubusercontent.com/aburgasser/splat/main/src/splat/model.py (_loadInterpolatedModel units)",
    "reference": "Allard et al. 2012, Philosophical Transactions A 370, 2765; SPLAT instrument-sampled distribution",
    "note": "Illustrative 500 K cool-atmosphere model, not an observed Y standard or a measured temperature. SPEX-PRISM wavelength coverage only; no extrapolation to 5 microns.",
}
(folder / "y-model.provenance.json").write_text(json.dumps(meta, indent=2))
manifest = json.loads((folder / "provenance.json").read_text())
manifest[name] = meta
(folder / "provenance.json").write_text(json.dumps(manifest, indent=2))
print(gzip.decompress(body).decode()[:2200])
