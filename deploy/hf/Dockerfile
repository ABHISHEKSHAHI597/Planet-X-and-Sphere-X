# syntax=docker/dockerfile:1
# ParallaX on Hugging Face Spaces (free "CPU basic": 2 vCPU, 16 GB RAM). Guide: docs/DEPLOY_HF.md.
#
# The Space repository holds only this file (as `Dockerfile`) and deploy/hf/README.md (as `README.md`). The build
# clones the code from GitHub, so no binary files have to be pushed to Hugging Face. For a private GitHub repo,
# add a Space secret GITHUB_TOKEN (read-only "Contents" access); for a public repo no secret is needed.
# One container: Caddy on :7860 serves the built frontend and proxies /api to uvicorn on 127.0.0.1:8000.

FROM node:22-slim AS src
ARG REPO=ABHISHEKSHAHI597/Planet-X-and-Sphere-X
ARG BRANCH=main
RUN apt-get update && apt-get install -y --no-install-recommends git ca-certificates && rm -rf /var/lib/apt/lists/*
RUN --mount=type=secret,id=GITHUB_TOKEN,mode=0444 \
    T="$(cat /run/secrets/GITHUB_TOKEN 2>/dev/null || true)"; \
    if [ -n "$T" ]; then URL="https://x-access-token:${T}@github.com/${REPO}.git"; \
    else URL="https://github.com/${REPO}.git"; fi; \
    git clone --depth 1 --branch "$BRANCH" "$URL" /src && rm -rf /src/.git

FROM node:22-slim AS web
COPY --from=src /src/frontend /src/frontend
WORKDIR /src/frontend
RUN npm ci && npm run build

FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv PATH=/opt/venv/bin:$PATH
RUN pip install --no-cache-dir "uv==0.5.11" && useradd --create-home --uid 1000 user
COPY --from=caddy:2.8.4-alpine /usr/bin/caddy /usr/bin/caddy

WORKDIR /app
COPY --from=src /src/backend/pyproject.toml /src/backend/uv.lock backend/
RUN cd backend && uv sync --frozen --no-dev --no-install-project
COPY --from=src --chown=user /src /app
COPY --from=web --chown=user /src/frontend/dist /app/site

# Locked calibration (~430 MB, public SPHEREx bucket, sha256-checked) baked into the image.
ENV PARALLAX_CALIB=/app/calib
RUN cd backend && python ../scripts/bootstrap_calib.py fetch && chown -R user /app/calib

# Defaults; any of them can be overridden under Space → Settings → Variables (docs/DEPLOY_HF.md §4).
ENV ENVIRONMENT=production FRAMESOURCE=auto IN_AWS_US_EAST_1=0 RUN_WATCHER=1 PUBLIC_GALLERY=0 \
    CALIB_ROOT=/app/calib CACHE_DIR=/tmp/parallax-cache CACHE_MAX_GB=30 CPU_WORKERS=2 \
    JOB_TIMEOUT_S=300 MAX_FOV_ARCMIN=30 MAX_FRAMES_PER_VIEW=600 \
    XDG_DATA_HOME=/tmp/caddy XDG_CONFIG_HOME=/tmp/caddy

USER user
EXPOSE 7860
CMD ["bash", "/app/deploy/hf/start.sh"]
