# ParallaX | NASA Space Apps Challenge 2026

Seven-slide, 16:9 Beamer deck for the **Planet X and SPHEREx** challenge. The PDF is ready to view offline. Keep the source and `assets/` together when editing.

## Compile

Use **pdfLaTeX** with Beamer, PGF/TikZ, Latin Modern and the standard LaTeX graphics and hyperlink packages. TeX Live 2026 was used for the build. Run these commands from this directory.

```sh
pdflatex -halt-on-error -file-line-error -interaction=nonstopmode -jobname=presentation main.tex
pdflatex -halt-on-error -file-line-error -interaction=nonstopmode -jobname=presentation main.tex
```

The second pass resolves TikZ page positions. Compilation uses local assets and requires no shell escape, network calls or application services.

## Repository and evidence

- Source examined at [`d1ea3789e671d76862a666209d9d237108f59d60`](https://github.com/dakshrathi-india/Planet-X-and-Sphere-X/commit/d1ea3789e671d76862a666209d9d237108f59d60), on `main`. The application source was left untouched.
- Architecture and methodology were checked against `backend/app/{main,pipeline,worker,store}.py`, `backend/spherex/{epochs,preprocess,grid,stack,render}.py`, the React client and WebGL renderer, and `config/{releases,features}.yaml`. The core blink is configured at staging level. Cross-survey blink, wavelength-matched subtraction and spectra were development features at this revision; the release decision of 2026-11-15 (`config/features.yaml`) ships every built capability at `staging`, so slide 5 calls them live and unvalidated.
- Slide 6 cites four records at that commit: the cross-survey position check (`validation/G5.25yr-jumps/2026-11-08-5f9f54b`), the two-route frame census (`validation/F11/2026-11-07-20efbf1`: 359 + 447 + 256 + 333 + 2,483 = 3,878 frames), the pinned-view reproducibility check (`validation/G2-repro/2026-11-10-989bf01`) and the SPHEREx-only motion fit for ε Indi B (`validation/G3-pm-epsindb/2026-11-08-8d12a02`: 0.056″/yr from the catalogue). These are historical team measurements with review or re-run pending. The cross-survey result concerns positions, and the predicted position is used to select the source to centroid. The two SPHEREx stills illustrate the core blink.
- The frontend test suite returned 162 passed and one skipped with `npm test -- --testTimeout 20000`. The standard timeout initially expired in one mock API test. The home screen was captured locally from the unchanged frontend. This check did not repeat the live archive measurements.
- Slide 1 lists the five team members, each linked to their GitHub profile.
- Slide 7's "more than 3,000 brown dwarfs" comes from [NASA, May 2026](https://science.nasa.gov/get-involved/citizen-science/nasa-volunteers-double-known-population-of-brown-dwarfs/) (Backyard Worlds: Planet 9).

## Figures and data

| Asset | Provenance |
| --- | --- |
| `spherex-cover.jpg` | Cropped [SPHEREx first all-sky mosaic, PIA26600](https://www.jpl.nasa.gov/images/pia26600-spherexs-first-all-sky-map/). NASA/JPL-Caltech. |
| `spherex-vela-098.jpg`, `spherex-vela-329.jpg` | Matched false-color views of the Vela region at 0.98 and 3.29 μm. [NASA Science SPHEREx public data article](https://science.nasa.gov/open-science/spherex-universe-map/). NASA/JPL-Caltech. |
| `parallax-home.jpg` | Screenshot of the ParallaX home page at the cited commit. The two-date Pluto panel in the app is a schematic illustration. |
| `barnard-v1.png`, `barnard-v5.png` | First and last frames of the repository's [Barnard's Star blink export](https://github.com/dakshrathi-india/Planet-X-and-Sphere-X/blob/d1ea3789e671d76862a666209d9d237108f59d60/docs/img/barnard-blink.gif), with the original header strip cropped for consistent typography. Underlying images are NASA/IPAC IRSA SPHEREx data. |

The application's primary images come from the [NASA/IPAC Infrared Science Archive SPHEREx mission collection](https://irsa.ipac.caltech.edu/Missions/spherex.html), specifically [QR2](https://doi.org/10.26131/IRSA652) and [QR3](https://doi.org/10.26131/IRSA662). The cross-survey validation uses earlier 2MASS or AllWISE images as reference epochs.

## Submission use

Set `\ToolURL` and `\Repo` at the top of `main.tex`: the live-tool links appear only when `\ToolURL` is set, and judges must be able to open both without signing in. Host the PDF at a publicly accessible URL when adding the demo link to the [NASA Space Apps submission](https://www.spaceappschallenge.org/resources/project-submission-guide/). The repository's submission draft flags pre-event work for a Local Lead decision. The materials reviewed did not include that decision. The last slide records AI assistance with the software and deck.
