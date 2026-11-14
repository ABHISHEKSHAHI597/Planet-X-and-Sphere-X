"""Acquire the 30 public M0--T9 SpeX standards by immutable author Git blobs."""

import base64
import csv
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import httpx
import numpy as np
from astropy.io import fits

ROOT = Path(__file__).resolve().parents[2]
tree = json.loads((ROOT / ".cache/m-splat/tree.json").read_text())["tree"]
standards = list(
    csv.DictReader(
        (ROOT / ".cache/m-splat/STANDARDS_DWARF_SPEX-PRISM.csv")
        .read_text()
        .splitlines()
    )
)
folder = ROOT / "backend/spherex/data/templates"
manifest_path = folder / "provenance.json"
manifest = json.loads(manifest_path.read_text())
for row in standards:
    entry = next(p for p in tree if p["path"].endswith("/" + row["FILENAME"] + ".gz"))
    name = "splat_" + row["FILENAME"] + ".gz"
    path = folder / name
    if path.exists():
        body = path.read_bytes()
    else:
        response = httpx.get(entry["url"], timeout=60)
        response.raise_for_status()
        body = base64.b64decode(response.json()["content"])
    if (
        hashlib.sha1(b"blob " + str(len(body)).encode() + b"\0" + body).hexdigest()
        != entry["sha"]
    ):
        raise ValueError("standard Git blob mismatch")
    path.write_bytes(body)
    with fits.open(path) as hdus:
        wave, flux, error = np.asarray(hdus[0].data, float)
        header = hdus[0].header
        absolute = header.get("XUNITS") == "um" and header.get("YUNITS") in (
            "Wm-2um-1",
            "ergss-1cm-2A-1",
        )
        relative = "XUNITS" not in header and "YUNITS" not in header
        if not (absolute or relative) or not np.all(np.diff(wave) > 0):
            raise ValueError("unsupported standard format")
        obj = header.get("OBJECT", row["FILENAME"])
    manifest[name] = {
        "url": entry["url"],
        "source_path": entry["path"],
        "git_blob": entry["sha"],
        "sha256": hashlib.sha256(body).hexdigest(),
        "inspected": datetime.now(UTC).isoformat(),
        "spectral_type": row["SPT"],
        "object": obj,
        "units": "wavelength micron; F_lambda "
        + str(header.get("YUNITS"))
        + "; third row uncertainty"
        if absolute
        else "wavelength micron; relative F_lambda shape only (original header lacks absolute units)",
        "format": "irtf-absolute-flambda" if absolute else "relative-splat-flambda",
        "units_source": "https://splat.physics.ucsd.edu/splat/splat.html (file format convention)",
        "reference": "Burgasser & SPLAT Development Team 2017; adopted type from STANDARDS_DWARF_SPEX-PRISM.csv",
        "kind": "observed standard",
    }
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(row["SPT"], name, flush=True)
