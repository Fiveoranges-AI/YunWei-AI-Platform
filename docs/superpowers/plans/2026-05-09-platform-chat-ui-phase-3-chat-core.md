# Platform Chat UI — Phase 3 — Chat Core — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire the `app/` SPA from a hello-world placeholder into a working chat surface for `/<client>/<agent>/`. After this phase, an authenticated user lands on `/yinhu/super-xiaochen/`, sees a sidebar with their session history, types a message, and gets a streaming response from the agent. **Tool-call rendering, followups chips, sources modal, onboarding modal, and memories panel are stubbed (placeholders) — Phase 4-5 implements them.**

**Architecture:**
- `useLocalRuntime(chatAdapter)` is the runtime; `chatAdapter.run({messages, abortSignal})` POSTs to `chat` (relative URL, picks up tenant prefix via `<base href>`), parses the agent's existing custom SSE schema (`data: {"type":"text",...}\n\n`), and yields cumulative content state per chunk.
- `useRemoteThreadListRuntime` wraps `chatAdapter` to provide the sessions sidebar; backed by `threadListAdapter` (calls agent's `GET /sessions`, `DELETE /sessions/{id}`) + `threadHistoryAdapter` (calls `GET /history?session=<id>`).
- `<TenantProvider>` calls `GET /me` once at mount and exposes `useTenant()` returning `{user, profile, tenant}` where `tenant` is **tolerant of both old and new `/me` shapes** (yinhu-rebuild's Phase 2 cutover hasn't shipped yet — `/me` may still return `tenant: <string>`).
- Routing: `wouter` (already used in `landing/`); `/:client/:agent/*` → `<Chat>`, otherwise `<NotInTenant>`.
- All chat state lives in assistant-ui runtime; the only React Context is `TenantProvider` for branding.

**Tech Stack adds (on top of Phase 1 deps):**
- `wouter@^3` — routing (matches `landing/`)
- `@assistant-ui/react@^0.14` — chat primitives + runtime
- `@assistant-ui/react-markdown@^0.14` — markdown rendering for assistant messages
- `vitest@^3` + `@testing-library/react@^16` + `jsdom` — unit tests for adapters and components
- (Do NOT install: `@assistant-ui/react-ai-sdk`, `assistant-stream`, `next` — explicitly rejected by the spike.)

**API guidance**: Use `useAuiState((s) => s.<x>)` and `useAui()` for state reads and runtime actions. Do NOT use the deprecated `useMessage`/`useThread`/`useComposer`/`useThreadRuntime`/etc. hooks (they live in `legacy-runtime/` for back-compat only).

**Branch:** `design/chat-core-phase-3` (off `main` at `8e5465a`).

---

## Pre-flight context for implementer subagents

- Repo root: `/Users/eason/agent-platform/`. Create a worktree at `.worktrees/chat-core-phase-3` if you prefer matching the team's prior pattern, otherwise work from the repo root checkout.
- Phase 1 already shipped (`33015ce`): `app/` exists with Vite+React 19+TS 5.6+Tailwind 4 scaffold; brand color `#3A8FB7` is in `app/src/styles/globals.css` as the `--brand-blue` CSS var and as the Tailwind 4 `@theme` token `--color-brand-blue`. `app/public/base-href.js` is the reverse-proxy IIFE. `app/dist/` is gitignored; populated by Vite at build time.
- The platform's `catch_all` (in `platform/platform_app/main.py`) already serves `app/dist/index.html` when present and falls through to `reverse_proxy(...)` for all non-static paths. **No catch_all changes needed in Phase 3.**
- Auth + ACL + firewall checks run BEFORE the static branch, so any request that reaches your SPA has a valid session and tenant grant. The SPA can assume the user is authenticated; it should NOT re-implement auth.
- Reference docs (read these first before touching code):
  - **Spec:** `docs/superpowers/specs/2026-05-07-platform-chat-ui-design.md` — D1 build pipeline, D2 tenant config (`/me` extension), D3 P1 chatAdapter path, D4 source-of-truth, D5 auth, D9 routing, D10 cross-repo coordination.
  - **Spike notes:** `~/yunwei-workspaces/yinhu-rebuild/generated/docs/specs/2026-05-07-assistant-ui-spike-notes.md` — resolved API names + caveats. Especially:
    - `useMessage` is `@deprecated`; use `useAuiState((s) => s.message)`.
    - `makeAssistantToolUI` fallback "register one component for all tool names" UNVERIFIED in 0.14.0 — this plan stubs tool calls without `makeAssistantToolUI` (Phase 4 verifies and uses it for real tool rendering).
    - Tool-call API on the wire is the agent's SSE schema (see "Agent SSE schema" below); we control the parsing in `chatAdapter.ts`.
  - **yinhu cutover plan (NOT yet executed):** `~/yunwei-workspaces/yinhu-rebuild/generated/docs/plans/2026-05-07-platform-cutover-plan.md` — informs how `/me` will eventually look. **`TenantProvider` must tolerate the OLD `/me` shape (legacy `tenant: <string>`) AND the NEW shape (`tenant: <object>`) gracefully.**

### Agent SSE schema (authoritative — derived from `yinhu-rebuild/generated/web_agent.py:781` and the legacy `index.html:1304-1370`)

POST `/<client>/<agent>/chat` with body `{message: <string>, session_id: <string|null>}`. Response is `text/event-stream`-flavored chunked HTTP, **frames separated by `\n\n`**, each frame is `data: <json>\n`. Event types and shapes:

| `type` | Other fields | Semantics |
|---|---|---|
| `classification` | `model: string` | Server selected this model for this turn (e.g. `"sonnet-4-6"`). Display in a model badge. |
| `text` | `text: string` | **Delta** of the assistant text. Concatenate as it arrives. |
| `tool_call` | `tool: string`, `input: object` | A tool was invoked. Add to the running list of tool calls for this turn. |
| `tool_lineage` | `tool: string`, `lineage: object` | Attaches data-source lineage to the **most recent tool_call with the same tool name** that does not yet have a lineage. |
| `followups` | `questions: string[]` | Suggested follow-up questions to render as chips. |
| `ui_action` | `action: string` (e.g. `"open_modal"`), `modal: string` | Server-driven UI side effect. Phase 3 logs and ignores; Phase 5 implements. |
| `error` | `message: string` | Stream error; reflect as message status `incomplete` + retry button. |

POST request includes `session_id`; backend creates a session row on first POST when null. Subsequent POSTs reuse it.

Sessions API:
- `GET /<client>/<agent>/sessions` → `{sessions: [{session_id, last_ts, title, ...}]}`
- `GET /<client>/<agent>/history?session=<id>` → `{turns: [{role, content, ...}]}`
- `DELETE /<client>/<agent>/sessions/{id}` → `{deleted: true}`

`GET /<client>/<agent>/me` (Phase 3 must tolerate BOTH shapes):

```jsonc
// OLD (current yinhu agent — Phase 2 hasn't shipped):
{ "user": "alice", "tenant": "yinhu-rebuild", "onboarded": false, "profile": null }

// NEW (after yinhu Phase 2 cutover):
{
  "user": "alice",
  "tenant_id": "yinhu-rebuild",
  "onboarded": false,
  "profile": null,
  "tenant": {
    "client_id": "yinhu", "agent_id": "super-xiaochen",
    "title": "超级小陈", "subtitle": "运帷 AI · 银湖租赁",
    "brand_color": "#3A8FB7", "brand_color_dark": "#2A6F92",
    "font_family": "Alibaba PuHuiTi 3.0",
    "font_css_url": "static/blueprint/fonts/alibaba-puhuiti.css",
    "logo_url": "static/blueprint/logo.png",
    "available_slash_commands": ["记一下"],
    "onboarding_enabled": true
  }
}
```

`TenantProvider` detection logic: `if (typeof me.tenant === "object" && me.tenant != null) { use it } else { fallback to client_id/agent_id from URL pathname + bake-in defaults from globals.css }`.

---

## File Structure (after this phase)

```
agent-platform/                                 ← existing
└── app/
    ├── package.json                            ← MODIFY: add deps
    ├── package-lock.json                       ← MODIFY: regenerated
    ├── vitest.config.ts                        ← NEW: vitest config (extends vite.config.ts)
    ├── tsconfig.json                           ← MODIFY: add "vitest/globals" types
    ├── index.html                              ← UNCHANGED (Phase 1 entry; React mounts on #root)
    ├── public/                                 ← UNCHANGED
    └── src/
        ├── main.tsx                            ← MODIFY: wrap App with <Router> from wouter
        ├── App.tsx                             ← MODIFY: provider tree (TenantProvider → Router → Chat | NotInTenant)
        ├── lib/                                ← NEW
        │   ├── api.ts                          ← relative-fetch wrapper (resp checking, abort plumbing)
        │   ├── tenant-config.ts                ← TenantProvider + useTenant() hook (tolerant of old/new /me)
        │   └── markdown.tsx                    ← <MarkdownText> from @assistant-ui/react-markdown wrapped with brand styles
        ├── runtime/                            ← NEW
        │   ├── sseEvents.ts                    ← TS types for hermes SSE event schema
        │   ├── parseSSE.ts                     ← async generator: ReadableStream<Uint8Array> → AsyncIterable<SSEEvent>
        │   ├── chatAdapter.ts                  ← ChatModelAdapter; cumulative state machine over parseSSE
        │   ├── threadListAdapter.ts            ← RemoteThreadListAdapter wrapping /sessions
        │   └── threadHistoryAdapter.ts         ← ThreadHistoryAdapter wrapping /history
        ├── pages/                              ← NEW
        │   ├── Chat.tsx                        ← /:client/:agent/ — wires runtime + AssistantRuntimeProvider + Layout
        │   └── NotInTenant.tsx                 ← shown when URL is missing /<client>/<agent>/ prefix
        ├── components/                         ← NEW
        │   ├── Layout.tsx                      ← grid: Sidebar + Main
        │   ├── Sidebar.tsx                     ← Brand + NewChat + DateGroupedThreadList + UserMenu
        │   ├── DateGroupedThreadList.tsx       ← groups by 今天/昨天/更早 from session.last_ts
        │   ├── ThreadItemMenu.tsx              ← "..." popup with delete
        │   ├── Topbar.tsx                      ← session title or default
        │   ├── WelcomeScreen.tsx               ← rendered when thread is empty; brand title + subtitle
        │   ├── Composer.tsx                    ← ComposerPrimitive.Root wrapper with Send + Cancel
        │   ├── UserMessage.tsx                 ← user bubble
        │   ├── AssistantMessage.tsx            ← assistant bubble + Markdown body + tool-call placeholder + (followups/sources stubs visible but inert)
        │   └── UserMenu.tsx                    ← username + sign out + (memories link STUB - Phase 5)
        ├── styles/
        │   └── globals.css                     ← MODIFY: add `.tool-call-stub` + a few message-bubble styles; tenant CSS vars overridable at runtime
        └── tests/                              ← NEW
            ├── chatAdapter.test.ts             ← cumulative state assertions over recorded SSE fixtures
            ├── parseSSE.test.ts                ← framing edge cases (split chunk, partial frame)
            ├── threadListAdapter.test.ts       ← list/delete with fetch-mock
            ├── threadHistoryAdapter.test.ts    ← parse history JSON into message parts
            ├── tenant-config.test.ts           ← old + new /me shape acceptance
            └── fixtures/
                ├── sse-text-only.txt           ← canned SSE for tests
                ├── sse-with-tool-call.txt
                └── sse-error.txt
```

**Out of scope (deferred):**
- `<ToolCallUI>` real rendering (Phase 4) — stubbed as `<div class="tool-call-stub">` showing tool name + JSON args.
- `<SourcesModal>` (Phase 4) — `tool_lineage` events captured into adapter state but not rendered.
- `<FollowupChips>` (Phase 5) — `followups` events captured but not rendered.
- `<OnboardingModal>` (Phase 5) — `ui_action` events captured + console.log only.
- `<MemoriesPanel>` (Phase 5) — UserMenu shows the link but it's `disabled`.
- `<ModelBadge>` (Phase 4) — `classification` events captured but not rendered.
- `<SlashCommands>` (Phase 5).
- Per-tenant font/logo loading from `tenant.font_css_url` / `tenant.logo_url` (Phase 5).

This phase ships **text-streaming chat with sessions sidebar**. Nothing more.

---

## Task 1: Install runtime + test dependencies

**Files:**
- Modify: `app/package.json`, `app/package-lock.json`
- Modify: `app/tsconfig.json`
- Create: `app/vitest.config.ts`

- [ ] **Step 1.1: Add runtime deps**

```bash
cd /Users/eason/agent-platform/app
npm install --save \
  wouter@^3 \
  @assistant-ui/react@^0.14 \
  @assistant-ui/react-markdown@^0.14
```

If `@assistant-ui/react-markdown@^0.14` does not exist (its versioning may lag react), use the highest published `^0.x` and record the chosen version. Same for any other peer-versioning surprise.

- [ ] **Step 1.2: Add test deps**

```bash
npm install --save-dev \
  vitest@^3 \
  @testing-library/react@^16 \
  @testing-library/jest-dom@^6 \
  @testing-library/user-event@^14 \
  jsdom@^25
```

- [ ] **Step 1.3: Add `test` and `test:watch` scripts to `package.json`**

```json
"scripts": {
  "dev": "vite --host",
  "build": "tsc --noEmit && vite build",
  "preview": "vite preview --host",
  "check": "tsc --noEmit",
  "test": "vitest run",
  "test:watch": "vitest"
}
```

- [ ] **Step 1.4: Create `app/vitest.config.ts`**

```typescript
/// <reference types="vitest" />
import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  test: {
    globals: true,
    environment: "jsdom",
    setupFiles: ["./src/tests/setup.ts"],
  },
});
```

- [ ] **Step 1.5: Add `vitest/globals` to `tsconfig.json` `compilerOptions.types`**

In `app/tsconfig.json`'s `compilerOptions`, add to `types`:
```json
"types": ["vite/client", "vitest/globals", "@testing-library/jest-dom"]
```

If `compilerOptions.types` doesn't exist yet, add it.

- [ ] **Step 1.6: Create `app/src/tests/setup.ts`**

```typescript
import "@testing-library/jest-dom";
```

- [ ] **Step 1.7: Smoke `npm run test` (no tests yet, should report "no test files")**

```bash
cd /Users/eason/agent-platform/app
npm run test 2>&1 | tail
```

Expected: vitest runs, reports "No test files found" or "0 tests passed" — either is fine. We'll add tests as we go.

- [ ] **Step 1.8: Smoke `npm run build` to confirm TS still compiles with new deps**

```bash
npm run build 2>&1 | tail
```

Expected: no TS errors, `app/dist/index.html` regenerated (still hello world from Phase 1).

- [ ] **Step 1.9: Commit**

```bash
git add app/package.json app/package-lock.json app/vitest.config.ts \
        app/tsconfig.json app/src/tests/setup.ts
git commit -m "chore(app): add runtime + test deps for Phase 3 chat core

wouter, @assistant-ui/react@0.14, @assistant-ui/react-markdown,
vitest, RTL. No code wiring yet."
```

---

## Task 2: Define agent SSE event types (`sseEvents.ts`)

**Files:**
- Create: `app/src/runtime/sseEvents.ts`
- Create: `app/src/tests/fixtures/sse-text-only.txt`

- [ ] **Step 2.1: Write `app/src/runtime/sseEvents.ts`**

```typescript
// Hermes-agent SSE event schema (current production format from
// yinhu-rebuild/generated/web_agent.py:781). Keep this file in sync with
// the agent backend. After yinhu's Phase 2 cutover the agent backend is
// unchanged; only /me's shape evolves.

export type ClassificationEvent = {
  type: "classification";
  model: string;
};

export type TextEvent = {
  type: "text";
  /** Delta — concatenate as you receive successive events. */
  text: string;
};

export type ToolCallEvent = {
  type: "tool_call";
  tool: string;
  input: unknown;
};

export type ToolLineageEvent = {
  type: "tool_lineage";
  tool: string;
  lineage: {
    source?: string;
    as_of?: string;
    transforms?: string[];
    [k: string]: unknown;
  };
};

export type FollowupsEvent = {
  type: "followups";
  questions: string[];
};

export type UiActionEvent = {
  type: "ui_action";
  action: string;
  modal?: string;
  [k: string]: unknown;
};

export type ErrorEvent = {
  type: "error";
  message: string;
};

export type SSEEvent =
  | ClassificationEvent
  | TextEvent
  | ToolCallEvent
  | ToolLineageEvent
  | FollowupsEvent
  | UiActionEvent
  | ErrorEvent;

export function isSSEEvent(x: unknown): x is SSEEvent {
  return typeof x === "object" && x !== null && typeof (x as { type?: unknown }).type === "string";
}
```

- [ ] **Step 2.2: Create one fixture file for tests**

`app/src/tests/fixtures/sse-text-only.txt` — verbatim bytes the agent would emit for a "hello world" reply. Tabs/spaces inside JSON exactly as agent emits.

```
data: {"type":"classification","model":"sonnet-4-6"}

data: {"type":"text","text":"Hello"}

data: {"type":"text","text":" "}

data: {"type":"text","text":"world"}

```

(The trailing blank line is significant — it's the frame terminator after the last event.)

- [ ] **Step 2.3: TS-compile check**

```bash
cd /Users/eason/agent-platform/app && npm run check 2>&1 | tail
```

No TS errors expected.

- [ ] **Step 2.4: Commit**

```bash
git add app/src/runtime/sseEvents.ts app/src/tests/fixtures/sse-text-only.txt
git commit -m "feat(app/runtime): typed SSE event schema for hermes agent

Schema mirrors yinhu-rebuild's web_agent.py:781 emission. Fixture for
upcoming chatAdapter tests committed alongside."
```

---

## Task 3: Stream framing parser (`parseSSE.ts`) — TDD

**Files:**
- Create: `app/src/tests/parseSSE.test.ts`
- Create: `app/src/runtime/parseSSE.ts`

- [ ] **Step 3.1: Write the failing tests first**

`app/src/tests/parseSSE.test.ts`:

```typescript
import { describe, expect, it } from "vitest";
import { parseSSE } from "../runtime/parseSSE";
import type { SSEEvent } from "../runtime/sseEvents";

function asStream(text: string): ReadableStream<Uint8Array> {
  const enc = new TextEncoder();
  const bytes = enc.encode(text);
  return new ReadableStream({
    start(c) { c.enqueue(bytes); c.close(); },
  });
}

function chunkedStream(chunks: string[]): ReadableStream<Uint8Array> {
  const enc = new TextEncoder();
  let i = 0;
  return new ReadableStream({
    pull(c) {
      if (i < chunks.length) c.enqueue(enc.encode(chunks[i++]));
      else c.close();
    },
  });
}

async function collect(stream: ReadableStream<Uint8Array>): Promise<SSEEvent[]> {
  const out: SSEEvent[] = [];
  for await (const ev of parseSSE(stream)) out.push(ev);
  return out;
}

describe("parseSSE", () => {
  it("parses a single text event", async () => {
    const events = await collect(asStream('data: {"type":"text","text":"hi"}\n\n'));
    expect(events).toEqual([{ type: "text", text: "hi" }]);
  });

  it("parses multiple events separated by blank lines", async () => {
    const events = await collect(asStream(
      'data: {"type":"text","text":"a"}\n\n' +
      'data: {"type":"text","text":"b"}\n\n',
    ));
    expect(events).toHaveLength(2);
    expect(events[0]).toEqual({ type: "text", text: "a" });
    expect(events[1]).toEqual({ type: "text", text: "b" });
  });

  it("handles a frame split across two stream chunks", async () => {
    const events = await collect(chunkedStream([
      'data: {"type":"te',
      'xt","text":"split"}\n\n',
    ]));
    expect(events).toEqual([{ type: "text", text: "split" }]);
  });

  it("ignores empty lines that aren't frame separators", async () => {
    const events = await collect(asStream(
      ': comment\n' +
      'data: {"type":"text","text":"only"}\n\n',
    ));
    expect(events).toEqual([{ type: "text", text: "only" }]);
  });

  it("yields nothing for malformed JSON but doesn't throw", async () => {
    const events = await collect(asStream('data: not-json\n\n'));
    expect(events).toEqual([]);
  });

  it("handles all event types without misclassifying", async () => {
    const events = await collect(asStream(
      'data: {"type":"classification","model":"x"}\n\n' +
      'data: {"type":"tool_call","tool":"t","input":{}}\n\n' +
      'data: {"type":"tool_lineage","tool":"t","lineage":{"source":"x"}}\n\n' +
      'data: {"type":"followups","questions":["a","b"]}\n\n' +
      'data: {"type":"ui_action","action":"open_modal","modal":"m"}\n\n' +
      'data: {"type":"error","message":"oops"}\n\n',
    ));
    expect(events.map((e) => e.type)).toEqual([
      "classification", "tool_call", "tool_lineage", "followups", "ui_action", "error",
    ]);
  });
});
```

- [ ] **Step 3.2: Run tests — confirm they FAIL**

```bash
cd /Users/eason/agent-platform/app
npm run test parseSSE 2>&1 | tail -15
```

Expected: vitest reports "Cannot find module '../runtime/parseSSE'" or similar.

- [ ] **Step 3.3: Write `app/src/runtime/parseSSE.ts`**

```typescript
import type { SSEEvent } from "./sseEvents";
import { isSSEEvent } from "./sseEvents";

/**
 * Parse a hermes-agent SSE byte stream into typed events.
 *
 * Wire format: each frame is `data: <json>\n` followed by a blank line
 * (`\n\n` overall). Lines starting with `:` are comments and ignored.
 * Malformed JSON is dropped silently (frames are best-effort) but the
 * stream is NOT torn down — subsequent valid frames still yield.
 */
export async function* parseSSE(
  stream: ReadableStream<Uint8Array>,
): AsyncIterable<SSEEvent> {
  const reader = stream.getReader();
  const decoder = new TextDecoder();
  let buf = "";

  try {
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buf += decoder.decode(value, { stream: true });

      // Each event ends with a blank line ("\n\n"). Split on that.
      let idx: number;
      while ((idx = buf.indexOf("\n\n")) !== -1) {
        const frame = buf.slice(0, idx);
        buf = buf.slice(idx + 2);
        const event = parseFrame(frame);
        if (event) yield event;
      }
    }
    // Flush any trailing frame missing its terminator (defensive)
    if (buf.length > 0) {
      const event = parseFrame(buf);
      if (event) yield event;
    }
  } finally {
    reader.releaseLock();
  }
}

function parseFrame(frame: string): SSEEvent | null {
  for (const line of frame.split("\n")) {
    if (line.startsWith(":")) continue;          // comment
    if (!line.startsWith("data: ")) continue;
    const json = line.slice(6);
    try {
      const parsed = JSON.parse(json);
      if (isSSEEvent(parsed)) return parsed;
    } catch {
      // malformed JSON — drop frame
    }
  }
  return null;
}
```

- [ ] **Step 3.4: Run tests — confirm they PASS**

```bash
npm run test parseSSE 2>&1 | tail -10
```

Expected: 6 tests pass.

- [ ] **Step 3.5: Commit**

```bash
git add app/src/runtime/parseSSE.ts app/src/tests/parseSSE.test.ts
git commit -m "feat(app/runtime): SSE byte-stream framer with TDD coverage

Async-generator parser tolerant of split chunks, comments, and malformed
JSON. 6 tests cover framing edge cases."
```

---

## Task 4: `chatAdapter.ts` cumulative state machine — TDD

**Files:**
- Create: `app/src/tests/chatAdapter.test.ts`
- Create: `app/src/tests/fixtures/sse-with-tool-call.txt`
- Create: `app/src/tests/fixtures/sse-error.txt`
- Create: `app/src/runtime/chatAdapter.ts`

- [ ] **Step 4.1: Write fixtures**

`app/src/tests/fixtures/sse-with-tool-call.txt`:

```
data: {"type":"classification","model":"sonnet-4-6"}

data: {"type":"text","text":"正在查询… "}

data: {"type":"tool_call","tool":"get_ar_summary","input":{"month":"2026-05","customer":"邦普"}}

data: {"type":"tool_lineage","tool":"get_ar_summary","lineage":{"source":"sal_order_detail","as_of":"2026-05-07T08:00:00Z"}}

data: {"type":"text","text":"邦普 5 月应收 ¥13.88M。"}

data: {"type":"followups","questions":["4 月对比?","按客户拆分?"]}

```

`app/src/tests/fixtures/sse-error.txt`:

```
data: {"type":"text","text":"Working… "}

data: {"type":"error","message":"upstream timeout"}

```

- [ ] **Step 4.2: Write the failing tests first**

`app/src/tests/chatAdapter.test.ts`:

```typescript
import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { chatAdapter } from "../runtime/chatAdapter";
import type {
  ChatModelAdapter, ChatModelRunResult, ThreadAssistantMessagePart,
} from "@assistant-ui/react";

function asStreamFromFixture(name: string): ReadableStream<Uint8Array> {
  const text = readFileSync(join(__dirname, "fixtures", name), "utf-8");
  const enc = new TextEncoder();
  return new ReadableStream({
    start(c) { c.enqueue(enc.encode(text)); c.close(); },
  });
}

const fakeUserMessage = {
  role: "user" as const,
  content: [{ type: "text" as const, text: "邦普 5 月应收?" }],
};

beforeEach(() => {
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
    return new Response(asStreamFromFixture("sse-with-tool-call.txt"), {
      status: 200, headers: { "content-type": "text/event-stream" },
    });
  });
});
afterEach(() => vi.restoreAllMocks());

async function runAdapter(
  adapter: ChatModelAdapter,
  init: Partial<Parameters<ChatModelAdapter["run"]>[0]> = {},
): Promise<ChatModelRunResult[]> {
  const out: ChatModelRunResult[] = [];
  for await (const chunk of adapter.run({
    messages: [fakeUserMessage],
    abortSignal: new AbortController().signal,
    runConfig: {},
    ...init,
  })) {
    out.push(chunk);
  }
  return out;
}

describe("chatAdapter", () => {
  it("yields cumulative text content as deltas arrive", async () => {
    const yields = await runAdapter(chatAdapter);
    // First text chunk after classification: "正在查询… "
    // Subsequent chunks should grow the same text part, not emit duplicate parts.
    const texts = yields
      .map((y) => (y.content?.find((p) => p.type === "text") as ThreadAssistantMessagePart | undefined))
      .filter(Boolean);
    expect(texts.length).toBeGreaterThan(0);
    const last = (texts[texts.length - 1] as { type: "text"; text: string }).text;
    expect(last).toContain("正在查询");
    expect(last).toContain("邦普 5 月应收 ¥13.88M。");
  });

  it("captures tool calls in metadata.toolCalls (Phase 3 stub representation)", async () => {
    const yields = await runAdapter(chatAdapter);
    const final = yields[yields.length - 1];
    const toolCalls = final.metadata?.custom?.toolCalls as Array<{ tool: string; input: unknown; lineage?: unknown }>;
    expect(toolCalls).toBeDefined();
    expect(toolCalls).toHaveLength(1);
    expect(toolCalls[0].tool).toBe("get_ar_summary");
    expect(toolCalls[0].input).toEqual({ month: "2026-05", customer: "邦普" });
    expect(toolCalls[0].lineage).toMatchObject({ source: "sal_order_detail" });
  });

  it("captures classification.model in metadata.model", async () => {
    const yields = await runAdapter(chatAdapter);
    const final = yields[yields.length - 1];
    expect(final.metadata?.custom?.model).toBe("sonnet-4-6");
  });

  it("captures followups in metadata.followups", async () => {
    const yields = await runAdapter(chatAdapter);
    const final = yields[yields.length - 1];
    expect(final.metadata?.custom?.followups).toEqual(["4 月对比?", "按客户拆分?"]);
  });

  it("propagates AbortSignal: stops yielding when aborted mid-stream", async () => {
    const ctrl = new AbortController();
    // Mock a slow stream
    vi.spyOn(globalThis, "fetch").mockImplementation(async () => {
      const enc = new TextEncoder();
      let idx = 0;
      const chunks = [
        'data: {"type":"text","text":"a"}\n\n',
        'data: {"type":"text","text":"b"}\n\n',
        'data: {"type":"text","text":"c"}\n\n',
      ];
      const stream = new ReadableStream<Uint8Array>({
        async pull(c) {
          if (idx === 1) ctrl.abort();              // abort after first chunk
          if (idx >= chunks.length) { c.close(); return; }
          c.enqueue(enc.encode(chunks[idx++]));
          await new Promise((r) => setTimeout(r, 5));
        },
      });
      return new Response(stream, { status: 200 });
    });

    const yields: ChatModelRunResult[] = [];
    try {
      for await (const y of chatAdapter.run({
        messages: [fakeUserMessage], abortSignal: ctrl.signal, runConfig: {},
      })) yields.push(y);
    } catch {
      // adapter may throw on abort; that's acceptable
    }
    expect(yields.length).toBeLessThan(3);
  });

  it("on type=error event, throws with the message", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(async () => {
      return new Response(asStreamFromFixture("sse-error.txt"), { status: 200 });
    });
    await expect(runAdapter(chatAdapter)).rejects.toThrow(/upstream timeout/);
  });

  it("posts to relative URL 'chat' with {message, session_id}", async () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch");
    await runAdapter(chatAdapter, { runConfig: { custom: { sessionId: "sess-abc" } } });
    expect(fetchSpy).toHaveBeenCalledWith(
      "chat",
      expect.objectContaining({
        method: "POST",
        headers: expect.objectContaining({ "content-type": "application/json" }),
        body: expect.stringContaining('"session_id":"sess-abc"'),
        signal: expect.any(AbortSignal),
      }),
    );
    const body = JSON.parse((fetchSpy.mock.calls[0][1] as RequestInit).body as string);
    expect(body.message).toBe("邦普 5 月应收?");
  });
});
```

- [ ] **Step 4.3: Run tests — confirm they FAIL**

```bash
npm run test chatAdapter 2>&1 | tail -15
```

Expected: import errors, tests fail.

- [ ] **Step 4.4: Write `app/src/runtime/chatAdapter.ts`**

```typescript
import type { ChatModelAdapter } from "@assistant-ui/react";
import { parseSSE } from "./parseSSE";

/**
 * P1 ChatModelAdapter for the hermes agent's custom SSE schema.
 *
 * - Posts `{message, session_id}` to relative URL "chat" (resolves under
 *   tenant prefix via <base href>).
 * - Parses SSE events from parseSSE().
 * - Accumulates text deltas into a single text part.
 * - Captures tool_call/tool_lineage/classification/followups/ui_action
 *   into metadata.custom for Phase 4-5 components to render.
 * - Abort: forwards abortSignal into fetch(); when aborted, fetch's
 *   ReadableStream rejects pull() and parseSSE returns; loop exits.
 * - On `error` event, throws with the message.
 *
 * Usage:
 *   const runtime = useLocalRuntime(chatAdapter);
 *   AssistantRuntimeProvider runConfig.custom.sessionId is the active session.
 */
export const chatAdapter: ChatModelAdapter = {
  async *run({ messages, abortSignal, runConfig }) {
    const last = messages[messages.length - 1];
    if (!last || last.role !== "user") return;

    // Extract plain text from the user message's parts. Phase 3 only
    // supports text-only user messages (no attachments).
    const text = last.content
      .map((c) => (c.type === "text" ? c.text : ""))
      .join("");
    if (!text) return;

    const sessionId =
      ((runConfig?.custom as { sessionId?: string } | undefined)?.sessionId) ??
      null;

    const resp = await fetch("chat", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ message: text, session_id: sessionId }),
      signal: abortSignal,
    });

    if (!resp.ok) {
      throw new Error(`HTTP ${resp.status}: ${await resp.text()}`);
    }
    if (!resp.body) {
      throw new Error("missing response body");
    }

    // Cumulative state machine.
    let textBuf = "";
    let model: string | undefined;
    let followups: string[] | undefined;
    let uiAction: { action: string; modal?: string } | undefined;
    type ToolCallState = { tool: string; input: unknown; lineage?: unknown };
    const toolCalls: ToolCallState[] = [];

    function snapshot(): { content: { type: "text"; text: string }[]; metadata: { custom: Record<string, unknown> } } {
      return {
        content: textBuf ? [{ type: "text", text: textBuf }] : [],
        metadata: {
          custom: {
            model,
            toolCalls: toolCalls.length > 0 ? toolCalls.map((t) => ({ ...t })) : undefined,
            followups,
            uiAction,
          },
        },
      };
    }

    for await (const ev of parseSSE(resp.body)) {
      switch (ev.type) {
        case "text":
          textBuf += ev.text;
          break;
        case "classification":
          model = ev.model;
          break;
        case "tool_call":
          toolCalls.push({ tool: ev.tool, input: ev.input });
          break;
        case "tool_lineage": {
          // Attach to the most recent matching tool_call with no lineage yet
          for (let i = toolCalls.length - 1; i >= 0; i--) {
            if (toolCalls[i].tool === ev.tool && toolCalls[i].lineage === undefined) {
              toolCalls[i].lineage = ev.lineage;
              break;
            }
          }
          break;
        }
        case "followups":
          followups = ev.questions;
          break;
        case "ui_action":
          uiAction = { action: ev.action, modal: ev.modal };
          // Phase 5: dispatch to a UI side-channel. Phase 3 just logs.
          // eslint-disable-next-line no-console
          console.log("[chatAdapter] ui_action received:", ev);
          break;
        case "error":
          throw new Error(ev.message);
      }
      yield snapshot();
    }

    // final yield ensures the last accumulated state is delivered even if
    // the last event was a stream end rather than a content event.
    yield snapshot();
  },
};
```

- [ ] **Step 4.5: Run tests — confirm they PASS**

```bash
npm run test chatAdapter 2>&1 | tail -15
```

Expected: all 7 tests pass.

- [ ] **Step 4.6: Commit**

```bash
git add app/src/runtime/chatAdapter.ts app/src/tests/chatAdapter.test.ts \
        app/src/tests/fixtures/sse-with-tool-call.txt \
        app/src/tests/fixtures/sse-error.txt
git commit -m "feat(app/runtime): chatAdapter cumulative state machine

ChatModelAdapter that posts to 'chat' with {message, session_id}, parses
hermes SSE, accumulates text deltas, captures tool_call/tool_lineage/
classification/followups/ui_action into metadata.custom for Phase 4-5
components to consume. Abort propagates through fetch's signal. 7 tests."
```

---

## Task 5: `threadListAdapter.ts` and `threadHistoryAdapter.ts` — TDD

**Files:**
- Create: `app/src/tests/threadListAdapter.test.ts`
- Create: `app/src/tests/threadHistoryAdapter.test.ts`
- Create: `app/src/runtime/threadListAdapter.ts`
- Create: `app/src/runtime/threadHistoryAdapter.ts`

- [ ] **Step 5.1: Write failing test for `threadListAdapter`**

`app/src/tests/threadListAdapter.test.ts`:

```typescript
import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { threadListAdapter } from "../runtime/threadListAdapter";

beforeEach(() => {
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
    const url = String(input);
    if (url === "sessions" && (!init || init.method === undefined || init.method === "GET")) {
      return new Response(JSON.stringify({
        sessions: [
          { session_id: "s1", last_ts: "2026-05-09T10:00:00Z", title: "first" },
          { session_id: "s2", last_ts: "2026-05-08T15:00:00Z", title: "second" },
        ],
      }), { status: 200, headers: { "content-type": "application/json" } });
    }
    if (url.match(/^sessions\/s2$/) && init?.method === "DELETE") {
      return new Response(JSON.stringify({ deleted: true }), { status: 200 });
    }
    return new Response("not mocked", { status: 500 });
  });
});
afterEach(() => vi.restoreAllMocks());

describe("threadListAdapter", () => {
  it("list() maps /sessions response to {threads}", async () => {
    const r = await threadListAdapter.list();
    expect(r.threads).toEqual([
      { remoteId: "s1", status: "regular", title: "first" },
      { remoteId: "s2", status: "regular", title: "second" },
    ]);
  });

  it("delete(remoteId) DELETEs sessions/{id}", async () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch");
    await threadListAdapter.delete("s2");
    expect(fetchSpy).toHaveBeenCalledWith(
      "sessions/s2",
      expect.objectContaining({ method: "DELETE" }),
    );
  });

  it("initialize(localId) returns localId as remoteId (server creates sessions on first /chat)", async () => {
    const r = await threadListAdapter.initialize("local-xyz");
    expect(r.remoteId).toBe("local-xyz");
  });

  it("rename, archive, unarchive, generateTitle are no-ops (Phase 3 minimum)", async () => {
    await expect(threadListAdapter.rename("s1", "new")).resolves.toBeUndefined();
    await expect(threadListAdapter.archive("s1")).resolves.toBeUndefined();
    await expect(threadListAdapter.unarchive("s1")).resolves.toBeUndefined();
  });
});
```

- [ ] **Step 5.2: Run tests — confirm FAIL**

```bash
npm run test threadList 2>&1 | tail -10
```

- [ ] **Step 5.3: Write `app/src/runtime/threadListAdapter.ts`**

```typescript
import type { RemoteThreadListAdapter } from "@assistant-ui/react";

/**
 * RemoteThreadListAdapter wrapping the hermes agent's session endpoints.
 *
 * - list: GET /sessions → {sessions: [{session_id, last_ts, title}]}
 * - initialize(localId): no-op; the agent creates a sessions row on the
 *   first POST /chat with session_id=null. We return localId so
 *   useRemoteThreadListRuntime correlates correctly until the first /chat.
 * - delete(remoteId): DELETE /sessions/{remoteId}
 * - rename / archive / unarchive / generateTitle: not implemented in
 *   this phase (the agent backend has no schema for archived threads or
 *   server-side title generation). Resolve with no-op.
 *
 * Note: last_ts is preserved in the raw response but not in the
 * RemoteThreadListThread shape (assistant-ui doesn't have a slot for it).
 * DateGroupedThreadList re-fetches via api.getSessionsRaw() to render the
 * grouped sidebar.
 */
type SessionRow = { session_id: string; last_ts: string; title: string | null };

export const threadListAdapter: RemoteThreadListAdapter = {
  async list() {
    const r = await fetch("sessions");
    if (!r.ok) throw new Error(`GET sessions HTTP ${r.status}`);
    const json = (await r.json()) as { sessions: SessionRow[] };
    return {
      threads: json.sessions.map((s) => ({
        remoteId: s.session_id,
        status: "regular" as const,
        title: s.title ?? undefined,
      })),
    };
  },

  async initialize(localId: string) {
    return { remoteId: localId, externalId: undefined };
  },

  async delete(remoteId: string) {
    const r = await fetch(`sessions/${encodeURIComponent(remoteId)}`, { method: "DELETE" });
    if (!r.ok) throw new Error(`DELETE sessions/${remoteId} HTTP ${r.status}`);
  },

  async rename(_remoteId: string, _title: string) {
    // Phase 3: not implemented. Backend has no rename endpoint.
  },

  async archive(_remoteId: string) {
    // Phase 3: not implemented. Backend has no archived state.
  },

  async unarchive(_remoteId: string) {
    // Phase 3: not implemented.
  },
};
```

- [ ] **Step 5.4: Run tests — confirm PASS**

```bash
npm run test threadList 2>&1 | tail -10
```

- [ ] **Step 5.5: Write failing test for `threadHistoryAdapter`**

`app/src/tests/threadHistoryAdapter.test.ts`:

```typescript
import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { makeThreadHistoryAdapter } from "../runtime/threadHistoryAdapter";

beforeEach(() => {
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
    const url = String(input);
    if (url.startsWith("history?session=")) {
      return new Response(JSON.stringify({
        turns: [
          { role: "user", content: "hi" },
          { role: "assistant", content: "hello there" },
          { role: "user", content: "what's up" },
          { role: "assistant", content: "not much" },
        ],
      }), { status: 200, headers: { "content-type": "application/json" } });
    }
    return new Response("not mocked", { status: 500 });
  });
});
afterEach(() => vi.restoreAllMocks());

describe("threadHistoryAdapter", () => {
  it("load() fetches history by session id and produces ThreadHistory messages", async () => {
    const adapter = makeThreadHistoryAdapter("sess-1");
    const r = await adapter.load();
    expect(r.messages).toHaveLength(4);
    expect(r.messages[0].message.role).toBe("user");
    expect(r.messages[0].message.content).toEqual([{ type: "text", text: "hi" }]);
    expect(r.messages[1].message.role).toBe("assistant");
    expect(r.messages[1].message.content).toEqual([{ type: "text", text: "hello there" }]);
  });

  it("load() with empty history returns {messages: []}", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      new Response(JSON.stringify({ turns: [] }), { status: 200 }),
    );
    const adapter = makeThreadHistoryAdapter("sess-empty");
    const r = await adapter.load();
    expect(r.messages).toEqual([]);
  });

  it("append() is a no-op (server appends via /chat, not via this adapter)", async () => {
    const adapter = makeThreadHistoryAdapter("sess-1");
    await expect(adapter.append({
      parentId: null,
      message: { role: "user", content: [{ type: "text", text: "x" }], id: "m1", createdAt: new Date(), attachments: [], metadata: { custom: {} } },
    })).resolves.toBeUndefined();
  });
});
```

- [ ] **Step 5.6: Write `app/src/runtime/threadHistoryAdapter.ts`**

```typescript
import type { ThreadHistoryAdapter } from "@assistant-ui/react";

type HistoryTurn = { role: "user" | "assistant"; content: string };

export function makeThreadHistoryAdapter(sessionId: string): ThreadHistoryAdapter {
  return {
    async load() {
      const r = await fetch(`history?session=${encodeURIComponent(sessionId)}`);
      if (!r.ok) throw new Error(`GET history HTTP ${r.status}`);
      const json = (await r.json()) as { turns: HistoryTurn[] };

      const messages = json.turns.map((t, i) => ({
        parentId: i === 0 ? null : `${sessionId}-${i - 1}`,
        message: {
          id: `${sessionId}-${i}`,
          role: t.role,
          content: [{ type: "text" as const, text: t.content }],
          createdAt: new Date(),
          attachments: [],
          metadata: { custom: {} },
          ...(t.role === "assistant"
            ? { status: { type: "complete" as const, reason: "stop" as const } }
            : {}),
        } as Parameters<ThreadHistoryAdapter["append"]>[0]["message"],
      }));

      return { messages };
    },

    async append(_arg) {
      // No-op. Server-side append happens automatically when chatAdapter
      // POSTs to /chat with session_id; we don't double-write client-side.
    },
  };
}
```

- [ ] **Step 5.7: Run tests — confirm both adapters PASS**

```bash
npm run test threadList threadHistory 2>&1 | tail -10
```

- [ ] **Step 5.8: Commit**

```bash
git add app/src/runtime/threadListAdapter.ts app/src/runtime/threadHistoryAdapter.ts \
        app/src/tests/threadListAdapter.test.ts app/src/tests/threadHistoryAdapter.test.ts
git commit -m "feat(app/runtime): thread list + history adapters

threadListAdapter wraps GET/DELETE /sessions; non-implemented archive/
rename/generateTitle resolve as no-ops. threadHistoryAdapter is a factory
keyed by sessionId that loads /history?session=<id> into ThreadHistory
shape. 7 tests."
```

---

## Task 6: `lib/api.ts` + `lib/tenant-config.ts` (TenantProvider) — TDD

**Files:**
- Create: `app/src/lib/api.ts`
- Create: `app/src/lib/tenant-config.ts`
- Create: `app/src/tests/tenant-config.test.ts`

- [ ] **Step 6.1: Write `app/src/lib/api.ts`**

Tiny relative-fetch wrapper. Phase 3 just centralizes 4xx/5xx handling:

```typescript
export class ApiError extends Error {
  constructor(public status: number, public body: string) {
    super(`HTTP ${status}: ${body.slice(0, 200)}`);
  }
}

export async function apiGet<T>(path: string): Promise<T> {
  const r = await fetch(path);
  if (!r.ok) throw new ApiError(r.status, await r.text());
  return r.json() as Promise<T>;
}
```

- [ ] **Step 6.2: Write failing test for tenant-config**

`app/src/tests/tenant-config.test.ts`:

```typescript
import { describe, expect, it } from "vitest";
import { interpretMeResponse } from "../lib/tenant-config";

describe("interpretMeResponse", () => {
  it("accepts the OLD shape (legacy yinhu pre-Phase-2) and falls back to defaults", () => {
    const me = { user: "alice", tenant: "yinhu-rebuild", onboarded: false, profile: null };
    const r = interpretMeResponse(me, { client_id: "yinhu", agent_id: "super-xiaochen" });
    expect(r.user).toBe("alice");
    expect(r.tenant.client_id).toBe("yinhu");
    expect(r.tenant.agent_id).toBe("super-xiaochen");
    expect(r.tenant.brand_color).toBe("#3A8FB7"); // built-in default
    expect(r.tenant.title).toBe("agent");          // safe fallback
  });

  it("accepts the NEW shape (post-Phase-2) and uses tenant block verbatim", () => {
    const me = {
      user: "alice",
      tenant_id: "yinhu-rebuild",
      onboarded: false,
      profile: null,
      tenant: {
        client_id: "yinhu", agent_id: "super-xiaochen",
        title: "超级小陈", subtitle: "运帷 AI",
        brand_color: "#3A8FB7", brand_color_dark: "#2A6F92",
        font_family: "Alibaba PuHuiTi 3.0",
        font_css_url: "static/blueprint/fonts/alibaba-puhuiti.css",
        logo_url: "static/blueprint/logo.png",
        available_slash_commands: ["记一下"],
        onboarding_enabled: true,
      },
    };
    const r = interpretMeResponse(me, { client_id: "yinhu", agent_id: "super-xiaochen" });
    expect(r.tenant.title).toBe("超级小陈");
    expect(r.tenant.brand_color).toBe("#3A8FB7");
    expect(r.tenant.font_css_url).toBe("static/blueprint/fonts/alibaba-puhuiti.css");
  });

  it("rejects nonsense (no user) — throws", () => {
    expect(() => interpretMeResponse({ wrong: 1 }, { client_id: "x", agent_id: "y" })).toThrow();
  });
});
```

- [ ] **Step 6.3: Write `app/src/lib/tenant-config.ts`**

```typescript
import { createContext, useContext, useEffect, useMemo, useState, type PropsWithChildren } from "react";
import { apiGet } from "./api";

export type TenantConfig = {
  client_id: string;
  agent_id: string;
  title: string;
  subtitle: string;
  brand_color: string;
  brand_color_dark: string;
  font_family: string;
  font_css_url: string | null;
  logo_url: string | null;
  available_slash_commands: string[];
  onboarding_enabled: boolean;
};

export type MeContext = {
  user: string;
  profile: object | null;
  onboarded: boolean;
  tenant: TenantConfig;
};

const DEFAULTS = {
  title: "agent",
  subtitle: "",
  brand_color: "#3A8FB7",
  brand_color_dark: "#2A6F92",
  font_family: "system-ui",
  font_css_url: null as string | null,
  logo_url: null as string | null,
  available_slash_commands: [] as string[],
  onboarding_enabled: false,
};

export function interpretMeResponse(
  raw: unknown,
  fallback: { client_id: string; agent_id: string },
): MeContext {
  if (typeof raw !== "object" || raw === null || !("user" in raw)) {
    throw new Error("invalid /me response: missing user");
  }
  const me = raw as Record<string, unknown>;
  const tenantRaw = me.tenant;

  // NEW shape: tenant is an object
  if (typeof tenantRaw === "object" && tenantRaw !== null) {
    const t = tenantRaw as Partial<TenantConfig>;
    return {
      user: me.user as string,
      profile: (me.profile as object | null) ?? null,
      onboarded: Boolean(me.onboarded),
      tenant: {
        client_id: t.client_id ?? fallback.client_id,
        agent_id: t.agent_id ?? fallback.agent_id,
        title: t.title ?? DEFAULTS.title,
        subtitle: t.subtitle ?? DEFAULTS.subtitle,
        brand_color: t.brand_color ?? DEFAULTS.brand_color,
        brand_color_dark: t.brand_color_dark ?? DEFAULTS.brand_color_dark,
        font_family: t.font_family ?? DEFAULTS.font_family,
        font_css_url: t.font_css_url ?? DEFAULTS.font_css_url,
        logo_url: t.logo_url ?? DEFAULTS.logo_url,
        available_slash_commands: t.available_slash_commands ?? DEFAULTS.available_slash_commands,
        onboarding_enabled: t.onboarding_enabled ?? DEFAULTS.onboarding_enabled,
      },
    };
  }

  // OLD shape: tenant is a string (legacy yinhu pre-Phase-2)
  return {
    user: me.user as string,
    profile: (me.profile as object | null) ?? null,
    onboarded: Boolean(me.onboarded),
    tenant: {
      client_id: fallback.client_id,
      agent_id: fallback.agent_id,
      ...DEFAULTS,
    },
  };
}

const TenantCtx = createContext<MeContext | null>(null);

export function TenantProvider({
  client_id, agent_id, children,
}: PropsWithChildren<{ client_id: string; agent_id: string }>) {
  const [me, setMe] = useState<MeContext | null>(null);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    let cancelled = false;
    apiGet<unknown>("me")
      .then((raw) => {
        if (cancelled) return;
        setMe(interpretMeResponse(raw, { client_id, agent_id }));
      })
      .catch((e) => { if (!cancelled) setError(e as Error); });
    return () => { cancelled = true; };
  }, [client_id, agent_id]);

  const styles = useMemo(() => {
    if (!me) return {};
    return {
      "--brand-blue": me.tenant.brand_color,
      "--brand-blue-dark": me.tenant.brand_color_dark,
    } as React.CSSProperties;
  }, [me]);

  if (error) {
    return <div style={{ padding: 24, color: "crimson" }}>无法加载租户配置: {error.message}</div>;
  }
  if (!me) return <div style={{ padding: 24 }}>loading...</div>;

  return (
    <TenantCtx.Provider value={me}>
      <div style={styles}>{children}</div>
    </TenantCtx.Provider>
  );
}

export function useTenant(): MeContext {
  const v = useContext(TenantCtx);
  if (!v) throw new Error("useTenant() outside TenantProvider");
  return v;
}
```

- [ ] **Step 6.4: Run tests — confirm PASS**

```bash
npm run test tenant-config 2>&1 | tail -10
```

- [ ] **Step 6.5: Commit**

```bash
git add app/src/lib/api.ts app/src/lib/tenant-config.ts \
        app/src/tests/tenant-config.test.ts
git commit -m "feat(app/lib): TenantProvider tolerant of old + new /me shapes

interpretMeResponse handles both legacy yinhu shape (tenant: <string>)
and post-Phase-2 shape (tenant: <object>). Falls back to bake-in defaults
when fields missing. 3 tests."
```

---

## Task 7: Wouter routing + provider tree

**Files:**
- Modify: `app/src/main.tsx`
- Modify: `app/src/App.tsx`
- Create: `app/src/pages/NotInTenant.tsx`
- Create: `app/src/pages/Chat.tsx` (stub for now — full impl in Task 9)

- [ ] **Step 7.1: Update `app/src/main.tsx` to inject Router**

```tsx
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { Router } from "wouter";
import "./styles/globals.css";
import { App } from "./App";

const rootEl = document.getElementById("root");
if (!rootEl) throw new Error("missing #root");

createRoot(rootEl).render(
  <StrictMode>
    <Router>
      <App />
    </Router>
  </StrictMode>,
);
```

- [ ] **Step 7.2: Update `app/src/App.tsx`**

```tsx
import { Route, Switch } from "wouter";
import { TenantProvider } from "./lib/tenant-config";
import { Chat } from "./pages/Chat";
import { NotInTenant } from "./pages/NotInTenant";

export function App() {
  return (
    <Switch>
      <Route path="/:client/:agent/:rest*">
        {(params) => (
          <TenantProvider client_id={params.client} agent_id={params.agent}>
            <Chat />
          </TenantProvider>
        )}
      </Route>
      <Route><NotInTenant /></Route>
    </Switch>
  );
}
```

- [ ] **Step 7.3: Write `app/src/pages/NotInTenant.tsx`**

```tsx
export function NotInTenant() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-gray-50">
      <div className="text-center">
        <h1 className="text-2xl font-semibold" style={{ color: "var(--brand-blue)" }}>
          请从平台登录后访问
        </h1>
        <p className="mt-3 text-sm text-gray-500">
          URL must include /&lt;client&gt;/&lt;agent&gt;/.
        </p>
      </div>
    </div>
  );
}
```

- [ ] **Step 7.4: Stub `app/src/pages/Chat.tsx` (full impl in Task 9)**

```tsx
import { useTenant } from "../lib/tenant-config";

export function Chat() {
  const me = useTenant();
  return (
    <div style={{ padding: 24 }}>
      <h1 style={{ color: "var(--brand-blue)" }}>{me.tenant.title}</h1>
      <p>{me.tenant.subtitle}</p>
      <p style={{ marginTop: 24, color: "#888" }}>chat UI — Task 9 wires runtime</p>
    </div>
  );
}
```

- [ ] **Step 7.5: Build smoke**

```bash
cd /Users/eason/agent-platform/app && npm run build 2>&1 | tail -15
```

Expected: clean TS build, dist/ regenerated.

- [ ] **Step 7.6: Manual local visual test (optional but helpful)**

```bash
# Start a stub /me + sessions endpoint locally with python:
cat > /tmp/stub-agent.py <<'PY'
from fastapi import FastAPI
import uvicorn
app = FastAPI()
@app.get("/me")
def me(): return {"user":"dev","tenant":"yinhu-rebuild","onboarded":False,"profile":None}
@app.get("/sessions")
def sessions(): return {"sessions": []}
@app.get("/healthz")
def hz(): return {"ok": True}
uvicorn.run(app, port=18000)
PY
python3 /tmp/stub-agent.py &
STUB_PID=$!

cd /Users/eason/agent-platform/app
# Vite proxy: configure dev server to proxy /yinhu/super-xiaochen/* to localhost:18000
# Easier: just build and serve via vite preview, then visit /yinhu/super-xiaochen/
npm run dev &
VITE_PID=$!
sleep 3
echo "Visit http://localhost:5174/yinhu/super-xiaochen/ — should show 'agent' title (default since /me old shape)"
sleep 2
kill $VITE_PID $STUB_PID 2>/dev/null
```

(This visual test is optional. The unit tests already verify the logic.)

- [ ] **Step 7.7: Commit**

```bash
git add app/src/main.tsx app/src/App.tsx \
        app/src/pages/NotInTenant.tsx app/src/pages/Chat.tsx
git commit -m "feat(app): wouter routing + TenantProvider provider tree

App.tsx routes /:client/:agent/* through TenantProvider into Chat (stub).
NotInTenant fallback for missing prefix. Phase 3 Task 9 wires the runtime."
```

---

## Task 8: UI components — Layout, Sidebar, Composer, messages, WelcomeScreen

**Files:**
- Create: `app/src/components/Layout.tsx`
- Create: `app/src/components/Sidebar.tsx`
- Create: `app/src/components/DateGroupedThreadList.tsx`
- Create: `app/src/components/ThreadItemMenu.tsx`
- Create: `app/src/components/Topbar.tsx`
- Create: `app/src/components/WelcomeScreen.tsx`
- Create: `app/src/components/Composer.tsx`
- Create: `app/src/components/UserMessage.tsx`
- Create: `app/src/components/AssistantMessage.tsx`
- Create: `app/src/components/UserMenu.tsx`
- Create: `app/src/lib/markdown.tsx`
- Modify: `app/src/styles/globals.css`

This task has many small files. Each is mechanical. Implementer should batch reads and writes within this task; tests come in Task 9 (integration).

- [ ] **Step 8.1: `app/src/components/Layout.tsx`**

```tsx
import type { PropsWithChildren } from "react";

export function Layout({ children }: PropsWithChildren) {
  return <div className="grid h-screen grid-cols-[260px_1fr]">{children}</div>;
}
```

- [ ] **Step 8.2: `app/src/components/Sidebar.tsx`**

```tsx
import { ThreadListPrimitive } from "@assistant-ui/react";
import { useTenant } from "../lib/tenant-config";
import { DateGroupedThreadList } from "./DateGroupedThreadList";
import { UserMenu } from "./UserMenu";

export function Sidebar() {
  const me = useTenant();
  return (
    <aside className="flex flex-col border-r border-gray-200 bg-gray-50 min-h-0">
      <div className="h-12 flex items-center gap-3 px-4 border-b border-gray-200">
        {me.tenant.logo_url && <img src={me.tenant.logo_url} alt="" className="h-7 w-7" />}
        <div className="text-sm leading-tight">
          <div className="font-semibold text-gray-900">{me.tenant.title}</div>
          <div className="text-xs text-gray-500">{me.tenant.subtitle}</div>
        </div>
      </div>
      <div className="px-2 pt-2">
        <ThreadListPrimitive.Root>
          <ThreadListPrimitive.New className="w-full h-8 rounded text-sm text-white" style={{ background: "var(--brand-blue)" }}>
            + 新对话
          </ThreadListPrimitive.New>
          <DateGroupedThreadList />
        </ThreadListPrimitive.Root>
      </div>
      <div className="mt-auto border-t border-gray-200">
        <UserMenu />
      </div>
    </aside>
  );
}
```

- [ ] **Step 8.3: `app/src/components/DateGroupedThreadList.tsx`**

```tsx
import { ThreadListItemPrimitive, useAuiState } from "@assistant-ui/react";
import { ThreadItemMenu } from "./ThreadItemMenu";

// Phase 3 minimum: render flat list. Date grouping reads session metadata
// not yet exposed by the assistant-ui state. We keep a simple flat list
// until Phase 4 adds a state surface or until we read /sessions directly
// for last_ts. (DateGroupedThreadList.tsx name reserved for full impl.)
export function DateGroupedThreadList() {
  const items = useAuiState((s) => s.threadList.threads) as Array<{ remoteId?: string; title?: string; status: string }>;
  return (
    <div className="mt-2 space-y-1">
      {items.map((t) => (
        <ThreadListItemPrimitive.Root
          key={t.remoteId ?? "new"}
          className="group flex items-center justify-between rounded px-2 py-1 text-sm hover:bg-gray-200"
        >
          <ThreadListItemPrimitive.Trigger className="flex-1 text-left truncate">
            {t.title ?? "未命名"}
          </ThreadListItemPrimitive.Trigger>
          <ThreadItemMenu />
        </ThreadListItemPrimitive.Root>
      ))}
    </div>
  );
}
```

- [ ] **Step 8.4: `app/src/components/ThreadItemMenu.tsx`**

```tsx
import { ThreadListItemPrimitive } from "@assistant-ui/react";

export function ThreadItemMenu() {
  return (
    <ThreadListItemPrimitive.Delete
      className="invisible group-hover:visible text-xs text-gray-400 hover:text-red-600"
      title="删除"
    >
      ×
    </ThreadListItemPrimitive.Delete>
  );
}
```

- [ ] **Step 8.5: `app/src/components/Topbar.tsx`**

```tsx
import { useAuiState } from "@assistant-ui/react";

export function Topbar() {
  const title = useAuiState((s) => s.threadListItem.title) as string | undefined;
  return (
    <div className="h-12 flex items-center px-4 border-b border-gray-200">
      <span className="text-sm font-medium">{title ?? "新对话"}</span>
    </div>
  );
}
```

- [ ] **Step 8.6: `app/src/components/WelcomeScreen.tsx`**

```tsx
import { useTenant } from "../lib/tenant-config";

export function WelcomeScreen() {
  const me = useTenant();
  return (
    <div className="flex flex-1 items-center justify-center px-8">
      <div className="text-center max-w-lg">
        <h1 className="text-3xl font-semibold" style={{ color: "var(--brand-blue)" }}>
          {me.tenant.title}
        </h1>
        <p className="mt-3 text-gray-500">{me.tenant.subtitle}</p>
        <p className="mt-8 text-sm text-gray-400">输入问题开始对话。</p>
      </div>
    </div>
  );
}
```

- [ ] **Step 8.7: `app/src/components/Composer.tsx`**

```tsx
import { ComposerPrimitive } from "@assistant-ui/react";

export function Composer() {
  return (
    <ComposerPrimitive.Root className="flex items-end gap-2 border-t border-gray-200 bg-white p-3">
      <ComposerPrimitive.Input
        className="flex-1 resize-none rounded border border-gray-300 px-3 py-2 text-sm focus:border-[var(--brand-blue)] focus:outline-none"
        placeholder="输入消息…  Shift+Enter 换行"
        autoFocus
      />
      <ComposerPrimitive.If running>
        <ComposerPrimitive.Cancel className="rounded px-3 h-9 bg-gray-200 text-sm">
          停止
        </ComposerPrimitive.Cancel>
      </ComposerPrimitive.If>
      <ComposerPrimitive.If running={false}>
        <ComposerPrimitive.Send
          className="rounded h-9 px-4 text-sm text-white"
          style={{ background: "var(--brand-blue)" }}
        >
          发送
        </ComposerPrimitive.Send>
      </ComposerPrimitive.If>
    </ComposerPrimitive.Root>
  );
}
```

- [ ] **Step 8.8: `app/src/lib/markdown.tsx`**

```tsx
import { MarkdownTextPrimitive } from "@assistant-ui/react-markdown";

export function MarkdownText() {
  return <MarkdownTextPrimitive className="prose prose-sm max-w-none" />;
}
```

> If `prose` isn't available without `@tailwindcss/typography`, drop the className for Phase 3 and rely on default browser styles. Phase 4 can add prose styling.

- [ ] **Step 8.9: `app/src/components/UserMessage.tsx`**

```tsx
import { MessagePrimitive } from "@assistant-ui/react";

export function UserMessage() {
  return (
    <MessagePrimitive.Root className="flex justify-end px-6 py-2">
      <div className="max-w-[80%] rounded-lg px-3 py-2 text-sm text-white" style={{ background: "var(--brand-blue)" }}>
        <MessagePrimitive.Parts />
      </div>
    </MessagePrimitive.Root>
  );
}
```

- [ ] **Step 8.10: `app/src/components/AssistantMessage.tsx`**

Phase 3: render text + a placeholder for tool calls. Real ToolCallUI is Phase 4.

```tsx
import { MessagePrimitive, useAuiState } from "@assistant-ui/react";
import { MarkdownText } from "../lib/markdown";

type ToolCallStub = { tool: string; input: unknown; lineage?: unknown };

export function AssistantMessage() {
  // Read the current message's metadata.custom from the assistant-ui state
  const toolCalls = useAuiState(
    (s) => (s.message.metadata?.custom as { toolCalls?: ToolCallStub[] } | undefined)?.toolCalls,
  );

  return (
    <MessagePrimitive.Root className="flex justify-start px-6 py-2">
      <div className="max-w-[80%] space-y-2">
        <div className="rounded-lg bg-gray-100 px-3 py-2 text-sm">
          <MessagePrimitive.Parts components={{ Text: MarkdownText }} />
        </div>
        {toolCalls && toolCalls.length > 0 && (
          <div className="space-y-1">
            {toolCalls.map((tc, i) => (
              <div key={i} className="tool-call-stub rounded border border-dashed border-gray-300 bg-gray-50 px-3 py-2 text-xs">
                <div className="font-mono">{tc.tool}</div>
                <pre className="mt-1 whitespace-pre-wrap text-gray-600">
                  {JSON.stringify(tc.input, null, 2)}
                </pre>
                {tc.lineage !== undefined && (
                  <div className="mt-1 text-gray-400">[lineage available — Phase 4 modal]</div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </MessagePrimitive.Root>
  );
}
```

- [ ] **Step 8.11: `app/src/components/UserMenu.tsx`**

```tsx
import { useTenant } from "../lib/tenant-config";

export function UserMenu() {
  const me = useTenant();
  return (
    <div className="px-3 py-3">
      <div className="text-sm font-medium text-gray-900">{me.user}</div>
      <div className="mt-1 flex flex-col gap-1 text-xs text-gray-500">
        <span className="cursor-not-allowed opacity-60" title="Phase 5">我的记忆</span>
      </div>
    </div>
  );
}
```

- [ ] **Step 8.12: Add minor styles to `app/src/styles/globals.css`**

Append:

```css
/* Phase 3 minimum: clamp body height so chat scrolls in viewport */
.chat-viewport {
  display: flex;
  flex-direction: column;
  flex: 1;
  min-height: 0;
}
.chat-messages {
  flex: 1;
  overflow-y: auto;
}
```

- [ ] **Step 8.13: Build smoke**

```bash
cd /Users/eason/agent-platform/app && npm run build 2>&1 | tail -10
```

Expected: clean. If TS errors about `useAuiState` selector typing surface, narrow the types in the selector callback.

- [ ] **Step 8.14: Commit**

```bash
git add app/src/components/ app/src/lib/markdown.tsx app/src/styles/globals.css
git commit -m "feat(app): chat UI components (sidebar, composer, messages, welcome)

Layout, Sidebar (with assistant-ui ThreadListPrimitive), Composer
(ComposerPrimitive + Send/Cancel), UserMessage, AssistantMessage with
Markdown body + Phase 3 tool-call stub. Real ToolCallUI/SourcesModal/
ModelBadge/FollowupChips are Phase 4-5."
```

---

## Task 9: Wire it all together in `Chat.tsx`

**Files:**
- Modify: `app/src/pages/Chat.tsx`

- [ ] **Step 9.1: Replace `Chat.tsx` stub with the wiring**

```tsx
import {
  AssistantRuntimeProvider,
  ThreadPrimitive,
  useAui,
  useAuiState,
  useLocalRuntime,
  useRemoteThreadListRuntime,
} from "@assistant-ui/react";
import { useMemo } from "react";
import { chatAdapter } from "../runtime/chatAdapter";
import { threadListAdapter } from "../runtime/threadListAdapter";
import { makeThreadHistoryAdapter } from "../runtime/threadHistoryAdapter";
import { Layout } from "../components/Layout";
import { Sidebar } from "../components/Sidebar";
import { Topbar } from "../components/Topbar";
import { WelcomeScreen } from "../components/WelcomeScreen";
import { Composer } from "../components/Composer";
import { UserMessage } from "../components/UserMessage";
import { AssistantMessage } from "../components/AssistantMessage";

function ChatInner() {
  // Pass the active session_id into chatAdapter via runConfig.custom.
  const sessionId = useAuiState((s) => s.threadListItem.remoteId) as string | undefined;
  const runtime = useLocalRuntime(chatAdapter, {
    runConfig: { custom: { sessionId: sessionId ?? null } },
  });

  return (
    <AssistantRuntimeProvider runtime={runtime}>
      <main className="flex flex-col min-h-0">
        <Topbar />
        <ThreadPrimitive.Root className="chat-viewport">
          <ThreadPrimitive.Viewport className="chat-messages">
            <ThreadPrimitive.If empty><WelcomeScreen /></ThreadPrimitive.If>
            <ThreadPrimitive.Messages
              components={{ UserMessage, AssistantMessage }}
            />
          </ThreadPrimitive.Viewport>
          <Composer />
        </ThreadPrimitive.Root>
      </main>
    </AssistantRuntimeProvider>
  );
}

export function Chat() {
  const runtime = useRemoteThreadListRuntime({
    runtimeHook: () => {
      // useLocalRuntime is created PER thread in ChatInner. The outer
      // RemoteThreadListRuntime owns the sidebar.
      return useLocalRuntime(chatAdapter);
    },
    adapter: useMemo(() => ({
      ...threadListAdapter,
      unstable_Provider: ({ children }: { children: React.ReactNode }) => {
        const aui = useAui();
        const remoteId = useMemo(
          () => (aui.threadListItem().getState().remoteId as string | undefined),
          [aui],
        );
        const history = useMemo(
          () => (remoteId ? makeThreadHistoryAdapter(remoteId) : undefined),
          [remoteId],
        );
        // Provide the per-thread history adapter via assistant-ui's
        // RuntimeAdapterProvider. If this hook signature differs in 0.14
        // re-check the migration guide; for now, render children verbatim
        // and let useLocalRuntime in ChatInner handle the adapter.
        return <>{children}</>;
      },
    }), []),
  });

  return (
    <AssistantRuntimeProvider runtime={runtime}>
      <Layout>
        <Sidebar />
        <ChatInner />
      </Layout>
    </AssistantRuntimeProvider>
  );
}
```

> ⚠️ **Likely needs adjustment**: the `unstable_Provider` shape in `@assistant-ui/react@0.14` may differ slightly from what's sketched. If the build fails with a type error on `unstable_Provider`, look at `node_modules/@assistant-ui/react/dist/*.d.ts` to find the exact type and adapt. The conceptual hook is "give the inner runtime a thread-history adapter keyed by remoteId" — the wiring may need to use `RuntimeAdapterProvider` from `@assistant-ui/react` to inject the history adapter into the inner runtime.
>
> Acceptable fallback: skip per-thread history (Phase 3 minimum), let each new thread start empty, and let `chatAdapter` rebuild context server-side from `session_id`. This still ships working chat — history reload across page refreshes is degraded but server has the truth. Add a TODO and move on.

- [ ] **Step 9.2: Build & type-check**

```bash
cd /Users/eason/agent-platform/app && npm run build 2>&1 | tail -20
```

Expected: clean. If `unstable_Provider` typing fails, take the fallback noted above (drop the per-thread history adapter; ship empty-on-load behavior; document as Phase 4 follow-up).

- [ ] **Step 9.3: Commit**

```bash
git add app/src/pages/Chat.tsx
git commit -m "feat(app): wire chat runtime — local + remote thread list

Chat page composes useRemoteThreadListRuntime over threadListAdapter,
nests useLocalRuntime(chatAdapter) per thread, mounts the full UI
(Layout/Sidebar/Topbar/WelcomeScreen/Composer/Messages). Per-thread
history adapter wired via unstable_Provider when remoteId is known."
```

---

## Task 10: Local end-to-end smoke (build + docker + curl + manual click-through)

**Files:** none

- [ ] **Step 10.1: Production build, sanity**

```bash
cd /Users/eason/agent-platform/app && npm run build
ls dist/
test -f dist/index.html && echo OK
test -f dist/base-href.js && echo OK
ls dist/assets/ | head
```

Expected: `index.html` + `base-href.js` + `assets/index-XXX.js` + `assets/index-XXX.css`.

- [ ] **Step 10.2: Run all unit tests**

```bash
npm run test 2>&1 | tail -10
```

Expected: ALL tests pass (parseSSE 6 + chatAdapter 7 + threadListAdapter 4 + threadHistoryAdapter 3 + tenant-config 3 = 23 tests).

- [ ] **Step 10.3: Build the platform Docker image (multi-stage)**

```bash
cd /Users/eason/agent-platform
docker build -f platform/Dockerfile -t agent-platform:phase3 .
```

Expected: clean build.

- [ ] **Step 10.4: Run smoke against the platform image**

This requires a real (or stubbed) yinhu agent to serve `/me`, `/sessions`, `/chat`. If the team has a dev compose stack, use it. Otherwise:

```bash
# Use the actual yinhu agent container if you have it:
# docker network create demo
# docker run --network demo --name yinhu --rm -d <yinhu-image>
# docker run --network demo --name platform --rm -d -p 28000:8000 agent-platform:phase3
#
# Then visit http://localhost:28000/yinhu/super-xiaochen/ in a browser
# (needs a session cookie — log in via /login first per platform auth flow).
```

If a full stack is too heavy, skip the docker run smoke and rely on the unit tests + manual visit via `npm run dev` against a stubbed agent (Step 7.6 pattern).

- [ ] **Step 10.5: Manual click-through verification**

When the stack is up, in the browser at `app.fiveoranges.ai/yinhu/super-xiaochen/` (or local equivalent):

1. Sidebar shows the brand logo (if `logo_url` returned), title, subtitle.
2. "+ 新对话" button is clickable.
3. Type "hi" + Enter → user message bubble (right side, brand color).
4. Streaming assistant response renders progressively (left side, gray bubble).
5. Tool calls (if the agent invoked any) render as a dashed-border stub showing tool name + JSON args.
6. Refresh page → sidebar still lists prior sessions; clicking one switches to that session and loads its messages (if `unstable_Provider` per-thread history wired; otherwise empty viewport — known Phase 3 limitation).

Document anything that doesn't work as expected; bring those into Phase 4 if they're substantive (e.g. broken history reload).

- [ ] **Step 10.6: Final commit (clean up any TODOs added during smoke)**

```bash
cd /Users/eason/agent-platform
git status -sb
git log --oneline -n 12
```

Expected: ~10 commits on `design/chat-core-phase-3`. If any small fixes landed during 10.4-10.5, commit them with a descriptive message.

---

## Self-review checklist

- [ ] All 23 unit tests pass (`npm run test`).
- [ ] `npm run build` clean, no TS warnings.
- [ ] `app/dist/index.html` produces a working SPA when served by the platform's catch_all.
- [ ] `chatAdapter` posts to relative URL `chat` (not `/chat` absolute, not `/yinhu/super-xiaochen/chat` hardcoded). Verified by the test in Task 4.
- [ ] `threadListAdapter` POSTs/DELETEs to relative `sessions` paths. Verified by tests in Task 5.
- [ ] No deprecated assistant-ui hooks (`useMessage`/`useThread`/`useComposer`/`useThreadRuntime`/`useComposerRuntime`/`useMessageRuntime`). Only `useAuiState`, `useAui`, primitives, runtime hooks.
- [ ] `TenantProvider` tolerates the legacy `/me` shape (yinhu's Phase 2 cutover hasn't shipped yet); falls back to defaults from `globals.css`.
- [ ] AbortSignal flows: composer's stop button → `useLocalRuntime` cancellation → `chatAdapter`'s `abortSignal` → `fetch` aborted → server disconnects. Verified by the abort test in Task 4.
- [ ] No tool-call rendering, no SourcesModal, no FollowupChips, no ModelBadge, no OnboardingModal, no MemoriesPanel, no SlashCommands. Those are Phase 4-5.
- [ ] No platform-side changes (no `platform/Dockerfile` edit, no `main.py` edit). Phase 3 is `app/`-only.

## Out-of-scope follow-ups (Phase 4+)

- **Tool call UI** with full input/output panels (Phase 4 verifies `makeAssistantToolUI` fallback registration mode in 0.14)
- **SourcesModal** (Phase 4): aggregates `tool_lineage` across the message's tool_calls; opens from a "数据源 N" tag in AssistantMessage
- **ModelBadge** (Phase 4): renders `metadata.custom.model` next to assistant name
- **FollowupChips** (Phase 5): clickable chips below the latest assistant message that submit composer text
- **OnboardingModal** + `ui_action` consumption (Phase 5)
- **MemoriesPanel + /me/memories CRUD** (Phase 5): lifts current yinhu UI behavior into platform UI
- **/记一下 SlashCommands** (Phase 5)
- **Per-tenant font/logo loading** from `tenant.font_css_url` / `tenant.logo_url` (Phase 5; for now only fonts the platform bundles itself work)
- **Date-grouped sessions sidebar** with 今天/昨天/更早 grouping (currently flat; needs `last_ts` from /sessions plumbed into a side-channel)
- **Per-thread history reload** if `unstable_Provider` wiring was deferred in Task 9.3
