"""L2/L3: time model on real MJDs (G1). Fixtures: tests/data/real/{wise0855,rdra}_mjd.json (SIA2 t_min) and
tests/data/real/frames_5targets.json (IMAGE headers of every frame of the 5 targets; see provenance)."""
import json
from pathlib import Path

import numpy as np

from spherex.epochs import (
    FULL_MIN_FRAMES,
    choose_axis,
    classify_visits,
    cluster_visits,
    fixed_bins,
    survey_number,
    time_bins,
)

D = Path(__file__).parents[1] / "data/real"


def _load(name):
    rows = json.loads((D / f"{name}_mjd.json").read_text())["rows"]
    return np.array([r[0] for r in rows]), np.array([r[1] for r in rows])


def _frames(target):
    d = json.loads((D / "frames_5targets.json").read_text())
    c = {k: i for i, k in enumerate(d["columns"])}
    R = [r for r in d["rows"] if r[c["target"]] == target]
    mjd = np.array([r[c["MJD-AVG"]] for r in R])
    det = np.array([r[c["DETECTOR"]] for r in R])
    sv = [survey_number(m, r[c["SPS_EPA"]]) for m, r in zip(mjd, R)]
    return mjd, det, sv


def test_real_wise0855_two_full_two_partial_in_band6():
    mjd, det = _load("wise0855")
    lab, visits = classify_visits(mjd, det)
    b6 = visits[6]
    assert [v["n"] for v in b6] == [3, 16, 3, 21]
    assert [v["status"] for v in b6] == ["partial", "full", "partial", "full"]
    assert choose_axis(mjd, lab) == "visit"


def test_real_partial_merge_rule_teeth():
    """Teeth (workflow.md §4.2): the documented "merge a partial into a full neighbour ≤ 45 d away" rule
    merges WISE 0855's Dec 2025 cluster and loses the verified 2 full + 2 partial outcome."""
    mjd, det = _load("wise0855")
    lab = cluster_visits(mjd)
    groups = [mjd[(lab == k) & (det == 6)] for k in np.unique(lab)]
    full = [g.size >= FULL_MIN_FRAMES for g in groups]
    naive = [g.size for g in groups]
    for i, g in enumerate(groups):                              # the documented 45-d neighbour rule
        near = [j for j in (i - 1, i + 1) if 0 <= j < len(groups) and full[j]
                and min(abs(groups[j].min() - g.max()), abs(g.min() - groups[j].max())) <= 45.0]
        if not full[i] and near:
            naive[near[0]] += naive[i]; naive[i] = 0
    assert [n for n in naive if n] == [3, 19, 21]               # Dec cluster wrongly merged into Nov


def test_real_rdra_uses_fixed_bins_and_counts_occupied_bins():
    mjd, det = _load("rdra")
    assert choose_axis(mjd, cluster_visits(mjd)) == "bin:14d"
    k = fixed_bins(mjd, 14.0)
    occupied = {b: np.unique(k[det == b]).size for b in range(1, 7)}
    # implementation.md §10.2 asks for ≥ 20 14-day bins for the periodogram. Real coverage gives 16 in
    # bands 1, 3, 4, 6 and 6 in bands 2, 5 (deep-field geometry): reported to M for G5.lc.
    assert occupied == {1: 16, 2: 6, 3: 16, 4: 16, 5: 6, 6: 16}
    assert np.unique(k).size >= 20                               # all bands together: enough bins


def test_real_five_targets_axes_visits_and_surveys():
    """G1: every target's time axis on real headers. Barnard is S2 → S1 → S4 (understanding.md §3.3)."""
    expect_axis = {"barnard": "visit", "epsindb": "visit", "wise0855": "visit", "rwaur": "visit", "rdra": "bin:14d"}
    for t, ax in expect_axis.items():
        mjd, det, sv = _frames(t)
        assert choose_axis(mjd, cluster_visits(mjd)) == ax, t
        if ax == "visit":
            full = [b for b in time_bins(mjd, det, "visit", sv)[6] if b.status == "full"]
            assert len(full) >= 2, t                                 # P0-3: ≥ 2 full visits
    mjd, det, sv = _frames("barnard")
    b6 = [b for b in time_bins(mjd, det, "visit", sv)[6] if b.status == "full"]
    assert [b.surveys for b in b6] == [(2,), (1,), (4,)]
    assert [b.n_visit_frames for b in b6] == [109, 113, 117]       # understanding.md §3.4
    mjd, det, sv = _frames("wise0855")
    assert [b.status for b in time_bins(mjd, det, "visit", sv)[6]] == ["partial", "full", "partial", "full"]


def test_real_ioc_frames_are_tagged():
    mjd, det, sv = _frames("epsindb")
    assert sum(s is None for s in sv) == 66 and all(m < 60796.0 for m, s in zip(mjd, sv) if s is None)
    assert "IOC" in time_bins(mjd, det, "visit", sv)[6][0].label


def test_empty_input():
    assert cluster_visits([]).size == 0 and fixed_bins(np.array([]), 14).size == 0
    assert choose_axis(np.array([]), np.array([], int)) == "visit"
    assert classify_visits([], [])[1] == {}
    assert FULL_MIN_FRAMES == 10


def test_axis_is_stable_as_the_mission_adds_clusters():
    """Audit B-02: Barnard had exactly 6 clusters, and the old "> 6 clusters" rule turned it into 14-day bins with
    its next cluster. Adding future clusters (partial or full, every 180 d) must keep every visit target on visits,
    while dense revisits (a full visit every month) and R Dra's continuous coverage still get bins."""
    rng = np.random.default_rng(0)
    for t in ("barnard", "epsindb", "wise0855", "rwaur"):
        mjd, _, _ = _frames(t)
        for n_frames in (3, 110):
            m2 = mjd.copy()
            for _ in range(4):
                m2 = np.r_[m2, m2.max() + 180 + rng.uniform(0, 14, n_frames)]
                assert choose_axis(m2, cluster_visits(m2)) == "visit", (t, n_frames)
    dense = np.concatenate([k * 30.0 + np.linspace(0, 5, 40) for k in range(8)])
    assert choose_axis(dense, cluster_visits(dense)) == "bin:14d"
    mjd, _, _ = _frames("rdra")
    assert choose_axis(mjd, cluster_visits(mjd)) == "bin:14d"
