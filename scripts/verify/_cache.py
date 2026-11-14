"""Readers for the real files collected by collect_real.py (cache dir, outside git). TEMPORARY: D's
Calib loader and FrameSources replace these once the calibration lock and pins exist."""
import io
import json
import os
import sys
from pathlib import Path

import numpy as np
from astropy.io import fits
from astropy.wcs import WCS

ROOT = Path(__file__).parents[2]
sys.path.insert(0, str(ROOT / "backend"))
CACHE = Path(os.environ.get("PARALLAX_CACHE", Path.home() / ".cache/parallax-verify"))
CAL = CACHE / "calib"


def table(stem):
    """A cached bintable (header text + raw data bytes) as a FITS_rec."""
    h = fits.Header.fromstring((CAL / f"{stem}.hdr").read_text())
    raw = (CAL / f"{stem}.bin").read_bytes()
    pad = b"\0" * (-len(raw) % 2880)
    buf = fits.PrimaryHDU().header.tostring().encode() + h.tostring().encode() + raw + pad
    with fits.open(io.BytesIO(buf)) as hl:
        return hl[1].data.copy(), h


def wcswave(det):
    t, h = table(f"wcswave_D{det}")
    return t["X"][0], t["Y"][0], t["VALUES"][0], h      # VALUES: (2, ny, nx) after FITS TDIM (2,9,9)


def lookup(det, xpix0, ypix0):
    """Bilinear WCS-WAVE lookup at 0-based parent pixels (table in raw 1-based FITS coordinates)."""
    from scipy.interpolate import RegularGridInterpolator
    X, Y, V, _ = wcswave(det)
    V = np.asarray(V, float)
    vals = V[0] if V.shape[0] == 2 else V[..., 0]
    f = RegularGridInterpolator((np.asarray(Y, float), np.asarray(X, float)), vals, method="linear",
                                bounds_error=False, fill_value=None)
    return f(np.stack([np.asarray(ypix0) + 1.0, np.asarray(xpix0) + 1.0], axis=-1))


def cwave_rows(det):
    return np.load(CAL / f"cwave_rows_D{det}.npy"), np.load(CAL / "cwave_rows_index.npy")


def cband_rows(det):
    return np.load(CAL / f"cband_rows_D{det}.npy")


def cwave_d6():
    return np.load(CAL / "cwave_D6.npy", mmap_mode="r")


def channel_map():
    return np.load(CAL / "channel_map.npy", mmap_mode="r")


def spectral_channels():
    return table("spectral_channels")[0]


def load_cutout(path):
    """A cached stream-aborted cutout → (types.RawFrame, meta). origin from CRPIXnA (cutout path)."""
    from spherex.calib import parent_origin
    from spherex.types import FrameRef, RawFrame
    z = np.load(path)
    hd = {n: fits.Header.fromstring(str(z[n + "_hdr"])) for n in ("IMAGE", "FLAGS", "VARIANCE", "ZODI")}
    hdus = {n: (hd[n], z[n]) for n in hd}
    meta = json.loads(str(z["meta"]))
    ref = FrameRef(access_url=meta["access_url"], s3_key=meta["s3_key"], collection=meta["collection"],
                   obs_id=meta["obs_id"], detector=meta["detector"], t_min=meta["t_min"])
    rel = "qr3" if "qr3" in meta["collection"] else "qr2"
    return RawFrame(hdus=hdus, wcs=WCS(hd["IMAGE"]), origin=parent_origin(hd["IMAGE"]), ref=ref, release=rel), \
        dict(meta, primary=fits.Header.fromstring(str(z["PRIMARY_hdr"])))


class D6Calib:
    """Calib (types.Calib) with the real QR3 D6 CWAVE (cal-swcs-v5-2026-191) and the real CHANNEL_MAP.
    CBAND is CWAVE/R (R = 128, band 6) because only sampled CBAND rows were collected: fine for
    stacks/cubes/diffs, which never read CBAND. fluxcorr is unavailable (F4, owner M)."""
    def __init__(self):
        self.cwave = {6: cwave_d6()}
        self.cband = {6: self.cwave[6] / 128.0}
        self.channel = channel_map()
        self.fluxcorr = {}


def cutouts(tag):
    return sorted((CACHE / "cutouts" / tag).glob("*.npz"))
