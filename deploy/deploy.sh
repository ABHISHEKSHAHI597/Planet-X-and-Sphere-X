#!/usr/bin/env bash
# Deploy or roll back on the VM (workflow.md §12.2 "Rollback is redeploying the previous RC tag"; owner P).
#   ./deploy/deploy.sh <image-tag>        e.g. main-3f2a1c0, RC0, RC1
# Pulls both images by tag, restarts, waits for /healthz, prints the time taken. Exit 1 if unhealthy in 120 s
# (then re-run with the previous tag). The previous tag is kept in .deployed-previous for one-command rollback:
#   ./deploy/deploy.sh "$(cat .deployed-previous)"
set -euo pipefail
cd "$(dirname "$0")/.."
TAG=${1:?usage: deploy.sh <image-tag>}
T0=$(date +%s)
[ -f .deployed ] && cp .deployed .deployed-previous
IMAGE_TAG="$TAG" docker compose pull
IMAGE_TAG="$TAG" docker compose up -d --remove-orphans
for i in $(seq 1 60); do
  if curl -fsS http://127.0.0.1/healthz >/dev/null 2>&1; then
    echo "$TAG" > .deployed
    echo "deployed $TAG, healthy after $(( $(date +%s) - T0 )) s"
    exit 0
  fi
  sleep 2
done
echo "UNHEALTHY after $(( $(date +%s) - T0 )) s — roll back: ./deploy/deploy.sh $(cat .deployed-previous 2>/dev/null || echo '<previous tag>')"
exit 1
