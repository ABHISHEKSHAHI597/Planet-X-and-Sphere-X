"""Experimental joint native-pixel visit centroid, with registration nuisance terms.

Shared sky offset; independent nonnegative target/neighbour fluxes and free sky
per exposure. No coadd, interpolation of science images or fixed spectral shape.
"""

from dataclasses import dataclass
from typing import Any

import numpy as np
from scipy import sparse
from scipy.optimize import least_squares, nnls

from .epsf import EPSF


@dataclass
class JointFrame:
    image: Any
    variance: Any
    bad: Any
    epsf: EPSF
    positions: Any
    zones: tuple[int, int]
    sky_to_pixel: Any
    registration_error: Any


def prepare_frame(
    cf: Any, psf: EPSF, target: tuple[float, float], neighbour: tuple[float, float], registration: dict[str, Any]
) -> JointFrame:
    """Map sky offsets to this frame's native pixels; retain registration uncertainty."""
    from astropy import units as u
    from astropy.coordinates import SkyCoord

    offset = registration["offset"]

    def shifted(position: tuple[float, float]) -> Any:
        return SkyCoord(position[0] * u.deg, position[1] * u.deg).spherical_offsets_by(
            offset[0] * u.arcsec, offset[1] * u.arcsec
        )

    centre, other = shifted(target), shifted(neighbour)
    x, y = map(float, cf.wcs.world_to_pixel(centre))
    nx, ny = map(float, cf.wcs.world_to_pixel(other))
    transform = np.empty((2, 2))
    for col, (dx, dy) in enumerate(((0.01, 0), (0, 0.01))):
        sky = centre.spherical_offsets_by(dx * u.arcsec, dy * u.arcsec)
        transform[:, col] = (np.asarray(cf.wcs.world_to_pixel(sky)) - [x, y]) / 0.01
    zones = psf.zone(x + cf.origin[0], y + cf.origin[1]), psf.zone(nx + cf.origin[0], ny + cf.origin[1])
    bad = cf.bad_phot | ((cf.flags & cf.bits.get("OVERFLOW", 0)) != 0)
    ix, iy = np.rint(np.mean([[x, y], [nx, ny]], axis=0)).astype(int)
    if ix < 4 or iy < 4 or ix + 4 >= cf.sci.shape[1] or iy + 4 >= cf.sci.shape[0]:
        raise ValueError("joint native stamp clipped")
    sl = np.s_[iy - 4 : iy + 5, ix - 4 : ix + 5]
    positions = np.array([[x, y], [nx, ny]]) - [ix - 4, iy - 4]
    return JointFrame(
        cf.sci[sl].copy(), cf.var[sl].copy(), bad[sl].copy(), psf, positions, zones, transform, registration["error"]
    )


def fit_visit(frames: list[JointFrame], max_shift_arcsec: float = 9.225) -> dict[str, Any]:
    """Profile per-frame flux/sky; fit a shared centroid and uncertain translations.

    Nonnegative fluxes prevent an artificial positive/negative coincident-source
    cancellation. Registration shifts are Gaussian nuisances, not exact values.
    Returned Hessian covariance remains conditional on the PSF and likelihood.
    """
    if len(frames) < 2 or max_shift_arcsec <= 0:
        raise ValueError("at least two native frames and positive search bound required")
    prepared = []
    sizes = []
    for frame in frames:
        pos = np.asarray(frame.positions, float)
        transform = np.asarray(frame.sky_to_pixel, float)
        error = np.asarray(frame.registration_error, float)
        if pos.shape != (2, 2) or transform.shape != (2, 2) or error.shape != (2,) or np.any(error <= 0):
            raise ValueError("two positions, sky/pixel transform and positive registration errors required")
        if not all(np.all(np.isfinite(v)) for v in [pos, transform, error]):
            raise ValueError("finite geometry required")
        ix, iy = np.rint(pos.mean(axis=0)).astype(int)
        half = 4
        if ix - half < 0 or iy - half < 0 or ix + half >= frame.image.shape[1] or iy + half >= frame.image.shape[0]:
            raise ValueError("joint native stamp clipped")
        sl = np.s_[iy - half : iy + half + 1, ix - half : ix + half + 1]
        yy, xx = np.mgrid[iy - half : iy + half + 1, ix - half : ix + half + 1]
        data, var = np.asarray(frame.image[sl], float), np.asarray(frame.variance[sl], float)
        ok = ~frame.bad[sl] & np.isfinite(data) & np.isfinite(var) & (var > 0)
        if ok.sum() < 8:
            raise ValueError("fewer than eight valid joint-stamp pixels")
        weight = 1 / np.sqrt(var[ok])
        background = weight / np.linalg.norm(weight)
        values = data[ok] * weight
        projected = values - background * (background @ values)
        prepared.append((frame, pos, transform, error, xx[ok], yy[ok], weight, background, values, projected))
        sizes.append(int(ok.sum()))

    n = len(frames)
    total = sum(sizes)
    pattern = sparse.lil_matrix((total + 2 * n, 2 + 2 * n), dtype=int)
    start = 0
    for j, size in enumerate(sizes):
        pattern[start : start + size, :2] = 1
        pattern[start : start + size, 2 + 2 * j : 4 + 2 * j] = 1
        pattern[total + 2 * j : total + 2 * j + 2, 2 + 2 * j : 4 + 2 * j] = 1
        start += size

    def residual(parameters: Any, return_flux: bool = False) -> Any:
        parts, fluxes = [], []
        for j, (frame, pos, transform, _error, xx, yy, weight, background, values, projected) in enumerate(prepared):
            translation = transform @ parameters[2 + 2 * j : 4 + 2 * j]
            target = pos[0] + translation + transform @ parameters[:2]
            neighbour = pos[1] + translation
            design = np.column_stack(
                [
                    frame.epsf.sample(z, xx - xy[0], yy - xy[1]) * weight
                    for xy, z in zip([target, neighbour], frame.zones, strict=True)
                ]
            )
            reduced = design - background[:, None] * (background @ design)
            flux, _ = nnls(reduced, projected)
            raw = values - design @ flux
            parts.append(raw - background * (background @ raw))
            fluxes.append(flux)
        for j, frame in enumerate(frames):
            parts.append(parameters[2 + 2 * j : 4 + 2 * j] / np.asarray(frame.registration_error))
        return fluxes if return_flux else np.concatenate(parts)

    lower, upper = np.full(2 + 2 * n, -np.inf), np.full(2 + 2 * n, np.inf)
    lower[:2], upper[:2] = -max_shift_arcsec, max_shift_arcsec
    alias = np.median([np.linalg.solve(v[2], v[1][1] - v[1][0]) for v in prepared], axis=0)
    solutions = []
    for start_offset in [np.zeros(2), 0.5 * alias, -0.5 * alias]:
        x_start = np.zeros(2 + 2 * n)
        x_start[:2] = np.clip(start_offset, -0.9 * max_shift_arcsec, 0.9 * max_shift_arcsec)
        candidate = least_squares(
            residual,
            x_start,
            bounds=(lower, upper),
            jac_sparsity=pattern.tocsr(),
            ftol=1e-9,
            xtol=1e-9,
            gtol=1e-9,
            max_nfev=300,
        )
        if candidate.success and not np.any(candidate.active_mask[:2]):
            solutions.append(candidate)
    if not solutions:
        raise ValueError("joint position is unconstrained or at search boundary")
    result = min(solutions, key=lambda p: p.cost)
    jac = result.jac.toarray()
    _, singular, right = np.linalg.svd(jac, full_matrices=False)
    if singular[-1] <= singular[0] * 1e-10:
        raise ValueError("rank-deficient joint centroid")
    dof = total - 3 * n - 2  # per-frame target/neighbor amplitudes and sky profiled out
    chi2 = float(result.fun @ result.fun)
    covariance = ((right.T / singular**2) @ right) * max(1.0, chi2 / dof)
    # A local Hessian cannot describe distinct competitive modes. Preserve a
    # failure instead of returning a narrow ellipse around just one mode.
    for candidate in solutions:
        delta = candidate.x[:2] - result.x[:2]
        if (
            2 * (candidate.cost - result.cost) <= 5.991464547
            and delta @ np.linalg.solve(covariance[:2, :2], delta) > 5.991464547
        ):
            raise ValueError("competitive separated joint-centroid modes; local covariance invalid")
    return dict(
        offset_arcsec=result.x[:2],
        covariance=covariance[:2, :2],
        chi2=chi2,
        dof=dof,
        registration_shifts=result.x[2:].reshape(n, 2),
        fluxes=np.asarray(residual(result.x, True)),
        n_frames=n,
        start_solutions=[dict(offset_arcsec=p.x[:2], chi2=float(p.fun @ p.fun)) for p in solutions],
        method="joint native pixel likelihood; nonnegative frame fluxes; Gaussian registration nuisances; conditional PSF/Hessian covariance",
    )
