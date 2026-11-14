"""Acquire a small public IRTF template subset with original bytes and provenance."""

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import httpx
from astropy.io import fits

ROOT = Path(__file__).resolve().parents[2]
out = ROOT / "backend/spherex/data/templates"
out.mkdir(parents=True, exist_ok=True)
manifest = {}
for name in [
    "M0V_HD19305.fits",
    "L1_2MASSJ1439+1929.fits",
    "T4.5_2MASSJ0559-1404.fits",
]:
    url = (
        "https://irsa.ipac.caltech.edu/data/IRTF_Extra/SpectralLibrary/spectra/spectrallibrary/"
        + name
    )
    path = out / name
    if not path.exists():
        response = httpx.get(url, timeout=90)
        response.raise_for_status()
        path.write_bytes(response.content)
    with fits.open(path) as hdus:
        # The original 2009 products use legacy (B-V) keyword names. Retain
        # original bytes and report warnings instead of rewriting the archive.
        hdus.verify("warn")
        header = dict(hdus[0].header)
        shape = list(hdus[0].data.shape)
    manifest[name] = {
        "url": url,
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "inspected": datetime.now(UTC).isoformat(),
        "shape": shape,
        "header": header,
        "reference": "Cushing, Rayner & Vacca 2005 ApJ 623 1115; Rayner, Cushing & Vacca 2009 ApJS 185 289",
        "catalogue": "IRTF Spectral Library (IRSA public mirror); original version 2009-12-01",
        "note": "Illustrative observed templates; not a complete M/L/T/Y classification grid. Missing wavelengths and atmospheric gaps must remain missing.",
    }
    print(name, shape, flush=True)
(out / "provenance.json").write_text(
    json.dumps(manifest, indent=2, default=str), encoding="utf-8"
)
