# Submission package — drafts

Drafts of the Space Apps 2026 submission for *Planet X and SPHEREx* (implementation.md §11.5, workflow.md §13.6).
Owner: F (product lead). **Drafts, not final:** re-check every number on the day you record. The format is confirmed
against the 2026 guides (fetched 14 Nov): see [2026-rules.md](2026-rules.md) — demo ≤ 30 s video (English subtitles)
or ≤ 7 slides in English, hosted publicly; the project page is what judges mostly score; SI use must be acknowledged
inside the project.

| File | What |
|---|---|
| [video-script.md](video-script.md) | The 30-second video, shot by shot, with the URL for each shot |
| [slides.md](slides.md) | Seven slides, one per judging column, text and what to show on each |
| [2026-rules.md](2026-rules.md) | The 2026 judging criteria, eligibility, form fields, SI and pre-event rules, quoted from the official guides |
| [project-page.md](project-page.md) | Project page text: summary, then Impact, Creativity, Validity, Relevance, How it works, data, SI use, prior work |

## Rules these drafts follow

- **Numbers come from evidence records, never from planning documents** (workflow.md §4.1, §11.2). Each number
  below names its record. A record that is *unreviewed* is said to be so on screen ("measured, review pending").
- **Nothing shown is a capability whose flag would be off in the release that is demoed.** If the public deployment
  is `staging` or `production`, the difference view, spectra and light curves are not shown; the
  blink, the epoch banner, the flags overlay and (if its flag is on) the 25-year blink are.
- **Candidate language only.** Nothing is called a discovery.
- **No NASA insignia; no implied endorsement.** The 1930 plates are drawn, not photographs.

## Before recording (checklist)

1. Every shot's URL opens a pinned, prewarmed view on the recording machine (README "Before a demo").
2. `validation/STATUS.md` is fresh; quote only what it says on the recording day.
3. The acknowledgement texts still marked `verbatim: false` in `frontend/src/content/credits.ts` are copied from
   their archives' pages (`RELEASE=1 npm test` lists what is left).
4. ~~Licence chosen~~ Done: GPL-3.0-or-later (`LICENSE`; Aladin Lite is GPL-3 and bundled).
5. SI-use disclosure matches the 2026 rules (README "Use of SI tools", About page; 2026-rules.md).
6. The proof page data is fresh: `python scripts/make_proof.py --check` (after `validate.py status --write`).
7. Every `<URL>` placeholder in these drafts and in the README top screen is replaced by the public host.
8. Nobody under 18 appears in the demo or the project (photo, video, voice).
9. Every external code, text and image source is in the References field (project-page.md §8), and the
   "original work" box is ticked only after the Local Lead's ruling on pre-event work (2026-rules.md).
10. Demo, slides and tool links open in a private window, without login, on a phone.
