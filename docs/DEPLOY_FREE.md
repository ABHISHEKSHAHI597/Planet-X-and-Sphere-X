# Deploy ParallaX for free and get a live link

This guide puts the full ParallaX site (frontend and backend) on the internet with HTTPS, for **₹0 / $0 per month**.

---

## 1. Which free host, and why

ParallaX is not a simple static website. It has:

- a **Python backend** (FastAPI + numpy/astropy) that does heavy image processing,
- a **~430 MB calibration** download it needs for spectra, astrometry and light curves,
- a **disk cache** of SPHEREx frames that can grow to many GB,
- jobs that can run for **several minutes**.

Most "free" hosts (Render, Railway, Vercel, Netlify, Fly.io free tiers) give 256–512 MB of RAM, sleep when idle, cut
requests after 30–100 seconds, or have no permanent disk. ParallaX does not run properly on them.

**Recommended: Oracle Cloud "Always Free" ARM server.**

| What you get for free, forever | ParallaX needs |
|---|---|
| 4 CPU cores (Ampere ARM) | 2–4 cores |
| 24 GB RAM | 4–16 GB |
| up to 200 GB disk | ~50–100 GB |
| a public IP address | yes |
| no sleeping, no time limits | yes |

The repo already has everything needed to run there: `docker-compose.yml` starts the backend (`api`) and a Caddy web
server (`web`) that serves the frontend, forwards `/api` to the backend, and gets an HTTPS certificate by itself.
All the Python packages have ARM builds, so nothing in the code needs to change.

> Oracle asks for a credit/debit card to verify you are a real person. You are **not charged** as long as you only
> use "Always Free" resources (this guide uses only those).

**Backup option, no card needed:** "ParallaX Lite" on GitHub Pages, a frozen copy that only shows the pre-built demo
views (see [section 6](#6-backup-option-parallax-lite-on-github-pages-no-card-no-server)).

---

## 2. Create the free server (Oracle Cloud)

### 2.1 Make an account

1. Go to <https://www.oracle.com/cloud/free/> and click **Start for free**.
2. Fill in the form and verify your card.
3. **Home region**: pick one close to you (for example *India West (Mumbai)* or *India South (Hyderabad)*).
   You cannot change it later, and free ARM servers can only be made in your home region.

### 2.2 Make an SSH key on your own computer (if you don't have one)

```bash
ssh-keygen -t ed25519 -f ~/.ssh/oracle_parallax
# press Enter twice (no passphrase is fine)
cat ~/.ssh/oracle_parallax.pub     # you will paste this text into Oracle
```

### 2.3 Create the virtual machine

In the Oracle Cloud console: **☰ menu → Compute → Instances → Create instance**.

| Setting | Choose |
|---|---|
| Name | `parallax` |
| Image | **Canonical Ubuntu 24.04** (click *Change image*) |
| Shape | *Change shape* → **Ampere** → `VM.Standard.A1.Flex` → **4 OCPUs, 24 GB memory** (shows "Always Free-eligible") |
| Networking | keep the default new VCN and public subnet; **Assign a public IPv4 address: Yes** |
| SSH keys | **Paste public keys** → paste the text from `oracle_parallax.pub` |
| Boot volume | tick *Specify a custom boot volume size* → **100 GB** (up to 200 GB is free) |

Click **Create**. After 1–2 minutes the instance is *Running*. Copy its **Public IP address** (e.g. `140.238.12.34`).

> **"Out of capacity" error?** Free ARM servers are popular. Try another *Availability Domain* in the same screen,
> try again a few hours later, or try 2 OCPU / 12 GB (also enough). Upgrading the account to *Pay As You Go* usually
> removes the error and Always Free resources stay free.

### 2.4 Open the website ports (80 and 443)

Oracle blocks web traffic in **two** places. You must open both.

**A. In the Oracle console:** open the instance → click the **Subnet** link → click the **Default Security List** →
**Add Ingress Rules**, and add two rules:

| Source CIDR | IP Protocol | Destination Port Range |
|---|---|---|
| `0.0.0.0/0` | TCP | `80` |
| `0.0.0.0/0` | TCP | `443` |

**B. Inside the server** (next step, after you log in):

```bash
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 80 -j ACCEPT
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 443 -j ACCEPT
sudo netfilter-persistent save
```

---

## 3. Install ParallaX on the server

### 3.1 Log in

From your own computer:

```bash
ssh -i ~/.ssh/oracle_parallax ubuntu@<PUBLIC_IP>
```

Now run the iptables commands from step 2.4 B.

### 3.2 Install Docker and tools

```bash
sudo apt-get update && sudo apt-get install -y git curl python3-venv
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker ubuntu
exit          # log out and back in so the docker group applies
```

```bash
ssh -i ~/.ssh/oracle_parallax ubuntu@<PUBLIC_IP>
docker run --rm hello-world      # should print "Hello from Docker!"
```

### 3.3 Download the code

```bash
sudo mkdir -p /srv/parallax /srv/parallax-data/calib /srv/parallax-data/snapshot
sudo chown -R ubuntu:ubuntu /srv/parallax /srv/parallax-data
git clone https://github.com/ABHISHEKSHAHI597/Planet-X-and-Sphere-X.git /srv/parallax
cd /srv/parallax
```

### 3.4 Download the calibration (~430 MB, one time)

Without it the blink still works, but spectra, astrometry, light curves, differences, cubes and the flipbook answer
"409 needs the locked calibration". It comes from NASA's public bucket, no password needed.

```bash
cd /srv/parallax
python3 -m venv .venv-tools && .venv-tools/bin/pip install -q uv
cd backend && ../.venv-tools/bin/uv sync --frozen --no-dev
PARALLAX_CALIB=/srv/parallax-data/calib ../.venv-tools/bin/uv run python ../scripts/bootstrap_calib.py fetch
cd ..
```

It checks every file against `config/calibration.lock`. Takes 2–10 minutes.

### 3.5 Pick your web address (free)

You need a host name so Caddy can get a free HTTPS certificate. Two free choices:

- **Easiest, no sign-up — sslip.io:** take your IP, replace dots with dashes, add `.sslip.io`.
  IP `140.238.12.34` → **`140-238-12-34.sslip.io`**. It already points to your server.
- **Nicer name — DuckDNS:** log in at <https://www.duckdns.org>, create a subdomain (e.g. `parallax-x`), and set its IP
  to your server's IP. Your address is **`parallax-x.duckdns.org`**.

### 3.6 Create the `.env` file (all the settings)

```bash
cd /srv/parallax
nano .env
```

Paste this, change the `SITE_ADDRESS` line to your address from 3.5, then save (`Ctrl+O`, `Enter`, `Ctrl+X`):

```dotenv
# ---------- web address ----------
SITE_ADDRESS=140-238-12-34.sslip.io

# ---------- what kind of server this is ----------
ENVIRONMENT=production
FRAMESOURCE=auto
IN_AWS_US_EAST_1=0
RUN_WATCHER=1
PUBLIC_GALLERY=0

# ---------- calibration and cache folders ----------
CALIB_ROOT_IN_CONTAINER=/calib
CALIB_HOST_DIR=/srv/parallax-data/calib
SNAPSHOT_HOST_DIR=/srv/parallax-data/snapshot
SNAPSHOT_DIR=
CACHE_MAX_GB=40

# ---------- compute limits ----------
CPU_WORKERS=3
JOB_TIMEOUT_S=300
MAX_FOV_ARCMIN=30
MAX_FRAMES_PER_VIEW=600

# ---------- rate limits (per visitor IP) ----------
JOBS_PER_MINUTE_PER_IP=6
LOOKUPS_PER_MINUTE_PER_IP=60
MEASUREMENTS_PER_MINUTE_PER_IP=20
CANDIDATES_PER_HOUR_PER_IP=10

# ---------- docker image names (we build on the server) ----------
REGISTRY=parallax
IMAGE_TAG=local
```

Do **not** copy `.env.example` as it is: it has `REGISTRY=ghcr.io/<org>`, which is not a valid image name, and
`IN_AWS_US_EAST_1=1`, which is wrong outside AWS.

### 3.7 Build and start

```bash
cd /srv/parallax
GIT_SHA=$(git rev-parse --short HEAD) docker compose build     # first time: 5–15 minutes
docker compose up -d
docker compose ps                                               # api and web should be "running"/"healthy"
```

### 3.8 Open your live link 🎉

- Site: **`https://<your SITE_ADDRESS>`** (e.g. `https://140-238-12-34.sslip.io`)
- Health check: `https://<your SITE_ADDRESS>/healthz` should show `ok` and a line like
  `"calibration": "locked 94e18b883fdc9b28 at …"`.

The first HTTPS visit can take ~30 seconds while Caddy gets the certificate.

---

## 4. Every environment variable, explained

All of these go in `/srv/parallax/.env`. Docker Compose reads the file for two things: to fill in
`docker-compose.yml`, and to pass the settings into the backend container. Source of truth:
`backend/app/settings.py`. **There are no secrets or API keys**: every archive ParallaX uses is public.

### 4.1 Used by `docker-compose.yml` (server setup)

| Variable | Put in it | What it does |
|---|---|---|
| `SITE_ADDRESS` | your host name, e.g. `140-238-12-34.sslip.io` or `parallax-x.duckdns.org`. No `https://`, no `/`. | Caddy serves the site at this name and gets the HTTPS certificate for it. `:80` = plain HTTP with no certificate (testing only). |
| `CALIB_HOST_DIR` | `/srv/parallax-data/calib` | Folder **on the server** where step 3.4 put the calibration. Mounted read-only into the backend. |
| `CALIB_ROOT_IN_CONTAINER` | `/calib` | Where that folder appears **inside** the backend container. Compose turns it into `CALIB_ROOT`. Leave empty to run without calibration. |
| `SNAPSHOT_HOST_DIR` | `/srv/parallax-data/snapshot` | Folder on the server for an optional pre-built snapshot. May be empty. |
| `REGISTRY` | `parallax` | First part of the Docker image names. Any simple lowercase word works when you build on the server. |
| `IMAGE_TAG` | `local` | Second part of the image names (the tag). |
| `GIT_SHA` | (set on the command line, see 3.7) | The commit shown by `/healthz`. Optional. |

### 4.2 Used by the backend (the app itself)

| Variable | Put in it | What it does |
|---|---|---|
| `ENVIRONMENT` | `production` | Which features are shown. `production` shows every released feature. Other values: `staging`, `local`, `snapshot`, `mock`. |
| `FRAMESOURCE` | `auto` | Where SPHEREx images are downloaded from. `auto` picks the best route by itself. Others: `s3`, `irsa`, `fixture` (test files only). |
| `IN_AWS_US_EAST_1` | `0` | `1` only when the server is in AWS us-east-1, next to NASA's bucket. Oracle is not, so `0`. |
| `RUN_WATCHER` | `1` | Checks every hour for new SPHEREx data releases. |
| `PUBLIC_GALLERY` | `0` | `1` shows the public gallery of Planet X candidates that visitors submit. Keep `0` unless someone checks submissions. |
| `CACHE_DIR` | *(don't set)* | Already set to `/cache` (a Docker volume) by the compose file. |
| `CACHE_MAX_GB` | `40` (with a 100 GB disk) | Size limit for downloaded frames and built views. Oldest are deleted past it. `0` = no limit (the disk can fill up). |
| `SNAPSHOT_DIR` | *(empty)* | A folder of pre-built views to fall back on if NASA's archive is down. Empty = no fallback. Set to `/snapshot` only after you put a snapshot in `SNAPSHOT_HOST_DIR` (see `docs/deploy.md` §5). |
| `OFFLINE` | *(don't set)* | `1` = no internet at all, serve the snapshot only. For demo laptops. |
| `MOCK` | *(don't set)* | `1` = fake test data. Never on a real site. |
| `CPU_WORKERS` | `3` (for 4 cores) | Number of parallel image-processing workers. Use cores − 1. |
| `JOB_TIMEOUT_S` | `300` | Seconds before a view-building job is stopped. |
| `MAX_FOV_ARCMIN` | `30` | Largest patch of sky (arcminutes) a visitor can ask for. |
| `MAX_FRAMES_PER_VIEW` | `600` | Most frames used in one view. |
| `JOBS_PER_MINUTE_PER_IP` | `6` | New views one visitor can start per minute. |
| `LOOKUPS_PER_MINUTE_PER_IP` | `60` | Name lookups, coverage and overlays per visitor per minute. |
| `MEASUREMENTS_PER_MINUTE_PER_IP` | `20` | Spectra, astrometry, light curves and exports per visitor per minute. |
| `CANDIDATES_PER_HOUR_PER_IP` | `10` | Candidate reports one visitor can submit per hour. |

### 4.3 Frontend build variables

For this setup you set **none**. The frontend is built inside Docker and served at the root of your domain.
They only matter for the Lite copy in section 6:

| Variable | Put in it | What it does |
|---|---|---|
| `VITE_BASE` | `/Planet-X-and-Sphere-X/` | The sub-path when hosted on GitHub Pages (`/<repo name>/`). |
| `VITE_LIVE_URL` | `https://<your SITE_ADDRESS>/` | Link from the Lite copy to the live tool. Optional. |

---

## 5. Day-to-day

**Update the site after you push new code to GitHub:**

```bash
ssh -i ~/.ssh/oracle_parallax ubuntu@<PUBLIC_IP>
cd /srv/parallax && git pull
GIT_SHA=$(git rev-parse --short HEAD) docker compose build && docker compose up -d
```

**See logs:** `docker compose logs -f api` (backend) or `docker compose logs -f web` (Caddy / HTTPS).

**Restart:** `docker compose restart`. The server also restarts the containers by itself after a reboot.

**Optional: pre-load demo stars** so they open instantly:

```bash
cd /srv/parallax/backend && ../.venv-tools/bin/uv run python ../scripts/prewarm.py --api https://<your SITE_ADDRESS>
```

**Problems**

| Symptom | Fix |
|---|---|
| Browser can't connect at all | Ports not open. Re-check **both** parts of step 2.4. |
| Certificate error / HTTPS fails | `SITE_ADDRESS` must point to this server's IP and ports 80 + 443 must be open. See `docker compose logs web`. |
| Spectra etc. say "needs the locked calibration" | Step 3.4 didn't finish, or `CALIB_HOST_DIR` is wrong. Re-run 3.4, then `docker compose up -d`. |
| "archive service not answering" | NASA's IRSA archive is down. Wait; nothing to fix on your side. |
| Disk full | Lower `CACHE_MAX_GB`, then `docker compose up -d`. |
| Oracle emails "idle instance will be reclaimed" | Oracle may reclaim Always Free servers that stay almost idle for 7 days. Normal visitor traffic or the hourly watcher is usually enough; upgrading to Pay As You Go stops reclaiming. |

> The CI job `build-deploy` in `.github/workflows/ci.yml` builds x86 images and deploys over SSH to an AWS server.
> You don't need it for this setup. It prints a warning and skips the deploy while `STAGING_HOST` is not set.

---

## 6. Backup option: ParallaX Lite on GitHub Pages (no card, no server)

A frozen, read-only copy: only the pre-built demo views, no new sky patches, no live archive. Good as a link that
never goes down. You need a running backend **once** (your laptop works) to record the views:

```bash
# 1. backend on your laptop (with the calibration from the README quick start)
cd backend && uv run uvicorn app.main:app &
uv run python ../scripts/prewarm.py --api http://localhost:8000

# 2. build the Lite frontend for GitHub Pages
cd ../frontend && npm ci
VITE_BASE=/Planet-X-and-Sphere-X/ VITE_LIVE_URL=https://<your SITE_ADDRESS>/ npm run build:lite

# 3. record the demo views into it
cd ../backend && uv run python ../scripts/make_lite.py --api http://localhost:8000 \
  --out ../frontend/dist-lite/lite --environment production
```

Then publish the folder `frontend/dist-lite/` to a `gh-pages` branch (for example `npx gh-pages -d frontend/dist-lite`
from the repo root), and in GitHub → **Settings → Pages** choose *Deploy from a branch* → `gh-pages`.
The link is **`https://abhishekshahi597.github.io/Planet-X-and-Sphere-X/`**. Full details: `docs/deploy.md` §8.
