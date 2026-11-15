#!/usr/bin/env bash
# Hugging Face Space entry point (deploy/hf/Dockerfile): the API on 127.0.0.1:8000 and Caddy on :7860.
# If either process exits, the container exits and the Space restarts it.
set -euo pipefail
mkdir -p "${CACHE_DIR:-/tmp/parallax-cache}" "${XDG_DATA_HOME:-/tmp/caddy}"

cd /app/backend
uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 1 --proxy-headers --forwarded-allow-ips '*' &
caddy run --config /app/deploy/hf/Caddyfile --adapter caddyfile &

wait -n
echo "a process exited; stopping the container" >&2
exit 1
