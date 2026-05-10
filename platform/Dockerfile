# Railway service config: build context = repo root (not platform/).
# So all COPY paths in this Dockerfile are repo-root-relative.

# ─────────────── Stage 1: build app-win (智通客户) UI ───────────────
# app-win/ lives inside platform/ so it ships with the platform service.
FROM node:20-alpine AS app-win-build
WORKDIR /build/app-win

# package*.json first for layer cache: re-run npm ci only when deps change.
COPY platform/app-win/package.json platform/app-win/package-lock.json ./
RUN npm ci

COPY platform/app-win/ ./
RUN npm run build && ls -la dist/ && ls -la dist/assets/ | head -10

# ─────────────── Stage 2: python runtime ───────────────
FROM python:3.13-slim
WORKDIR /app

# Hatchling needs the package present to compute metadata, so copy
# pyproject + platform_app + yinhu_brain together before pip install.
COPY platform/pyproject.toml /app/
COPY platform/platform_app /app/platform_app/
COPY platform/yinhu_brain /app/yinhu_brain/
RUN pip install --no-cache-dir .

COPY platform/migrations /app/migrations/
COPY platform/static /app/static/

# Built app-win UI from stage 1 → /app/app-win/dist.
# main.py: _WIN_DIST = Path(__file__).resolve().parent.parent / "app-win" / "dist"
#  - container:  /app/platform_app/main.py → /app → /app/app-win/dist  ✅
#  - local dev:  <repo>/platform/platform_app/main.py → <repo>/platform/
#                → <repo>/platform/app-win/dist  ✅
COPY --from=app-win-build /build/app-win/dist /app/app-win/dist

# Railway sets $PORT (typically 8080). Local docker-compose sets it via
# the `command:` override. Default to 80 so plain `docker run` also works.
EXPOSE 80
CMD ["sh", "-c", "uvicorn platform_app.main:app --host 0.0.0.0 --port ${PORT:-80} --workers 1"]
