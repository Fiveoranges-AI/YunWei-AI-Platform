# Local stack — `infra/local/`

Bring up `platform-api` + Cloudflare tunnel on a single host using
`docker compose`. This is the dev/staging stack, not the Railway
production deploy (see `infra/railway/platform-api.md` for that).

## Layout

```
infra/local/
  docker-compose.yml      # platform-app + cloudflared services
README.md                 # this file
```

## Prerequisites

- Docker + `docker compose` v2.
- `.env` at the repo root with:
  - `PLATFORM_DATABASE_URL` (Postgres URL the container can reach)
  - `REDIS_URL`
  - `COOKIE_SECRET`, `CSRF_SECRET`
  - `ANTHROPIC_API_KEY`, `MISTRAL_API_KEY`, `LANDINGAI_API_KEY`
  - `TUNNEL_TOKEN` (Cloudflare Zero Trust tunnel token)
- A `data/` directory at the repo root (created on first run) for the
  upload volume when `STORAGE_BACKEND=local`.

The compose file uses relative paths anchored at `infra/local/`:

```yaml
services:
  platform-app:
    build:
      context: ../..              # repo root
      dockerfile: platform/Dockerfile
    env_file: ../../.env
    volumes:
      - ../../data:/data
```

## Bring up

From the repo root:

```bash
docker compose -f infra/local/docker-compose.yml up --build -d
```

`platform-app` listens on port 80 inside the container; Cloudflare
tunnel forwards your public hostname to it. There is no published
port on the host — connect via the tunnel hostname.

## Bootstrap the DB

Once the stack is up, seed the admin user + enterprise + membership:

```bash
./ops/bootstrap.sh
```

This is the minimal v3 path. It does **not** provision any
dedicated runtime or legacy HMAC tenant — the shared `/win/` product
works against `platform-app` alone.

Vars consulted from `.env`:

| Var | Default |
|---|---|
| `ADMIN_BOOTSTRAP_USER` | `xuzong` |
| `ADMIN_BOOTSTRAP_PASSWORD` | (required) |
| `BOOTSTRAP_ENTERPRISE_ID` | `yinhu` |
| `BOOTSTRAP_ENTERPRISE_NAME` | `银湖石墨` |

## Optional: register a dedicated runtime

Pro/Max plans route their assistant through a dedicated per-enterprise
runtime container. Register it via the runtime_registry:

1. Start the runtime container in a separate compose stack joined to
   the `cf-tunnel` external network (see
   `runtimes/examples/yinhu-super-xiaochen.compose.yml`).
2. Re-run bootstrap with `--with-runtime`:

   ```bash
   ./ops/bootstrap.sh --with-runtime
   ```

   Override the defaults with env vars when needed:

   | Var | Default |
   |---|---|
   | `RUNTIME_ID` | `rt_yinhu_super_xiaochen` |
   | `RUNTIME_PROVIDER` | `super-xiaochen` |
   | `RUNTIME_URL` | `http://agent-yinhu-super-xiaochen:8000` |
   | `RUNTIME_VERSION` | `v1` |
   | `RUNTIME_CAPABILITY` | `assistant` |

3. Verify the binding landed in the DB:

   ```bash
   docker compose -f infra/local/docker-compose.yml exec platform-app \
     python -c "from platform_app import db, runtime_registry; \
       db.init(); \
       print(runtime_registry.get_runtime_for('yinhu', 'assistant'))"
   ```

## Tear down

```bash
docker compose -f infra/local/docker-compose.yml down
```

Add `-v` to also drop the named volumes (you almost never want this:
it deletes uploads in `/data` and the Cloudflare tunnel state).

## Running the ingest worker locally

The compose file does **not** include the RQ worker — it's an optional
sidecar for testing async ingest. To run it against the same image:

```bash
docker compose -f infra/local/docker-compose.yml run --rm \
  --entrypoint yunwei-win-ingest-worker \
  platform-app
```

Or run it natively from the repo:

```bash
cd platform && ./.venv/bin/yunwei-win-ingest-worker
```

Both modes need the same `REDIS_URL` as `platform-app` so they see the
same queue.

## Running a dedicated runtime (Pro+ test)

Dedicated runtimes are out-of-stack by design — they sit behind their
own deployment and join the platform via the runtime registry. An
example compose file for the legacy `yinhu-super-xiaochen` runtime
lives at `runtimes/examples/yinhu-super-xiaochen.compose.yml`. To test
end-to-end locally:

1. Start the local stack as above.
2. Start the runtime stack separately, joining it to the
   `cf-tunnel` external network.
3. Register it via `./ops/bootstrap.sh --with-runtime` (see
   *Optional: register a dedicated runtime* above) — that writes the
   row into `runtimes` + `runtime_bindings` for you.

See `runtimes/README.md` for the runtime contract.

## Troubleshooting

- **`/win/` returns 503** — frontend was not built. Run
  `cd apps/yunwei-win-web && npm run build` or rebuild the Docker
  image. The dev fallback path is
  `apps/yunwei-win-web/dist`; the container path is
  `/app/yunwei-win-web/dist`.
- **Worker fails with "command not found"** — start command is still
  the legacy `yinhu-ingest-worker`. The console script renamed in v3;
  it is now `yunwei-win-ingest-worker`.
- **Login works but `/win/api/customers` returns 403 no_enterprise** —
  the cookie is valid but no `enterprise_members` row exists for the
  user. Either register via the invite-code flow (it auto-creates the
  enterprise) or `INSERT` a membership manually.
