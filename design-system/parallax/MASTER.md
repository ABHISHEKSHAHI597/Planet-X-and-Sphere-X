# ParallaX design system — "Observing log"

Source of truth for the frontend's look and behaviour. Tokens live in `frontend/src/styles.css` (`:root`); this file
explains them. Page-specific overrides would go in `design-system/parallax/pages/<page>.md` (none yet).

**Product.** A public blink comparator for SPHEREx visit stacks: type a star or RA/Dec and see what moves and what
changes, across six infrared bands. Users: Space Apps judges and the public (Simple), interested amateurs (Explorer),
astronomers (Expert). It is an instrument with a short landing page, not a marketing site.

**Direction.** The UI borrows from an observatory's instrument panel and plate logbook, not from "space theme" UI: a
neutral graphite surround (so the sky images are judged against neutral grey, not navy), one sodium-amber signal
colour for things you can act on, the six SPHEREx bands as the only other colour (they always encode a band), measured
values in a monospace face, uppercase micro-labels like engraved panel legends, hairlines in place of shadows.

How the UI/UX Pro Max searches were used: the `--design-system` aggregate returned an unrelated biotech profile for
every query, so it was not used. Verified domain matches were: *Space Tech / Aerospace* palette (near-black neutral
background, star-white text, one accent), *Data-Dense Dashboard* style (8–12px gaps, sticky headers, compact
controls), *Swiss Modernism* for the research-lab angle (grid, hairlines, type-led hierarchy), and the
*Developer Mono* pairing idea (Plex/JetBrains mono for data). UX rules applied: visible focus on every control,
44px targets on coarse pointers, progress for multi-step work, one live region per status, reduced motion.

Avoid: purple/blue gradients, glows, glass panels, pill buttons, coloured top-stripes on cards, card grids for lists,
eyebrow labels above headings (removed in the 2026-11-09 audit), all-caps badges,
emoji or Unicode glyphs as icons, decorative motion, raw hex values inside components.

## 1–7. Colour (dark only; the images are of the night sky)

| Role | Token | Hex | Notes |
|---|---|---|---|
| Primary / signal | `--amber` | `#F2B33D` | play, primary buttons, current frame, focus ring, target name |
| Primary hover | `--amber-hi` | `#FFC760` | |
| On primary | `--amber-ink` | `#1A1306` | 9.9:1 on amber |
| Primary wash | `--amber-wash` | `rgba(242,179,61,.12)` | selected state background |
| Secondary / info | `--cyan` | `#74C7EC` | links, crosshair, info banners |
| Accent: bands 1–6 | `--b1`…`--b6` | `#7D8CFF #4FC3F0 #5ED6A0 #D9D05A #F59A45 #F2606A` | **data only**: band buttons, band axis, mission band chips |
| Success | `--ok` | `#6FCF97` | QA pass, freshness dot |
| Warning | `--warn` | `#F0974A` | "unvalidated", skipped frames |
| Error | `--bad` | `#F2656F` | errors, failed checks |
| No data | `--nodata` | `rgb(46,26,56)` | scientific convention: no-data pixels are purple, never black |
| Background | `--ink-1` | `#0D0E11` | page |
| Deep | `--ink-0` | `#08090B` | inputs, plate surround |
| Surface | `--ink-2` | `#14161A` | panels, rail, timeline, dialogs |
| Raised | `--ink-3` | `#1B1E23` | buttons, hover |
| Pressed / selected | `--ink-4` | `#252930` | segmented "on" |
| Text | `--text` | `#EBEDF0` | 16.5:1 on ink-1 |
| Text secondary | `--text-2` | `#A8AEBB` | 8.7:1 |
| Text tertiary | `--text-3` | `#7C8391` | 5.1:1 (4.8:1 on surfaces) — labels and metadata only |
| Border | `--line` | `#2A2E36` | control borders |
| Border soft | `--line-soft` | `#1E2127` | dividers |
| Border strong | `--line-strong` | `#3B404B` | hover borders, axes |

## 8–9. Typography

- **Archivo** (variable width 62–125) for UI and prose. Display headings use `font-stretch: 125%`, weight 800,
  tracking −0.035em. **IBM Plex Mono** (400/500/600) for every measured or identifying value: coordinates, epochs,
  wavelengths, pins, frame counts, bin labels, catalogue ids, chart ticks.
- Micro-label: 11px, weight 600, uppercase, +0.09em, `--text-3`. Only for control-group names, panel kickers and
  table column headers — never above page or section headings, and never on a `<th>` that holds a symbol (μ → Μ).

| Use | Size | Weight |
|---|---|---|
| Display (home h1) | `clamp(2.6rem, 5.6vw, 4.6rem)` | 800, expanded |
| Page title (About) | `clamp(2rem, 4vw, 2.8rem)` | 800, expanded |
| Section title | 1.5rem | 700, 112% |
| Panel title | 0.95rem | 650 |
| Body | 15px (0.9375rem), line-height 1.5; long prose 1.06rem / 1.65 | 400 |
| Controls | 14px | 500 |
| Meta | 13px | 400 |
| Micro | 11px | 600 uppercase |

## 10–12. Space, radius, elevation

- Spacing: 4-pt scale `--s1…--s16` = 4, 8, 12, 16, 20, 24, 32, 48, 64 px. Workspace gaps 14–20px (dense); home
  sections 48px.
- Radius: `--r-xs` 2 (tags, badges) · `--r-sm` 4 (controls, plate) · `--r-md` 6 (panels) · `--r-lg` 8 (dialogs).
  No pills.
- Elevation: hairlines carry structure. One shadow, `--shadow-pop`, only for things floating above content (dialog,
  loupe). No glows.

## 13–17. Components

- **Buttons:** 34px min height (44px on coarse pointers), 4px radius, `--ink-3` with `--line` border. `primary` is
  solid amber. `icon-btn` is square and always has an `aria-label`. Selected = amber wash + amber border.
  Disabled = 38% opacity, `not-allowed`.
- **Segmented control** (`.segmented`): a recessed `--ink-0` track; the chosen item is raised (`--ink-4`). Used for
  detail level and mode; always `role="radiogroup"` with `aria-checked`.
- **Band picker:** six equal mono cells with a band-colour foot; the selected cell is tinted with its band. Under it a
  0.75–5.0 µm scale line.
- **Inputs/selects:** `--ink-0`, 1px `--line`, custom chevron; focus = amber border + 3px amber wash.
- **Navigation:** sticky 56px header (static on phones) — brand, search (hidden on home, where the hero holds the
  large search), live target readout + FOV + data freshness,
  detail level, share, shortcuts, about. On phones it reflows to: brand · share / search / FOV · level / status line.
- **Panels:** the side panel is one accordion (not a stack of cards): kicker + title, sticky summaries, mono key/value
  lists. Lists (missions) are ruled rows, not cards.
- **Banners:** full-width strip, 3px left rule in the status colour, icon, text, actions on the right.
- **Badges:** 18px tall mono sentence-case tags; `unvalidated` is dashed orange and must appear on every capability that
  has not passed its gate.
- **Dialogs:** native `<dialog>`, 8px radius, hairline header with an icon close button, 74% backdrop, no blur.
- **Selection:** clicking a source shows a bar under the plate: its RA/Dec (green, like the ring on the plate),
  "Report a candidate here" when that capability is on, and Clear.
- **Header alignment:** the header's side padding follows `--content-w`, the width of the content under it (workspace,
  home column, placeholder, or full width in side-by-side), never less than 1040px so the header still fits.
- **One player per view:** in flipbook mode the rail keeps only the visit stepper and speed; the flipbook's own control plays.
- **External services:** a third-party view (Aladin/CDS) shows "connecting" and then an explicit "unavailable" state with
  retry; never a blank or grey box.
- **States:** loading before a manifest = an empty plate holder with a 3-step checklist; failure = the same holder in
  red with the server's message and a way back; empty = dashed panel with the one action that fixes it.
- **Icons:** `components/Icon.tsx`, one 24-unit stroke set (1.75 stroke, round joins), `aria-hidden`; never emoji.

## 18. Breakpoints and layout

- Workspace: `[stage | 380px side panel]`, 330px below 1240px, single column below 980px.
- The workspace is one centred block: `--plate` (min(100vh − header − 120px, 880px)) + `--rail` 252px + side panel;
  side-by-side mode takes the full width.
- The stage is a **container**: at ≥600px of stage width the plate and the control rail sit side by side (rail 252px,
  sticky, scrolls inside itself); narrower, the rail drops below the plate and its groups flow into columns.
- The plate is square and sized from the viewport height so play/band controls stay above the fold on a laptop.
- Home: search-first hero (large target box + example queries in each input form) beside the blink comparator and
  its plate log; two-column above 760px; observing-list rows collapse into a stacked grid on phones.
- Phone header ≤600px, icon-only share ≤380px. Never horizontal scroll (checked at 375 and 720px).

## 19. Motion

- 120ms colour/border transitions, 180ms disclosure and dialog entry, `cubic-bezier(.2,.7,.2,1)`.
- Motion only where it means something: the blink itself, a pulsing dot while a job runs, the chevron of a
  disclosure, a 3px nudge of a row's arrow on hover.
- `prefers-reduced-motion`: every transition and animation is off; the player does not autoplay; the home blink demo
  shows both plate positions at once instead of blinking.
