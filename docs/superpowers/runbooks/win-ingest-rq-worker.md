# win-ingest RQ worker — rollout runbook

`/win/api/ingest/jobs` (the async upload surface) writes `IngestBatch` /
`IngestJob` rows to the tenant Postgres database and enqueues a job_id on
the Redis `win-ingest` queue. A separate worker service consumes that
queue and runs the same `auto_ingest` pipeline that `/win/api/ingest/auto`
runs, persisting the result back to the job row.

Two Railway services, one Docker image, one Postgres, one Redis. Files
go through an S3-compatible object store (Cloudflare R2 recommended) —
**Railway Volumes cannot be shared between services**, so the local
backend is only suitable for single-service / dev deployments.

## Railway services

### `platform-app` (web — existing)

No change. Start command stays:

```
uvicorn platform_app.main:app --host 0.0.0.0 --port $PORT --workers 1
```

### `platform-ingest-worker` (new)

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
   python -m yunwei_win.workers.ingest_rq_worker
   ```

   (Use `python -m` instead of the bare `yunwei-win-ingest-worker`
   console script so CWD=`/app` gets on `sys.path` and prompts at
   `/app/prompts` resolve via `Path(__file__).parents[N]`. The console
   script also works once `find_prompt` is in place, but `python -m` is
   the safer shape that matches how `uvicorn` starts the web service.)

4. Settings → Variables: copy all variables from `platform-app`, in
   particular:
   - `DATABASE_URL`
   - `REDIS_URL`
   - `DATA_ROOT`
   - `MISTRAL_API_KEY`
   - `VISION_AGENT_API_KEY`
   - `DOCUMENT_AI_PROVIDER` (set to `landingai`)
   - `LANDINGAI_*` model overrides if any
   - `ANTHROPIC_API_KEY` (Claude/DeepSeek)
   - `MODEL_PARSE` / `MODEL_QA` / `MODEL_VISION` if customized
   - `WORKER_MAX_JOBS` (optional; default `100`) — worker processes this
     many jobs then exits so Railway restarts it, capping memory growth
     from LandingAI/httpx pools. Set to `0` (or empty) to disable.
   - `STORAGE_BACKEND` (optional; default `local`) — set to `s3` to write
     uploads to an S3-compatible bucket instead of the shared Volume.
   - `S3_BUCKET` / `S3_ENDPOINT_URL` / `S3_REGION` /
     `S3_ACCESS_KEY_ID` / `S3_SECRET_ACCESS_KEY` — required when
     `STORAGE_BACKEND=s3`. See the storage-backend section below.

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
no egress fees). On **both** services set:

```env
STORAGE_BACKEND=s3
S3_BUCKET=your-bucket-name
S3_ENDPOINT_URL=https://<accountid>.r2.cloudflarestorage.com   # R2 example
S3_REGION=auto
S3_ACCESS_KEY_ID=...
S3_SECRET_ACCESS_KEY=...
```

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
- **Worker can't read staged file**: most likely the volume isn't
  mounted on the worker. Confirm both services have a volume at the same
  `DATA_ROOT`. Without it the worker job fails with
  `FileNotFoundError`.
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
- Object storage (S3 / R2) instead of Railway Volume so workers can scale
  beyond a single shared disk.
- Retry budget per failure class (LLM 429 ≠ user error ≠ FK violation).
