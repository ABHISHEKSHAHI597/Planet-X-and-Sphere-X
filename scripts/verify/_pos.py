"""Compatibility names for validation scripts, using M production astrometry."""
from spherex.targets import Target
from spherex.constants import TEST_TARGETS
from spherex.astrometry import parallax_factors

def pos(name):
    ra,dec,epoch,pmra,pmdec,plx,rv,source=TEST_TARGETS[name]
    return Target(name,'star',name,ra,dec,epoch,pmra,pmdec,plx,rv,astrometry_source=source).pos
WISE_ERA=(133.795129,-7.245147)
