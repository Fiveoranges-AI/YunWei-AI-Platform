# Platform-level Chat UI (`agent-platform/app/`) — Design

- **Date**: 2026-05-07
- **Status**: Approved direction; supersedes yinhu-rebuild's per-agent migration design.
- **Branch**: `design/platform-chat-ui` (off `origin/main` at `09a348c`)
- **Inputs (referenced, not duplicated)**:
  - yinhu-rebuild [`design`](../../../../yinhu-rebuild/generated/docs/specs/2026-05-07-assistant-ui-migration-design.md) — most decisions D1, D5–D8 transfer; D2/D3/D4 adjusted below
  - yinhu-rebuild [`spike notes`](../../../../yinhu-rebuild/generated/docs/specs/2026-05-07-assistant-ui-spike-notes.md) — verdict P1, all resolved unknowns are platform-agnostic
- **Reference repos**:
  - Backend: this repo (`agent-platform/`)
  - First customer agent: `~/yunwei-workspaces/yinhu-rebuild/generated/`
  - Future agents: `agents/<client>-<agent>/`

## TL;DR

Replace each agent's per-container chat UI (currently a hand-written `static/index.html`) with a **single Vite + React + TypeScript + Tailwind app at `agent-platform/app/`**, served by the platform's FastAPI catch-all route at `/<client>/<agent>/`. Per-tenant branding (color, font, logo, title) is config-driven via the existing per-agent `GET /me` endpoint, extended to return tenant metadata. New tenant onboarding becomes: insert a `tenants` row + provision a container_url + (if needed) tweak `/me`'s `tenant` block. **Zero UI code per tenant.**

## Why platform-level (not per-agent)

The platform already implements multi-tenant routing (`platform_app/proxy.py`), HMAC signing, ACL, and a `tenants` table keyed by `(client_id, agent_id)`. The agent containers are dumb backends that happen to ship their own UI — that is a historical artifact from the single-tenant origin, not a designed boundary. Centralizing UI:

- Eliminates per-agent Docker stage 1 (no node build per tenant; agent images shrink).
- New tenants ship in hours instead of days (DB row + config, no UI fork).
- Bug fixes and feature additions deploy once for all tenants.
- UI is already a dumb client (all data from API); centralizing UI delivery does not weaken data isolation, which lives at the agent container boundary.

## Key decisions

### D1 — Build pipeline: Vite + React + TypeScript + Tailwind

Same as yinhu spec D1. **`landing/` already uses Vite + React** — consistency, no second framework in the monorepo.

**Not Next.js.** No SSR/SSG/ISR/API-routes/edge-middleware needs (auth-walled, no SEO, FastAPI is the backend, not Vercel-deployed). Next adds complexity without adding value here. Reverse-proxy `<base href>` interaction is cleaner with Vite.

**Not Vue.** assistant-ui is a React-only library; choosing Vue means rebuilding the entire chat surface from scratch and losing the migration's primary ROI.

### D2 — Per-tenant config: extend agent's `GET /me`, no new endpoint

Each agent already exposes `GET /me` (returns `{user, profile}`). Extend it to return:

```json
{
  "user": {...},
  "profile": {...},
  "tenant": {
    "client_id": "yinhu",
    "agent_id": "super-xiaochen",
    "title": "超级小陈",
    "subtitle": "运帷 AI · 银湖租赁",
    "brand_color": "#3A8FB7",
    "brand_color_dark": "#2A6F92",
    "font_family": "Alibaba PuHuiTi 3.0",
    "font_css_url": "/yinhu/super-xiaochen/static/fonts/alibaba-puhuiti.css",
    "logo_url": "/yinhu/super-xiaochen/static/logo.png",
    "available_slash_commands": ["记一下"],
    "onboarding_enabled": true
  }
}
```

UI mounts → fetches `/<client>/<agent>/me` → applies branding via CSS variables + dynamic `<link rel="stylesheet">` insertion for fonts. **No new endpoint; `/me` is the single source of truth for "what tenant am I in".**

Per-tenant assets (logo, custom font woff2) stay served by the agent container at its existing `/static/` mount. Platform's catch_all proxies them through. Generic UI assets (the React bundle, base-href.js, default fallback fonts) are served by platform from `app/dist/`.

### D3 — Backend protocol: P1 (frontend `ChatModelAdapter` parses agent's existing SSE)

**Unchanged from yinhu spec D3 (post-spike verdict).** Each agent emits its existing custom SSE schema (`data: {"type":"text","text":"..."}\n\n` etc.); `app/src/runtime/chatAdapter.ts` parses it. No `assistant-stream` Python lib (rejected — version-skew with JS half).

**Why this works platform-level**: all hermes-based agents speak the same SSE schema. The adapter is one file, lives in `app/`, supports any hermes agent without per-agent code.

### D4 — Conversation history source-of-truth: agent backend

Same as yinhu spec D4 (post-update). The chat adapter POSTs `{message, session_id}` to `/<client>/<agent>/chat`; agent backend pulls history from sqlite and runs the agent. Frontend never persists history; it reads via `/<client>/<agent>/history` on session switch.

### D5 — Auth: platform reverse-proxy + HMAC, unchanged

Browser hits `app.fiveoranges.ai/<client>/<agent>/...` → platform validates session cookie + ACL → HMAC-signs upstream request → proxies to agent's container_url. UI uses `fetch()` with same-origin relative paths; no secrets in bundle. Same model the platform already implements in `proxy.py`.

### D6 — Reverse-proxy `<base href>`: extracted IIFE, same approach as yinhu Task 10

`<base href>` is set client-side by `app/public/base-href.js` (an IIFE that infers the `/<client>/<agent>/` prefix from `location.pathname`). Vite `base: './'` so all asset URLs are relative; combined with `<base href>`, asset requests automatically pick up the tenant prefix. **Production HTML has zero inline `<script>` blocks** — the IIFE is external — making CSP nonce injection a clean no-op.

### D7 — CSP: platform-side nonce injection on the served HTML

The platform's catch_all route serves `app/dist/index.html`. If a CSP nonce header is present (`X-CSP-Nonce`), inject into any inline `<style>`/`<script>` (Vite production has none, so this is defensive). Same logic the agents currently run, just moved to the platform side.

### D8 — Message branch / edit / regenerate: out of scope (same as yinhu spec)

### D9 — Routing inside `app/`: client-side, single SPA, wouter

`app/` mounts at `/<client>/<agent>/` and renders the chat surface. Future routes (`/<client>/<agent>/memory`, `/<client>/<agent>/settings`) added under the same mount. Use `wouter` (already in `landing/`) for client routing — small, no churn for migrating later. **Not implementing extra routes in this migration**; just `/` (chat).

### D10 — Cross-repo phase coordination

Two repos change in coordinated phases:
- `agent-platform`: build new `app/`, modify `platform/Dockerfile` + `main.py:catch_all`
- `yinhu-rebuild`: delete `static/index.html`, drop `web_agent.py:GET /` + StaticFiles mount, extend `/me` with `tenant` block

Phases 1, 3, 4 happen in `agent-platform`. Phase 2 happens in `yinhu-rebuild`. Phase 5 cuts over both at the same time. Details in [Phase Plan](#phased-implementation) below.

## Architecture

```
agent-platform/                            ← THIS REPO
├── platform/
│   ├── Dockerfile                         ← MODIFY: add stage 1 building app/
│   ├── platform_app/
│   │   ├── main.py                        ← MODIFY: catch_all static-vs-proxy split
│   │   ├── proxy.py                       ← UNCHANGED (still proxies API paths)
│   │   └── ...
│   └── static/                            ← UNCHANGED (admin/login pages)
├── landing/                               ← UNCHANGED (fiveoranges.ai marketing)
├── app/                                   ← NEW: app.fiveoranges.ai chat UI
│   ├── package.json
│   ├── vite.config.ts                     ← base: './', outDir: 'dist'
│   ├── tsconfig.json
│   ├── tailwind.config.ts
│   ├── postcss.config.mjs
│   ├── index.html                         ← Vite entry, <script src="./base-href.js"></script>
│   ├── public/
│   │   └── base-href.js                   ← extracted IIFE (reverse-proxy prefix inference)
│   └── src/
│       ├── main.tsx
│       ├── App.tsx                        ← Provider tree: ToastProvider → TenantProvider → ThreadList → Layout
│       ├── runtime/
│       │   ├── chatAdapter.ts             ← ChatModelAdapter: parses hermes SSE → assistant-ui content
│       │   ├── threadListAdapter.ts       ← RemoteThreadListAdapter wrapping /<client>/<agent>/sessions
│       │   ├── threadHistoryAdapter.ts    ← /<client>/<agent>/history → message parts
│       │   └── sseEvents.ts               ← TS types for hermes SSE event schema
│       ├── pages/
│       │   ├── Chat.tsx                   ← /:client/:agent/ route
│       │   └── NotInTenant.tsx            ← shown when URL is missing /<client>/<agent>/ prefix
│       ├── components/                    ← Sidebar, AssistantMessage, ToolCallUI, FollowupChips, SourcesModal, MemoriesPanel, OnboardingModal, Composer, SlashCommands, WelcomeScreen
│       ├── lib/
│       │   ├── api.ts                     ← relative fetch wrapper (uses <base href>)
│       │   ├── tenant-config.ts           ← TenantProvider + useTenant() hook; loads /me on mount
│       │   └── markdown.tsx               ← @assistant-ui/react-markdown config
│       └── styles/
│           ├── globals.css                ← @tailwind + base CSS variables (overridden at runtime by tenant)
│           └── fonts/                     ← generic fallback fonts only; tenant-specific fonts loaded from agent's /static/
├── agents/<client>-<agent>/.env           ← per-agent secrets only, no UI code
└── docs/superpowers/specs/{this file}
```

After Phase 5, in `yinhu-rebuild/generated/`:

```
yinhu-rebuild/generated/
├── static/
│   ├── fonts/                             ← KEEP: alibaba-puhuiti.css + woff2 (served by agent's StaticFiles mount, fetched by app/)
│   └── logo.png                           ← KEEP: tenant logo
│   (index.html + blueprint/  — DELETED in Phase 2)
├── web_agent.py                           ← MODIFY in Phase 2: drop GET /, drop StaticFiles mount of root assets, extend /me with tenant block
├── Dockerfile                             ← MODIFY in Phase 2: drop COPY static/index.html, no node stage
└── (everything else unchanged)
```

## Platform routing change (the core platform-side diff)

`platform/platform_app/main.py:74` `catch_all('/<client>/<agent>/{full_path:path}')` currently proxies all paths to the agent. Modify to split static-vs-proxy:

```python
_APP_DIST = Path(__file__).parent.parent.parent / "app" / "dist"
_NO_STORE = {"cache-control": "no-store"}
_STATIC_PREFIXES = ("assets/", "base-href.js", "favicon.ico")  # served from app/dist/

@app.api_route("/{client_id}/{agent_id}/{full_path:path}",
               methods=["GET","POST","HEAD","PUT","DELETE","PATCH"])
async def catch_all(client_id: str, agent_id: str, full_path: str, request: Request):
    # tenant existence + ACL check (existing logic)
    user = await _require_session_and_acl(request, client_id, agent_id)

    # 1. Serve the SPA shell from app/dist/ for the root path
    if request.method == "GET" and full_path in ("", "index.html"):
        html = (_APP_DIST / "index.html").read_text(encoding="utf-8")
        nonce = request.headers.get("x-csp-nonce", "")
        if nonce:
            html = html.replace("<script>", f'<script nonce="{nonce}">')
            html = html.replace("<style>", f'<style nonce="{nonce}">')
        return HTMLResponse(html, headers=_NO_STORE)

    # 2. Serve hashed assets from app/dist/
    if request.method == "GET" and any(full_path.startswith(p) for p in _STATIC_PREFIXES):
        path = _APP_DIST / full_path
        if not path.is_file():
            raise HTTPException(404)
        return FileResponse(path)

    # 3. Everything else: API requests → reverse_proxy to agent (current behaviour)
    return await reverse_proxy(
        request, client_id=client_id, agent_id=agent_id,
        user=user, subpath=full_path,
    )
```

The agent container's `/static/` (font files, logo) is reached via case 3 (`full_path = "static/fonts/..."` → proxied to agent's existing `StaticFiles` mount).

## Data flow

### Mount → tenant config → render

```
1. Browser GET /yinhu/super-xiaochen/
   ↓ platform catch_all → serves app/dist/index.html (with <base href> injected client-side)
   ↓ HTML loads /<base>/assets/index-XXX.js
   ↓ React mounts, App.tsx
2. <TenantProvider> in App.tsx fetch('me')
   ↓ platform proxies to yinhu agent's GET /me
   ↓ returns {user, profile, tenant: {brand_color, font_css_url, ...}}
3. TenantProvider sets CSS vars: --yw-accent: <tenant.brand_color>; injects <link rel="stylesheet" href={tenant.font_css_url}>
4. <Chat> renders for the tenant; useLocalRuntime(chatAdapter) ready
```

### User sends a message

```
Composer submit → chatAdapter.run({messages, abortSignal})
  ↓
  POST chat (relative) → resolves to /yinhu/super-xiaochen/chat via <base href>
  body: {message: <text>, session_id: currentSessionId}
  signal: abortSignal
  ↓
  platform proxy → HMAC sign → yinhu agent's POST /chat
  ↓
  agent _agent_stream yields SSE events
  ↓
  chatAdapter parses SSE, accumulates, yields cumulative {content, metadata}
  ↓
  AssistantMessage / ToolCallUI / FollowupChips / SourcesModal render
```

Identical to the per-agent design's data flow except the URL prefix path. Adapter is unchanged.

## Component tree

Identical to yinhu spec's component tree, with one new wrapper:

```
<App>
  ├── <ToastProvider>
  ├── <TenantProvider>                          ← NEW: loads /me, provides {user, profile, tenant} via useTenant()
  ├── <Router>                                  ← wouter
  │     ├── Route /:client/:agent/ → <Chat>
  │     └── Route * → <NotInTenant>
  └── inside <Chat>:
       <ThreadListProvider> → <Layout>           ← exactly as yinhu spec, brand applied via CSS variables from useTenant()
```

## Phased implementation (cross-repo)

| Phase | Repo | PR content | Completion criterion |
|---|---|---|---|
| 0 | yinhu-rebuild | spike (DONE 2026-05-07) | spike-notes verdict P1 |
| 1 | **agent-platform** | `app/` Vite+React+TS+Tailwind scaffold, hello-world, public/base-href.js, multi-stage `platform/Dockerfile`, `main.py:catch_all` static-vs-proxy split | platform docker image serves new SPA at `/<client>/<agent>/`; existing tenants still work because their agents still serve `static/index.html` as fallback (catch_all hits case 1 first, but if you DELETE app/dist/ at this stage, case 3 falls through to current behaviour — Phase 1 ships a working hello world so this is non-issue) |
| 2 | **yinhu-rebuild** | drop `web_agent.py:GET /` + StaticFiles root mount; extend `/me` with `tenant` block; delete `static/index.html` + `static/blueprint/` (keep `static/fonts/` + `static/logo.png` accessible via narrower StaticFiles mount); update Dockerfile to remove `COPY static/index.html` | yinhu agent serves API only;`/me` returns tenant block;`/yinhu/super-xiaochen/static/fonts/...` still resolves through proxy |
| 3 | agent-platform | `app/` core chat: chatAdapter + threadListAdapter + Sidebar + AssistantMessage + Markdown + Composer; followups/sources stub | e2e: load `/<client>/<agent>/`, send message, see streaming response (via yinhu agent in dev) |
| 4 | agent-platform | ToolCallUI + SourcesModal + ModelBadge + tool_lineage merge | tool calls render with data-source modal showing lineage |
| 5 | agent-platform | FollowupChips + OnboardingModal + MemoriesPanel + /记一下 + tenant config consumption | 1:1 feature parity with legacy yinhu UI; **deploy both repos at the same time, cut traffic** |

**Branch strategy**:
- `agent-platform`: this branch (`design/platform-chat-ui`) holds spec + Phase 1+ plans. Phase 1 PR opens against `main` once spec is approved. Phases 3–5 are subsequent PRs against `main`.
- `yinhu-rebuild`: existing `design/assistant-ui-migration` branch is **abandoned** (kept for thinking record). New branch `feat/platform-ui-cutover` for Phase 2's small change set.

## Cross-repo cutover safety

Phase 1 is a no-op for end users (UI lives in `app/dist/` but agents still serve their own UI). Phase 2 makes yinhu's agent backend API-only and breaks its standalone UI — but **end users go through the platform**, which has the new UI by Phase 1. So end users see continuity throughout.

If Phase 5 fails post-deploy: revert the `app/` PR on platform (rollback ~5 min), revert yinhu Phase 2 PR (rollback ~5 min), redeploy both. Old code path restored. Total ~15 min downtime worst case. No 30-second env-var rollback, but acceptable for this migration scale.

## Out-of-scope

- Migrating `landing/` (marketing site), `platform/static/admin.html`, `platform/static/login.html`, `platform/static/agents.html` — those stay as-is.
- Other tenant-facing routes inside `app/` (memory editor, settings) — future work; this migration ships chat only.
- Multi-tenant unit tests for `app/` — first tenant is yinhu; second-tenant fixtures added when a second tenant is provisioned.
- @assistant-ui/react-ai-sdk, assistant-stream — rejected by Phase 0 spike, not used.
- Visual 1:1 pixel parity with the legacy yinhu UI — accepted tradeoff (yinhu spec D2).

## Open questions for plan stage

- The agent's `/me` extension: should `tenant` be a pure DB-driven projection (read from `tenants` table by platform, injected into the response by proxy) or stay agent-implemented (each agent's `/me` reads its own env vars and returns)? Platform-driven is more centralized; agent-driven is simpler and matches current ownership. **Recommend: agent-driven for now (no platform proxy mutation), revisit if it churns.**
- `useChatModelAdapter` thread-switch state reset — same open question as yinhu spec; covered by a vitest case in Phase 3 plan.
- `makeAssistantToolUI` fallback "register one component for all tool names" — needs first-step verification in Phase 4 plan.

## References

- [yinhu-rebuild design spec](../../../../yinhu-rebuild/generated/docs/specs/2026-05-07-assistant-ui-migration-design.md) — D1, D5–D8, error handling, test strategy, Out-of-scope all transfer with minor adjustments
- [yinhu-rebuild Phase 0 spike notes](../../../../yinhu-rebuild/generated/docs/specs/2026-05-07-assistant-ui-spike-notes.md) — verdict P1, all resolved unknowns
- [yinhu-rebuild Phase 1 plan](../../../../yinhu-rebuild/generated/docs/plans/2026-05-07-assistant-ui-migration-phase-1-scaffold.md) — ~6 of 12 tasks (Vite config, Tailwind tokens, base-href.js, hello-world bootstrap, first build) lift directly into agent-platform's Phase 1 plan, only paths change
- assistant-ui docs: https://www.assistant-ui.com/
- Platform v2 customer isolation: `agent-platform/docs/v2.0-customer-isolation.md`
