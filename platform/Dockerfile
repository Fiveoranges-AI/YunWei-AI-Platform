# ─────────────── Stage 1: build agent-platform/app/ chat UI ───────────────
# Produces /build/app/dist/ which stage 2 copies into the runtime image.
# This stage adds ~150 MB during build, but is discarded — the final image
# never contains node/npm. Skip without breaking anything: if app/ is empty
# the COPY in stage 2 will copy an empty dir and the index.html existence
# check inside main.py:catch_all trips the deploy-safe fallback.
FROM node:20-alpine AS app-build
WORKDIR /build/app

# package*.json first for layer cache: re-run npm ci only when deps change.
COPY app/package.json app/package-lock.json ./
RUN npm ci

# Then source — changes here don't invalidate the npm ci layer.
COPY app/ ./
RUN npm run build && ls -la dist/ && ls -la dist/assets/ | head -10

# ─────────────── Stage 2: python runtime (existing) ───────────────
FROM python:3.13-slim
WORKDIR /app

# Hatchling needs the package present to compute metadata, so copy
# pyproject + platform_app together before pip install. migrations/static
# follow because they're runtime-only and don't affect the install layer.
COPY platform/pyproject.toml /app/
COPY platform/platform_app /app/platform_app/
RUN pip install --no-cache-dir .

COPY platform/migrations /app/migrations/
COPY platform/static /app/static/

# Built chat UI from stage 1 → /app/dist inside the container.
# main.py computes _APP_DIST = Path(__file__).parent.parent.parent / "app" / "dist"
# Inside the container: /app/platform_app/main.py → parent=/app/platform_app
# → parent=/app → parent=/ → _APP_DIST = /app/dist (which is inside WORKDIR /app).
# So placing dist at /app/dist makes the path resolution work correctly.
COPY --from=app-build /build/app/dist /app/dist

# Railway sets $PORT (typically 8080). Local docker-compose sets it via
# the `command:` override. Default to 80 so plain `docker run` also works.
EXPOSE 80
CMD uvicorn platform_app.main:app --host 0.0.0.0 --port ${PORT:-80} --workers 1
