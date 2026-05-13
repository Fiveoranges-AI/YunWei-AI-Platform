# Platform v3 — legacy removal log

Tracks what was deleted, moved, or archived during the v3 restructure
(branch `feat/platform-v3-restructure`). Use this as the diff
companion when re-onboarding or auditing the v2 → v3 transition.

## What was removed

### `app/` — legacy platform chat-UI scaffold

The `/<client>/<agent>/` chat dashboard React app. It was the v2
customer entry point, served from `/app/dist` by the `catch_all`
handler in `platform/platform_app/main.py`. v3 routes logged-in users
straight to `/win/`, so the dashboard is no longer reachable from the
customer flow.

- **Status:** deleted (`git rm -rf app/`).
- **Behavior lost:** none for current customers; the `/api/agents`
  endpoint is still served and the HMAC reverse proxy
  (`/<client>/<agent>/...`) is still wired up for admin / debug.
- **Recovery:** any v2 deploy SHA; the directory was last present at
  the parent of `feat/platform-v3-restructure`.

### `platform/static/agents.html`

The pre-Win customer dashboard. `index()` used to serve it on `GET /`
when the `app_session` cookie was present.

- **Status:** archived to `docs/migration/archive/agents-dashboard.html`.
- **Why archive (not delete):** snapshot of v2 product surface for
  audit / screenshot reference. Not reachable from any route.

### `platform/tests/test_platform_chat_ui_routing.py`

Tested the `_APP_DIST` static-file branch and the dashboard ACL path.
Every assertion targeted code that is now gone.

- **Status:** deleted.
- **Coverage:** the surviving routing paths are covered by
  `test_proxy.py` (HMAC reverse proxy) and
  `test_yunwei_win_assistant_runtime.py` (dedicated-runtime forwarding).

### `agent-yinhu-super-xiaochen` service in `ops/docker-compose.yml`

The bundled per-customer agent runtime that v2 expected every deploy
to ship with. v3 treats dedicated runtimes as opt-in per-enterprise,
selected via the runtime registry — they are not part of the default
stack.

- **Status:** removed from the default compose file; an opt-in example
  preserved at `runtimes/examples/yinhu-super-xiaochen.compose.yml`.

## What moved

| Old path | New path | Why |
|---|---|---|
| `platform/yinhu_brain/` | `platform/yunwei_win/` | Package rebranded to its product (`/win/` 智通客户) and detached from the original Yinhu brand. URL `/win/api/*` is unchanged. |
| `platform/app-win/` | `apps/yunwei-win-web/` | Frontends now live under top-level `apps/`. Matches the future `services/` + `apps/` repo shape. |
| `ops/docker-compose.yml` | `infra/local/docker-compose.yml` | Infra lives under `infra/`. `ops/bootstrap.sh` stays and was updated to point at the new path. |
| `docs/PLAN.md` | `docs/migration/legacy-agent-dashboard-plan.md` | Historical agent-dashboard implementation plan; superseded by `docs/architecture/platform-v3.md`. |
| `docs/SSO.md` | `docs/migration/legacy-sso-plan.md` | v2 SSO design notes; kept as reference. |

The package rename touched ~117 files. `rg yinhu_brain` under
`platform/` returns zero hits; the only remaining references are
historical plan/spec markdown files under `docs/superpowers/`.

## What was renamed

### Console script

| Old | New |
|---|---|
| `yinhu-ingest-worker` | `yunwei-win-ingest-worker` |

Declared in `platform/pyproject.toml`'s `[project.scripts]`. The old
script name is gone from the wheel — any deploy whose worker service
still invokes `yinhu-ingest-worker` will fail to start. Update the
Railway dashboard Start Command before promoting.

### Product copy

`问 AI` → `问小陈` across the Win frontend (`Ask.tsx`, `Sidebar.tsx`,
`TabBar.tsx`). The backend never carried the string.

## What was added

| Path | Purpose |
|---|---|
| `platform/platform_app/context.py` | `AuthContext` + `require_auth_context(request)`. |
| `platform/platform_app/entitlements.py` | Plan → capability resolution. |
| `platform/platform_app/runtime_registry.py` | `runtimes` + `runtime_bindings` helpers. |
| `platform/migrations/010_runtime_registry.sql` | Schema for the two new tables. |
| `platform/yunwei_win/assistant/` | `/win/api/assistant/chat` shared assistant + dedicated runtime forwarder. |
| `apps/yunwei-win-web/` | Win product SPA (moved from `platform/app-win`). |
| `runtimes/README.md` | Contract dedicated runtimes must satisfy. |
| `runtimes/examples/yinhu-super-xiaochen.compose.yml` | Opt-in compose for the legacy demo runtime. |
| `infra/local/` | Local docker-compose stack. |
| `infra/railway/platform-api.md` | Railway service config + env vars. |
| `docs/architecture/platform-v3.md` | New architecture overview. |
| `docs/migration/legacy-removal.md` | This file. |

## What was retained

- `platform_app/proxy.py` and `/api/agents` — used by admin / debug,
  not customer flow.
- HMAC sign / verify utilities — retained for the legacy proxy and
  for the planned dedicated-runtime auth scheme.
- `tenants` table — still referenced by the HMAC proxy. Replacing it
  is out of scope for v3; the new runtime registry coexists.
- `document_ai_provider` setting in `platform/yunwei_win/config.py` —
  no longer read by `auto_ingest`, but left in place to avoid env
  churn. Safe to remove in a follow-up.

## Risks and follow-ups

- **Railway worker service Start Command** — must change from
  `yinhu-ingest-worker` to `yunwei-win-ingest-worker` before the next
  promote, or the worker will not start.
- **External links** — any bookmark / partner integration pointing
  at `app.fiveoranges.ai/` for an authed user now hits a 303 → `/win/`.
  Unauthed users still see login. Anything deep-linking to
  `/agents.html` (no known callers) will 404; the file is archived.
- **Volume sharing** — when `STORAGE_BACKEND=local`, the web and
  worker services must share the same `/data` volume. Already covered
  by the worker session-commit fix shipped pre-v3 (commit
  `5b7eda0`).
- **`document_ai_provider`** — see above; trivial removal once nothing
  still imports the symbol.
- **HMAC proxy → runtime registry migration** — once dedicated-runtime
  routing is the only Pro/Max path, the `tenants` table and
  `/<client>/<agent>/` URL pattern can be retired. Tracked separately.
- **`ops/bootstrap.sh` legacy tenant path** — fully removed. The v2
  `add-tenant` + HMAC-patching flow is no longer reachable from the
  bootstrap script. If a v2 tenant is genuinely needed for the
  `/<client>/<agent>/` HMAC reverse proxy (admin/debug only), invoke
  `python -m platform_app.admin add-tenant` directly. Default
  bootstrap seeds admin user + enterprise + membership; dedicated
  runtimes register via `--with-runtime`.
- **`agents/` directory** — archived to
  `docs/migration/archive/agents/`. Held the per-tenant `.env.example`
  for the HMAC proxy. Real `.env` files live on deploy hosts (not in
  the repo), so production tenants are unaffected. Restore the
  example by copying from the archive if a v2 tenant is provisioned.
