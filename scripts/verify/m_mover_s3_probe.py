"""Try public S3 explicitly for a real random-field frame that returned IRSA 503."""

import asyncio
import hashlib
import json
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "backend"), str(ROOT / "scripts")]
from _m_evidence import record
from spherex.access.dedup import dedup
from spherex.access.frames import snap_box
from spherex.access.http import make_client
from spherex.access.releases import load
from spherex.access.replay import RecordingTransport
from spherex.access.sources import build_source


async def main():
    cache = ROOT / ".cache/m-mover-fields"
    index = json.loads((cache / "http/index.json").read_text())
    failed = {
        k.split(" ", 1)[1].split("?", 1)[0]
        for k, v in index.items()
        if k.startswith("GET ") and ".fits?" in k and v["status"] >= 500
    }
    selected = None
    for path in sorted((cache / "coverage").glob("*.json")):
        doc = json.loads(path.read_text())
        for row in doc["rows"]:
            if row["access_url"] in failed:
                selected = row, [float(x) for x in doc["key"].split(",")[:2]]
                break
        if selected:
            break
    if selected is None:
        raise ValueError("No recorded IRSA-503 frame to probe")
    row, (ra, dec) = selected
    (ref,) = dedup([row], load(ROOT / "config/releases.yaml")).frames
    result = {
        "frame": ref.id,
        "irsa_url": ref.access_url,
        "s3_key": ref.s3_key,
        "centre": [ra, dec],
        "fov_arcmin": 2.0,
    }
    async with make_client(RecordingTransport(cache / "s3-probe-http")) as client:
        source = build_source(
            "s3", client=client, failover=False, cache_root=cache / "s3-probe-frames"
        )
        try:
            async with asyncio.timeout(180):
                raw = await source.fetch(ref, snap_box(ra, dec, 2.0))
            result.update(
                origin=raw.origin,
                mjd=float(raw.hdus["IMAGE"][0]["MJD-AVG"]),
                shape=list(raw.hdus["IMAGE"][1].shape),
                sha256={
                    n: hashlib.sha256(raw.hdus[n][1].tobytes()).hexdigest()
                    for n in ("IMAGE", "VARIANCE", "FLAGS", "ZODI")
                },
            )
        except Exception as ex:
            logging.getLogger(__name__).exception("Explicit public S3 probe failed")
            result["error"] = f"{type(ex).__name__}: {ex}"
    record(
        "M-mover-s3-probe",
        "L2",
        "inconclusive",
        {},
        "# Public alternate-source probe\n```json\n"
        + json.dumps(result, indent=2)
        + "\n```\nTransport availability only; not five-field detection or recovery acceptance. Native array checksums and exact frame/box preserved; range exchanges remain in .cache/m-mover-fields/s3-probe-http.",
        [ref.access_url],
        author="M",
        n_frames=0 if "error" in result else 1,
        code_paths=[
            "scripts/verify/m_mover_s3_probe.py",
            "backend/spherex/access/s3sections.py",
        ],
        extra_files={"probe.json": json.dumps(result, indent=2)},
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
