"""FITS primitives shared by both FrameSources (implementation.md §3.4).

No network here: the streamed cutout reader and the S3 range reader feed bytes in. Two rules from
implementation.md §15: data sizes follow the FITS standard, and integers stay integers (FLAGS needs bit
tests, so never promote them to float)."""
from __future__ import annotations

import math
from typing import Any

import numpy as np
from astropy.io import fits

BLOCK = 2880
CARD = 80
_DT = {8: ">u1", 16: ">i2", 32: ">i4", 64: ">i8", -32: ">f4", -64: ">f8"}
WANTED = ("IMAGE", "FLAGS", "VARIANCE", "ZODI")     # HDUs 1–4; they end at byte 89,280 of a 29×29 cutout


class CorruptResponse(ValueError):
    """Bytes that are not the FITS we asked for (an HTML error page behind HTTP 200, a bad header).
    Retryable: IRSA has served truncated and odd bodies under load (understanding.md §4.6)."""


def padded(n: int) -> int:
    return -(-n // BLOCK) * BLOCK


def data_bytes(h: fits.Header) -> int:
    """FITS standard: |BITPIX|/8 · GCOUNT · (PCOUNT + NAXIS1 · … · NAXISn), unpadded."""
    n = int(h.get("NAXIS", 0))
    if n == 0:
        return 0
    return abs(int(h["BITPIX"])) // 8 * int(h.get("GCOUNT", 1)) * (
        int(h.get("PCOUNT", 0)) + math.prod(int(h[f"NAXIS{i}"]) for i in range(1, n + 1)))


def header_end(raw: bytes) -> int | None:
    """Length of the padded header in `raw` (a multiple of 2880) if its END card is present."""
    for i in range(0, len(raw) - CARD + 1, CARD):
        if raw[i:i + 8] == b"END     ":
            return padded(i + CARD)
    return None


def parse_header(raw: bytes) -> fits.Header:
    if not (raw.startswith(b"SIMPLE  =") or raw.startswith(b"XTENSION=")):
        raise CorruptResponse(f"not a FITS header: {raw[:40]!r}")
    try:
        return fits.Header.fromstring(raw.decode("ascii"))
    except (UnicodeDecodeError, ValueError) as e:
        raise CorruptResponse(f"unparseable FITS header: {e}") from e


def extname(h: fits.Header) -> str:
    return str(h.get("EXTNAME", "PRIMARY")).strip()


def is_rice_tiled(h: fits.Header) -> bool:
    return bool(h.get("ZIMAGE", False)) and str(h.get("ZCMPTYPE", "")).strip() == "RICE_1"


def decode_image(h: fits.Header, raw: bytes) -> np.ndarray[Any, Any]:
    """Plain image HDU bytes → native-endian array, (NAXISn, …, NAXIS1). Integers keep integer type
    (int64 after BZERO); floats get BSCALE/BZERO only if present."""
    shape = tuple(int(h[f"NAXIS{i}"]) for i in range(int(h["NAXIS"]), 0, -1))
    arr = np.frombuffer(raw, dtype=_DT[int(h["BITPIX"])]).reshape(shape)
    return _scale(h, arr, h.get("BSCALE", 1), h.get("BZERO", 0))


def _scale(h: fits.Header, arr: np.ndarray[Any, Any], bscale: Any, bzero: Any) -> np.ndarray[Any, Any]:
    if arr.dtype.kind in "iu" and float(bscale) == 1.0 and float(bzero) == int(float(bzero)):
        return arr.astype(np.int64) + int(float(bzero))
    if "BSCALE" in h or "BZERO" in h or "ZSCALE" in h or "ZZERO" in h:
        return arr.astype(np.float64) * float(bscale) + float(bzero)
    return arr.astype(arr.dtype.newbyteorder("="))


def rice_rows_layout(h: fits.Header) -> tuple[int, int]:
    """Validate a one-row-tile RICE_1 image (SPHEREx full-file FLAGS, F1) → (nx, heap offset in the
    data unit). Anything else is refused rather than decoded wrongly."""
    if not is_rice_tiled(h):
        raise CorruptResponse("not a RICE_1 tile-compressed image")
    nx = int(h["ZNAXIS1"])
    if int(h.get("ZTILE1", nx)) != nx or int(h.get("ZTILE2", 1)) != 1:
        raise CorruptResponse(f"unsupported tiling ZTILE=({h.get('ZTILE1')},{h.get('ZTILE2')})")
    if int(h["NAXIS1"]) != 8:
        raise CorruptResponse("expected one 32-bit (count, offset) descriptor per row")
    heap = int(h.get("THEAP", int(h["NAXIS1"]) * int(h["NAXIS2"])))
    return nx, heap


def rice_decode_rows(h: fits.Header, descriptors: np.ndarray[Any, Any], heap_blob: bytes,
                     heap_lo: int) -> np.ndarray[Any, Any]:
    """Decode rows of a one-row-tile RICE_1 image. descriptors: (n, 2) int (nbytes, heap offset);
    heap_blob holds heap bytes [heap_lo, heap_lo + len). Returns (n, nx) int64 with ZZERO applied."""
    from astropy.io.fits.hdu.compressed._codecs import Rice1  # astropy's own decoder
    nx = int(h["ZNAXIS1"])
    zbitpix = int(h["ZBITPIX"])
    if zbitpix not in (16, 32):
        raise CorruptResponse(f"unsupported ZBITPIX {zbitpix}")
    codec = Rice1(blocksize=int(h.get("ZVAL1", 32)), bytepix=int(h.get("ZVAL2", zbitpix // 8)), tilesize=nx)
    view = np.int32 if zbitpix == 32 else np.int16
    rows = []
    for nbytes, off in np.asarray(descriptors, dtype=np.int64):
        lo = int(off) - heap_lo
        chunk = heap_blob[lo:lo + int(nbytes)]
        if len(chunk) != int(nbytes):
            raise EOFError("compressed row truncated")
        rows.append(np.asarray(codec.decode(np.frombuffer(chunk, np.uint8))).view(view)[:nx])
    out = np.array(rows, dtype=np.int64).reshape(len(rows), nx)
    zscale, zzero = float(h.get("ZSCALE", h.get("BSCALE", 1))), float(h.get("ZZERO", h.get("BZERO", 0)))
    if zscale != 1.0:
        return out * zscale + zzero
    return out + int(zzero)


def decode_hdu(h: fits.Header, raw: bytes) -> tuple[fits.Header, np.ndarray[Any, Any]]:
    """A whole data unit → (image header, array). Plain images decode directly; a one-row-tile RICE_1
    table (full-file FLAGS) is decompressed and reported with its image header."""
    if not is_rice_tiled(h):
        return h, decode_image(h, raw)
    nx, heap = rice_rows_layout(h)
    ny = int(h["NAXIS2"])
    desc = np.frombuffer(raw[:8 * ny], ">i4").reshape(ny, 2)
    return image_header_from_compressed(h), rice_decode_rows(h, desc, raw[heap:], 0)


def image_header_from_compressed(h: fits.Header) -> fits.Header:
    """The image header a RICE_1 BINTABLE represents (ZNAXISn → NAXISn, ZBITPIX → BITPIX), so a section
    of FLAGS from S3 carries the same keywords as the plain FLAGS image a cutout delivers."""
    from astropy.io.fits.hdu.compressed.header import _bintable_header_to_image_header
    return _bintable_header_to_image_header(h)


def shift_wcs_header(h: fits.Header, x0: int, y0: int, nx: int, ny: int) -> fits.Header:
    """Header of the sub-image [y0:y0+ny, x0:x0+nx]: NAXISn and every CRPIXn<alt> shifted, so the
    primary (SIP) WCS, alt WCS A (0-based parent pixels) and alt WCS W (λ lookup) all stay valid. SIP is
    relative to CRPIX, so its coefficients don't change. A section header then follows the cutout
    convention, i.e. calib.parent_origin(header) == (x0, y0) for a full-file CRPIXnA of 1 (F2)."""
    out = h.copy()
    out["NAXIS1"], out["NAXIS2"] = nx, ny
    for key in list(out.keys()):
        if key.startswith("CRPIX1"):
            out[key] = float(out[key]) - x0
        elif key.startswith("CRPIX2"):
            out[key] = float(out[key]) - y0
    return out
