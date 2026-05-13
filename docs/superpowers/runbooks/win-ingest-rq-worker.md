# win-ingest RQ worker — rollout runbook

`/win/api/ingest/jobs` (the async upload surface) writes `IngestBatch` /
`IngestJob` rows to the tenant Postgres database and enqueues a job_id on
the Redis `win-ingest` queue. A separate worker service consumes that
queue and runs the same `auto_ingest` pipeline that `/win/api/ingest/auto`
runs, persisting the result back to the job row.

Two Railway services, one Docker image, one Postgres, one Redis. Files
go through an S3-compatible object store (Cloudflare R2 recommended);
the local backend is only suitable for single-service / dev deployments.

For the deploy-time variable template, use
`infra/railway/platform-api.md`. This runbook focuses on worker
operations and failure modes.

## Railway services

### `platform-app` (web — existing)

No change. Start command stays:

```
uvicorn platform_app.main:app --host 0.0.0.0 --port $PORT --workers 1
```

### `win-ingest-worker` (new)

Same image as `platform-app`. In Railway:

1. Create a new service from the same GitHub repo.
2. Settings → Build:
   - **Builder**: Dockerfile (not Railpack — auto-detect fails because
     `pyproject.toml` lives under `services/platform-api/`, not at repo root)
   - **Dockerfile Path**: `services/platform-api/Dockerfile`
   - **Build Context**: leave empty (= repo root, because the Dockerfile's
     `COPY` paths are repo-root-relative)
3. Settings → Deploy → **Custom Start Command**:

   ```
   yunwei-win-ingest-worker
   ```

4. Settings → Variables: use the template in
   `infra/railway/platform-api.md`. In particular the worker needs:
   - `DATABASE_URL`
   - `REDIS_URL`
   - `STORAGE_BACKEND=s3`
   - `S3_BUCKET` / `S3_ENDPOINT_URL` / `S3_REGION` /
     `S3_ACCESS_KEY_ID` / `S3_SECRET_ACCESS_KEY`
   - `OCR_PROVIDER`
   - `EXTRACTOR_PROVIDER`
   - `MISTRAL_API_KEY`
   - `VISION_AGENT_API_KEY`
   - `LANDINGAI_*` model overrides if any
   - `ANTHROPIC_API_KEY` / `ANTHROPIC_BASE_URL`
   - `MODEL_PARSE` / `MODEL_QA` / `MODEL_VISION` if customized
   - `WORKER_MAX_JOBS` (optional; default `100`) — worker processes this
     many jobs then exits so Railway restarts it, capping memory growth
     from LandingAI/httpx pools. Set to `0` (or empty) to disable.

5. Settings → Volumes: **leave empty**. Railway Volumes cannot be shared
   between services — every attached Volume is scoped to one service.
   The S3 backend (next section) is the supported way to give both
   services access to the same staged files.

   If you really must keep `STORAGE_BACKEND=local` for development, run
   the worker inside the web service as a background asyncio task
   instead of a separate Railway service.

### Postgres + Redis

Both services target the same `DATABASE_URL` and `REDIS_URL`. No
separate provisioning needed — Railway's Postgres + Redis plugins suffice.

## First-time onboarding

Existing tenant databases were provisioned before the `ingest_batches` /
`ingest_jobs` tables existed. The API handler calls
`ensure_ingest_job_tables_for(enterprise_id)` on every job-related
request, so the tables are created on first use (CREATE TABLE IF NOT
EXISTS). No migration script needs to run.

## Smoke test

1. Upload a contract PDF via the win-app — Upload screen.
2. Expect immediate response (no spinner waiting for OCR).
3. The "正在处理" panel shows a job card at `queued` → `running` → `extracted`.
4. Click the card → Review screen renders the draft from `result_json`.
5. Refresh the page in the middle of step 3 → the same job card should
   reappear (it was loaded from Postgres, not memory).
6. Confirm归档 → job status flips to `confirmed` and the card moves to
   "查看历史".

## Storage backend (S3-compatible required for two-service deploy)

`STORAGE_BACKEND=local` writes to `$DATA_ROOT/files` on the service's
disk. That works fine for a single-service deploy (dev / running the
worker inside the web process). It does **not** work across two Railway
services because Railway Volumes are scoped to one service — there is no
"attach this same Volume to both" option in the Railway UI.

For the standard two-service deploy use an S3-compatible store. AWS S3
works; Cloudflare R2 is recommended (S3-compatible, free at our volume,
no egress fees). Use `infra/railway/env/shared.env.example` for the
storage variables and reference them from both service templates.

When the S3 backend is active, `staged_file_url` rows look like
`s3://your-bucket-name/files/<uuid>.pdf`. The Volume mount is no longer
required.

Migration path: existing `file://...` URLs continue to work alongside
new `s3://...` URLs because `open_for_read` / `materialize_to_local`
dispatch on the URL scheme.

## Failure modes

- **Worker can't reach Redis**: enqueue fails inside the API handler;
  the job is created with `status=failed` and an error_message. Check
  `REDIS_URL` on both services.
- **Worker can't read staged file**: most likely `STORAGE_BACKEND=s3` or
  one of the `S3_*` variables differs between `platform-app` and
  `win-ingest-worker`. Confirm both services point at the same bucket and
  endpoint. If someone used `STORAGE_BACKEND=local` in a two-service
  Railway deploy, the worker will not have a reliable way to read files
  staged by the web service.
- **Mistral OCR or LandingAI extract failure**: surfaces as a normal
  `failed` job with the upstream error in `error_message`. User can
  click "重试" — increments `attempts` and re-enqueues.
- **Worker process died mid-job**: the job row stays in `running` until
  the next worker picks it up. RQ doesn't auto-resurrect; the user
  needs to use Cancel + Retry. (Future: heartbeat watchdog.)

## Rollback

Set the worker service's Start Command back to a no-op (`sleep infinity`)
or disable the service. The web service continues to enqueue jobs but
nothing consumes them — every job stays `queued` until you re-enable.
The legacy `/win/api/ingest/auto` endpoint is unaffected; it runs
synchronously in the web process and ignores Redis.

## Future hardening

- Worker heartbeat → `running` jobs older than N minutes auto-reset to
  `queued` for re-run.
- Optional provider fallback policy, for example MinerU OCR → Mistral OCR
  when the precision parser is unavailable.
- Retry budget per failure class (LLM 429 ≠ user error ≠ FK violation).
