# Repository Structure v2

Status: Phase 1 complete (branch `chore/repo-structure-v2`).
Phase 2-4 still proposed; see Migration Plan below.

Date: 2026-05-13

Phase 1 execution (commits on `chore/repo-structure-v2`):

- `b64293c refactor(repo): move frontends to apps/marketing-web and apps/win-web`
- `ea682ac refactor(repo): move backend service to services/platform-api`
- `ed93b0a refactor(repo): move ops to scripts and update infra references`
- `docs(repo): align README and docs with services/platform-api layout` (this commit)

## Problem

The repository currently mixes several different boundaries:

- `landing/` is a public marketing web app, but it lives outside `apps/`.
- `apps/yunwei-win-web/` is a customer product UI, but its name still reflects a partial migration state.
- `platform/` contains the FastAPI control plane, the `yunwei_win` product backend, RQ worker entry points, migrations, prompts, static HTML, tests, and the Dockerfile.
- `runtimes/` contains runtime contracts and examples, but the examples still look like customer-specific platform code.
- `ops/` mixes operational scripts with deployment concepts that now mostly live under `infra/`.
- Current docs still include mixed references to legacy dashboard paths, `/win/api/*`, and the newer `/api/win/*` direction.

The core issue is not cosmetic. Deployment units, product boundaries, runtime boundaries, and shared code boundaries are not obvious from the filesystem.

## First Principles

A top-level directory should answer one clear question:

- `apps/`: user-facing web applications that people open in a browser.
- `services/`: independently started backend processes.
- `packages/`: reusable libraries consumed by more than one app or service.
- `runtimes/`: AI runtime contracts, SDKs, and examples called by the platform.
- `infra/`: deployment configuration and environment wiring.
- `scripts/`: local or operational commands.
- `docs/`: architecture, decisions, runbooks, migration notes, and implementation specs.

The repository should be organized by runtime and ownership boundaries, not by historical names such as `landing`, `app`, or `platform`.

## Target Structure

```text
agent-platform/
  apps/
    marketing-web/              # fiveoranges.ai public marketing site
    platform-web/               # app.fiveoranges.ai portal, auth shell, admin, settings
    win-web/                    # 智通客户 UI, if kept separate from platform-web

  services/
    platform-api/               # Python FastAPI control plane
      src/platform_api/
      migrations/
      tests/
      pyproject.toml
      Dockerfile

    win-api/                    # Python 智通客户 domain backend, if split later
      src/win_api/
      prompts/
      tests/
      pyproject.toml

    win-worker/                 # RQ ingest worker, if split later
      src/win_worker/

  packages/
    api-client/                 # generated TypeScript client from OpenAPI
    ui/                         # shared React components / design system
    config/                     # shared TS, lint, formatting, Tailwind config

  runtimes/
    contracts/
      assistant-runtime.md
      healthcheck.md
      dedicated-runtime-auth.md
    sdk/
      python/
    examples/
      dedicated-assistant/

  infra/
    local/
    railway/
    cloudflare/
    docker/

  scripts/
    bootstrap-dev.sh
    generate-openapi-client.sh
    sync-silver-canonical.py

  docs/
    architecture/
    decisions/
    migration/
    runbooks/
    specs/

  data/                         # gitignored local development data only
```

## Recommended Intermediate Structure

Do not split Python services first. The current FastAPI process already hosts both `platform_app` and `yunwei_win`, and the most valuable first move is clarifying the outer repository shape without changing runtime behavior.

Phase 1 should produce:

```text
agent-platform/
  apps/
    marketing-web/              # moved from landing/
    platform-web/               # new Next.js portal, when introduced
    win-web/                    # moved from apps/yunwei-win-web/

  services/
    platform-api/               # moved from platform/
      platform_app/
      yunwei_win/
      migrations/
      prompts/
      tests/
      Dockerfile
      pyproject.toml

  runtimes/
    contracts/
    examples/

  infra/
    local/
    railway/

  scripts/
    bootstrap-dev.sh
    sync-silver-canonical.py

  docs/
    architecture/
    decisions/
    migration/
    runbooks/
    specs/
```

This gets the important boundary right:

- All browser applications live under `apps/`.
- All Python backend processes live under `services/`.
- Runtime contracts are not confused with platform backend code.
- Deployment configuration remains separate from business logic.
- Operational scripts are visible and separate from deployment manifests.

## Dependency Rules

The filesystem structure should be backed by explicit dependency rules:

```text
apps/*        -> may call services through HTTP APIs
apps/*        -> must not import Python service code
services/*    -> must not import apps/*
packages/*    -> must not depend on a specific deployment environment
runtimes/*    -> implement platform runtime contracts; no browser cookies
infra/*       -> deployment only; no business logic
scripts/*     -> may call service CLIs or HTTP APIs; must be idempotent
```

For browser flows:

```text
apps/platform-web
  -> /api/auth/*
  -> /api/me
  -> /api/win/*
  -> /api/admin/*
```

For backend flows:

```text
services/platform-api
  -> owns auth/session/enterprise/entitlements/runtime registry
  -> owns server-side runtime selection
  -> calls dedicated runtimes server-side
  -> does not trust enterprise_id from browser bodies
```

For runtime flows:

```text
runtimes/*
  -> exposes GET /healthz
  -> exposes POST /assistant/chat
  -> receives platform-signed identity context
  -> never receives browser cookies
  -> never decides enterprise_id from browser input
```

## Naming

Preferred names:

| Current | Target | Notes |
| --- | --- | --- |
| `landing/` | `apps/marketing-web/` | Public marketing site. |
| `apps/yunwei-win-web/` | `apps/win-web/` | Product UI for 智通客户. |
| `platform/` | `services/platform-api/` | Python FastAPI service. |
| `ops/` | `scripts/` | Local and operational commands. |
| `platform_app` | `platform_api` | Later Python package rename; not part of Phase 1. |
| `yunwei_win` | `win_api` or keep `yunwei_win` | Keep initially to avoid unnecessary import churn. |
| customer names such as `yinhu` | examples/fixtures only | Must not appear in core package names. |

Do not rename Python import packages in the same commit as the outer directory move unless the change is intentionally scoped as a package rename. Moving the outer directory first keeps the migration reviewable.

## URL Contract

The repository structure should align with the URL structure:

Browser pages:

```text
/
/login
/register
/win
/win/customers
/win/customers/:customerId
/win/ask
/win/uploads
/win/review
/settings/organization
/settings/members
/settings/billing
/admin
/admin/enterprises
/admin/runtimes
/admin/data
```

Browser-facing APIs:

```text
/api/auth/*
/api/me
/api/win/*
/api/admin/*
```

Do not keep legacy URL compatibility as part of the target:

```text
/win/api/*
/<client>/<agent>/*
/data
/enterprise/:enterpriseId
```

If any old URL is still needed by an external deployment, that is a release blocker requiring an explicit owner decision, not an implicit compatibility layer.

## Deployment Mapping

```text
apps/marketing-web
  deploy: Vercel / Cloudflare Pages
  domain: fiveoranges.ai

apps/platform-web
  deploy: Vercel, Railway, or Cloudflare Pages + Node
  domain: app.fiveoranges.ai

apps/win-web
  deploy: either bundled into platform-web or served as a product UI asset
  domain/path: app.fiveoranges.ai/win

services/platform-api
  deploy: Railway
  public API paths: /api/*
  internal calls: dedicated runtimes

services/platform-api worker entry
  deploy: Railway worker service
  command: yunwei-win-ingest-worker

runtimes/*
  deploy: Railway private services or customer-owned services
  browser access: none
```

## Migration Plan

### Phase 1: Directory Structure Only

Move:

- `landing/` -> `apps/marketing-web/`
- `apps/yunwei-win-web/` -> `apps/win-web/`
- `platform/` -> `services/platform-api/`
- `ops/` -> `scripts/`

Update:

- Dockerfile paths.
- Railway docs.
- Local compose paths.
- README layout.
- `.gitignore`.
- Vite build references.
- Test commands.
- Script paths.

Do not change application behavior in this phase.

### Phase 2: URL Contract

Move browser-facing API routes to the new contract:

- `/api/win/*` for Win product APIs.
- `/api/auth/*` and `/api/me` for auth/session.
- `/api/admin/*` for platform admin.

Remove old URL surfaces instead of redirecting:

- `/win/api/*`
- `/<client>/<agent>/*`
- `/data`
- `/enterprise/:enterpriseId`

### Phase 3: Platform Web

Introduce `apps/platform-web/` as the Next.js portal:

- Own login/register page shell.
- Own `/win`, `/admin`, and `/settings` page routing.
- Call Python APIs through same-origin `/api/*`.
- Keep Python as the source of truth for auth, enterprise scope, entitlements, runtime registry, AI, ingest, and workers.

### Phase 4: Optional Python Service Split

Only split `services/platform-api` into `services/platform-api`, `services/win-api`, and `services/win-worker` if the system has a real need for independent ownership, deploy cadence, scaling, or isolation.

Until then, keeping one Python service is simpler and safer.

## Non-Goals

- Do not rewrite the Python backend into Next.js.
- Do not move AI, OCR, ingestion, or RQ worker logic into the frontend layer.
- Do not put customer-specific dedicated runtime implementations into core platform packages.
- Do not keep legacy URL aliases by default.
- Do not rename every Python import package during Phase 1.

## Verification Checklist

After Phase 1:

```bash
git diff --check
cd services/platform-api && .venv/bin/pytest -q
cd apps/win-web && npm run build
```

Search checks:

```bash
rg "platform/" README.md docs infra scripts apps services
rg "apps/yunwei-win-web|landing/|ops/" README.md docs infra scripts apps services
```

After Phase 2:

```bash
cd services/platform-api && .venv/bin/pytest tests/test_page_routes.py tests/test_yunwei_win_assistant.py tests/test_yunwei_win_assistant_runtime.py -q
cd apps/win-web && npm run build
```

Search checks:

```bash
rg "/win/api|/<client>/<agent>|agents.html|/data|/enterprise/" apps services infra docs
```

Historical migration docs may mention old paths only if clearly marked as archived history and not linked as the current contract.
