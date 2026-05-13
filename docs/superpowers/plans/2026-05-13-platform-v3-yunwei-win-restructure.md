# Platform V3 Yunwei Win Restructure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild the platform around `/win` as the authenticated product portal, rename the shared product backend from `yinhu_brain` to `yunwei_win`, provide shared AI Q&A for Free/Lite users, route Pro+ users through dedicated runtimes, and remove dashboard/agent-list legacy code from the customer path.

**Architecture:** `platform_app` is the control plane: auth, enterprise, plan, entitlement, runtime registry, admin, audit, and Pro/Max runtime gateway. `yunwei_win` is the `/win` product backend: customer profile, ingestion, shared assistant, customer memory, and `/win/api/*`. Dedicated runtimes are execution-plane services selected by runtime bindings; they are not the default customer portal.

**Tech Stack:** FastAPI, psycopg/Postgres migrations, SQLAlchemy async, Redis, Vite/React, pytest, Docker/Railway.

---

## First-Principles Decisions

- `app.fiveoranges.ai` is an authenticated product portal, not a dashboard.
- `/` redirects logged-in users to `/win/`; unauthenticated users still see login.
- `/win/` is the main customer product surface.
- `platform_app` owns identity, enterprise, plan, quota, entitlement, runtime registry, and runtime gateway.
- `yunwei_win` owns the Win product domain: customers, documents, ingest, shared assistant, customer memory.
- Free/Lite users use a shared assistant service with hard server-side enterprise scoping.
- Pro/Max users may use dedicated runtimes through the same product entry point.
- LLM/tool calls never receive a trusted `enterprise_id` argument from user input or model output. The server injects `enterprise_id` via an authenticated context.
- Platform metadata DB and customer business data plane remain separate concepts.
- Rename spelling is `yunwei`, not `yunwe`.

## Target File System Structure

This plan moves toward the following structure. Do not try to complete every move in one commit.

```text
agent-platform/
  apps/
    landing-web/
    yunwei-win-web/

  services/
    platform-api/
      Dockerfile
      pyproject.toml
      migrations/
      static/
      src/
        platform_app/
        yunwei_win/
        platform_contracts/
      tests/

  runtimes/
    README.md
    examples/

  infra/
    local/
    railway/
    cloudflare/

  docs/
    architecture/
    migration/
    superpowers/
```

Implementation can be incremental. The first executable milestone may keep the current `platform/` service root while renaming product packages inside it:

```text
platform/platform_app/      -> keep first
platform/yinhu_brain/       -> platform/yunwei_win/
platform/app-win/           -> keep first or move to apps/yunwei-win-web/ in Task 2
```

## Execution Order

Tasks 1-3 are foundational and must run sequentially. Tasks 4-5 can start after Task 1. Tasks 6-7 must start after Task 4. Task 8 runs after all code-path changes are merged.

1. Rename `yinhu_brain` to `yunwei_win`.
2. Move/rename the Win frontend and update build paths.
3. Make `/win/` the logged-in portal and remove dashboard from the customer path.
4. Add explicit `AuthContext` and entitlement policy.
5. Add shared assistant service under `yunwei_win`.
6. Add runtime registry tables and resolver.
7. Add Pro+ dedicated runtime adapter through the same assistant endpoint.
8. Remove or archive legacy customer-facing agent-list/chat scaffolding.
9. Final verification and deployment runbook update.

## Parallel Assignment Map

- **Agent A:** Package rename: `yinhu_brain` -> `yunwei_win`. Runs first.
- **Agent B:** Frontend filesystem rename: `platform/app-win` -> `apps/yunwei-win-web`. Starts after Agent A or works on a branch rebased after Agent A.
- **Agent C:** Portal routing: `/` -> `/win/`, dashboard removal from customer path. Starts after Agent A.
- **Agent D:** AuthContext + entitlement policy. Starts after Agent A.
- **Agent E:** Shared assistant service. Starts after Agent D.
- **Agent F:** Runtime registry + dedicated runtime adapter. Starts after Agent D.
- **Agent G:** Legacy cleanup and docs. Runs last.

Do not run agents that edit the same file at the same time unless the later agent is explicitly rebased after the earlier one. Known shared files: `platform/platform_app/main.py`, `platform/Dockerfile`, `platform/pyproject.toml`, `platform/tests/conftest.py`.

---

## Task 1: Rename Product Backend Package to `yunwei_win`

**Files:**
- Move: `platform/yinhu_brain/` -> `platform/yunwei_win/`
- Modify: `platform/platform_app/main.py`
- Modify: `platform/pyproject.toml`
- Modify: `platform/Dockerfile`
- Modify: all imports under `platform/yunwei_win/`
- Modify: tests importing `yinhu_brain`
- Test: `platform/tests/test_invite_codes.py`
- Test: `platform/tests/test_yinhu_brain_tenant_isolation.py` renamed to `platform/tests/test_yunwei_win_tenant_isolation.py`

### Task Brief: Agent A

```text
你是 coding agent，在仓库 `/Users/eason/agent-platform` 工作。

任务：
把共享 Win 产品后端包从 `yinhu_brain` 重命名为 `yunwei_win`，保持 `/win/api/*` 外部路由不变。

背景：
- `yinhu_brain` 最早来自银湖，但现在承载的是智通客户 `/win` 产品后端。
- 新架构中 `platform_app` 是控制面，`yunwei_win` 是 Win 产品后端。
- URL 不跟 Python 包名耦合：`/win/api/*` 保持兼容。

目标行为：
- `from yunwei_win ...` 成为唯一产品后端 import。
- `platform_app.main` 继续 `app.include_router(..., prefix="/win")`。
- `yinhu-ingest-worker` console script 改名为 `yunwei-win-ingest-worker`。
- 所有相关测试通过。

非目标 / 禁止事项：
- 不要修改业务逻辑。
- 不要改 `/win/api/*` URL。
- 不要删除 HMAC proxy 或 `platform_app.proxy`。
- 不要覆盖或回滚用户未提交改动。

相关文件：
- `platform/yinhu_brain/`：需要移动为 `platform/yunwei_win/`。
- `platform/platform_app/main.py`：当前 import `yinhu_brain` router 和 dispose。
- `platform/pyproject.toml`：packages 和 script 仍指向 `yinhu_brain`。
- `platform/Dockerfile`：COPY 路径仍是 `platform/yinhu_brain`。
- `platform/tests/test_yinhu_brain_*`：测试文件名和 imports 需要改。

实现要求：
1. 用 `git mv platform/yinhu_brain platform/yunwei_win` 移动目录。
2. 用 `rg -n "yinhu_brain|yinhu-ingest-worker"` 找到所有引用并改为 `yunwei_win` / `yunwei-win-ingest-worker`。
3. 更新 `platform/pyproject.toml`：
   - dependency 注释改成 `yunwei_win (智通客户) deps`。
   - `[project.scripts]` 改为 `yunwei-win-ingest-worker = "yunwei_win.workers.ingest_rq_worker:main"`。
   - wheel packages 改为 `["platform_app", "yunwei_win"]`。
4. 更新 `platform/Dockerfile`：
   - COPY `platform/yunwei_win /app/yunwei_win/`。
   - 注释中的 `yinhu_brain` 改为 `yunwei_win`。
   - worker start command 注释改为 `yunwei-win-ingest-worker`。
5. 更新 `platform/platform_app/main.py`：
   - `from yunwei_win import router as _win_router`
   - `from yunwei_win.db import dispose_all as _win_dispose`
   - 注释统一为 `yunwei_win (智通客户)`。
6. 重命名测试文件：
   - `platform/tests/test_yinhu_brain_contract_flow.py` -> `platform/tests/test_yunwei_win_contract_flow.py`
   - `platform/tests/test_yinhu_brain_tenant_isolation.py` -> `platform/tests/test_yunwei_win_tenant_isolation.py`

测试要求：
- 运行：
  - `cd platform && ../.venv/bin/pytest tests/test_invite_codes.py tests/test_yunwei_win_contract_flow.py -q`
  - `cd platform && ../.venv/bin/pytest tests/test_ingest_jobs.py tests/test_ingest_rq_worker.py -q`
- 预期：
  - 所有测试通过。
  - `rg -n "yinhu_brain"` 只允许出现在 archived docs 或 migration docs；生产代码和测试不应出现。

交付标准：
- 提交一个原子 commit：`refactor(win): rename yinhu_brain to yunwei_win`
- 输出变更摘要、测试结果、剩余风险。
```

---

## Task 2: Move Win Frontend to `apps/yunwei-win-web`

**Files:**
- Move: `platform/app-win/` -> `apps/yunwei-win-web/`
- Modify: `platform/Dockerfile`
- Modify: `platform/platform_app/main.py`
- Modify: docs mentioning `platform/app-win`
- Test: `platform/tests/test_page_routes.py`
- Test: frontend build from `apps/yunwei-win-web`

### Task Brief: Agent B

```text
你是 coding agent，在仓库 `/Users/eason/agent-platform` 工作。

任务：
把智通客户前端从 `platform/app-win` 移到 `apps/yunwei-win-web`，保持 `/win/` 页面和静态资源行为不变。

背景：
- 新文件系统按 deployable/product boundary 组织。
- `yunwei_win` 是后端包，`apps/yunwei-win-web` 是 Win 前端。
- 当前 Dockerfile 在 stage 1 构建 `platform/app-win`，FastAPI 从 `_WIN_DIST` 读取 dist。

目标行为：
- `npm run build` 在 `apps/yunwei-win-web` 成功。
- Docker build stage 从 `apps/yunwei-win-web` 构建前端。
- 平台运行时仍把构建产物复制到 `/app/yunwei-win-web/dist` 或清晰等价路径。
- `/win/` 返回 Win SPA。

非目标 / 禁止事项：
- 不要重写前端 UI。
- 不要改 `/win/` URL。
- 不要同时引入新的前端框架。

相关文件：
- `platform/app-win/package.json`：移动到 `apps/yunwei-win-web/package.json`。
- `platform/Dockerfile`：前端 build stage 路径。
- `platform/platform_app/main.py`：`_WIN_DIST` 路径。
- `platform/tests/test_page_routes.py`：可新增 `/win/` route smoke test。

实现要求：
1. 用 `mkdir -p apps` 和 `git mv platform/app-win apps/yunwei-win-web` 移动目录。
2. 更新 `apps/yunwei-win-web/package.json`：
   - `"name": "yunwei-win-web"`
   - description 保持说明 `/win/` 产品前端。
3. 更新 `platform/Dockerfile`：
   - stage 名可改为 `yunwei-win-web-build`。
   - COPY `apps/yunwei-win-web/package.json apps/yunwei-win-web/package-lock.json ./`。
   - COPY `apps/yunwei-win-web/ ./`。
   - COPY build output 到 `/app/yunwei-win-web/dist`。
4. 更新 `platform/platform_app/main.py`：
   - `_WIN_DIST = Path(__file__).resolve().parent.parent.parent / "yunwei-win-web" / "dist"` 如果容器复制到 `/app/yunwei-win-web/dist`。
   - 本地 dev fallback 可以先明确指向 repo-root `apps/yunwei-win-web/dist`。
5. 新增或修改测试：
   - 在 `platform/tests/test_page_routes.py` 加 logged-in `/win/` 返回 Win title marker 的 smoke test。

测试要求：
- 运行：
  - `cd apps/yunwei-win-web && npm run build`
  - `cd platform && ../.venv/bin/pytest tests/test_page_routes.py -q`
- 预期：
  - frontend build 成功。
  - `/win/` smoke test 通过。

交付标准：
- 提交一个原子 commit：`refactor(win): move frontend app to apps directory`
- 输出变更摘要、测试结果、剩余风险。
```

---

## Task 3: Make `/win/` the Logged-In Portal and Remove Dashboard from Customer Path

**Files:**
- Modify: `platform/platform_app/main.py`
- Modify: `platform/static/login.html` only if login form has hardcoded redirect assumptions
- Modify: `platform/static/agents.html` only to archive/remove from customer path
- Modify: `platform/tests/test_page_routes.py`
- Modify: `platform/tests/test_invite_codes.py`

### Task Brief: Agent C

```text
你是 coding agent，在仓库 `/Users/eason/agent-platform` 工作。

任务：
把 `app.fiveoranges.ai/` 的登录后入口改成 `/win/`，不再展示 customer-facing dashboard。

背景：
- 新产品模型中 platform 不是 agent dashboard。
- `/win/` 是智通客户主产品。
- `agents.html` 可以暂时保留为内部 legacy/debug 页面，但不能再作为登录后的默认体验。

目标行为：
- GET `/` 未登录：返回 login.html。
- GET `/` 已登录：302/307 redirect 到 `/win/`。
- GET `/win/` 未登录：返回 login.html 或 redirect login，保持现有体验。
- GET `/win/` 已登录：返回 Win SPA。
- `/api/agents` 可以暂时保留给内部兼容，但不再驱动用户入口。

非目标 / 禁止事项：
- 不要删除 auth/session/register。
- 不要删除 `platform_app.proxy`。
- 不要修改 `/win/api/*`。

相关文件：
- `platform/platform_app/main.py`：`index()` 当前返回 `agents.html` 或 `login.html`。
- `platform/tests/test_page_routes.py`：页面 smoke tests。
- `platform/tests/test_invite_codes.py`：注册后 redirect 已经期待 `/win/`。

实现要求：
1. 修改 `index()`：
   ```python
   from fastapi.responses import RedirectResponse

   @app.api_route("/", methods=["GET", "HEAD"])
   def index(request: Request):
       if not request.cookies.get("app_session"):
           return FileResponse(_STATIC / "login.html", headers=_NO_STORE)
       return RedirectResponse("/win/", status_code=303, headers=_NO_STORE)
   ```
2. 如果 `HEAD /` 因 `RedirectResponse` 行为导致测试不稳定，为 HEAD 单独保留兼容，但 GET 必须 redirect。
3. 给 legacy dashboard 增加内部路径，二选一：
   - 简单方案：不新增路径，只让 `agents.html` 不再被 `/` 引用。
   - 内部方案：新增 `/admin/agents`，要求 logged-in + platform admin。
4. 更新 `platform/tests/test_page_routes.py`：
   - 新增 `test_root_serves_login_when_unauthed`。
   - 新增 `test_root_redirects_to_win_when_authed`。
   - 新增 `test_win_serves_when_authed`。
5. 更新任何仍断言 `/` 返回 dashboard 的测试。

测试要求：
- 运行：
  - `cd platform && ../.venv/bin/pytest tests/test_page_routes.py tests/test_invite_codes.py -q`
- 预期：
  - `/` authed redirect 到 `/win/`。
  - 注册后 redirect 仍是 `/win/`。

交付标准：
- 提交一个原子 commit：`feat(portal): route logged-in users to win`
- 输出变更摘要、测试结果、剩余风险。
```

---

## Task 4: Introduce Explicit `AuthContext` and Entitlement Policy

**Files:**
- Create: `platform/platform_app/context.py`
- Create: `platform/platform_app/entitlements.py`
- Modify: `platform/platform_app/main.py`
- Modify: `platform/platform_app/api.py` if shared helper should move
- Test: `platform/tests/test_context.py`
- Test: `platform/tests/test_entitlements.py`

### Task Brief: Agent D

```text
你是 coding agent，在仓库 `/Users/eason/agent-platform` 工作。

任务：
新增显式 `AuthContext` 和 entitlement policy，让 `/win/api/*`、共享 assistant、runtime resolver 都通过同一服务端上下文读取 `user_id`、`enterprise_id`、`plan` 和 allowed capabilities。

背景：
- 数据隔离不能由 LLM/agent 决定。
- 当前 `platform_app.main._attach_enterprise` 直接把 `enterprise_id` 写到 request.state，但逻辑散在 middleware 内。
- 新架构需要共享问答和 dedicated runtime 都消费同一个硬边界。

目标行为：
- 后端从 cookie/session 解析 `AuthContext`。
- `AuthContext.enterprise_id` 来自 `enterprise_members`，不是请求体。
- Entitlement policy 根据 enterprise plan 返回 allowed capabilities。
- `/win/api/*` middleware 继续写 `request.state.enterprise_id`，同时写 `request.state.auth_context`。

非目标 / 禁止事项：
- 不要把 enterprise_id 暴露为 LLM 工具入参。
- 不要改变登录 cookie 格式。
- 不要支持多企业切换，本任务保持当前 one user -> first enterprise 行为；后续再设计企业切换。

相关文件：
- `platform/platform_app/main.py`：middleware 当前内联解析用户和企业。
- `platform/platform_app/db.py`：已有 `list_user_enterprises`。
- `platform/migrations/004_enterprises.sql`：enterprises 有 `plan` 字段。

实现要求：
1. 新建 `platform/platform_app/context.py`：
   ```python
   from __future__ import annotations
   from dataclasses import dataclass
   from fastapi import HTTPException, Request
   from . import auth, db

   @dataclass(frozen=True)
   class AuthContext:
       user_id: str
       username: str
       display_name: str
       session_id: str
       enterprise_id: str
       enterprise_plan: str
       enterprise_role: str

   def require_auth_context(request: Request) -> AuthContext:
       cookie = request.cookies.get("app_session")
       user = auth.current_user_from_request(cookie)
       if not user:
           raise HTTPException(401, {"error": "not_logged_in", "message": "请登录"})
       enterprises = db.list_user_enterprises(user["id"])
       if not enterprises:
           raise HTTPException(403, {"error": "no_enterprise", "message": "当前账号未绑定企业"})
       ent = enterprises[0]
       return AuthContext(
           user_id=user["id"],
           username=user["username"],
           display_name=user["display_name"],
           session_id=user["session_id"],
           enterprise_id=ent["id"],
           enterprise_plan=ent.get("plan") or "trial",
           enterprise_role=ent.get("role") or "member",
       )
   ```
2. If `db.list_user_enterprises` does not include `plan`, update its SELECT to return `e.plan`.
3. 新建 `platform/platform_app/entitlements.py`：
   ```python
   from __future__ import annotations
   from dataclasses import dataclass
   from typing import Literal
   from .context import AuthContext

   Plan = Literal["trial", "lite", "pro", "max", "enterprise", "standard"]

   @dataclass(frozen=True)
   class Entitlements:
       runtime_mode: str
       can_use_shared_assistant: bool
       can_use_dedicated_runtime: bool
       allowed_tools: tuple[str, ...]

   def entitlements_for(ctx: AuthContext) -> Entitlements:
       plan = (ctx.enterprise_plan or "trial").lower()
       if plan in {"pro", "max", "enterprise"}:
           return Entitlements(
               runtime_mode="dedicated_customer",
               can_use_shared_assistant=True,
               can_use_dedicated_runtime=True,
               allowed_tools=("customer_profile", "document_qa", "cross_customer_summary", "erp_runtime"),
           )
       if plan in {"lite", "standard"}:
           return Entitlements(
               runtime_mode="pooled_lite",
               can_use_shared_assistant=True,
               can_use_dedicated_runtime=False,
               allowed_tools=("customer_profile", "document_qa", "cross_customer_summary"),
           )
       return Entitlements(
           runtime_mode="pooled_trial",
           can_use_shared_assistant=True,
           can_use_dedicated_runtime=False,
           allowed_tools=("customer_profile", "document_qa"),
       )
   ```
4. 修改 `main._attach_enterprise` 使用 `require_auth_context(request)`，并写：
   ```python
   request.state.auth_context = ctx
   request.state.enterprise_id = ctx.enterprise_id
   request.state.user_id = ctx.user_id
   ```
5. 新增 tests 覆盖：
   - no cookie -> 401。
   - user without enterprise -> 403。
   - trial plan -> pooled_trial。
   - pro plan -> dedicated_customer and dedicated runtime allowed。

测试要求：
- 运行：
  - `cd platform && ../.venv/bin/pytest tests/test_context.py tests/test_entitlements.py tests/test_invite_codes.py -q`
- 预期：
  - AuthContext 和 entitlements 行为稳定。
  - `/win/api/customers` 注册后仍可访问。

交付标准：
- 提交一个原子 commit：`feat(platform): add auth context and entitlements`
- 输出变更摘要、测试结果、剩余风险。
```

---

## Task 5: Add Shared Assistant Service for Free/Lite

**Files:**
- Create: `platform/yunwei_win/assistant/__init__.py`
- Create: `platform/yunwei_win/assistant/router.py`
- Create: `platform/yunwei_win/assistant/service.py`
- Create: `platform/yunwei_win/assistant/context.py`
- Modify: `platform/yunwei_win/__init__.py`
- Modify: `platform/app-win/src/api/client.ts` or `apps/yunwei-win-web/src/api/client.ts` depending on Task 2
- Modify: `platform/app-win/src/screens/Ask.tsx` or moved path
- Test: `platform/tests/test_yunwei_win_assistant.py`

### Task Brief: Agent E

```text
你是 coding agent，在仓库 `/Users/eason/agent-platform` 工作。

任务：
在 `yunwei_win` 中新增共享 assistant endpoint `/win/api/assistant/chat`，供 Free/Lite 用户使用。它必须从 server-side AuthContext 获取 enterprise scope，不允许请求体或 LLM 工具传入企业 ID。

背景：
- Pro 以下用户没有 dedicated runtime，但仍要有 AI 问答能力。
- 当前 Win 前端 `askAI()` 调 `/win/api/ask` 或 `/win/api/customers/{id}/ask`。
- 当前后端已有 `api/ask.py` 和 `api/customer_profile/ask.py` 可复用知识库构建和 LLM 调用。
- 本任务先实现非流式 JSON 版本，后续可以加 SSE。

目标行为：
- POST `/win/api/assistant/chat` 接收 `{question, customer_id?}`。
- 如果 `customer_id` 缺失或 `"all"`，走跨客户共享问答。
- 如果 `customer_id` 是 UUID，走单客户问答。
- 服务端用 `request.state.auth_context` 和 `request.state.enterprise_id` 决定数据范围。
- 响应兼容前端 Ask UI 的 `{answer, citations, confidence, no_relevant_info}`。

非目标 / 禁止事项：
- 不要引入 dedicated runtime 转发；Task 7 处理。
- 不要让请求体携带可信 `enterprise_id`。
- 不要重写所有 ask prompt；只做 endpoint 收敛。
- 不要删除旧 `/api/ask` 和 `/api/customers/{id}/ask`，本任务先保留兼容。

相关文件：
- `platform/yunwei_win/api/ask.py`：现有跨客户问答。
- `platform/yunwei_win/api/customer_profile/ask.py`：现有单客户问答。
- `platform/yunwei_win/db.py`：基于 request.state.enterprise_id 获取 session。
- `platform/app-win/src/api/client.ts`：当前 `askAI()`。

实现要求：
1. 新建 `platform/yunwei_win/assistant/context.py`：
   ```python
   from __future__ import annotations
   from dataclasses import dataclass
   from platform_app.context import AuthContext
   from platform_app.entitlements import Entitlements

   @dataclass(frozen=True)
   class AssistantContext:
       auth: AuthContext
       entitlements: Entitlements
   ```
2. 新建 `platform/yunwei_win/assistant/service.py`，实现 `answer_shared_assistant(session, question, customer_id=None)`：
   - `customer_id is None or "all"` 调用现有 `services.qa.answer_question(session, question)`。
   - UUID customer 调用现有 customer ask helper。若现有函数耦合 router，先提取最小 service helper，不复制大段 KB 逻辑。
3. 新建 `platform/yunwei_win/assistant/router.py`：
   ```python
   from __future__ import annotations
   from pydantic import BaseModel, Field
   from fastapi import APIRouter, Depends, HTTPException, Request
   from sqlalchemy.ext.asyncio import AsyncSession
   from platform_app.entitlements import entitlements_for
   from yunwei_win.db import get_session
   from yunwei_win.services.llm import LLMCallFailed
   from .service import answer_shared_assistant

   router = APIRouter(prefix="/api/assistant")

   class AssistantChatRequest(BaseModel):
       question: str = Field(min_length=1, max_length=2000)
       customer_id: str | None = None

   @router.post("/chat")
   async def chat(payload: AssistantChatRequest, request: Request, session: AsyncSession = Depends(get_session)) -> dict:
       ctx = getattr(request.state, "auth_context", None)
       if ctx is None:
           raise HTTPException(401, {"error": "not_logged_in", "message": "请登录"})
       ent = entitlements_for(ctx)
       if not ent.can_use_shared_assistant:
           raise HTTPException(403, {"error": "assistant_not_enabled", "message": "当前套餐未开通问答"})
       try:
           result = await answer_shared_assistant(session, payload.question, customer_id=payload.customer_id)
       except LLMCallFailed as exc:
           raise HTTPException(502, f"upstream LLM error: {exc!s}") from exc
       await session.commit()
       return result
   ```
4. 修改 `platform/yunwei_win/__init__.py` include assistant router before/after existing ask routers.
5. 修改前端 `askAI(customerId, question)`：
   - POST `/assistant/chat` body `{ question, customer_id: customerId }`。
   - 兼容返回 shape 不变。
6. UI 文案把 `问 AI` 改为 `问小陈`。

测试要求：
- 新增 `platform/tests/test_yunwei_win_assistant.py`：
  - no login -> 401 via `/win/api/assistant/chat`。
  - trial enterprise can call assistant when LLM service is monkeypatched。
  - request body enterprise_id is ignored if present。
  - customer_id `"all"` routes to shared path。
- 运行：
  - `cd platform && ../.venv/bin/pytest tests/test_yunwei_win_assistant.py -q`
  - 前端路径移动后运行：`cd apps/yunwei-win-web && npm run check`
- 预期：
  - 新 endpoint 可用。
  - Ask UI 仍渲染 answer/evidence。

交付标准：
- 提交一个原子 commit：`feat(win): add shared assistant endpoint`
- 输出变更摘要、测试结果、剩余风险。
```

---

## Task 6: Add Runtime Registry for Pro/Max

**Files:**
- Create: `platform/migrations/010_runtime_registry.sql`
- Create: `platform/platform_app/runtime_registry.py`
- Test: `platform/tests/test_runtime_registry.py`
- Modify: `platform/tests/conftest.py`

### Task Brief: Agent F1

```text
你是 coding agent，在仓库 `/Users/eason/agent-platform` 工作。

任务：
新增 runtime registry，用于表达 Free/Lite pooled runtime 与 Pro/Max dedicated runtime 的绑定关系。

背景：
- 旧 `tenants(client_id, agent_id, container_url)` 是 dashboard/agent-list 时代的模型。
- 新模型按 capability 绑定 runtime，例如 `assistant`, `daily_report`, `erp_sync`。
- 本任务只新增 registry，不切换现有 proxy。

目标行为：
- Platform DB 有 `runtimes` 和 `runtime_bindings` 表。
- 可通过 Python helper 查询某 enterprise 的 capability binding。
- 测试清理逻辑覆盖新表。

非目标 / 禁止事项：
- 不要删除 `tenants` 表。
- 不要改 HMAC proxy。
- 不要把 runtime endpoint 暴露给前端。

相关文件：
- `platform/migrations/001_init.sql`：旧 tenants。
- `platform/platform_app/db.py`：DB helper style。
- `platform/tests/conftest.py`：TRUNCATE table list。

实现要求：
1. 新建 `platform/migrations/010_runtime_registry.sql`：
   ```sql
   CREATE TABLE IF NOT EXISTS runtimes (
     id           TEXT PRIMARY KEY,
     mode         TEXT NOT NULL,
     provider     TEXT NOT NULL,
     endpoint_url TEXT NOT NULL,
     health       TEXT NOT NULL DEFAULT 'unknown',
     version      TEXT NOT NULL DEFAULT 'unknown',
     created_at   BIGINT NOT NULL
   );

   CREATE TABLE IF NOT EXISTS runtime_bindings (
     enterprise_id TEXT NOT NULL REFERENCES enterprises(id),
     capability    TEXT NOT NULL,
     runtime_id    TEXT NOT NULL REFERENCES runtimes(id),
     enabled       INTEGER NOT NULL DEFAULT 1,
     created_at    BIGINT NOT NULL,
     PRIMARY KEY (enterprise_id, capability)
   );

   CREATE INDEX IF NOT EXISTS idx_runtime_bindings_runtime
     ON runtime_bindings(runtime_id);
   ```
2. 新建 `platform/platform_app/runtime_registry.py`：
   ```python
   from __future__ import annotations
   import time
   from dataclasses import dataclass
   from . import db

   @dataclass(frozen=True)
   class Runtime:
       id: str
       mode: str
       provider: str
       endpoint_url: str
       health: str
       version: str

   def get_runtime_for(enterprise_id: str, capability: str) -> Runtime | None:
       row = db.main().execute(
           "SELECT r.* FROM runtime_bindings b "
           "JOIN runtimes r ON r.id=b.runtime_id "
           "WHERE b.enterprise_id=%s AND b.capability=%s AND b.enabled=1",
           (enterprise_id, capability),
       ).fetchone()
       if not row:
           return None
       return Runtime(
           id=row["id"],
           mode=row["mode"],
           provider=row["provider"],
           endpoint_url=row["endpoint_url"],
           health=row["health"],
           version=row["version"],
       )

   def upsert_runtime(*, runtime_id: str, mode: str, provider: str, endpoint_url: str, version: str = "unknown") -> None:
       db.main().execute(
           "INSERT INTO runtimes (id, mode, provider, endpoint_url, version, created_at) "
           "VALUES (%s,%s,%s,%s,%s,%s) "
           "ON CONFLICT (id) DO UPDATE SET mode=EXCLUDED.mode, provider=EXCLUDED.provider, "
           "endpoint_url=EXCLUDED.endpoint_url, version=EXCLUDED.version",
           (runtime_id, mode, provider, endpoint_url, version, int(time.time())),
       )

   def bind_runtime(*, enterprise_id: str, capability: str, runtime_id: str) -> None:
       db.main().execute(
           "INSERT INTO runtime_bindings (enterprise_id, capability, runtime_id, created_at) "
           "VALUES (%s,%s,%s,%s) "
           "ON CONFLICT (enterprise_id, capability) DO UPDATE SET runtime_id=EXCLUDED.runtime_id, enabled=1",
           (enterprise_id, capability, runtime_id, int(time.time())),
       )
   ```
3. Update `platform/tests/conftest.py` TRUNCATE list to include `runtime_bindings, runtimes` before `enterprises`.
4. Add tests:
   - `get_runtime_for` returns None without binding.
   - binding returns Runtime.
   - rebinding updates runtime_id.

测试要求：
- 运行：
  - `cd platform && ../.venv/bin/pytest tests/test_runtime_registry.py tests/test_db.py -q`
- 预期：
  - migrations create tables.
  - registry helper works.

交付标准：
- 提交一个原子 commit：`feat(platform): add runtime registry`
- 输出变更摘要、测试结果、剩余风险。
```

---

## Task 7: Route Pro+ Assistant Calls to Dedicated Runtime

**Files:**
- Create: `platform/yunwei_win/assistant/dedicated.py`
- Modify: `platform/yunwei_win/assistant/router.py`
- Modify: `platform/yunwei_win/assistant/service.py`
- Test: `platform/tests/test_yunwei_win_assistant_runtime.py`

### Task Brief: Agent F2

```text
你是 coding agent，在仓库 `/Users/eason/agent-platform` 工作。

任务：
让 `/win/api/assistant/chat` 对 Pro/Max 企业优先调用 dedicated runtime；没有 binding 或 runtime unhealthy 时降级到 shared assistant。

背景：
- Task 5 已新增 shared assistant endpoint。
- Task 6 已新增 runtime registry。
- 前端入口不变，runtime 选择是服务端策略。

目标行为：
- trial/lite: always shared assistant。
- pro/max with `assistant` runtime binding: forward to dedicated runtime endpoint。
- pro/max without binding: shared assistant fallback。
- dedicated runtime response normalized to existing `{answer, citations, confidence, no_relevant_info}`。

非目标 / 禁止事项：
- 不要让前端直接知道 runtime endpoint。
- 不要删除 old HMAC proxy。
- 不要实现 streaming；先做 JSON forwarding。

相关文件：
- `platform/platform_app/runtime_registry.py`：runtime lookup。
- `platform/platform_app/entitlements.py`：plan policy。
- `platform/yunwei_win/assistant/router.py`：unified endpoint。

实现要求：
1. 新建 `platform/yunwei_win/assistant/dedicated.py`：
   ```python
   from __future__ import annotations
   import httpx

   class DedicatedRuntimeError(Exception):
       pass

   async def ask_dedicated_runtime(endpoint_url: str, *, question: str, customer_id: str | None, user_id: str) -> dict:
       url = endpoint_url.rstrip("/") + "/assistant/chat"
       payload = {"question": question, "customer_id": customer_id, "user_id": user_id}
       async with httpx.AsyncClient(timeout=httpx.Timeout(connect=5.0, read=60.0, write=30.0, pool=5.0)) as client:
           try:
               resp = await client.post(url, json=payload)
           except httpx.HTTPError as exc:
               raise DedicatedRuntimeError(str(exc)) from exc
       if resp.status_code >= 500:
           raise DedicatedRuntimeError(f"runtime HTTP {resp.status_code}")
       if resp.status_code >= 400:
           return {
               "answer": "专属运行时暂时无法回答，请稍后重试。",
               "citations": [],
               "confidence": 0.0,
               "no_relevant_info": True,
           }
       body = resp.json()
       return {
           "answer": body.get("answer", ""),
           "citations": body.get("citations") or [],
           "confidence": float(body.get("confidence", 0.5)),
           "no_relevant_info": bool(body.get("no_relevant_info", False)),
       }
   ```
2. Modify router logic:
   - `ent = entitlements_for(ctx)`.
   - If `ent.can_use_dedicated_runtime`, call `runtime_registry.get_runtime_for(ctx.enterprise_id, "assistant")`.
   - If runtime exists and health != "unhealthy", call dedicated.
   - On `DedicatedRuntimeError`, fallback to shared assistant and include no raw endpoint details in user response.
3. Add tests using `respx`:
   - pro with runtime binding forwards to runtime.
   - pro without binding uses shared service monkeypatch.
   - runtime 500 falls back to shared service.
   - lite with binding still does not call dedicated.

测试要求：
- 运行：
  - `cd platform && ../.venv/bin/pytest tests/test_yunwei_win_assistant_runtime.py -q`
- 预期：
  - runtime routing policy behaves by plan.

交付标准：
- 提交一个原子 commit：`feat(win): route pro assistant to dedicated runtime`
- 输出变更摘要、测试结果、剩余风险。
```

---

## Task 8: Legacy Cleanup and Archive

**Files:**
- Delete or archive: `app/`
- Archive: `platform/static/agents.html`
- Modify: `ops/docker-compose.yml` or move to `infra/local/docker-compose.yml`
- Modify: `docs/PLAN.md` or move to `docs/migration/legacy-agent-dashboard-plan.md`
- Modify: tests for platform chat UI routing if `app/` is removed
- Test: full relevant suite

### Task Brief: Agent G

```text
你是 coding agent，在仓库 `/Users/eason/agent-platform` 工作。

任务：
清理 dashboard/agent-list/chat scaffold legacy，使主线代码只保留 Win portal、platform control plane、runtime gateway。

背景：
- Task 1-7 已建立新命名、新 portal、新 shared assistant 和 runtime registry。
- `app/` 是旧 platform chat UI scaffold。
- `platform/static/agents.html` 是旧 customer-facing dashboard。
- `ops/docker-compose.yml` 默认包含 `agent-yinhu-super-xiaochen`，不应再代表默认生产路径。

目标行为：
- 主用户路径不依赖 dashboard 或 `app/` chat scaffold。
- legacy docs 被归档，不再作为当前实施主线。
- Pro/Max runtime 仍有 gateway/contract 文档。

非目标 / 禁止事项：
- 不要删除 `platform_app.proxy`。
- 不要删除 runtime registry。
- 不要删除 `/api/agents`，除非所有测试和 admin/debug 替代路径已就绪。
- 不要删除任何真实 secret 文件。

相关文件：
- `app/`：legacy chat scaffold。
- `platform/tests/test_platform_chat_ui_routing.py`：可能变为无效，需要删除或重写为 runtime gateway test。
- `platform/static/agents.html`：legacy dashboard。
- `ops/docker-compose.yml`：local infra definition。
- `docs/PLAN.md`、`docs/SSO.md`：旧 agent-dashboard 主线。

实现要求：
1. 如果 `app/` 已无引用，删除 `app/` 并移除 Dockerfile 对 app/dist 的旧逻辑。
2. 删除或重写 `platform/tests/test_platform_chat_ui_routing.py`：
   - 如果 `/<client>/<agent>/` gateway 仍保留，只测 proxy/gateway，不测 `app/dist`。
3. 把 `platform/static/agents.html` 移到 `docs/migration/archive/agents-dashboard.html`，或保留为 `/admin/agents` 的 internal-only 静态页。二选一，优先 archive。
4. 把 `ops/docker-compose.yml` 移到 `infra/local/docker-compose.yml`，并移除默认 `agent-yinhu-super-xiaochen` service；如果需要示例，放到 `runtimes/examples/yinhu-super-xiaochen.compose.yml`。
5. 新建 `runtimes/README.md`，写清 dedicated runtime contract：
   - health endpoint
   - assistant endpoint
   - auth/HMAC expectations
   - no customer-facing direct URL
6. 新建 `docs/architecture/platform-v3.md`，总结最终边界：
   - platform_app
   - yunwei_win
   - shared assistant
   - dedicated runtime
   - data plane

测试要求：
- 运行：
  - `cd platform && ../.venv/bin/pytest tests/test_page_routes.py tests/test_proxy.py tests/test_runtime_registry.py tests/test_yunwei_win_assistant.py -q`
  - `cd apps/yunwei-win-web && npm run build`
- 预期：
  - customer path `/` -> `/win/`。
  - shared assistant still works。
  - proxy/gateway tests still pass。

交付标准：
- 提交一个原子 commit 或最多两个 commits：
  - `refactor(platform): remove legacy dashboard path`
  - `docs(architecture): archive legacy agent dashboard plan`
- 输出变更摘要、测试结果、剩余风险。
```

---

## Task 9: Final Verification and Deployment Readiness

**Files:**
- Modify: `docs/architecture/platform-v3.md`
- Modify: `docs/migration/legacy-removal.md`
- Modify: `infra/railway/platform-api.md`
- Modify: `infra/local/README.md`

### Task Brief: Release Agent

```text
你是 release/verification agent，在仓库 `/Users/eason/agent-platform` 工作。

任务：
验证 platform v3 重构后的主路径，并补齐部署/回滚文档。

背景：
- 前序任务已完成代码重构。
- 本任务不做大功能，只做验证和上线准备。

目标行为：
- 本地测试覆盖 auth, /win portal, shared assistant, runtime registry, runtime gateway。
- 文档说明如何部署 platform-api 和 win worker。
- 文档说明如何回滚到上一个 release。

非目标 / 禁止事项：
- 不要引入新功能。
- 不要修改业务逻辑，除非验证发现明确 bug。

验证命令：
- `cd platform && ../.venv/bin/pytest -q`
- `cd apps/yunwei-win-web && npm run build`
- 如果 Docker 可用：`docker build -f platform/Dockerfile -t platform-api:v3 .`

文档要求：
- `docs/architecture/platform-v3.md`：最终边界和 request flow。
- `docs/migration/legacy-removal.md`：删除了什么、保留了什么、为什么。
- `infra/railway/platform-api.md`：web service start command 和 worker start command。
- `infra/local/README.md`：本地启动方式。

交付标准：
- 所有验证命令已运行并记录结果。
- 文档没有未完成占位符。
- 输出 release readiness summary 和 rollback notes。
```

---

## Self-Review

- Spec coverage: This plan covers filesystem restructure, `yinhu_brain` -> `yunwei_win`, `/` -> `/win/`, shared assistant for Pro below, runtime registry for Pro+, dedicated runtime adapter, and legacy cleanup.
- Placeholder scan: No unfinished placeholder markers are present. Future work is explicitly out of scope or assigned to later tasks.
- Type consistency: `AuthContext`, `Entitlements`, `Runtime`, and assistant response shape are defined once and reused consistently.
- Scope risk: The full target filesystem under `services/platform-api` is intentionally not forced in one task. The first milestone uses the current `platform/` service root to reduce migration blast radius while still fixing product boundaries.
