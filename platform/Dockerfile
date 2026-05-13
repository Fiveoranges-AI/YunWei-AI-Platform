# Railway service config: build context = repo root (not platform/).
# So all COPY paths in this Dockerfile are repo-root-relative.

# ─────────────── Stage 1: build yunwei-win-web (智通客户) UI ───────────────
# apps/yunwei-win-web/ is the /win/ SPA, built and shipped alongside
# the platform service.
FROM node:20-alpine AS yunwei-win-web-build
WORKDIR /build/yunwei-win-web

# package*.json first for layer cache: re-run npm ci only when deps change.
COPY apps/yunwei-win-web/package.json apps/yunwei-win-web/package-lock.json ./
RUN npm ci

COPY apps/yunwei-win-web/ ./
RUN npm run build && ls -la dist/ && ls -la dist/assets/ | head -10

# ─────────────── Stage 2: python runtime ───────────────
FROM python:3.13-slim
WORKDIR /app

# Hatchling needs the package present to compute metadata, so copy
# pyproject + platform_app + yunwei_win together before pip install.
COPY platform/pyproject.toml /app/
COPY platform/platform_app /app/platform_app/
COPY platform/yunwei_win /app/yunwei_win/
RUN pip install --no-cache-dir .

COPY platform/migrations /app/migrations/
COPY platform/static /app/static/
# yunwei_win reads its LLM prompts via Path(__file__).parents[N] / "prompts"
# which resolves to /app/prompts in the container. Without this the
# /win/api/ingest/* endpoints raise 422 "draft failed: [Errno 2] No such file…".
COPY platform/prompts /app/prompts/

# Built yunwei-win-web UI from stage 1 → /app/yunwei-win-web/dist.
# main.py: _WIN_DIST resolves to:
#  - container:  /app/platform_app/main.py → /app → /app/yunwei-win-web/dist  ✅
#  - local dev:  <repo>/platform/platform_app/main.py →
#                <repo>/apps/yunwei-win-web/dist  ✅
COPY --from=yunwei-win-web-build /build/yunwei-win-web/dist /app/yunwei-win-web/dist

# Railway sets $PORT (typically 8080). Local docker-compose sets it via
# the `command:` override. Default to 80 so plain `docker run` also works.
EXPOSE 80
CMD ["sh", "-c", "uvicorn platform_app.main:app --host 0.0.0.0 --port ${PORT:-80} --workers 1"]

# ─────────────── Worker service ───────────────
# This image is also used by the win-ingest RQ worker (a separate Railway
# service that shares the same code + env). Override the start command in
# the worker service settings:
#
#     Start Command: yunwei-win-ingest-worker
#
# The web and worker services MUST share:
#  - DATABASE_URL  — same Postgres
#  - REDIS_URL     — same Redis (the queue is `win-ingest`)
#  - DATA_ROOT     — Railway Volume mounted at the same path on both services
#                    so staged_file_url paths are readable by the worker
#  - MISTRAL_API_KEY / VISION_AGENT_API_KEY / DOCUMENT_AI_PROVIDER /
#    ANTHROPIC_API_KEY / model_* — extractor providers
#
# See docs/superpowers/runbooks/win-ingest-rq-worker.md for the full
# rollout checklist.
