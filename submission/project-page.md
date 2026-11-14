# Project page — draft (optimisation.md PRE-4)

One section per field of the 2026 project form ([2026-rules.md](2026-rules.md)). English only. Every number names
its record; re-read each against `validation/STATUS.md` and the `/proof` page on the day. Replace `<URL>` with the
public host and `<LITE>` with the ParallaX Lite address before submitting.

Judges score Impact, Creativity, Validity (now including usability and completeness), Relevance (now including how
deeply NASA data is used) and Presentation, each 1–5, mostly from this page.

---

## 1. Project name

ParallaX — SPHEREx blink comparator

## 2. High-level summary

ParallaX is a free web tool that plays NASA SPHEREx images of any patch of sky like a little video, so that anyone
can spot stars and brown dwarfs that move and objects that change. It is the blink comparator that found Pluto in
1930, rebuilt for a telescope that sees the whole sky in 102 colours. It answers the challenge directly: type a name
or any RA/Dec, and it builds the series of SPHEREx images from the archive and blinks them, tested on all five
challenge targets. It matters because volunteers blinking WISE images found more than 3,000 brown dwarfs, WISE has
stopped observing, and SPHEREx, which now re-images the whole sky every six months, had no public blink tool.

## 3. Demo

<link to the 30-second video, English subtitles burned in> (script: [video-script.md](video-script.md))

## 4. Final project

Tool: <URL> · Frozen copy for the judging period: <LITE> · Code: https://github.com/ABHISHEKSHAHI597/Nasa-Space-Apps-2026

## 5. Project details

**What it does.** Type a star name or coordinates. ParallaX finds every SPHEREx frame of that patch, groups them
into visits, stacks each visit in each of six infrared bands on one shared grid and brightness scale, north up, and
plays the visits as a blink. Moving stars hop; varying objects pulse. Five one-click missions cover the challenge's
test targets: Barnard's Star, ε Indi B, WISE 0855−0714, RW Aurigae and R Draconis.

**The idea that makes it work.** SPHEREx is a spectral imager: each exposure sees a different wavelength, so blinking
raw exposures shows a spectrum, not motion. ε Indi B's published spectrum doubles in brightness between 3.25 and
3.58 µm, so its raw exposures flicker although nothing about it varies. ParallaX blinks one stack per visit per band.
It also recognises when typed coordinates are an old position of a fast mover: the challenge's own WISE 0855
coordinate is a 2010 position, and ParallaX says so and shows where the object is now.

**Benefits.** No login; works on a phone, and without WebGL through a PNG viewer; keyboard control; home page and
missions in English, Hindi and Spanish. Every view is a link to share or embed. Candidate reports copy as plain text
for a citizen-science forum, and each view links to WiseView, the Legacy Survey viewer, ESASky and SIMBAD. A frozen
static copy keeps the five targets online through judging, independent of any server.

**How we know it works.** Every capability sits behind an evidence gate, and `<URL>/proof` lists each claim with our
number, the reference and its record, including what is not proven yet. Example, from
`validation/G5.25yr-jumps/2026-11-08-5f9f54b` (L3, independent review pending): Barnard's Star moved 4.540′ between
2MASS and SPHEREx, as its catalogue motion predicts (4.540′). Known limits, stated by us: short-band star profiles
(spectra stay off the public site), WISE 0855's close neighbour, R Dra's too-short light curve.

**What we hope to achieve.** A blink tool that the people who found brown dwarfs in WISE can use on SPHEREx from the
first public release onward; a new data release is one configuration entry.

**Tools.** Python (FastAPI, NumPy, Astropy, reproject, photutils), TypeScript (React, WebGL2), Aladin Lite, Docker,
GitHub Actions.

## 6. NASA data and resources

- **SPHEREx** Quick Release spectral images (QR2, QR3) from NASA/IPAC IRSA (DOIs 10.26131/IRSA652,
  10.26131/IRSA662): the frames of every blink, their flags, wavelength and PSF calibration files. Read through
  IRSA's SIA2 and TAP services, cutouts and the public S3 bucket.
- **WISE / NEOWISE, AllWISE, CatWISE2020, unWISE** (NASA/IPAC IRSA): the 25-year blink's WISE epochs and the WISE
  catalogue layer.
- **2MASS** (NASA/IPAC IRSA): the oldest epoch of the 25-year blink.
- **JPL Horizons**: positions of Solar System bodies as seen from SPHEREx.

## 7. Space Agency Partner data

- **ESA Gaia DR3**: positions, proper motions and parallaxes propagated to every visit; Gaia markers.
- **ESASky** (ESA): a link-out from every view.

## 8. References

SPHEREx, WISE/NEOWISE, AllWISE, CatWISE2020, unWISE, 2MASS and Gaia DR3 archives as above; SIMBAD and Aladin Lite
(CDS, Strasbourg; Aladin Lite GPL-3); IMCCE SkyBoT; AAVSO; SPIFF spectra (Gagné et al. 2026, CC-BY 4.0); open-source
software listed on the About page (`<URL>/about`) and in `backend/pyproject.toml` and `frontend/package.json`;
fonts Archivo and IBM Plex Mono (SIL OFL 1.1). Full acknowledgement texts: `<URL>/about`.

## 9. SI use (data collection only; the same text is in the README and on the About page)

The team used an SI coding assistant (Claude Code) to write and review parts of the code, tests and documentation,
including a code audit and the fixes that followed it (in the git history). The challenge idea and the scientific approach (visit stacks per band, epoch
handling, evidence gates) are the team's. No SI-generated images, video or audio are used. Scientific claims rest on
the evidence records in `validation/`, produced by the repository's scripts and reviewed by a team member other than
the author.

## Prior work (state it in the details or summary, as the Local Lead rules)

The FAQ says "Teams are not allowed to begin working on the challenges prior to the hackathon." Most of this
repository was written between 5 and 12 November 2026; the commit dates show it and are not rewritten.
<State here what the Local Lead ruled (optimisation.md item 0.1).>
