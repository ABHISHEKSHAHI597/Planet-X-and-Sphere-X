# Seven slides — draft

One slide per column of the judging sheet, so a judge can fill the row left to right (optimisation.md PRE-3).
Historical Space Apps format (≤ 7 slides); confirm against the 2026 guide (item 0.2). Export as a PDF into
`submission/` and link it from the project page even if the demo link is the video. Every number names its record;
re-read each against `validation/STATUS.md` on the day.

## 1. ParallaX — SPHEREx blink comparator
- "The 1930 blink comparator, rebuilt for a 102-colour telescope."
- Picture: the viewer on Barnard's Star, band 6.
- Footer: public URL and QR code · repository · "Not affiliated with or endorsed by NASA".

## 2. The challenge, and the trap
- The brief: a public web tool that blinks SPHEREx images of any RA/Dec so people can spot what moves and changes.
- The trap: each SPHEREx exposure sees a different colour. ε Indi B's raw exposures flicker although nothing varies;
  ParallaX's visit stacks stay steady (the side-by-side, CRE-2, if rendered; otherwise the band axis from the home page).
- The challenge's WISE 0855 coordinate is a 2010 position.

## 3. The solution (Relevance)
- Requirement map in miniature: R1–R5 and O1–O8 with a tick and where to click (README "Does it do what the
  challenge asks?").
- Five targets, one click each, pinned so the links never change; any RA/Dec builds a new view from live data.
- Picture: home page with the five missions.

## 4. Proof (Validity)
- The proof page as a table: claim, our number, reference, state, record (`/proof`, generated from `validation/`).
- Example: Barnard's Star moved 4.540′ between 2MASS and SPHEREx, 4.540′ predicted
  (`G5.25yr-jumps/2026-11-08-5f9f54b`, L3; say "review pending" unless accepted by then).
- "What is not proven yet" is on the same page: short-band star profiles, WISE 0855's neighbour, R Dra's period.

## 5. What is new (Creativity)
- The README "What is new" table: raw exposure blink against ParallaX.
- Only here: visit-stack blink for a spectral imager, epoch-aware coordinates, the 25-year blink (if shown).

## 6. Who it is for (Impact)
- Volunteers blinking WISE found more than 3,000 brown dwarfs (Backyard Worlds); WISE has stopped; SPHEREx has no
  public blinker.
- No login, phone, PNG viewer without WebGL, keyboard; English, Hindi, Spanish; links out to WiseView and friends;
  reports as plain text; a frozen copy online after the event.

## 7. Data, credits, SI use, prior work
- SPHEREx DOIs, Gaia, 2MASS, WISE/NEOWISE, CDS, JPL, IMCCE, AAVSO (About page).
- Use of AI tools and the prior-work statement, as on the project page.
- Licence GPL-3.0-or-later; how to cite (`CITATION.cff`); how to add a release or a mission (`docs/extending.md`).
