"""TEMPORARY ADAPTER (owner I, to be replaced by D's spherex/access/*): minimal, polite, stdlib-only
archive reads used by Role I's foundation-check scripts when no committed fixture covers a check.
  * S3 byte ranges of public SPHEREx files (anonymous HTTPS), header walking without data download
  * IRSA SIA2 coverage (multi-collection) and TAP sync (CSV)
  * IRSA cutouts streamed and closed after ZODI (implementation.md §3.4 B), with retries
Nothing in backend/spherex imports this module (workflow.md §3: only spherex/access does network I/O).
"""
import csv
import io
import math
import time
import urllib.parse
import urllib.request

import numpy as np
from astropy.io import fits

S3 = "https://nasa-irsa-spherex.s3.amazonaws.com/"
SIA = "https://irsa.ipac.caltech.edu/SIA"
TAP = "https://irsa.ipac.caltech.edu/TAP/sync"
IBE_PREFIX = "https://irsa.ipac.caltech.edu/ibe/data/spherex/"
UA = {"User-Agent": "ParallaX/0.1 (NASA Space Apps 2026; foundation checks)"}
BLOCK = 2880
_DT = {8: ">u1", 16: ">i2", 32: ">i4", 64: ">i8", -32: ">f4", -64: ">f8"}


def _get(url, headers=None, timeout=90, tries=4, data=None):
    for k in range(tries):
        try:
            req = urllib.request.Request(url, headers={**UA, **(headers or {})}, data=data)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except Exception as e:
            code = getattr(e, "code", 500)
            if 400 <= code < 500 and code != 429:
                raise
            if k == tries - 1:
                raise
            time.sleep(min(30, 2 ** k))


def s3_range(key, start, stop):
    """Bytes [start, stop) of an S3 object."""
    return _get(S3 + key, {"Range": f"bytes={start}-{stop - 1}"})


def data_bytes(h):
    n = h.get("NAXIS", 0)
    if n == 0:
        return 0
    return abs(h["BITPIX"]) // 8 * h.get("GCOUNT", 1) * (
        h.get("PCOUNT", 0) + math.prod(h[f"NAXIS{i}"] for i in range(1, n + 1)))


def _padded(n):
    return -(-n // BLOCK) * BLOCK


def s3_header_at(key, offset, chunk=4 * BLOCK):
    """Parse one FITS header starting at byte `offset`. Returns (header, data_offset)."""
    raw = b""
    while True:
        raw += s3_range(key, offset + len(raw), offset + len(raw) + chunk)
        for i in range(0, len(raw) - 79, 80):
            if raw[i:i + 8] == b"END     ":
                end = _padded(i + 80)
                return fits.Header.fromstring(raw[:end].decode("ascii")), offset + end


def s3_hdu_map(key, stop_after=None):
    """Walk every header of an S3 FITS file. Returns [(extname, header, data_offset, nbytes)]."""
    out, off = [], 0
    while True:
        try:
            h, doff = s3_header_at(key, off)
        except Exception:
            return out
        name = h.get("EXTNAME", "PRIMARY").strip()
        nb = data_bytes(h)
        out.append((name, h, doff, nb))
        if stop_after and name == stop_after:
            return out
        off = doff + _padded(nb)


def s3_image_rows(key, h, data_offset, y0, y1):
    """Rows y0..y1-1 (0-based) of a 2-D image HDU, decoded to native-endian."""
    nx = h["NAXIS1"]
    bpp = abs(h["BITPIX"]) // 8
    raw = s3_range(key, data_offset + y0 * nx * bpp, data_offset + y1 * nx * bpp)
    a = np.frombuffer(raw, _DT[h["BITPIX"]]).reshape(y1 - y0, nx)
    return a.astype(a.dtype.newbyteorder("="))


def sia2(ra, dec, radius_deg, collections):
    q = [("POS", f"CIRCLE {ra:.7f} {dec:.7f} {radius_deg:.6f}"), ("RESPONSEFORMAT", "VOTABLE")]
    q += [("COLLECTION", c) for c in collections]
    from astropy.io.votable import parse_single_table
    raw = _get(SIA + "?" + urllib.parse.urlencode(q), timeout=120)
    vt = parse_single_table(io.BytesIO(raw))
    t = vt.to_table(use_names_over_ids=True)
    if "access_url" not in t.colnames:      # IRSA SIA2 fields carry names, not ids
        t.rename_columns(t.colnames, [f.name for f in vt.fields])
    return [dict(collection=str(r["obs_collection"]), obs_id=str(r["obs_id"]),
                 band=str(r["energy_bandpassname"]), t_min=float(r["t_min"]),
                 access_url=str(r["access_url"]),
                 s3_key=str(r["access_url"]).removeprefix(IBE_PREFIX)) for r in t]


def tap_csv(query, url=TAP):
    body = urllib.parse.urlencode(dict(REQUEST="doQuery", LANG="ADQL", FORMAT="csv", QUERY=query)).encode()
    raw = _get(url, data=body, timeout=180)
    return list(csv.DictReader(io.StringIO(raw.decode())))


def cutout(access_url, ra, dec, size_deg, wanted=("IMAGE", "FLAGS", "VARIANCE", "ZODI"), tries=4):
    """IRSA cutout, read until the last wanted HDU and then closed (EPSF never transferred)."""
    url = f"{access_url}?center={ra:.7f},{dec:.7f}deg&size={size_deg:.5f}"
    for k in range(tries):
        try:
            req = urllib.request.Request(url, headers=UA)
            out, nread = {}, 0
            with urllib.request.urlopen(req, timeout=120) as r:
                def take(n):
                    b = r.read(n)
                    if len(b) != n:
                        raise EOFError("stream ended early")
                    return b
                primary = None
                while len(out) < len(wanted):
                    raw = b""
                    while True:
                        blk = take(BLOCK); raw += blk
                        if any(blk[i:i + 8] == b"END     " for i in range(0, BLOCK, 80)):
                            break
                    h = fits.Header.fromstring(raw.decode("ascii"))
                    nb = data_bytes(h)
                    data = take(_padded(nb)) if nb else b""
                    nread += len(raw) + len(data)
                    name = h.get("EXTNAME", "PRIMARY").strip()
                    if name == "PRIMARY":
                        primary = h
                    if name in wanted:
                        shape = tuple(h[f"NAXIS{i}"] for i in range(h["NAXIS"], 0, -1))
                        a = np.frombuffer(data[:nb], _DT[h["BITPIX"]]).reshape(shape)
                        a = a.astype(a.dtype.newbyteorder("="))
                        if a.dtype.kind in "iu":
                            a = a.astype(np.int64) + int(h.get("BZERO", 0))
                        out[name] = (h, a)
            return out, primary, nread
        except Exception as e:
            code = getattr(e, "code", 500)
            if (400 <= code < 500 and code != 429) or k == tries - 1:
                raise
            time.sleep(min(30, 2 ** (k + 1)))


def s3_rice_rows(key, h, data_offset, y0, y1):
    """Rows y0..y1-1 of a RICE_1 tile-compressed image HDU with one-row tiles (ZTILE1 = NAXIS1,
    ZTILE2 = 1), as SPHEREx full-file FLAGS are: fetch the row descriptors, then each row's heap bytes."""
    from astropy.io.fits.hdu.compressed._codecs import Rice1
    assert h["ZCMPTYPE"] == "RICE_1" and h["ZTILE2"] == 1 and h["NAXIS1"] == 8
    desc = np.frombuffer(s3_range(key, data_offset + 8 * y0, data_offset + 8 * y1), ">i4").reshape(-1, 2)
    heap = data_offset + h.get("THEAP", h["NAXIS1"] * h["NAXIS2"])
    codec = Rice1(blocksize=h.get("ZVAL1", 32), bytepix=h.get("ZVAL2", 4), tilesize=h["ZNAXIS1"])
    lo, hi = int(desc[:, 1].min()), int((desc[:, 1] + desc[:, 0]).max())
    blob = s3_range(key, heap + lo, heap + hi)
    rows = [np.asarray(codec.decode(np.frombuffer(blob[o - lo:o - lo + n], np.uint8))).view(np.int32 if h["ZBITPIX"] == 32 else np.int16)
            for n, o in desc]
    return np.array(rows).astype(np.int64) + int(h.get("BZERO", 0))
