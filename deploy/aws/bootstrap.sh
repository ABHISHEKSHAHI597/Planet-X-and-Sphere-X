#!/usr/bin/env bash
# EC2 user-data / manual bootstrap for the ParallaX VM (Ubuntu 24.04, us-east-1). Owner P.
# provision.sh substitutes __REPO_URL__, __BRANCH__, __ENV_NAME__. Safe to re-run by hand:
#   sudo REPO_URL=... BRANCH=main ENV_NAME=staging bash deploy/aws/bootstrap.sh
set -euxo pipefail
exec > >(tee -a /var/log/parallax-bootstrap.log) 2>&1
REPO_URL=${REPO_URL:-__REPO_URL__}
BRANCH=${BRANCH:-__BRANCH__}
ENV_NAME=${ENV_NAME:-__ENV_NAME__}

export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y ca-certificates curl git python3-venv python3-pip unattended-upgrades
if ! command -v docker >/dev/null; then
  curl -fsSL https://get.docker.com | sh
fi
usermod -aG docker ubuntu || true
systemctl enable --now docker

mkdir -p /srv/parallax-data/{calib,snapshot} /srv/parallax
if [ ! -d /srv/parallax/.git ]; then
  git clone --branch "$BRANCH" "$REPO_URL" /srv/parallax
fi
cd /srv/parallax
git fetch --all --tags && git checkout "$BRANCH" && git pull --ff-only || true
if [ ! -f .env ]; then
  cp .env.example .env
  sed -i "s/^ENVIRONMENT=.*/ENVIRONMENT=${ENV_NAME}/" .env
  sed -i "s/^SITE_ADDRESS=.*/SITE_ADDRESS=:80/" .env
fi
chown -R ubuntu:ubuntu /srv/parallax /srv/parallax-data

# Calibration (≈350 MB, implementation.md §9) — public bucket, no credentials needed.
sudo -u ubuntu bash -lc 'cd /srv/parallax && python3 -m venv .venv-tools && .venv-tools/bin/pip install -q uv && \
  cd backend && ../.venv-tools/bin/uv sync --frozen --no-dev && \
  PARALLAX_CALIB=/srv/parallax-data/calib ../.venv-tools/bin/uv run python ../scripts/bootstrap_calib.py fetch || true'

# Build locally on first boot (CI pushes images later; docs/deploy.md "Deploy from CI").
sudo -u ubuntu bash -lc 'cd /srv/parallax && GIT_SHA=$(git rev-parse --short HEAD) docker compose build && docker compose up -d'

# Daily cache hygiene: keep the 100 GB SSD below 85 %.
cat >/etc/cron.daily/parallax-cache <<'CRON'
#!/bin/sh
USE=$(df --output=pcent / | tail -1 | tr -dc 0-9)
if [ "$USE" -gt 85 ]; then
  docker run --rm -v parallax_cache:/cache alpine sh -c 'find /cache/frames -type f -atime +7 -delete' || true
fi
CRON
chmod +x /etc/cron.daily/parallax-cache
echo "bootstrap complete: $(date -u)"
