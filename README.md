# YunWei AI Platform

The platform behind **app.fiveoranges.ai** — an authenticated product
portal that serves the **智通客户 (`/win/`)** customer-relationship
product, with optional dedicated AI runtimes for Pro/Max tenants.

```
fiveoranges.ai          → marketing site         (apps/marketing-web)
app.fiveoranges.ai/     → authed → /win/         (platform_app)
app.fiveoranges.ai/win/ → 智通客户 SPA          (yunwei_win + apps/win-web)
```

> 📐 **Architecture overview:** [`docs/architecture/platform-v3.md`](docs/architecture/platform-v3.md)
> 🗂️ **Repo structure proposal:** [`docs/architecture/repo-structure-v2.md`](docs/architecture/repo-structure-v2.md)
> 🚢 **Deploy:** [`infra/railway/platform-api.md`](infra/railway/platform-api.md)
> 🧹 **What changed in v3:** [`docs/migration/legacy-removal.md`](docs/migration/legacy-removal.md)

---

## Repo layout

```
agent-platform/
├── apps/
│   ├── marketing-web/            # fiveoranges.ai marketing site (separate Vercel project)
│   └── win-web/                  # /win/ React SPA (Vite + TypeScript)
│
├── services/
│   └── platform-api/             # FastAPI monolith (control plane + product backend)
│       ├── platform_app/         #   control plane — auth, enterprise, plan, entitlements,
│       │                         #   runtime registry, HMAC proxy, admin, audit
│       ├── yunwei_win/           #   product backend — customer profile, ingestion,
│       │                         #   shared assistant, dedicated-runtime adapter
│       │                         #   mounted at /api/win/*
│       ├── migrations/           #   SQL migrations (auto-run on startup)
│       ├── prompts/              #   LLM prompts (shared across extractors)
│       ├── static/               #   login.html, register.html
│       ├── tests/                #   pytest — requires Postgres + Redis on :5433 / :6380
│       ├── Dockerfile            #   multi-stage: builds frontend + Python svc
│       └── pyproject.toml
│
├── runtimes/
│   ├── README.md                 # contract dedicated runtimes must satisfy
│   └── examples/                 # opt-in compose files for example runtimes
│
├── infra/
│   ├── local/                    # docker-compose stack for dev/staging
│   └── railway/                  # Railway deploy notes
│
├── scripts/
│   ├── bootstrap-dev.sh          # seed admin user + enterprise (v3-compatible)
│   └── sync-silver-canonical.py
│
├── docs/
│   ├── architecture/             # current architecture docs
│   ├── migration/                # v2 → v3 migration log + archived v1/v2 docs
│   └── superpowers/              # implementation plans + specs
│
├── AGENTS.md                     # AI-agent guidance (Codex / generic)
├── CLAUDE.md                     # AI-agent guidance (Claude Code)
├── coding-principle.md           # team coding conventions
└── README.md                     # this file
```

The Python import packages (`platform_app`, `yunwei_win`) are unchanged
by the Phase 1 directory move; only their filesystem location changed.
See [`docs/architecture/repo-structure-v2.md`](docs/architecture/repo-structure-v2.md)
for the full rationale and future phases.

---

## Quickstart — local dev

### Prerequisites

- Python 3.14, `uv` for dependency install (or `pip`)
- Node 20+, `npm`
- Postgres (local or remote), Redis
- A `.env` at repo root — copy from `.env.example` and fill in:
  `DATABASE_URL`, `REDIS_URL`, `COOKIE_SECRET`,
  `ANTHROPIC_API_KEY`, `MISTRAL_API_KEY`, `LANDINGAI_API_KEY`.

### Backend

```bash
cd services/platform-api
uv sync                              # creates .venv with all deps
./.venv/bin/uvicorn platform_app.main:app --reload --port 8000
```

Migrations run automatically on startup. The first time you boot, seed
an admin + enterprise:

```bash
./scripts/bootstrap-dev.sh
```

(Override `ADMIN_BOOTSTRAP_USER`, `ADMIN_BOOTSTRAP_PASSWORD`,
`BOOTSTRAP_ENTERPRISE_ID`, `BOOTSTRAP_ENTERPRISE_NAME` via env to
customize.)

### Frontend

```bash
cd apps/win-web
npm install
npm run dev                          # Vite dev server on :5173
# OR for a one-off build that the FastAPI process can serve:
npm run build                        # writes dist/ that /win/ reads
```

`/win/` returns the SPA if `apps/win-web/dist` exists, otherwise
a `503 win_not_built` for clearer dev feedback.

> **🏭 锦泰耐火材料 demo:** A frontend-only customer-pitch demo lives inside the same SPA at the
> `锦泰试点 / jintai` tab. Pure mock data, no backend wiring. See
> [`apps/win-web/JINTAI_DEMO.md`](apps/win-web/JINTAI_DEMO.md) for scope, scripted walkthrough, and the
> 7 hook points needed for a real backend.

The marketing site lives at `apps/marketing-web/` and deploys
independently to Vercel — see `apps/marketing-web/` for its own README
if you need to run it locally.

### Tests

```bash
cd services/platform-api && ./.venv/bin/pytest -q
```

The autouse fixture truncates all DB tables between tests, so the test
DB on `:5433` is destructive. Use a separate Postgres instance from
your dev data.

---

## Deploy

Production runs on Railway as **two services** sharing one Docker
image (`services/platform-api/Dockerfile`):

1. **`platform-app`** — FastAPI web. CMD is the default (`uvicorn`).
2. **`win-ingest-worker`** — RQ worker. Start Command:
   `yunwei-win-ingest-worker`.

Both services need the same `DATABASE_URL`, `REDIS_URL`, and
(when `STORAGE_BACKEND=local`) the same `/data` volume.

Full env-var checklist + promote/rollback flow:
[`infra/railway/platform-api.md`](infra/railway/platform-api.md).

For local docker-compose: [`infra/local/README.md`](infra/local/README.md).

---

## Architecture in one paragraph

`platform_app` is the **control plane** — auth, enterprise, plan,
entitlements, runtime registry, HMAC reverse proxy, admin. It
populates `request.state.auth_context` for every `/api/win/*` call
from the session cookie; the customer's `enterprise_id` is **never**
trusted from request bodies or LLM tool inputs.

`yunwei_win` is the **product backend** mounted at `/api/win/*` —
customer profile, document ingestion (OCR + extractor providers via
the modular ingest pipeline), customer memory, and the
**shared assistant** (`/api/win/assistant/chat`) for Free/Lite users.

Pro/Max enterprises can bind a **dedicated runtime** for a capability
(`assistant`, `daily_report`, `erp_sync`, …) in the runtime registry.
The shared assistant endpoint transparently forwards to the bound
runtime, falling back to the shared path on
`DedicatedRuntimeError` or `runtime.health == "unhealthy"`.

Provider plumbing for ingest (`OCR_PROVIDER`,
`EXTRACTOR_PROVIDER`) is documented in
[`docs/superpowers/specs/2026-05-12-modular-ocr-extractor-design.md`](docs/superpowers/specs/2026-05-12-modular-ocr-extractor-design.md).

---

## Working with AI agents

This repo is configured to be agent-friendly:

- **[`CLAUDE.md`](CLAUDE.md)** — guidance for Claude Code sessions.
- **[`AGENTS.md`](AGENTS.md)** — guidance for Codex / generic agents.
- **[`coding-principle.md`](coding-principle.md)** — team conventions
  (think before coding, surgical changes, minimal code).
- **[`docs/superpowers/plans/`](docs/superpowers/plans/)** —
  implementation plans for large changes; each one is self-contained
  enough that a fresh agent can execute it task-by-task.

When you ask an agent to "execute the plan at `docs/superpowers/plans/<file>.md`",
they'll use the `superpowers:executing-plans` skill (Claude Code) to
walk through each numbered task, run verifications, and produce
atomic commits.

---

## Where things live

| Looking for… | Path |
|---|---|
| Current architecture | `docs/architecture/platform-v3.md` |
| Repo structure proposal | `docs/architecture/repo-structure-v2.md` |
| What was deleted in v3 | `docs/migration/legacy-removal.md` |
| Old plans (v1/v2 era) | `docs/migration/archive/` |
| Active implementation plans | `docs/superpowers/plans/` |
| LLM provider design notes | `docs/superpowers/specs/` |
| Runtime contract (Pro+) | `runtimes/README.md` |
| Railway deploy notes | `infra/railway/platform-api.md` |
| Local docker compose | `infra/local/docker-compose.yml` |
| Database schema | `services/platform-api/migrations/` |
| API routes (control plane) | `services/platform-api/platform_app/*_api.py` |
| API routes (product) | `services/platform-api/yunwei_win/api/` |

---

## Status

- v3 restructure landed in PR #77 (May 2026): `yinhu_brain` → `yunwei_win`,
  `/` → `/win/`, `AuthContext` + entitlements, shared assistant + dedicated
  runtime adapter, runtime registry, legacy dashboard archived.
- URL canonicalization (PR #79): browser API surface unified onto
  `/api/auth/*`, `/api/me`, `/api/win/*`, `/api/admin/*`,
  `/api/enterprise/*`. Legacy `/win/api/*`, `/<client>/<agent>/*`,
  `/data`, `/enterprise/:id` deleted outright.
- Repo structure v2 Phase 1 (branch `chore/repo-structure-v2`):
  `landing/` → `apps/marketing-web/`, `apps/yunwei-win-web/` → `apps/win-web/`,
  `platform/` → `services/platform-api/`, `ops/` → `scripts/`.
  Python import packages unchanged.

## License

Proprietary. © Five Oranges AI.
