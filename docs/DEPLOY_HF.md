# Deploy ParallaX on Hugging Face Spaces (free, no card, no watermark)

This works like Netlify: you create a "Space", it builds the site by itself, and you get a live HTTPS link:

**`https://<your-hf-username>-parallax.hf.space`**

That link shows only your site, with no Hugging Face bar or watermark.

| Free plan ("CPU basic") | |
|---|---|
| Cost / card | ₹0, **no card**, just an email |
| Hardware | 2 CPU cores, 16 GB RAM, ~50 GB disk |
| HTTPS | automatic |
| Sleeps | after **48 hours with no visitors**. The next visit wakes it in about a minute |
| Disk | wiped on every restart (the frame cache starts empty, and the calibration is part of the image so it is not lost) |

Why not Netlify or Vercel themselves? They host only static frontends. ParallaX also needs its Python backend
(numpy/astropy image processing), and a Space runs both in one container.

The files used for this are in `deploy/hf/`:

| File | What it is |
|---|---|
| `deploy/hf/Dockerfile` | Goes into the Space as `Dockerfile`. It downloads the code from GitHub, builds the frontend, installs the backend, and downloads the ~430 MB calibration. |
| `deploy/hf/README.md` | Goes into the Space as `README.md`. Its top block tells Hugging Face "this is a Docker app on port 7860". |
| `deploy/hf/start.sh`, `deploy/hf/Caddyfile` | Used from the GitHub copy. They start the backend and the Caddy web server together. |

---

## Step 1: Get the code on GitHub

1. These `deploy/hf/` files must be in the GitHub repo's `main` branch (commit and push them).
2. **Make the repo public:** GitHub → the repo → **Settings → General** → scroll to **Danger Zone** →
   **Change visibility → Make public**.
   (If you want to keep it private, see "Private repo" in step 4.)

## Step 2: Make a Hugging Face account

Go to <https://huggingface.co/join>, sign up with your email, and confirm the email. No card needed.

## Step 3: Create the Space

1. Go to <https://huggingface.co/new-space>.
2. Fill in:

   | Field | Choose |
   |---|---|
   | Space name | `parallax` |
   | License | `mit` (or whatever the repo's `LICENSE` is) |
   | Select the Space SDK | **Docker** → template **Blank** |
   | Space hardware | **CPU basic · 2 vCPU · 16 GB · FREE** |
   | Visibility | **Public** (private Spaces can only be opened by you) |

3. Click **Create Space**.

## Step 4: Add the two files

In your new Space, open the **Files** tab.

**A. `Dockerfile`:** click **+ Add file → Create a new file**. Name it exactly `Dockerfile` (capital D, no
extension). Paste the whole contents of `deploy/hf/Dockerfile` from this repo, then click **Commit new file to main**.

**B. `README.md`:** click the existing `README.md` → **edit** (pencil icon). Replace everything with the contents of
`deploy/hf/README.md`, then **Commit changes to main**.

> If your GitHub username or repo name is different, change the line `ARG REPO=ABHISHEKSHAHI597/Planet-X-and-Sphere-X`
> in the Dockerfile. To build another branch, change `ARG BRANCH=main`.

**Private repo (only if you didn't make it public):**
1. On GitHub: **Settings (your profile) → Developer settings → Personal access tokens → Fine-grained tokens →
   Generate new token**. Repository access: *Only select repositories* → this repo. Permissions:
   **Contents → Read-only**. Copy the token.
2. In the Space: **Settings → Variables and secrets → New secret**. Name: `GITHUB_TOKEN`, Value: the token.

## Step 5: Wait for the build

Committing starts the build automatically. Watch it in the **Logs** tab (top right, next to "Building").
The first build takes **10–20 minutes**: it installs Node and Python packages and downloads the calibration.
When it says **Running**, the site is live.

## Step 6: Open your live link

- Direct link (no Hugging Face frame): **`https://<your-hf-username>-parallax.hf.space`**
  (also under **⋮ menu → Embed this Space → Direct URL**)
- Health check: `https://<your-hf-username>-parallax.hf.space/healthz` should say `ok` and show
  `"calibration": "locked …"`.

The first star you open is slower, because its SPHEREx frames are downloaded from NASA. After that they're cached
(until the Space restarts).

---

## Environment variables

**You don't need to set any.** The Dockerfile already sets good defaults. There are no API keys: every data source
ParallaX uses is public.

To change one: Space → **Settings → Variables and secrets → New variable**, then click **Restart Space**.

| Variable | Default in the Space | What it does |
|---|---|---|
| `ENVIRONMENT` | `production` | Which features are shown. `production` shows every released feature. |
| `FRAMESOURCE` | `auto` | Where SPHEREx images come from. `auto` picks the best route. Others: `s3`, `irsa`. |
| `IN_AWS_US_EAST_1` | `0` | `1` only on a server inside AWS us-east-1. Keep `0`. |
| `RUN_WATCHER` | `1` | Checks every hour for new SPHEREx data releases. |
| `PUBLIC_GALLERY` | `0` | `1` shows visitor-submitted Planet X candidates publicly. Keep `0` unless someone checks them. |
| `CALIB_ROOT` | `/app/calib` | Where the calibration is inside the image. Don't change it. |
| `CACHE_DIR` | `/tmp/parallax-cache` | Where downloaded frames and built views are stored. |
| `CACHE_MAX_GB` | `30` | Disk limit for that cache. Oldest files are deleted past it. |
| `CPU_WORKERS` | `2` | Parallel image-processing workers. The free Space has 2 cores. |
| `JOB_TIMEOUT_S` | `300` | Seconds before a view-building job is stopped. |
| `MAX_FOV_ARCMIN` | `30` | Largest patch of sky (arcminutes) a visitor can request. |
| `MAX_FRAMES_PER_VIEW` | `600` | Most frames used in one view. |
| `JOBS_PER_MINUTE_PER_IP` | `6` (built-in) | New views one visitor can start per minute. |
| `LOOKUPS_PER_MINUTE_PER_IP` | `60` (built-in) | Name lookups, coverage and overlays per visitor per minute. |
| `MEASUREMENTS_PER_MINUTE_PER_IP` | `20` (built-in) | Spectra, astrometry, light curves and exports per visitor per minute. |
| `CANDIDATES_PER_HOUR_PER_IP` | `10` (built-in) | Candidate reports one visitor can submit per hour. |

**Secret** (only for a private GitHub repo):

| Secret | Put in it |
|---|---|
| `GITHUB_TOKEN` | A GitHub fine-grained token with **Contents: Read-only** on this repo. It is used only while the image is built. |

---

## Updating the site

The Space doesn't watch GitHub. After you push new code to GitHub `main`:
Space → **Settings → Factory rebuild**. It rebuilds from the latest GitHub code (10–20 minutes).

## Problems

| Symptom | Fix |
|---|---|
| Build log: `could not read Username` / `Repository not found` | The repo is private and there is no `GITHUB_TOKEN` secret, or the token can't read this repo. Or `ARG REPO` is wrong. |
| Build log: `bash: /app/deploy/hf/start.sh: No such file` | The `deploy/hf/` files aren't on GitHub `main` yet. Push them, then Factory rebuild. |
| Space shows **Runtime error** | Open **Logs**. Click **Restart Space**. If it says a calibration file failed its check, Factory rebuild. |
| "archive service not answering" | NASA's IRSA archive is down. Wait; nothing to fix on your side. |
| Site is slow to open after a few days | It was asleep (no visitors for 48 h). It wakes in about a minute. |
