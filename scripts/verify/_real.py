"""Shared Role I real-target pipeline for the L3 checks: cached real cutouts → calibrate → QA → grid →
visit stacks and cubes, through the production modules (preprocess, epochs, grid, stack, cube)."""
import json

import numpy as np
from _cache import CACHE, D6Calib, cutouts, load_cutout

from spherex.cube import DIFF_ORDER, build_cube, diff_fwhm_arcsec
from spherex.epochs import survey_number, time_bins
from spherex.grid import frame_to_grid
from spherex.preprocess import calibrate
from spherex.stack import build_stack


class StackCalib:
    """Calib for bands whose CWAVE was not collected: stacks never read λ, so λ is NaN (cubes impossible)."""
    def __init__(self, base):
        nan = np.broadcast_to(np.float32(np.nan), (2040, 2040))
        self.cwave = {d: base.cwave.get(d, nan) for d in range(1, 7)}
        self.cband = {d: base.cband.get(d, nan) for d in range(1, 7)}
        self.channel, self.fluxcorr = base.channel, {}


CALIB = StackCalib(D6Calib())


def frames(tag, band=None, preset="discovery"):
    out = []
    for p in cutouts(tag):
        raw, meta = load_cutout(p)
        if band is None or int(raw.hdus["IMAGE"][0]["DETECTOR"]) == band:
            cf = calibrate(raw, CALIB, preset)
            out.append((raw, cf, meta))
    return out


def visits(items):
    """{band: [TimeBin…]} from real MJD-AVG, DETECTOR and SPS_EPA, plus the input list order."""
    mjd = [cf.mjd for _, cf, _ in items]
    det = [cf.detector for _, cf, _ in items]
    sv = [survey_number(cf.mjd, cf.header["SPS_EPA"]) for _, cf, _ in items]
    return time_bins(mjd, det, "visit", sv)


def stack_and_cube(items, tbin, grid, cube=True):
    """Visit stack (bilinear, documented path) and, if asked, the λ-matched-difference cube (bicubic,
    PSF-homogenised; decision record 0003). QA-rejected frames are listed as skipped."""
    sel = [items[i] for i in tbin.idx]
    ok = [(r, c) for r, c, _ in sel if c.qa["ok"]]
    skipped = [(c.ref.id, ";".join(c.qa["reasons"])) for _, c, _ in sel if not c.qa["ok"]]
    gs = [frame_to_grid(c, grid) for _, c in ok]
    st = build_stack(gs, tbin, grid, skipped)
    cb = None
    if cube:
        gd = [frame_to_grid(c, grid, DIFF_ORDER) for _, c in ok]
        cb = (gd, tbin)
    return st, cb


def cubes_pair(ca, cb, grid, band, rej=None):
    (ga, ta), (gb, tb) = ca, cb
    f = diff_fwhm_arcsec(ga, gb)
    return build_cube(ga, ta, band, grid, homog_fwhm_arcsec=f), build_cube(gb, tb, band, grid, homog_fwhm_arcsec=f), f


def gaia(name):
    return json.loads((CACHE / f"gaia_{name}.json").read_text())


def gaia_xy(rows, grid, mjd):
    """Gaia DR3 (J2016.0) positions propagated linearly to mjd, on the grid (field stars: parallax and
    perspective terms are < 0.01 px at these distances, so linear PM suffices)."""
    from spherex.targets import Target
    out=[]
    for r in rows:
        if r['pmra'] is None or r['pmdec'] is None:
            continue
        t=Target('', 'star', str(r['source_id']), float(r['ra']),float(r['dec']),2016.,float(r['pmra']),float(r['pmdec']),r.get('parallax'),r.get('radial_velocity'))
        ra,dec=t.pos([mjd]);x,y=grid.wcs.world_to_pixel_values(ra[0],dec[0])
        out.append((float(x),float(y),float(r['phot_g_mean_mag']),r['source_id']))
    return out
