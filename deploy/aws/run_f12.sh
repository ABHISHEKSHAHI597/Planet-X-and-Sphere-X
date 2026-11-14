#!/usr/bin/env bash
# F12 from the deployment region (workflow.md §5 F12: owner D, pair P). Run ON the us-east-1 VM:
#   cd /srv/parallax && ./deploy/aws/run_f12.sh
# Writes validation/F12/<date>-<sha>/ through the harness; then open a PR with the record (reviewer P).
set -euo pipefail
cd "$(dirname "$0")/../.."
TOKEN=$(curl -s -X PUT http://169.254.169.254/latest/api/token -H "X-aws-ec2-metadata-token-ttl-seconds: 60" || true)
AZ=$(curl -s -H "X-aws-ec2-metadata-token: $TOKEN" http://169.254.169.254/latest/meta-data/placement/availability-zone || echo unknown)
TYPE=$(curl -s -H "X-aws-ec2-metadata-token: $TOKEN" http://169.254.169.254/latest/meta-data/instance-type || echo unknown)
case "$AZ" in us-east-1*) ;; *) echo "refusing: not in us-east-1 (AZ=$AZ) — F12 must run from the deployment region"; exit 1;; esac
cd backend
export PARALLAX_ENVIRONMENT="AWS us-east-1 VM ($TYPE, $AZ)"
../.venv-tools/bin/uv run python ../scripts/verify/f12_framesource_bench.py --soak-seconds 600 --concurrency 4 \
  --where "AWS ${AZ} ${TYPE} (deployment VM)"
../.venv-tools/bin/uv run python ../scripts/validate.py status --write
echo "Now: git checkout -b verify/f12-vm && git add ../validation && git commit && git push; reviewer P."
