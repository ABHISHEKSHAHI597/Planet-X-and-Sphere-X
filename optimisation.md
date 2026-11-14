# Optimisation plan: the five judging criteria

Written 2026-11-14 (event day) from the Space Apps judging sheet (*Judging Criteria Template – Team Scores*) and the
repository at `56b852f`. It re-orders the open work by the column of the score sheet it raises. It does not replace
the research notes, the audit action plan or [`submission/`](submission/README.md); it points into them (the notes and audit were removed from the repository before submission; see the git history).

Owners are the role letters of workflow.md §2.1: **D** data, **I** imaging, **M** measurement, **P** platform,
**F** frontend and product. Sizes: **XS** < 30 min · **S** < 2 h · **M** half a day · **L** a day.
H0 is Saturday 14 Nov 09:00; the deadline is Sunday 15 Nov 23:59.

No plan can promise full marks: the sheet itself lets local judges "make your own holistic assessment". What this plan
does is remove every reason a judge has today to take points off, column by column.

---

## 1. What the sheet says

| Column | The judge's questions (verbatim) |
|---|---|
| **Impact** | How much impact (quality and quantity) can this project have? Does it solve a big problem or a little problem? Will it inspire or help many, or a few? |
| **Creativity** | How creative/innovative is the approach? Is the project novel and something that hasn't been attempted before, or is it an incremental improvement on something that already exists? |
| **Validity** | Is the solution scientifically valid? Will it do what it sets out to do? Can it work in the real world? |
| **Relevance** | Is this project responsive to the challenge for which it was submitted? Is it a complete solution or does it have a long way to go? Is it technically feasible? How usable or user friendly is the solution? |
| **Presentation** | How well did the team communicate their project? Were they effective in telling the story of the project: the challenge, the solution, and why it is important? |

Three facts about the sheet decide the strategy:

1. **The five columns are added with equal weight** (the example row: 6 + 7 + 3.5 + 4 + 4.5 = 25; half points are
   used; the sheet prints no maximum). A point in the weakest column is worth exactly as much as a point in the
   strongest, and it is far cheaper to get. Raise the lowest columns first.
2. **The judge fills the row from three things:** the project page, the demo (30 s video or 7 slides) and the link.
   Allow about five minutes per team. Work that is not visible on one of those three surfaces scores nothing, however
   good it is. Every item below therefore says where the judge sees it.
3. **The sheet is the 2023 template.** It says NASA and partner judges use the same criteria, and past years kept
   them, but the 2026 Judging & Awards Guide appeared on 13 Nov. Check it first (item 0.2).

## 2. Where points are lost today, and the five moves that fix most of it

| Column | What a judge would deduct for today | Fixed by |
|---|---|---|
| Relevance | The brief's first words are "public-facing web tool" and there is no public URL. Several optional extras exist only on our laptops | REL-1 to REL-5 |
| Presentation | Video, slides and project page are drafts. The drafts never say why the project matters | PRE-1 to PRE-8 |
| Validity | 0 of 24 capabilities accepted; every record stale; the public build would show "unvalidated" on everything | VAL-1 to VAL-7 |
| Creativity | The novel parts (25-year blink, RGB, flipbook, spectra) are `dev` flags, so a public visitor sees a plain blink, which at least five other entries also have | CRE-1 to CRE-5 |
| Impact | Shared links and embeds work, but nothing says who will use this, how many they are, or shows the tool surviving past Sunday | IMP-1 to IMP-6 |

The five moves, in order. Each raises more than one column.

| # | Move | Columns | When |
|---|---|---|---|
| 1 | Settle eligibility and read the 2026 guide (§3) | all five (a disqualified entry scores 0) | H0–H1 |
| 2 | **Public URL** with the five targets prewarmed (REL-1) | Relevance, Validity ("real world"), Impact, Presentation | by Sat 13:00 |
| 3 | **Accept G1 and G2, then show the evidence** on a proof page (VAL-1, VAL-2) | Validity, Relevance ("complete") | freeze Sat 22:00, accept Sun 11:00 |
| 4 | **Make the novel parts visible in the public build** and say what is new (CRE-1 to CRE-3) | Creativity, Relevance (optional extras) | Sat afternoon to Sun 11:00 |
| 5 | **Tell the story the sheet asks for:** challenge, solution, why it matters; one slide per column (PRE-2 to PRE-5) | Presentation, and it is how the other four columns get seen | Sun 11:00–18:00 |

---

## 3. Gate zero (H0–H2): things that can zero the whole row

| # | Item | Owner | Size |
|---|---|---|---|
| 0.1 | **Pre-event work.** advanced_research.md §1.1 quotes the participant FAQ: teams may not begin work on the challenge before the hackathon. `git log` shows 54 commits from 5 to 12 Nov. If this has not been put to the Local Lead yet, ask at kickoff, describe exactly what exists, follow the ruling, and state in the submission what was prepared beforehand. Do not rewrite history or re-date commits | F (lead) | XS to ask |
| 0.2 | **Read the 2026 Judging & Awards Guide and Participant Guide** (published 13 Nov). Confirm: the five criteria and their scale; demo format (2025: ≤ 30 s video or ≤ 7 slides, public link, English subtitles); project-page fields; the SI/AI-use statement; nobody under 18 in the demo; whether the page can be edited until the deadline. If a criterion differs, re-map §4–§8 before doing anything else | F | S |
| 0.3 | **Three decisions** left open since the audit (audit/08 Tier 0). Recommendations below | F + P | S |

Recommended answers for 0.3:

- **How the tool becomes public: a live server now, a frozen copy before Sunday.**
  1. Sat morning: run `deploy/aws/provision.sh` (docs/deploy.md §1, ≈ 15 min, ≈ $0.19/h) with `ENVIRONMENT=staging`.
     That alone satisfies the required item, and it also unblocks G2.perf, F12 and G0.staging, which need the VM.
  2. Sat afternoon to Sun morning: ParallaX Lite (advanced_research.md A1), the pinned views as static files on
     GitHub Pages or Cloudflare Pages. NASA judges click in December and January; a static copy costs nothing to keep.
  3. Neither one is enough alone. Lite cannot serve "any coordinates", which is the brief's core sentence; a VM alone
     is a dead link the day someone stops paying (≈ $140 a month). If Lite slips, budget the VM to the end of January
     and decide who pays.
  4. No AWS account or card today: any Docker host runs `docker-compose.yml`; outside us-east-1 cold builds are slower
     (README: ≈ 2.5 min for Barnard from India), so prewarm more. A tunnel from a laptop is the last resort and only
     covers local judging.
- **Licence: GPL-3.0-or-later.** Aladin Lite is GPL-3 and bundled, so this is the choice that needs no code change.
  Add `LICENSE` and say so in the README.
- **Claims:** positions and pictures, plus any number whose record is accepted and reviewed on the day. Everything
  else is "measured, review pending" or left out (workflow.md §4.1, submission/README.md).

---

## 4. Relevance

*Responsive to the challenge? Complete, or a long way to go? Technically feasible? Usable?*

The judge answers this by holding the brief next to the tool. Make that comparison take ten seconds and come out
complete.

| ID | Action | Owner | Size | Done when | Where the judge sees it |
|---|---|---|---|---|---|
| REL-1 | Public URL (decision 0.3), `prewarm.py` on the host for every entry of `config/demo_views.yaml`, snapshot built so an IRSA outage does not blank the site | P | M | In a private window on a phone over mobile data: the home page loads, each of the five mission buttons shows its first image in < 5 s, the challenge coordinate shows the epoch banner, `?gl=0` works | The link |
| REL-2 | **Requirement map.** One table: each sentence of the brief (R1–R5) and each optional extra (O1–O8, audit/01 §3) beside the feature and a one-click link on the public host. Put it in the README and in the project description | F | S | Every row has a working link; no row says "planned" | Project page, README |
| REL-3 | **Five targets, proven.** Record `G2-render-all`: 6 bands × 5 targets × both viewers from the pins, on the public host | I | S | Record passes; any empty stack is listed with its reason in the UI | Proof page (VAL-2) |
| REL-4 | **Any coordinate, first time.** A cold build must never look broken: progress text from the first second, first image in ≈ 15 s, a plain sentence for "no SPHEREx coverage here yet", for an unknown name and for an archive outage | F + P | S | Ten random RA/Dec typed by someone outside the team: ten views or ten clear sentences, zero blank screens or raw errors | The link |
| REL-5 | **Optional extras the public build must actually show.** Today on a `staging` host: O1 freshness, O4 FOV, O6 URL and embed, O7 flags, O8 Aladin are visible. Still hidden or missing: O2 (bands and spectra), O3 (add and subtract), O5 (Gaia **and WISE** overlays: the track and Gaia markers are `dev`; a WISE catalogue layer is not drawn at all, `state/url.ts:71`) | F + M + I | M | O5: Gaia markers and a WISE layer (AllWISE positions labelled with their epoch is enough) visible publicly. O2: RGB composites public (needs only G2). O3 and spectra: public if their gate or the F5 decision allows (VAL-4), otherwise shown as a reviewed figure on the proof page and named as next step | The link, requirement map |
| REL-6 | **Hallway test.** Three people who have never seen the tool, on their own phones, one task: "find the star that moves". No help. Note where each one stalls; fix the top three stalls. Repeat once on Sunday | F | S + S | All three succeed in under a minute on the second round | Usability score |
| REL-7 | **Feasibility in one picture.** The architecture diagram from the README as a slide corner or README figure, with three facts: it runs today on real SPHEREx data, a new release is a YAML entry (`config/releases.yaml`), CI is green. Check the Actions tab is actually green at the submitted commit | P | XS | Green badge at the top of the README | README, slide |

Known small gaps that a judge can hit: MP4 export answers 501 (hide the button or ship GIF only); FOV above 24′ is
slow off AWS (keep 30′ only on the VM).

## 5. Validity

*Scientifically valid? Does what it sets out to do? Works in the real world?*

ParallaX's science is its strongest asset and currently its worst-looking one: a visitor sees "unvalidated"
everywhere, and the status table says 0 accepted. The work is mostly re-running and reviewing, not building.

| ID | Action | Owner | Size | Done when | Where the judge sees it |
|---|---|---|---|---|---|
| VAL-1 | **Accept G1 and G2.** Freeze `backend/spherex/` and the pipeline paths in `backend/app/` at Sat 22:00 (any later change makes records stale again). Overnight: `validate.py run` for every stale check. Sun morning: cross-reviews with `validate.py review` (the author never reviews their own science), the nine G2 rows of unvalidated.md, then `status --write`, `check_flags.py`, and set the five core flags to `on` | D + P run, I ↔ M review, F for G2.p0 / png / credits | L (mostly machine time) | `validation/STATUS.md` shows G1 and G2 **accepted**; the public blink carries no "unvalidated" badge | The link, proof page, slide |
| VAL-2 | **Proof page** (advanced_research.md A4): claim, our number, reference number, verdict, link to the record. Generated from `validation/`, never typed by hand. Candidate rows, each only if its record is fresh and reviewed: static Gaia stars registered to < 0.1 px between visits; two cold builds byte-identical; Barnard 25-year jump 4.540′; difference dipole on Barnard 9.7″ at PA 353° against 10.3″ at 356° predicted; ε Indi B proper motion 4.628 against 4.684″/yr; the WISE 0855 epoch banner; Horizons-as-seen-from-SPHEREx to 1.5–2.8 km | F + D, signed by I and M | M | One URL and one slide; every row links to a record; rows not yet reviewed say "review pending" | Its own page, slide, video caption |
| VAL-3 | **An independent comparison on the page.** The ε Indi B spectrum against the published SPIFF library (median ratio 0.988, scatter 5.1 %, methane index 0.182 against 0.177) is exploratory today. Turn it into an L4 record and have I review it | M, I reviews | S | A record under `validation/` and a row on the proof page, with the CC-BY credit | Proof page |
| VAL-4 | **Decide F5 in writing.** Either the calibrated VARIANCE rescale with a fresh F5, or a decision note that limits what is claimed (unvalidated.md, problem 4). Without one of them astrometry, spectra and bright fill stay off the public site | M + I | S for the note | A file in `docs/decisions/`; flags and proof page follow it | Limitations section |
| VAL-5 | **Show a null result.** One row or picture where the tool correctly sees nothing: field stars static while Barnard moves; the difference of two halves of one visit (`G4a-null`). A method that also reports "no motion" is what a scientist trusts | I | S | On the proof page | Proof page |
| VAL-6 | **Limitations, stated by us.** A short section in the README and project page: what is validated, what is not, and why (short-band ePSF, WISE 0855's neighbour 0.7–1.35 px away, R Dra 18 bins of 20, Planet X reach). The README has the start of it; replace the link to STATUS with the real table | F | S | A judge can find a weakness only where we already named it | README, project page |
| VAL-7 | **Citations complete.** Nine acknowledgement texts are still `verbatim: false` in `frontend/src/content/credits.ts` (IRSA, 2MASS, SIMBAD, Aladin, SkyBoT, AAVSO, CatWISE2020, templates, HiPS). A person copies each from its source page. This is also G2.credits | D | S | `RELEASE=1 npm test` passes | Credits page, project page "data used" |

"Works in the real world" is answered by REL-1 and REL-4: a stranger types coordinates and gets real SPHEREx images.
Say on the slide that it handled an archive outage (snapshot mode) and a second data release (QR2 and QR3).

If G2 is not accepted by Sunday 11:00, do not flip flags. Ship `staging` with the badges, and let the proof page
carry the numbers with their honest state.

## 6. Impact

*How much impact, quality and quantity? Big problem or little? Inspire or help many, or a few?*

Nothing in the tool or the drafts says who this is for or how many they are. That sentence is the cheapest point
available in the whole sheet.

| ID | Action | Owner | Size | Done when | Where the judge sees it |
|---|---|---|---|---|---|
| IMP-1 | **State the problem and its size**, with sources (advanced_research.md §1.5, §3.5): volunteers blinking WISE images found more than 3,000 brown dwarfs; the brief itself asks to help "as many people as possible pitch in"; WISE has stopped observing; SPHEREx re-images the whole sky every six months and has no public blink tool (IRSA's own tool list). ParallaX is that tool, plus the spectral dimension WISE never had | F | XS | Two sentences, first paragraph of the project page, and one slide | Project page, slide, video |
| IMP-2 | **It outlives the weekend.** Lite or a funded VM (decision 0.3); pins that freeze resolved targets before Gaia DR4 on 2 Dec (advanced_research.md A2) so judged links cannot drift | P + D | M | Every pinned link reproduces its view key with the resolver unplugged | The link, in January |
| IMP-3 | **Bridge to the people who already do this** (advanced_research.md B6): per-view links out to WiseView, the Legacy Survey viewer, IRSA's tools and SIMBAD; the candidate report formatted so it can be pasted into a citizen-science forum. Claim no partnership | F | S | Links present on every view; a report copies as plain text with coordinates, epochs and a permalink | The link, slide |
| IMP-4 | **Nobody is locked out.** No login; works on a phone; PNG viewer for old devices; keyboard control, alt text and sonification exist. Run Lighthouse, fix what it finds, and check that reduced-motion opens side-by-side instead of a blink | F | S | Accessibility ≥ 95; keyboard-only pass through one mission | One line on the slide; the link |
| IMP-5 | **Reach beyond English.** Simple-mode mission text in Hindi and one more language (five short blocks in `frontend/src/content/missions.ts`); a one-page classroom activity, "measure Barnard's Star with a ruler", from two pinned frames | F | S–M | Language switch on the home page; PDF linked from the README | Home page, project page |
| IMP-6 | **Others can build on it.** `LICENSE`, `CITATION.cff`, the embed snippet in the README, and "add a data release" and "add a mission" as two short how-tos (docs/data-refresh.md has the first) | P + F | S | A stranger can embed a view from the README alone | README |

For "inspire": keep the Pluto-to-Planet-X thread, and be honest about reach. The calculator of advanced_research.md
B5 ("SPHEREx would see a Planet Nine inside about 350 AU") is small, true, and memorable. Build it only if IMP-1 to
IMP-4 are done.

## 7. Creativity

*Novel, not attempted before, or an incremental improvement?*

Blink, difference and a comet track are now common to the strongest entries (advanced_research.md §2). The judge
will call ParallaX incremental unless the new parts are in front of them and named as new.

| ID | Action | Owner | Size | Done when | Where the judge sees it |
|---|---|---|---|---|---|
| CRE-1 | **"What is new" table.** WiseView, IRSA's SPHEREx tools, a plain exposure blink, ParallaX; rows: correct frames for a spectral imager, epoch-aware coordinates, parallax in the track, 25-year multi-mission blink, wavelength-matched difference, evidence gates. Compare with established tools, not with other teams | F | S | One slide and one README section | Slide, project page |
| CRE-2 | **"The trap"** (advanced_research.md A3): ε Indi B's exposures in time order flicker about 2× although nothing varies; ParallaX's visit stacks stay steady. It is the single idea that separates this entry from a naive blink, and it is also a Validity point. Ship it as a rendered side-by-side from pinned data on the home page and in the video, so it does not depend on the `flip` flag | F, I reviews | S | The pair plays on the home page with one caption a non-astronomer understands | Home page, video seconds 5–10 |
| CRE-3 | **Unhide what is closest to acceptance.** After G2: `rgb` (needs only G2) and `blink25` (G2 plus M's review of the passing `G5.25yr-jumps` record and a re-run of the data record) go `on`. These two plus the epoch banner are the public "only here" features | M reviews, P flips | S after VAL-1 | Both visible with no badge on the public host | The link, video |
| CRE-4 | **One thing nobody else shows. Pick one, not both.** (a) 3I/ATLAS in CO₂ light, August against December 2025 (B1, size M, needs the per-day coverage planner), or (b) "SPHEREx alone measured this distance" for ε Indi B (B2, size S–M, pre-register bands and pass rule before running). Start only if moves 1–3 of §2 are on schedule at Sat 15:00 | M + D + F | M | Meets the acceptance test written in advanced_research.md §4 | Video, slide |
| CRE-5 | **Keep the frame.** "The 1930 blink comparator, rebuilt for a 102-colour telescope" is the creative idea in one line. Use the full name "ParallaX — SPHEREx blink comparator" everywhere (another entry is also called Parallax). The 1930 plate pair stays drawn; no Lowell photographs without permission | F | XS | Same line on page, slide 1 and video | Everywhere |

Sonification, the methane meter and the flipbook are creative but sit behind spectra and G4a. Mention them as built
and gated; do not spend event hours trying to free them before CRE-1 to CRE-3 are done.

## 8. Presentation

*How well communicated? The challenge, the solution, and why it is important.*

The sheet names three story beats. The current video script (submission/video-script.md) spends 30 seconds on the
solution and none on why it matters. Rebuild both drafts on the three beats.

| ID | Action | Owner | Size | Done when |
|---|---|---|---|---|
| PRE-1 | Format confirmed against the 2026 guide (item 0.2); drafts corrected | F | XS | submission/README.md updated |
| PRE-2 | **Video, three beats in 30 s.** Challenge (≈ 8 s): Pluto was found by blinking two plates; SPHEREx re-images the whole sky, but its exposures change colour, so a naive blink lies (CRE-2). Solution (≈ 14 s): Barnard hops; 25-year leap with its number; the challenge coordinate and the epoch banner. Why it matters (≈ 6 s): IMP-1 in one sentence. Last 2 s: the URL | F | M | Understood with the sound off (subtitles burned in); every number on screen names its record; plays from a public link in a private window |
| PRE-3 | **Slides: one slide per column**, so the judge can fill the row left to right. 1 title and URL · 2 the challenge and the trap · 3 the solution (Relevance: requirement map in miniature) · 4 proof (Validity) · 5 what is new (Creativity) · 6 who it is for (Impact) · 7 data, credits, SI use, prior work. Keep them as a PDF in `submission/` and link it from the project page even if the demo link is the video | F | M | A person outside the team can say what each slide claims after 10 s on it |
| PRE-4 | **Project page.** First two sentences: what it is and who it is for, no jargon, with the URL. Then five short sections titled Impact, Creativity, Validity, Relevance and How it works, then data used, references, SI use and prior work. The judge should be able to copy a phrase from each section into each column | F | S | Two readers outside the team each repeat back what the project does and why it matters |
| PRE-5 | **README top screen:** name, one-line pitch, public URL, an animated capture of the Barnard blink, the five target links on the public host, the validation table. Run instructions move below | F | S | A visitor learns what it is and can open it without scrolling |
| PRE-6 | **Live pitch for local judging:** the three-minute arc of implementation.md §11.4, one speaker, one driver, and the one-line answers of advanced_research.md §5 ("why visits, not exposures?", "how do you know the motion is real?", "what is not validated?"). Rehearse twice, once with the network off | all | S | Runs in 3 min from the snapshot laptop |
| PRE-7 | **Record from frozen ground.** Record after the Sunday 11:00 feature freeze, from pinned prewarmed views, at 1080p, with a large cursor. Re-read every number against `STATUS.md` on the recording day | F | — | Checklist of submission/README.md ticked |
| PRE-8 | **Submit early.** All fields filled by Sunday 20:00. Open every link from the page logged out, on a phone. After 20:00 only typos change and nobody deploys | F + P | S | Page complete four hours before the deadline |

---

## 9. Schedule

| Window | D | I | M | P | F |
|---|---|---|---|---|---|
| Sat 09:00–11:00 | `refresh_check.py`; read the Resources tab | — | Draft the F5 decision (VAL-4) | Provision the VM; `staging` deploy (REL-1) | Items 0.1–0.3; 2026 guides |
| Sat 11:00–15:00 | Credit texts (VAL-7); freeze targets in pins (IMP-2) | `G2-render-all` (REL-3); F14 real-field orientation | SPIFF record (VAL-3) | Prewarm, snapshot, `G2-perf` from the VM; CI green; `LICENSE` | Requirement map (REL-2); trap figure (CRE-2); hallway test 1 (REL-6) |
| Sat 15:00–22:00 | WISE layer data (REL-5); CRE-4 coverage if chosen | Null test (VAL-5); review M's records | CRE-4 if chosen; review I's records | ParallaX Lite export (0.3) | Proof page (VAL-2); "what is new" (CRE-1); link-outs (IMP-3); cold-load and error text (REL-4) |
| **Sat 22:00** | **Science code freeze.** Start the overnight re-run of every stale record (VAL-1) | | | | |
| Sun 08:00–11:00 | Reviews; `status --write` | Reviews | Reviews; `blink25` sign-off (CRE-3) | `check_flags.py`; flip flags; redeploy; prewarm; snapshot; rebuild Lite | G2.p0, G2.png records; Lighthouse (IMP-4); translations (IMP-5) |
| **Sun 11:00** | **Feature freeze.** | | | | |
| Sun 11:00–18:00 | Check every number in the drafts against records | Review mission and slide wording | Review claims in video and slides | Phone, `?gl=0`, private-window and network-off checks | Video, slides, project page, README (PRE-2 to PRE-5); hallway test 2 |
| Sun 18:00–20:00 | | | | Final link check | Submit (PRE-8); pitch rehearsal (PRE-6) |
| Sun 20:00–23:59 | Buffer. Typos only | | | No deploys | |

**Cut order if time runs short.** Keep, in this order: 0.1–0.3, REL-1, PRE-2 to PRE-4, REL-2, VAL-1, VAL-2, CRE-1,
CRE-2, IMP-1, VAL-6, VAL-7. Drop first: CRE-4, IMP-5, the Planet X calculator, ParallaX Lite (replace it with a
funded VM), IMP-6 beyond the `LICENSE` file.

## 10. Before pressing submit: one sentence per column

After five minutes with the page, the video and the link, the judge should be able to write each of these in the
Notes column. If one is not supported by something they can see, that column is not finished.

| Column | The sentence | Supported by |
|---|---|---|
| Relevance | "It does everything the brief lists, on all five test targets, and I used it myself on my phone" | REL-1, REL-2, REL-6 |
| Validity | "They knew raw exposures would mislead, their numbers match Gaia and published SPHEREx spectra, and they say what is not yet proven" | CRE-2, VAL-2, VAL-3, VAL-6 |
| Creativity | "I have not seen the 25-year blink or the trap comparison anywhere else" | CRE-1 to CRE-3 |
| Impact | "This is the missing blink tool for the next all-sky infrared survey, anyone can use it, and it will still be online next month" | IMP-1 to IMP-4 |
| Presentation | "I understood the problem, the tool and why it matters in thirty seconds" | PRE-2 to PRE-4 |

## 11. Do not

- Rewrite or re-date git history (item 0.1).
- Touch `backend/spherex/` after the Saturday 22:00 freeze, or anything after Sunday 11:00, unless the site is down.
- Quote a number from a planning document, or call anything a discovery (workflow.md §4.1, §11.2).
- Turn a flag `on` without its accepted gate to make the site look finished. `check_flags.py` will fail CI, and a
  wrong number in front of a NASA scientist costs more Validity than a badge does.
- Use NASA insignia, imply endorsement, or use the Lowell plate photographs.
- Start a new feature because another team has it. Past REL-1, every hour is better spent making existing work visible.

---

## 12. Progress (updated 2026-11-14)

Done in the repository (tests, `check_flags.py`, `validate.py status --check`, `make_proof.py --check` and
`freeze_targets.py --check` green):

| Item | What exists |
|---|---|
| 0.3 licence | `LICENSE` (GPL-3.0-or-later), README badge and section, `CITATION.cff` |
| 0.3 / IMP-2 Lite | `scripts/make_lite.py`, `frontend/src/api/lite.ts`, `npm run build:lite`, `VITE_BASE` sub-path support, frozen-copy banner; runbook docs/deploy.md §8 |
| IMP-2 frozen targets | `config/pins/targets.json` (`scripts/freeze_targets.py`), used by `pipeline.frozen_target`; a Gaia failure is now marked degraded |
| REL-2, CRE-1, VAL-6, PRE-5 (text) | README top screen: pitch, who it is for, five target paths, requirement map, "What is new", limitations |
| REL-5 O5 | AllWISE layer (`/overlays/allwise`, "WISE (2010)" squares), its own `wise_layer` capability at `staging` (requires G2) so it is public on staging with the *unvalidated* badge |
| VAL-2, VAL-5 | `/proof` page and README proof table, generated from `validation/` by `scripts/make_proof.py` (CI checks it) |
| IMP-3 | "Look elsewhere" card (WiseView, Legacy Survey, ESASky, SIMBAD); candidate report as plain text |
| IMP-5 | Home page and missions in Hindi and Spanish (`?lang=`); docs/classroom-barnard.md |
| IMP-6 | Embed snippet in the README; docs/extending.md (release, pinned target, mission, capability) |
| CRE-5 | "ParallaX — SPHEREx blink comparator" in the README, page title, drafts |
| PRE-1 to PRE-4 (drafts) | submission/video-script.md (three beats), slides.md (one slide per column), project-page.md |

Still open, because it needs people, a host or live data (not doable from the repository alone):

- 0.1, 0.2: the Local Lead's ruling on prior work and the 2026 guides; fill the prior-work and SI text in
  submission/project-page.md accordingly.
- REL-1: provision the host, prewarm, snapshot; then run the Lite export and publish it. Replace every `<URL>`
  placeholder (README top screen, embed snippet, submission drafts).
- VAL-1: the Saturday 22:00 freeze, overnight re-runs of stale records, cross-reviews, `status --write`, then
  `make_proof.py --write`. No flag goes `on` before that.
- VAL-3 (SPIFF L4 record), VAL-4 (F5 decision note by M + I), VAL-7 (nine `verbatim: false` credits, copied by a person).
- CRE-2: render the ε Indi B trap side-by-side from pinned data (needs the frames); CRE-3 after G2.
- REL-3, REL-6, IMP-4 (Lighthouse), PRE-2/PRE-3 recording and PDF, PRE-6 rehearsal, PRE-8 submission; an animated
  Barnard capture for the README.
- A fluent speaker reads the Hindi and Spanish text before release.

## 12a. Re-map after reading the 2026 guides (2026-11-14)

The 2026 Judging & Awards Guide and Project Submission Guide are out; the rules are quoted in
[submission/2026-rules.md](submission/2026-rules.md). Changes to this plan:

- **Scale 1–5 per criterion**, equal weight. Half points are not mentioned.
- **Usability moved to Validity** ("the usability and user-friendliness of the project influence its practicality").
  REL-4, REL-6 and IMP-4 now also raise Validity.
- **Relevance now rewards deep use of NASA data** ("a core component … rather than a superficial addition"). Say on
  the project page and slide 3 that every frame is SPHEREx, with WISE, 2MASS and Horizons as NASA sources and Gaia as
  ESA partner data (project form fields 6 and 7).
- **Presentation is scored from the demo and the full project**; "the majority of judges' evaluation will be based
  on your project submission". PRE-4 (the project page) outranks the video.
- **SI (AI) disclosure must be inside the project**, not only on the form (the form answer is not shown to judges):
  README "Use of SI tools" and the About page carry it. SI-generated images/video need a visible watermark; none are used.
- **References must list all code, text and images used**, open source included (project-page.md §8).
- **Pre-event work:** the FAQ says "Teams are not allowed to begin working on the challenges prior to the hackathon."
  Item 0.1 is the biggest risk to the whole entry; ask the Local Lead before anything else.
- **Judging dates:** Global Nominees 3 Dec, Finalists 17 Dec, Winners 26 Jan 2027: the link must live to the end of
  January (ParallaX Lite).
- Optional: request a FortiGuard Web Filter Classification for the public host.

## 12b. Browser test on live SPHEREx data (2026-11-14 afternoon)

The app was run as `staging` against live IRSA (calibration locked), all 10 demo views were built, and it was driven
in a headless Chromium (desktop, phone 390 px, `?gl=0`, embed 480×520, Hindi). Fixed:

| Found | Fix |
|---|---|
| Views built on a laptop (`bright_fill` shown) were served by staging with **model-filled cores** (4 of the 10 demo views); the Lite copy had recorded them | `fill` is part of the view key (`app/viewkey.py`); `make_lite.py` refuses filled stacks when the capability is off; views and Lite rebuilt |
| `/healthz` grew by two rows per call inside its 60 s cache | the cached probe list is no longer mutated |
| The WISE layer looked dead for ~40 s (IRSA TAP), then drew 215 squares on a 6′ field | "loading catalogue markers…" / "unavailable" badges; W2 ≤ 14 cut (keeps WISE 0855) |
| Target names shown as SIMBAD ids ("NAME Barnard's star", "* eps Ind B") | `lib/names.ts` `displayName` |
| Barnard's mission step pointed at the predicted track, which is `dev` | per-step `lookNeeds`; the step hides where the capability is off |
| Fill mask fetched by a bare `fetch('/api/v1/…')`, bypassing mock and Lite | `api.filledMask` through the transport |
| Embed controls cut off at the snippet's own 480×520 | plate height capped to the iframe |
| Embed "Open in ParallaX" ignored the Lite sub-path | `href()` |
| Frozen copy offered "Update to the latest" (cannot work there) | hidden in Lite |
| Banners pushed the image below the fold on phones | compact banners under 640 px |
| `?lang=hi` logged "unknown URL parameter" | accepted silently |
| axe-core: skip link without target, no h1 in the viewer, notices outside landmarks, About heading order | fixed; 0 violations on home, viewer and proof |
| "View not built" heading for a not-found name or no coverage | "Nothing to show", plus a hint that quick releases do not cover the whole sky |

Verified working: progress text within 2.5 s of a cold build; a clear sentence for an unknown name and for no
coverage; WebGL and PNG viewers; Share; loupe; Hindi switch; ParallaX Lite under a GitHub Pages sub-path with no
request to any API (10 views, 51 MB; `scripts/publish_lite.sh` publishes it). README now opens with a GIF of the real
Barnard blink (the app's own GIF export). VAL-7: 2MASS acknowledgement verified word for word (8 still open; CDS was
serving a fallback page and IRSA's acknowledgement page could not be found).
