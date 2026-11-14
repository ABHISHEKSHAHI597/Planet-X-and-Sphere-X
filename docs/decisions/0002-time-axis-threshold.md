# 0002 — Visit vs fixed-bin threshold

**Date:** 2026-11-06 · **Owner:** I · **Reviewer:** M (approved for the recorded pins, 2026-11-08; decision 0004)

## Context
implementation.md §4.2 `choose_axis` switches to 14-day bins when there are more than 6 clusters or any
cluster spans more than 45 d. On the real headers of every ε Ind B frame
(`backend/tests/data/real/frames_5targets.json`), its first two visits (β = −41.5°) span 46.3 d and
44.9 d once their tails are included, so the 45-d rule turned ε Ind B into 14-day bins, against
understanding.md §3.4 (4 visits) and P0-3 (≥ 2 full visits per target). R Dra's shortest cluster spans
88.7 d.

## Decision
`epochs.MAX_VISIT_CLUSTER_DAYS = 60`: bins when > 6 clusters or any cluster spans > 60 d. Barnard,
ε Ind B, WISE 0855 and RW Aur get visits; R Dra gets bins (`tests/real/test_real_epochs.py`,
`validation/G1-time-model/`).

## Alternatives rejected
- 45 d: misclassifies ε Ind B.
- Splitting long clusters at their tails: changes visit membership for every high-latitude target and
  needs a second free parameter; nothing on the 5 targets requires it.

## Amendment — 2026-11-10 (audit B-02; I to review)
The "> 6 clusters" half of the rule counted every cluster, including 2–30-frame partial ones. Barnard's Star
already had exactly 6 (three full visits and three stragglers), so its next public cluster would have switched
every un-pinned Barnard view to 14-day bins; ε Ind B, WISE 0855 and RW Aur would follow within about a year
(`audit/repro/axis_time_bomb.py`).

Rule now (`epochs.choose_axis`): bins when any cluster spans more than 60 d (unchanged: R Dra), **or** when
*substantial* clusters (≥ 2 × `FULL_MIN_FRAMES` = 20 frames, a full visit on one detector pair) recur faster than
`MAX_VISITS_PER_YEAR = 4` over the baseline. The normal survey cadence is about 2 a year. All five targets keep
their axes; they also keep them with up to four more clusters added, full or partial
(`tests/real/test_real_epochs.py::test_axis_is_stable_as_the_mission_adds_clusters`). Pinned views are unaffected
(their frame lists are frozen). The threshold was set from the survey cadence, not tuned on a result.
