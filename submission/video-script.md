# 30-second video — draft

Rebuilt on the three beats the judging sheet names: the challenge, the solution, why it matters (optimisation.md
PRE-2). Times are targets. Subtitles burned in: it must be understood with the sound off. Record after the Sunday
11:00 feature freeze, from pinned prewarmed views, 1080p, large cursor (PRE-7). `<host>` is the public URL, or
`http://localhost:5173` for a laptop recording.

| Beat | Time | Picture | Words (voice-over and subtitle) | URL / source |
|---|---|---|---|---|
| Challenge | 0–4 s | Home page hero: the drawn 1930 plate pair, one dot jumping | "1930: Pluto was found by blinking two photographs of the same stars." | `<host>/` |
| Challenge | 4–9 s | The trap, side by side: ε Indi B's raw exposures in time order flicker; ParallaX's visit stacks stay steady | "SPHEREx now images the whole sky in 102 colours. But each exposure sees a different colour, so a naive blink lies." | Rendered side-by-side (CRE-2). If it is not rendered from pinned data by the freeze, cut it and give these 5 s to the solution |
| Solution | 9–14 s | Click *Barnard's Star* → visit blink in band 6; the star hops while the field stays | "ParallaX blinks one stack per visit, one band at a time, on one brightness scale." | `<host>/?q=Barnard's%20Star&pin=21a7689afc4b` |
| Solution | 14–18 s | 25-year blink panel: 2MASS → SPHEREx; the star jumps across the field | "Against 2MASS, 26 years ago, Barnard's Star has moved four and a half arcminutes." | Only if `blink25` is shown in the demoed release. Number: `validation/G5.25yr-jumps/2026-11-08-5f9f54b` (4.540′; L3, review pending — subtitle says "measured, review pending" unless accepted by then) |
| Solution | 18–23 s | Home → "The challenge's coordinate" → epoch banner → *Track it* | "Type the challenge's WISE 0855 coordinate: ParallaX knows it is a 2010 position, and where the coldest known brown dwarf is now." | `<host>/?ra=08:55:10.831&dec=-07:14:42.53&fov=12&pin=325c57328320`. Banner numbers come from the live manifest |
| Why it matters | 23–28 s | Phone in hand, the same view; Share dialog | "Volunteers blinking WISE found over 3,000 brown dwarfs. WISE has stopped; SPHEREx has no public blinker. Now it does, for anyone." | Backyard Worlds figure: advanced_research.md §3.5 (NASA, 2026-05-06) |
| URL | 28–30 s | The URL, large | "<host>" | — |

## Do not say (until the matching gate is accepted)

- "Fitted proper motion matches Gaia" (G3 is blocked on F5; the motion card is unvalidated).
- "Its spectrum shows methane" or "the methane meter says cold" (G4b blocked; spectra unvalidated).
- "Empty at 1–2 µm" for WISE 0855: a G = 16.3 field star sits 0.7–1.35 px away (understanding.md §8.4).
- Any light-curve period for R Dra (G5.lc fails: 18 bins against 20).

## If a gate is accepted before recording

Replace the second half of the WISE 0855 shot with the fitted motion beside Gaia (G3) or the spectrum with a T6 template (G4b), and
quote the number from the accepted record, not from this file.
