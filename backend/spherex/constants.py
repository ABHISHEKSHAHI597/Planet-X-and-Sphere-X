"""Shared constants (implementation.md §14.1)."""
PIXEL_ARCSEC = 6.15
EXPTIME_S = 113.58
BANDS = {  # detector: (λmin, λmax µm, R)  — Supplement v2.0 Table 2
    1: (0.744, 1.116, 39), 2: (1.099, 1.651, 41), 3: (1.636, 2.421, 41),
    4: (2.423, 3.822, 35), 5: (3.809, 4.420, 112), 6: (4.412, 5.002, 128)}
CHANNELS_PER_DETECTOR = 17
DETECTOR_PARTNER = {1: 4, 2: 5, 3: 6, 4: 1, 5: 2, 6: 3}   # co-aligned through the dichroic
SCIENCE_START = "2025-05-01"
SPHEREX_HORIZONS_ID = -163182
NODATA_F16 = -65504.0
# Use each catalogue's own epoch; pass rv only with Gaia epochs (SIMBAD J2000 is linear)
TEST_TARGETS = {  # name: (ra, dec, epoch, pmra*, pmdec [mas/yr], plx [mas], rv [km/s] or None, source)
    "Barnard's Star": (269.44850252544, 4.73942005111, 2016.0, -801.551, 10362.394, 546.976, -110.47,
                       "Gaia DR3 4472832130942575872"),
    "eps Ind B":      (331.07645259656, -56.79381206688, 2016.0, 3981.977, -2466.832, 270.658, None,
                       "Gaia DR3 6412596012146801152 (Ba+Bb photocentre)"),
    "WISE 0855-0714": (133.81890825, -7.247048, 2000.0, -8123.7, 673.2, 439.0, None,
                       "SIMBAD J2000 from Kirkpatrick+2021 (linear)"),
    "RW Aur":         (76.95654431103, 30.40131614989, 2016.0, 2.641, -27.398, 6.406, None,
                       "Gaia DR3: position of A (…815232); PM and plx of B (…424576), since A has RUWE 16"),
    "R Dra":          (248.16737836729, 66.75500674547, 2016.0, -20.643, 6.149, 1.251, None,
                       "Gaia DR3 1648328016354496384")}
TWOMASS_EPOCH = {"Barnard's Star": 2000.405, "eps Ind B": 1999.851, "RW Aur": 1999.904}
