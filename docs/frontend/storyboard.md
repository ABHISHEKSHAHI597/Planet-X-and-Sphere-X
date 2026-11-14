# Storyboard — the five missions (+ the challenge coordinate)

Owner: F (product lead). Phase A deliverable (workflow.md §10.2). Mission text lives in
`frontend/src/content/missions.ts`; each target's steward (workflow.md §6) reviews its wording. **No measured
number appears in mission text**: numbers on screen come from the live API (resolver, manifest, accepted
evidence), never from planning documents (workflow.md §4.1; enforced by `tests/content.test.ts`).

| # | Mission | Opens with | What the visitor does | What must be true before it ships (gate) |
|---|---|---|---|---|
| 1 | **Barnard's Star** — "The fastest star in the sky" (steward M) | band 6, 6′, visits | Blink → star hops while the field stays; turn on OVERFLOW to see why the core is blank in bands 1–4; predicted-track dots show the parallax side-step | G2 (blink, flags); track overlay needs G3; diff dipole needs G4a; 25-year blink needs G5.25yr |
| 2 | **ε Indi B** — "Two brown dwarfs, one dot" (I) | band 4 | Step bands short→long: brightness changes with methane/water; check flags near ε Indi A's ghosts | G2; spectrum panel needs G4b |
| 3 | **WISE 0855−0714** — "The coldest known brown dwarf" (D) | band 6 | Typing the famous coordinate triggers the epoch banner → "Track it"; compare band 1 with band 6 (a *different* field star is at its position in the short bands); partial visits hatched | G1 epoch guard, G2; spectrum needs G4b with the two-source fit (validation/G4b-wise-stacks) |
| 4 | **RW Aurigae** — "A young star behind shifting dust" (I) | band 3 | Static star: look for brightness changes between visits; OVERFLOW in some bands | G2; light curve needs G5.lc |
| 5 | **R Draconis** — "A breathing giant" (D) | band 3 | Time axis switches itself to 14-day bins; relative light curve from annulus ratios | G2 (fixed bins); light curve/periodogram needs G5.lc |
| + | **The challenge's coordinate** | WISE 0855's 2010 position | Epoch banner explains the 2.2′-ish move (number from `/resolve`), one click to track | G1 |

Demo arc and video: implementation.md §11.4 (authoritative). Segments whose capability is off in the final
RC are replaced by the next segment, never patched with an unvalidated feature (workflow.md §13.2).
Pinned links: each mission's `pin` is filled from D's `config/pins/*.json` before RC0 and added to
`frontend/fixtures/urls/demo-links.txt` (CI checks every demo link parses and is canonical).
