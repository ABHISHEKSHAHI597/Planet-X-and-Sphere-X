# 0001 — Partial-visit merge rule

**Date:** 2026-11-06 · **Owner:** I · **Reviewer:** M

## Context
implementation.md §4.2 says a partial cluster (< 10 frames in a band) merges "into a full neighbour if
that neighbour is ≤ 45 d away". The same section, implementation.md §10.1, understanding.md §3.4 and
workflow.md G1 all state the verified outcome for WISE 0855 band 6: **2 full + 2 partial** visits
(counts 3 · 16 · 3 · 21).

Real SIA2 MJDs (2026-11-06, `backend/tests/data/real/wise0855_mjd.json`) show the Dec 2025 cluster
starts 27.4 d after the Nov 2025 visit ends. The 45 d rule merges it, giving 2 full + 1 partial
(19 · 21), which contradicts the verified outcome.

## Decision
Merge a partial cluster into its nearest full neighbour only if the merged visit spans ≤ 21 d, the
"≈1–3 weeks" visit length from understanding.md §0.3 (`epochs.MAX_VISIT_SPAN_DAYS`). This reproduces
3 · 16 · 3 · 21 → partial, full, partial, full.

## Alternatives rejected
- Keep 45 d: fails the documented acceptance test.
- No merging at all: same result on WISE 0855 today, but drops the documented intent of absorbing
  small tails of a visit.

## Follow-up
implementation.md §4.2 updated with this rule on 2026-11-06 (same change as decision 0002).
