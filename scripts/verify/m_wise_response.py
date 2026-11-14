"""Retrieve primary WISE photon response data with immutable local provenance."""

import asyncio
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import httpx


async def main():
    out = Path(__file__).resolve().parents[2] / "backend/spherex/data"
    out.mkdir(exist_ok=True)
    provenance = {}
    async with httpx.AsyncClient(timeout=60) as client:
        for band in ["W1", "W2"]:
            url = f"https://irsa.ipac.caltech.edu/data/WISE/docs/release/All-Sky/expsup/figures/RSR-{band}.txt"
            response = await client.get(url)
            response.raise_for_status()
            body = response.content
            (out / f"wise_{band}.txt").write_bytes(body)
            provenance[band] = {
                "url": url,
                "sha256": hashlib.sha256(body).hexdigest(),
                "bytes": len(body),
                "retrieved": datetime.now(UTC).isoformat(),
                "units": "wavelength micron; response per photon; uncertainty ppt",
                "source": "Wright et al. 2010 via WISE All-Sky Explanatory Supplement IV.4.h Fig5a",
            }
    (out / "wise.provenance.json").write_text(json.dumps(provenance, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
