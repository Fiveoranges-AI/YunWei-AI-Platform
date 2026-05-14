# Railway deploy — platform API + win ingest worker

The Railway production shape is:

1. `platform-app` — public FastAPI web service. Serves `/`, `/win/`, and
   `/api/*`.
2. `win-ingest-worker` — private RQ worker. No HTTP listener. Drains the
   `win-ingest` Redis queue and runs the schema-first ingest pipeline.
3. `Postgres` — one shared platform metadata database.
4. `Redis` — one shared session/cache/queue Redis.
5. S3-compatible object storage — required for the standard two-service
   ingest deploy because staged upload files must be readable by both the
   web service and the worker.

Both app services use the same Docker image built from
`services/platform-api/Dockerfile`; only the start command and variables
differ.

## Railway service build settings

Apply these settings to both `platform-app` and `win-ingest-worker`:

```text
Builder:          Dockerfile
Dockerfile path:  services/platform-api/Dockerfile
Root Directory:   <blank; repo root>
```

Do not set a custom build context under `services/platform-api`. The
Dockerfile copies `apps/win-web`, `services/platform-api/platform_app`,
`services/platform-api/yunwei_win`, migrations, static files, and prompts
using repo-root-relative paths.

## Start commands

`platform-app`:

```text
Start Command: <blank>
```

The Dockerfile `CMD` runs:

```text
uvicorn platform_app.main:app --host 0.0.0.0 --port ${PORT:-80} --workers 1
```

`win-ingest-worker`:

```text
Start Command: yunwei-win-ingest-worker
```

The old `yinhu-ingest-worker` entrypoint no longer exists.

## Variable strategy

Use service-specific variables. Each Railway service gets a complete
copy/paste env template; variables that must match are duplicated
intentionally instead of going through a project-level variable layer.

Principles:

- `DATABASE_URL` and `REDIS_URL` must point to the same Railway Postgres
  and Redis resources for both services.
- AI provider and storage variables must match between `platform-app` and
  `win-ingest-worker` because the worker drains jobs created by the web
  service through `/api/win/ingest/jobs`.
- `COOKIE_SECRET` belongs only on `platform-app`; the worker does not serve
  browser sessions.
- Do not set `PORT` manually unless Railway domain routing requires a fixed
  target port. The web service already listens on Railway's injected `PORT`;
  the worker should not expose public networking.
- Prefer `STORAGE_BACKEND=s3` for Railway. `STORAGE_BACKEND=local` only
  works when the process that stages files is the same process that reads
  them.
- Do not set `DOCUMENT_AI_PROVIDER` for new deploys. The schema-first
  ingest path uses `OCR_PROVIDER` and `EXTRACTOR_PROVIDER`.

## Railway variable templates

The copy/paste-ready Railway variables live outside this Markdown file so
the deploy contract stays easy to reuse and review.

| Railway target | Template file | Notes |
|---|---|---|
| `platform-app` → Variables → Raw Editor | `infra/railway/env/platform-app.env.example` | Complete web-service template. Includes `COOKIE_SECRET`. |
| `win-ingest-worker` → Variables → Raw Editor | `infra/railway/env/win-ingest-worker.env.example` | Complete worker template. Includes `WORKER_MAX_JOBS`; no browser-session secrets. |

Adjust resource names in the service templates if your Railway Postgres
or Redis services are not named exactly `Postgres` and `Redis`.

The default LLM upstream in both service templates is DeepSeek. The
`ANTHROPIC_*` names are historical because the app uses an
Anthropic-compatible client shape; put the DeepSeek key in
`ANTHROPIC_API_KEY` and keep `ANTHROPIC_BASE_URL` pointed at DeepSeek's
Anthropic-compatible endpoint. Do not rely on `DEEPSEEK_API_KEY` for win
ingest unless the code grows an explicit alias.

## Service notes: `platform-app`

Healthcheck: `GET /` is enough. It returns login or redirects an
authenticated user to `/win/`.

## Service notes: `win-ingest-worker`

The worker intentionally does not need:

- `COOKIE_SECRET`
- `PLATFORM_HOST_APP`
- `PLATFORM_HOST_API`
- public networking
- `PORT`

## Storage

For two Railway services, set the S3 storage section in both
`infra/railway/env/platform-app.env.example` and
`infra/railway/env/win-ingest-worker.env.example` to the same values.
Cloudflare R2, AWS S3, or any S3-compatible store is fine.

Avoid `STORAGE_BACKEND=local` for the standard Railway split. The web
service stages uploaded files, and the worker later reads them. A local
filesystem path inside one service is not a shared storage contract for
another service.

## Rollout checklist

1. Create or confirm services: `platform-app`, `win-ingest-worker`,
   `Postgres`, `Redis`.
2. Set the same Dockerfile build settings on both app services.
3. Leave `platform-app` start command blank.
4. Set `win-ingest-worker` start command to `yunwei-win-ingest-worker`.
5. Paste `infra/railway/env/platform-app.env.example` into `platform-app`
   Variables → Raw Editor, then fill secrets.
6. Paste `infra/railway/env/win-ingest-worker.env.example` into
   `win-ingest-worker` Variables → Raw Editor, then fill matching
   AI/storage/provider values.
7. Confirm `platform-app` has public networking and custom domain.
8. Confirm `win-ingest-worker` has no public domain.
9. Deploy both app services from the same git SHA.
10. Smoke test:
    - login redirects to `/win/`
    - `/api/win/ingest/jobs` creates a queued job
    - worker logs show it picked up the job
    - job status reaches `extracted`
    - review screen renders `result_json`

## Rollback

Roll back `platform-app` and `win-ingest-worker` to the same git SHA. Do
not roll one back without the other when migrations or job payload shape
changed.

If the worker deploy is bad but the web service is healthy, temporarily
stop the worker service or set its start command to `sleep infinity`. New
async ingest jobs will remain queued until the worker is restored.
