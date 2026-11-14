# Deploy, release and demo-operations runbook (owner P)

Authority: workflow.md §9.5, §12, §13; implementation.md §9. Files: `backend/Dockerfile`, `deploy/web.Dockerfile`,
`deploy/Caddyfile`, `docker-compose.yml`, `.env.example`, `deploy/offline.env`, `deploy/deploy.sh`,
`deploy/aws/{provision.sh,bootstrap.sh,run_f12.sh}`, `.github/workflows/{ci,nightly,release}.yml`.

## 0. Status (2026-11-07)

| Item | State | Blocked on |
|---|---|---|
| Images, compose, Caddy, CI build/push | written; CI builds on merge to `main` | — |
| Staging VM (us-east-1) | **not created** | a team AWS account with EC2/IAM rights in us-east-1 (owner: P with the team; the account holder runs §1) |
| F12 from the VM | script ready (`deploy/aws/run_f12.sh`) | the VM (D runs it, P reviews) |
| Nightly validation | workflow ready | the VM registered as a self-hosted runner |
| Production, RCs | workflow ready | G2 accepted (RC0), the VM |
| Offline laptops | procedure ready (§6) | an RC and its snapshot |

## 1. Create the VM (one time, ≈15 min, needs the AWS account)

On a machine with AWS CLI v2:

```bash
aws configure                       # access key of an IAM user/role allowed EC2, IAM, SSM in us-east-1
ENV_NAME=staging KEY_NAME=<ec2-key-pair> SSH_CIDR=<your-ip>/32 \
  REPO_URL=https://github.com/ABHISHEKSHAHI597/Nasa-Space-Apps-2026.git BRANCH=main \
  ./deploy/aws/provision.sh
```

This creates a 4 vCPU / 16 GB `m6i.xlarge` (100 GB gp3, IMDSv2 only) with an Elastic IP, a security group
(80/443 public, 22 only from `SSH_CIDR`), and an SSM-enabled instance role. The user-data
(`deploy/aws/bootstrap.sh`) installs Docker, clones the repo, fetches the locked calibration (≈350 MB) into
`/srv/parallax-data/calib`, builds the images and starts the stack. Watch it with
`sudo tail -f /var/log/parallax-bootstrap.log`. Cost ≈ $0.19/h; `aws ec2 stop-instances` when idle.

Then:
1. DNS: an A record for the staging host → the Elastic IP. On the VM set `SITE_ADDRESS=<host>` in
   `/srv/parallax/.env` and `docker compose up -d` (Caddy obtains the certificate).
2. GitHub → Settings → Variables: `STAGING_HOST` = the IP or host, `STAGING_URL` = `https://<host>`;
   Secrets: `DEPLOY_SSH_KEY` (private key of the EC2 key pair). From then on every merge to `main` deploys.
3. Self-hosted runner for nightly validation: GitHub → Settings → Actions → Runners → New (Linux x64), run the
   shown commands on the VM as `ubuntu` with labels `self-hosted,parallax-vm`, install as a service.
4. F12 (D, with P): `cd /srv/parallax && ./deploy/aws/run_f12.sh`, then PR the record (reviewer P).
5. Production: repeat §1 with `ENV_NAME=production`, set `PRODUCTION_HOST`, and create the GitHub environment
   `production` with required reviewers (P plus one of I, M, F).

## 2. Deploy

- **Staging:** automatic on merge to `main` (`ci.yml` → images `main-<sha>` pushed by digest → `deploy/deploy.sh`).
- **By hand on the VM:** `./deploy/deploy.sh <tag>`; it waits for `/healthz` and prints the elapsed time.
- **Health:** `curl https://<host>/healthz` → `ok`, `mode`, probes (SIA2, S3, snapshot, jobs). `/metrics` is
  reachable only from private ranges.

## 3. Release candidates (workflow.md §12.2)

1. `python scripts/check_flags.py` green; nightly on the candidate sha passed; no stale records for enabled flags.
2. Actions → `release` → `rc=RC0`, `sha=<commit>`. It builds and pushes images, writes `release/RC0/release.json`
   (sha, image digests, contract versions, calibration lock, pins, production flags, STATUS digest), tags `RC0`.
3. Pre-warm production: `python scripts/prewarm.py --api https://<prod> --json release/RC0/prewarm.json`.
4. Perf record: `python scripts/perf_probe.py --api https://<prod> --where "us-east-1 VM" --cold-cache-confirmed --record`
   (run right after deploying with an empty cache volume).
5. G6: fill `release/RC0/checklist.yaml` (`pinned_links`, `device_matrix`, `credits`, `rollback`, `prewarm`:
   `{ok, by, evidence}`), then `python scripts/go_no_go.py --rc RC0 --api https://<prod> --answers release/RC0/checklist.yaml`.
   GO → approve the `production` environment in the workflow run.

## 4. Rollback (first response to any production problem)

```bash
ssh ubuntu@<prod> 'cd /srv/parallax && ./deploy/deploy.sh "$(cat .deployed-previous)"'
```

**Drill (required before G6):** deploy RC(n), then roll back to RC(n−1) with the command above and record the
printed elapsed time in `release/<RC>/checklist.yaml` → `rollback`. Target < 5 min (images are already on the
host after the first deploy, so the drill measures `compose up` + health only).

## 5. Snapshot (implementation.md §9)

```bash
# on the VM, after pre-warm (views are complete in the cache volume)
docker compose exec api python /srv/parallax/scripts/make_snapshot.py --cache /cache --out /cache/snapshot-RC1
docker compose cp api:/cache/snapshot-RC1 ./snapshot-RC1 && tar czf snapshot-RC1.tgz snapshot-RC1
sha256sum snapshot-RC1.tgz > snapshot-RC1.tgz.sha256
```
`index.json` lists every packaged view, its pin and a content digest. Only complete views are packaged.

## 6. Offline demo laptops (×2) (workflow.md §12.1, §13)

1. Install Docker Desktop. Copy the repo at the RC tag, `snapshot-RC1.tgz` (+ `.sha256`), and either pull the RC
   images once while online (`IMAGE_TAG=RC1 docker compose pull`) or `docker load` saved images
   (`docker save ghcr.io/<org>/parallax-api:RC1 ghcr.io/<org>/parallax-web:RC1 -o parallax-RC1.tar`).
2. `sha256sum -c snapshot-RC1.tgz.sha256 && tar xzf snapshot-RC1.tgz && mv snapshot-RC1 snapshot`
3. `cp deploy/offline.env .env && docker compose --env-file deploy/offline.env up -d`
4. **Wi-Fi off**, open `http://localhost`, open every pinned link from the README/card; each shows the
   "cached demo data" badge. `curl localhost/healthz` → `mode: snapshot`.
5. Bookmark the pinned links; charge; notifications off (workflow.md §13.4).

## 7. Failure drills (workflow.md §13.5)

| Failure | Detect | Do |
|---|---|---|
| IRSA slow/down | `/healthz` SIA2 probe false, or a pinned link stalls | Pinned views are warm; the API falls back to the snapshot automatically |
| Venue network | pre-flight | Present from an offline laptop (§6) |
| WebGL fails | viewer switches to PNG | Continue (PNG fallback is tested in CI with WebGL disabled) |
| Production down | health check | §4 rollback; present offline meanwhile |
| Laptop fails | — | Second laptop |
| Everything fails | — | Video and slides |

## 8. ParallaX Lite: the frozen static copy (optimisation.md item 0.3; advanced_research.md A1)

The pinned demo views as static files, served by any static host (GitHub Pages, Cloudflare Pages). No server and no
archive: the link keeps working through global judging (December–January) after the VM is stopped. It cannot build
a new patch of sky and says so in a banner, with a link to the live tool when one exists.

```bash
# 1. an API with the demo views built: the VM, or a laptop with OFFLINE=1 SNAPSHOT_DIR=../snapshot
cd backend && uv run python ../scripts/prewarm.py --api http://localhost:8000

# 2. the app, for the host's path ("/<repository>/" on GitHub Pages, "/" on a custom domain)
cd ../frontend && VITE_BASE=/Nasa-Space-Apps-2026/ VITE_LIVE_URL=https://<live host>/ npm run build:lite

# 3. record the views next to it (exit 1 if any view is not built: build it, then run again)
cd ../backend && uv run python ../scripts/make_lite.py --api http://localhost:8000 --out ../frontend/dist-lite/lite --environment staging
```

Run step 3 after step 2: it copies `index.html` to `embed/`, `about/` and `proof/` (so those links answer 200) and to
`404.html` (anything else). Publish `frontend/dist-lite/` (for GitHub Pages: push it to the `gh-pages` branch, or upload it with
`actions/upload-pages-artifact`). Only capabilities a static copy can serve are recorded (`STATIC_CAPABLE` in
`scripts/make_lite.py`), at the chosen environment's flag levels. Check before announcing the link: each mission
opens on a phone in a private window, the browser's network panel shows no `/api` call, and `?gl=0` works.

Rebuild the copy whenever the pins, the frozen targets (`config/pins/targets.json`) or a flag level change.
