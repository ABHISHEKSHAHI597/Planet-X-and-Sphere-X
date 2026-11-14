# Web image: the built frontend served by Caddy, which also reverse-proxies /api, /healthz, /metrics to the API
# (implementation.md §9; owner P). Build from the repo root:
#   docker build -f deploy/web.Dockerfile -t parallax-web .
FROM node:22-alpine AS build
WORKDIR /src/frontend
COPY frontend/package.json frontend/package-lock.json* ./
RUN if [ -f package-lock.json ]; then npm ci; else npm install; fi
COPY frontend/ ./
RUN npm run build

FROM caddy:2.8.4-alpine
COPY --from=build /src/frontend/dist /srv
COPY deploy/Caddyfile /etc/caddy/Caddyfile
