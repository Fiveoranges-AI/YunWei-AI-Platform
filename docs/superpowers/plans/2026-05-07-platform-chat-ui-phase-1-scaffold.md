# Platform Chat UI — Phase 1 Scaffold Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up a Vite+React+TS+Tailwind app at `agent-platform/app/`, build it via a multi-stage Dockerfile, and add a static-vs-proxy routing split in `platform_app/main.py:catch_all` so `/<client>/<agent>/` serves the new SPA shell while everything else continues to reverse-proxy to the agent — with a deploy-safe fallback that no-ops when `app/dist/` is empty.

**Architecture:** `app/` is a self-contained Vite project (mirrors `landing/`'s tooling: React 19 + Vite 7 + TS 5.6 + Tailwind 4 via `@tailwindcss/vite`). It builds to `app/dist/`. The platform's existing FastAPI catch-all gains a new branch: if the request matches the SPA root or a known static prefix AND `app/dist/index.html` exists on disk, serve it; otherwise fall through to the current reverse-proxy behavior. Phase 1 ships a hello-world page only — chat logic is Phase 3+.

**Tech Stack:**
- Frontend: Vite 7 + React 19 + TypeScript 5.6 + Tailwind 4 (`@tailwindcss/vite`) — versions matched to `landing/package.json`
- Build: multi-stage Docker, stage 1 `node:20-alpine`, stage 2 `python:3.13-slim` (existing platform base)
- Backend: FastAPI catch_all gets a static-vs-proxy split with deploy-safe fallback (no-op when `app/dist/` missing)

**Branch:** `design/platform-ui` (currently at `d9f78d5`, off `main`).

---

## Pre-flight context for implementer subagents

- Repo root: `/Users/eason/agent-platform/`. Worktree we are operating from: `/Users/eason/agent-platform/.worktrees/platform-ui` on branch `design/platform-ui`.
- The primary spec lives at `docs/superpowers/specs/2026-05-07-platform-chat-ui-design.md` — read sections "Platform routing change" and "Phased implementation" before touching `main.py`.
- The reference repos and references:
  - `landing/package.json` + `landing/vite.config.ts` — version baseline & plugin choices
  - `landing/tsconfig.json` — TypeScript baseline; we'll simplify (no `client/` subdir, no path aliases yet)
  - `platform/platform_app/main.py:75-109` — the catch_all we'll modify
  - `platform/platform_app/firewall.py` — already permits same-origin GET subresource loads via referer-prefix; no change needed
  - `platform/platform_app/proxy.py:17 reverse_proxy(...)` — signature stays the same
  - `platform/Dockerfile` — current single-stage python image; becomes multi-stage
- Phase 1 ships a **deploy-safe fallback**: if `app/dist/index.html` does not exist at request time (e.g. the platform image was built before stage 1 started populating it), the new branch is bypassed and the route behaves exactly as today. This means Phase 1 can deploy to prod independently of any Phase 3+ work.
- **Do NOT** install `@assistant-ui/react`, `wouter`, or any chat libs in this phase. Hello world only. Future phases install them.
- Per-tenant branding (color override, font, logo) is **out of scope for Phase 1**. The scaffold uses a hardcoded brand color `#3A8FB7` and generic system fonts. Per-tenant `/me` consumption is Phase 5.

---

## File Structure

After this phase:

```
agent-platform/                              ← existing
├── .gitignore                               ← MODIFY: add /app/node_modules, /app/dist
├── app/                                     ← NEW
│   ├── package.json
│   ├── package-lock.json                    ← committed for deterministic builds
│   ├── tsconfig.json
│   ├── vite.config.ts                       ← base:'./', outDir:'dist', emptyOutDir:true
│   ├── index.html                           ← Vite entry; loads external base-href.js
│   ├── public/
│   │   └── base-href.js                     ← extracted IIFE for reverse-proxy prefix
│   └── src/
│       ├── main.tsx
│       ├── App.tsx                          ← hello-world, brand color
│       └── styles/
│           └── globals.css                  ← @import "tailwindcss"; CSS variables
├── platform/
│   ├── Dockerfile                           ← MODIFY: multi-stage (node + python)
│   ├── platform_app/
│   │   └── main.py                          ← MODIFY: catch_all static-vs-proxy split
│   └── tests/
│       └── test_platform_chat_ui_routing.py ← NEW: catch_all routing tests
└── docs/superpowers/plans/
    └── 2026-05-07-platform-chat-ui-phase-1-scaffold.md  ← this file
```

Nothing is deleted in Phase 1.

---

## Task 1: Bootstrap `app/` with `package.json`

**Files:**
- Create: `app/package.json`

- [ ] **Step 1.1: Create `app/` directory**

```bash
mkdir -p /Users/eason/agent-platform/.worktrees/platform-ui/app
cd /Users/eason/agent-platform/.worktrees/platform-ui/app
```

- [ ] **Step 1.2: Write `app/package.json`**

Versions match `landing/package.json` so the monorepo runs one toolchain.

```json
{
  "name": "agent-platform-app",
  "private": true,
  "version": "0.1.0",
  "type": "module",
  "description": "agent-platform chat UI (app.fiveoranges.ai/<client>/<agent>/) — Phase 1 scaffold",
  "scripts": {
    "dev": "vite --host",
    "build": "tsc --noEmit && vite build",
    "preview": "vite preview --host",
    "check": "tsc --noEmit"
  },
  "dependencies": {
    "react": "^19.2.1",
    "react-dom": "^19.2.1"
  },
  "devDependencies": {
    "@tailwindcss/vite": "^4.1.14",
    "@types/react": "^19.0.0",
    "@types/react-dom": "^19.0.0",
    "@vitejs/plugin-react": "^5.0.4",
    "tailwindcss": "^4.1.14",
    "typescript": "5.6.3",
    "vite": "^7.1.7"
  },
  "engines": {
    "node": ">=20"
  }
}
```

- [ ] **Step 1.3: Run `npm install`**

```bash
cd /Users/eason/agent-platform/.worktrees/platform-ui/app
npm install
```

Expected: `node_modules/` populated, `package-lock.json` created. Record the actual locked versions in your task report. If any `^` resolves to a major bump beyond what `landing/` uses, pin to landing's exact version.

- [ ] **Step 1.4: Smoke-test `npx vite --version`**

```bash
npx vite --version
```

Expected: prints something like `7.1.7`. Confirms Vite is callable. No commit yet.

---

## Task 2: TypeScript + Vite configuration

**Files:**
- Create: `app/tsconfig.json`
- Create: `app/vite.config.ts`

- [ ] **Step 2.1: Write `app/tsconfig.json`**

Simpler than `landing/`'s — no client/ subdir, no path aliases yet (add when needed).

```json
{
  "include": ["src/**/*", "vite.config.ts"],
  "exclude": ["node_modules", "dist", "**/*.test.ts"],
  "compilerOptions": {
    "incremental": true,
    "tsBuildInfoFile": "./node_modules/typescript/tsbuildinfo",
    "target": "ES2022",
    "lib": ["esnext", "dom", "dom.iterable"],
    "jsx": "preserve",
    "module": "ESNext",
    "moduleResolution": "bundler",
    "allowImportingTsExtensions": true,
    "resolveJsonModule": true,
    "isolatedModules": true,
    "noEmit": true,
    "strict": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "noFallthroughCasesInSwitch": true,
    "esModuleInterop": true,
    "skipLibCheck": true,
    "types": ["node", "vite/client"]
  }
}
```

- [ ] **Step 2.2: Write `app/vite.config.ts`**

```typescript
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  // base: "./" emits relative asset paths so the same bundle works under
  // any reverse-proxy prefix (e.g. /yinhu/super-xiaochen/) without rebuild.
  // The runtime <base href> injection in public/base-href.js translates
  // them into absolute tenant-prefixed URLs at load time.
  base: "./",
  build: {
    outDir: "dist",
    emptyOutDir: true,
    sourcemap: true,
    target: "es2022",
  },
  server: {
    port: 5174,
    strictPort: false,
    host: true,
  },
});
```

> Port 5174 chosen so it doesn't collide with `landing/` (port 3000). Phase 1 has no dev-server-to-platform proxy; that's a Phase 3 concern.

- [ ] **Step 2.3: Verify the type-check works on the empty project**

```bash
cd /Users/eason/agent-platform/.worktrees/platform-ui/app
npx tsc --noEmit
```

Expected: no errors (project is currently just configs; nothing to type-check yet — passes vacuously).

---

## Task 3: Tailwind 4 globals.css with brand tokens

Tailwind 4 ships its config in CSS via `@theme` blocks; no separate `tailwind.config.ts` needed for Phase 1.

**Files:**
- Create: `app/src/styles/globals.css`

- [ ] **Step 3.1: Write `app/src/styles/globals.css`**

```css
@import "tailwindcss";

@theme {
  --color-brand-blue: #3A8FB7;
  --color-brand-blue-dark: #2A6F92;
  --color-brand-blue-darker: #1F567A;
}

:root {
  --brand-blue: #3A8FB7;
  --brand-blue-dark: #2A6F92;
  --brand-blue-darker: #1F567A;
}

html,
body {
  margin: 0;
  padding: 0;
  height: 100%;
  font-family:
    "PingFang SC",
    "Hiragino Sans GB",
    "Microsoft YaHei",
    -apple-system,
    BlinkMacSystemFont,
    "Helvetica Neue",
    sans-serif;
  -webkit-font-smoothing: antialiased;
  font-feature-settings: "tnum";
}

#root {
  min-height: 100%;
}
```

> No tenant fonts here. Generic CN system fallback is good enough for Phase 1 hello-world. Tenant fonts arrive via `/me` in Phase 5 and load on the fly.

---

## Task 4: Extract `<base href>` IIFE into `public/base-href.js`

The same IIFE approach used by yinhu's legacy static UI — preserve verbatim so future phases can move chat logic across without changing this file.

**Files:**
- Create: `app/public/base-href.js`

- [ ] **Step 4.1: Create `public/` and write the IIFE**

```bash
mkdir -p /Users/eason/agent-platform/.worktrees/platform-ui/app/public
```

Then create `app/public/base-href.js` with this exact content:

```javascript
(function () {
  // Infer /<client>/<agent>/ prefix from URL so the same bundle works behind
  // platform reverse proxy AND at the bare root in dev. Must run before any
  // module script so relative URLs in CSS/JS resolve correctly.
  var m = location.pathname.match(/^(\/[^/]+\/[^/]+\/)/);
  var base = document.createElement('base');
  base.href = m ? m[1] : '/';
  document.head.appendChild(base);
})();
```

- [ ] **Step 4.2: Verify Vite copies `public/` to dist root**

`public/` files are copied as-is to `dist/` by Vite (no fingerprinting). So `app/public/base-href.js` lands at `app/dist/base-href.js` after build, accessible at `/<client>/<agent>/base-href.js` once the platform serves it.

No code to write here — mental check that the path will resolve at runtime.

---

## Task 5: Vite entry `index.html` + React bootstrap

**Files:**
- Create: `app/index.html`
- Create: `app/src/main.tsx`
- Create: `app/src/App.tsx`

- [ ] **Step 5.1: Write `app/index.html`**

```html
<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width,initial-scale=1" />
    <title>运帷 AI · 平台 chat UI</title>
    <!--
      Reverse-proxy <base href> inference. MUST run before any module script
      so relative URLs in CSS/JS resolve correctly under platform reverse-
      proxy paths like /yinhu/super-xiaochen/. External (not inline) so
      CSP-strict deployments work without a nonce.
    -->
    <script src="./base-href.js"></script>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

- [ ] **Step 5.2: Write `app/src/main.tsx`**

```tsx
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "./styles/globals.css";
import { App } from "./App";

const rootEl = document.getElementById("root");
if (!rootEl) {
  throw new Error("missing #root element in index.html");
}

createRoot(rootEl).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
```

- [ ] **Step 5.3: Write `app/src/App.tsx` (hello-world placeholder)**

```tsx
export function App() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-gray-50">
      <div className="text-center">
        <h1
          className="text-4xl font-semibold"
          style={{ color: "var(--brand-blue)" }}
        >
          运帷 AI · 平台 chat UI · Phase 1 scaffold
        </h1>
        <p className="mt-3 text-sm text-gray-500">
          tenant routing active — Phase 3 wires chat
        </p>
        <p className="mt-8 font-mono text-xs text-gray-400">
          build mode: {import.meta.env.MODE}
        </p>
      </div>
    </div>
  );
}
```

> Brand color is applied via inline `style` reading the CSS variable, exactly the path Phase 5's `/me`-driven theming will use. This validates the variable plumbing end-to-end on a hello-world.

---

## Task 6: First successful Vite build → output to `app/dist/`

**Files:** none modified (build artifacts only)

- [ ] **Step 6.1: Run the build**

```bash
cd /Users/eason/agent-platform/.worktrees/platform-ui/app
npm run build
```

Expected: `tsc --noEmit` passes, `vite build` completes, prints:

```
vite v7.x.x building for production...
✓ N modules transformed.
dist/index.html              ~0.5 kB
dist/base-href.js            ~0.3 kB
dist/assets/index-XXX.css    ~30-50 kB (Tailwind)
dist/assets/index-XXX.js     ~140-160 kB (React + app)
```

If the build fails:
- TypeScript errors → fix in `src/*.tsx` (most likely strict mode catching unused vars)
- "Failed to resolve `tailwindcss`" → npm install didn't pull it; re-run `npm install`

- [ ] **Step 6.2: Verify the build output**

```bash
ls /Users/eason/agent-platform/.worktrees/platform-ui/app/dist/
ls /Users/eason/agent-platform/.worktrees/platform-ui/app/dist/assets/
```

Expected: `index.html`, `base-href.js`, `assets/` containing hashed JS/CSS.

- [ ] **Step 6.3: Inspect built `index.html` for inline-script absence**

```bash
cat /Users/eason/agent-platform/.worktrees/platform-ui/app/dist/index.html
```

Expected:
- `<title>运帷 AI · 平台 chat UI</title>`
- `<script src="./base-href.js"></script>` — relative path preserved
- `<script type="module" crossorigin src="./assets/index-XXX.js"></script>`
- `<link rel="stylesheet" crossorigin href="./assets/index-XXX.css">`
- **No** non-`src` inline `<script>` blocks (otherwise platform's CSP nonce-replace logic would mutate them).

If `grep -n '<script>' app/dist/index.html` returns any matches that aren't `<script src=` or `<script type="module" src=`, investigate.

- [ ] **Step 6.4: Local serve smoke test**

```bash
cd /Users/eason/agent-platform/.worktrees/platform-ui/app
npm run preview -- --port 4174
```

Open `http://localhost:4174/` in a browser. Expected:
- Page renders "运帷 AI · 平台 chat UI · Phase 1 scaffold" in brand blue
- Subtitle in grey, build mode "production" shown
- DevTools console: no errors
- DevTools elements panel: `<base href="/">` injected by base-href.js (URL is bare `/`)

Kill `npm run preview` when done.

---

## Task 7: Add `.gitignore` rules for `app/`

**Files:**
- Modify: `.gitignore` (repo root)

- [ ] **Step 7.1: Append `app/` rules to `.gitignore`**

Open `/Users/eason/agent-platform/.worktrees/platform-ui/.gitignore` and append:

```gitignore

# app/ (platform chat UI — Phase 1+) build artifacts. Stage 1 of platform/
# Dockerfile rebuilds dist/ from source.
/app/node_modules/
/app/dist/
```

- [ ] **Step 7.2: Verify git sees the build artifacts as ignored**

```bash
cd /Users/eason/agent-platform/.worktrees/platform-ui
git status --ignored | grep -E '(node_modules|dist)' | head -10
```

Expected output should mention `app/node_modules/` and `app/dist/` under "Ignored files". If `git status` shows `app/node_modules/` or `app/dist/index.html` as untracked, the `.gitignore` rule didn't take.

---

## Task 8: Write failing tests for catch_all static-vs-proxy split (TDD)

We TDD this so the routing changes are nailed by tests before the implementation lands.

**Files:**
- Create: `platform/tests/test_platform_chat_ui_routing.py`

- [ ] **Step 8.1: Create the test file with all four cases**

```python
"""Phase 1 platform chat UI routing tests.

Verifies the catch_all static-vs-proxy split:
- GET /<client>/<agent>/ serves app/dist/index.html (when present)
- GET /<client>/<agent>/index.html serves app/dist/index.html
- GET /<client>/<agent>/assets/<file> serves from app/dist/assets/
- GET /<client>/<agent>/base-href.js serves from app/dist/
- Non-static subpaths fall through to reverse_proxy
- If app/dist/index.html does NOT exist (deploy-safe fallback), every
  request falls through to reverse_proxy (Phase 1 ships independently
  of when app/dist/ is populated).
"""
from __future__ import annotations
import time
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from platform_app import auth, db
from platform_app.main import app


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def authed_session():
    db.init()
    db.main().execute(
        "INSERT INTO users (id, username, password_hash, display_name, created_at) "
        "VALUES (%s,%s,%s,%s,%s)",
        ("u_chat", "chatuser", auth.hash_password("p"), "Chat User", int(time.time())),
    )
    db.main().execute(
        "INSERT INTO acls (user_id, client_id, agent_id) VALUES (%s,%s,%s)",
        ("u_chat", "yinhu", "super-xiaochen"),
    )
    sid, _ = auth.create_session("u_chat", "127.0.0.1", "test")
    return sid


# --- helpers ---------------------------------------------------------------

NAV_HEADERS = {
    "sec-fetch-mode": "navigate",
    "sec-fetch-site": "same-origin",
}
SUBRESOURCE_HEADERS = {
    "sec-fetch-mode": "no-cors",
    "sec-fetch-site": "same-origin",
    "referer": "http://testserver/yinhu/super-xiaochen/",
}


@pytest.fixture
def fake_app_dist(tmp_path, monkeypatch):
    """Point platform_app.main._APP_DIST at a tmp dir with a fake build.

    Yields the dist Path so tests can write/delete index.html as needed.
    catch_all derives index/asset paths from _APP_DIST inside the function,
    so a single monkeypatch is sufficient (no derived constants to update).
    """
    from platform_app import main as main_mod

    dist = tmp_path / "app" / "dist"
    dist.mkdir(parents=True)
    # Include a bare <script> + <style> so the CSP nonce-injection branch is
    # actually exercised (rather than no-op'd by the absence of inline tags).
    (dist / "index.html").write_text(
        "<!doctype html><html><head>"
        "<title>运帷 AI · 平台 chat UI</title>"
        "<script src=\"./base-href.js\"></script>"
        "<script>window.__BOOT__ = 1;</script>"
        "<style>body{color:red}</style>"
        "</head><body><div id=root></div></body></html>",
        encoding="utf-8",
    )
    (dist / "base-href.js").write_text("(function(){})();", encoding="utf-8")
    assets = dist / "assets"
    assets.mkdir()
    (assets / "index-deadbeef.js").write_text("/* fake bundle */", encoding="utf-8")

    monkeypatch.setattr(main_mod, "_APP_DIST", dist)
    return dist


# --- positive cases (app/dist populated) -----------------------------------


def test_root_serves_spa_shell(client, authed_session, fake_app_dist):
    r = client.get(
        "/yinhu/super-xiaochen/",
        cookies={"app_session": authed_session},
        headers=NAV_HEADERS,
    )
    assert r.status_code == 200
    assert "<title>运帷 AI · 平台 chat UI</title>" in r.text
    assert r.headers.get("cache-control", "").lower().startswith("no-store")


def test_index_html_serves_spa_shell(client, authed_session, fake_app_dist):
    r = client.get(
        "/yinhu/super-xiaochen/index.html",
        cookies={"app_session": authed_session},
        headers=NAV_HEADERS,
    )
    assert r.status_code == 200
    assert "<title>运帷 AI · 平台 chat UI</title>" in r.text


def test_assets_served_from_app_dist(client, authed_session, fake_app_dist):
    r = client.get(
        "/yinhu/super-xiaochen/assets/index-deadbeef.js",
        cookies={"app_session": authed_session},
        headers=SUBRESOURCE_HEADERS,
    )
    assert r.status_code == 200
    assert "fake bundle" in r.text


def test_base_href_js_served_from_app_dist(client, authed_session, fake_app_dist):
    r = client.get(
        "/yinhu/super-xiaochen/base-href.js",
        cookies={"app_session": authed_session},
        headers=SUBRESOURCE_HEADERS,
    )
    assert r.status_code == 200
    assert r.text == "(function(){})();"


def test_unknown_asset_under_assets_returns_404(client, authed_session, fake_app_dist):
    r = client.get(
        "/yinhu/super-xiaochen/assets/does-not-exist.js",
        cookies={"app_session": authed_session},
        headers=SUBRESOURCE_HEADERS,
    )
    assert r.status_code == 404


def test_csp_nonce_injected_when_header_present(
    client, authed_session, fake_app_dist
):
    """fake_app_dist's index.html contains a bare `<script>` and a bare
    `<style>` — both must be rewritten to carry the nonce attribute."""
    r = client.get(
        "/yinhu/super-xiaochen/",
        cookies={"app_session": authed_session},
        headers={**NAV_HEADERS, "x-csp-nonce": "abc123"},
    )
    assert r.status_code == 200
    assert '<script nonce="abc123">window.__BOOT__' in r.text
    assert '<style nonce="abc123">body{color:red}' in r.text


def test_csp_nonce_no_op_when_header_absent(
    client, authed_session, fake_app_dist
):
    """Without the X-CSP-Nonce header, HTML is served verbatim."""
    r = client.get(
        "/yinhu/super-xiaochen/",
        cookies={"app_session": authed_session},
        headers=NAV_HEADERS,
    )
    assert r.status_code == 200
    assert "<script>window.__BOOT__" in r.text
    assert "<style>body{color:red}" in r.text
    assert "nonce=" not in r.text


# --- pass-through cases (non-static subpaths) ------------------------------


def test_chat_post_falls_through_to_proxy(
    client, authed_session, fake_app_dist
):
    """POST /<client>/<agent>/chat must NOT be intercepted by static logic
    even when app/dist exists; it's an API call destined for the agent."""
    with patch("platform_app.main.proxy.reverse_proxy") as mock_proxy:
        from fastapi.responses import JSONResponse
        mock_proxy.return_value = JSONResponse({"proxied": True})
        r = client.post(
            "/yinhu/super-xiaochen/chat",
            cookies={"app_session": authed_session},
            headers={**SUBRESOURCE_HEADERS, "x-csrf-token": "x"},
            json={"message": "hi", "session_id": "s1"},
        )
    assert mock_proxy.called, "API POST must reach reverse_proxy"


def test_get_history_falls_through_to_proxy(
    client, authed_session, fake_app_dist
):
    with patch("platform_app.main.proxy.reverse_proxy") as mock_proxy:
        from fastapi.responses import JSONResponse
        mock_proxy.return_value = JSONResponse({"history": []})
        r = client.get(
            "/yinhu/super-xiaochen/history",
            cookies={"app_session": authed_session},
            headers=SUBRESOURCE_HEADERS,
        )
    assert mock_proxy.called, "API GET /history must reach reverse_proxy"


def test_agent_static_fonts_falls_through_to_proxy(
    client, authed_session, fake_app_dist
):
    """The agent serves its own /static/fonts/*.woff2 — those must reach
    the agent, not be looked up under app/dist/."""
    with patch("platform_app.main.proxy.reverse_proxy") as mock_proxy:
        from fastapi.responses import Response
        mock_proxy.return_value = Response(b"woff2 data", media_type="font/woff2")
        r = client.get(
            "/yinhu/super-xiaochen/static/fonts/foo.woff2",
            cookies={"app_session": authed_session},
            headers=SUBRESOURCE_HEADERS,
        )
    assert mock_proxy.called, "agent /static/* must reach reverse_proxy"


# --- deploy-safe fallback (app/dist absent) --------------------------------


def test_deploy_safe_fallback_when_index_missing(
    client, authed_session, tmp_path, monkeypatch
):
    """If app/dist/index.html does not exist, every request falls through
    to reverse_proxy. Phase 1 ships safely before stage 1 populates dist."""
    from platform_app import main as main_mod
    empty = tmp_path / "app" / "dist"
    empty.mkdir(parents=True)
    monkeypatch.setattr(main_mod, "_APP_DIST", empty)

    with patch("platform_app.main.proxy.reverse_proxy") as mock_proxy:
        from fastapi.responses import JSONResponse
        mock_proxy.return_value = JSONResponse({"legacy": True})
        r = client.get(
            "/yinhu/super-xiaochen/",
            cookies={"app_session": authed_session},
            headers=NAV_HEADERS,
        )
    assert mock_proxy.called, "missing dist must fall through to proxy"


# --- ACL / auth still enforced --------------------------------------------


def test_unauthed_static_request_rejected(client, fake_app_dist):
    r = client.get(
        "/yinhu/super-xiaochen/",
        headers=NAV_HEADERS,
    )
    # No cookie → auth fails before static branch is even consulted.
    assert r.status_code in (401, 403)


def test_acl_denied_static_request_rejected(client, fake_app_dist):
    """User exists but has no ACL for yinhu/super-xiaochen — must 403
    even though the SPA shell is harmless to leak (defense in depth)."""
    db.init()
    db.main().execute(
        "INSERT INTO users (id, username, password_hash, display_name, created_at) "
        "VALUES (%s,%s,%s,%s,%s)",
        ("u_no_acl", "noacl", auth.hash_password("p"), "No ACL", int(time.time())),
    )
    sid, _ = auth.create_session("u_no_acl", "127.0.0.1", "test")
    r = client.get(
        "/yinhu/super-xiaochen/",
        cookies={"app_session": sid},
        headers=NAV_HEADERS,
    )
    assert r.status_code == 403
```

- [ ] **Step 8.2: Run the tests — confirm they fail**

```bash
cd /Users/eason/agent-platform/.worktrees/platform-ui/platform
pytest tests/test_platform_chat_ui_routing.py -v
```

Expected: tests **fail**. Most positive cases will return 200 from the existing reverse_proxy path (which we have not yet modified) but they'll fail content assertions like "<title>运帷 AI · 平台 chat UI</title> in r.text" because they're hitting reverse_proxy, which will try to contact the (non-existent) yinhu agent and either timeout or return an error.

Acceptable failure modes for this step: AssertionError on body content, 502/503 from reverse_proxy attempting upstream connection, AttributeError on `main_mod._APP_DIST` (the symbol doesn't exist yet — that's expected and proves the test file structure is wired correctly).

If a test errors on `main_mod._APP_DIST` not existing, that's the strongest "needs implementation" signal. Proceed to Task 9.

---

## Task 9: Implement catch_all static-vs-proxy split

**Files:**
- Modify: `platform/platform_app/main.py`

- [ ] **Step 9.1: Add imports + module-level constants near the top**

Open `platform/platform_app/main.py`. Find the existing imports block (lines 1-13). After the existing imports, add:

```python
from fastapi.responses import HTMLResponse  # already-imported FileResponse + JSONResponse stay; add HTMLResponse
```

(Note: line 7 already imports FileResponse + JSONResponse. Edit line 7 to add HTMLResponse to the same import:
`from fastapi.responses import FileResponse, HTMLResponse, JSONResponse`)

After `_STATIC = ...` (around line 34), add:

```python
# app/dist/ holds the Phase 1+ chat UI build artifacts. Stage 1 of
# platform/Dockerfile populates it; if index.html is missing (e.g. an old
# image without the new stage), catch_all transparently falls through to
# reverse_proxy, preserving pre-Phase-1 behavior. This is the deploy-safety
# guarantee documented in 2026-05-07-platform-chat-ui-design.md.
#
# We compute index existence inside catch_all (not as a module-level
# constant) so tests can monkeypatch _APP_DIST and have the change picked up
# on the next request without touching a derived constant.
_APP_DIST = Path(__file__).parent.parent.parent / "app" / "dist"
# Subpaths under /<client>/<agent>/ that the platform serves from app/dist
# instead of forwarding to the agent. Anything else proxies through.
_APP_STATIC_PREFIXES: tuple[str, ...] = ("/assets/", "/base-href.js", "/favicon.ico")
```

> The path `Path(__file__).parent.parent.parent / "app" / "dist"` resolves to:
> `<repo>/platform/platform_app/main.py` → `parent` = `platform_app/` → `parent` = `platform/` → `parent` = `<repo>/` → `<repo>/app/dist`. That's the build output of `cd app && npm run build` from the repo root.

- [ ] **Step 9.2: Replace the `catch_all` body**

Find the existing `catch_all` (currently around line 75-109). Replace the function body (keeping the decorator and signature) with:

```python
@app.api_route("/{full_path:path}", methods=["GET", "HEAD", "POST", "PUT", "PATCH", "DELETE"])
async def catch_all(full_path: str, request: Request):
    m = PATH_RE.match("/" + full_path)
    if not m:
        raise HTTPException(404)

    client_id = m.group("client")
    agent_id = m.group("agent")
    subpath = m.group("sub") or "/"

    # auth
    user = api._user_from_request(request)

    # ACL
    if not db.has_acl(user["id"], client_id, agent_id):
        raise HTTPException(403, {"error": "not_authorized_for_tenant", "message": "无权访问"})

    # §7.2 firewall
    try:
        firewall.check_request(
            sec_fetch_mode=request.headers.get("sec-fetch-mode"),
            sec_fetch_site=request.headers.get("sec-fetch-site"),
            referer=request.headers.get("referer"),
            host=request.headers.get("host", ""),
            dest_path_prefix=f"/{client_id}/{agent_id}/",
            csrf_header=request.headers.get("x-csrf-token"),
            csrf_cookie=request.cookies.get("app_csrf"),
            method=request.method,
        )
    except firewall.FirewallReject as e:
        raise HTTPException(403, {"error": "cross_agent_blocked", "message": str(e)})

    # Phase 1: serve the new chat UI from app/dist when populated. The
    # exists() check is the deploy-safe fallback — if the platform image
    # hasn't been rebuilt with the node stage yet, every request falls
    # through to the existing reverse_proxy path below.
    app_index = _APP_DIST / "index.html"
    if request.method in ("GET", "HEAD") and app_index.exists():
        if subpath in ("/", "/index.html"):
            html = app_index.read_text(encoding="utf-8")
            nonce = request.headers.get("x-csp-nonce", "")
            if nonce:
                html = html.replace("<script>", f'<script nonce="{nonce}">')
                html = html.replace("<style>", f'<style nonce="{nonce}">')
            return HTMLResponse(html, headers=_NO_STORE)
        for prefix in _APP_STATIC_PREFIXES:
            if subpath.startswith(prefix):
                asset = _APP_DIST / subpath.lstrip("/")
                if not asset.is_file():
                    raise HTTPException(404)
                return FileResponse(asset)

    return await proxy.reverse_proxy(
        request, client_id=client_id, agent_id=agent_id, user=user, subpath=subpath,
    )
```

> **Why the order auth → ACL → firewall → static-vs-proxy**: every existing security guarantee runs before any new branching. A static GET for the SPA shell still requires a valid session cookie + ACL grant + same-origin referer; nothing is opened up by Phase 1.

> **`favicon.ico` in static prefixes**: Vite emits `favicon.ico` to `dist/` only if you put one in `public/`. Phase 1 doesn't ship one, so requests to `/<client>/<agent>/favicon.ico` will 404 from the static branch (rather than fall through to the agent). This is fine — the browser tolerates a 404 favicon. If you'd rather have it fall through to the agent, drop `/favicon.ico` from `_APP_STATIC_PREFIXES` and add a real one in Phase 5.

- [ ] **Step 9.3: Run the tests — they should pass now**

```bash
cd /Users/eason/agent-platform/.worktrees/platform-ui/platform
pytest tests/test_platform_chat_ui_routing.py -v
```

Expected: all tests pass. If any fail:
- "AttributeError: module has no attribute '_APP_DIST'" → Step 9.1 incomplete; verify the constant was added at module level.
- 500 on positive cases → likely an import error; check `from fastapi.responses import HTMLResponse` was added.
- 200 but wrong body → check the read+replace logic in Step 9.2.
- Pass-through cases not hitting `mock_proxy` → the static branch is consuming requests it shouldn't; check the `if subpath in ("/", "/index.html")` and prefix-list logic.

- [ ] **Step 9.4: Run the full platform test suite to confirm no regression**

```bash
cd /Users/eason/agent-platform/.worktrees/platform-ui/platform
pytest -x --tb=short
```

Expected: every test that passed before this task still passes. If `test_page_routes.py` or `test_enterprise_api.py` break, the most likely cause is the new `HEAD` method on the catch_all interfering with an existing route. Investigate.

---

## Task 10: Multi-stage Dockerfile

**Files:**
- Modify: `platform/Dockerfile`

- [ ] **Step 10.1: Rewrite the Dockerfile**

Replace the contents of `platform/Dockerfile` with:

```dockerfile
# ─────────────── Stage 1: build agent-platform/app/ chat UI ───────────────
# Produces /build/app/dist/ which stage 2 copies into the runtime image.
# This stage adds ~150 MB during build, but is discarded — the final image
# never contains node/npm. Skip without breaking anything: if app/ is empty
# the COPY in stage 2 will copy an empty dir and main.py's _APP_INDEX.exists()
# check trips the deploy-safe fallback.
FROM node:20-alpine AS app-build
WORKDIR /build/app

# package*.json first for layer cache: re-run npm ci only when deps change.
COPY app/package.json app/package-lock.json ./
RUN npm ci

# Then source — changes here don't invalidate the npm ci layer.
COPY app/ ./
RUN npm run build && ls -la dist/ && ls -la dist/assets/ | head -10

# ─────────────── Stage 2: python runtime (existing) ───────────────
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

# Built chat UI from stage 1 → /app/../app/dist relative to /app/platform_app/main.py.
# main.py computes _APP_DIST = Path(__file__).parent.parent.parent / "app" / "dist",
# so we mirror that layout: /app is platform/, /app/.. needs an app/dist sibling.
# Put it at /app-frontend/dist and symlink, or — simpler — adjust by placing
# the dist at ../app/dist relative to platform_app. WORKDIR /app means parent
# is /, so: /app/platform_app/main.py.parent.parent.parent = /. Therefore the
# COPY target is /app/dist at the filesystem root.
COPY --from=app-build /build/app/dist /app/dist

# Railway sets $PORT (typically 8080). Local docker-compose sets it via
# the `command:` override. Default to 80 so plain `docker run` also works.
EXPOSE 80
CMD uvicorn platform_app.main:app --host 0.0.0.0 --port ${PORT:-80} --workers 1
```

> **About the `_APP_DIST` path resolution inside the container**:
> - In dev: `<repo>/platform/platform_app/main.py` → `_APP_DIST = <repo>/app/dist`
> - In docker: `/app/platform_app/main.py` → `parent = /app/platform_app` → `parent = /app` → `parent = /` → `_APP_DIST = /app/dist`. So the COPY target must be `/app/dist`.
>
> Wait — that's `/` + `"app"` + `"dist"` = `/app/dist`. But `WORKDIR /app` already exists. So `/app/dist` lives inside `/app` (alongside `platform_app/`, `static/`, `migrations/`). Placement is fine; just be aware of the slightly confusing dual meaning of "app" here (it's the platform's `/app` workdir AND the new chat UI's `app/` source dir; the COPY target conflates them by design).

- [ ] **Step 10.2: Verify in dev shell that paths line up**

Sanity check the path math without docker:

```bash
cd /Users/eason/agent-platform/.worktrees/platform-ui
python3 -c "from pathlib import Path; p = Path('platform/platform_app/main.py').resolve(); print(p.parent.parent.parent / 'app' / 'dist')"
```

Expected: prints `/Users/eason/agent-platform/.worktrees/platform-ui/app/dist`. That matches the actual location of `app/dist` produced in Task 6.

If the printed path is wrong, the COPY target in Step 10.1 may be misaligned — debug before docker build.

- [ ] **Step 10.3: Verify Dockerfile syntax**

The Dockerfile references `COPY app/...` and `COPY platform_app ...` — both relative to the build context root, which must be the **repo root**, not `platform/`. This is a **change** from the previous single-stage Dockerfile which worked from `platform/` as context. Document this in the commit message and update Railway / docker-compose configs in Task 11.1.

```bash
cd /Users/eason/agent-platform/.worktrees/platform-ui
docker buildx build --check -f platform/Dockerfile . 2>&1 | head -30 || true
```

Expected: no syntax errors. Deprecation warnings (e.g., for legacy ENV/CMD shell form) are acceptable — the original Dockerfile uses the same patterns.

---

## Task 11: Docker build + run + curl smoke test

**Files:** none

- [ ] **Step 11.1: Build the image (from the repo root, NOT from platform/)**

The Dockerfile's stage 1 has `COPY app/package.json ...` and stage 2 has `COPY platform_app ...`. Both paths are relative to the build context root, which means the `docker build` command MUST be invoked with the **repo root** as context and `-f platform/Dockerfile`:

```bash
cd /Users/eason/agent-platform/.worktrees/platform-ui
docker build -t agent-platform:phase1-chatui -f platform/Dockerfile .
```

> If Railway / docker-compose currently invokes `docker build` from `platform/` as context (single-stage worked because everything it needed was inside `platform/`), the Phase 1 Dockerfile breaks that convention. **Action**: update Railway service config to use the repo root as context and `dockerfile: platform/Dockerfile`. Document this in the commit message. If you can't change Railway's invocation pattern, fall back to keeping a `Dockerfile` at the repo root that includes `platform/Dockerfile` — but prefer the explicit `-f` flag.

Expected output: stage 1 runs `npm ci` then `npm run build`, prints the `dist/` listing including `index.html` + `assets/`. Stage 2 copies it. Final image tagged.

- [ ] **Step 11.2: Verify image size delta**

```bash
docker image inspect agent-platform:phase1-chatui --format '{{.Size}}' | numfmt --to=iec
```

Expected: roughly the current platform image size + ~5-10 MB (the static dist files). If size grew by >100 MB, something leaked from stage 1 — inspect with `docker image history`.

- [ ] **Step 11.3: Run the container and curl the SPA**

```bash
docker run --rm -d --name platform-phase1-smoke -p 28080:80 agent-platform:phase1-chatui
sleep 5
docker logs platform-phase1-smoke | tail -10
```

Expected: uvicorn startup logs, no errors.

```bash
# /healthz or / should return something (auth/login flow may differ; check logs).
curl -sI http://127.0.0.1:28080/ | head -3
```

> Full SPA-shell e2e check requires logging in + having an ACL row. That's heavier than this phase warrants. The unit tests in Task 8 already cover the happy paths; this docker smoke is just "does the image start and serve _something_ on port 80".

- [ ] **Step 11.4: Verify dist files are present in the running container**

```bash
docker exec platform-phase1-smoke ls -la /app/dist/
docker exec platform-phase1-smoke ls -la /app/dist/assets/ | head -5
```

Expected: `index.html`, `base-href.js`, `assets/index-XXX.js`, `assets/index-XXX.css`. If `/app/dist/` is empty or missing, stage 1 didn't copy properly — debug the `COPY --from=app-build` line in the Dockerfile.

- [ ] **Step 11.5: Stop the container**

```bash
docker stop platform-phase1-smoke
```

If any step in 11.3-11.4 failed, fix the Dockerfile before proceeding to commit.

> **If docker is not available locally**: skip Tasks 11.1-11.5. The Task 8 unit tests already cover the routing logic; the Dockerfile change has been syntax-checked in Task 10.3. Note in the commit message that the docker smoke was deferred to Railway CI / next push.

---

## Task 12: Final commit

**Files:** none changed (commit only)

- [ ] **Step 12.1: Review the diff**

```bash
cd /Users/eason/agent-platform/.worktrees/platform-ui
git status -sb
git diff --stat HEAD
```

Sanity checks:
- `app/node_modules/` is **not** staged (Task 7 gitignore working)
- `app/dist/` is **not** staged
- `app/package-lock.json` **is** staged (deterministic builds)
- `platform/Dockerfile`, `platform/platform_app/main.py`, `platform/tests/test_platform_chat_ui_routing.py`, `.gitignore` all show as modified/added

- [ ] **Step 12.2: Stage the changes**

```bash
cd /Users/eason/agent-platform/.worktrees/platform-ui
git add app/
git add platform/Dockerfile platform/platform_app/main.py platform/tests/test_platform_chat_ui_routing.py
git add .gitignore
git add docs/superpowers/plans/2026-05-07-platform-chat-ui-phase-1-scaffold.md
git status -sb
```

Expected: a clean staged set covering all Phase 1 files plus this plan doc.

- [ ] **Step 12.3: Commit**

```bash
git commit -m "$(cat <<'EOF'
feat(app): Phase 1 chat UI scaffold + multi-stage Dockerfile

Stand up agent-platform/app/ as a Vite+React 19+TS+Tailwind 4 project that
builds to app/dist/ via a new node stage in platform/Dockerfile. Adds a
static-vs-proxy split in platform_app/main.py:catch_all so /<client>/<agent>/
serves the SPA shell while everything else continues to reverse-proxy to
the agent. Includes a deploy-safe fallback: if app/dist/index.html does not
exist at request time, every request falls through to the existing
reverse_proxy path, so Phase 1 deploys safely before any chat content lands.

- app/ Vite project mirrors landing/'s tooling (React 19 + Vite 7 + TS 5.6
  + Tailwind 4 via @tailwindcss/vite); hello-world page in brand blue
- public/base-href.js extracts the reverse-proxy <base href> IIFE so
  production HTML has zero inline scripts (CSP-clean)
- platform/Dockerfile becomes multi-stage: node:20-alpine builds the app,
  python:3.13-slim copies the dist and runs uvicorn as before
- catch_all gains GET/HEAD branches for /<client>/<agent>/{,index.html}
  + /assets/* + /base-href.js + /favicon.ico, served from app/dist; all
  other paths preserve current reverse_proxy behavior
- Auth/ACL/firewall checks all run BEFORE the static branch, so no
  security surface change

Phase 1 of docs/superpowers/specs/2026-05-07-platform-chat-ui-design.md.
Chat logic + per-tenant /me consumption are Phases 3-5.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

- [ ] **Step 12.4: Push to remote (per user's PR workflow — push only, no `gh pr create`)**

```bash
git push
```

Expected: `design/platform-ui` advances on the remote.

- [ ] **Step 12.5: Show resulting state**

```bash
git log --oneline -n 5
git show --stat HEAD | tail -25
```

Expected: new commit on top of `d9f78d5` with all Phase 1 files. PR opened from a different account per user's workflow.

---

## Out-of-scope for Phase 1 (do NOT do here)

- Install `@assistant-ui/react`, chat runtime, or any chat library — Phase 3
- Write `chatAdapter.ts`, runtime code, or message components — Phase 3
- Per-tenant `/me` consumption, branding override, font loading — Phase 5
- Cutover yinhu-rebuild's agent to drop legacy UI — Phase 5 cross-repo work
- shadcn/ui, additional component libraries — Phase 3 if needed
- Vitest / Playwright scaffolding — Phase 2/3 introduces test infra
- Bundle splitting, code splitting, lazy loading — defer

## Self-review checklist (run before declaring Phase 1 done)

- [ ] `cd app && npm run build` clean, no warnings about CSS or TS
- [ ] `app/dist/index.html` contains zero non-`src` inline `<script>` blocks (`grep -E '<script>(?!.*src)' app/dist/index.html` empty)
- [ ] `cd platform && pytest tests/test_platform_chat_ui_routing.py -v` all green
- [ ] `cd platform && pytest -x --tb=short` no regressions in pre-existing tests
- [ ] `git status` is clean after commit (no stragglers)
- [ ] `app/node_modules/` not committed (`git ls-files app/node_modules/` empty)
- [ ] `app/package-lock.json` IS committed (deterministic CI builds)
- [ ] Docker image (if built) has `/app/dist/` populated and serves on port 80
- [ ] `_APP_INDEX.exists()` falls through to `reverse_proxy` path verified by `test_deploy_safe_fallback_when_index_missing`
