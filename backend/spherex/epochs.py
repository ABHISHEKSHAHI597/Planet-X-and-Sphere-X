"""Time model: visits, partial visits, surveys and bins (implementation.md §4.2)."""

from collections.abc import Sequence
from typing import TYPE_CHECKING, Any

from numpy.typing import ArrayLike, NDArray

if TYPE_CHECKING:
    from .types import TimeBin

import numpy as np

A = NDArray[Any]

SCIENCE_START_MJD = 60796.0          # 2025-05-01
HALF_MISSION_DAYS = 12.5 * 30.4375   # Surveys 1/2 vs 3/4 split (Supplement §2.2) → 2026-05-16
FULL_MIN_FRAMES = 10                 # a visit is full in a band when its detector has ≥ 10 frames
# A visit lasts ≈1–3 weeks (understanding.md §0.3). A partial cluster merges into a full neighbour only
# if the merged visit still spans ≤ 3 weeks. implementation.md §4.2 says "neighbour ≤ 45 d away", but
# that would merge WISE 0855's Dec 2025 cluster (27 d after the Nov visit) and contradict the verified
# "2 full + 2 partial" outcome both documents state. The verified outcome wins; see docs/decisions.
MAX_VISIT_SPAN_DAYS = 21.0


def survey_number(mjd: float, sps_epa: float) -> int | None:
    if mjd < SCIENCE_START_MJD:
        return None                                   # commissioning (IOC) frames
    pa180 = abs(((sps_epa + 180.0) % 360.0) - 180.0) > 90.0
    second_year = (mjd - SCIENCE_START_MJD) > HALF_MISSION_DAYS
    return (3 if second_year else 1) + (1 if pa180 else 0)


def cluster_visits(mjd: ArrayLike, gap_days: float = 20.0) -> A:
    mjd = np.asarray(mjd, float)
    if mjd.size == 0:
        return np.empty(0, int)
    order = np.argsort(mjd)
    lab = np.empty(mjd.size, int)
    lab[order] = np.r_[0, np.cumsum(np.diff(mjd[order]) > gap_days)]
    return lab


# implementation.md §4.2 used 45 d. Real ε Ind B visits (β = −41.5°) span 46.3 and 44.9 d with their
# tails, so 45 d turned ε Ind B into 14-day bins; R Dra's shortest cluster spans 88.7 d. See
# docs/decisions/0002-time-axis-threshold.md.
MAX_VISIT_CLUSTER_DAYS = 60.0


# Dense revisits (decision 0002, amended 2026-11-10): more than this many substantial clusters per year of
# baseline means visits can no longer be told apart. A "substantial" cluster has ≥ 2 × FULL_MIN_FRAMES frames,
# i.e. a full visit on at least one detector pair; 2–30-frame partial clusters never count.
MAX_VISITS_PER_YEAR = 4.0


def choose_axis(mjd: ArrayLike, lab: A) -> str:
    """Fixed bins for dense coverage. Continuous coverage (R Dra) forms ONE long cluster, so the span rule
    catches it. The earlier "more than 6 clusters" rule counted every partial cluster, so an ordinary target
    switched to 14-day bins as the mission went on (Barnard's Star already had 6; audit B-02). Now: bins when a
    cluster spans more than MAX_VISIT_CLUSTER_DAYS, or when substantial clusters recur faster than
    MAX_VISITS_PER_YEAR (≈ 2 a year is the normal survey cadence)."""
    mjd = np.asarray(mjd, float)
    if mjd.size == 0:
        return "visit"
    ks = np.unique(lab)
    spans = np.array([np.ptp(mjd[lab == k]) for k in ks])
    if spans.max() > MAX_VISIT_CLUSTER_DAYS:
        return "bin:14d"
    big = np.array([mjd[lab == k].mean() for k in ks if (lab == k).sum() >= 2 * FULL_MIN_FRAMES])
    if big.size >= 3:
        years = (big.max() - big.min()) / 365.25
        if years > 0 and (big.size - 1) / years > MAX_VISITS_PER_YEAR:
            return "bin:14d"
    return "visit"


def fixed_bins(mjd: ArrayLike, width_days: float) -> A:
    mjd = np.asarray(mjd, float)
    if mjd.size == 0:
        return np.empty(0, int)
    return np.floor((mjd - mjd.min()) / width_days).astype(int)


def classify_visits(mjd: ArrayLike, band: ArrayLike, gap_days: float = 20.0, full_min: int = FULL_MIN_FRAMES,
                    max_span: float = MAX_VISIT_SPAN_DAYS) -> tuple[A, dict[Any, list[dict[str, Any]]]]:
    """Visits per band, each labelled full or partial.
    Clusters are found on all frames (so V1, V2… mean the same dates in every band). Per band, a
    cluster with < full_min frames is merged into its nearest full neighbour when the merged visit
    spans ≤ max_span days, otherwise kept as a partial visit.
    Returns (cluster label per frame, {band: [visit dict, … in time order]}). Each visit dict has
    clusters, idx (frame indices), n, status, mjd_mean, mjd_min, mjd_max."""
    mjd, band = np.asarray(mjd, float), np.asarray(band)
    lab = cluster_visits(mjd, gap_days)
    out = {}
    for b in np.unique(band):
        inb = band == b
        groups = [[k] for k in np.unique(lab[inb])]            # cluster ids are in time order
        def idx(g: list[int], inb: Any = inb) -> A:
            return np.flatnonzero(inb & np.isin(lab, g))
        full = [idx(g).size >= full_min for g in groups]
        merged = True
        while merged:                                          # merge one partial at a time
            merged = False
            for i, g in enumerate(groups):
                if full[i]:
                    continue
                best = None
                for j in (i - 1, i + 1):
                    if 0 <= j < len(groups) and full[j]:
                        t = mjd[idx(g + groups[j])]
                        if np.ptp(t) <= max_span and (best is None or np.ptp(t) < best[1]):
                            best = (j, np.ptp(t))
                if best is not None:
                    j = best[0]
                    groups[j] = sorted(groups[j] + g)
                    del groups[i], full[i]
                    merged = True
                    break
        visits = []
        for g in groups:
            ii = idx(g)
            t = mjd[ii]
            visits.append(dict(clusters=g, idx=ii, n=int(ii.size),
                               status="full" if ii.size >= full_min else "partial",
                               mjd_mean=float(t.mean()), mjd_min=float(t.min()), mjd_max=float(t.max())))
        out[b.item() if hasattr(b, "item") else b] = visits
    return lab, out


def _date(mjd: float) -> str:
    from astropy.time import Time
    return Time(mjd, format="mjd").to_value("iso", subfmt="date")


def date_range(mjd_min: float, mjd_max: float) -> str:
    """'2025-05-05/06', '2026-03-11→04-10', '2025-12-28→2026-01-09' or a single date."""
    a, b = _date(mjd_min), _date(mjd_max)
    if a == b:
        return a
    if a[:7] == b[:7]:
        return f"{a}/{b[8:]}"
    if a[:4] == b[:4]:
        return f"{a}→{b[5:]}"
    return f"{a}→{b}"


def _surveys_label(surveys: Sequence[int | None]) -> str:
    """None = IOC (commissioning), 0 = unknown (no header PA yet)."""
    parts = [f"S{x}" for x in sorted({x for x in surveys if x})]
    parts += ["S?"] * (0 in surveys) + ["IOC"] * (None in surveys)
    return "+".join(parts)


def label(bin_id: str, status: str, mjd_min: float, mjd_max: float, surveys: Sequence[int | None], n_band: int,
          band: int, n_visit: int = 0) -> str:
    """implementation.md §4.2 labels: `V2 · 2026-03-11→04-10 · S1 · 113 frames` (full visits count every
    band's frames of the visit) or `V1 · 2025-05-05/06 · S1 · partial (3 in band 6)`."""
    head = f"{bin_id} · {date_range(mjd_min, mjd_max)} · {_surveys_label(surveys)}"
    if status == "partial":
        return f"{head} · partial ({n_band} in band {band})"
    return f"{head} · {n_visit or n_band} frames"


def time_bins(mjd: ArrayLike, band: ArrayLike, axis: str = "visit", surveys: Sequence[int | None] | None = None,
              gap_days: float = 20.0, width_days: float = 14.0) -> "dict[int, list[TimeBin]]":
    """The time axis of a view, per band (I -> P). axis: visit | bin:<N>d | survey | exposure | auto.
    surveys: per-frame survey number from epochs.survey_number on each frame's header (None = IOC);
    if omitted, IOC frames are still tagged from their date and the rest show "S?".
    Returns {band: [types.TimeBin, …in time order]}."""
    from .types import TimeBin
    mjd, band = np.asarray(mjd, float), np.asarray(band)
    surveys = list(surveys) if surveys is not None else [None if t < SCIENCE_START_MJD else 0 for t in mjd]
    sv = np.array([-1 if s is None else s for s in surveys])
    lab = cluster_visits(mjd, gap_days)
    if axis == "auto":
        axis = choose_axis(mjd, lab)
    out = {}

    def mk(bid: str, b: Any, ii: A, status: Any, n_visit: int = 0) -> "TimeBin":
        t = mjd[ii]
        ss = tuple(sorted({None if sv[i] < 0 else int(sv[i]) for i in ii}, key=lambda x: -1 if x is None else x))
        return TimeBin(id=bid, band=int(b), idx=np.asarray(ii, np.int64), status=status,
                       mjd_mean=float(t.mean()), mjd_min=float(t.min()), mjd_max=float(t.max()),
                       surveys=ss, label=label(bid, status, t.min(), t.max(), ss, ii.size, int(b), n_visit),
                       n_visit_frames=n_visit)

    if axis == "visit":
        _, vis = classify_visits(mjd, band, gap_days)
        for b, vs in vis.items():
            bins = []
            for v in vs:
                anchor = max(v["clusters"], key=lambda c: ((lab == c) & (band == b)).sum())
                n_visit = int(np.isin(lab, v["clusters"]).sum())
                bins.append(mk(f"V{anchor + 1}", b, v["idx"], v["status"], n_visit))
            out[int(b)] = bins
    elif axis.startswith("bin:"):
        width = float(axis[4:].rstrip("d"))
        k = fixed_bins(mjd, width)
        for b in np.unique(band):
            out[int(b)] = [mk(f"B{j}", b, np.flatnonzero((k == j) & (band == b)), "bin")
                           for j in np.unique(k[band == b])]
    elif axis == "survey":
        for b in np.unique(band):
            out[int(b)] = [mk("IOC" if s < 0 else ("S?" if s == 0 else f"S{s}"), b, np.flatnonzero((sv == s) & (band == b)), "survey")
                           for s in np.unique(sv[band == b])]
    elif axis == "exposure":
        for b in np.unique(band):
            ii = np.flatnonzero(band == b)
            out[int(b)] = [mk(f"E{j}", b, np.array([i]), "exposure") for j, i in enumerate(ii[np.argsort(mjd[ii])])]
    else:
        raise ValueError(f"unknown axis {axis!r}")
    return out
