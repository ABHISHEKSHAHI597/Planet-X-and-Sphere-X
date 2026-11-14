"""Acquire two small Pickles normal-star composites from the ESO mirror."""

import gzip
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import httpx

root = Path(__file__).resolve().parents[2]/"backend/spherex/data/templates"
manifest_path = root/"provenance.json"
manifest = json.loads(manifest_path.read_text())
for filename, spectral_type in [("uka0v.dat.gz","Pickles A0 V"),("ukg2v.dat.gz","Pickles G2 V")]:
    url = "https://www.eso.org/sci/observing/tools/standards/IR_spectral_library/"+filename
    path = root/filename
    if path.exists():
        body = path.read_bytes()
    else:
        response = httpx.get(url,timeout=60,follow_redirects=True)
        response.raise_for_status()
        body = response.content
    print(filename,gzip.decompress(body).decode()[:600],flush=True)
    path.write_bytes(body)
    manifest[filename] = {"url": url,"sha256": hashlib.sha256(body).hexdigest(),"retrieved": datetime.now(UTC).isoformat(),
        "format": "pickles-flambda-shape","spectral_type": spectral_type,"kind": "empirical/synthetic composite",
        "units": "wavelength Angstrom; relative F_lambda","reference": "Pickles 1998 PASP 110,863; ESO reference mirror",
        "note": "Some infrared values in original library are interpolated/modelled, as documented by ESO. Relative shape only; no absolute flux or template-error claim.",
        "units_source": "https://www.eso.org/sci/observing/tools/standards/IR_spectral_library.html"}
    manifest_path.write_text(json.dumps(manifest,indent=2))
