# API image (implementation.md §9; owner P). Build from the REPO ROOT so config/ and the contract fixtures ship
# with the code (the app resolves them relative to the repo layout):
#   docker build -f backend/Dockerfile -t parallax-api .
# One uvicorn worker: the job registry is in memory; CPU work runs in the API's process pool (CPU_WORKERS).
FROM python:3.12-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv PATH=/opt/venv/bin:$PATH
RUN pip install --no-cache-dir "uv==0.5.11"
WORKDIR /srv/parallax/backend
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PATH=/opt/venv/bin:$PATH \
    CACHE_DIR=/cache SNAPSHOT_DIR= CALIB_ROOT= CPU_WORKERS=2
RUN useradd --create-home --uid 10001 parallax && mkdir -p /cache /snapshot /calib && chown -R parallax /cache
COPY --from=base /opt/venv /opt/venv
WORKDIR /srv/parallax
COPY backend/app backend/app
COPY backend/spherex backend/spherex
COPY backend/pyproject.toml backend/
COPY config config
COPY frontend/fixtures/colormaps.json frontend/fixtures/colormaps.json
COPY frontend/fixtures/golden frontend/fixtures/golden
COPY scripts/bootstrap_calib.py scripts/prewarm.py scripts/make_snapshot.py scripts/
ARG GIT_SHA=unknown
ENV GIT_SHA=$GIT_SHA
USER parallax
WORKDIR /srv/parallax/backend
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=8).status == 200 else 1)"
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--proxy-headers", \
     "--forwarded-allow-ips", "*"]
