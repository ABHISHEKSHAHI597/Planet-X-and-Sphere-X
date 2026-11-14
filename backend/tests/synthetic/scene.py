"""Shared synthetic scene generator (workflow.md §8.1). Owner: I. Used by I and M. Seeded; nothing committed.

Two levels, with one set of declared assumptions:

A. On-grid frames (`visit`): frames already on the common north-up grid, for stack/cube/diff algebra.
  * PSF: circular Gaussian, point-sampled, FWHM 1.46 px (≈9.0″, band-6 PSF_FWHM).
  * LVF: λ varies along grid y only. Frame i puts row y at channel
        c = i + 0.5 + offset_ch + jitter_i + direction·(y − yc)/ch_px,  one channel = 12′ = 117 px.
    Rows with c outside [0, 17) fall off the detector: NaN λ, no data. direction = −1 models the PA 180°
    flip (gradient reversed on the sky); offset_ch = 0.5 the Survey 3/4 half-channel shift.

B. Native frames (`native_visit`): real-format RawFrames (IMAGE/FLAGS/VARIANCE/ZODI headers and data)
   that go through the real pipeline: calibrate → reproject → stack/cube/diff.
  * Detector: 2040², CWAVE per detector = LVF along parent y with a 0.2-channel "smile" in x
    (`SynthCalib`), DETCOORD 'sky'. One channel = 2040/17 = 120 parent rows.
  * Pointing: frame i of a visit places the target at channel i + 0.5 + offset_ch (+ jitter) and at a
    dithered parent x. PA 0: +y north, +x west; PA 180: rotated 180° (LVF gradient reversed on the sky).
    A 2nd-order SIP distortion (≈1 px at the detector edge) is centred on the detector.
  * Cutout: an IRSA-style cutout around the target with CRPIX1A/2A = 1 − origin (implementation.md §3.5).
  * PSF: Gaussian or an asymmetric 33×33 table ePSF oversampled ×5 (`table_epsf`), point-sampled at
    pixel centres; the table is in detector orientation, so it rotates on the sky with PA.
  * Spectrum: power law F(λ) = flux·(λ/λmin)^α evaluated at each pixel's own CWAVE.
  * Background: ZODI plane (level + gradient) added to IMAGE; IMAGE − ZODI has zero sky.
  * Noise: var = sky_var + model/gain; VARIANCE holds it.
  * Saturation: model > sat_nan → NaN with OVERFLOW|SUR_ERROR (early overflow); model > sat_flag →
    OVERFLOW only (ramp-fitted value kept); BLOOM/HALO footprint (r = 3 px) around NaN cores.
  * Flags header: MSKNnnnn/MSKMnnnn planes of understanding.md §4.4 minus SATELLITE_HALO (as in R7 7.0.5).
    SOURCE footprint (r = 2.5 px) at catalogue positions (`catalogued=True`).
  * Cosmic rays: single pixels +cr_amp, half of them flagged TRANSIENT.
  * Variables: per-visit `Star.flux` (callers scale it). Movers: per-visit star positions.
  * Partial visits: `visit_mjds` makes clusters with given frame counts and gaps.
Not modelled: persistence, ghosts, crosstalk, bloom trails, PSF variation across the detector.
"""
import warnings
from dataclasses import dataclass, replace

import numpy as np
from astropy.io import fits
from astropy.wcs import WCS
from scipy.ndimage import map_coordinates

from spherex.constants import BANDS, PIXEL_ARCSEC
from spherex.constants import CHANNELS_PER_DETECTOR as NCH
from spherex.cube import CH_LN
from spherex.flags import CANONICAL_BITS
from spherex.types import FrameRef, RawFrame

FWHM_PX = 1.46
CH_PX = 12 * 60 / 6.15
DET = 2040


@dataclass(frozen=True)
class Star:
    x: float             # on-grid scenes: grid px; native scenes: RA (deg)
    y: float             # on-grid scenes: grid px; native scenes: Dec (deg)
    flux: float          # total flux at λmin (image units × pixels)
    alpha: float = 0.0   # power-law index in λ
    catalogued: bool = True


def steep(band, factor):
    lo, hi, _ = BANDS[band]
    return np.log(factor) / np.log(hi / lo)


# ---------------------------------------------------------------- A. on-grid frames
def lvf_lambda(shape, band, i, direction=1, offset_ch=0.0, jitter=0.0):
    lo, _, _ = BANDS[band]
    ny, nx = shape
    yy = np.broadcast_to(np.arange(ny, dtype=float)[:, None], shape)
    c = i + 0.5 + offset_ch + jitter + direction * (yy - (ny - 1) / 2) / CH_PX
    return np.where((c >= 0) & (c < NCH), lo * np.exp(c * CH_LN[band]), np.nan)


def model_image(shape, stars, lam, band, fwhm=FWHM_PX):
    lo = BANDS[band][0]
    s = fwhm / 2.3548
    yy, xx = np.indices(shape, dtype=float)
    img = np.zeros(shape)
    for st in stars:
        psf = np.exp(-((xx - st.x) ** 2 + (yy - st.y) ** 2) / (2 * s * s)) / (2 * np.pi * s * s)
        img += st.flux * (lam / lo) ** st.alpha * psf
    return img


def visit(shape, stars, band, rng, nframes=NCH, direction=1, offset_ch=0.0, jitter_ch=0.0,
          sky_var=1.0, gain=100.0, sat=None, n_cr=0, cr_amp=50.0):
    """Returns frames, var, lam (each (n, ny, nx)) and the noiseless models."""
    F, V, L, M = [], [], [], []
    for i in range(nframes):
        lam = lvf_lambda(shape, band, i, direction, offset_ch, rng.uniform(-jitter_ch, jitter_ch))
        m = model_image(shape, stars, lam, band)
        var = sky_var + np.maximum(np.nan_to_num(m), 0) / gain
        f = m + rng.normal(size=shape) * np.sqrt(var)          # NaN off the detector
        if sat is not None:
            f[m > sat] = np.nan
        F.append(f); V.append(var); L.append(lam); M.append(m)
    F = np.array(F)
    for _ in range(n_cr):
        k, y, x = rng.integers(nframes), rng.integers(shape[0]), rng.integers(shape[1])
        F[k, y, x] += cr_amp
    return F, np.array(V), np.array(L), np.array(M)


def shifted(stars, index, dx, dy):
    """The same star list with one star moved (a mover between visits)."""
    out = list(stars)
    out[index] = replace(out[index], x=out[index].x + dx, y=out[index].y + dy)
    return out


def sky_mask(shape, stars, r=5.0):
    yy, xx = np.indices(shape, dtype=float)
    m = np.ones(shape, bool)
    for st in stars:
        m &= np.hypot(xx - st.x, yy - st.y) > r
    return m


# ---------------------------------------------------------------- B. native frames
def cwave_map(band, smile_ch=0.2):
    """Synthetic CWAVE (µm) of one detector, parent pixels, DETCOORD 'sky'."""
    lo, _, _ = BANDS[band]
    yy, xx = np.mgrid[0:DET, 0:DET].astype(float)
    c = (NCH - smile_ch) * (yy + 0.5) / DET + smile_ch * ((xx - (DET - 1) / 2) / (DET / 2)) ** 2
    return lo * np.exp(c * CH_LN[band])


def channel_of(band, lam):
    lo, _, _ = BANDS[band]
    return np.floor(np.log(lam / lo) / CH_LN[band]).astype(int) + 1


class SynthCalib:
    """Calib (types.Calib) for synthetic detectors: CWAVE, CBAND = λ/R, CHANNEL_MAP, flux corrections."""
    def __init__(self, bands=(1, 2, 3, 4, 5, 6), fluxcorr=1.0):
        self.cwave = {b: cwave_map(b) for b in bands}
        self.cband = {b: self.cwave[b] / BANDS[b][2] for b in bands}
        self.channel = channel_of(bands[0], self.cwave[bands[0]]).astype(np.uint8)
        self.fluxcorr = {b: np.full((DET, DET), fluxcorr) for b in bands}


def table_epsf(fwhm_px=FWHM_PX, os=5, size=33, ellip=0.25, coma=0.15):
    """An ePSF-like table: elliptical Gaussian core plus an offset wing (asymmetric, so a 180° rotation
    changes it), oversampled ×os; normalised so it sums to os² (unit flux at native sampling)."""
    c = (size - 1) / 2
    yy, xx = (np.mgrid[0:size, 0:size] - c) / os
    s = fwhm_px / 2.3548
    core = np.exp(-(xx ** 2 / (2 * (s * (1 + ellip)) ** 2) + yy ** 2 / (2 * (s / (1 + ellip)) ** 2)))
    wing = coma * np.exp(-((xx - 0.6 * s) ** 2 + (yy + 0.4 * s) ** 2) / (2 * (1.8 * s) ** 2))
    t = core + wing
    return t / t.sum() * os ** 2


def epsf_bintable(table, band):
    """The table in the layout of a QR3 EPSF HDU (implementation.md §4.7): 21×21 zones of one PSF."""
    g = np.linspace(48.5, DET - 48.5, 21)
    yc, xc = (a.ravel() for a in np.meshgrid(g, g, indexing="ij"))
    lam = cwave_map(band)[yc.astype(int), xc.astype(int)]
    return dict(XCENTER=xc, YCENTER=yc, CWAVE=lam, CBAND=lam / BANDS[band][2],
                EPSF=np.repeat(table[None], xc.size, axis=0))


def _psf_sample(dx, dy, fwhm_px, table, os=5):
    """PSF at pixel offsets (dx, dy) from the source, unit total flux at native sampling."""
    if table is None:
        s = fwhm_px / 2.3548
        return np.exp(-(dx ** 2 + dy ** 2) / (2 * s * s)) / (2 * np.pi * s * s)
    c = (table.shape[-1] - 1) / 2
    return map_coordinates(table, [c + os * dy, c + os * dx], order=3, mode="grid-constant", cval=0.0) / os ** 2


SIP = dict(A_2_0=2.0e-7, A_1_1=-1.0e-7, A_0_2=1.5e-7, B_2_0=-1.0e-7, B_1_1=2.0e-7, B_0_2=1.0e-7)


def detector_wcs(ra, dec, xp, yp, pa=0.0, rot_deg=0.0, sip=True):
    """Full-detector TAN(-SIP) WCS, CRPIX at the detector centre, that puts (ra, dec) at parent pixel
    (xp, yp) (0-based). PA 0: +y north, +x west (CD = diag(−s, s)); PA 180 rotates by 180°."""
    s = PIXEL_ARCSEC / 3600
    th = np.radians(pa + rot_deg)
    cd = np.array([[-s * np.cos(th), s * np.sin(th)], [s * np.sin(th), s * np.cos(th)]])
    h = fits.Header()
    h["CTYPE1"], h["CTYPE2"] = ("RA---TAN-SIP", "DEC--TAN-SIP") if sip else ("RA---TAN", "DEC--TAN")
    h["CRPIX1"], h["CRPIX2"] = (DET + 1) / 2, (DET + 1) / 2
    h["CRVAL1"], h["CRVAL2"] = ra, dec
    for (i, j), v in np.ndenumerate(cd):
        h[f"CD{i + 1}_{j + 1}"] = v
    if sip:
        h["A_ORDER"] = h["B_ORDER"] = 2
        for k, v in SIP.items():
            h[k] = v
    w = WCS(h)
    for _ in range(4):                                       # move CRVAL until (xp, yp) → (ra, dec)
        r0, d0 = w.wcs_pix2world([[xp, yp]], 0)[0] if not sip else w.all_pix2world([[xp, yp]], 0)[0]
        h["CRVAL1"] += (ra - r0)
        h["CRVAL2"] += (dec - d0)
        w = WCS(h)
    return w, h


def _flags_header():
    h = fits.Header()
    for name, b in CANONICAL_BITS.items():
        if name != "SATELLITE_HALO":
            h[f"MSKN{b:04d}"] = name
            h[f"MSKM{b:04d}"] = 1 << b
    return h


def native_frame(stars, band, rng, ra0, dec0, ch_pos, xp=None, pa=0.0, rot_deg=0.0, size=61, mjd=61000.0,
                 sky_var=1.0, gain=100.0, zodi=(5.0, 0.01), table=None, fwhm_px=FWHM_PX, sat_flag=None,
                 sat_nan=None, n_cr=0, cr_amp=60.0, calib=None, obsid="SYNTH_0001_1", finast=0, sip=True,
                 release="qr3"):
    """One IRSA-style cutout RawFrame with the target (ra0, dec0) at channel position ch_pos (0..17)."""
    calib = calib or SynthCalib((band,))
    yp = ch_pos / NCH * DET
    xp = DET / 2 + rng.uniform(-60, 60) if xp is None else xp
    w_full, h_full = detector_wcs(ra0, dec0, xp, yp, pa, rot_deg, sip)
    x0, y0 = int(round(xp)) - size // 2, int(round(yp)) - size // 2
    x0, y0 = min(max(x0, 0), DET - size), min(max(y0, 0), DET - size)
    w = w_full.slice((slice(y0, y0 + size), slice(x0, x0 + size)))
    yy, xx = np.mgrid[0:size, 0:size].astype(float)
    lam = calib.cwave[band][y0:y0 + size, x0:x0 + size]
    lo = BANDS[band][0]
    model = np.zeros((size, size))
    src = np.zeros((size, size), bool)
    for st in stars:
        sx, sy = w.all_world2pix([[st.x, st.y]], 0)[0]
        if -10 < sx < size + 10 and -10 < sy < size + 10:
            model += st.flux * (lam / lo) ** st.alpha * _psf_sample(xx - sx, yy - sy, fwhm_px, table)
            if st.catalogued:
                src |= np.hypot(xx - sx, yy - sy) <= 2.5
    var = sky_var + np.maximum(model, 0) / gain
    z = zodi[0] + zodi[1] * (yy - size / 2)
    img = model + z + rng.normal(size=model.shape) * np.sqrt(var)
    flg = np.zeros((size, size), np.int64)
    bit = lambda n: 1 << CANONICAL_BITS[n]
    flg[src] |= bit("SOURCE")
    if sat_flag is not None:
        flg[model > sat_flag] |= bit("OVERFLOW")
    if sat_nan is not None:
        core = model > sat_nan
        img[core] = np.nan
        flg[core] |= bit("OVERFLOW") | bit("SUR_ERROR")
        if core.any():
            cy, cx = np.argwhere(core).mean(axis=0)
            flg[(np.hypot(xx - cx, yy - cy) <= 3.0) & ~core] |= bit("BLOOM") | bit("HALO")
    for k in range(n_cr):
        y, x = rng.integers(size), rng.integers(size)
        img[y, x] += cr_amp
        if k % 2 == 0:
            flg[y, x] |= bit("TRANSIENT")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", fits.verify.VerifyWarning)   # OMEGA_MEDIAN is HIERARCH, as in real files
        hi = w.to_header(relax=True)
        hi["OMEGA_MEDIAN"] = 37.94
    hi["EXTNAME"] = "IMAGE"
    hi["CRPIX1A"], hi["CRPIX2A"] = 1 - x0, 1 - y0          # IRSA cutout convention
    hi.update(DETECTOR=band, OBSID=obsid, **{"MJD-AVG": mjd}, SPS_EPA=float(pa), FINAST=finast,
              L1DQAFLG="Pass", L2DQAFLG="Pass", PSF_FWHM=fwhm_px * PIXEL_ARCSEC)
    hf = _flags_header()
    hdus = {"IMAGE": (hi, img.astype(np.float32)), "FLAGS": (hf, flg), "VARIANCE": (fits.Header(), var.astype(np.float32)),
            "ZODI": (fits.Header(), z.astype(np.float32))}
    ref = FrameRef(access_url=f"synthetic://{obsid}D{band}", s3_key=f"synthetic/{obsid}D{band}.fits",
                   collection=f"spherex_{release}", obs_id=obsid, detector=band, t_min=mjd)
    return RawFrame(hdus=hdus, wcs=WCS(hi), origin=(x0, y0), ref=ref, release=release), model


def native_visit(stars, band, rng, ra0, dec0, nframes=NCH, pa=0.0, offset_ch=0.0, jitter_ch=0.1,
                 mjd0=61000.0, visit_tag="A", **kw):
    """One visit of one band: nframes frames stepping the target through the channels (PA, survey
    half-channel offset and dithers as declared above). Returns (RawFrames, noiseless models)."""
    frames, models = [], []
    for i in range(nframes):
        ch = (i % NCH) + 0.5 + offset_ch + rng.uniform(-jitter_ch, jitter_ch)
        ch = min(max(ch, 0.05), NCH - 0.05)
        f, m = native_frame(stars, band, rng, ra0, dec0, ch, pa=pa, mjd=mjd0 + 0.7 * i,
                            obsid=f"SYNTH{visit_tag}_{i:04d}_1", rot_deg=rng.uniform(-1.0, 1.0), **kw)
        frames.append(f); models.append(m)
    return frames, models


def field(ra0, dec0, rng, n=12, radius_deg=0.05, flux=(20.0, 200.0), alpha=0.0):
    """Random static field stars around (ra0, dec0)."""
    r = radius_deg * np.sqrt(rng.uniform(0, 1, n))
    t = rng.uniform(0, 2 * np.pi, n)
    return [Star(ra0 + r[k] * np.cos(t[k]) / np.cos(np.radians(dec0)), dec0 + r[k] * np.sin(t[k]),
                 float(rng.uniform(*flux)), alpha) for k in range(n)]


def visit_mjds(counts_per_cluster, starts, band=6, partner=3, spacing_days=0.6):
    """Frame MJDs and detectors for a band and its co-aligned partner: cluster k has counts[k] frames
    starting at starts[k] (partial visits are clusters with < 10 frames)."""
    mjd, det = [], []
    for n, t0 in zip(counts_per_cluster, starts):
        t = t0 + spacing_days * np.arange(n)
        mjd += list(t) * 2
        det += [band] * n + [partner] * n
    return np.array(mjd), np.array(det)


def pipeline(frames, calib, grid, preset="discovery", **kw):
    """The real Role I chain on RawFrames: calibrate → QA → reproject. Returns (GridFrames, skipped)."""
    from spherex.grid import frame_to_grid
    from spherex.preprocess import calibrate
    out, skipped = [], []
    for f in frames:
        cf = calibrate(f, calib, preset, **kw)
        if not cf.qa["ok"]:
            skipped.append((f.ref.id, ";".join(cf.qa["reasons"])))
            continue
        out.append(frame_to_grid(cf, grid))
    return out, skipped
