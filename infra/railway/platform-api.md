# Railway deploy — `platform-api`

The platform v3 stack on Railway is **two services backed by the same
Docker image**, both built from `services/platform-api/Dockerfile`:

1. **`platform-app`** — FastAPI web service. Serves the canonical v3
   surface: page routes (`/`, `/login`, `/register`, `/admin`, `/win/`)
   and the `/api/*` browser API (`/api/auth/*`, `/api/me`, `/api/win/*`,
   `/api/admin/*`, `/api/enterprise/*`). No legacy reverse proxy.
2. **`win-ingest-worker`** — long-running RQ worker that drains the
   `yunwei_win` ingest queue. No HTTP listener.

Both services share `PLATFORM_DATABASE_URL`, `REDIS_URL`, and the upload
volume so a Document INSERT by the web service is visible to the worker
and vice versa.

---

## Image build

`services/platform-api/Dockerfile` is a multi-stage build. The build
context is the **repo root** — Railway's "Root Directory" should be
left blank (or set to `/`).

```
Service settings:
  Builder:          Dockerfile
  Dockerfile path:  services/platform-api/Dockerfile
  Root Directory:   <blank — repo root>
```

The Dockerfile:
1. Builds `apps/win-web` with Vite → dist copied into
   `/app/win-web/dist`.
2. Installs `services/platform-api/` Python deps via `uv` into a venv.
3. Copies `services/platform-api/platform_app/` and
   `services/platform-api/yunwei_win/` into `/app/`.

The same image runs both services. The start command differs.

---

## Service: `platform-app` (web)

```
Start Command:  (leave blank — uses CMD)
```

The Dockerfile's `CMD` already runs:

```
uvicorn platform_app.main:app --host 0.0.0.0 --port ${PORT:-80} --workers 1
```

Railway injects `$PORT` automatically.

### Required env vars

| Key | Notes |
|---|---|
| `PLATFORM_DATABASE_URL` | Postgres — platform metadata (users, enterprises, runtimes, …). |
| `REDIS_URL` | Shared with the worker; used for sessions + RQ queue. |
| `COOKIE_SECRET` | Signing key for `app_session` cookie. |
| `CSRF_SECRET` | Double-submit token secret. |
| `ANTHROPIC_API_KEY` | LLM upstream for the shared assistant + ingest extractors. |
| `MISTRAL_API_KEY` | OCR provider (default). |
| `LANDINGAI_API_KEY` | Extractor provider (default). |
| `STORAGE_BACKEND` | `local` or `s3`. If `s3`, set `S3_*` vars. |

### Optional / per-feature

| Key | Default | Purpose |
|---|---|---|
| `OCR_PROVIDER` | `mistral` | `mistral` or `mineru`. |
| `EXTRACTOR_PROVIDER` | `landingai` | `landingai` or `deepseek`. |
| `MINERU_API_TOKEN` | — | Required if `OCR_PROVIDER=mineru`. |
| `DEEPSEEK_API_KEY` | — | Required if `EXTRACTOR_PROVIDER=deepseek`. |

### Health

`GET /` returns 200 (login) or 303 → `/win/`. Railway's default HTTP
healthcheck on `/` works.

---

## Service: `win-ingest-worker`

Same Dockerfile, same image. Override the start command:

```
Start Command:  yunwei-win-ingest-worker
```

`yunwei-win-ingest-worker` is a console-script entry point declared in
`services/platform-api/pyproject.toml`
(`yunwei_win.workers.ingest_rq_worker:main`).
The worker subscribes to the `ingest` queue on `REDIS_URL`.

> Prior to v3 this entry point was named `yinhu-ingest-worker`.
> **The old name no longer exists in the wheel** — make sure the
> Railway dashboard reflects the new name or the worker service will
> fail to start with a "command not found" error.

### Required env vars

Same as `platform-app`. Both services must read the same
`PLATFORM_DATABASE_URL` and `REDIS_URL`. If `STORAGE_BACKEND=local`,
both must mount the same persistent volume.

---

## Shared volume (only when `STORAGE_BACKEND=local`)

| Mount path | Used by | Purpose |
|---|---|---|
| `/data` | platform-app + worker | Uploaded staged files |

When `STORAGE_BACKEND=s3` the volume is not needed — both services
stream uploads through the configured bucket.

---

## Promote / rollback

Railway tags every successful deploy with a git SHA. Promotion is a
no-op rebuild from the new SHA on both services. To roll back:

```
Service → Deployments → <previous deploy> → Redeploy
```

Both services should be rolled back to the same SHA together. The web
service and worker share migrations
(`services/platform-api/migrations/`), so if a deploy ran
`010_runtime_registry.sql` you must NOT roll back below the
migration that introduced it without first dropping those tables. The
safer rollback path is: re-deploy the previous SHA and re-apply any
needed forward-only schema fix in a separate change.

---

## First-time provisioning checklist

1. Create two Railway services in the same project from this repo.
2. Set `Dockerfile path = services/platform-api/Dockerfile` on both.
3. Override `Start Command = yunwei-win-ingest-worker` on the second.
4. Provision a Postgres add-on → `PLATFORM_DATABASE_URL`.
5. Provision a Redis add-on → `REDIS_URL`.
6. Set `COOKIE_SECRET` + `CSRF_SECRET` (`openssl rand -hex 32` each).
7. Set the AI provider keys above.
8. If `STORAGE_BACKEND=local`: attach a Volume to both services at
   `/data`.
9. Deploy. Migrations run on `platform-app` startup
   (`platform_app.main.lifespan` → `db._migrate`).

---

## Related

- Docker stack for local dev: `infra/local/docker-compose.yml`.
- Worker operations: `docs/superpowers/runbooks/win-ingest-rq-worker.md`.
- Architecture overview: `docs/architecture/platform-v3.md`.
- Dedicated runtime contract (Pro+): `runtimes/README.md`.
