# Railway service config: build context = repo root (not services/platform-api/).
# So all COPY paths in this Dockerfile are repo-root-relative.

# ─────────────── Stage 1: build win-web (智通客户) UI ───────────────
# apps/win-web/ is the /win/ SPA, built and shipped alongside
# the platform service.
FROM node:20-alpine AS win-web-build
WORKDIR /build/win-web

# package*.json first for layer cache: re-run npm ci only when deps change.
COPY apps/win-web/package.json apps/win-web/package-lock.json ./
RUN npm ci

COPY apps/win-web/ ./
RUN npm run build && ls -la dist/ && ls -la dist/assets/ | head -10

# ─────────────── Stage 2: python runtime ───────────────
FROM python:3.13-slim
WORKDIR /app

# Hatchling needs the package present to compute metadata, so copy
# pyproject + platform_app + yunwei_win together before pip install.
COPY services/platform-api/pyproject.toml /app/
COPY services/platform-api/platform_app /app/platform_app/
COPY services/platform-api/yunwei_win /app/yunwei_win/
RUN pip install --no-cache-dir .

COPY services/platform-api/migrations /app/migrations/
COPY services/platform-api/static /app/static/
# yunwei_win reads its LLM prompts via Path(__file__).parents[N] / "prompts"
# which resolves to /app/prompts in the container. Without this the
# /win/api/ingest/* endpoints raise 422 "draft failed: [Errno 2] No such file…".
COPY services/platform-api/prompts /app/prompts/

# Built win-web UI from stage 1 → /app/win-web/dist.
# main.py: _WIN_DIST resolves to:
#  - container:  /app/platform_app/main.py → /app → /app/win-web/dist  ✅
#  - local dev:  <repo>/services/platform-api/platform_app/main.py →
#                <repo>/apps/win-web/dist  ✅
COPY --from=win-web-build /build/win-web/dist /app/win-web/dist

# Railway sets $PORT (typically 8080). Local docker-compose sets it via
# the `command:` override. Default to 80 so plain `docker run` also works.
EXPOSE 80
CMD ["sh", "-c", "uvicorn platform_app.main:app --host 0.0.0.0 --port ${PORT:-80} --workers 1"]

# ─────────────── Worker service ───────────────
# This image is also used by the win-ingest RQ worker (a separate Railway
# service that shares the same code and provider env). Override the start
# command in the worker service settings:
#
#     Start Command: yunwei-win-ingest-worker
#
# The web and worker services MUST share:
#  - DATABASE_URL  — same Postgres
#  - REDIS_URL     — same Redis (the queue is `win-ingest`)
#  - STORAGE_BACKEND=s3 plus S3_* — staged uploads must be readable by both
#  - OCR_PROVIDER / EXTRACTOR_PROVIDER
#  - MISTRAL_API_KEY / VISION_AGENT_API_KEY / ANTHROPIC_API_KEY / model_*
#
# See infra/railway/platform-api.md for the full Railway variable template and
# docs/superpowers/runbooks/win-ingest-rq-worker.md for the operational
# rollout checklist.
