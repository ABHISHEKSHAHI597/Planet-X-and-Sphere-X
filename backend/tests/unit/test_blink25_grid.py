"""25-year blink gridding and normalisation (spherex.blink25). L0/L1.

Assumptions (workflow.md §4.2): archival images are simple TAN images with Gaussian stars on a flat sky plus
Gaussian noise; zero points and pixel scales differ per "telescope". The tests check that a star lands where its
sky position says on the common grid, whatever the input pixel scale, orientation and zero point, and that every
epoch comes out with sky median 0 and robust σ 1 (so one stretch fits all)."""
import gzip
import io

import numpy as np
import pytest
from astropy.io import fits
from astropy.wcs import WCS

from spherex.blink25 import epoch_on_grid, read_image, select_epochs, sky_mask, spherex_epoch
from spherex.grid import centroids, make_grid

RA0, DEC0 = 269.45, 4.73


def fake_image(star_radec, pix_arcsec, n=200, flip=False, zero=1000.0, gain=5.0, sigma_noise=2.0, seed=0, gz=False,
               centre=(RA0, DEC0)):
    w = WCS(naxis=2)
    w.wcs.ctype = ["RA---TAN", "DEC--TAN"]
    w.wcs.crval = list(centre)
    w.wcs.crpix = [(n + 1) / 2, (n + 1) / 2]
    s = pix_arcsec / 3600
    w.wcs.cdelt = [s, -s] if flip else [-s, s]           # flip = rotated 180°: east right, north down
    rng = np.random.default_rng(seed)
    img = zero + rng.normal(0, sigma_noise, (n, n))
    x, y = w.wcs_world2pix(*star_radec, 0)
    yy, xx = np.indices((n, n))
    fw = 2.5 * 6.15 / pix_arcsec                          # same sky FWHM in every "telescope"
    img += gain * 400 * np.exp(-((xx - x) ** 2 + (yy - y) ** 2) / (2 * (fw / 2.355) ** 2))
    buf = io.BytesIO()
    fits.PrimaryHDU(img, header=w.to_header()).writeto(buf)
    raw = buf.getvalue()
    return gzip.compress(raw) if gz else raw


def star_xy(img, grid, radec):
    x, y = grid.wcs.world_to_pixel_values(*radec)
    return centroids(np.nan_to_num(img), [(float(x), float(y))], half=3)[0], (float(x), float(y))


@pytest.mark.parametrize("pix,flip,gz", [(1.0, False, True), (2.75, True, False), (1.375, False, False)])
def test_star_lands_at_its_sky_position_and_epoch_is_on_sky_sigma(pix, flip, gz):
    grid = make_grid(RA0, DEC0, 6.0, 3.0)
    star = (RA0 + 40 / 3600, DEC0 - 25 / 3600)
    img, n = epoch_on_grid([fake_image(star, pix, flip=flip, gz=gz)], grid)
    assert n == 1
    (cx, cy), (tx, ty) = star_xy(img, grid, star)
    assert np.hypot(cx - tx, cy - ty) < 0.35                     # < 1″ at 3″ pixels
    sky = sky_mask(img)
    assert abs(np.median(img[sky])) < 0.1
    assert 0.6 < 1.4826 * np.median(np.abs(img[sky] - np.median(img[sky]))) < 1.4   # resampling correlates noise


def test_mosaic_of_images_with_different_zero_points_is_seamless():
    grid = make_grid(RA0, DEC0, 6.0, 3.0)
    star = (RA0, DEC0)
    a = fake_image(star, 1.0, zero=100.0, seed=1)
    b = fake_image(star, 1.0, zero=9000.0, gain=50.0, sigma_noise=20.0, seed=2)
    img, n = epoch_on_grid([a, b, b"not a fits file"], grid)
    assert n == 2                                                 # the bad body is skipped, not fatal
    sky = sky_mask(img)
    assert abs(np.median(img[sky])) < 0.1                         # zero points never mix


def test_no_usable_image_is_all_nan_not_zero():
    grid = make_grid(RA0, DEC0, 6.0, 3.0)
    far = fake_image((RA0 + 10, DEC0), 1.0, centre=(RA0 + 10, DEC0))                       # covers a different patch of sky
    img, n = epoch_on_grid([far], grid)
    assert n == 0 and np.isnan(img).all()


def test_read_image_rejects_files_without_celestial_wcs():
    buf = io.BytesIO()
    fits.PrimaryHDU(np.zeros((10, 10))).writeto(buf)
    with pytest.raises(ValueError):
        read_image(buf.getvalue())


def test_spherex_epoch_is_on_the_same_sigma_scale():
    rng = np.random.default_rng(3)
    st = 0.4 + rng.normal(0, 0.05, (59, 59))
    st[30, 30] = 50.0
    n = spherex_epoch(st)
    assert abs(np.median(n)) < 0.05 and n[30, 30] > 100


def test_select_epochs_keeps_2mass_allwise_w2_and_thins_neowise():
    ep = [dict(label="2MASS Ks", year=2000.4), dict(label="AllWISE W1", year=2010.5), dict(label="AllWISE W2", year=2010.5)]
    ep += [dict(label="NEOWISE W2", year=2014.0 + 0.5 * k) for k in range(21)]
    out = select_epochs(ep, max_neowise=6)
    labels = [e["label"] for e in out]
    assert labels[:2] == ["2MASS Ks", "AllWISE W2"] and "AllWISE W1" not in labels
    neo = [e["year"] for e in out if e["label"].startswith("NEOWISE")]
    assert len(neo) == 6 and neo[0] == 2014.0 and neo[-1] == 2024.0 and neo == sorted(neo)
