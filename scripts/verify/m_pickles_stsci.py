"""Acquire Pickles normal-star composites from the official STScI CDBS mirror."""

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import httpx
from astropy.io import fits

ROOT = Path(__file__).resolve().parents[2]
cache = ROOT/".cache/m-pickles"
cache.mkdir(parents=True,exist_ok=True)
base = "https://ssb.stsci.edu/cdbs/grid/pickles/dat_uvk/"
index = cache/"pickles_uk.fits"
if not index.exists():
    response = httpx.get(base+index.name,timeout=60)
    response.raise_for_status()
    index.write_bytes(response.content)
table = fits.getdata(index)
print(table.dtype.names,flush=True)
folder = ROOT/"backend/spherex/data/templates"
manifest_path = folder/"provenance.json"
manifest = json.loads(manifest_path.read_text())
for spectral_type in ["A0V","G2V"]:
    rows = [r for r in table if str(r["SPTYPE"]).replace(" ","").upper() == spectral_type]
    if len(rows) != 1:
        raise ValueError("ambiguous Pickles spectral type")
    filename = str(rows[0]["FILENAME"]).strip()
    if not filename.endswith(".fits"):
        filename += ".fits"
    path = folder/filename
    if not path.exists():
        response = httpx.get(base+filename,timeout=60)
        response.raise_for_status()
        path.write_bytes(response.content)
    with fits.open(path) as hdus:
        print(filename,hdus[1].columns,flush=True)
    manifest[filename] = {"url": base+filename,"sha256": hashlib.sha256(path.read_bytes()).hexdigest(),"retrieved": datetime.now(UTC).isoformat(),
        "format": "pickles-stsci-flambda","spectral_type": "Pickles "+spectral_type,"kind": "empirical/synthetic composite",
        "catalogue_url": base+index.name,"catalogue_sha256": hashlib.sha256(index.read_bytes()).hexdigest(),
        "reference": "Pickles 1998 PASP 110,863; STScI CDBS UVK library",
        "note": "Composite stellar spectrum normalized to V=0 Vega magnitude by STScI; includes interpolated/modelled infrared regions. No template-error estimate. Not a target flux calibration."}
    manifest_path.write_text(json.dumps(manifest,indent=2))
