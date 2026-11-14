"""Seeded five random fields through production native detection/linking/vetting.

Small declared sampling budget: at most twelve D6 inputs per field, selected by
date before measurement. This records actual counts and misses, not full-depth
all-Gaia recovery acceptance. The full frame selection is retained for replay.
"""

import asyncio
import json
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "backend"), str(ROOT / "scripts")]
import numpy as np
from _m_evidence import record
from app.measurement import movers_api, native_detections
from app.pipeline import plan_view, skeleton
from app.services import Services
from app.settings import Settings
from spherex.access.replay import RecordingTransport
from spherex.external.gaia import GaiaClient


async def main():
    cache = ROOT / ".cache/m-mover-fields"
    svc = Services(
        Settings(
            cache_dir=cache,
            calib_root=ROOT / ".cache/calib",
            cpu_workers=0,
            run_watcher=False,
        ),
        transport=RecordingTransport(cache / "http"),
    )
    rng = np.random.default_rng(584031)
    # Four simultaneous IRSA cutouts have produced recorded HTTP 503s. Use a
    # single archive request at a time, retaining D's automatic S3 failover.
    svc.limiter.limits["irsa.ipac.caltech.edu"] = 1
    fields = [
        (
            float(rng.uniform(0, 360)),
            float(np.degrees(np.arcsin(rng.uniform(-0.866, 0.866)))),
        )
        for _ in range(5)
    ]
    results, manifests, sources = [], [], []
    try:
        for index, (ra, dec) in enumerate(fields):
            item = {"index": index, "ra": ra, "dec": dec}
            results.append(item)
            try:
                plan = await plan_view(
                    svc,
                    {
                        "q": f"{ra:.9f} {dec:.9f}",
                        "fov": "12",
                        "px": "6.15",
                        "bands": "6",
                    },
                )
                m = skeleton(svc, plan)
                available = sorted(
                    [r for r in plan.refs if r.detector == 6], key=lambda r: r.t_min
                )
                chosen = (
                    [
                        available[j]
                        for j in sorted(
                            set(
                                np.linspace(
                                    0, len(available) - 1, min(12, len(available))
                                ).astype(int)
                            )
                        )
                    ]
                    if available
                    else []
                )
                selected = {r.id for r in chosen}
                for f in m["frames"]:
                    if f["id"] not in selected:
                        f["skipped"] = "declared twelve-D6-frame empirical budget"
                m["_refs"] = [
                    r for r in m["_refs"] if r["s3_key"].rsplit("/", 1)[-1] in selected
                ]
                manifests.append(m)
                sources.extend(r.access_url for r in chosen)
                item.update(
                    key=plan.key,
                    selected_frames=[r.id for r in chosen],
                    available_d6=len(available),
                )

                def checkpoint(epochs, item=item, index=index):
                    item["partial_epochs"] = epochs
                    item["partial_detection_count"] = sum(map(len, epochs))
                    (cache / "progress.json").write_text(
                        json.dumps(results, indent=2, default=str)
                    )
                    print(
                        index,
                        "completed epochs",
                        len(epochs),
                        "partial detections",
                        item["partial_detection_count"],
                        flush=True,
                    )

                async with asyncio.timeout(300):
                    detections = await native_detections(svc, m, progress=checkpoint)
                m["_native_detections"] = detections
                svc.store.put_manifest(plan.key, m)
                result = await movers_api(svc, plan.key)
                stars = await GaiaClient(svc.client).cone(ra, dec, 0.1, g_max=20.0)
                expected = [
                    s.source_id
                    for s in stars
                    if s.pmra is not None
                    and s.pmdec is not None
                    and np.hypot(s.pmra, s.pmdec) > 500
                ]
                item.update(
                    n_native_detections=sum(map(len, detections)),
                    expected_gaia_pm_gt_500=expected,
                    detections=detections,
                    candidates=result["candidates"],
                    skipped=result.get("skipped", []),
                )
                print(
                    index,
                    "detections",
                    item["n_native_detections"],
                    "candidates",
                    len(item["candidates"]),
                    flush=True,
                )
            except Exception as ex:
                logging.getLogger(__name__).exception("Random-field experiment failed")
                item["error"] = f"{type(ex).__name__}: {ex}"
                item["fetch_skipped"] = (
                    m.get("_measurement_fetch_skipped", []) if "m" in locals() else []
                )
            (cache / "progress.json").write_text(
                json.dumps(results, indent=2, default=str)
            )
    finally:
        await svc.close()
    record(
        "M-mover-five-field-sample",
        "L3",
        "inconclusive",
        {},
        "# Five preselected random-field sample\n```json\n"
        + json.dumps(
            [{k: v for k, v in r.items() if k != "detections"} for r in results],
            indent=2,
            default=str,
        )
        + "\n```\nSmall declared input budget is not full-depth recovery. Original source manifests, detections and catalogue IDs retained. Proposed workflow all-Gaia mu>0.5 recovery cannot be certified without addressing displacement completeness: 0.3 pixel at 6.15 arcsec is 1.845 arcsec, requiring >3.69 years for a 0.5 arcsec/year source. No threshold changed; no public candidate claim.",
        sources,
        author="M",
        n_frames=len(sources),
        code_paths=[
            "scripts/verify/m_mover_fields.py",
            "backend/app/measurement.py",
            "backend/spherex/linking.py",
            "backend/spherex/movers.py",
        ],
        extra_files={
            "fields.json": json.dumps(results, indent=2, default=str),
            "manifests.json": json.dumps(manifests, indent=2, default=str),
        },
    )


if __name__ == "__main__":
    asyncio.run(main())
