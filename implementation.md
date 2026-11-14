# ParallaX — Implementation Plan

### A public, time-correct, spectral blink tool for SPHEREx

> **Working name:** *ParallaX* (parallax + Planet X). Rename freely.
> Read [`understanding.md`](./understanding.md) first. This document assumes its concepts: LVF, co-aligned detector pairs, full and partial visits, flags, the ePSF cutout trap, and epoch propagation.
> Facts marked ✅ were verified on 2026-11-05 against IRSA services or real SPHEREx files. **✅ 11-06** marks facts (re)verified on 2026-11-06 against IRSA, the S3 bucket, SIMBAD, Gaia DR3, JPL Horizons or SkyBoT. **≈** marks estimates. [§15](#15-revision-log-2026-11-06) lists what the 2026-11-06 revision changed and why.

---

## 0. TL;DR architecture

```
 ┌─────────────────────────── Browser (React + TS + WebGL2) ───────────────────────────┐
 │  Target box ─► URL state ◄─► Blink viewer (R16F textures, shader stretch, diff)     │
 │  Timeline (visits · partials · bins) · Band/RGB picker · Flags overlay · Vectors    │
 │  Spectrum panel · Light-curve panel · Aladin Lite context · PNG fallback viewer     │
 └───────────────▲───────────────────────────────────────────────────────▲─────────────┘
                 │ JSON + binary float16 stacks (≈0.1–3 MB per view)     │ SSE progress
 ┌───────────────┴──────────── API (FastAPI, one process) ───────────────┴─────────────┐
 │ /resolve /coverage /views (jobs) /frames /diff /spectrum /lightcurve /sso /export   │
 │ job runner: asyncio tasks for I/O + ProcessPoolExecutor for numpy/astropy           │
 │                                                                                     │
 │ coverage (SIA2; TAP fallback) → dedup → plan (selected band first) → fetch          │
 │ (S3 row sections in us-east-1 | IRSA cutout stream-abort elsewhere; auto-failover)  │
 │ → preprocess (zodi, bkg, flags, gain) → reproject → reject transients               │
 │ → stacks + per-visit spectral cubes → λ-matched diffs → astrometry (ePSF, PM + ϖ)   │
 │ → spectra / light curves → mover finder                                             │
 └───────▲──────────────────────────────▲──────────────────────────────▲───────────────┘
         │                              │                              │
   Disk cache: coverage,          Disk cache: frames, stacks,    Calibration cache
   ephemerides (TTL)              cubes (keyed by frame list)    (CWAVE, channels, ePSF,
                                                                  flux corrections)
 External: IRSA SIA2/TAP/cutouts · s3://nasa-irsa-spherex · SIMBAD (CfA mirror) ·
           Gaia DR3, 2MASS, AllWISE/NEOWISE at IRSA · JPL Horizons (SPHEREx = −163182) ·
           IMCCE SkyBoT · AAVSO (validation)
```

**Design principles**
1. **The server does astronomy and the browser does pixels.** Stacks, not raw frames, cross the wire.
2. **Correct time axis by default.** Visits are frames, wavelengths are matched per pixel, and epochs are propagated, parallax included.
3. **Everything is a URL.** Any view can be reproduced, shared, embedded and *pinned*.
4. **The data release is configuration, not code.** QR2, QR3, DR1… are entries in YAML.
5. **Cache by content.** A view's key is the hash of its exact frame list, so new data elsewhere in the sky never cold-starts it.
6. **Fewest moving parts.** One API process, one disk cache, one VM. No Redis or worker fleet unless load demands it.
7. **The demo can't fail.** Pre-warm the 5 targets, pin their links, keep a PNG fallback viewer, and run a snapshot server on the demo laptop.

---

## 1. Product specification

### 1.1 Personas
| Persona | Needs | Mode |
|---|---|---|
| Curious public (student, teacher, amateur) | "Type a star, see it move." Explanations and no jargon. | **Simple** |
| Citizen scientist (Backyard Worlds style) | Fast flipping through many fields, difference images, overlays, reporting candidates | **Explorer** |
| Astronomer | Flags, per-frame metadata, spectra with errors, FITS/CSV export, reproducible URLs | **Expert** |

### 1.2 Core user journeys
1. **"Show me it move."** Enter `Barnard's Star` → auto-resolve (PM-aware) → visit blink in band 6 → a predicted-track overlay and a motion arrow appear → toggle the "difference" view and see a dipole → toggle "25-year blink" and see a **4.6′** jump.
2. **"What is this red dot?"** Click a source → spectrum panel (per-visit spectra, error bars) → methane meter says "cold (T/Y dwarf-like)" → overlay a T6 template → "Report candidate", or see that it's a known object via SIMBAD/Gaia match.
3. **"Is it variable?"** On R Dra, the time axis switches itself to 14-day bins → light-curve panel, periodogram (≈245 d), phase-folded curve → spectra vs phase.
4. **"Embed it."** Copy the share link or iframe snippet. The page opens with identical state.
5. **"Find Planet X."** Enter `Pluto`. SIMBAD has no such star, so the resolver asks JPL Horizons, which returns positions *as seen from SPHEREx*. Track mode centres every frame on Pluto while the stars stream past. Click it, and the spectrum shows methane ice at 1.7, 2.3 and 3.3 µm.

### 1.3 Feature tiers and acceptance criteria

**P0, must ship (maps to the required objectives):**
| ID | Feature | Acceptance |
|---|---|---|
| P0-1 | RA/Dec input (decimal, sexagesimal, Unicode minus), object-name resolve with aliases, epoch handling | The challenge's WISE 0855 coordinate triggers "this is a ≈2010.4 position; the object is now 2.2′ west". `Barnard's Star`, `WISE 0855`, `WISE 0855−0714` and `eps Ind B` all resolve. Barnard resolves to its 2026 position. |
| P0-2 | Coverage summary (full and partial visits, frames per band, dates, release) | One SIA2 call: ≤ 8 s cold, < 1 s warm, for any sky position |
| P0-3 | **Visit-stack blink** per band (1–6) with a shared stretch | All 5 targets show ≥ 2 full visits, labelled with date, survey, frame count and full/partial status. WISE 0855 has exactly 2 full visits (✅ 11-06). |
| P0-4 | FOV selector (2′–30′) | Larger FOV degrades gracefully (binning). Cutouts carry the √2 rotation margin. |
| P0-5 | URL state, permalinks and pinned demo links | Reload reproduces the view exactly. `pin=` links never change when new data arrives. |
| P0-6 | Flags overlay (per-bit toggles) and per-frame QA badges | `OVERFLOW` hole visible on Barnard; tooltip explains it |
| P0-7 | Credits/About with SPHEREx DOIs and every other acknowledgement | Present |
| P0-8 | **PNG fallback viewer** (server-rendered frames, shared stretch) | The blink works with WebGL disabled |

**P1, the "extra kudos" items from the brief:**
| ID | Feature | Acceptance |
|---|---|---|
| P1-1 | **Per-pixel wavelength-matched difference** (visit A − visit B) from spectral cubes | Barnard shows a dipole aligned with the Gaia PM vector. Static field stars leave < 3σ residuals. |
| P1-2 | **Spectrum on click** (forced ePSF photometry, per visit) | ε Ind B shows a 3.3 µm CH₄ trough. Points have errors and λ widths. |
| P1-3 | Predicted track (catalogue PM **and parallax** at each visit) and fitted motion arrow | Fitted PM is within acceptance limits (§10) |
| P1-4 | Aladin Lite context: 2MASS/AllWISE/unWISE/DSS HiPS plus Gaia DR3 and SIMBAD markers | Toggleable, synchronized FOV |
| P1-5 | Embed route and iframe/postMessage API | Works on a plain HTML page |
| P1-6 | Release freshness badge and auto-update | Shows the newest SPHEREx planning period ingested (✅ 11-06: `2026W40_2A`) |
| P1-7 | Bright-target display: saturated cores filled with the fitted ePSF model, clearly marked, with a "show raw" toggle | Barnard looks like a star, not a donut. Measurements never use filled pixels. |

**P2, differentiators (pick by time left):**
| ID | Feature |
|---|---|
| P2-1 | **25-year blink:** 2MASS → AllWISE → NEOWISE → SPHEREx |
| P2-2 | **Spectral flipbook** (exposures sorted by λ) and **λ-scrubber** (the per-visit spectral cube) |
| P2-3 | Light curves (spectrally normalized), Lomb–Scargle, phase folding; R Dra via same-channel annulus ratios |
| P2-4 | **Mover finder:** auto-detect, cross-visit linking, PM fit, known-object labelling, candidate list |
| P2-5 | Asteroid layer: exposure-level orphans plus SkyBoT labels |
| P2-6 | **Planet X mode:** per-day orphans linked by a distance-parametrized parallax model, validated on known dwarf planets |
| P2-7 | GIF/MP4/APNG export, FITS/CSV export |
| P2-8 | Sonification of spectra; "methane meter"; guided missions for the 5 targets |
| P2-9 | Candidate reports with automatic vetting checks |
| P2-10 | **Solar System track mode:** Horizons ephemerides as seen from SPHEREx (Pluto, dwarf planets, comets) |

---

## 2. System architecture

### 2.1 Why a backend is non-negotiable (✅ verified; re-checked 11-06)
1. **CORS:** IRSA SIA2, TAP and cutout responses carry no `Access-Control-Allow-Origin`, so browsers block them.
2. **Bandwidth:** each IRSA cutout drags a ≈3.9 MB ePSF extension. A server can stop reading after `ZODI`, at byte ≈89 KB; a browser cannot cheaply.
3. **Compute:** SIP-aware reprojection, ePSF fitting, stacking hundreds of frames and periodograms belong in numpy/scipy/astropy.
4. **Venue networks are slow.** ✅ 11-06: our own network got 30–80 KB/s from IRSA and S3. A cloud server keeps pixel traffic off the venue link; only small stacks reach the browser.

(The S3 mirror *does* allow CORS. A future "serverless" variant could range-read FITS from the browser, but that stays out of scope for 39 hours.)

### 2.2 Technology choices
| Layer | Choice | Why |
|---|---|---|
| Frontend | **React 18/19 + TypeScript + Vite** | Fast dev, big ecosystem |
| Image rendering | **Custom WebGL2** (R16F textures, GLSL stretch/colormap), plus a **server-rendered PNG fallback** | 60 fps blink and client-side stretch without refetching. The PNG path guarantees P0. |
| Sky context | **Aladin Lite v3** (pin an exact version) | HiPS surveys (2MASS, AllWISE, unWISE, DSS, PanSTARRS) and catalogue overlays for free |
| Charts | **uPlot** (fast) or Plotly (richer). ✅ 11-07 (F): small SVG charts instead (`components/charts.tsx`): x *and* y error bars, one marker shape per series (never hue alone), no extra dependency, testable in jsdom | Spectra with error bars, light curves |
| State | **Zustand** + URL sync; **TanStack Query** for fetches | Simple, cache-aware |
| API | **FastAPI** (Python 3.12), `httpx` async, `sse-starlette` | Async I/O to IRSA. Same language as the science code. |
| Science | **astropy** (WCS/SIP, coordinates, time, LombScargle), **numpy/scipy**, **reproject**, **photutils** | Standard and trusted; matches IRSA tutorials. photutils is pure Python, which avoids `sep` build problems on new Pythons. |
| Jobs | **In-process**: asyncio tasks for I/O, a `ProcessPoolExecutor` for CPU work, an in-memory job registry, one API process | Fewest moving parts. Add arq + Redis only to scale past one VM. |
| Cache | Local SSD: `diskcache` for coverage and ephemerides (TTL); content-addressed files for frames, stacks and cubes | No Redis needed |
| Remote FITS | astropy + fsspec over HTTPS range requests | Reads row sections from S3 without s3fs |
| Deploy | Docker Compose (API + Caddy) on one VM in **AWS us-east-1**, next to the bucket. A demo laptop runs the same image in snapshot mode. | Simple, fast, and offline-capable |

### 2.3 Request lifecycle
```
user → POST /api/v1/views {params}
  1. resolve → position function pos(t)   (star: PM + parallax; Solar System body: Horizons)
  2. coverage: one SIA2 call               (cached; refreshed when release_state moves, or after 24 h)
  3. plan: dedup → frame list F (sorted URLs; versions are in the names)
           key = sha256(canonical params + F)
  ├─ cache hit  → 200 {view manifest}              (warm: <300 ms)
  └─ cache miss → 202 {job_id}; client subscribes /api/v1/jobs/{id}/events (SSE)
        job: fetch the selected band's detector first (≈60 frames), then the rest
             (bounded concurrency) → preprocess → reproject → reject transients
             → stack + spectral cube per (time-bin, band)  [emit "stack_ready" as each finishes]
             → (optional) λ-matched diff, astrometry, spectra
        client renders stacks progressively as events arrive
```
- **Why key on the frame list:** a key built from a global `release_state` changes whenever *any* new data lands anywhere in the sky. That cold-starts every cached view, including the pre-warmed demo, possibly in the middle of judging. Keying on the exact frame list changes the key only when frames *covering this view* change. Individual frames are immutable, because their filenames carry the pipeline version.
- **Pinned links:** `pin=<12 hex of sha256(F)>` freezes the frame list. ✅ 11-07 (D): F is hashed as
  `sha256("\n".join(sorted(access URLs)))` (`access/pins.py::frame_list_digest`); pins for the 5 targets are in
  `config/pins/` (index: `config/pins/index.json`). README and demo permalinks are pinned, so new data can neither alter nor cold-start them. The UI shows "newer data available → update".
- **Band-first planning:** the selected band's ≈60 frames arrive first, so the first blink appears long before all ≈360 frames are in.

---

## 3. Data access layer

### 3.1 Release registry (`config/releases.yaml`)
```yaml
# Add DR1 here the day IRSA announces its collection names. No code changes needed.
# ✅ 11-06: the bucket has no dr1/ prefix yet (only qr2/ and qr3/).
releases:
  - id: qr3
    collections: [spherex_qr3, spherex_qr3_deep]
    s3_prefix: qr3/
    pipeline_family: R7
    photometric_scale: qr3          # reference gain scale
    priority: 30
  - id: qr2
    collections: [spherex_qr2, spherex_qr2_deep]
    s3_prefix: qr2/
    pipeline_family: "6.x"
    photometric_scale: qr2          # needs l3_flux_corrections to reach qr3 scale
    priority: 20
  # - id: dr1                       # expected "late fall 2026"; supersedes qr2 for Surveys 1–2
  #   collections: [<from IRSA>]
  #   s3_prefix: dr1/
  #   pipeline_family: R7
  #   photometric_scale: qr3
  #   priority: 40
never_use: [qr1]                    # retired Feb 2026; never mix with later releases
calibration:
  release: qr3                      # spectral_wcs, spectral_channels, epsf, l3_flux_corrections
  discover_by_listing: true         # real dir is cal-swcs-v5-2026-191, not the documented cal-wcs
include_deep: auto                  # include *_deep collections when a target lies in a deep field
```

### 3.2 Coverage: SIA2 first, TAP as fallback
```python
# spherex/access/coverage.py
import io
import httpx
from astropy.io.votable import parse_single_table

SIA = "https://irsa.ipac.caltech.edu/SIA"
IBE_PREFIX = "https://irsa.ipac.caltech.edu/ibe/data/spherex/"

async def coverage(client: httpx.AsyncClient, ra, dec, radius_deg, collections):
    """Every frame that overlaps a circle, from all collections in one call.
    ✅ 11-06: COLLECTION may repeat. qr2+qr3 for Barnard → 359 rows in ≈6 s (TAP: same rows, 10–17 s)."""
    params = [("POS", f"CIRCLE {ra:.7f} {dec:.7f} {radius_deg:.6f}"), ("RESPONSEFORMAT", "VOTABLE")]
    params += [("COLLECTION", c) for c in collections]
    r = await client.get(SIA, params=params, timeout=60)
    r.raise_for_status()
    rows = []
    for row in parse_single_table(io.BytesIO(r.content)).to_table():
        url = str(row["access_url"])
        rows.append(dict(collection=str(row["obs_collection"]), obs_id=str(row["obs_id"]),
                         band=str(row["energy_bandpassname"]), t_min=float(row["t_min"]),
                         access_url=url, s3_key=url.removeprefix(IBE_PREFIX)))
    return rows
```
- **Radius:**
  - **Target-centred views (the default):** radius 0.001°. Frames that contain the target are what matter; one that only grazes a corner of the view adds little.
  - **Discovery views:** the FOV half-diagonal, because SIA2 `POS=CIRCLE` matches every image that overlaps the circle.
- **Caching:** cache by (rounded position, radius, collections) for 24 h, or until `release_state` (§3.6) moves.
- **Freshness:** SIA2 lags ingest by about a day. That is fine for interactive use.

**TAP fallback** (also used by the release watcher and back-fills). The same joins return detector names and file URIs:
```python
TAP = "https://irsa.ipac.caltech.edu/TAP/sync"
COVERAGE_SQL = """
SELECT o.collection, o.observationid, p.energy_bandpassname,
       p.energy_bounds_lower, p.energy_bounds_upper,
       p.time_bounds_lower, p.time_bounds_upper, p.time_exposure,
       a.uri, a.contentlength
FROM spherex.plane AS p
JOIN spherex.artifact AS a ON a.planeid = p.planeid
JOIN spherex.observation AS o ON o.obsid = p.obsid
WHERE 1 = CONTAINS(POINT('ICRS', {ra}, {dec}), p.poly)
  AND o.collection IN ({collections})
ORDER BY p.time_bounds_lower
"""
# ✅ CONTAINS(POINT, poly) with these joins works. ✅ 11-06: even a trivial TAP query takes 10–17 s
#    (service overhead), so keep TAP off the interactive path.
# ⚠️ INTERSECTS works only column-first (INTERSECTS(p.poly, CIRCLE(...))), and the joined version timed
#    out (>200 s). Use SIA2 for FOV coverage instead.
# ✅ 11-06: one artifact per plane, all image/fits. a.uri → HTTP: "https://irsa.ipac.caltech.edu/" + uri;
#    S3 key: uri.removeprefix("ibe/data/spherex/").
```

### 3.3 Deduplication and version policy
```python
# spherex/access/dedup.py
import re
FNAME = re.compile(r"level2_(?P<obsid>\w+?)D(?P<det>\d)_spx_l2b(?:_retry)?-v(?P<ver>\d+)-(?P<y>\d{4})-(?P<doy>\d{3})(?P<fix>\+psffix1)?\.fits")
# ✅ 11-06: 11 of the 3,878 files covering the 5 targets are named `…_spx_l2b_retry-v27-…` (QR3 reprocessing
# retries); without `(?:_retry)?` dedup silently skips them (validation/G1-time-model, I → D).

def collection_priority(registry) -> dict[str, int]:
    return {c: rel["priority"] for rel in registry["releases"] for c in rel["collections"]}

def dedup(rows, coll_prio):
    """One frame per (observation id, detector). Prefer the newer release, then the newer pipeline
    version, then the newer processing date. Handles the 2026-05-16..07-19 frames that exist in QR2
    today and will reappear as R7 with DR1. Unknown file names and collections are skipped, not fatal."""
    best = {}
    for r in rows:
        m = FNAME.search(r["access_url"])
        if m is None or r["collection"] not in coll_prio:
            continue
        key = (m["obsid"], int(m["det"]))
        rank = (coll_prio[r["collection"]], int(m["ver"]), int(m["y"]) * 1000 + int(m["doy"]))
        if key not in best or rank > best[key][0]:
            best[key] = (rank, r)
    return [v[1] for v in best.values()]
```
✅ 11-06: each exposure covers a target on a co-aligned **detector pair** (D1/D4, D2/D5, D3/D6), so one observation id normally yields two frames. That is expected, not a duplicate.
✅ 11-07 (D, `backend/spherex/access/dedup.py`): the rank is (release priority, pipeline version, processing date,
`+psffix1`, `_retry`). Skipped rows (unknown file names, collections not in the registry, `never_use`) and
superseded rows are returned with reasons, so a new DR1 collection is never used before the registry lists it.
F11: SIA2 and TAP return identical deduplicated sets for all 5 targets; no target has a superseded row today.

### 3.4 Pixel fetchers (pluggable `FrameSource` interface)
Both sources return the same `RawFrame(hdus, wcs, origin)`. `origin` is the 0-based parent-detector pixel of the frame's pixel (0, 0). Every per-pixel calibration lookup uses it (§3.5).

**Which source by default?**
| Where the API runs | Default | Why |
|---|---|---|
| AWS us-east-1 | **S3 row sections** (A) | Same region as the bucket: tens of ms per range request, no egress cost, no load on IRSA, no throttling. It reads whole rows, ≈3 MB per frame for a 6′ view, which is fine in-region. |
| Anywhere else | **IRSA cutout, stream-aborted** (B) | ≈190 KB per frame for a 6′ view, ≈15× fewer bytes than S3 rows |
| Either | Fail over to the other source after 3 consecutive failures, and re-probe every 5 min | ✅ 11-06: IRSA returned a 503 under 4 parallel requests and some truncated bodies |

**Size every request for rotation.** Frames are rotated relative to the north-up grid, at any angle in RA/Dec, so a square cutout must be √2 larger than the display square:
```python
def cutout_size_deg(fov_arcmin, margin_px=4, pix_arcsec=6.15):
    """Square cutout that covers a north-up display square at any rotation, plus a few pixels for
    interpolation and PSF wings."""
    return (fov_arcmin * 2 ** 0.5 + 2 * margin_px * pix_arcsec / 60) / 60
```
Snap cutout centres to a 30″ grid and sizes up to the next preset (3′, 6′, 12′, 24′, 48′, plus 30″). Nearby views and small pans then reuse cached cutouts.

✅ 11-07 (D, F2): IRSA returns an axis-aligned n×n box in frame pixels. "Pixel centres within c ± size/2"
fits 4 of 7 observed boxes exactly and is 1 px short on one axis for the other 3, so IRSA's exact sizing isn't
reproduced. `S3SectionSource` therefore reads that box **plus 1 px** (a superset), and failover never loses
pixels. Either source's `RawFrame.origin` gives identical per-pixel lookups.

#### A) S3 row sections (default in us-east-1; best for large FOVs)
```python
# spherex/access/s3sections.py
import numpy as np
from astropy.io import fits
from astropy.wcs import WCS

S3_HTTPS = "https://nasa-irsa-spherex.s3.amazonaws.com/"     # anonymous, CORS-enabled ✅; no s3fs needed

def read_s3_section(key, grid_wcs, grid_shape, hdus=("IMAGE", "FLAGS", "VARIANCE", "ZODI"), margin=4):
    with fits.open(S3_HTTPS + key, use_fsspec=True, lazy_load_hdus=True,
                   fsspec_kwargs={"block_size": 256 * 1024}) as hl:
        h = hl["IMAGE"].header                                    # header-only read
        w = WCS(h)
        ny_g, nx_g = grid_shape                                   # grid corners → frame pixels:
        gx = np.array([-0.5, nx_g - 0.5, -0.5, nx_g - 0.5])       # this includes any rotation and
        gy = np.array([-0.5, -0.5, ny_g - 0.5, ny_g - 0.5])       # works across RA = 0 and near poles
        px, py = w.world_to_pixel(grid_wcs.pixel_to_world(gx, gy))
        x0, x1 = max(int(np.floor(px.min())) - margin, 0), min(int(np.ceil(px.max())) + margin + 1, h["NAXIS1"])
        y0, y1 = max(int(np.floor(py.min())) - margin, 0), min(int(np.ceil(py.max())) + margin + 1, h["NAXIS2"])
        if x0 >= x1 or y0 >= y1:
            return None                                           # the grid misses this frame
        out = {n: (hl[n].header, hl[n].section[y0:y1, x0:x1]) for n in hdus}   # whole rows are fetched
    sub_wcs = w.slice((slice(y0, y1), slice(x0, x1)))             # CRPIX shifted; SIP stays valid
    return out, sub_wcs, (x0, y0)                                 # origin is known directly
```
- **Byte map** (✅ 11-06, full QR3 file): IMAGE data starts at byte 25,920 and is exactly 5,780 FITS blocks (16,646,400 B). Each row is 8,160 B.
- **`FLAGS` is tile-compressed in full QR3 files** (✅ 11-06, found by F1; ✅ 11-07, F2: full **QR2** 6.5.x files store it as a plain int32 image, and `s3sections.py` handles both): a RICE_1 BINTABLE with one-row tiles (`ZBITPIX = 32`, ≈11 MB), not a plain image, so `section` reads of FLAGS go through the compressed-HDU path (row descriptors, then each row's heap bytes). IMAGE, VARIANCE and ZODI are plain images. The S3 section and the cutout return identical pixels in all four HDUs for the Barnard fixture frame (`validation/F1/`, supporting evidence for F2).
- **Cost:** a 6′ view needs ≈90 rows × 8,160 B × 4 HDUs ≈ 3 MB per frame. That is free and fast in-region but wasteful elsewhere.

#### B) IRSA cutout, streamed and aborted after `ZODI` (default outside AWS)
```python
# spherex/access/fitsstream.py
import math, numpy as np, httpx
from astropy.io import fits

BLOCK = 2880
_DT = {8: ">u1", 16: ">i2", 32: ">i4", 64: ">i8", -32: ">f4", -64: ">f8"}
WANTED = ("IMAGE", "FLAGS", "VARIANCE", "ZODI")   # HDUs 1–4: they end at byte 89,280 of a 29×29 cutout ✅ 11-06

class _Reader:
    def __init__(self, resp):
        self._it, self._buf = resp.aiter_bytes(), bytearray()
    async def take(self, n: int) -> bytes:
        while len(self._buf) < n:
            chunk = await anext(self._it, None)
            if chunk is None:
                raise EOFError("stream ended early")    # ✅ 11-06: seen on HTTP 200 responses → retry
            self._buf += chunk
        out = bytes(self._buf[:n]); del self._buf[:n]
        return out

async def _read_header(rd: _Reader) -> fits.Header:
    raw = b""
    while True:
        blk = await rd.take(BLOCK); raw += blk
        if any(blk[i:i + 8] == b"END     " for i in range(0, BLOCK, 80)):
            return fits.Header.fromstring(raw.decode("ascii"))

def _data_bytes(h: fits.Header) -> int:
    """FITS standard: |BITPIX|/8 · GCOUNT · (PCOUNT + NAXIS1 · … · NAXISn)."""
    n = h.get("NAXIS", 0)
    if n == 0:
        return 0
    return abs(h["BITPIX"]) // 8 * h.get("GCOUNT", 1) * (
        h.get("PCOUNT", 0) + math.prod(h[f"NAXIS{i}"] for i in range(1, n + 1)))

def _decode(h: fits.Header, raw: bytes) -> np.ndarray:
    shape = tuple(h[f"NAXIS{i}"] for i in range(h["NAXIS"], 0, -1))
    arr = np.frombuffer(raw, dtype=_DT[h["BITPIX"]]).reshape(shape)
    if arr.dtype.kind in "iu" and h.get("BSCALE", 1) == 1:
        return arr.astype(np.int64) + int(h.get("BZERO", 0))     # keep integers: FLAGS needs bit tests
    if "BSCALE" in h or "BZERO" in h:
        return arr * h.get("BSCALE", 1.0) + h.get("BZERO", 0.0)
    return arr.astype(arr.dtype.newbyteorder("="))

async def fetch_cutout(client: httpx.AsyncClient, access_url: str, ra: float, dec: float,
                       size_deg: float, wanted=WANTED) -> dict[str, tuple[fits.Header, np.ndarray]]:
    url = f"{access_url}?center={ra:.7f},{dec:.7f}deg&size={size_deg:.5f}"   # size defaults to degrees ✅
    out: dict[str, tuple[fits.Header, np.ndarray]] = {}
    async with client.stream("GET", url, timeout=90) as resp:
        resp.raise_for_status()
        rd = _Reader(resp)
        while len(out) < len(wanted):
            h = await _read_header(rd)
            nbytes = _data_bytes(h)
            data = await rd.take(-(-nbytes // BLOCK) * BLOCK) if nbytes else b""
            name = h.get("EXTNAME", "PRIMARY").strip()
            if name in wanted:
                out[name] = (h, _decode(h, data[:nbytes]))
    return out   # leaving the context closes the connection before EPSF is transferred
```
- **Cost:** about 66 KB of headers plus 16·N² bytes per frame, against about 4 MB naive ✅. A 6′ view (an 8.9′ cutout with margin) is ≈190 KB. ✅ 11-07 (F12): 6′ cutouts measured ≈200 KB, p50 ≈3 s from our network.
- **Wavelengths:** get them without `WCS-WAVE`, from the cached `CWAVE` map (§3.5).
- **`gzip=true`** doesn't help (✅ 11-06). Stream-abort is better.

#### Retries
```python
# spherex/access/retry.py
import asyncio, random, httpx

RETRYABLE = (httpx.TransportError, EOFError)

async def with_retry(fetch, *args, tries=4):
    for k in range(tries):
        try:
            return await fetch(*args)
        except httpx.HTTPStatusError as e:
            code = e.response.status_code
            if code < 500 and code != 429:
                raise                                   # 4xx: e.g. the point is off this frame
        except RETRYABLE:
            pass
        await asyncio.sleep(min(30, 2 ** k) * (0.5 + random.random()))   # backoff with jitter
    raise RuntimeError(f"gave up after {tries} tries")
```
A frame that still fails is listed in the manifest as skipped. Never fail a whole view.

### 3.5 Calibration cache and parent-pixel lookups
```python
# spherex/calib.py
import numpy as np
from astropy.io import fits

class Calib:
    """Per-detector static maps, downloaded once per calibration release (≈6×33 MB + 4 MB + 6×8 MB + 6×17 MB)."""
    def __init__(self, paths):
        get = lambda p, **kw: fits.getdata(p, memmap=True, **kw)
        self.cwave = {d: get(paths.spectral_wcs[d], extname="CWAVE") for d in range(1, 7)}  # µm
        self.cband = {d: get(paths.spectral_wcs[d], extname="CBAND") for d in range(1, 7)}  # µm
        self.channel = get(paths.spectral_channels, extname="CHANNEL_MAP")  # ✅ 11-06 F3: HDU 1, uint8, one map
        #   for all detectors (DETECTOR='ALL'); 1..17 channels, 0 = blueward of ch 1, 18 = redward of ch 17
        self.fluxcorr = {d: get(paths.flux_corr[d]) for d in range(1, 7)}  # QR2 → QR3 scale

def parent_origin(img_hdr) -> tuple[int, int]:
    """IRSA cutouts only: 0-based parent-detector pixel of cutout pixel (0,0).
    IRSA: x_orig = 1 + x_cut - CRPIX1A (x_cut 0-based). Example ✅: CRPIX1A=-642 → x0=643.
    S3 sections already know their origin, and a full-file header must NOT be read this way."""
    return int(round(1 - img_hdr["CRPIX1A"])), int(round(1 - img_hdr["CRPIX2A"]))

def parent_slice(origin, shape):
    (x0, y0), (ny, nx) = origin, shape
    return np.s_[y0:y0 + ny, x0:x0 + nx]
```
> ✅ 11-07 (D): implemented in `backend/spherex/calib.py`: `discover` (bucket listing, newest version per
> product and detector), `config/calibration.lock` (25 files, MD5 = ETag, sha256, `lock_hash 94e18b883fdc9b28`),
> `bootstrap` (resumable, verified), `Calib` (memory-mapped; `fluxcorr` and `solid_angle` read the HDU named
> `IMAGE`), `SlicedCalib` for fixtures. `scripts/bootstrap_calib.py discover|fetch --freeze|verify`.
>
> **Day-1 verification (§11.0):**
> - On one full file, check that `cwave[parent_slice]` matches the `WCS-WAVE` bilinear lookup to ≈1 nm. Both are in `DETCOORD='sky'` orientation.
> - Confirm the HDU index of the channel map in `spectral_channels`.
> - Confirm whether the `l3_flux_corrections` factors multiply or divide QR2 fluxes.

### 3.6 Release watcher (cheap and robust)
New data shows up as **new planning-period prefixes** in S3. Listing them with a delimiter is one small request:
```python
# GET https://nasa-irsa-spherex.s3.amazonaws.com/?list-type=2&prefix=qr3/level2/&delimiter=/
# → CommonPrefixes: qr3/level2/2026W30_1B/ … qr3/level2/2026W40_2A/   (✅ 11-06: 23 periods, newest 2026W40_2A)
import re
PP = re.compile(r"(\d{4})W(\d{2})_(\d)([A-Z])")
def pp_key(prefix: str):          # sort by parsed fields, not by string; follow continuation tokens
    y, w, n, s = PP.search(prefix).groups()
    return int(y), int(w), int(n), s
```
- **Schedule:** run hourly. Store `release_state = {qr3: "2026W40_2A", ...}` on disk. A top-level listing (`?list-type=2&delimiter=/`) also detects a new `dr1/` prefix.
- **Effects:**
  - It refreshes cached *coverage* (not view keys, see §2.3) and the UI freshness badge: "Latest SPHEREx data: planning period 2026W40 (≈early Oct 2026)".
  - Views whose frame list changes get new keys. Pinned links stay as they are and show "newer data available".
- **SIA2 caveat:** SIA2 lags about a day behind the S3 listing. The watcher can confirm new frames with TAP.
- ✅ 11-07 (D): `backend/spherex/access/watcher.py` + `scripts/refresh_check.py`. The first run records a
  baseline, but an unknown top-level prefix (DR1) is reported even then. A new release is reported as
  "detected, NOT adopted" and the code never writes `config/releases.yaml`. Candidate pins are diffed against the
  current pins (docs/data-refresh.md).

### 3.7 Politeness and resilience
- **Concurrency:** start at **4** concurrent IRSA requests per process, behind a global semaphore. Raise it only after a soak test from the VM (✅ 11-06: 4 parallel requests from our network drew a 503). S3 range reads in-region can use 32 or more. ✅ 11-07 (F12, our network): 503s on 9.6% of requests at 4 concurrent and 4.1% at 2, steady over time, with no truncation in 929 requests. Do not raise concurrency; the VM soak (`scripts/verify/f12_framesource_bench.py --deployment`) decides the default.
- **Retries:** exponential backoff with jitter on 429/5xx, truncation (`EOFError`) and transport errors (§3.4). Then skip the frame and report it in the manifest.
- **Health checks:** probe SIA2 and S3 in `/healthz`, not TAP (TAP needs 10–17 s even for trivial queries).
- **User-Agent:** `ParallaX/0.1 (+repo URL; NASA Space Apps 2026)`.
- **Caching:**
  - Cache every frame forever under `sha1(url) + snapped box`.
  - Cache coverage for 24 h, or until `release_state` changes.
  - Cache Horizons and SkyBoT results forever, keyed by object and time list.

---

## 4. The science core

### 4.1 Target resolution, epochs and position functions
```python
# spherex/targets.py
import re
import numpy as np
import astropy.units as u
from astropy.coordinates import SkyCoord, Distance
from astropy.time import Time

SIMBAD_TAPS = ("https://simbad.harvard.edu/simbad/sim-tap/sync",       # ✅ 11-06 CfA mirror
               "https://simbad.cds.unistra.fr/simbad/sim-tap/sync")    # CDS timed out from our network twice
ALIASES = {  # what people type → an identifier SIMBAD resolves (✅ 11-06; SIMBAD normalizes the rest)
    "barnard's star": "NAME Barnard's Star", "barnards star": "NAME Barnard's Star",
    "eps ind b": "* eps Ind B", "eps indi b": "* eps Ind B", "epsilon indi b": "* eps Ind B",
    "ε indi b": "* eps Ind B", "ε ind b": "* eps Ind B",
    "wise 0855": "WISE J085510.83-071442.5", "wise 0855-0714": "WISE J085510.83-071442.5",
    "wise j0855-0714": "WISE J085510.83-071442.5", "wise j085510.83-071442.5": "WISE J085510.83-071442.5",
    "rw aur": "V* RW Aur", "rw aurigae": "V* RW Aur", "r dra": "V* R Dra", "r draconis": "V* R Dra",
}

def normalize_query(q: str) -> str:
    q = q.replace("−", "-").replace("–", "-").replace("’", "'")   # − – ’ → - - '
    return re.sub(r"\s+", " ", q).strip()

def adql_literal(s: str) -> str:
    return "'" + s.replace("'", "''") + "'"       # "Barnard's Star" breaks an unescaped query ✅ 11-06

SQL = """SELECT b.oid, b.main_id, b.ra, b.dec, b.pmra, b.pmdec, b.plx_value, b.plx_bibcode,
       b.rvz_radvel, b.sp_type, b.otype
FROM basic AS b JOIN ident AS i ON i.oidref = b.oid WHERE i.id = {name}"""
GAIA_ID_SQL = "SELECT id FROM ident WHERE oidref = {oid} AND id LIKE 'Gaia DR3 %'"
# usage: SQL.format(name=adql_literal(ALIASES.get(q.lower(), q))) with q = normalize_query(user_text)

def propagate(ra, dec, pmra_masyr, pmdec_masyr, plx_mas, rv_kms, epoch_from: Time, epoch_to: Time) -> SkyCoord:
    """Barycentric position at epoch_to (uniform space motion). Pass rv only with Gaia's own J2016.0
    astrometry. SIMBAD's J2000 positions were back-propagated *linearly*, so propagate those with rv=None.
    ✅ 11-06, Barnard at 2026.87: Gaia+RV → +04°46′14.6″; SIMBAD-J2000 linear → 14.6″; SIMBAD-J2000+RV → 15.0″."""
    c = SkyCoord(ra=ra * u.deg, dec=dec * u.deg,
                 pm_ra_cosdec=(pmra_masyr or 0) * u.mas / u.yr, pm_dec=(pmdec_masyr or 0) * u.mas / u.yr,
                 distance=Distance(parallax=max(plx_mas or 0.01, 0.01) * u.mas),
                 radial_velocity=(rv_kms or 0) * u.km / u.s, obstime=epoch_from)
    return c.apply_space_motion(new_obstime=epoch_to)

def seen_by_spherex(src, mjd):
    """Where SPHEREx sees a star at time(s) mjd: barycentric propagation plus annual parallax.
    No aberration term: frame WCSs are tied to Gaia exposure by exposure, which absorbs it."""
    c = propagate(src.ra, src.dec, src.pmra, src.pmdec, src.plx, src.rv, src.epoch, Time(mjd, format="mjd"))
    pa, pd = parallax_factors(mjd, c.ra.deg, c.dec.deg)                    # §4.7
    p = (src.plx or 0.0) / 3.6e6                                            # mas → deg
    return c.ra.deg + p * pa / np.cos(np.radians(c.dec.deg)), c.dec.deg + p * pd
```
- **Resolver order:**
  1. Coordinates (decimal or sexagesimal, Unicode minus allowed).
  2. The alias table, then SIMBAD with an escaped literal (CfA mirror first).
  3. If SIMBAD knows a Gaia DR3 ID (`GAIA_ID_SQL`), take the astrometry from Gaia at IRSA (`gaia_dr3_source`, J2016.0, with RV).
  4. No SIMBAD match → JPL Horizons (§4.11), or `sso:<name>` explicitly.
- **One position function everywhere:** `pos(t)` is `seen_by_spherex` for stars and Horizons for Solar System bodies. Overlays, track mode, forced photometry and astrometric residuals all call it, so the model is consistent.

**Epoch guard (UX).** When a user types coordinates:
1. Cone-search SIMBAD within **6′** for high-PM objects. 6′ covers 10.4″/yr over 34 years:
   ```sql
   SELECT ... FROM basic WHERE 1 = CONTAINS(POINT('ICRS', ra, dec), CIRCLE('ICRS', {ra}, {dec}, 0.1))
     AND pmra * pmra + pmdec * pmdec > 250000          -- > 0.5″/yr
   ```
2. For each candidate, find the epoch at which its track passes closest to the input:
   ```python
   def epoch_of_match(ra_in, dec_in, src, years=np.arange(1990.0, 2031.0, 0.02)):
       track = propagate(src.ra, src.dec, src.pmra, src.pmdec, src.plx, None, src.epoch,
                         Time(years, format="decimalyear"))
       sep = track.separation(SkyCoord(ra_in * u.deg, dec_in * u.deg)).arcsec
       i = int(np.argmin(sep))
       return years[i], sep[i]     # banner when sep < 3″ and |years[i] − now| > 1 yr
   ```
3. Show the banner: *"These coordinates match WISE 0855−0714 as of ≈2010.5. It has since moved 2.2′ west. [Track it] [Keep fixed sky]"*. For the challenge coordinate this gives epoch 2010.46 at a 0.2″ separation.

The same search labels a user's *current* position for Barnard (4.6′ from J2000) as "Barnard's Star (2026 position)".

**Two centring modes:**
- **Fixed sky** (default for discovery): one grid for all frames, so movers move. Centre it on `pos(t)` at the *median frame time*, so the mover stays near the centre in every visit.
- **Track** (for photometry and spectra of a known mover): each frame's grid is centred on `pos(MJD-AVG)` of that frame, so the target stays still and the stars stream past. For Solar System bodies this is the only useful mode.

### 4.2 The time model: visits, partial visits, surveys and bins
```python
# spherex/epochs.py
import numpy as np
SCIENCE_START_MJD = 60796.0          # 2025-05-01
HALF_MISSION_DAYS = 12.5 * 30.4375   # Surveys 1/2 vs 3/4 split (Supplement §2.2) → 2026-05-16

def survey_number(mjd: float, sps_epa: float) -> int | None:
    if mjd < SCIENCE_START_MJD:
        return None                                   # commissioning (IOC) frames
    pa180 = abs(((sps_epa + 180.0) % 360.0) - 180.0) > 90.0
    second_year = (mjd - SCIENCE_START_MJD) > HALF_MISSION_DAYS
    return (3 if second_year else 1) + (1 if pa180 else 0)

def cluster_visits(mjd, gap_days: float = 20.0) -> np.ndarray:
    mjd = np.asarray(mjd, float)
    if mjd.size == 0:
        return np.empty(0, int)
    order = np.argsort(mjd)
    lab = np.empty(mjd.size, int)
    lab[order] = np.r_[0, np.cumsum(np.diff(mjd[order]) > gap_days)]
    return lab

def choose_axis(mjd, lab) -> str:
    """Fixed bins for dense coverage. Continuous coverage (R Dra) forms ONE long cluster, so a rule
    based only on 'more than 6 visits' or 'median gap' would miss it."""
    spans = np.array([np.ptp(mjd[lab == k]) for k in np.unique(lab)])
    return "bin:14d" if (spans.size > 6 or spans.max() > 60) else "visit"   # ✅ 11-06: 45 d turned ε Ind B
    # (visits span 46.3 and 44.9 d with tails) into bins; R Dra's shortest cluster is 88.7 d (decision 0002)

def fixed_bins(mjd: np.ndarray, width_days: float) -> np.ndarray:
    return np.floor((mjd - mjd.min()) / width_days).astype(int)
```
- **Visits** are the default axis.
- **Full vs partial:** a visit is **full** in a band when its detector has ≥ 10 frames. Otherwise:
  - merge it into its nearest full neighbour if the merged visit spans ≤ 21 d (the "1–3 weeks" visit length; docs/decisions/0001: the earlier "neighbour ≤ 45 d away" merged WISE 0855's Dec 2025 cluster);
  - if not, keep it as a **partial** visit, hatched on the timeline, off in the default blink, and used for astrometry.

  ✅ 11-06, WISE 0855 band 6 has frame counts 3 · 16 · 3 · 21. That gives two full visits and two partial ones. Merging the May 2025 cluster into a visit six months away would be wrong, and dropping it would throw away the one-year baseline.
- **Per-band epochs:** each (visit, band) stack carries its own mean MJD. A visit can reach the three detector pairs on different days.
- **Fixed bins:** default width 14 d.
- **Labels:** each time-bin label shows the date range, survey number(s), frame count and status, e.g. `V2 · 2026-03-11→04-10 · S1 · 113 frames`, or `V1 · 2025-05-05/06 · S1 · partial (3 in band 6)`.

### 4.3 Per-frame preprocessing
```python
# spherex/flags.py
import numpy as np

def flag_bits(flags_hdr) -> dict[str, int]:
    """Mask plane names and values are self-described, so read them from the header instead of
    hardcoding. ✅ 11-06 (F6): two conventions exist. QR3 (R7 7.0.x): MSKNnnnn / MSKMnnnn. QR2 (6.x):
    HIERARCH MP_<NAME> = <bit>. Reading only the first masked nothing on every QR2 frame."""
    out = {}
    for k in flags_hdr:
        if k.startswith("MSKN"):
            n = k[4:]
            out[flags_hdr[k].strip()] = int(flags_hdr.get("MSKM" + n, 1 << int(n)))
        elif k.startswith("MP_"):
            out[k[3:]] = 1 << int(flags_hdr[k])
    if not out:
        raise ValueError("FLAGS header defines no mask planes")
    return out
# ✅ 11-06 (F6): bit numbers agree with understanding.md §4.4 in every release, but plane *sets* differ:
# 6.4 has no BLOOM/CROSSTALK/GHOST*/HALO/SNOWBALL/STREAK; 6.5.6 no CROSSTALK/STREAK; 7.0.5 no SATELLITE_HALO.
# QR2 also defines PHANTOM (4) and REFERENCE (5); REFERENCE (not light-sensitive) is masked in every preset.

PRESETS = {
    # IRSA Mosaic Tool list (Supplement §3.4.3): clean imaging
    "imaging": ["TRANSIENT", "SUR_ERROR", "NONFUNC", "DICHROIC", "MISSING_DATA", "HOT", "COLD",
                "PHANMISS", "NONLINEAR", "PERSIST", "CROSSTALK", "GHOST", "GHOST_FPA", "GHOST_EXT",
                "STREAK", "BLOOM", "SNOWBALL", "HALO", "SATELLITE_HALO"],
    # IRSA photometry list (Supplement §3.3)
    "photometry": ["SUR_ERROR", "NONFUNC", "MISSING_DATA", "HOT", "COLD", "NONLINEAR", "PERSIST",
                   "BLOOM", "SNOWBALL", "HALO", "SATELLITE_HALO"],
    # Ours: like imaging, but keep STREAK (fast NEOs) visible. OUTLIER and SOURCE are never masked.
    "discovery": ["TRANSIENT", "SUR_ERROR", "NONFUNC", "DICHROIC", "MISSING_DATA", "HOT", "COLD",
                  "PHANMISS", "NONLINEAR", "PERSIST", "CROSSTALK", "GHOST", "GHOST_FPA", "GHOST_EXT",
                  "BLOOM", "SNOWBALL", "HALO", "SATELLITE_HALO"],
    # Ours, for bright targets (Barnard, R Dra, RW Aur): mask only hard-bad pixels. Footprint flags
    # (BLOOM, HALO, NONLINEAR, PERSIST, GHOST…) can cover the star itself; draw them instead.
    "bright": ["TRANSIENT", "SUR_ERROR", "NONFUNC", "MISSING_DATA", "HOT", "COLD"],
}

def bad_mask(flags: np.ndarray, bits: dict[str, int], preset: str) -> np.ndarray:
    m = 0
    for name in PRESETS[preset]:
        m |= bits.get(name, 0)
    return (flags & m) != 0
```
```python
# spherex/preprocess.py
import numpy as np
from astropy.stats import sigma_clipped_stats
from .calib import parent_slice
from .flags import flag_bits, bad_mask
from .stack import frame_weight

def calibrate_frame(hdus, origin, calib, preset="discovery", release_scale="qr3", min_sky_pix=50):
    (hi, img), (hf, flg), (_, var), (_, zodi) = (hdus[k] for k in ("IMAGE", "FLAGS", "VARIANCE", "ZODI"))
    bits = flag_bits(hf)
    ps = parent_slice(origin, img.shape)              # origin from the FrameSource (§3.4), never guessed
    bad = bad_mask(flg, bits, preset) | ~np.isfinite(img) | ~(var > 0)
    sci = img - zodi                                  # 1) model zodi (not subtracted in L2)
    if release_scale == "qr2":                        # 2) QR2 → QR3 photometric scale (verify multiply vs
        fc = calib.fluxcorr[hi["DETECTOR"]][ps]       #    divide on day 1). Order vs. step 1 only changes a
        sci, var = sci * fc, var * fc ** 2            #    smooth term that step 3 removes.
    src = (flg & bits.get("SOURCE", 0)) != 0          # 3) local residual background: He 1.083 µm,
    sky = ~bad & ~src                                 #    aurora, shuttle glow, zodi error
    if sky.sum() < min_sky_pix:                       #    SOURCE can cover ≈all pixels of a small,
        sky = ~bad                                    #    crowded box (81% at Barnard ✅)
    med = sigma_clipped_stats(sci[sky], sigma=3.0)[1] if sky.any() else 0.0
    sci = sci - med
    sci[bad] = np.nan
    w_frame = frame_weight(var, sky)                  # 4) one weight per frame (§4.5)
    lam = calib.cwave[hi["DETECTOR"]][ps]             # per-pixel λ (µm)
    return sci, var, bad, lam, flg, bits, sky, w_frame
```
- **Smooth background:** for FOVs larger than about 10′, replace the scalar `med` with a smooth 2-D background (`photutils.Background2D`, box ≈ 16 px), because atmospheric lines vary along the LVF (λ) axis.
- **Frame QA:**
  - Reject a frame when `FINAST != 0` (astrometry is what a blink depends on) or when more than 50% of the box is bad.
  - Show `L1DQAFLG`/`L2DQAFLG` as badges, and hard-reject on a `Fail`. ✅ 11-06 (F8): 0 of the 3,878 frames of the 5 targets fail either keyword or FINAST, so the rule removes nothing today and guards future releases (`validation/F8/`).
- **Bright-target display (P1-7):**
  1. Fit the ePSF (§4.7) to unflagged wing pixels with the core masked.
  2. Fill NaN core pixels with the model *in the display stack only*.
  3. Draw a dashed outline around the filled pixels, and offer "show raw".
  4. Filled pixels are tagged and never reach measurements.

### 4.4 Common grid and reprojection
```python
# spherex/grid.py
import numpy as np
from astropy.wcs import WCS
from reproject import reproject_interp

def make_grid(ra, dec, fov_arcmin, pix_arcsec=6.15):
    n = int(fov_arcmin * 60 / pix_arcsec) | 1                    # odd → centre on a pixel
    w = WCS(naxis=2)
    w.wcs.ctype = ["RA---TAN", "DEC--TAN"]; w.wcs.crval = [ra, dec]
    w.wcs.crpix = [(n + 1) / 2, (n + 1) / 2]
    w.wcs.cdelt = [-pix_arcsec / 3600, pix_arcsec / 3600]        # north up, east left
    return w, (n, n)

def to_grid(sci, var, frame_wcs, grid_wcs, shape, order="bilinear"):
    a, foot = reproject_interp((sci, frame_wcs), grid_wcs, shape_out=shape, order=order)
    v, _ = reproject_interp((var, frame_wcs), grid_wcs, shape_out=shape, order="nearest-neighbor")
    a[foot == 0] = np.nan
    return a, v
# Surface brightness (MJy/sr) is intensive, so interpolation conserves it with no flux rescaling.
# frame_wcs = WCS(IMAGE header) picks up RA---TAN-SIP. The 180° rotation between PA 0/180 visits is
# handled automatically. Reproject each frame's λ map (CWAVE slice) the same way, with nearest-neighbour.

def significance(img, var, sky):
    """img/√var, rescaled so that sky pixels have unit robust σ. Resampling correlates noise, and a
    nearest-neighbour variance map is only approximate. Without this step, '5σ' is not 5σ."""
    s = img / np.sqrt(var)
    ss = s[sky & np.isfinite(s)]
    k = 1.4826 * np.median(np.abs(ss - np.median(ss))) if ss.size > 50 else 1.0
    return s / k, k          # report k as a QA number; ≈1 at native sampling
```
- **Display pixel scale:** 6.15″ (native) for honesty, or 3.0″ (2× upsampled) for smoother blinks. `reproject_exact` (drizzle-like) gives sharper stacks from the ≈20 naturally dithered frames, if time allows.
- **Large FOVs:** at 30–60′, use 12–25″ pixels (server-side binning), or the histogram reprojection IRSA uses (nearest-bin accumulate, no correlated noise, Supplement §3.4.6).
- **Measurement and detection:** do all measurement (photometry, astrometry) on **native** frames, and run detection on native-scale grids. Never measure on upsampled ones.

### 4.5 Transient rejection and stacking (per time-bin × band)
```python
# spherex/stack.py
import warnings
import numpy as np

def frame_weight(var, sky):
    """One weight per frame, from its sky variance. Per-pixel inverse-variance weights include the
    source's own shot noise, so bright pixels would down-weight themselves and bias stacks low."""
    v = var[sky & (var > 0)]
    return 1.0 / np.median(v) if v.size else 0.0

def reject_transients(frames, var, k=5.0):
    """Flag single-frame outliers on pixels whose stack median looks like empty sky.
    Pixels on real sources (median clearly positive) are never clipped. That keeps real
    channel-to-channel spectral changes: a T dwarf varies ×3–5 across band 4, often with one bright end,
    which a symmetric clip would cut. Asteroids, residual cosmic rays and glints on empty sky are caught.
    The flagged pixels feed the asteroid finder (P2-5)."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)          # all-NaN columns are fine
        med = np.nanmedian(frames, axis=0)
        n = np.isfinite(frames).sum(axis=0)
        sig_med = 1.2533 * np.sqrt(np.nanmedian(var, axis=0) / np.maximum(n, 1))
        skylike = np.abs(med) < 3.0 * sig_med
        return np.isfinite(frames) & skylike & (np.abs(frames - med) > k * np.sqrt(var))

def weighted_stack(frames, var, w_frame, rej):
    """frames/var: (n, ny, nx) on the common grid, NaN = masked; w_frame: (n,) from frame_weight."""
    ok = np.isfinite(frames) & (var > 0) & ~rej
    w = np.where(ok, np.asarray(w_frame, float)[:, None, None], 0.0)
    sw = w.sum(axis=0)
    with np.errstate(invalid="ignore", divide="ignore"):
        mean = (w * np.where(ok, frames, 0.0)).sum(axis=0) / sw
        v = (w ** 2 * np.where(ok, var, 0.0)).sum(axis=0) / sw ** 2
    return mean, v, ok.sum(axis=0)          # NaN where nothing contributed
```
**Outputs per (bin, band):**
- `mean` (MJy/sr), `var`, `nhits`
- `flag_or`: the bitwise OR of propagated informational flags (`OVERFLOW`, `SOURCE`, `OUTLIER`, `STREAK`)
- **`rej`, the rejected-pixel cube.** Positive connected components of 2 or more pixels in `rej` are per-exposure transients. After artifact vetting, those are the **asteroid candidates** feeding P2-5.

### 4.6 Spectral cubes and wavelength-matched differences
Each visit's frames of one band are binned **per pixel** by the wavelength each pixel actually saw. This cube is the core intermediate product, with three uses:
- the λ-matched difference (P1-1)
- the λ-scrubber and click-any-pixel spectra (P2-2)
- a check on what each broadband stack really contains

Matching must be per pixel because consecutive visits are rotated 180°: the LVF gradient runs in opposite sky directions, so a match made at the target drifts by ≈2 channels per 12′ of offset (understanding.md §5.3).
```python
# spherex/cube.py
import numpy as np
from scipy.optimize import linear_sum_assignment
from .constants import BANDS                      # detector: (λmin µm, λmax µm, R)

NCH = 17
CH_LN = {d: np.log(hi / lo) / NCH for d, (lo, hi, _) in BANDS.items()}   # one channel, in ln λ

def spectral_cube(frames, var, lam, w_frame, band, rej=None, oversample=1):
    """Bin one (time-bin, band) frame set by the wavelength each pixel saw.
    frames/var/lam: (n, ny, nx) on the common grid (lam = reprojected CWAVE, µm).
    Returns cube, cube_var, cube_lam: (17·oversample, ny, nx). cube_lam is the mean λ each bin actually
    sampled at each pixel. NaN where no frame sampled that bin at that pixel."""
    lo, hi, _ = BANDS[band]
    nb = NCH * oversample
    ok = np.isfinite(frames) & np.isfinite(lam) & (var > 0)
    if rej is not None:
        ok &= ~rej
    idx = np.floor(nb * np.log(np.where(ok, lam, lo) / lo) / np.log(hi / lo)).astype(int).clip(0, nb - 1)
    w = np.where(ok, np.asarray(w_frame, float)[:, None, None], 0.0)
    f, v, l = np.where(ok, frames, 0.0), np.where(ok, var, 0.0), np.where(ok, lam, 0.0)
    cube = np.full((nb,) + frames.shape[1:], np.nan)
    cvar, clam = np.full_like(cube, np.nan), np.full_like(cube, np.nan)
    for k in range(nb):
        wk = np.where(idx == k, w, 0.0)
        sw = wk.sum(axis=0)
        with np.errstate(invalid="ignore", divide="ignore"):
            cube[k] = (wk * f).sum(axis=0) / sw
            cvar[k] = (wk ** 2 * v).sum(axis=0) / sw ** 2
            clam[k] = (wk * l).sum(axis=0) / sw
    return cube, cvar, clam

def at_wavelengths(lam_t, cube, cvar, clam, band, max_gap_ch=0.75):
    """Evaluate a cube's per-pixel spectrum at wavelengths lam_t (nb, ny, nx): linear in ln λ between
    neighbouring bins. Where a neighbour is missing, fall back to the same bin if it lies within
    max_gap_ch channels. This removes the half-channel S1/S2 ↔ S3/S4 offset, which no pairing can."""
    nb = len(cube)
    lt, ls = np.log(lam_t), np.log(clam)
    k = np.broadcast_to(np.arange(nb)[:, None, None], cube.shape)
    with np.errstate(invalid="ignore"):
        j0 = np.where(lt >= ls, k, k - 1).clip(0, nb - 1)
    j1 = (j0 + 1).clip(0, nb - 1)
    take = lambda a, j: np.take_along_axis(a, j, axis=0)
    f0, f1, l0, l1 = take(cube, j0), take(cube, j1), take(ls, j0), take(ls, j1)
    with np.errstate(invalid="ignore", divide="ignore"):
        t = (lt - l0) / (l1 - l0)
        good = np.isfinite(f0) & np.isfinite(f1) & (j1 > j0) & (t >= 0) & (t <= 1)
        f = np.where(good, f0 * (1 - t) + f1 * t, np.nan)
        v = np.where(good, take(cvar, j0) * (1 - t) ** 2 + take(cvar, j1) * t ** 2, np.nan)
        near = ~good & np.isfinite(cube) & (np.abs(lt - ls) < max_gap_ch * CH_LN[band])
    return np.where(near, cube, f), np.where(near, cvar, v)

def matched_difference(a, b, band, sky):
    """Visit A − visit B, matched in wavelength pixel by pixel. a, b: (cube, var, lam) from spectral_cube
    (same band, same grid). B's spectrum is interpolated to the wavelengths A sampled, so both the PA-flip
    gradient reversal and the half-channel survey offset drop out. Bin weights come from sky pixels, so
    bright sources don't down-weight themselves."""
    ca, va, la = a
    fb, vb = at_wavelengths(la, *b, band)
    ok = np.isfinite(ca) & np.isfinite(fb) & (va > 0) & (vb > 0)
    wk = np.zeros(len(ca))
    for k in range(len(ca)):
        s = ok[k] & sky
        if s.any():
            wk[k] = 1.0 / np.median(va[k][s] + vb[k][s])
    w = np.where(ok, wk[:, None, None], 0.0)
    sw = w.sum(axis=0)
    with np.errstate(invalid="ignore", divide="ignore"):
        d = (w * np.where(ok, ca - fb, 0.0)).sum(axis=0) / sw
        v = (w ** 2 * np.where(ok, va + vb, 0.0)).sum(axis=0) / sw ** 2
    return d, v               # display significance(d, v, sky) (§4.4) with a diverging map

def pair_frames(lam_a, lam_b, band, tol_channels=0.75):
    """Fast path for target-only spectra: pair frames of two visits by λ *at the target*. 0.75 channel
    lets the half-channel S3/S4 offset pair, but the 0.5-channel mismatch then stays in the difference."""
    cost = np.abs(np.log(lam_a)[:, None] - np.log(lam_b)[None, :])
    ia, ib = linear_sum_assignment(cost)
    ok = cost[ia, ib] < tol_channels * CH_LN[band]
    return ia[ok], ib[ok]
```
- **Sampling:** with ≈20 frames per band per visit, each pixel has ≈1 sample per bin. 12–17 bins overlap between two visits, so the matched difference has the S/N of ≈12–17 frame pairs. Linear interpolation in ln λ across one channel errs by only ≈(α·Δln λ)²/8 for a power law, ≈0.1% even for a spectrum that changes ×4 across the band.
- **Measured on synthetic data:** we used a steep-spectrum star (×4 across band 4, peak S/N 23–90 per frame), the LVF gradient reversed in visit B and the half-channel survey offset. Peak |residual| in a 5×5 box (noise alone gives ≈2σ):

  | Method | Residual at the centre | Residual 1.8–3.7′ off-centre |
  |---|---|---|
  | Pairing frames at the target (the old method) | 6σ | 10–13σ on one side |
  | Per-pixel bins without interpolation | 3.3σ | — |
  | Per-pixel bins with interpolation | ≤ 2.6σ | ≤ 2.6σ, everywhere from −3.7′ to +3.7′ |

  The test runs every code block in this section as written. It also confirms a 1.7 px mover still leaves a ≫10σ dipole.
- **Resampling on real frames (✅ 11-06, decision 0003, numbers proposed).** The table above was measured on frames generated on the grid. Through real reprojection the undersampled PSF (FWHM ≈ 1.46 px) changes shape with sub-pixel phase, and with one frame per bin that left 16–30σ static residuals at peak S/N ≈ 90 per frame. The difference path therefore resamples with NaN-safe bicubic, homogenises all frames to 1.5 × the largest `PSF_FWHM`, adds (0.02·F)² + (0.05 px·|∇F|)² per visit to the bin variance, and brackets B's spectrum with the nearest *sampled* bins (identical to the code above wherever it returns a value). Dipole shifts come from fitting B's own matched image onto A (`cube.fit_shift`), because bright targets' cores are masked (Barnard band 6: TRANSIENT + SUR_ERROR in 52 of 59 frames). Real Barnard V1→V3: 1.62 px at 354° (`validation/G4a-real/`).
- **Use `pair_frames` only** for target-only work (spectra, the target's own pixels), and only when both visits share channel centres (same survey family: S1↔S2 or S3↔S4) or the target is faint.
- **Display:** use a diverging colormap centred on 0, clipped at ±5σ (after `significance`). Annotate automatically:
  - **dipole:** fit a two-PSF model (+f at r₂, −f at r₁). Label it "moved ≈X″" when |r₂ − r₁| > 0.3 px and its direction agrees with `pos(t)`.
  - **monopole:** labelled "brightened" or "faded"
- **PSF matching** is mostly unnecessary, because matched λ means a matched diffraction PSF. The PSF is not rotationally symmetric, though, so PA 0°/180° pairs of bright stars can leave faint rotated residuals. If they distract, convolve the sharper visit with a Gaussian of σ² = σ_b² − σ_a², using `PSF_FWHM` from the headers.

### 4.7 Astrometry: centroids, re-registration, PM and parallax
**(a) ePSF model and per-frame fit on native pixels**
```python
# spherex/epsf.py
import numpy as np
from scipy.ndimage import map_coordinates
from scipy.optimize import least_squares

class EPSF:
    """QR3 ePSF calibration table: one row per zone; columns XCENTER, YCENTER (parent px), CWAVE,
    CBAND, EPSF (33×33 float64, oversampled ×5) ✅. Recommended for QR2 images too."""
    def __init__(self, table):
        self.xc = np.asarray(table["XCENTER"], float); self.yc = np.asarray(table["YCENTER"], float)
        self.os = 5
        psf = np.asarray(table["EPSF"], float)
        # Normalise so the ePSF sampled at native-pixel spacing sums to 1 at any sub-pixel phase
        # (the oversampled array then sums to os²). Fitted amplitudes become total fluxes.
        self.psf = psf / psf.sum(axis=(1, 2), keepdims=True) * self.os ** 2
        self.c = (psf.shape[-1] - 1) / 2

    def zone(self, xp, yp):           # parent-detector 0-based coordinates
        return int(np.argmin((self.xc - xp) ** 2 + (self.yc - yp) ** 2))

    def stamp(self, iz, dx, dy, half=3):
        """ePSF sampled at native-pixel centres for a source offset (dx,dy) from the stamp centre.
        An ePSF already includes the pixel response, so point sampling is correct. Not renormalised:
        the stamp sums to the encircled fraction inside it, so the fitted flux stays total."""
        g = np.arange(-half, half + 1, dtype=float)
        yy, xx = np.meshgrid(g, g, indexing="ij")
        # The table spans only ±3.3 px, so the stamp's outer pixels can sample past its edge.
        # "grid-constant" tapers smoothly to 0 there. Plain "constant" jumps to 0 at the edge, which
        # makes the model discontinuous in position: ✅ 11-06, 46% of bright-star fits stalled.
        return map_coordinates(self.psf[iz], [self.c + self.os * (yy - dy), self.c + self.os * (xx - dx)],
                               order=3, mode="grid-constant", cval=0.0)

def fit_star(img, var, bad, epsf, iz, x0, y0, half=3, fixed_xy=False, max_shift=1.5):
    """Returns (params, errors, reduced χ²), or None if the stamp is off the image or too masked.
    params = (x, y, flux, bkg), or (flux, bkg) with fixed_xy; flux in MJy/sr·pix (total)."""
    ix, iy = int(round(x0)), int(round(y0))
    ny, nx = img.shape
    if ix - half < 0 or iy - half < 0 or ix + half >= nx or iy + half >= ny:
        return None
    sl = np.s_[iy - half:iy + half + 1, ix - half:ix + half + 1]
    d, v = img[sl], var[sl]; m = bad[sl] | ~np.isfinite(d) | ~(v > 0)
    npar = 2 if fixed_xy else 4
    if (~m).sum() < npar + 3:
        return None
    def model(p):
        x, y, f, b = (x0, y0, *p) if fixed_xy else p
        return f * epsf.stamp(iz, x - ix, y - iy, half) + b
    def resid(p):
        return ((d - model(p)) / np.sqrt(np.where(m, 1, v)))[~m]
    f0 = float(np.nansum(np.where(m, 0, d)))
    if fixed_xy:
        p0, lb, ub = [f0, 0.0], [-np.inf, -np.inf], [np.inf, np.inf]
    else:
        p0 = [x0, y0, f0, 0.0]
        lb = [x0 - max_shift, y0 - max_shift, -np.inf, -np.inf]
        ub = [x0 + max_shift, y0 + max_shift, np.inf, np.inf]
    r = least_squares(resid, p0, bounds=(lb, ub))
    rchi2 = float((r.fun ** 2).sum() / max(1, r.fun.size - npar))
    cov = np.linalg.pinv(r.jac.T @ r.jac) * max(1.0, rchi2)
    return r.x, np.sqrt(np.diag(cov)), rchi2
```
- **Saturated targets:** OVERFLOW pixels that are not NaN still carry ramp-fitted values. NaN cores are excluded automatically, so the fit uses the **wings**. For Barnard and R Dra, mark these results as `wing_fit=True`. The tabulated ePSF only reaches ±3.3 px, so a core larger than ≈2 px leaves too few pixels for a meaningful fit. Then fall back to §4.9's annulus ratios.
- **Day 1:** confirm the ePSF's orientation matches `IMAGE` pixels. Fit 5 isolated stars and check that the residuals are symmetric.

**(b) Differential re-registration (removes per-frame WCS systematics).**
1. Query Gaia DR3 (IRSA `gaia_dr3_source`, ✅ 11-06) once, over a **registration region of ≥ 12′**, independent of the display FOV. A 6′ view rarely holds enough good stars.
2. For each frame, propagate the stars from J2016.0 to `MJD-AVG`.
3. Fit the isolated, unsaturated ones with `fit_star`.
4. Take the median (ΔRA·cosδ, ΔDec) residual and apply it to the target's position in that frame.

This typically turns ≈0.3–0.5″ absolute frame errors into ≈0.1″ relative ones **≈**.

**(c) Proper motion and parallax fit.** SPHEREx's quadrature geometry puts each visit at a parallax extreme (understanding.md §6.1).
```python
# spherex/astrometry.py
import numpy as np
from astropy.coordinates import get_body_barycentric
from astropy.time import Time
import astropy.units as u
AU_KM = 1.495978707e8

def parallax_factors(mjd, ra_deg, dec_deg, sc_geo_km=None):
    """Observer barycentric position (AU, ICRS axes) → factors (Pα*, Pδ) such that
    Δα* = ϖ·Pα*, Δδ = ϖ·Pδ. Adding the spacecraft geocentric offset matters only for Solar System
    objects (≤ 7000 km ≈ 4.7e-5 AU). Verify the frame of X_SC/Y_SC/Z_SC ('GEOCENTER') before relying
    on it, or use Horizons with SPHEREx as the observer (§4.11)."""
    e = get_body_barycentric("earth", Time(mjd, format="mjd", scale="utc"))
    X, Y, Z = (e.x.to_value(u.au), e.y.to_value(u.au), e.z.to_value(u.au))
    if sc_geo_km is not None:
        X, Y, Z = X + sc_geo_km[0] / AU_KM, Y + sc_geo_km[1] / AU_KM, Z + sc_geo_km[2] / AU_KM
    a, d = np.radians(ra_deg), np.radians(dec_deg)
    return X * np.sin(a) - Y * np.cos(a), X * np.cos(a) * np.sin(d) + Y * np.sin(a) * np.sin(d) - Z * np.cos(d)

def fit_pm(t_yr, xi, eta, s_xi, s_eta, p_a, p_d, t0, plx_fixed=None):
    """xi, eta: tangent-plane offsets (arcsec) of per-frame positions from a reference point.
    Unknowns: xi0, eta0, mu_a*, mu_d [arcsec/yr], parallax [arcsec] (unless fixed)."""
    dt = np.asarray(t_yr) - t0
    A = np.zeros((2 * len(dt), 5)); b = np.r_[xi, eta]; w = np.r_[1 / np.square(s_xi), 1 / np.square(s_eta)]
    A[:len(dt), 0] = 1; A[:len(dt), 2] = dt; A[:len(dt), 4] = p_a
    A[len(dt):, 1] = 1; A[len(dt):, 3] = dt; A[len(dt):, 4] = p_d
    if plx_fixed is not None:
        b = b - A[:, 4] * plx_fixed; A = A[:, :4]
    N = A.T @ (A * w[:, None]); p = np.linalg.solve(N, A.T @ (b * w)); C = np.linalg.inv(N)
    chi2 = float((((A @ p) - b) ** 2 * w).sum())
    return p, np.sqrt(np.diag(C)), chi2
```
- **Fix the parallax for known targets** (`plx_fixed` = catalogue value) when measuring PM, and fit it freely only as a stretch goal. With 3 visits, the free parallax has almost no redundancy in the longitude direction.
- **Scale the errors** by √(χ²/dof) when χ²/dof > 1. Per-frame errors within a visit share systematics.
- **WISE 0855:** its two full visits are 0.78 px apart *including* 0.9″ of parallax in the same direction (✅ 11-06). A PM-only fit would overestimate μ by ≈20%.

**UI:** an "astrometry card" shows:
- the fitted μ (″/yr) and position angle, beside Gaia/SIMBAD values
- the χ² of a stationary model versus the moving model; the motion significance is Δχ²
- a small (ξ, η) track plot with per-visit error ellipses, showing the parallax zig-zag when present (east–west for Barnard, perpendicular to its northward PM)

### 4.8 Photometry and spectra on the fly
```python
# spherex/photometry.py
import numpy as np
SR_PER_ARCSEC2 = (np.pi / 648000.0) ** 2                  # 2.3504e-11 sr

def to_uJy(f_pix_sum_mjysr, omega_arcsec2):
    """ePSF amplitude (MJy/sr summed over pixels) × pixel solid angle → µJy.
    1 MJy/sr over 1 arcsec² = 23.504 µJy."""
    return f_pix_sum_mjysr * omega_arcsec2 * SR_PER_ARCSEC2 * 1e12

def ab_mag(uJy):
    return 23.9 - 2.5 * np.log10(uJy)

def spectrum_point(frame, epsf, ra, dec, omega_arcsec2):
    """Forced photometry at a known (propagated) position in one native frame."""
    x, y = frame.wcs.world_to_pixel_values(ra, dec)
    xp, yp = frame.origin[0] + x, frame.origin[1] + y
    iz = epsf[frame.detector].zone(xp, yp)
    res = fit_star(frame.sci, frame.var, frame.bad_phot, epsf[frame.detector], iz, x, y, fixed_xy=True)
    if res is None:
        return None
    (f, _), (ef, _), rchi2 = res
    iy, ix = int(round(float(y))), int(round(float(x)))
    F, eF = to_uJy(f, omega_arcsec2), to_uJy(ef, omega_arcsec2)
    eF = np.hypot(eF, 0.03 * abs(F))                       # IRSA's 3% irreducible-scatter floor
    return dict(lam=frame.lam[iy, ix], dlam=frame.dlam[iy, ix], flux_uJy=F, err_uJy=eF, mjd=frame.mjd,
                detector=frame.detector, obsid=frame.obsid, rchi2=rchi2,
                flags_near=frame.flags_near(x, y, r=2.5))
```
- **Pixel solid angle:** use the solid-angle pixel map at the parent pixel, or `OMEGA_MEDIAN` (≈37.94 arcsec²) as a quick fallback.
- **Movers:** in track mode the (ra, dec) passed in is `pos(t)` at that frame's MJD.
- **Output and UI:**
  - All about 100–120 points per visit, coloured by visit.
  - Optional channel-binned medians (17 bins per band, from the channel map).
  - Feature markers (CH₄ 3.3, H₂O 2.7/3.05, CO₂ 4.26, CO 4.67, Paα 1.875, Brα 4.05, He 1.083 contamination).
  - Template overlays (SpeX Prism Library for M/L/T, a Y-dwarf model, Pickles for stars), each scaled by least squares.
- **Indices:**
  - `methane = F(3.25–3.40 µm) / F(3.95–4.20 µm)` in F_ν. A Rayleigh–Jeans star gives ≈1.5; T and Y dwarfs give ≪ 1. Report it **relative to the median of field stars** in the same view, because the two points come from different detectors.
  - `W1W2_syn`: a synthetic WISE colour from integrating channel fluxes over the W1 and W2 response curves. SPHEREx stops at 5.0 µm, while W2 extends to ≈5.3 µm, so label the result approximate.
- **Validation:** cross-check one source against IRSA's **Spectrophotometry Tool**. Agreement within ≈5–10% shows judges the results are trustworthy.

### 4.9 Light curves (variables: RW Aur, R Dra)
**Spectrally normalized light curve.** Different bins sample different channels, so raw fluxes mix spectrum and time. Divide that out:
1. Build a reference spectrum S_ref(λ): the median over all epochs, smoothed per band.
2. For each point i, compute rᵢ = Fᵢ / S_ref(λᵢ).
3. Light curve per band and bin = inverse-variance mean of r. This is dimensionless relative flux.
4. Periodogram: `astropy.timeseries.LombScargle` on bins, with false-alarm probability. Show a phase-folded plot at the best period.

Then plot spectra against phase (R Dra: water and CO band depths change).

**Saturated stars (R Dra, K_AB ≈ 4.1).** The core is NaN in most bands, and the tabulated ePSF only spans ±3.3 px. Use **same-channel annulus ratios**, which need no PSF model:
```python
def annulus_flux(img, bad, x, y, r_in=3.0, r_out=6.0):
    """Mean surface brightness in a fixed annulus × its area. Compare it only between frames where the
    star fell in the same channel and detector region, so the PSF shape cancels."""
    yy, xx = np.indices(img.shape)
    r = np.hypot(xx - x, yy - y)
    ring = (r >= r_in) & (r < r_out) & ~bad & np.isfinite(img)
    if ring.sum() < 10:
        return np.nan
    return float(np.mean(img[ring]) * np.pi * (r_out ** 2 - r_in ** 2))
```
Group R Dra's ≈2,480 frames by (detector, channel). Normalise each group by its own median, then merge the groups into one relative light curve per band. Label it "relative, qualitative". **Validate** against AAVSO (VSX period: R Dra ≈ 245 d).

### 4.10 Mover finder (P2-4)
1. **Detect:**
   - Run photutils `detect_sources` on each (bin, band) significance image (§4.4, renormalised) at **native** 6.15″ sampling. Use a threshold of 5σ and npixels ≥ 3.
   - Also detect on the **red-sum** image (band 5 + 6 visit stacks), which catches cold brown dwarfs.
2. **Link across bins:** use KD-trees per bin and accept links within `r = max(1.5 px, μ_max·Δt + 2ϖ_max)`, where μ_max is user-set (default 10″/yr). Fit each chain with `fit_pm`.
3. **Score:** `S = Δχ²(stationary − moving)`. Flag a candidate when S > 25 and |μ| > 3σ_μ and the shift exceeds 0.3 px.
4. **Identify:**
   - Cross-match with Gaia DR3 (propagated to each bin epoch, parallax included), CatWISE2020 (has PMs, in IRSA), and SIMBAD. Label matches "known (Gaia ID…)".
   - Unmatched candidates with a red colour (red-sum detected, blue bands empty) are flagged **"cold & new? 🔥"**.
5. **Vet automatically.** Reject a candidate when, in any epoch, it:
   - sits inside a `GHOST`/`CROSSTALK`/`PERSIST`/`BLOOM` footprint,
   - sits 32 rows or 64·k columns from a bright star in detector coordinates, or
   - has a PSF-fit reduced χ² that is too high.
6. **Orphans** (detected in exactly one bin) go to the asteroid/Planet X queues (§4.11, §4.12).

### 4.11 Solar System layer: asteroids, comets, Pluto
**Known asteroids (SkyBoT).** Query IMCCE SkyBoT once per frame time, or use `astroquery.imcce.Skybot`:
```
https://ssp.imcce.fr/webservices/skybot/api/conesearch.php?-ep=<JD>&-ra=<deg>&-dec=<deg>&-rd=<deg>
    &-mime=text&-output=basic&-loc=500&-filter=0&-objFilter=111&-from=ParallaX
```
- ✅ 11-06: the observer parameter is **`-loc`** (500 = geocentre). `-observer` is silently ignored.
- **Output:** each row has Mv, rates (dRA, dDEC in ″/h) and distance.
- **Geocentric → SPHEREx:** shift by the topocentric parallax, using `parallax_factors(..., sc_geo_km=(X_SC, Y_SC, Z_SC))` with the Earth term removed and ϖ = 206265″ / Δ[AU]. For a main-belt asteroid at Δ ≈ 2 AU the shift is ≈5″ ≈ 0.8 px.
- **Brightness:** only V ≲ 18.5 shows in a single frame **≈**. ✅ 11-06: a sample 15′ field near RW Aur held only V = 22.6–24.1 objects. Filter on Mv, and pick demo frames where SkyBoT predicts a bright one.
- **Display:** label exposure-level orphans that match within 15″. Unmatched orphans that survive vetting are **"unknown mover?"** candidates. Never call them discoveries; link to the MPC reporting guidance.

**Named bodies (Horizons, P2-10).** ✅ 11-06: JPL Horizons knows SPHEREx as body **−163182**, from TLEs. It returns ephemerides *as seen from SPHEREx*, which makes the topocentric correction unnecessary:
```python
# spherex/ephem.py
import httpx

HORIZONS = "https://ssd.jpl.nasa.gov/api/horizons.api"
SPHEREX_CENTER = "500@-163182"        # ✅ 11-06: Pluto from here differs from geocentric by ≈0.3″

async def sso_radec(client: httpx.AsyncClient, command: str, jd_utc: list[float],
                    center: str = SPHEREX_CENTER) -> list[tuple[float, float]]:
    """Astrometric RA/Dec (deg, ICRF) of a Solar System body at each JD, as seen from `center`.
    command: '999' (Pluto), '136472;' (Makemake; the semicolon means small body). Chunk long time lists."""
    params = {"format": "json", "COMMAND": f"'{command}'", "OBJ_DATA": "'NO'", "MAKE_EPHEM": "'YES'",
              "EPHEM_TYPE": "'OBSERVER'", "CENTER": f"'{center}'", "QUANTITIES": "'1'",
              "ANG_FORMAT": "'DEG'", "TLIST": ",".join(f"'{t:.6f}'" for t in jd_utc)}
    r = await client.get(HORIZONS, params=params, timeout=60)
    r.raise_for_status()
    rows = r.json()["result"].split("$$SOE")[1].split("$$EOE")[0].strip().splitlines()
    return [tuple(float(v) for v in row.split()[-2:]) for row in rows]
```
- **Track mode** with `pos(t)` = Horizons. Coverage must be queried **per visit** at the body's position, because a Solar System body moves degrees between visits. Each visit's frames are then centred on the body.
- **Pluto**, the original Planet X, is the headline: V ≈ 14.4–14.6 in 2025–26 at ≈34–36 AU (✅ 11-06), which is high S/N in single frames. Its spectrum shows CH₄ ice at 1.7, 2.3 and 3.3 µm. Within a visit, Pluto moves arcminutes, so only track mode works.
- **Comets:** the same path shows comets such as 3I/ATLAS, which SPHEREx observed in Aug 2025. Look up the Horizons record ID first.
- **Day 1:** compare Horizons' SPHEREx position with the header `X_SC/Y_SC/Z_SC` (§11.0).

### 4.12 Planet X mode (P2-6, ambitious, but it is the challenge's namesake)
Geometry (understanding.md §6.1): at quadrature a distant body is stationary in ecliptic **longitude** within a visit. It drifts in **latitude** at ϖ·sin β per radian of Earth's orbit, e.g. 5.5 px over 14 days at 500 AU and β = 20°. Between visits it jumps ≈2ϖ in longitude. Whole-visit stacks smear it, so work with **per-day stacks** (one target group each).
```python
def distant_body_offset(mjd, mjd0, ra, dec, dist_au):
    """Apparent offset (Δα*, Δδ in arcsec) at mjd relative to mjd0 for a body at dist_au whose direction
    is fixed: parallax only. Orbital motion (≤ 0.7″/day beyond 300 AU) is a bounded nuisance term.
    First order in ϖ: errors of a few arcsec at 40 AU, negligible beyond 100 AU."""
    plx = 206264.806 / dist_au
    pa1, pd1 = parallax_factors(mjd, ra, dec)
    pa0, pd0 = parallax_factors(mjd0, ra, dec)
    return plx * (pa1 - pa0), plx * (pd1 - pd0)
```
For FOV ≥ 30′ and a distance grid d ∈ {50, 100, 150, 200, 300, 500, 800, 1200} AU:
1. **Per-day orphans:** sources in a per-day stack (red-sum and broadband) with no counterpart at the same spot in other days and visits.
2. **Within-visit linking:** chain per-day orphans whose day-to-day offsets match `distant_body_offset` for some d, plus a bounded orbital term (|v_orb| ≤ √(GM☉/d), projected).
3. **Cross-visit linking:** connect chains whose ≈2ϖ longitude jump agrees with the *same* d. Require that their spectra agree (flux ratios within errors).
4. **Rank and display** as **"parallax-linked orphan candidates"**, with a "why" panel showing the predicted and observed offsets.

**Shift-and-stack variant:** for each d, shift each per-day stack by the predicted offset and coadd, so faint consistent movers rise above the noise. This is the digital tracking used in modern Planet Nine searches. Be honest in the UI: SPHEREx depth limits this to bright hypothetical planets.

**Validation set (do this before showing the mode):**
- **Makemake** (V ≈ 17, ≈52 AU), **Haumea** (V ≈ 17.3, ≈50 AU) and **Eris** (V ≈ 18.7, ≈96 AU). Their parallactic drift should exceed their orbital motion by ≈3× **≈**, so the distance grid should place them within ≈±30%. Get truth positions from Horizons (`sso_radec`).
- **Pluto** is the easy visual check. Its orbital motion (≈16″/day) is comparable to its latitude drift, so validate its *linking* against Horizons rather than its fitted distance.

### 4.13 The 25-year blink (P2-1)
| Epoch | Source | Access (server-side), ✅ 11-06 | Band to pair with |
|---|---|---|---|
| 1997–2001, per target: Barnard **2000.41**, ε Ind B **1999.85**, RW Aur **1999.90** (`fp_psc.jdate`) | 2MASS Atlas images (J/H/Ks) | IBE search `https://irsa.ipac.caltech.edu/ibe/search/twomass/allsky/allsky?POS=ra,dec` → data URL `…/ibe/data/twomass/allsky/allsky/{ordate}{hemisphere}/s{scanno:03d}/image/{fname}?center=…&size=…` (file prefix `j`/`h`/`k`) | SPHEREx band 3 (≈2.2 µm channels) |
| 2010–2011 | AllWISE Atlas coadds (W1/W2) | SIA2 `COLLECTION=wise_allwise`, then an IBE cutout of the `access_url` | Bands 4 (W1) and 6 (W2) |
| 2014–2024 | NEOWISE single exposures | SIA2 `COLLECTION=neowiser`; stack per 6-month epoch. unWISE time-domain coadds (unwise.me) are an alternative, not hosted at IRSA. | Band 6 |
| 2025–2027 | SPHEREx visit stacks | ours | — |

**Normalisation:**
- Reproject all epochs to the same grid (6.15″, or the coarser of the two).
- Normalize each to its own sky σ, and apply a common asinh stretch.
- Label clearly: "different telescopes, positions only".
- ✅ 11-07 (D, `access/blink25.py`, `scripts/blink25_acquire.py`, `validation/G5.25yr-data/`): the 2MASS match
  needs position *and* Ks (a K = 15.8 star lies 3.6″ from WISE 0855's J2000 position). The 2MASS image search runs
  at the archival, mid and 2026 positions, because Barnard's single midpoint image missed the 2000 position. AllWISE
  and NEOWISE SIA2 rows are filtered to `dataproduct_subtype = science` (`-int-` images; the rest are artefact
  tables). Catalogue-based jumps: Barnard 4.54′, ε Ind B 2.09′, WISE 0855 2.19′.
- ✅ 11-08 (server side, `spherex/blink25.py`, `GET /views/{key}/blink25`): epochs = 2MASS Ks (mosaic of ≤ 3 Atlas
  images), AllWISE W2, NEOWISE W2 thinned to ≤ 6 epochs (≈ one per two years, ≤ 4 exposures each), and the view's
  latest full band-6 visit; each image is normalised on its own sky before images of one epoch are median-combined.
  **Measured on the images** (`validation/G5.25yr-jumps/`, L3): Barnard 2MASS → SPHEREx V4 (2026.63) 4.540′, ε Ind B
  2.085′ (→ 2026.73), WISE 0855 AllWISE → SPHEREx 2.149′ (→ 2026.32); each within 1″ of pos(t).
- **Auto-size the FOV** to ≥ 1.5 × the expected jump. A 2MASS Atlas image is 8.5′ × 17′, so a large cutout may clip at an image edge. IBE returns every overlapping image; mosaic two if needed.

Expected jumps (✅ 11-06):
- Barnard: **≈4.55′** (2MASS 2000-05-28 → Aug 2026)
- ε Ind B: **≈2.1′**
- WISE 0855: **≈2.2′** (AllWISE → 2026). It is undetected by 2MASS.

**"Lite" fallback:** if the server-side version slips, blink Aladin Lite HiPS layers (`CDS/P/2MASS/color` ↔ `CDS/P/unWISE/color-W2-W1W2-W1`) against the SPHEREx stack drawn as an overlay.

---

## 5. API design

### 5.1 Endpoints (`/api/v1`)
| Method | Path | Purpose |
|---|---|---|
| GET | `/resolve?q=WISE 0855` | Name, alias, coordinates or `sso:<name>` → `{kind: star\|sso\|coords, ra, dec, epoch, pm, plx, rv, otype, spt, astrometry_source, propagated_now}` plus epoch-mismatch hints |
| GET | `/coverage?ra=&dec=&fov=` | Full and partial visits, frames per band, releases, freshness. One cached SIA2 call. |
| POST | `/views` | Body: view params (§5.3), optional `pin`. Returns 200 manifest (warm) or 202 `{job_id}` |
| GET | `/jobs/{id}/events` | SSE: `planned{n}`, `fetched{i,n}`, `stack_ready{bin,band}`, `diff_ready`, `done`, `warning{…}` |
| GET | `/views/{key}/manifest` | Bins (full/partial), bands, grid WCS, stretch limits, frame-list hash (`pin`), per-frame metadata, QA, warnings |
| GET | `/views/{key}/stack/{bin}/{band}.f16` | Binary float16 LE, row-major; −65504 = no data. Also `.f32` (NaN = no data), `.var.f32`, `.flags.u32` |
| GET | `/views/{key}/png/{bin}/{band}.png` | Server-rendered frame with the shared stretch (fallback viewer, exports) |
| GET | `/views/{key}/cube/{bin}/{band}.f16` | Spectral cube (17 × ny × nx) for the λ-scrubber |
| GET | `/views/{key}/diff?a=&b=&band=` | λ-matched significance map (float16) plus auto-annotations. ✅ 11-07 (F, proposed to P): JSON `DiffInfo` with a `url` to the `.f16` map (CONTRACTS.md) |
| GET | `/views/{key}/frames?band=&sort=time\|lambda` | Exposure-level flipbook (decimated, max 64 frames) |
| GET | `/views/{key}/frames/{band}/{digest}.f16` | ✅ 11-08: one gridded exposure of the flipbook (CONTRACTS.md) |
| GET | `/views/{key}/rgb/{bin}/{methane\|ice}.f16` | ✅ 11-08: λ-range RGB preset (3 planes) from `cube.lambda_slice` (§7) |
| GET | `/views/{key}/blink25` (+ `/blink25/{i}.f16`) | ✅ 11-08: 25-year blink epochs on one grid, each on its own sky σ (§4.13) |
| GET | `/spectrum?ra=&dec=&track=1&visits=all` | Rows: λ, Δλ, flux, err, mjd, visit, detector, flags, reduced χ² |
| GET | `/lightcurve?ra=&dec=&bin=14d&bands=&method=psf\|annulus` | Normalized LC per band plus periodogram |
| GET | `/astrometry?ra=&dec=&name=` | Per-frame positions, PM/ϖ fit, Gaia comparison |
| GET | `/sso?name=&mjd=` | Horizons positions as seen from SPHEREx at the given frame times |
| GET | `/movers?key=` | Candidate list (mover finder) |
| GET | `/overlays/{gaia\|catwise\|simbad\|sso}?ra=&dec=&r=&mjd=` | Positions propagated to the epoch (parallax included) |
| GET | `/export/{gif\|mp4\|apng\|fits\|csv}?...` | Server-rendered exports |
| GET | `/releases` | `release_state`, newest planning periods |
| POST | `/candidates` | Citizen report (§8) |

### 5.2 Binary payload
- **Display stacks:** float16 little-endian (`.f16`), uploaded straight into an R16F texture with no decoding.
  - Real values are first clipped to [−5×10⁴, 6.5×10⁴] MJy/sr. No real pixel reaches those limits; saturated cores are NaN anyway.
  - No data becomes the sentinel **−65504**, the most negative finite float16:
  ```python
  def to_f16(a):
      out = np.clip(a, -5.0e4, 6.5e4).astype("<f2")
      out[~np.isfinite(a)] = -65504.0
      return out.tobytes()
  ```
- **Science payloads** (`.f32`, FITS, CSV) keep NaN.
- **Compression:** brotli/gzip at the HTTP layer.
- **Budget:** a 6′ view at 3″ display pixels is 121² × 2 B = 29 KB per stack. 4 visits × 6 bands ≈ 0.7 MB. ✅ 11-06: on a 50 KB/s venue link even this takes ≈15 s, so the selected band comes first.

### 5.3 View parameters and the URL schema
```
/?q=Barnard's%20Star          | /?ra=08:55:10.831&dec=-07:14:42.53   (the challenge's WISE 0855 coordinate)
                               | /?q=WISE%200855  |  /?q=sso:Pluto
 &fov=6                        arcmin (2–30; up to 60 binned in P2)
 &px=3                         display pixel arcsec (native 6.15)
 &axis=visit|survey|bin:14d|exposure|multi
 &partial=0|1                  include partial visits in the blink
 &bands=6 | 1,2,3 | rgb:4,5,6 | rgb:ice | rgb:methane
 &mode=blink|diff|side|flip    flip = exposure flipbook
 &a=V1&b=V3                    visits for diff
 &stretch=asinh:8&lim=zscale   lin|sqrt|log|asinh:β ; zscale|p99.5|manual:lo,hi
 &cmap=gray|magma|cividis
 &fps=2&center=fixed|track
 &ov=gaia,simbad,sso,vec       overlays
 &flags=OVERFLOW,OUTLIER       flag planes to draw
 &mask=discovery|bright|imaging
 &rel=auto|qr3|qr2             release policy
 &pin=3fa9c27e01bd             freeze the frame list (demo and README links)
 &sel=133.7578,-7.2420         selected source (opens spectrum panel)
 &t=V2  &ui=simple|explorer|expert   (additive, ✅ 11-07 F) current bin; detail level
```
- ✅ 11-07 (F): also `mode=onion` and `ov=track,crosshair`; old spellings keep working through an alias table (`frontend/src/state/url.ts`, CONTRACTS.md).
- **Normalisation:** canonicalize params, sorting keys and rounding coordinates to 1e-5°. The canonical string plus the frame list hash into the **view key** (§2.3), so identical links share caches.
- **Embed:** `/embed?…` uses the same params with minimal chrome. Send `Content-Security-Policy: frame-ancestors *` on `/embed` only (the rest of the site stays `SAMEORIGIN`). Host pages can drive it:
```html
<iframe src="https://<host>/embed?q=WISE%200855&fov=6&bands=6&mode=blink&pin=…"
        width="480" height="520" style="border:0" loading="lazy" allowfullscreen></iframe>
<script>
  // optional: iframe.contentWindow.postMessage({type:"parallax:goto", ra:269.446, dec:4.7707}, "*")
  // The embed validates message shape and ignores anything else.
</script>
```

---

## 6. Frontend

### 6.1 Layout (desktop; on mobile, panels stack under the viewer)
```
┌──────────────────────────────────────────────────────────────────────────────────┐
│ ParallaX  [ Barnard's Star            ⏎ ]  FOV[6′▾] Release: QR2+QR3 ● fresh 2026W40│
│  ⚠ "These coordinates are WISE 0855's 2010 position — it has moved 2.2′ W [Track]"│
├───────────────────────────────────────────────┬──────────────────────────────────┤
│                                               │  ▸ Target: Barnard's Star (M4V)  │
│        BLINK VIEWER (WebGL)                   │    μ = 10.39″/yr  ϖ = 547 mas    │
│   [crosshair] [predicted track ●─●─●]         │  ▸ Astrometry card               │
│   [motion arrow] [flag overlay]               │    fitted μ vs Gaia  ✓           │
│                                               │  ▸ Spectrum (click a source)     │
│   ◀ ▶ ⏯  fps[2]  mode: Blink|Diff|Side|Flip   │    [uPlot: per-visit spectra]    │
│   band: 1 2 3 4 5 [6] RGB▾  stretch: asinh ▾  │    methane meter ▮▮▮▯▯ "cold"    │
├───────────────────────────────────────────────┤  ▸ Light curve (variables)       │
│ TIMELINE ─●──────────●──────────●──────▶      │  ▸ Frame metadata / flags / QA   │
│  V1 2025-08 S2   V2 2026-03 S1  V3 2026-08 S4 │  ▸ Sky context (Aladin Lite)     │
└───────────────────────────────────────────────┴──────────────────────────────────┘
```

### 6.2 Component tree
✅ 11-07 (F): as built in `frontend/src/components/` — flag contours are a separate canvas layer (`FlagLayer`) under the SVG `OverlayLayer`; extra routes `/embed`, `/about`, `/f14` (orientation check).

`App` → `TargetBar` (parser, resolver, epoch banner) · `Viewer` (`GLCanvas`, `PngViewer` fallback, `OverlayLayer` [SVG: crosshair, tracks, vectors, SSO labels, Gaia markers], `PlayerControls`, `Loupe`) · `Timeline` (full visits solid, partial visits hatched) · `SidePanel` (`TargetCard`, `AstrometryCard`, `SpectrumPanel`, `LightCurvePanel`, `FrameInspector`, `SkyContext`) · `ShareDialog` · `About/Credits`.

### 6.3 WebGL2 renderer (core of the blink)
```ts
// gl/renderer.ts (essentials)
export const NODATA = -65504;     // most negative finite float16; the server writes it for "no data"
const FRAG = `#version 300 es
precision highp float;
uniform sampler2D u_img;      // R16F stack (R32F also works)
uniform sampler2D u_cmap;     // 256×1 RGBA LUT
uniform float u_lo, u_hi, u_beta;
uniform int u_mode;           // 0 lin, 1 asinh, 2 log, 3 sqrt, 4 diverging (diff, symmetric)
in vec2 v_uv; out vec4 o;
void main() {
  float x = texture(u_img, v_uv).r;
  if (x < -6.0e4) { o = vec4(0.18, 0.10, 0.22, 1.0); return; }   // "no data" tint, never black
  float t;
  if (u_mode == 4) { t = clamp(0.5 + 0.5 * x / u_hi, 0.0, 1.0); }
  else {
    t = clamp((x - u_lo) / (u_hi - u_lo), 0.0, 1.0);
    if (u_mode == 1) t = asinh(t * u_beta) / asinh(u_beta);
    else if (u_mode == 2) t = log(1.0 + t * u_beta) / log(1.0 + u_beta);
    else if (u_mode == 3) t = sqrt(t);
  }
  o = texture(u_cmap, vec2(t, 0.5));
}`;

export function uploadStack(gl: WebGL2RenderingContext, w: number, h: number, half: Uint16Array) {
  const tex = gl.createTexture()!;
  gl.bindTexture(gl.TEXTURE_2D, tex);
  gl.pixelStorei(gl.UNPACK_ALIGNMENT, 1);          // odd widths: 2-byte rows aren't 4-byte aligned
  gl.texImage2D(gl.TEXTURE_2D, 0, gl.R16F, w, h, 0, gl.RED, gl.HALF_FLOAT, half);   // raw float16 bits
  // NEAREST: honest pixels, and the sentinel never blends with real values. For a smoother look,
  // ask the server for px=3 (upsampled) instead of enabling LINEAR here.
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.NEAREST);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.NEAREST);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
  return tex;
}
// Orientation: FITS row 0 is the south edge of our north-up grid, and WebGL stores the first uploaded
// row at v = 0. Draw the quad with v = 0 at the bottom of the canvas and the image is north-up, east-left,
// with no flip. Libraries that treat row 0 as the top (HTML images, canvas ImageData, SVG overlays)
// need one. Check on day 1 with an asymmetric test pattern: an "F" in the north-east corner.
```
- ✅ 11-07 (F14, golden half): north-up/east-left confirmed in WebGL and the CPU/PNG path (`validation/F14/`). Never call `WEBGL_lose_context` when disposing a renderer whose canvas may be reused: React remounts then get a dead context (blank viewer).
- **Why a sentinel, not `isnan()`:** NaN handling is not guaranteed to survive every GPU, driver and shader-compiler path, and a missed NaN renders as garbage on a judge's laptop. A finite sentinel is portable.
- **Loupe values:** the loupe decodes the single hovered float16 value on the CPU, or fetches `.f32` lazily.

**Blink player rules**
- **Shared stretch:** all frames use the **same** `u_lo`/`u_hi`, computed server-side (ZScale on the median stack). A "per-frame" toggle exists for experts but is off by default.
- **Playback:**
  - Defaults: 2 fps, ping-pong, spacebar play/pause, ←/→ to step, 1–6 for bands, D for diff, F for flipbook.
  - "Hold to compare" (hold B to flash the previous visit), onion-skin (50/50 blend), and side-by-side mode.
  - Partial visits are skipped unless `partial=1`. When included, they show a "partial: 3 frames" badge.
- **Overlays** are drawn in sky coordinates through the manifest WCS:
  - **predicted track:** `pos(t)` at each visit's mid-epoch, PM and parallax included (the zig-zag is visible on Barnard)
  - **fitted vector:** an arrow scaled ×10 with its label
  - **SSO labels** and **flag contours** (per selected plane), plus dashed outlines around model-filled cores
- **Loupe:** ×4 magnifier under the cursor, with pixel value, σ, λ range, nhits and flags.
- **Performance:** keep all textures of a view resident (24 stacks × 29 KB is trivial) for instant switching and 60 fps.

### 6.4 PNG fallback viewer (build it first, ≈1 h)
`GET /views/{key}/png/{bin}/{band}.png?stretch=…&lim=…&cmap=…` renders each frame server-side with the *shared* limits: numpy → 8-bit LUT → PNG. `PngViewer` blinks plain `<img>` elements.
- It guarantees P0 even if the WebGL viewer slips.
- It works on any device, and when WebGL2 is missing, which the app detects and switches automatically.
- It doubles as the GIF/MP4 export path.

### 6.5 Spectrum panel
- **Axes:** x = λ (µm, log option); y = µJy or AB.
- **Series:** points with x error = Δλ and y error = σ, one colour per visit.
- **Lines:** a binned median line, feature markers, and a template dropdown.
- **Interaction:** hover a point to highlight the frame and its position in the viewer. Click to open that exposure.
- **Toggles:** "Show contaminated" for He-line and flagged points (hidden by default but counted).
- **Sonification** (P2-8): pitch maps to λ and loudness to flux. Play the spectrum in ≈2 s.

### 6.6 Sky context (Aladin Lite v3)
- **Sync:** the Aladin FOV follows the viewer. The footprint of the current cutout is drawn.
- **HiPS presets:** `CDS/P/2MASS/color`, `CDS/P/allWISE/color`, `CDS/P/unWISE/color-W2-W1W2-W1`, `CDS/P/DSS2/color`, `CDS/P/PanSTARRS/DR1/color-z-zg-g`.
- **Catalogues:** Gaia DR3 (VizieR `I/355/gaiadr3`) and SIMBAD. Positions are **propagated server-side** to the selected visit epoch before drawing, because Aladin's markers sit at the catalogue epoch.

### 6.7 Accessibility, mobile, performance budgets
- **Reduced motion:** honour `prefers-reduced-motion` by defaulting to side-by-side or diff instead of autoplay blinking.
- **Colormaps:** colour-blind-safe sequential (cividis, magma) and diverging (blue–white–red) maps. Never encode by hue alone.
- **Keyboard and screen readers:** full keyboard control, ARIA labels, and auto-generated alt text such as *"Band 6 stacks from 3 visits (Aug 2025–Aug 2026). The central source shifts 10″ toward the north."*
- **Budgets:**
  - First stack visible ≤ 3 s warm / ≤ 30 s cold (selected band first).
  - Payload per view ≤ 3 MB. JS bundle ≤ 400 KB gz without Aladin; lazy-load Aladin.
  - Blink at 60 fps.

---

## 7. Creative uses of the 102 bands (catalogue to pick from)

| Visualization | How | Why it wows |
|---|---|---|
| **Band stacks** (default) | 6 per-detector visit stacks | The challenge hint, done correctly (S/N gain ≈√N) |
| **RGB presets** | `rgb:4,5,6` (thermal); **`rgb:methane`** (R = 4.0–4.2 µm, G = 3.6 µm, B = 3.25–3.4 µm: T/Y dwarfs glow red); **`rgb:ice`** (R = 2.6 µm continuum, G = 3.05 µm ice band, B = 3.6 µm continuum: ice-rich sightlines lose green and look **magenta**); `rgb:pah` | Spectral physics becomes colour |
| **λ-scrubber** | The per-visit spectral cube (§4.6), 17 planes per band and 102 in all (61×61×102 f16 ≈ 0.76 MB). A slider scans 0.75 → 5 µm. | "Fly through the spectrum" |
| **Click-any-pixel spectrum** from the cube | Client-side, instant | Hyperspectral feel |
| **Spectral flipbook** | Exposures of one visit sorted by λ | Turns the misleading flicker into a lesson |
| **Methane / coldness meter** | Index from §4.8 (relative to field stars), mapped to a thermometer from "star" to "Y dwarf" | One number the public gets |
| **Sonification** | Spectrum → sound | Accessibility plus delight |
| **Spectral anomaly map** | PCA over the per-pixel cube, with residual magnitude as an image | Finds odd sources automatically |
| **Pluto in 102 colours** | Track mode (§4.11), spectrum with CH₄-ice markers | The original Planet X, seen by the new instrument |

---

## 8. Citizen-science loop (impact multiplier)
1. **Report.** "Report candidate" captures the view key (pinned), (ra, dec), visit(s), the user's note and the type guess (mover, variable, artifact?).
2. **Auto-vet** (runs instantly, shown as a checklist):
   - SIMBAD/Gaia/CatWISE match (known?)
   - SkyBoT match (asteroid?)
   - Appears in ≥2 visits?
   - Inside an artifact footprint (ghost, crosstalk, persistence)?
   - PM significance; red colour?
3. **Store** in SQLite (one file, no server; swap types for Postgres if needed):
```sql
CREATE TABLE candidate (
  id TEXT PRIMARY KEY,                                  -- uuid4
  created_at TEXT DEFAULT CURRENT_TIMESTAMP,
  ra REAL NOT NULL, dec REAL NOT NULL, view_key TEXT NOT NULL, visits TEXT,          -- JSON
  kind TEXT CHECK (kind IN ('mover','variable','transient','artifact','other')),
  note TEXT CHECK (length(note) <= 1000), auto_checks TEXT,                          -- JSON
  votes INTEGER DEFAULT 0, status TEXT DEFAULT 'new');
```
4. **Community:** a public candidate gallery with up/down votes. Export CSV/VOTable. Link out to Backyard Worlds forums for brown-dwarf candidates and to MPC guidance for asteroids.
5. **Safety:**
   - Render notes as plain text, never HTML.
   - Rate-limit reports per IP.
   - Keep the public gallery behind a moderation flag during judging.
6. **Honesty banner:** "Candidates are not discoveries until confirmed by follow-up."

---

## 9. Deployment and operations

```yaml
# docker-compose.yml (sketch)
services:
  api:  { build: ./backend, command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1,
          env_file: .env, volumes: [cache:/cache, ./snapshot:/snapshot:ro] }
  web:  { image: caddy:2, volumes: [./frontend/dist:/srv, ./Caddyfile:/etc/caddy/Caddyfile],
          ports: ["80:80", "443:443"], depends_on: [api] }
volumes: { cache: {} }
# One uvicorn worker, because the job registry is in memory. CPU work runs in the API's process pool.
# Scale-out later: add redis + an arq worker service; the job API stays the same.
```
- **Host:** one 4–8 vCPU / 16 GB VM with a 100 GB SSD cache in **AWS us-east-1**. Any VM works with the IRSA-cutout path.
- **Calibration bootstrap** (`scripts/bootstrap_calib.py`): list S3 `qr3/{spectral_wcs,spectral_channels,epsf,l3_flux_corrections}/`, download the newest version of each (≈350 MB), and verify shapes and headers.
- **Pre-warm** (`scripts/prewarm.py`): build the default views for the 5 targets and **pin** them:
  - FOV 6′ and 12′, all bands, visit axis
  - diff V-first↔V-last
  - spectra at the target
  - the 25-year blink for Barnard, ε Ind B and WISE 0855
  - Pluto's track view, if P2-10 exists

  Run it again after every release change.
- **Snapshot mode:** `SNAPSHOT_DIR` holds the pre-warmed manifests and arrays. With `OFFLINE=1`, or if IRSA health checks fail, the API serves from the snapshot and shows a small "cached demo data" badge.
- **Demo laptop:** run the same compose file with `OFFLINE=1` and serve the app at `http://localhost`. The live demo then needs no network at all. **The demo must work on bad venue Wi-Fi** (✅ 11-06: ours delivered 30–80 KB/s).
- **Observability:**
  - Structured logs per job: frames planned/fetched/failed, bytes, time per stage, and which FrameSource served them.
  - `/healthz` checks SIA2 and S3, not TAP.
  - Simple counters.
- **Abuse limits:** cap FOV ≤ 60′ and frames per view (≤ 600, decimating by QA rank). Add a per-IP job rate limit. Jobs time out after 5 min.

---

## 10. Testing and validation

### 10.1 Unit tests (pytest)
- `fitsstream`:
  - Parse a saved cutout and compare it byte-for-byte with `astropy.io.fits` HDUs 1–4.
  - Confirm the stream stops before `EPSF`: bytes read < 120 KB on the 29×29 sample, since everything needed ends at byte 89,280 ✅ 11-06.
  - A truncated stream raises `EOFError`, which `with_retry` retries.
- `dedup`: unknown file names are skipped, and QR3 beats QR2 for the same (obsid, detector). A detector *pair* from one exposure is not a duplicate.
- `resolve`:
  - `Barnard's Star`, `barnards star`, `WISE 0855`, `WISE 0855−0714` (U+2212), `ε Indi B`, `RW Aur` and `R Dra` all reach the right main IDs.
  - `x' OR '1'='1` is quoted harmlessly.
- `propagate`: Barnard from Gaia J2016.0 + RV → 17h57m47.06s +04°46′14.6″ (±0.2″). SIMBAD J2000 *linear* gives the same position (±0.2″).
- `epoch_of_match`: the challenge's WISE 0855 coordinate → epoch 2010.46 ± 0.1, separation < 1″.
- `parallax_factors`:
  - Sign test against astropy's own apparent-place computation for a synthetic star at 1 pc.
  - WISE 0855's Nov 2025 → May 2026 displacement is 4.8″ ± 0.2″ toward PA 277° ± 5°.
- `cluster_visits` / `choose_axis` / visit classification:
  - WISE 0855's real MJDs → 2 full + 2 partial visits in band 6.
  - R Dra's MJDs → fixed bins.
  - Empty input → empty output.
- `parent_slice`: `CRPIX1A = -642` → x0 = 643 ✅. An S3 section reports its own origin, and the full-file header is never read for CRPIXnA.
- `flag_bits`: parse the real FLAGS header. No preset includes `SOURCE` or `OUTLIER`.
- `survey_number`: the Barnard Aug 2026 frame with `SPS_EPA = 180` → Survey 4.
- `reject_transients`: an injected moving point source on dark sky is flagged. A bright source whose flux varies ×5 across frames, skewed with one bright channel, is **not**.
- `weighted_stack`: a bright star's stacked flux is unbiased (< 1%) with per-frame weights.
- `spectral_cube` + `at_wavelengths` + `matched_difference`, on a synthetic steep-spectrum static star with the LVF gradient reversed in visit B *and* the half-channel survey offset:
  - residual ≤ 3σ at every offset from −3.7′ to +3.7′. Pairing frames at the target leaves 6–13σ; ✅ 11-06 run of this section's code.
  - the same star shifted by 1.7 px → dipole ≥ 10σ
- `pair_frames`: half-channel offsets pair; the tolerance is in channels.
- `fit_star`:
  - Recovers an injected (x, y) with σ consistent with the Cramér–Rao estimate.
  - An edge stamp → None; an all-masked stamp → None.
  - Recovered flux = injected total flux within 2%.
  - Over 300 noise draws of a bright star, the median reduced χ² is ≈1.0, and no fit ends above χ²(truth). This must hold at sub-pixel positions where the stamp edge reaches the ePSF table edge. ✅ 11-06: `mode="constant"` failed this (139/300 stalled); `"grid-constant"` passes.
- `significance`: sky robust σ ≈ 1 after renormalisation, on native and upsampled grids.
- `view_key`: unchanged when frames elsewhere in the sky change, and changed when a covering frame is added. `pin` freezes it.
- `to_f16`: NaN → −65504; values stay within ±6.5×10⁴.

### 10.2 Target acceptance tests (integration; thresholds **≈**, tune on day 1)
| Target | Check | Pass |
|---|---|---|
| Barnard's Star | PM fit over all full visits | \|μ − 10.39″/yr\| < 1.0″/yr; PA within 6° of 355.6° |
| | λ-matched diff, V1→V3 (band 6, Aug 2025 → Aug 2026) | Dipole-model shift 1.5–1.9 px (expected 1.7) along PA 356° ± 15° |
| | 25-year blink | 2MASS (2000.41) → SPHEREx offset 4.55′ ± 0.1′ |
| ε Indi B | Spectrum | Detected in all 6 bands. Methane index < 0.5 × the field-star median. PM within 1.5″/yr of 4.68 at PA ≈ 122°. |
| WISE 0855 | Band-6 stacks of the two full visits, at the propagated position | S/N ≥ 5 in both; < 3σ in bands 1–3; displacement 0.78 ± 0.3 px toward PA 277° ± 20°. ✅ 11-06: Gaia DR3 5756956644387831296 (G = 16.3) lies 1.35 px / 0.70 px from WISE 0855 in the two full visits, so bands 1–3 and the displacement need a two-source fit (`validation/G4b-wise-stacks/`) |
| RW Aur | Light curve | ≥ 3 visits per band, finite errors, flags shown; spectra per visit overlaid |
| R Dra | Periodogram (14-day bins, ≥ 20 bins, annulus method) | Peak at 245 ± 30 d; phase-folded curve coherent. ✅ 11-06: real coverage gives 16 occupied 14-day bins in bands 1, 3, 4, 6 and 6 in bands 2, 5 (≥ 20 only with all bands together) |
| Pluto (P2-10) | Track mode | Pluto within 1 px of the frame centre in every frame; stars stream past; CH₄-ice dips visible at 1.7/2.3 µm |
| All | Visual | Shared stretch, north up / east left, correct dates, surveys and full/partial labels, no blank frames without explanation |

### 10.3 Performance tests
- **Cold view** (6′, from a us-east-1 VM):
  - first stack p50 ≤ 30 s; full view p50 ≤ 90 s, p95 ≤ 180 s
  - bytes from IRSA ≤ 70 MB per view on the cutout path
- **Warm view:** ≤ 300 ms manifest, ≤ 1 s all stacks.
- **Soak:** 4 concurrent IRSA requests for 10 minutes without 503s before raising concurrency (§3.7).

---

## 11. Hackathon execution plan

### 11.0 Day-1 verification checklist (first 2 hours, one person, `scripts/verify_day1.py`)
1. On one full QR3 file, check `CWAVE[parent_slice]` against `WCS-WAVE` (≈1 nm) and confirm both share `IMAGE` orientation.
2. Read the headers of `spectral_channels` (which HDU?), `l3_flux_corrections` (multiply or divide?) and `epsf` (normalised? oriented like `IMAGE`? Fit 5 isolated stars and check that residuals are symmetric).
3. From the VM, time an S3 section read and an IRSA cutout, then pick the default FrameSource.
4. Check that the SIA2 VOTable has `obs_collection`, `obs_id`, `access_url`, `t_min` and `cloud_access`.
5. Compare Horizons' SPHEREx position (−163182) with the header `X_SC/Y_SC/Z_SC` for 3 frames. Is the difference < 10 km?
6. Find the `OVERFLOW` onset: match OVERFLOW flags to 2MASS K in one crowded cutout.
7. For the 5 targets, measure the fraction of frames with `L2DQAFLG ≠ Pass` or `FINAST ≠ 0`, then set the rejection policy.
8. Check for a survey-number keyword in the headers or archive tables.
9. Render an asymmetric test pattern and confirm north-up, east-left in both the WebGL and PNG viewers.
10. Run the resolver aliases and the propagation tests (§10.1) against live SIMBAD and Gaia.

### 11.1 Before the event (Nov 5–13): learn and plan, don't build the product
Check the **2026 Participant FAQ/Terms**. Historically, team formation, research and planning before the weekend are fine, but project work is meant to happen during it.
- **Everyone:** read `understanding.md` and run IRSA notebooks *spherex-intro* and *spherex-cutouts* in throwaway environments.
- **Science lead:** read Explanatory Supplement §1.3–1.4, §2.2–2.4, §3.2.5, §3.3 and §3.4.
- **Design:** wireframes in Figma; colormap and accessibility choices; the 5 "missions" storyboard, plus Pluto.
- **Ops:** create the cloud account (us-east-1), domain, and a CI template (generic, not project code). Verify network access to IRSA and S3 from the venue if possible.
- **Nov 13:** read the Resources tab and update the open questions in understanding.md §11.

### 11.2 Roles (team of up to 6)
| Role | Owns |
|---|---|
| **Data engineer** | SIA2/TAP client, both FrameSources + failover, cache, release watcher, calibration bootstrap, day-1 checklist items 1–5 |
| **Science lead** | Preprocess, reprojection, stacks, spectral cubes and λ-matched diff, ePSF astrometry and photometry, validation table |
| **Backend/API** | FastAPI, in-process jobs and SSE, manifests and pins, PNG renderer, exports, deploy, snapshot mode |
| **Viewer dev** | WebGL renderer, player, overlays, URL state, embed |
| **Panels and UX** | Spectrum and light-curve panels, Aladin context, target bar, aliases and epoch banner, accessibility |
| **Storyteller/PM** | Scope control, demo script, video, slides, README and credits, submission. Also tests targets continuously. |

### 11.3 The 39-hour plan (H0 = Sat 09:00, deadline Sun 23:59)
| Window | Goal | Deliverables |
|---|---|---|
| H0–H2 | Kickoff | Repo, envs, CI, "hello" front and back deployed to the us-east-1 VM. Read final resources. Freeze the API contract (§5). Start the day-1 checklist (§11.0). |
| H2–H8 | Plumbing | SIA2 coverage, both fetchers plus cache, calibration bootstrap, resolver with aliases and PM. **PNG fallback viewer on real stacks.** The WebGL viewer renders a fake float16 stack. |
| H8–H14 | **M1: P0 blink** | End-to-end visit stacks per band for any RA/Dec. Shared stretch. Timeline with full/partial visits. URL state and pins. Barnard works. |
| H14–H20 | P1 core | Spectral cubes and λ-matched diff, predicted track (PM + parallax), flags overlay, Aladin context. Pre-warm 5 targets. **Rotate sleep.** |
| H20–H26 | **M2: P1 complete** | Spectrum on click (forced ePSF), astrometry card (PM fit), embed route, freshness badge, bright-target display |
| H26–H32 | P2 picks | In order: 25-year blink → Pluto track mode (Horizons) → spectral flipbook / methane meter → light curves (R Dra) → mover finder → GIF export |
| H32–H34 | Freeze + **complete submission** | Validation table run, snapshot mode, performance pass, mobile bug bash. **Submit a complete project by H34 (Sun 19:00).** |
| H34–H38 | Story | 30 s video, slides, README, credits/DOIs, AI-use disclosure if required. Update the submission as each lands (if the rules allow edits, §11 of understanding.md). |
| H38–H39 | Final update | Last edit well before 23:59. Then hands off. |

**Cut lines:**
- **Behind at H14:** keep only the FrameSource that already works, and drop the exposure flipbook and Planet X mode.
- **Behind at H26:** drop the mover finder and light curves, but keep R Dra as a static "many visits" example.
- **Never drop:** the 5 targets working, URL coordinates and name aliases, flags, epoch handling, credits, the PNG fallback.

### 11.4 Demo script
**30-second video**
1. *(0–5 s)* "1930: Pluto found by blinking two photographs." (Archival plate pair; check its licence and credit it.)
2. *(5–11 s)* Type "Barnard's Star" → 2MASS 2000 → SPHEREx 2026: the star leaps 4.6′.
3. *(11–17 s)* SPHEREx-only visits: blink → λ-matched diff dipole → fitted μ beside Gaia's 10.39″/yr ✓ (numbers from the live run).
4. *(17–23 s)* WISE 0855: at 1–2 µm only an ordinary field star sits beside it (G = 16.3, 0.7–1.35 px away); at 4.6 µm the brown dwarf itself appears as a dot that moves. Spectrum and methane meter say "colder than any star" only if G4b is accepted by then; otherwise show the blink alone (audit V-07, workflow.md §11.2).
5. *(23–27 s)* If P2-10 shipped: Pluto, the original Planet X, as SPHEREx saw it, methane ice and all. Otherwise extend segment 4.
6. *(27–30 s)* "Any coordinates. One link. Find the next one." (URL plus embed.)

**3-minute live demo:** the same arc, plus:
- ε Indi B's spectrum with a T6 template
- R Dra's periodogram
- the flags overlay explaining Barnard's NaN core (and the model-filled display)
- the "data updated weekly" badge
- if built, Planet X mode recovering Makemake's distance

### 11.5 Submission checklist (confirm against the 2026 guide)
- [ ] Public URL (and the snapshot fallback) works logged-out on mobile and desktop, with and without WebGL
- [ ] Repo public with README: what, why, how to run, architecture, validation table, limitations
- [ ] ≤30 s video and/or ≤7 slides (historical format, so verify)
- [ ] Space agency data listed: SPHEREx QR2/QR3 (IRSA), Gaia DR3, WISE/NEOWISE, 2MASS, plus JPL Horizons if Pluto ships
- [ ] SPHEREx DOIs (10.26131/IRSA652, 10.26131/IRSA662) and acknowledgement text; Gaia, 2MASS, WISE, IRSA and CDS acknowledgements (understanding.md §4.8)
- [ ] No NASA insignia; licensed images only (the 1930 plates included)
- [ ] AI-use disclosure, if required
- [ ] All 5 test targets linked as one-click **pinned** permalinks in the README

---

## 12. Risk register
| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| IRSA slow, throttling or down during judging | Med (✅ 11-06: a 503 under 4 parallel requests; truncated bodies) | High | Pre-warm, pinned links, snapshot mode, S3 path, backoff with jitter |
| Slow venue network | High (✅ 11-06: our network got 30–80 KB/s) | High | Backend in the cloud; float16 stacks; selected band first; demo laptop serves the snapshot locally |
| New data cold-starts cached demo views | Med (weekly ingests) | High | Frame-list cache keys; pinned demo links |
| DR1 lands mid-hackathon (new collections, superseded QR2) | Med | Med | Release registry plus dedup policy. One YAML edit. Pinned links don't change. |
| Name resolution fails on a test target | Certain without aliases (✅ 11-06: `WISE 0855-0714`, `Barnard's Star`) | High | Alias table, quote escaping, Unicode normalisation, tests |
| Cutout bandwidth explosion | High if ignored | High | Stream-abort after ZODI. Server-side stacking. FOV caps. |
| WISE 0855 too faint, or its first visit too thin | Med | Med | Use the two full visits (16 and 21 band-6 frames). Band 5+6 red-sum. AllWISE long-baseline blink. Honest S/N and full/partial labels. |
| WISE 0855's autumn-2026 visit not public in time | Near-certain (✅ 11-06) | Low | Plan around the existing QR2 visits |
| Saturated targets break photometry or vanish under masks | High | Med | `bright` mask preset, model-filled display cores (marked), wing fits, same-channel annulus ratios, labels |
| False variability from channel mixing | High if naive | High (validity) | Per-pixel λ-matched diff, spectrally normalized light curves |
| Epoch confusion (the given WISE 0855 coordinates) | Certain | High | Epoch banner plus track mode |
| WebGL NaN or orientation bugs on judges' devices | Med | High | Sentinel instead of NaN, day-1 orientation test, PNG fallback viewer |
| `CWAVE` orientation, flux-correction direction or ePSF normalisation wrong | Low | Med | Day-1 checklist (§11.0) |
| Scope creep | High | High | Tiered features, cut lines, a PM who says no |
| Time-zone or deadline confusion | Low | Fatal | Complete submission by H34; final update by H38. The deadline is local-event time. |

---

## 13. Repository layout
```
parallax/
├─ README.md                     # pitch, quickstart, validation table, credits, pinned permalinks
├─ understanding.md  implementation.md
├─ backend/
│  ├─ app/
│  │  ├─ main.py                 # FastAPI app, routers, CORS for our origin, frame-ancestors for /embed
│  │  ├─ api/{resolve,coverage,views,jobs,spectrum,lightcurve,astrometry,overlays,sso,export,candidates}.py
│  │  ├─ jobs.py                 # in-process job registry: asyncio tasks + ProcessPoolExecutor
│  │  ├─ render_png.py           # PNG fallback frames, GIF/MP4/APNG export
│  │  └─ settings.py
│  ├─ spherex/
│  │  ├─ access/{coverage.py,dedup.py,fitsstream.py,s3sections.py,retry.py,releases.py,watcher.py}
│  │  ├─ calib.py  flags.py  preprocess.py  epochs.py  grid.py  stack.py  cube.py
│  │  ├─ epsf.py  photometry.py  astrometry.py  lightcurve.py  movers.py  sso.py  ephem.py  planetx.py
│  │  ├─ targets.py  constants.py  external/{gaia.py,catwise.py,simbad.py,twomass.py,wise.py}
│  │  └─ render.py               # zscale limits, float16 encoding
│  ├─ config/releases.yaml
│  └─ tests/{unit,integration}/  # + data/cutout_29x29_qr3.fits fixture, WISE 0855 / R Dra MJD lists
├─ frontend/
│  ├─ src/{App.tsx, state/{store.ts,url.ts}, api/client.ts}
│  ├─ src/gl/{renderer.ts,shaders.ts,colormaps.ts}
│  └─ src/components/{TargetBar,Viewer,PngViewer,OverlayLayer,PlayerControls,Timeline,
│                      SpectrumPanel,LightCurvePanel,AstrometryCard,FrameInspector,
│                      SkyContext,ShareDialog,About}.tsx
├─ scripts/{verify_day1.py,bootstrap_calib.py,prewarm.py,make_snapshot.py}
│  (✅ 11-07 D: config/ lives at the repo root, per workflow.md §15: config/releases.yaml, config/pins/,
│   config/calibration.lock; D scripts: bootstrap_calib.py, make_pins.py, refresh_check.py,
│   collect_d_fixtures.py, blink25_acquire.py, rdra_inputs.py)
├─ docker-compose.yml  Caddyfile  .env.example
└─ snapshot/                     # pre-computed demo data (git-lfs or release asset)
```

---

## 14. Appendix

### 14.1 Constants
```python
PIXEL_ARCSEC = 6.15
EXPTIME_S = 113.58
BANDS = {  # detector: (λmin, λmax µm, R)  — Supplement v2.0 Table 2
    1: (0.744, 1.116, 39), 2: (1.099, 1.651, 41), 3: (1.636, 2.421, 41),
    4: (2.423, 3.822, 35), 5: (3.809, 4.420, 112), 6: (4.412, 5.002, 128)}
CHANNELS_PER_DETECTOR = 17
DETECTOR_PARTNER = {1: 4, 2: 5, 3: 6, 4: 1, 5: 2, 6: 3}   # co-aligned through the dichroic ✅ 11-06
SCIENCE_START = "2025-05-01"
SPHEREX_HORIZONS_ID = -163182                              # ✅ 11-06
NODATA_F16 = -65504.0
# Use each catalogue's own epoch; pass rv only with Gaia epochs (SIMBAD J2000 is linear) ✅ 11-06
TEST_TARGETS = {  # name: (ra, dec, epoch, pmra*, pmdec [mas/yr], plx [mas], rv [km/s] or None, source)
    "Barnard's Star": (269.44850252544, 4.73942005111, 2016.0, -801.551, 10362.394, 546.976, -110.47,
                       "Gaia DR3 4472832130942575872"),
    "eps Ind B":      (331.07645259656, -56.79381206688, 2016.0, 3981.977, -2466.832, 270.658, None,
                       "Gaia DR3 6412596012146801152 (Ba+Bb photocentre)"),
    "WISE 0855-0714": (133.81890825, -7.247048, 2000.0, -8123.7, 673.2, 439.0, None,
                       "SIMBAD J2000 from Kirkpatrick+2021 (linear)"),
    "RW Aur":         (76.95654431103, 30.40131614989, 2016.0, 2.641, -27.398, 6.406, None,
                       "Gaia DR3: position of A (…815232); PM and plx of B (…424576), since A has RUWE 16"),
    "R Dra":          (248.16737836729, 66.75500674547, 2016.0, -20.643, 6.149, 1.251, None,
                       "Gaia DR3 1648328016354496384")}
TWOMASS_EPOCH = {"Barnard's Star": 2000.405, "eps Ind B": 1999.851, "RW Aur": 1999.904}   # fp_psc.jdate ✅ 11-06
```

### 14.2 Handy queries
```bash
# Which SPHEREx images cover Barnard's Star now? SIA2, two collections in one call ✅ 11-06 (359 rows, ≈6 s)
curl -s "https://irsa.ipac.caltech.edu/SIA?COLLECTION=spherex_qr2&COLLECTION=spherex_qr3&POS=circle+269.4461+4.7707+0.001&RESPONSEFORMAT=VOTABLE"

# Same via TAP, with detector names (10–17 s) ✅ 11-06 (WISE 0855 at its 2026 position)
curl -s https://irsa.ipac.caltech.edu/TAP/sync --data REQUEST=doQuery --data LANG=ADQL --data FORMAT=csv \
  --data-urlencode "QUERY=SELECT o.collection, o.observationid, p.energy_bandpassname, p.time_bounds_lower
    FROM spherex.plane p JOIN spherex.observation o ON o.obsid=p.obsid
    WHERE 1=CONTAINS(POINT('ICRS',133.7578,-7.2420),p.poly) ORDER BY p.time_bounds_lower"

# A cutout. It carries ~3.9 MB of ePSF regardless of size; everything needed ends at byte 89,280 ✅
curl -o c.fits "https://irsa.ipac.caltech.edu/ibe/data/spherex/qr3/level2/2026W33_2A/l2b-v27-2026-241/6/level2_2026W33_2A_0594_4D6_spx_l2b-v27-2026-241.fits?center=269.4461,4.7707deg&size=0.05"

# Freshest planning period in QR3 (release watcher) ✅ 11-06 → 2026W40_2A
curl -s "https://nasa-irsa-spherex.s3.amazonaws.com/?list-type=2&prefix=qr3/level2/&delimiter=/" | grep -o '<Prefix>qr3/level2/[^<]*' | tail -1

# Has DR1 appeared? ✅ 11-06 → only qr2/ and qr3/
curl -s "https://nasa-irsa-spherex.s3.amazonaws.com/?list-type=2&delimiter=/" | grep -o '<Prefix>[^<]*'

# Calibration products ✅
curl -s "https://nasa-irsa-spherex.s3.amazonaws.com/?list-type=2&prefix=qr3/spectral_wcs/" | grep -o '<Key>[^<]*'

# Gaia DR3 astrometry at IRSA ✅ 11-06
curl -s https://irsa.ipac.caltech.edu/TAP/sync --data REQUEST=doQuery --data LANG=ADQL --data FORMAT=csv \
  --data-urlencode "QUERY=SELECT source_id, ra, dec, parallax, pmra, pmdec, radial_velocity, ruwe FROM gaia_dr3_source
    WHERE 1=CONTAINS(POINT('ICRS',ra,dec),CIRCLE('ICRS',269.4485,4.7394,0.003))"

# 2MASS epoch of a source ✅ 11-06 (Barnard → jdate 2451692.93 = 2000-05-28)
curl -s https://irsa.ipac.caltech.edu/TAP/sync --data REQUEST=doQuery --data LANG=ADQL --data FORMAT=csv \
  --data-urlencode "QUERY=SELECT designation, ra, dec, k_m, jdate FROM fp_psc
    WHERE 1=CONTAINS(POINT('ICRS',ra,dec),CIRCLE('ICRS',269.45208,4.69336,0.01))"

# 2MASS image search, then a Ks cutout ✅ 11-06
curl -s "https://irsa.ipac.caltech.edu/ibe/search/twomass/allsky/allsky?POS=269.452,4.6946&ct=csv" | head -3
curl -o k.fits.gz "https://irsa.ipac.caltech.edu/ibe/data/twomass/allsky/allsky/000528n/s101/image/ki1010209.fits.gz?center=269.452,4.6946&size=0.1"

# SIMBAD by name, quote escaped (CfA mirror) ✅ 11-06
curl -s https://simbad.harvard.edu/simbad/sim-tap/sync --data REQUEST=doQuery --data LANG=ADQL --data FORMAT=csv \
  --data-urlencode "QUERY=SELECT b.main_id, b.ra, b.dec, b.pmra, b.pmdec, b.plx_value FROM basic b JOIN ident i ON i.oidref=b.oid WHERE i.id='Barnard''s Star'"

# Pluto as seen from SPHEREx (JPL Horizons) ✅ 11-06
curl -s "https://ssd.jpl.nasa.gov/api/horizons.api?format=text&COMMAND='999'&OBJ_DATA='NO'&MAKE_EPHEM='YES'&EPHEM_TYPE='OBSERVER'&CENTER='500@-163182'&TLIST='2460900.5','2461080.5'&QUANTITIES='1'"

# Known asteroids near RW Aur on 2025-09-10 (SkyBoT; the observer parameter is -loc) ✅ 11-06
curl -s "https://ssp.imcce.fr/webservices/skybot/api/conesearch.php?-ep=2460928.5&-ra=76.9565&-dec=30.4013&-rd=0.25&-mime=text&-output=basic&-loc=500&-filter=0&-objFilter=111&-from=ParallaX"
```

### 14.3 Non-obvious facts this plan depends on
**Checked 2026-11-05 (✅):**
- IRSA SIA2, TAP and cutout responses have no CORS headers. The S3 bucket returns `Access-Control-Allow-Origin: *`. Both re-checked 11-06.
- IRSA TAP: `CONTAINS(POINT, p.poly)` with the plane/artifact/observation join works. `INTERSECTS` works only column-first (`INTERSECTS(p.poly, CIRCLE(...))`), and the joined version timed out at >200 s.
- A 29×29 QR3 cutout is 3,962,880 bytes, dominated by the 441-row `EPSF` table (8752 B/row).
- The QR3 header uses `SPS_EPA`, not `SPS_PA_ECL`. `CRPIX1A`/`CRPIX2A` locate a *cutout* in the parent detector.
- `PXSRCMSK = 81.19`: SOURCE covers most pixels in crowded fields.
- The real spectral-WCS directory is `cal-swcs-v5-2026-191`. The ePSF has an extra D3 `v2`.
- Frames from before 2025-05-01 (IOC) exist in the archive for some targets.

**Checked 2026-11-06 (✅ 11-06):**
- Archive and data:
  - Each exposure covers a star on a co-aligned detector pair: 178 of 181 Barnard exposures have exactly D1+D4, D2+D5 or D3+D6.
  - WISE 0855 has 256 frames, all QR2. Band-6 counts per cluster are 3 · 16 · 3 · 21, so it has two full visits. R Dra has ≈2,480 frames, ≈1,950 of them in the deep collections.
  - S3 holds only `qr2/` and `qr3/` (no DR1). The newest QR3 planning period is `2026W40_2A`.
  - In a cutout, everything up to `ZODI` ends at byte 89,280. In a full file, IMAGE data starts at byte 25,920 and is exactly 5,780 blocks.
- Service performance:
  - SIA2 accepts repeated `COLLECTION` and answers in ≈6 s. TAP takes 10–17 s even for trivial queries.
  - The IRSA cutout service returned one 503 under 4 parallel requests, and some transfers stopped early after HTTP 200. `gzip=true` doesn't help.
  - Our network: 30–80 KB/s from IRSA and S3; 1–2 s per S3 request.
- Names and astrometry:
  - SIMBAD (CfA mirror) normalizes identifiers but needs `'` escaped as `''`. `WISE 0855-0714` doesn't resolve; `WISE J085510.83-071442.5` does.
  - SIMBAD's J2000 coordinates are linear back-propagations of Gaia.
  - SIMBAD's RW Aur parallax is Hipparcos 2007 (15.42 mas). Gaia DR3 gives 6.41 mas (RW Aur B).
  - 2MASS epochs: Barnard 2000-05-28, ε Ind B 1999-11-07, RW Aur 1999-11-26.
- Other services:
  - JPL Horizons supports SPHEREx as an observer (`CENTER='500@-163182'`).
  - SkyBoT's observer parameter is `-loc`.

---

## 15. Revision log (2026-11-06)

| Area | Was | Now | Why |
|---|---|---|---|
| Cache key (§2.3) | `sha256(params + global release_state)` | `sha256(params + exact frame list)`, plus `pin=` links | Any new data anywhere changed every key, which would cold-start the pre-warmed demo during judging |
| Jobs (§2.2) | arq + Redis + 2 worker replicas | In-process asyncio plus a process pool, one API process | Fewer moving parts for a 39-hour build; scale-out stays possible |
| Coverage (§3.2) | TAP (≈10 s), with 5 corner queries for FOVs | One SIA2 call, multi-collection (≈6 s); TAP as fallback | Measured; TAP has 10–17 s fixed overhead |
| Corner offsets (§3.2, §3.4) | `ra ± d/cos(dec)` | Grid-corner projection through the WCS; no corners for SIA2 | The old form broke across RA = 0 and near the poles |
| Fetch default (§3.4) | IRSA cutouts | S3 sections in us-east-1, cutouts elsewhere, automatic failover | IRSA 503s and truncation seen on 11-06; S3 is unthrottled in-region |
| Cutout size (§3.4) | Same as the FOV | FOV × √2 + margin | Rotated frames left NaN corners |
| Parent pixels (§3.5) | `CRPIXnA` read from any header | The FrameSource supplies `origin` | A full-file header (S3 path) would have mapped every λ lookup to the wrong pixels |
| `_data_bytes`, BZERO | Non-standard formula; ints promoted to float | Standard formula; integers stay integers | Correctness; FLAGS bit tests |
| Retries | Unspecified | Backoff with jitter on 429/5xx, `EOFError` and transport errors | Truncated HTTP 200 bodies seen on 11-06 |
| Resolver (§4.1) | `WHERE i.id = '{name}'` | Escaped literal, alias table, Unicode normalisation, CfA mirror first, Horizons fallback | `Barnard's Star` broke the query (and allowed injection); `WISE 0855-0714` doesn't resolve |
| Propagation (§4.1) | SIMBAD J2000 + RV | Gaia J2016.0 + RV, or SIMBAD J2000 linear | SIMBAD back-propagated linearly: 0.4″ inconsistency for Barnard |
| Predicted positions (§4.1) | PM only | PM + parallax, through one `pos(t)` | Overlays, track mode and residuals now share one model |
| Epoch guard (§4.1) | 3′ search; vague match test | 6′ search; closest-approach epoch | 3′ missed Barnard typed at its current position |
| Time axis (§4.2) | "> 6 visits or median gap < 30 d" → bins | "> 6 clusters or any cluster > 45 d" → bins; full vs partial visits | Continuous coverage forms one long cluster; partial visits were merged across six months |
| Preprocess (§4.3) | Empty-background crash; no bright-target handling | Sky-pixel fallback, per-frame weight, `bright` preset, model-filled display cores | Robustness; bright targets could vanish under footprint masks |
| Significance (§4.4) | `mean/√var` used directly | Empirically renormalised | Resampling makes the variance map approximate, so "5σ" wasn't 5σ |
| Stacking (§4.5) | Per-pixel inverse-variance weights; symmetric clip with a 0.35 spectral tolerance | Per-frame weights; clip only on sky-like pixels | Bright sources were biased low; skewed spectra (one bright channel) got clipped |
| Differencing (§4.6) | Frame pairs matched at the target only; tolerances disagreed | Per-pixel spectral cubes; one 0.75-channel tolerance | The LVF gradient reverses between PA 0°/180° visits |
| ePSF fit (§4.7) | Stamp renormalised; no bounds or edge checks; `map_coordinates(mode="constant")` | Unit-flux ePSF, bounded fit, guards, reduced χ², `mode="grid-constant"` | Fluxes were per-7×7 box, not total, and edge stamps silently wrapped. The 7×7 stamp can sample past the ±3.3 px table, where "constant" jumps to zero, so 46% of bright-star fits stalled in a synthetic test (✅ 11-06). |
| R Dra (§4.9) | ePSF wing fits | Same-channel annulus ratios | The ePSF table only spans ±3.3 px |
| SkyBoT (§4.11) | `-observer=500` | `-loc=500` | `-observer` is ignored by the service |
| Solar System (§4.11) | Topocentric shift by hand | Horizons with SPHEREx (−163182) as observer; Pluto track mode | Simpler, more accurate, and it puts the original Planet X in the demo |
| Planet X (§4.12) | Visit-level orphans; "near-static within a visit" | Per-day stacks, latitude drift, validation on dwarf planets | Latitude drift is 5.5 px per 14 days at 500 AU and β = 20° |
| 25-year blink (§4.13) | 2MASS via SIA2 "≈1998", 4.9′ | 2MASS via IBE, per-target epochs (2000.41 for Barnard), 4.55′ | Measured `jdate`; 2MASS isn't in IRSA's SIA2 ObsCore |
| Renderer (§6.3) | `isnan()` in the shader, R32F, "flip v" | Float16 sentinel, R16F upload with no decode, explicit orientation rule | Portability; the old flip advice would have produced south-up images |
| Fallback (§6.4) | None | Server-rendered PNG viewer | Guarantees P0 |
| rgb:ice (§7) | "green-dark" | Magenta, since the ice band sits in G | Colour logic |
| Database (§8) | Postgres DDL labelled SQLite/Postgres | SQLite-valid DDL; moderation and safety rules | `now()`, `UUID` and `JSONB` fail in SQLite |
| Schedule (§11) | Submit at H38 | Complete submission at H34; day-1 checklist | "Early" at H38 left no buffer |
| Constants (§14.1) | SIMBAD J2000 everywhere; RW Aur ϖ = 15.42 mas | Gaia J2016.0 astrometry where available; RW Aur ϖ = 6.41 mas; 2MASS epochs | Verified values |
| Box sizing (§3.4, ✅ 11-07) | S3 section box = the grid corners projected | IRSA's box rule + 1 px (a superset of the cutout box) | F2: IRSA's exact sizing isn't public; failover must never lose pixels |
| QR2 FLAGS (§3.4, ✅ 11-07) | Full-file FLAGS always RICE_1 | RICE_1 in QR3 only; plain in QR2 | F2 |
| IRSA concurrency (§3.7, ✅ 11-07) | 4, raise after the soak | 4, with retries mandatory: 9.6% 503s at 4 and 4.1% at 2 from our network | F12 (VM run pending) |
| 2MASS match (§4.13, ✅ 11-07) | Nearest/brightest source | Nearest within 10″ with Ks consistent with the catalogue | WISE 0855 trap |


## 16. Revision log (2026-11-07, platform — P)

Deviations recorded by P with the platform implementation (`backend/app/`). Each row is implemented and tested
in `backend/tests/app/`.

| Area | Was | Now | Why |
|---|---|---|---|
| View key (§2.3, §5.3) | Canonical view params + frame list | Canonical **compute** params (resolved target id, grid centre rounded to 1e-5°, `fov`, `px`, `axis`, `center`, resolved `mask` preset, `rel`, `lim`) + `frame_list_digest(F)`; display-only params (`bands`, `partial`, `stretch`, `cmap`, `mode`, `fps`, `ov`, `flags`, `sel`, `t`, `ui`) are excluded; `pin` enters through F | One build makes every band and bin (selected band first), so display choices share one cache entry; `lim` stays because it sets the manifest's shared limits |
| Frame cap (§9) | ≤ 600 frames, "decimating by QA rank" | ≤ 600 frames via D's `deepfield.cap_frames`, per (bin, detector), with the per-bin cap found by bisection; every dropped frame appears in `stacks[].skipped` as `cap:…` | Keeps all bins represented (R Dra: 2,483 frames) and never drops frames silently (workflow.md §11.2) |
| Job rate limit (§9) | "per-IP job rate limit" | 6 cold builds per minute per IP (`JOBS_PER_MINUTE_PER_IP`); warm views and payloads are not limited; candidates 10/hour/IP | Demo and judges hit warm views; only cold builds cost IRSA traffic |
| Snapshot fallback (§9) | `OFFLINE=1` or IRSA health failure | Same; the IRSA probe is cached 60 s, and a view missing from the snapshot returns 404 with a "not in the offline snapshot" message | Never a half-live view during the demo |
| `/healthz` (§9) | SIA2 and S3 | SIA2 and S3 (never TAP), plus snapshot and job-registry probes; `/metrics` serves the counters in Prometheus text | Pre-flight and failure drills (workflow.md §13.4–13.5) need one URL |
| Difference (§5.1) | `GET /views/{key}/diff` | Behind the `diff` flag; needs the locked calibration (`CALIB_ROOT`), otherwise 409; `validity` = `accepted` only when the flag is `on` (G4a accepted) | workflow.md §11.2: no difference image without G4a |
| Flipbook (§5.1) | `GET /views/{key}/frames?sort=lambda` | 501 naming owner I until a per-frame λ-at-target product exists | Sorting by an unknown λ would mislabel the flipbook (G5.flip) |
| Exports (§5.1) | gif, mp4, apng, fits, csv | gif, apng, fits, csv; mp4 returns 501 | No ffmpeg in the image; GIF/APNG cover the use |
| Science routes | spectrum, lightcurve, astrometry, sso, movers, overlays/sso | Wired to M's modules by name; 501 naming owner M while the module is missing; all behind flags that are `off` | Honest failure instead of a placeholder result |
| Resolver, `pos(t)` (§4.1) | M's `targets.py` | P's temporary adapter `app/adapters/targets.py` (SIMBAD → Gaia through D's clients, offline table fallback; PM + parallax `pos(t)`); replaced when M's module lands | P0-1 and the track overlay need a resolver now; G1 acceptance stays with M |


## 17. Role M integration and scientific adjudication (2026-11-08)

This supersedes section 16's missing-M science-route and temporary-target-adapter rows. The
implementation and scientific acceptance are separate: see the strict responsibility
and inherited-dependency matrices in [docs/role-M-handoff.md](docs/role-M-handoff.md).
The source modules and routes now perform native measurements. Scientific flags stay
off until fresh evidence, the prescribed independent reviews and gate sign-offs exist.

* `spherex.targets` is the common catalogue/epoch/PM/parallax model. P's adapter is a
  compatibility re-export. CatWISE client PMs already arrive in mas/yr; overlays must
  not multiply them by 1000 a second time. Gaia RV is used only at Gaia's own epoch.
* ePSFs retain sky orientation, zero-based parent zoning and an oversampled integral
  of 25. Real F5 fits do not show approximately unit reduced chi-square in short
  bands. Eight rotations/reflections do not repair that discrepancy; no orientation,
  variance inflation or wider acceptance threshold is selected to manufacture a pass.
* WISE forced two-source photometry fits a common local WCS translation with signed
  amplitudes. Catalogue separation stays fixed and translation uncertainty enters
  the joint covariance. WISE motion now uses a joint native-pixel likelihood per
  full visit: a shared sky offset, independent nonnegative target/neighbour fluxes
  and free constant sky per exposure, and Gaussian registration nuisance terms.
  Catalogue motion/parallax defines within-visit relative positions; independent
  visit offsets remain free. Three starting positions check competitive modes;
  separated competitive modes, singular fits and boundary solutions are rejected.
  Covariance is conditional on the PSF/Gaussian registration model. Two epochs
  with fixed catalogue parallax have zero residual model-test degrees of freedom;
  they do not estimate intrinsic scatter or independently measure parallax.
  Independent I review is required; this is not IRSA Tool agreement.
* PM fitting uses whitening/SVD, preserves the WCS sky covariance and rejects deficient
  geometries. Only full visits enter the target motion fit; WISE uses band 6. Internal
  parallax is arcsec, while HTTP `fit.plx_fixed` remains **mas**, as the existing UI expects.
* Science calls with `key` use that immutable view's references. Registration fetches
  at least a 12-arcmin region independently of the display FOV. Cap exclusions and
  failed native inputs are retained. Light curves can select `release=qr2|qr3`;
  cross-release quantitative aggregation is still refused while F4 is unresolved.
* A periodogram requires at least 20 actual time bins; detectors at the same epoch do
  not become extra bins. Search periods stop at the observed baseline. The initial M
  implementation's additional fixed 500-day baseline guard was not a governing
  acceptance requirement and was removed explicitly; the 245+/-30-day criterion is unchanged.
* QR2 correction headers say **multiply** in sky-oriented pixels. The empirical test
  uses matched wavelengths and position-dependent solid angles. A noisy comparison
  that does not improve cannot reverse the documented operator or pass F4.
* Official WISE photon response files and hashes are packaged with the backend.
  Synthetic W1-W2 is Vega based, approximate because W2 extends beyond 5 microns.
  Packaged checksum-verified assets now include M0--M9/L0--L9/T0--T9 observed SpeX
  standards, three IRTF spectra, a 500 K BT-Settl Y-regime model, and Pickles A0V/G2V
  composites. Native CBAND boxcar overlays are approximate, preserve gaps, do not
  extrapolate, and fit separate positive scales per visit/release. Relative SPLAT
  spectra and surface atmosphere flux are distinguished from observed absolute
  flux. No template error or fitted target temperature is invented.
  Independent colour/template agreement and classification remain unaccepted.
* SkyBoT identifies possible SSOs geocentrically; displayed positions are refined
  with Horizons for the SPHEREx observer at the exact epoch. The widened identification
  cone is finite and is not a complete search for arbitrarily close NEOs. Missing
  refinements are reported. Pluto spectra use exact native-frame midpoint ephemerides.
* Mover integration detects each native-scale band plus the red sum, then returns to
  native pixels. Gaia/CatWISE/SIMBAD matches are propagated to epoch; missing catalogue
  checks veto an unmatched candidate. Real recovery and five-field statistics remain
  unaccepted. Planet X geometry agreement alone is not real-image recovery.
  Daily orphan ambiguities remain separate branches with an explicit budget;
  distance fits require four days, two visits and reduced chi-square <=3, matching
  the existing experimental vetting ceiling. This ceiling is proposed, not accepted
  empirical false-positive calibration. Invalid Planet X views fail before acquisition.

The later light-curve implementation supersedes earlier missing-reference/FAP
notes: per-detector [1,2,1] reference smoothing and first-order shared-reference
covariance feed eigen-whitened GLS and a seeded 1024-trial maximum-over-frequency
Gaussian-null periodogram. Its FAP is conditional on estimated covariance; median
reference selection and temporal/model systematics remain limitations (decision 0005).

The exact outdated claims needing correction are section 15's historical 45-day classifier
(row Time axis; section 4.2 and decision 0002 specify 60 days), section 11.4 step 4's empty-blue WISE
narrative (understanding section 8.4 records the blend), and section 16's missing-M adapter/routes.
No numerical acceptance criterion has been relaxed. Decisions 0001/0002 are narrowly
reviewed for the recorded pins; 0003's proposed systematics and G4a post-hoc statistics
remain rejected for release. See [decision 0004](docs/decisions/0004-measurement-scientific-review.md).

## 18. Revision log (2026-11-09, cross-release difference and spectrum chart — P)

| Area | Was | Now | Why |
|---|---|---|---|
| Difference, mixed releases (§4.6, §5.1) | `cube.diff` raised `mixed photometric scales … apply l3_flux_corrections (F4) first`; every QR2 − QR3 pair failed with HTTP 409 | In-situ photometric match (`cube.fit_relative_scale`): per-λ-bin scale and offset fitted on shared static sources (York errors-in-variables, Tukey IRLS, island bootstrap, empirical-Bayes shrinkage), target masked in both visits, uncertainty propagated into the variance; applied only to mixed-scale pairs; refused when fewer than 5 static sources qualify. Cross-release monopoles are labelled residuals (`sign: null`) | F4 is inconclusive, so the advised correction does not exist; workflow.md §11.2 still holds: positions only across releases. Decision record [0008](docs/decisions/0008-cross-release-difference.md) (I and M to review) |
| `DiffInfo` (§5.1) | `a, b, band, format, k, clip_sigma, annotations, validity, url` | + optional `photometric_match` (scale ± error, per-bin list, sources, static residual before → after, note); the cached diff JSON is rebuilt once when it lacks the field | Additive; the UI states what was matched and what may be read |
| Spectrum chart (§6.5) | Shared `ScatterChart`, fixed 380 px, y-range included every error bar, one median line through all releases | `SpectrumChart`: container width, y-range from the binned values (2–98 % quantiles; error bars clip), Hampel despiking across λ, per-release σ-clipped inverse-variance bins with √χ²ᵣ-inflated errors and error ribbons, detector shading, collision-free feature labels, hover read-out, ×10ⁿ axis title, expand-to-dialog | ±1000 µJy error bars squashed the spectrum into one line; a median through QR2 and QR3 draws a spectrum that exists in neither (§11.2) |

## 19. Revision log (2026-11-10, platform — P: view load time)

Measured from a home connection and from the frame cache, then fixed; numbers and reasoning are in
[decision 0009](docs/decisions/0009-pooled-fetch-and-progressive-stacks.md). Flags, skips and the limit rule are unchanged;
stack values move at the ≈ 1 % sky level through the canonical frame window (last row).

| Area | Was | Now | Why |
|---|---|---|---|
| Fetch default outside AWS (§3.4) | IRSA cutouts, S3 sections as failover | `PooledSource`: IRSA cutouts (≤ 4 in flight) and S3 sections (12 frames) share the queue, earliest expected finish per frame, a failing source rests 60 s and its frames move to the other | Each alone ran ≈ 1.1 frames/s from India (IRSA: request policy; S3: whole-row bandwidth); together their throughputs add |
| Stacking order (§2.3) | Fetch a whole band, then stack all its bins, band by band | One fetch stream; each bin stacks when its last frame arrives; the selected band's stacks (and its cached-frame reads) go first; shared limits rewritten with each stack | First cold image +174 s → +14 s after `planned`; first warm image 13.8 s → 4.75 s |
| Frame cache I/O (§3.7) | Synchronous, on the event loop | 2 dedicated threads; a failed write keeps the frame | ≈ 25 s of blocked loop (and SSE) per 359-frame warm rebuild |
| Pinned "newer data?" check (§5) | Awaited before the job starts (4.5–30 s) | Bounded at 2 s; finishes in the background and fills the coverage cache | Informational only |
| Stacking threads (§9) | 2 when `CPU_WORKERS=0` | `max(2, min(8, cpu − 1))` | numpy, scipy and WCS release the GIL for most of a stack: 8.6 s → 5.0 s at 4 threads |
| Live display limits (§6) | Manifest read at `planned` and `done` only | Re-read while stacks land (≤ 1 per 1.2 s, trailing) | First visits were drawn with placeholder 0–1 limits |
| `FRAMESOURCE=s3` outside us-east-1 | Silent | Startup warning recommending `auto` | Whole-row reads are ≈ 16× the bytes of a cutout on a home link |
| Frame window (§3.4) | Whatever the serving source returned (S3 = IRSA's rule + 1 px) | Every frame cut to IRSA's rule shrunk by 1 px in `fetch_frames` (`access/window.py`) | Stacks depended on the source, ≈ 1 % of the sky level, so mixed or failed-over builds weren't byte-reproducible (G2-repro) |
