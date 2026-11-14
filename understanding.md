# Planet X and SPHEREx — Deep Understanding

> **NASA Space Apps Challenge 2026** · Difficulty: **Advanced** · Skills: Astrophysics, Planets & Moons, Software
> **Hackathon:** Sat Nov 14, 09:00 → Sun Nov 15, 23:59 (local time) · **Resources tab opens:** Fri Nov 13
> **Challenge page:** https://www.spaceappschallenge.org/2026/challenges/planet-x-and-spherex/
>
> Written 2026-11-05 and **revised 2026-11-06** after a second verification pass. [§14](#14-revision-log-2026-11-06) lists every correction and why. Facts marked ✅ were checked against primary sources: the challenge page, IRSA's SPHEREx docs, the *SPHEREx Explanatory Supplement* v2.0 (2026-08-25), live IRSA SIA/TAP queries, the S3 bucket, SIMBAD, Gaia DR3, 2MASS, JPL Horizons, IMCCE SkyBoT, and real QR3 FITS cutouts. A plain ✅ means checked on 2026-11-05; **✅ 11-06** means (re)checked on 2026-11-06. Numbers marked **≈** are engineering estimates. Check them before quoting to judges.
>
> Companion document: [`implementation.md`](./implementation.md) covers how to build it.

---

## 0. TL;DR: the 13 things that decide this challenge

1. **The ask.** Build a public web tool. A user enters RA/Dec, and the tool plays SPHEREx images of that patch "like a little video" so anyone can spot things that move or change. Test it on Barnard's Star, ε Indi B, WISE 0855−0714, RW Aurigae and R Draconis.
2. **SPHEREx is not a normal camera.** It is a *linear-variable-filter (LVF) spectral imager*, so the wavelength changes across each detector. In a single exposure a star lands on only **two** detectors: one short-wave detector and its co-aligned long-wave partner (**D1+D4, D2+D5 or D3+D6**, ✅ 11-06). It is therefore measured at **two wavelengths per exposure**. Two consecutive exposures of the same patch are taken at *different wavelengths*. Playing raw exposures in order therefore produces flicker from the source's **spectrum**, not from motion. **This is trap #1.**
3. **The correct "frame" for a blink is a *visit*.** Each patch of sky is visited roughly every **6 months**. A visit lasts about **1–3 weeks** and yields about **18–24 exposures per detector**, stepping through all 17 channels. Stack each (visit, detector) combination to get 6 broadband images per visit, then blink *visits*. The challenge hints at this directly ("add together all the data taken by each of the six detector arrays"). ✅ 11-06: real coverage also contains **partial visits**, clusters of 2–30 frames with sometimes only 3 per detector. Label them; don't blink them as full epochs.
4. **Motion over SPHEREx's own baseline is tiny.** From the first to the latest visit (≈1.0–1.4 yr), Barnard's Star moves **1.9 px** and ε Indi B **1.1 px** (6.15″ pixels). ✅ 11-06: WISE 0855 has only **two full visits** (Oct–Nov 2025 and Apr–May 2026), **0.78 px** apart including parallax. Its one-year baseline rests on a May 2025 partial visit with just 3 band-6 frames. A plain blink shows Barnard's hop but makes the others subtle. Difference imaging (moving sources leave **dipoles**), sub-pixel centroiding, drawn motion vectors, and a **long-baseline blink against 2MASS/WISE** are what make motion "easy to spot".
5. **Coordinates and names have epochs and traps.** The challenge's coordinate for WISE 0855 is its position in **≈2010.45** (WISE era). By Nov 2026 the object is **2.2′ (≈22 px) away**. Barnard's Star is 4.6′ from its J2000 position. The tool must **propagate proper motion**, starting from the right catalogue epoch. ✅ 11-06: SIMBAD's J2000 positions are *linear* back-propagations of Gaia, so running them through a radial-velocity-aware propagator puts Barnard 0.4″ off. Names hide traps too. `WISE 0855-0714` does not resolve in SIMBAD, `Barnard's Star` breaks an unescaped ADQL string, and SIMBAD's RW Aur parallax is a 2007 Hipparcos value 2.4× too large.
6. **Every other visit is rotated 180°.** The spacecraft flies at position angle 0° on ascending orbit halves and 180° on descending halves. Images also carry SIP distortion. **Reprojecting to a common north-up grid is mandatory.**
7. **You need a backend.** ✅ IRSA's SIA2, TAP and cutout endpoints send **no CORS headers**, so a browser-only app cannot call them. The AWS S3 mirror (`nasa-irsa-spherex`) does allow cross-origin GETs.
8. **The cutout trap.** ✅ Every IRSA cutout carries the full ePSF extension, **≈3.9 MB**, even for a 29×29-pixel cutout. A target has about 360 frames, so a naive client downloads **≈1.4 GB**. Everything you need sits in the first **89,280 bytes** (✅ 11-06), so stopping the stream after the ZODI extension, or reading byte ranges from S3, cuts this by roughly 30–100×. ✅ 11-06 from our network: the cutout service took 1–4 s to first byte and delivered ≈15 KB/s. It returned an HTTP 503 under 4 parallel requests, and some transfers ended early after an HTTP 200 header. Plan for throttling and truncation, and keep pixel traffic off the venue Wi-Fi.
9. **Flags are subtle.** ✅ In a crowded field **81% of pixels** carry the `SOURCE` bit. It marks known catalogue sources and must never be used as a mask. `OUTLIER` and `STREAK` are computed only on pixels that are *not* known sources. They can light up on exactly the **uncatalogued movers** you want to find, so show them as hints and don't mask them in discovery mode.
10. **Brightness extremes.** Barnard's Star, R Dra and RW Aur are bright enough to reach the onboard **OVERFLOW** threshold. Their cores can be NaN in the short bands **≈**. WISE 0855 is the opposite: invisible below ≈3.5 µm, so you need **band 5–6 stacks**.
11. **Data arrives every week.** ✅ QR3 has been flowing since 2026-09-16. ✅ 11-06: the newest QR3 planning period in S3 is `2026W40_2A`, about 5 weeks behind real time, and the bucket holds only `qr2/` and `qr3/`. **DR1**, a reprocessing of Surveys 1–2, is due "late fall 2026" and could land during the hackathon. Keep collections in config and deduplicate by pipeline version.
12. **The gap to fill.** IRSA already offers search, forced photometry and per-channel mosaics. Nobody offers a *WiseView-style, public, time-domain blinker for SPHEREx* with spectra on the fly. To win: get the time axis right, make motion obvious, extract spectra on demand, make it embeddable, and make the public UX a delight.
13. **The namesake is in reach.** ✅ 11-06: JPL Horizons knows SPHEREx as an observer (body −163182), so any Solar System object can be tracked *as SPHEREx saw it*. Pluto, the original "Planet X", is at V ≈ 14.4 in 2025–26. That is bright enough for single frames, and its methane ice absorbs at 1.7, 2.3 and 3.3 µm. Showing it closes the story the challenge's title opens.

---

## 1. The challenge, decoded

### 1.1 Verbatim core (✅ from the challenge page)

> *Your challenge is to create a public-facing web tool to display images of the sky from the SPHEREx mission, making it easy for anyone to quickly see how they change over time. Users will enter the coordinates of a patch of sky (Right Ascension and declination). Your tool will display a series of images of that patch like a little video, making it easy to spot moving objects.*
>
> *Test your tool on Barnard's Star, Epsilon Indi B (a pair of brown dwarfs orbiting a star), WISE 0855 (a fast-moving brown dwarf Right Ascension 08h55m10.831s, declination −7d14m42.53s), and variable stars RW Aurigae and R Draconis.*

### 1.2 Requirement matrix

| # | Item from the page | Type | What it *really* means | Our answer (see implementation.md) |
|---|---|---|---|---|
| R1 | Public-facing web tool | **Required** | No install. Works for non-experts on a laptop or phone browser. Fast first paint. | SPA + hosted API, plus a "Simple" mode |
| R2 | Enter RA/Dec | **Required** | Accept sexagesimal and decimal input. Names are a bonus. Must handle **proper-motion epochs**. | Coordinate parser + SIMBAD/Gaia resolver with PM propagation |
| R3 | "Series of images … like a little video" | **Required** | You must *define* a frame. Raw exposures mislead (see §5). | Visit-stacked flipbook (default) plus an exposure flipbook (expert) |
| R4 | Easy to spot moving objects | **Required** | Motion is 1–2 px, so plain blinking is not enough. | Blink + difference + predicted-track overlay + motion vectors + long-baseline blink |
| R5 | Test on 5 targets | **Required validation** | Judges will try these first. | Pre-warmed "missions" with expected results (§8) |
| O1 | Easy to update with new releases | Optional | Weekly ingests, QR→DR transitions | Config-driven collections, version dedup, release watcher |
| O2 | Creative display of 102 bands; coadd per detector; spectra on the fly | Optional, "extra kudos" | The spectral dimension is SPHEREx's superpower. | Band stacks, RGB presets, λ-scrubber, click-for-spectrum, spectral flipbook |
| O3 | Add/subtract images taken at different times | Optional | Difference imaging, coadds | Wavelength-matched differencing (§5.3) |
| O4 | User-chosen field of view | Optional | Bigger FOV catches faster movers but costs bandwidth | 2′–30′ at native scale (P0); up to 60′ with server-side binning (P2) |
| O5 | Overlay Gaia / WISE | Optional | Context and validation | Aladin Lite HiPS + Gaia DR3 propagated to each epoch + CatWISE PMs |
| O6 | Coordinates in the URL; embeddable | Optional | Shareability | Full app state in the URL, `/embed` route, iframe snippet |
| O7 | Show metadata such as contamination flags | Optional | Trust and science validity | Flag overlay with per-bit toggles, per-frame QA badges |
| O8 | Use public tools (Astropy, Aladin) | Optional | Don't reinvent | astropy/reproject/photutils, Aladin Lite v3 |

> "Astrophy tools" on the page is a typo for **Astropy**.

---

## 2. Science background: why motion finds new worlds

### 2.1 The blink comparator and the original "Planet X"
Percival Lowell predicted a "Planet X" beyond Neptune. At Lowell Observatory in **February 1930**, Clyde Tombaugh used a *blink comparator* to flip quickly between two photographic plates taken six days apart (Jan 23 and Jan 29, 1930). One faint dot jumped while thousands of stars stayed still, and that dot was **Pluto**. Your tool is a digital, spectral, all-sky descendant of that instrument, which is why the challenge is named "Planet X and SPHEREx".

### 2.2 The three kinds of apparent motion

| Motion | Cause | Magnitude | Formula |
|---|---|---|---|
| **Proper motion** μ | The object's real sideways velocity relative to the Sun | Up to 10.4″/yr (Barnard's Star). Brown dwarfs near the Sun: 0.5–8″/yr. | μ[″/yr] = v_t[km/s] / (4.74 · d[pc]) |
| **Parallax** ϖ | The observer orbiting the Sun | ϖ[″] = 1/d[pc]. Barnard: 0.547″. A body at 500 AU: 412″. | Displacement = ϖ × (observer offset in AU, projected) |
| **Orbital motion** | Solar-system bodies orbiting the Sun | Main-belt asteroids: tens of ″/hr. TNOs: ″/hr. | Ephemeris (JPL Horizons, IMCCE SkyBoT) |

**Nearby means fast.** Both proper motion and parallax scale as 1/distance. Searching for movers is therefore searching for the Sun's nearest neighbours (stars and brown dwarfs) and for Solar System bodies.

### 2.3 Citizen science already works
- **Backyard Worlds: Planet 9** (Zooniverse, 2017–) shows volunteers *flipbooks* of unWISE images from different epochs. Volunteers have found thousands of brown dwarf candidates. Notable finds include **WISE J0830+2837**, one of the coldest known brown dwarfs (found in 2020), and **"The Accident"** (WISEA J1534−1043), spotted by chance in **WiseView**.
- **WiseView** (Caselden et al. 2018) is the blink tool behind much of that work. You type coordinates and it animates unWISE W1/W2 epochs, with controls for size, speed and contrast. **Your tool is essentially "WiseView for SPHEREx", plus a spectral dimension WISE never had.**
- The challenge page itself says that *"most of the known comets and brown dwarfs were discovered by volunteers in this manner."*

### 2.4 What "Planet X" honestly means in 2026
- **Planet Nine hypothesis** (Batygin & Brown 2016 and later): a planet of about 5–10 Earth masses at a few hundred AU, inferred from clustering of distant TNO orbits. Most predictions put it fainter than **V ≈ 20–21**.
- **SPHEREx's realistic reach:** per-channel depth is roughly 18.5–19.5 AB (5σ, full mission, 1–3.5 µm) **≈**. Stacking many channels gains about 1–2 mag. SPHEREx can probe only the bright, optimistic corner of Planet Nine parameter space, and the pixels are coarse. Pitch the tool as the instrument that *could* catch such an object; don't promise a discovery.
- **Any remaining chance lies at 4–5 µm.** Atmosphere models of a Neptune-like Planet Nine predict extra flux around 4–5 µm, where methane absorbs less (Fortney et al. 2016). A WISE/NEOWISE search at 3.4 µm (Meisner et al. 2018) already excluded the brightest cases over most of the sky. Any SPHEREx chance therefore lies in band 5–6 stacks.
- **The original Planet X is in the data.** Pluto is at V ≈ 14.4–14.6 and ≈34–36 AU in 2025–26 (✅ 11-06, Horizons), far above single-frame depth. Known dwarf planets such as Makemake (V ≈ 17), Haumea (V ≈ 17.3) and Eris (V ≈ 18.7) should be within reach of per-day stacks **≈**. They are the honest test set for any "Planet X mode" (§6.1).
- **What SPHEREx *can* realistically find with a blink tool:** new nearby **cold brown dwarfs** (bright only at 4–5 µm, with a methane dip at 3.3 µm), **high-proper-motion stars**, **comets and asteroids** (with spectra showing ices and CO₂), **variable stars and YSO outbursts**, and artifacts that need flagging, which is useful too.
- **The killer synergy is SPHEREx plus (un)WISE.** WISE/NEOWISE imaged the whole sky at 3.4/4.6 µm from 2010 to 2024. Adding SPHEREx's 2025–2027 epochs at matching wavelengths extends the baseline to **15+ years**. A 0.3″/yr mover shifts 4.5″ over that span, which is detectable, but only 0.4″ within SPHEREx alone. The ideal Planet X/brown-dwarf finder blinks unWISE and SPHEREx band 5–6 stacks together.

---

## 3. SPHEREx: the instrument you must understand

### 3.1 Key parameters (✅ Explanatory Supplement v2.0, Tables 1–2)

| Parameter | Value |
|---|---|
| Launch | 2025-03-12 03:10 UTC, Falcon 9, Vandenberg |
| Science operations | Began **2025-05-01**. Nominal 25 months, **4 all-sky surveys**. |
| Orbit | Sun-synchronous polar, **98 min** period, i = 97.95°, dawn–dusk (6:00 ascending node), a = 7037 km |
| Telescope | 20 cm effective aperture, f/3, three-mirror anastigmat, passively cooled |
| Field of view | **2 × (3.5° × 11.3°)**. A dichroic splits the light so both focal planes see the same sky. |
| Detectors | 6 × Teledyne H2RG, 2040 × 2040 active pixels. 3 SWIR (2.6 µm cutoff, 62 K) + 3 MWIR (5.3 µm cutoff, 45 K). |
| Co-aligned detector pairs | **D1↔D4, D2↔D5, D3↔D6** see the same sky through the dichroic. ✅ 11-06: of 181 exposures covering Barnard's Star, 178 put it on exactly one such pair. The other 3 caught it on a single detector near an edge. |
| Pixel scale | **6.15″** (pixel solid angle ≈ 37.9 arcsec², from the `OMEGA_MEDIAN` header) |
| Exposure | **113.58 s**, sample-up-the-ramp, 1.5349 s frame time |
| Spectral channels | 17 per detector × 6 = **102** |
| PSF FWHM | Varies by band and detector position. **≈9.0″ in band 6** (`PSF_FWHM` header, real QR3 file). |

| Band | Detector | λ range (µm) | R = λ/Δλ | Physics highlights |
|---|---|---|---|---|
| 1 | D1 (SWIR) | 0.744–1.116 | 39 | Stellar continuum, atmospheric He 1.083 µm line (contaminant) |
| 2 | D2 (SWIR) | 1.099–1.651 | 41 | H₂O/CH₄ in brown dwarfs, Paβ 1.28 |
| 3 | D3 (SWIR) | 1.636–2.421 | 41 | CH₄ 1.6/2.2, Paα 1.875, CO bandhead 2.29 |
| 4 | D4 (MWIR) | 2.423–3.822 | 35 | **H₂O ice 3.05**, **CH₄ 3.3**, PAH 3.3, hydrated asteroids at 2.7–3.1 |
| 5 | D5 (MWIR) | 3.809–4.420 | 112 | Brα 4.05, **CO₂ ice/gas 4.26**, Y-dwarf flux peak |
| 6 | D6 (MWIR) | 4.412–5.002 | 128 | **CO ice/gas 4.67**, brown-dwarf 4.5 µm peak (WISE W2 analogue) |

### 3.2 LVF spectroscopy: the concept everything hangs on
```
   One SPHEREx detector (2040 × 2040 px ≈ 3.5° × 3.5°), schematic
   ┌──────────────────────────────────────────────┐ ← λ_max of the band
   │ channel 17      (iso-λ contours are curved,  │
   │ channel 16       a "smile", not straight)    │
   │   ...                                        │   wavelength changes
   │ channel 2                                    │   continuously along
   │ channel 1                                    │   ONE detector axis
   └──────────────────────────────────────────────┘ ← λ_min of the band
   A star landing here is measured only at λ(its pixel position).
   To build its spectrum, the spacecraft re-points so the star
   lands on every channel in turn.
```
- A **linear variable filter** sits above each detector, so pixels at different positions along one axis see different narrow bands.
- **One exposure gives each source two wavelengths**: one from the short-wave detector it lands on and one from that detector's long-wave partner (D1+D4, D2+D5 or D3+D6). The other four detectors see different sky in that exposure.
- **A spectrum takes many exposures.** ✅ "SPHEREx obtains spectra through multiple exposures, placing a given source at multiple positions in the field of view."
- The exact centre wavelength of every pixel is published (✅ the `spectral_wcs` calibration product, extensions `CWAVE`/`CBAND`). An approximate lookup table also sits in each file's `WCS-WAVE` extension.

### 3.3 Survey strategy (✅ Supplement §1.4) and why it matters for blinking
- **Target group:** 17 pointings at the *same ecliptic longitude*, each **stepped by one channel width (≈12′) in ecliptic latitude**. After one group, every point in a square region has been seen in all 17 channels of one detector pair (for example D2 and D5).
- **Latitude rings:** target groups are tiled around great circles, overlapping for redundancy. Over a visit (≈1–3 weeks), successive overlapping groups place a given point on each detector column. This is our reading, and it is consistent with the real data: each visit has frames from all 6 detectors spread over days to weeks.
- **Orientation:** the wide (11.3°) axis is kept along constant ecliptic latitude. **PA = 0° on ascending orbit halves and 180° on descending halves.**
- **Survey definitions are interleaved, not chronological.** ✅ In months 0–12.5, PA 0° data is Survey 1 and PA 180° data is Survey 2. Months 12.5–25 give Surveys 3 (PA 0°) and 4 (PA 180°). One patch of sky can therefore be seen in the order S2 → S1 → S4. Barnard's Star is visited in Aug 2025 (S2), Mar 2026 (S1) and Aug 2026 (S4; the real header has `SPS_EPA = 180`).
- **Surveys 3 and 4 are shifted by 6′ (half a channel)** relative to Surveys 1 and 2, so the combined mission samples every spectrum at the Nyquist rate.
- **Deep fields:** one at the north ecliptic pole and one near the south ecliptic pole, covered by heavily overlapping target groups. ✅ R Draconis lies inside the NEP deep coverage, which gives a near-continuous time series.

### 3.4 The cadence a user actually experiences (✅ live IRSA queries, 2026-11-05)

| Target | β (ecl. lat.) | Visits found (wide + deep, QR2 + QR3) | Frames |
|---|---|---|---|
| Barnard's Star | +28.2° | ✅ 11-06, at the 2026 position: 2025-08-15→09-05 (109 frames) · 2026-03-11→04-10 (113) · 2026-08-16→09-02 (117, QR3), plus partial clusters of 10, 8 and 2 frames | 359 |
| ε Indi B | −41.5° | 2025-04-24→06-10 · 2025-09-28→11-12 · 2026-04-18→05-04 · 2026-09-22→10-02 (✅ 11-06: the first two span 46 and 45 d with their tails; 66 frames predate 2025-05-01, IOC) | **447** (✅ 11-07, F11: SIA2 and TAP both give 447 after dedup; the earlier 449 is not reproduced) |
| WISE 0855−0714 | −23.6° | ✅ 11-06: 2025-05-05/06 (30 frames, **only 3 in band 6**) · 2025-10-31→11-14 (108; 16 in band 6) · 2025-12-11→13 (18; 3 in band 6) · 2026-04-21→05-14 (100; 21 in band 6). All QR2. | 256 (no QR3 yet) |
| RW Aurigae | +7.5° | 2025-09-01→09-20 · 2026-02-20→03-12 · 2026-09-02→09-16 | 333 |
| R Draconis | +81.4° | Nearly continuous 2025-04-24 → 2026-09-27 (NEP deep field) | **≈2,480** (≈1,950 of them from the `_deep` collections; ✅ 11-07, F11: 2,483, of which 1,947 deep) |

Takeaways:
- Low and mid ecliptic latitudes get **about 2 visits per year**, each with about **18–24 frames per detector**.
- ✅ 11-06: each exposure covers a detector *pair*, so per-visit counts come in near-equal pairs (D1/D4, D2/D5, D3/D6).
- **Partial visits are common.** These are short clusters of 2–30 frames next to, or between, the main visits. One with 3 frames per detector is ≈1 mag shallower than a full visit. Label them and keep them out of the default blink, but use them for astrometry when they lengthen the baseline. WISE 0855's May 2025 cluster is the only thing that gives it a one-year baseline.
- Some frames predate 2025-05-01. They come from the commissioning period, so tag them "IOC".
- High ecliptic latitudes and deep fields get dense coverage. There the right time axis is a **fixed time bin** (e.g. 14 days), not a "visit".
- ✅ Data appears at IRSA within **≤60 days** of observation. ✅ 11-06: the newest QR3 planning period is `2026W40_2A` (≈Sep 28–Oct 4), about 5 weeks behind. WISE 0855's next visit should fall around Oct 31–Nov 14 2026, by analogy with 2025, so it will very likely **not** be public during the hackathon.

### 3.5 Sensitivity and saturation (**≈**, verify against Supplement Fig. 3)
- **Depth:** per-channel 5σ point-source depth over the full four-survey mission is roughly **18.5–19.5 AB at 1–3.5 µm**. It is about 1 mag shallower in bands 5–6, where the bandpasses are about 3× narrower. A single visit is about 0.75 mag shallower than four.
- **Stacking gain:** coadding N frames from one detector gains about 2.5·log₁₀(√N) mag, so ≈ **+1.6 mag for N ≈ 20**. That is the case for per-detector visit stacks.
- ✅ 11-06 (F7, Barnard 12′ field, QR3): `OVERFLOW` sets in at K ≈ 9.5 in bands 2–3 and K ≈ 9 in band 4; in bands 1, 5 and 6 K = 8.6 stars are not flagged (onset between K 4.5 and 8.6). Barnard's Star overflows in all six bands; its core is NaN in bands 1–4 and flagged TRANSIENT + SUR_ERROR (early event, masked) in band 6 in 52 of 59 frames.
- **Saturation:** the onboard overflow threshold is set at about half of full well (✅ `KOVR_A = 15000` ADU). Pixels that overflow in the first ≈5 s become NaN (✅ "early overflow"). Later overflows keep a ramp-fitted value but get flagged. A rough photon budget (20 cm aperture, ≈50% throughput, ≈30% of a star's light in its peak pixel) puts the `OVERFLOW` onset somewhere around K ≈ 7–10 (Vega) in bands 1–3 **≈**. The detector gain (e⁻/ADU) is the main unknown. Measure the onset on day 1 by matching `OVERFLOW` flags to 2MASS K magnitudes in one crowded cutout.

---

## 4. The data: what exists and how to get it

### 4.1 Release timeline (✅ IRSA docs, Supplement §2.1)

| Release | Content | Status (✅ 2026-11-06) |
|---|---|---|
| QR1 | First weekly quick-release images (Jul 2025) | **Retired Feb 2026. Do not use or mix.** |
| QR2 | Reprocessed QR1 plus weekly data (pipeline 6.4–6.5.6). PSF header errors fixed Mar/Apr 2026 (`+psffix1` suffix). | Live. SIA collections `spherex_qr2`, `spherex_qr2_deep`. |
| QR3 | Survey 3/4 data on the R7 pipeline (new gain, astrometry, ePSF, flags) | Live since 2026-09-16. Collections `spherex_qr3`, `spherex_qr3_deep`. Newest planning period `2026W40_2A`. |
| QR3 back-fill | Survey 3/4 data from 2026-05-16 to 2026-07-19 was first processed with 6.5.6 (it sits in QR2 today) | R7 versions to be released together with DR1 |
| **DR1** | Full R7 reprocessing of Surveys 1 and 2, plus higher-level products | "Late fall 2026". Not in S3 yet; the bucket holds only `qr2/` and `qr3/`. **Could appear mid-hackathon.** |
| DR2 | Surveys 1–4 reprocessed | After year 2 |

✅ **Mixing rules:** never combine QR1 with QR2. Use *caution* combining QR2 and QR3, because the absolute gain changed. IRSA publishes `l3_flux_corrections`, per-pixel factors that put QR2 fluxes on the QR3 gain scale. For position and morphology blinking, mixing is fine. For photometry and light curves, apply the correction.

### 4.2 Anatomy of a Level-2 Spectral Image MEF (✅ real QR3 file plus docs)
One file per (exposure, detector), **≈65–72 MB**:

| HDU | EXTNAME | Type / shape | Units | Notes |
|---|---|---|---|---|
| 0 | PRIMARY | header only | — | `VERSION` (pipeline version) lives here |
| 1 | `IMAGE` | float32 2040² | MJy/sr | Calibrated surface brightness. **Zodiacal light is not subtracted.** Primary WCS: `RA---TAN-SIP` (3rd-order SIP). Alt WCS **A** gives 0-based parent-detector pixels; alt WCS **W** gives wavelength/bandwidth via `WAVE-TAB`. |
| 2 | `FLAGS` | int32 2040² | bitmask | Bit names are self-described in the header: `MSKNnnnn`/`MSKMnnnn` in QR3, **`HIERARCH MP_<NAME> = <bit>` in QR2** (✅ 11-06, F6). In full **QR3** (7.0.5) files on S3 this HDU is a RICE_1 tile-compressed bintable (one-row tiles) (✅ 11-06, F1); in full **QR2** (6.5.5, 6.5.6) files it is a plain int32 image (✅ 11-07, F2). Cutouts deliver it as a plain image. |
| 3 | `VARIANCE` | float32 2040² | (MJy/sr)² | Per-pixel variance. IRSA adds a 3% flux floor for photometry. |
| 4 | `ZODI` | float32 2040² | MJy/sr | Zodiacal-light model (scaled Kelsall). Subtract it yourself. |
| 5 | `EPSF` (QR3) / `PSF` (QR2) | QR3: bintable with 441 zones (451 for D3), each a 33×33 float64 ePSF oversampled 5× plus `XCENTER`, `YCENTER`, `CWAVE`, `CBAND`. QR2: 101×101×121 cube. | — | ≈3.9–4.9 MB. **Included even in tiny cutouts.** |
| 6 | `WCS-WAVE` | bintable 1 row: X(9), Y(9), VALUES(2,9,9) | µm | Bilinear λ/Δλ lookup, good to ≈1 nm, "for visualization". Use `spectral_wcs` `CWAVE`/`CBAND` for science. |

### 4.3 Header keywords that matter (✅ real QR3 header)

| Keyword | Meaning | Use |
|---|---|---|
| `DETECTOR` | 1–6 | Band |
| `OBSID`, `EXPIDN` | Observation ID (`2026W33_2A_0594_4` = planning period, large slew, small slew) | Grouping, dedup |
| `MJD-BEG/AVG/END`, `DATE-AVG`, `XPOSURE` | Timing | Epoch assignment, motion fits |
| `SPS_ELON`, `SPS_ELAT`, `SPS_EPA` | Planned boresight ecliptic lon/lat and PA (**the Supplement calls it `SPS_PA_ECL`, but the real header says `SPS_EPA`**) | Survey number (PA 0 vs 180) |
| `CRPIX1A`, `CRPIX2A` | Cutout origin within the parent detector (0-based parent pixel = 1 + cutout pixel − CRPIXnA) | Look up `CWAVE`, channel map, flux corrections and ePSF zone for cutout pixels |
| `X_SC`, `Y_SC`, `Z_SC` (+ `_START`/`_END`, velocities) | Spacecraft geocentric position (km) | Topocentric parallax for Solar System objects |
| `FINAST` | 0 = good fine astrometry | Reject frames with poor astrometry |
| `L1DQAFLG`, `L2DQAFLG` | Pass/Fail data-quality outcomes | Frame QA badge |
| `PSF_FWHM` | Median PSF FWHM in arcsec | PSF matching, detection kernels |
| `OMEGA_MEDIAN` | Median pixel solid angle (arcsec²) | MJy/sr → µJy |
| `HE_AIRGLOW_CONT`, `AURORA_CONT`, `SHUTTLE_GLOW_CONT`, `*_CORR` | Atmospheric contamination indicators | Warning badges |
| `PXSRCMSK`, `L2 N_*` | Fraction of SOURCE-flagged pixels; counts of each flag type | Crowding indicator, QA |
| `NBLMSRCS`, `NSNOWSRC` | Bloomed sources, snowballs | Artifact warnings |

### 4.4 Pixel flags (✅ Supplement Table 16 plus the real FLAGS header)

✅ 11-06 (F6, 280 real FLAGS headers): bit numbers below hold in every release, but the set of planes
depends on the pipeline version. QR2 6.4 defines no BLOOM, CROSSTALK, GHOST*, HALO, SNOWBALL or STREAK
plane (those artifacts are unflagged there); 6.5.6 lacks CROSSTALK and STREAK; QR3 7.0.5 lacks
SATELLITE_HALO. QR2 also defines **PHANTOM (bit 4)** and **REFERENCE (bit 5)**, not listed below.
Across all 3,878 frames of the 5 targets, `L1DQAFLG` and `L2DQAFLG` are `Pass` and `FINAST = 0`
(✅ 11-06, F8).

| Bit | Name | Meaning | Imaging stack | Photometry | **Discovery blink** |
|---|---|---|---|---|---|
| 0 | TRANSIENT | Cosmic ray detected on the ramp (or bloom onset) | mask | — | mask |
| 1 | OVERFLOW | Reached about half full well | keep, flag | keep, flag | **keep** (bright stars) |
| 2 | SUR_ERROR | Onboard error. With TRANSIENT/OVERFLOW it means an early event. | mask | mask | mask |
| 6 | NONFUNC | Permanently dead pixel | mask | mask | mask |
| 7 | DICHROIC | Low throughput at the band 3/4 edge | mask | — | mask |
| 9 | MISSING_DATA | Lost in downlink | mask | mask | mask |
| 10 / 11 | HOT / COLD | Per-exposure bad | mask | mask | mask |
| 12 | FULLSAMPLE | Informational only | ignore | ignore | ignore |
| 14 | PHANMISS | Not correctable | mask | — | mask |
| 15 | NONLINEAR | No reliable nonlinearity correction | mask | mask | mask |
| 17 | PERSIST | Persistence from earlier bright exposure | mask | mask | mask (**persistence mimics transients**) |
| 19 | OUTLIER | Isolated >Nσ pixel *outside known sources* | propagate | — | **show, don't mask** (could be an uncatalogued source) |
| 20 | CROSSTALK | Electrical crosstalk echo | mask | — | mask |
| 21 | SOURCE | Pixel mapped to a *known* catalogue source (incl. known Solar System objects) | propagate | — | **never mask**. A known-source footprint seen in only one visit is a free "known mover" hint. |
| 22–24 | GHOST, GHOST_FPA, GHOST_EXT | Optical ghosts | mask | — | mask |
| 25 | STREAK | Linear streak (satellite). Fast NEO trails can also trigger it. | mask | — | show, don't mask |
| 26–29 | BLOOM, SNOWBALL, HALO, SATELLITE_HALO | Charge bloom, snowballs, halos | mask | mask | mask |

### 4.5 Calibration products we actually need (✅ S3 listing)
Paths are under `s3://nasa-irsa-spherex/qr3/…`, mirrored at `https://irsa.ipac.caltech.edu/ibe/data/spherex/qr3/…`. **Discover the directory names by listing, don't hardcode them.** The docs say `cal-wcs` but the real directory is `cal-swcs-v5-2026-191`.

| Product | Real example | Size | Why |
|---|---|---|---|
| Spectral WCS | `spectral_wcs/cal-swcs-v5-2026-191/6/spectral_wcs_D6_spx_cal-swcs-v5-2026-191.fits` | 33 MB / detector | Exact per-pixel λ (`CWAVE`) and Δλ (`CBAND`). Lets us skip downloading WCS-WAVE. ✅ 11-06 (F1): each L2 file's `WCS-WAVE` table is identical to the one in this file; CWAVE agrees with it to 0.7–2.5 nm (p99) in the same orientation as `IMAGE`, with localised structure up to 96 nm the lookup cannot follow. |
| Spectral channels | `spectral_channels/cal-sch-v2-2026-229/spectral_channels_spx_cal-sch-v2-2026-229.fits` | 4 MB | Pixel → channel 1–17 template, plus channel statistics. ✅ 11-06 (F3): HDU 1 `CHANNEL_MAP` (uint8, `DETECTOR='ALL'`: one map for all six detectors, within ±1 channel of each detector's CWAVE); 0 = blueward of channel 1, 18 = redward of channel 17. HDU 2 `SPECTRAL_CHANNELS`: 102 rows of centre, edges and R. |
| ePSF | `epsf/cal-epsf-v1-2026-191/N/epsf_DN_…fits` (D3 also has `v2`; HDUs `EPSF`, `EPSF_MOSAIC`) | 8 MB / detector | PSF photometry and centroiding. Recommended for QR2 images too. |
| Flux corrections | `l3_flux_corrections/cal-flxc-v1-2026-191/N/…` (HDU `IMAGE`) | 17 MB / detector | Puts QR2 fluxes on the QR3 gain |
| Solid-angle pixel map | `solid_angle_pixel_map/cal-sapm-v3-2026-191/N/…` (HDU `IMAGE`) | 16 MB / detector | Exact MJy/sr → Jy |

✅ 11-07: these five products (25 files, 452 MB, newest version per detector, so D3's ePSF is `v2`) are frozen
in `config/calibration.lock` with size, S3 ETag (= MD5; all single-part) and sha256, `lock_hash
94e18b883fdc9b28`. Every HDU header of every locked file is in `backend/tests/data/real/calib_headers.json`.

### 4.6 Access channels (✅ tested 2026-11-05)

| Channel | Endpoint | Good for | CORS for browsers | Notes |
|---|---|---|---|---|
| SIA2 | `https://irsa.ipac.caltech.edu/SIA?COLLECTION=spherex_qr3&POS=circle+RA+DEC+R` | "Which images cover this point?" | ❌ none | Returns `access_url`, `cloud_access` (S3 bucket/key), `t_min`, `energy_bandpassname`, `em_min/max`. Lags ingest by about a day. ✅ 11-06: repeat `COLLECTION` to query several collections at once. QR2+QR3 for Barnard came back in ≈6 s (1.7 s to first byte) with the same 359 frames TAP finds. **The fastest coverage path.** |
| TAP | `https://irsa.ipac.caltech.edu/TAP/sync`, tables `spherex.plane`, `spherex.artifact`, `spherex.observation`, `spherex.obscore` | Flexible metadata queries (about 10 s per cone, measured) | ❌ none | Gets new data before SIA2 does. ✅ 11-06: even a trivial query took 10–17 s, so the cost is service overhead, not the cone. Use TAP for the release watcher and back-fill, not for interactive requests. |
| Cutouts | `<access_url>?center=RA,DECdeg&size=0.05` (or `pix`/`arcmin`) | Small spatial subsets with all HDUs | ❌ none | Not gzipped. **Always includes the ≈3.9 MB ePSF HDU.** ✅ 11-06: 1–4 s to first byte, an HTTP 503 under 4 parallel requests, and some transfers that stopped early after an HTTP 200 header. `gzip=true` doesn't help. Validate every response by parsing it. ✅ 11-07 (F12, our network, not the deployment region): a 10-minute soak at 4 concurrent stream-aborted 6′ cutouts gave 68 HTTP 503s in 710 requests (9.6%, steady every minute); at 2 concurrent, 9 in 219 (4.1%). No truncations in those 929 requests; p50 ≈3.0 s, ≈200 KB each. So retries with backoff are needed at any concurrency. |
| Browsable dirs | `https://irsa.ipac.caltech.edu/ibe/data/spherex/{qr2,qr3}/…` | Calibration files, bulk | — | Listing pages are JS-rendered. Use the S3 listing instead. |
| AWS S3 | `s3://nasa-irsa-spherex/{qr2,qr3}/…` (us-east-1, anonymous) | Byte-range reads of full files, listings, release detection | ✅ `Access-Control-Allow-Origin: *` (GET/HEAD) | Running compute in us-east-1 keeps egress cheap and fast |
| Python | `astroquery.ipac.irsa`, `pyvo` | Prototyping | — | IRSA tutorial notebooks: intro, cutouts, PSF, Source Discovery Tool |
| GUI | SPHEREx Data Explorer (`irsa.ipac.caltech.edu/applications/spherex`) | Manual inspection; IRSA's spectrophotometry and mosaic tools | — | Use it to cross-check your numbers |

**Supporting services** (all called server-side):

| Service | Endpoint | Use | Status |
|---|---|---|---|
| Gaia DR3 at IRSA | TAP table `gaia_dr3_source` | J2016.0 astrometry for targets; reference stars for re-registration | ✅ 11-06 |
| 2MASS PSC at IRSA | TAP table `fp_psc` (column `jdate` is each source's 2MASS epoch) | Per-target 2MASS epochs | ✅ 11-06 |
| 2MASS images | IBE search `https://irsa.ipac.caltech.edu/ibe/search/twomass/allsky/allsky?POS=ra,dec` → data `…/ibe/data/twomass/allsky/allsky/<ordate><hemisphere>/s<scanno>/image/<fname>?center=…&size=…` | 25-year blink | ✅ 11-06 (cutout returned) |
| AllWISE / NEOWISE images | SIA2 `COLLECTION=wise_allwise` (Atlas coadds) or `neowiser` (single exposures) | WISE-era epochs | ✅ 11-06 |
| SIMBAD | TAP `https://simbad.harvard.edu/simbad/sim-tap/sync` (CfA mirror; the CDS host timed out again on 11-06) | Names, PMs, parallaxes | ✅ 11-06 |
| JPL Horizons | `https://ssd.jpl.nasa.gov/api/horizons.api` with `CENTER='500@-163182'` | Solar System ephemerides **as seen from SPHEREx** | ✅ 11-06 (Pluto) |
| IMCCE SkyBoT | `https://ssp.imcce.fr/webservices/skybot/api/conesearch.php?…&-loc=500` | Known asteroids in a field (geocentric) | ✅ 11-06. The observer parameter is `-loc`; `-observer` is silently ignored. |

✅ 11-06 network check: from our network, IRSA and S3 both delivered only 30–80 KB/s, with 1–2 s per S3 request. ✅ 11-07: 1 MB S3 ranges reached ≈200 KB/s; a 6′ S3 row section (≈3 MB) took p50 ≈14 s here, against ≈2.7 s for the ≈200 KB cutout (F12). Run the backend on a cloud VM, ideally in us-east-1 next to the bucket, so pixel traffic never crosses the venue Wi-Fi.

### 4.7 Data-volume math: the ePSF trap (✅ measured)
A QR3 cutout of 29 × 29 pixels (0.05°) came back as **3,962,880 bytes**. About 3.86 MB of that is the `EPSF` table. ✅ 11-06 byte map of that cutout:
- The PRIMARY header is 2,880 B.
- The IMAGE, FLAGS, VARIANCE and ZODI headers are 23,040, 17,280, 11,520 and 11,520 B. Each is followed by 5,760 B of padded data.
- The `EPSF` header starts at byte **89,280**.

In a full 2040² file, the IMAGE data starts at byte 25,920 and is exactly 5,780 FITS blocks (16,646,400 B, no padding).

Cost for one target with about 360 frames:

| Strategy | Per frame | 360 frames |
|---|---|---|
| Naive IRSA cutouts | ≈4.0 MB | **≈1.4 GB** |
| Stream the cutout, stop after `ZODI` (headers ≈66 KB + 4 × N² × 4 B) | ≈75 KB at 3′; ≈220 KB at 10′ | ≈27 MB at 3′; ≈80 MB at 10′ |
| S3 byte-range read of only the needed rows (4 HDUs) | ≈rows × 8160 B × 4. Whole rows are read, so a 6′ view (≈90 rows with margins) costs ≈3 MB per frame. | Good for large FOVs and in-region (us-east-1) servers. Zero load on IRSA's cutout servers. |

**Conclusion:** cutouts must be fetched and reduced **server-side**. The browser should receive *stacks*, not raw frames.

### 4.8 Citation obligations (✅ IRSA overview page)
Cite DOIs **10.26131/IRSA652** (QR2) and **10.26131/IRSA662** (QR3), and include IRSA's acknowledgement sentence: *"This publication makes use of data products from the Spectro-Photometer for the History of the Universe, Epoch of Reionization and Ices Explorer (SPHEREx), which is a joint project of the Jet Propulsion Laboratory and the California Institute of Technology, and is funded by the National Aeronautics and Space Administration."* Put it on an "About / Credits" page, because it signals rigour to judges.

The other services need credit too:
- the Gaia DR3 (ESA/DPAC), 2MASS, WISE and NEOWISE acknowledgements
- the IRSA acknowledgement
- the CDS lines for SIMBAD and Aladin
- JPL Horizons, IMCCE SkyBoT and AAVSO, if their data appear
- citations for Astropy, reproject and photutils

Copy each text verbatim from its archive's page on day 1. Don't use the NASA insignia or imply NASA endorsement.

---

## 5. The central design problem: what is a "frame"?

### 5.1 Candidate time axes

| Axis | Granularity | Shows | Pitfall |
|---|---|---|---|
| **Exposure** | 113.6 s, about 360 per target | Asteroids (present in 1–few frames), satellites, cosmic rays | Consecutive frames differ in **wavelength**, so brightness changes are mostly spectral. Frames also flip orientation between visits. |
| **Visit / epoch** | About 2 per year (dense at the poles) | **Proper motion, parallax, long-term variability** | Few frames, small motion |
| **Survey** | S1–S4 | Same as visits, labelled by the mission | Interleaved order confuses users |
| **Fixed time bin** | e.g. 7–30 days | Deep fields and polar targets (R Dra light curve) | Needs enough frames per bin |
| **Long-baseline, multi-mission** | 2MASS (1997–2001; each target has its own epoch, §8.1) → WISE (2010) → NEOWISE (…2024) → SPHEREx (2025–) | The most dramatic motion; the Planet X/brown-dwarf hunting mode | Different PSFs and bands, so normalise display |

**Default:** visit stacks per band, with the auto-stretch shared across frames. **Expert modes:** exposure flipbook (sorted by time *or* by wavelength), fixed bins, and multi-mission blink.

### 5.2 Why naive exposure blinking misleads
Within a visit, a star's 20-odd frames in band 4 sample 2.42–3.82 µm. A T dwarf such as ε Indi B is *dark* at 3.3 µm (methane) and bright at 3.8 µm. In an exposure-order animation it will **pulse**, and a member of the public will call it variable. Two fixes:
- **Sort by wavelength** and call it a *spectral flipbook*, a feature in its own right ("watch the brown dwarf fade at 3.3 µm").
- **Stack by visit** before comparing epochs.

### 5.3 Wavelength-matched difference imaging (the rigorous way to subtract epochs)
Visit stacks are fair broadband images, but two visits can sample slightly different channel mixes. Surveys 3 and 4 are also offset by half a channel. A source with a steep spectrum can then show a false residual.

There is a second, subtler problem. Consecutive visits are rotated 180° (§3.3), so **the LVF wavelength gradient runs in opposite sky directions in the two visits**. If frames are paired by λ at the target, the mismatch elsewhere in the view grows with distance from the target. It changes by two channels per channel-width of offset (≈12′), which is already half a channel 3′ from the centre. The rigorous approach therefore matches wavelengths **per pixel**:
1. Reproject each frame *and its λ map* (`CWAVE`, located with the `CRPIXnA` offsets) to the common grid.
2. For each visit and band, bin every pixel's samples by the wavelength that pixel saw: 17 bins equally spaced in ln λ, one per channel. The result is a per-visit **spectral cube** with about one sample per bin per pixel.
3. For each pixel, **interpolate** visit B's spectrum to the exact wavelengths visit A sampled, linearly in ln λ between neighbouring bins. This also removes the half-channel S1/S2 ↔ S3/S4 offset, which no frame pairing can remove.
4. Subtract bin by bin, propagate the variances, and combine the bin differences with weights.

✅ 11-06 synthetic test: we used a steep-spectrum star (×4 across band 4), the gradient reversed, and the half-channel offset. Pairing frames at the target left a **6σ** false residual at the centre and **10–13σ** 2–4′ away. Per-pixel interpolation stayed at the noise level everywhere (implementation.md §4.6).

Frame pairing by nearest ln λ at the target (Hungarian assignment, pairs within **0.75 channel**) is still fine for *target-only* work, such as spectra and the target's own pixels. It needs one of two conditions: both visits come from the same survey family (S1↔S2 or S3↔S4, which share channel centres), or the target is faint.

Static stars cancel channel by channel. **Movers leave dipoles** (+ at the new position, − at the old). **Variables leave monopoles.** **New sources leave positive monopoles.** The same spectral cube also drives the λ-scrubber and per-pixel spectra (implementation.md §4.6).

### 5.4 Keeping the stretch honest
A blink is only meaningful if every frame uses the **same display transfer function**. Compute ZScale/percentile limits once, on the median stack, and apply them to all frames. Per-frame auto-stretch creates flicker that looks like variability.

---

## 6. Motion in SPHEREx's viewing geometry

### 6.1 Quadrature geometry: a gift for parallax
SPHEREx always looks roughly **90° from the Sun** (dawn–dusk orbit, Sun-avoidance limits). A given sky point is therefore observed near *western* quadrature and, about six months later, near *eastern* quadrature.
```
                 distant object (ecliptic longitude λ)
                              ▲
                              │  line of sight ≈ parallel to Earth's velocity
                              │  at both visits
     Earth at visit A ●───────☉───────● Earth at visit B
                      ◄──── 2 AU baseline, ⟂ to line of sight ────►
```
Consequences:
- **Each visit catches the object at a parallax extreme.** Between visits the parallactic shift is about **2ϖ** (Barnard: 1.09″), alternating in sign. Proper motion grows linearly. With **3 visits, PM and parallax separate** (a zig-zag on top of a line). With 4+ visits, SPHEREx alone could measure parallaxes of the nearest stars and brown dwarfs. WISE used the same geometry for brown-dwarf parallaxes.
- **Distant Solar System bodies are stationary in ecliptic *longitude* during a visit, but not in latitude.** At quadrature, Earth's velocity points along the line of sight's longitude, so there is no reflex motion in longitude. For a body at ecliptic latitude β, the part of Earth's velocity perpendicular to the line of sight is v⊕·sin β, directed along latitude. The body therefore drifts in latitude at ϖ·sin β per radian of Earth's orbit, which is ≈ ϖ·sin β·0.24 over 14 days. Between visits it **jumps by about 2 AU/d** in longitude. The table comes from a ✅ 11-06 vector calculation; the sin β formula matches it to better than 1%:

| Distance | Jump between visits (≈2 AU/d, along longitude) | Drift within a 14-day visit at β = 20° (along latitude) |
|---|---|---|
| 1 pc star | 2″ | ≈0 |
| 40 AU (Kuiper belt) | ≈2.9° | ≈7′ (69 px) |
| 300 AU (Planet X) | ≈23′ | ≈57″ (9 px) |
| 500 AU | ≈14′ | ≈34″ (5.5 px); only ≈9″ at β = 5° |
| 800 AU (Planet X) | ≈8.6′ | ≈21″ (3.4 px) |

So **a Planet X would appear as an "orphan" in each visit**: a source with no counterpart at the same spot in other visits. It is displaced mostly along ecliptic longitude by 2 AU/d, plus a small orbital term of ≈1′ per 6 months at 500 AU. Within a visit it **smears along latitude** unless β ≈ 0. A whole-visit stack therefore dilutes it, but **per-day stacks** (one target group each) keep it point-like. The latitude drift rate is itself a distance measurement. The search algorithm has two steps, both parametrised by distance:
1. Link per-day orphans within a visit along the predicted latitude drift.
2. Link those tracks across visits with the predicted longitude jump.

FOVs of ≥15–30′ are needed, which is exactly the "larger FOV tracks faster sources" trade-off the challenge mentions. Validate the method on known dwarf planets (§2.4) before showing it.

### 6.2 What each class of mover looks like (**≈**)

| Class | Within one exposure (113.6 s) | Within a visit | Between visits | How to catch it |
|---|---|---|---|---|
| Nearby high-PM star | static | static | μ·Δt ± 2ϖ (≤ ≈2 px) | Visit difference → **dipole**. Centroid track vs Gaia prediction. |
| Cold brown dwarf | static | static | ≤ ≈1.5 px | As above, plus **colour**: bands 5–6 ≫ bands 1–3, CH₄ dip at 3.3 µm |
| Main-belt asteroid (≈10–60″/hr near quadrature; ✅ 11-06 SkyBoT: 25–39″/hr near RW Aur) | ≲2″, point-like | Seen in one target group (minutes to an hour), gone the next day | gone | **Single-visit/single-day orphans.** Sigma-clipping rejects them from stacks, and the rejected pixels *are* the detections. Label known ones with SkyBoT. Only V ≲ 18.5 shows in a single frame **≈**, and most catalogued asteroids crossing a small field are far fainter. |
| NEO (arcmin–deg/hr) | can **trail** | one or a few frames | gone | Trails, possible `STREAK` flags |
| Comet | fuzzy | like asteroids | gone | Coma. Spectra show **CO₂ at 4.26 µm**, H₂O and CO. SPHEREx observed interstellar comet **3I/ATLAS** in Aug 2025. |
| TNO / Centaur | static | drifts ≈arcminutes | jumps degrees | Orphans in large FOVs |
| Variable star / YSO | static | static (except fast YSOs) | flux change | **Monopole** in difference images. Light curves. |
| Satellite | streak | one frame | gone | `STREAK` / `SATELLITE_HALO`. Reject. |

### 6.3 False movers (and how to reject them)
- **Persistence:** a bright star from a previous exposure leaves a ghost image at fixed *detector* coordinates, which wanders on the sky. `PERSIST` flag.
- **Crosstalk:** negative echoes **32 rows** away and positive echoes at **multiples of 64 columns** from bright stars (✅ Supplement Fig. 9). ε Indi A (K≈2.2) is **402″ ≈ 65 px** from ε Indi B, so a 64-column echo could fall near B in some orientations. Check `CROSSTALK`.
- **Ghosts:** frame-edge triangles, ≈10′ beam-splitter disks (bands 3–6), linear ghosts, and an "8° ghost" from very bright stars.
- **Snowballs, bloom and cosmic-ray halos:** flagged since pipeline 6.5 / R7.
- **Atmospheric lines:** He 1.083 µm (bands 1–2, up to 30× zodi), aurora (mostly N₂, bands 1–2), and shuttle glow (≈2.9 and ≈4.5 µm). Other lines appear at 0.78, 0.84, 0.93, 1.13, 1.81, 2.63, 2.75, 4.03 and 4.64 µm. These vary orbit to orbit and can make whole frames change brightness. Fix: subtract a local background after the zodi model.
- **Moon stray light** at detector edges in bands 1, 4, 5 and 6, and **diffuse optical transients** in about 1% of exposures.

---

## 7. Spectral science in 0.75–5 µm (what "spectra on the fly" can reveal)

| Feature | λ (µm) | Where it matters | Band |
|---|---|---|---|
| H₂O (stellar/BD atmospheres) | 1.15, 1.4, 1.9, 2.7 | M/L/T dwarfs, Miras | 1–4 |
| CH₄ | 1.6, 2.2, **3.3** | **T and Y dwarfs** (deep 3.3 µm trough); giant planets | 2–4 |
| CO | 2.29 bandhead, **4.6–4.7** | Cool stars, Miras, YSOs; comets | 3, 6 |
| CO₂ | **4.26** | Ices toward YSOs; comet comae (3I/ATLAS) | 5 |
| H₂O ice | **3.05** (broad) | Molecular clouds, YSO envelopes (SPHEREx core science) | 4 |
| CO ice | 4.67 | Cold clouds | 6 |
| PAH | 3.3 | Star-forming regions, galaxies | 4 |
| H recombination | Paβ 1.282, Paα 1.875, Brα 4.05 | Accretion in YSOs (RW Aur), H II regions | 2, 3, 5 |
| Hydrated minerals | ≈2.7–3.1 | C-type asteroids | 4 |
| Thermal tail | > ≈3.5 | NEOs (warm) vs reflected light | 4–6 |

**Brown-dwarf signatures (central to "Planet X" hunting):**
- **L dwarfs:** red, smooth, with CO.
- **T dwarfs:** CH₄ at 1.6/2.2/3.3 µm and a strong 4–4.5 µm peak.
- **Y dwarfs** (WISE 0855, about 285 K): essentially nothing below about 3.5 µm and a peak at 4–4.6 µm.

Simple derived indices give the public a one-number "is it cold?" meter:
- A **methane index** F(3.3)/F(4.1), in F_ν. A Rayleigh–Jeans star gives ≈1.5, and T and Y dwarfs give ≪ 1. The two points come from different detectors, so calibrate against field stars in the same view rather than using a fixed cut.
- **Synthetic W1−W2**, integrating channels over WISE W1 (≈3.4 µm) and W2 (≈4.6 µm) bandpasses

---

## 8. The five test targets, in depth

### 8.1 Summary (✅ SIMBAD via the CDS Harvard mirror; positions propagated linearly with PM)

| Target | Type | Position, ICRS, epoch **J2000.0** | PM (mas/yr) | ϖ (mas) | J / H / K (Vega) | Position at **2026.87** (hackathon) | Shift since J2000 |
|---|---|---|---|---|---|---|---|
| Barnard's Star | M4V, 1.83 pc | 269.45208, +4.69336 | −801.6, +10362.4 (**10.39″/yr**) | 547.0 | 5.24 / 4.83 / 4.52 | **17h57m47.06s +04°46′14.6″** | 279″ = **45 px** |
| ε Indi B (Ba+Bb) | T1 + T6 binary (0.7″ apart, unresolved), 3.7 pc | 331.04415, −56.78284 | +3982.0, −2466.8 (**4.68″/yr**) | 270.7 | 11.91 / 11.31 / 11.21 | **22h04m23.62s −56°48′04.5″** | 126″ = 20 px |
| WISE 0855−0714 | Y dwarf (~285 K), 2.28 pc | 133.81891, −7.24705 | −8123.7, +673.2 (**8.15″/yr**) | 439.0 | J ≈ 25.0, H ≈ 23.8; W2 ≈ 14.0 | **08h55m01.87s −07°14′31.3″** | 219″ = 36 px |
| RW Aurigae | Classical T Tauri binary (K1/5e + K5e), **≈156 pc** | 76.95653, +30.40144 | +7.2, −20.3 ¹ | **6.41** ¹ | 8.38 / 7.62 / 7.02 | (static) | 1″ |
| R Draconis | Mira, M4.5–6e, P ≈ 245 d | 248.16761, +66.75498 | −20.6, +6.1 | 1.25 | 3.71 / 3.13 / 2.23 | (static) | 1″ |

¹ ✅ 11-06: SIMBAD's RW Aur parallax (15.42 ± 3.69 mas) and proper motion come from the 2007 Hipparcos reduction and are wrong for this binary. Gaia DR3 resolves the pair:
- **RW Aur B** (`156430822114424576`, RUWE 1.5): ϖ = 6.41 ± 0.04 mas, PM (+2.6, −27.4) mas/yr.
- **RW Aur A** (`156430817820015232`, 1.5″ away at PA ≈ 253°): RUWE 16, so its astrometry is unusable.

B's distance fits the 130–160 pc of Taurus–Auriga.

**Epochs, names and the best astrometry** (✅ 11-06):

| Target | Query SIMBAD as | Best astrometry | 2MASS epoch (`fp_psc.jdate`) | 2MASS → Aug 2026 jump |
|---|---|---|---|---|
| Barnard's Star | `Barnard''s Star` (quote escaped) → `NAME Barnard's star` | Gaia DR3 4472832130942575872, J2016.0, RV −110.5 km/s | 2000-05-28 (2000.41) | **4.55′** |
| ε Indi B | `eps Ind B` → `* eps Ind B` | Gaia DR3 6412596012146801152 (G = 18.0, ϖ = 270.66 ± 0.69 mas; Ba+Bb photocentre) | 1999-11-07 (1999.85) | 2.1′ |
| WISE 0855−0714 | `WISE J085510.83-071442.5` → `WISEA J085510.74-071442.5`. **`WISE 0855-0714` does not resolve.** | Kirkpatrick et al. 2021 via SIMBAD (J2000, linear) | not detected (J ≈ 25) | AllWISE (≈2010.5) → 2.2′ |
| RW Aurigae | `RW Aur` → `V* RW Aur` | Gaia DR3 (see ¹) | 1999-11-26 (1999.90) | static |
| R Draconis | `R Dra` → `V* R Dra` | Gaia DR3 1648328016354496384 (ϖ = 1.25 ± 0.06 mas) | 1999-05-26 (1999.40; ✅ 11-07) | static |

✅ 11-07: the dates above are local observing nights; in UT, ε Ind B is 1999-11-08 02:43 and RW Aur
1999-11-27 07:00. The decimal-year epochs are unchanged (`backend/tests/data/real/recorded/catalogs`).

> ⚠️ **The challenge's WISE 0855 coordinate (08h55m10.831s −07°14′42.53″) is its ≈2010.45 position, the WISE discovery epoch.** It is neither J2000.0 nor current. By Nov 2026 the dwarf is **≈134″ west** of it (≈22 px), outside any small cutout centred on the given coordinate. Use a FOV ≥ 6′ there, or better, **track mode**, which centres each epoch on the PM-propagated position.

### 8.2 Barnard's Star: "the fastest star in the sky"
- **Motion across SPHEREx data:** between the first and last full visits (Aug 2025 → Aug 2026, 1.0 yr) it moves **10.4″ ≈ 1.7 px** north. Parallax cancels because both visits sit at the same quadrature. The March 2026 visit sits 2ϖ ≈ 1.1″ off that line, a ±0.55″ zig-zag. At Barnard's position the zig-zag runs east–west, perpendicular to the northward PM, so the two separate cleanly. Counting the Sep 2026 partial cluster, the span is 1.1 yr (**11.5″ ≈ 1.9 px**). This is the cleanest motion demo.
- **Brightness:** J_AB ≈ 6.2. Expect `OVERFLOW` and possibly **NaN cores in bands 1–4 ≈**. Band 6 is likely cleanest. Centroid on PSF wings with an ePSF fit that excludes NaN and overflow pixels, and show the flag overlay so users understand the "hole".
- **Wow factor:** a **2MASS (2000-05-28, ✅ 11-06) → SPHEREx (Aug 2026) blink** shows a **≈4.55′ (44 px)** jump. Use a FOV of at least 8′. That makes the most compelling 5 seconds of the demo.
- **Astrometry source:** propagate Gaia DR3 (J2016.0) with its RV of −110.5 km/s; the perspective acceleration adds ≈0.4″ over 26 years. SIMBAD's J2000 position is a *linear* back-propagation of the same Gaia data, so propagate it linearly. ✅ 11-06: Gaia+RV and SIMBAD-linear both give +04°46′14.6″ at 2026.87, but SIMBAD+RV gives 15.0″.
- **Validation:** the fitted PM should match Gaia (10.39″/yr, PA ≈ 356°) within errors. **Stretch goal:** detect the parallax zig-zag (amplitude ±0.55″ against an expected centroid error of ≈0.1–0.3″ per visit **≈**).

### 8.3 ε Indi B: "two brown dwarfs, one dot"
- At 6.15″ pixels the T1 + T6 pair (≈0.7″) is a single source. It is moderately bright (K_AB ≈ 13.1), so expect high S/N in every band.
- ✅ 11-06: the pair's photocentre is in Gaia DR3 (`6412596012146801152`, G = 18.0, ϖ = 270.66 ± 0.69 mas), so propagate from Gaia. Its 2MASS epoch is 1999-11-07, giving a ≈2.1′ jump to 2026.
- **Motion:** 4 visits over 1.44 yr → **6.7″ ≈ 1.1 px**.
- **Spectrum:** the best showcase for **spectra on the fly**. Expect a methane trough at **3.3 µm** and a 4.0–4.2 µm peak typical of T dwarfs, plus H₂O/CH₄ structure at 1.1–2.2 µm. Overlay T1/T6 templates (SpeX Prism Library) for a convincing classification.
- **Pitfall:** the primary **ε Indi A** (K5V, K ≈ 2.2) is **402″ (65 px)** away. Watch for ghosts, bloom and possible 64-column crosstalk echoes. The scene is a natural "artifact literacy" lesson.

### 8.4 WISE 0855−0714: "the coldest known brown dwarf"
- **≈285 K (≈12 °C)** from JWST spectroscopy (Luhman et al. 2024). The popular "as cold as the North Pole" line belongs to the original 225–260 K estimate (Luhman 2014), so don't mix the two. W2 ≈ 14.0 (Vega) → **≈17.3 AB ≈ 0.42 mJy at 4.6 µm**. Invisible at < 3.5 µm (J ≈ 25).
- **Name trap:** ✅ 11-06: SIMBAD's main ID is `WISEA J085510.74-071442.5`. It resolves `WISE J085510.83-071442.5` but **not** `WISE 0855-0714`, which is what people type and what our own example URLs use. Ship an alias table.
- **SPHEREx detectability ≈:** per channel in band 6, a single frame gives S/N of only a few. A **band-6 visit stack** of either full visit (16 and 21 frames, ✅ 11-06) should reach roughly 5–15σ, with band 5 adding a little more. The 3-frame partial visits reach only ≈2–5σ. This is the target that *proves* why per-detector coadds matter. Show bands 1–3 as empty, bands 5–6 as a dot that moves, and a methane/W1−W2 meter reading "very cold".
- **Motion:** ✅ 11-06: the archive holds **two full visits**, Oct 31–Nov 14 2025 and Apr 21–May 14 2026. Between them the dwarf moves **≈4.8″ ≈ 0.78 px toward PA ≈ 277°**: 3.9″ of proper motion plus 0.9″ of parallax in nearly the same direction. The partial May 2025 cluster (3 band-6 and 8 band-5 frames) stretches the baseline to 1.02 yr and **8.1″ ≈ 1.3 px**, with the parallax cancelling May to May, but at low S/N. There are no QR3 frames yet, and the autumn-2026 visit will very likely miss the hackathon. Plan the demo around the 0.78 px shift, a dipole fit and the long-baseline blink. Check again on Nov 13–14.
- **Long-baseline mode:** WISE W2 (2010) → SPHEREx band 6 (2026) gives about **2.2′**, which is unmistakable.
- **Pitfall:** it is not in Gaia. ✅ 11-06 (F6): the `SOURCE` plane marks its **propagated (current)** position in every band, even bands 1–3 where it is invisible, and not its WISE-era position, so the reference catalogue carries its proper motion. Its pixels are therefore SOURCE, never OUTLIER. Discovery mode must still never mask SOURCE.
- **Pitfall (✅ 11-07): a 2MASS source sits near its 2MASS-era position.** 2MASS 08551654−0714457 (K = 15.8,
  J = 16.7) lies 3.6″ from WISE 0855's J2000 position and ≈9″ from its 1999 position. WISE 0855 itself has
  J ≈ 25. A positional cross-match alone would wrongly give it a 2MASS epoch, so match on brightness too
  (`external/twomass.py::epoch_of`, `k_expected`).
- **Pitfall (✅ 11-06, real stacks): a field star sits on it.** Gaia DR3 5756956644387831296 (G = 16.3, static) is 8.3″ (1.35 px) from WISE 0855 in Nov 2025 and 4.2″ (0.7 px) in Apr–May 2026. Bands 1–3 are **not** empty at its pixel (that star shows at 7–45σ), and a one-source band-6 centroid is pulled toward the star by ≈0.1–0.3 px. Photometry, the 0.78 px displacement and the "empty below 3.5 µm" story need a two-source model.

### 8.5 RW Aurigae: "a young star behind shifting dust"
- A classical T Tauri binary (A+B ≈1.5″ apart per Gaia, unresolved by SPHEREx) in Taurus–Auriga, at ≈156 pc (§8.1 note ¹). Known for **deep optical dimming episodes since 2010**, caused by dust crossing the line of sight to RW Aur A, with accompanying changes in near/mid-IR excess. Check AAVSO for its current state.
- K_AB ≈ 8.9, so expect `OVERFLOW` flags in some channels.
- **Show:** a per-visit light curve per band and **per-visit spectra overlaid**. Look for changes in the 2–5 µm excess, Brα 4.05 / Paα 1.875 emission (accretion), and the 3 µm region.
- **Bonus, with care:** β = 7.5° means **asteroid traffic**, but most of it is too faint. ✅ 11-06: SkyBoT found three asteroids within 15′ on a sample date, all at V = 22.6–24.1, while single frames reach only V ≲ 18.5 **≈**. Use SkyBoT to *pick* frames where a V < 17 asteroid crosses a ≥30′ field, then demo "orphan" detection on those.

### 8.6 R Draconis: "a breathing giant"
- A Mira variable with a period of about **245 days**. V varies over ≈6.7–13.2. Near-IR amplitude ≈1 mag.
- **Very bright** (K_AB ≈ 4.1), so expect saturated, NaN cores, bloom and ghosts in most bands. The tabulated ePSF only spans ±3.3 native pixels, so it cannot model far wings. Measure **same-channel annulus ratios** instead: the flux in a fixed 3–6 px annulus, compared only between frames where R Dra fell in the same channel and detector region, so the PSF shape cancels. Label the result relative and qualitative.
- **Coverage is superb:** ≈2,480 frames (≈1,950 from the deep-field collections), near-continuous over ≈520 days (> 2 cycles), thanks to the NEP deep field and the polar survey geometry. Use **14-day bins**, a Lomb–Scargle periodogram (expect ≈245 d), and phase-folded light curves. Spectra versus phase should show changing **H₂O and CO band depths**.
- Validate against the AAVSO light curve, and the VSX period.

---

## 9. Landscape: existing tools and the gap

| Tool | What it does | Why it doesn't solve this challenge |
|---|---|---|
| **IRSA SPHEREx Data Explorer** | Spectral Image Search (Firefly viewer), **Spectrophotometry Tool** (Tractor forced photometry with ePSF), **Mosaic Tool** (per-channel cubes, all-sky survey only, ≥ 9″ pixels) | Expert UI. No time-domain blink, no difference imaging, not embeddable, no public storytelling. *Use it to validate our spectra and photometry.* |
| IRSA notebooks: Intro, Cutouts, PSF, **Source Discovery Tool** (image subtraction for red sources, SExtractor, bokeh) | Recipes | Python/Jupyter, not a public web tool. *Great reference code.* |
| **WiseView** / Backyard Worlds flipbooks | unWISE time-series blink | No SPHEREx and no spectra. *UX benchmark.* |
| Aladin Lite v3 (CDS) | Embeddable HiPS sky atlas, catalogue overlays | No SPHEREx time series. *Use it for context and overlays.* |
| Firefly (IPAC), JS9 (SAO) | Browser FITS viewers | Generic, heavy. Not designed for blinking. |
| Public GitHub projects | At least one repo with a similar aim ("spherex-motion-explorer") appeared on 2026-11-02 | Expect competitors. Differentiate on correctness and UX. |

**The gap:** a **public, embeddable, time-correct SPHEREx blinker** that makes 1–2 px motions obvious and unlocks the 102-band spectral dimension in one click.

---

## 10. What judges will likely reward
Space Apps has historically judged on **Impact, Creativity, Validity, Relevance and Presentation**. Confirm against the 2026 guide.

| Criterion | How we score |
|---|---|
| **Relevance** | Hits every objective and all 5 targets on day one. Uses SPHEREx as primary data, Gaia and WISE as overlays. |
| **Validity** | Proper-motion epoch handling. Wavelength-aware differencing. Flag literacy. Fitted PMs match Gaia. Spectra cross-checked with IRSA's photometry tool. Correct citations. |
| **Creativity** | Spectral flipbook. λ-scrubber. Methane "coldness meter". Orphan-linking Planet X mode. Multi-mission 25-year blink. Spectrum sonification. |
| **Impact** | Citizen-science-ready (shareable URLs, embeds, "report a candidate"). Updates automatically with weekly data. Reusable by IRSA, Backyard Worlds and teachers. |
| **Presentation** | A 30-second story: "Pluto was found with a blink comparator in 1930. Here's the 2026 version, in 102 colours" → Barnard's Star leaps → WISE 0855 appears only at 4.6 µm → spectra prove it's cold → (if built) Pluto itself, tracked as SPHEREx saw it, showing its methane ice. |

---

## 11. Open questions to re-verify when the Resources tab opens (Nov 13)
1. Do NASA's listed resources point to anything new, such as a SPHEREx HiPS, a DR1 collection name, or a recommended API?
2. Has **DR1** landed? What are its SIA collection names, and do QR2 frames become superseded? (✅ 11-06: not yet. S3 holds only `qr2/` and `qr3/`. ✅ 11-07: unchanged; `scripts/refresh_check.py` checks it.)
3. Has WISE 0855's autumn-2026 QR3 visit appeared? (✅ 11-06: no. The newest QR3 period is `2026W40_2A`, so expect "no" on Nov 14 too. ✅ 11-07: still `2026W40_2A`; WISE 0855 still 256 QR2 frames.)
4. Re-check the 2026 **participant rules**: pre-event work, AI-use disclosure, the submission format (historically a ≤30 s video or ≤7 slides plus a project link), and whether submissions can be edited until the deadline.
5. Confirm IRSA endpoint health and latency from the demo venue's network. Prepare an offline snapshot. (✅ 11-06 from our network: 30–80 KB/s, and a cutout 503 under 4 parallel requests.)
6. Confirm `CWAVE` orientation matches `IMAGE` pixels (both should be `DETCOORD='sky'`). Spot-check against `WCS-WAVE` on one full file.
7. Read the headers of the `l3_flux_corrections`, `spectral_channels` and `epsf` products. Do the flux factors multiply or divide QR2 fluxes? Which HDU holds the channel map? Is the ePSF normalised, and is it oriented like `IMAGE`?
8. Does Horizons' TLE-based SPHEREx orbit (body −163182) agree with the header `X_SC/Y_SC/Z_SC` to within ≈10 km? If so, use Horizons for every SPHEREx-centric ephemeris.
9. Is there a survey-number keyword in the headers or archive tables? If so, it replaces the PA-and-date derivation.

---

## 12. Glossary
- **AB magnitude:** m_AB = −2.5 log₁₀(F_ν / 3631 Jy).
- **Blink:** alternating display of aligned images taken at different times.
- **Channel:** one of 17 narrow-band regions per detector. 102 in total.
- **Co-aligned detector pair:** D1+D4, D2+D5 or D3+D6, the two detectors on either side of the dichroic that see the same sky in one exposure.
- **Dipole:** the +/− pair a moving source leaves in a difference image.
- **ePSF:** effective PSF, the optical PSF convolved with the pixel response. Oversampled 5×, tabulated in zones across the detector.
- **Epoch (astrometric):** the date at which a catalogue position applies (J2000.0 for SIMBAD, J2016.0 for Gaia DR3).
- **HiPS:** Hierarchical Progressive Survey, an all-sky tiled image format used by Aladin.
- **LVF:** linear variable filter.
- **MEF:** multi-extension FITS.
- **PA:** position angle.
- **Parallax factor:** the coefficients (P_α*, P_δ) that turn a parallax ϖ into a displacement at a given time. They are set by the observer's barycentric position.
- **Partial visit:** a short cluster of 2–30 frames near a main visit. Too shallow to blink as an epoch, but useful for astrometry.
- **Planning period:** a ≈3.5-day survey plan ID, such as `2026W33_2A`.
- **QR / DR:** Quick Release / Data Release.
- **Quadrature:** 90° from the Sun as seen from Earth, which is roughly where SPHEREx always looks.
- **SIP:** Simple Imaging Polynomial, the distortion terms in the WCS.
- **SUR:** sample-up-the-ramp readout.
- **Visit:** a contiguous cluster of observations of a sky point (≈1–3 weeks), recurring about every 6 months.
- **ZODI:** zodiacal-light model layer.

## 13. References
- Challenge page: https://www.spaceappschallenge.org/2026/challenges/planet-x-and-spherex/
- *SPHEREx Explanatory Supplement* (SSDC-DP-017) v2.0, 2026-08-25: https://irsa.ipac.caltech.edu/data/SPHEREx/docs/SPHEREx_Expsupp_QR.pdf
- SPHEREx Archive at IRSA, data access and products: https://caltech-ipac.github.io/spherex-archive-documentation/
- SPHEREx QR overview, DOIs and acknowledgement: https://irsa.ipac.caltech.edu/data/SPHEREx/docs/overview_qr.html
- IRSA cutout service: https://irsa.ipac.caltech.edu/ibe/cutouts.html · SIA2: https://irsa.ipac.caltech.edu/ibe/sia.html
- IRSA tutorials: https://caltech-ipac.github.io/irsa-tutorials/ (spherex-intro, spherex-cutouts, spherex-psf, spherex-source-discovery-tool-demo)
- AWS Open Data, SPHEREx QR: https://registry.opendata.aws/spherex-qr/
- SPHEREx pipeline paper: arXiv:2511.15823
- SIMBAD TAP (CORS-enabled mirror used): https://simbad.harvard.edu/simbad/sim-tap
- Backyard Worlds: https://backyardworlds.org · WiseView (Caselden et al. 2018, ASCL)
- Aladin Lite v3: https://aladin.cds.unistra.fr/AladinLite/
- WISE 0855: Luhman 2014, ApJL 786, L18 (discovery) · Luhman et al. 2024, AJ 167, 5 (JWST spectrum, ≈285 K) · Kirkpatrick et al. 2021, ApJS 253, 7 (the astrometry SIMBAD uses)
- van Leeuwen 2007, A&A 474, 653 (Hipparcos reduction; the source of SIMBAD's RW Aur parallax)
- Planet Nine: Fortney et al. 2016, ApJL 824, L25 (spectra, 4–5 µm window) · Meisner et al. 2018, AJ 155, 166 (WISE search)
- JPL Horizons API: https://ssd-api.jpl.nasa.gov/doc/horizons.html · IMCCE SkyBoT: https://ssp.imcce.fr/webservices/skybot/
- IRSA IBE, including 2MASS images: https://irsa.ipac.caltech.edu/ibe/

---

## 14. Revision log (2026-11-06)

A second verification pass ran live queries against IRSA (TAP, SIA2, cutouts, IBE), the S3 bucket, SIMBAD, Gaia DR3, 2MASS, JPL Horizons and SkyBoT, plus a rigorous space-motion calculation. It changed the following:

| # | Was | Now | Evidence |
|---|---|---|---|
| 1 | One exposure measures a star at six wavelengths ("one per detector") | **Two**: a short-wave detector and its co-aligned long-wave partner (D1+D4, D2+D5, D3+D6) | TAP: 178 of 181 exposures covering Barnard's Star have exactly one such pair |
| 2 | WISE 0855: 3 visits over 1.02 yr, 1.4 px | 2 full visits 0.78 px apart (PM plus parallax). The 1.3 px one-year baseline relies on a 3-frame partial visit. | TAP per-visit, per-detector counts; parallax-factor calculation |
| 3 | 2MASS epoch "≈1998"; Barnard 2MASS→2026 jump ≈4.9′ | 2000-05-28 and **4.55′**. ε Ind B: 1999.85, 2.1′. RW Aur: 1999.90. | IRSA `fp_psc.jdate` |
| 4 | RW Aur ϖ = 15.4 mas, next to "~140 pc" | ϖ = 6.41 mas (Gaia DR3, component B), ≈156 pc. SIMBAD's value is from Hipparcos 2007. | SIMBAD `plx_bibcode`; IRSA `gaia_dr3_source` |
| 5 | WISE 0855 "285 K, as cold as Earth's North Pole" | 285 K ≈ 12 °C (JWST). The North Pole line belongs to the old 225–260 K estimate. | Literature |
| 6 | Distant bodies are "near-static within a visit" | Stationary in longitude only. They drift ϖ·sin β·(2π/yr) in latitude, e.g. 5.5 px in 14 days at 500 AU and β = 20°. Planet X search needs per-day stacks. | Vector calculation |
| 7 | λ-matched differencing pairs frames at the target; tolerance 1/(2R) here and 0.75/R in implementation.md | Per-pixel matching with spectral cubes, because the LVF gradient reverses between PA 0° and 180° visits. Pairing tolerance is 0.75 channel everywhere. | Geometry |
| 8 | Names are resolved by sending them to SIMBAD as typed | Escape quotes (`Barnard's Star` broke the query). `WISE 0855-0714` doesn't resolve, so ship an alias table. | SIMBAD TAP tests |
| 9 | Propagate SIMBAD J2000 positions with RV | SIMBAD J2000 is linear from Gaia. Propagate it linearly, or use Gaia J2016.0 plus RV. The two disagree by 0.4″ for Barnard. | Rigorous space-motion calculation |
| 10 | Planet X mode had no validation set | Pluto, Makemake, Haumea and Eris via Horizons, with SPHEREx (−163182) as the observer | Horizons API test |
| 11 | Asteroid "traffic" at RW Aur assumed visible | SkyBoT shows mostly V = 22–24 objects. Pick frames where a bright one passes. | SkyBoT test |
| 12 | Archive status as of 11-05 | DR1 is not in S3. The newest QR3 period is `2026W40_2A`. WISE 0855 is still QR2-only. | S3 listing; TAP |
| 13 | Coverage via TAP (≈10 s) | SIA2 with several collections in one call, ≈6 s. TAP costs 10–17 s even for trivial queries. | Timed queries |
| 14 | Overflow onset "K ≲ 7–8" | "K ≈ 7–10; measure it on day 1" (the gain is unknown) | Photon budget |
| 15 | FOV 2′–60′ here vs 2′–30′ in implementation.md; R Dra frame counts disagreed; a firm claim that WISE 0855 is absent from the reference catalogue | Harmonised, clarified and hedged | — |
| 16 | FLAGS planes "self-described as MSKN/MSKM" | QR2 uses `MP_<NAME>`; plane sets differ by pipeline; PHANTOM, REFERENCE exist | F6, `validation/F6/` |
| 17 | Channel-map HDU unknown | HDU 1 `CHANNEL_MAP`, one map for all detectors; 0/18 outside the band | F3, `validation/F3/` |
| 18 | WISE 0855 expected un-masked, maybe OUTLIER | SOURCE at its propagated position; a G = 16.3 star within 0.7–1.35 px during both full visits | F6, `validation/G4b-wise-stacks/` |
| 19 | Overflow onset K ≈ 7–10 (estimate) | Measured K ≈ 9–9.5 in bands 2–4; bands 1, 5, 6 bounded | F7, `validation/F7/` |
| 20 | Unknown QA failure rate | 0 of 3,878 frames fail L1/L2DQAFLG or FINAST | F8, `validation/F8/` |

### 14.1 Revision log (2026-11-07, Role D evidence)

| # | Was | Now | Evidence |
|---|---|---|---|
| 21 | ε Ind B 449 frames (447 SIA2 rows) | 447 in both SIA2 and TAP after dedup; all 5 targets give identical SIA2/TAP frame sets | F11, `validation/F11/` |
| 22 | Full-file FLAGS is RICE_1 | RICE_1 in QR3 7.0.5 full files; plain image in QR2 6.5.x full files | F2, `validation/F2/` |
| 23 | Cutout and S3-section equivalence supported by one frame | Confirmed on QR3, QR2 and QR2-deep frames: same parent-pixel origin, WCS and bit-identical IMAGE/FLAGS/VARIANCE/ZODI | F2 |
| 24 | IRSA 503 under 4 parallel requests (one observation) | 9.6% 503s at 4 concurrent over 10 min; 4.1% at 2; no truncation in 929 requests (our network) | F12, `validation/F12*/` |
| 25 | Calibration directories known by example | Locked: 25 files, sizes, MD5 = ETag, sha256; HDU names (`IMAGE` for flux corrections and solid angle; `EPSF`, `EPSF_MOSAIC`) | `config/calibration.lock`, `calib_headers.json` |
| 26 | R Dra 2MASS epoch "—"; UT vs night dates unstated | R Dra 1999-05-26 (1999.40); ε Ind B / RW Aur UT dates 1999-11-08 / 11-27 | recorded fp_psc responses |
| 27 | — | WISE 0855 2MASS trap: K = 15.8 source 3.6″ from its J2000 position | recorded fp_psc response |

