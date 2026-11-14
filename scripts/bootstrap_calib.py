"""Calibration bootstrap and lock (owner D; implementation.md §3.5, workflow.md §8.4).

  discover          list the bucket, select the newest version per product/detector, write
                    config/calibration.lock (sha256 kept from the old lock where the file is unchanged)
  fetch [--freeze]  download every locked file to $PARALLAX_CALIB (default ~/.cache/parallax/calib),
                    check MD5 == S3 ETag, then check sha256 against the lock; --freeze records missing
                    sha256 values (only in a lock PR, reviewed by I and M)
  verify            re-hash the local files against the lock (what `Calib(verify=True)` does)

Changing the lock re-runs F1, F3, F4, F5, F13 (workflow.md §8.4).
"""
import argparse
import asyncio
import os
import sys
from pathlib import Path

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from spherex.access.http import make_client  # noqa: E402
from spherex.access.releases import load as load_registry  # noqa: E402
from spherex.calib import LOCK_PATH, Calib, CalibrationLock, bootstrap, discover  # noqa: E402

CAL_ROOT = Path(os.environ.get("PARALLAX_CALIB", Path.home() / ".cache/parallax/calib"))


async def do_discover():
    reg = load_registry()
    async with make_client() as c:
        new = await discover(c, reg.calibration_release)
    if LOCK_PATH.exists():
        old = {e.s3_key: e for e in CalibrationLock.load().entries}
        for e in new.entries:
            o = old.get(e.s3_key)
            if o and o.size == e.size and o.etag_md5 == e.etag_md5:
                e.sha256 = o.sha256
    new.save()
    print(f"wrote {LOCK_PATH.relative_to(ROOT)}: {len(new.entries)} files, "
          f"{sum(e.size for e in new.entries) / 1e6:.0f} MB, complete={new.complete}, lock_hash={new.lock_hash()}")
    for n in new.notes:
        print("note:", n)


async def do_fetch(freeze):
    lock = CalibrationLock.load()
    async with make_client(timeout=300) as c:
        lock = await bootstrap(c, lock, CAL_ROOT, freeze=freeze,
                               progress=lambda e: print("ok", e.s3_key, e.sha256[:12], flush=True))
    if freeze:
        lock.save()
        print("lock frozen:", lock.lock_hash(), "complete:", lock.complete)


def do_verify():
    Calib(CAL_ROOT, verify=True)
    print("all locked calibration files verified under", CAL_ROOT)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("cmd", choices=["discover", "fetch", "verify"])
    p.add_argument("--freeze", action="store_true")
    a = p.parse_args()
    if a.cmd == "discover":
        asyncio.run(do_discover())
    elif a.cmd == "fetch":
        asyncio.run(do_fetch(a.freeze))
    else:
        do_verify()
