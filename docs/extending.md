# Extending ParallaX: a data release, a mission, a pinned target (optimisation.md IMP-6)

Short how-tos for people who want to build on ParallaX. Each step names the file that holds it; the tests named at
the end of each section say whether the change is complete.

## Add a SPHEREx data release

A release is one entry in `config/releases.yaml`. The full procedure (detection, dedup between releases, what to
re-run) is [data-refresh.md](data-refresh.md). View keys depend on the frame list, so existing links keep showing
what they showed; pinned links never change.

## Add a pinned target

A pin freezes the frame list of one target, so its link shows the same pixels forever.

1. Add the target's position to `TARGETS` in `scripts/verify/f11_coverage.py` and record its coverage
   (`python scripts/verify/f11_coverage.py`, network needed once).
2. `python scripts/make_pins.py` writes `config/pins/<pin>.json` and the index. Existing pins are never rewritten.
3. Add the view to `config/demo_views.yaml` (the body exactly as the frontend posts it: `q` or `ra`/`dec`, `pin`,
   `bands`, `fov`).
4. If the view is opened by name, freeze its resolved target: `python scripts/freeze_targets.py`, with the archives
   reachable. Read the printed source: a star that normally has Gaia astrometry must say "Gaia DR3 …". A degraded
   answer is refused, not written.
5. Build it: `python scripts/prewarm.py --api <api>`; for the frozen copy, rebuild ParallaX Lite (deploy.md §8).

Checks: `pytest tests/app/test_audit_fixes.py` (every pinned demo target is frozen) and `npm test`.

## Add a mission to the home page

1. Add an entry to `MISSIONS` in `frontend/src/content/missions.ts`: `id`, `pin`, `q`, the `match` pattern for the
   names it answers to, the `bands` and `fov` it opens with, a steward (the role letter who signs its wording), and
   `title`, `hook` and the `look` steps. Mission text quotes no measured number (workflow.md §4.1).
2. Translate the title, hook and every step into each language of `frontend/src/content/translations.ts`, step for
   step. A fluent speaker reads it before release.
3. Its view must be pinned and prewarmed (above): a home-page button must never wait on a cold build.

Checks: `npm test` (`tests/content.test.ts` holds every language to the same steps and the no-numbers rule, and every
mission to a committed pin and a prewarmed demo view). That test also lists the mission ids in order: add the new id
there, on purpose.

## Add a capability

New capabilities start at `dev` in `config/features.yaml` and are listed in `CAPABILITIES`
(`frontend/src/lib/features.ts`); `scripts/check_flags.py` fails CI otherwise. `on` needs every `requires` gate
accepted in `validation/STATUS.md`; `staging` is for UX immaturity only, never for a number that could be wrong.
