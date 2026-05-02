FROM python:3.13-slim

WORKDIR /app

# Hatchling needs the package present to compute metadata, so copy
# pyproject + platform_app together before pip install. migrations/static
# follow because they're runtime-only and don't affect the install layer.
COPY pyproject.toml /app/
COPY platform_app /app/platform_app/
RUN pip install --no-cache-dir .

COPY migrations /app/migrations/
COPY static /app/static/

# Railway sets $PORT (typically 8080). Local docker-compose sets it via
# the `command:` override. Default to 80 so plain `docker run` also works.
EXPOSE 80
CMD uvicorn platform_app.main:app --host 0.0.0.0 --port ${PORT:-80} --workers 1
