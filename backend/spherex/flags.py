"""Pixel flags and mask presets (implementation.md §4.3, understanding.md §4.4)."""

from typing import Any

import numpy as np
from numpy.typing import ArrayLike, NDArray

A = NDArray[Any]

# understanding.md §4.4 bit table. Used as the canonical layout of every payload we emit (`.flags.u32`,
# stack flag_or), so a release whose header numbers a plane differently still reads the same downstream.
# F6 (2026-11-06): QR3 R7 7.0.5 headers match this table bit for bit; SATELLITE_HALO is absent there.
# F6 also found PHANTOM (4) and REFERENCE (5) defined in QR2 (6.x) headers; they are added here.
CANONICAL_BITS = {
    "TRANSIENT": 0, "OVERFLOW": 1, "SUR_ERROR": 2, "PHANTOM": 4, "REFERENCE": 5, "NONFUNC": 6, "DICHROIC": 7, "MISSING_DATA": 9,
    "HOT": 10, "COLD": 11, "FULLSAMPLE": 12, "PHANMISS": 14, "NONLINEAR": 15, "PERSIST": 17,
    "OUTLIER": 19, "CROSSTALK": 20, "SOURCE": 21, "GHOST": 22, "GHOST_FPA": 23, "GHOST_EXT": 24,
    "STREAK": 25, "BLOOM": 26, "SNOWBALL": 27, "HALO": 28, "SATELLITE_HALO": 29}

# One-line meanings for overlays and tooltips (understanding.md §4.4). Scientific text: owner I.
FLAG_INFO = {
    "TRANSIENT": "cosmic ray or bloom onset on the ramp", "OVERFLOW": "reached about half full well "
    "(bright star); cores that overflowed early are blank", "SUR_ERROR": "onboard ramp-fit error",
    "PHANTOM": "phantom pixel (QR2 plane)", "REFERENCE": "reference pixel, not light-sensitive (QR2 plane)",
    "NONFUNC": "dead pixel", "DICHROIC": "low throughput at the band 3/4 edge",
    "MISSING_DATA": "lost in downlink", "HOT": "hot pixel", "COLD": "cold pixel",
    "FULLSAMPLE": "informational", "PHANMISS": "not correctable", "NONLINEAR": "no reliable "
    "nonlinearity correction", "PERSIST": "persistence from an earlier bright exposure (mimics transients)",
    "OUTLIER": "isolated outlier outside known sources: could be an uncatalogued source",
    "CROSSTALK": "electrical crosstalk echo", "SOURCE": "pixel of a known catalogue source",
    "GHOST": "optical ghost", "GHOST_FPA": "optical ghost (focal plane)", "GHOST_EXT": "optical ghost "
    "(external)", "STREAK": "linear streak (satellite or fast asteroid)", "BLOOM": "charge bloom",
    "SNOWBALL": "snowball", "HALO": "halo", "SATELLITE_HALO": "satellite halo"}


def flag_bits(flags_hdr: Any) -> dict[str, int]:
    """Mask plane names and values are self-described, so read them from the header instead of
    hardcoding. Two conventions exist (F6, 2026-11-06):
      QR3 (R7 7.0.x):  MSKNnnnn = '<NAME>', MSKMnnnn = <mask value>
      QR2 (6.4–6.5.x): HIERARCH MP_<NAME> = <bit number>
    A plane missing from the header (e.g. SATELLITE_HALO in R7 7.0.5) simply masks nothing. A header
    with neither convention raises: silently masking nothing would let bad pixels into every stack."""
    out = {}
    for k in flags_hdr:
        if k.startswith("MSKN"):
            n = k[4:]
            out[flags_hdr[k].strip()] = int(flags_hdr.get("MSKM" + n, 1 << int(n)))
        elif k.startswith("MP_"):
            out[k[3:]] = 1 << int(flags_hdr[k])
    if not out:
        raise ValueError("FLAGS header defines no mask planes (neither MSKNnnnn nor MP_<name>)")
    return out


PRESETS = {
    # IRSA Mosaic Tool list (Supplement §3.4.3): clean imaging
    "imaging": ["TRANSIENT", "SUR_ERROR", "REFERENCE", "NONFUNC", "DICHROIC", "MISSING_DATA", "HOT", "COLD",
                "PHANMISS", "NONLINEAR", "PERSIST", "CROSSTALK", "GHOST", "GHOST_FPA", "GHOST_EXT",
                "STREAK", "BLOOM", "SNOWBALL", "HALO", "SATELLITE_HALO"],
    # IRSA photometry list (Supplement §3.3)
    "photometry": ["SUR_ERROR", "REFERENCE", "NONFUNC", "MISSING_DATA", "HOT", "COLD", "NONLINEAR", "PERSIST",
                   "BLOOM", "SNOWBALL", "HALO", "SATELLITE_HALO"],
    # Ours: like imaging, but keep STREAK (fast NEOs) visible. OUTLIER and SOURCE are never masked.
    "discovery": ["TRANSIENT", "SUR_ERROR", "REFERENCE", "NONFUNC", "DICHROIC", "MISSING_DATA", "HOT", "COLD",
                  "PHANMISS", "NONLINEAR", "PERSIST", "CROSSTALK", "GHOST", "GHOST_FPA", "GHOST_EXT",
                  "BLOOM", "SNOWBALL", "HALO", "SATELLITE_HALO"],
    # Ours, for bright targets (Barnard, R Dra, RW Aur): mask only hard-bad pixels. Footprint flags
    # (BLOOM, HALO, NONLINEAR, PERSIST, GHOST…) can cover the star itself; draw them instead.
    "bright": ["TRANSIENT", "SUR_ERROR", "REFERENCE", "NONFUNC", "MISSING_DATA", "HOT", "COLD"],
}

# Informational planes OR-ed into every stack's flag_or output (§4.5).
INFO_FLAGS = ("OVERFLOW", "SOURCE", "OUTLIER", "STREAK")


def bad_mask(flags: A, bits: dict[str, int], preset: str) -> A:
    m = 0
    for name in PRESETS[preset]:
        m |= bits.get(name, 0)
    return (flags & m) != 0


def info_bits(bits: dict[str, int]) -> int:
    m = 0
    for name in INFO_FLAGS:
        m |= bits.get(name, 0)
    return m


def canonical(flags: ArrayLike, bits: dict[str, int]) -> A:
    """Re-pack a frame's flags (its own header layout) into CANONICAL_BITS as uint32.
    Unknown planes are dropped: a payload bit must always mean what CANONICAL_BITS says."""
    f = np.asarray(flags, np.int64)
    out = np.zeros(f.shape, np.uint32)
    for name, v in bits.items():
        if name in CANONICAL_BITS:
            out |= (((f & v) != 0).astype(np.uint32) << np.uint32(CANONICAL_BITS[name]))
    return out


CANONICAL_INFO = sum(1 << CANONICAL_BITS[n] for n in INFO_FLAGS)
