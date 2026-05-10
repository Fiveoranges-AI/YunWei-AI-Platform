# Railway service config: Root Directory = `platform/`. So all COPY paths
# in this Dockerfile are relative to the platform/ subdirectory of the repo.
# That means app-win/ MUST live inside platform/ (it does — see platform/app-win/).
# The legacy /app/ chat UI scaffold sits OUTSIDE platform/ (at the repo root)
# so we cannot include it in this build context. main.py:_APP_DIST.exists()
# returns False at runtime and falls back to reverse_proxy — that's the
# documented deploy-safe path.

# ─────────────── Stage 1: build app-win (智通客户) UI ───────────────
FROM node:20-alpine AS app-win-build
WORKDIR /build/app-win

# package*.json first for layer cache: re-run npm ci only when deps change.
COPY app-win/package.json app-win/package-lock.json ./
RUN npm ci

COPY app-win/ ./
RUN npm run build && ls -la dist/ && ls -la dist/assets/ | head -10

# ─────────────── Stage 2: python runtime ───────────────
FROM python:3.13-slim
WORKDIR /app

# Hatchling needs the package present to compute metadata, so copy
# pyproject + platform_app + yinhu_brain together before pip install.
COPY pyproject.toml /app/
COPY platform_app /app/platform_app/
COPY yinhu_brain /app/yinhu_brain/
RUN pip install --no-cache-dir .

COPY migrations /app/migrations/
COPY static /app/static/

# Built app-win (智通客户) UI from stage 1 → /app/app-win/dist.
# main.py: _WIN_DIST = Path(__file__).resolve().parent.parent / "app-win" / "dist"
#  - container:  /app/platform_app/main.py → /app → /app/app-win/dist  ✅
#  - local dev:  platform/platform_app/main.py → platform/ → platform/app-win/dist  ✅
COPY --from=app-win-build /build/app-win/dist /app/app-win/dist

# Railway sets $PORT (typically 8080). Local docker-compose sets it via
# the `command:` override. Default to 80 so plain `docker run` also works.
EXPOSE 80
CMD ["sh", "-c", "uvicorn platform_app.main:app --host 0.0.0.0 --port ${PORT:-80} --workers 1"]
