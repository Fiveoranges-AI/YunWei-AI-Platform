# 智通客户 Unified UI Implementation Plan

> **For agentic workers:** Implementation work uses bite-sized commits; this is a visual restructure of an existing React SPA, not greenfield logic. Each task should produce a working build that passes `npm run build` in `apps/win-web/`.

**Goal:** Port the unified.html design (claude.ai/design handoff `YCZ-4ZwvDzYGeX4JaLO6TA`) into `apps/win-web` — a slim dark-navy rail + clean header + two-pane content shell, responsive across desktop / tablet / mobile.

**Architecture:** Replace the existing 240px light-surface sidebar with a 64px navy rail (`URail`) + 60px header (`UHeader`). Customers and a new "Inbox" tab each become two-pane (380px list + detail) on desktop, list-first with drill-in on tablet/mobile. Upload becomes a centered "添加资料" form that returns to Inbox. Ask becomes three-pane (history + chat + composer). Profile becomes a card-list. All existing API integration (`listCustomers`, `getCustomer`, `listIngestJobs`, `askAI`, `confirmIngestJob`, …) is preserved.

**Tech Stack:** React 18 + TypeScript + Vite (`apps/win-web`). Inline styles for fine-grained layout (matches existing pattern); `styles.css` for tokens + base classes; `tokens.css` for the shared design-system tokens.

---

## File Structure

**Modify (replace contents):**
- `apps/win-web/src/styles.css` — update tokens to unified palette (light tech blue brand, AI cyan, navy rail, restrained shadows). Keep class names so unrelated components still work.
- `apps/win-web/src/components/AppShell.tsx` — switch to `URail` + `UHeader` on desktop/tablet. Mobile keeps bottom tab bar.
- `apps/win-web/src/components/Sidebar.tsx` — rewrite as `URail` (64px navy, icons + CTA + avatar).
- `apps/win-web/src/App.tsx` — add `inbox` to `TabName` / `ScreenName`; route changes.
- `apps/win-web/src/screens/CustomerList.tsx` — desktop becomes two-pane (left list + right detail inline); mobile keeps list-first.
- `apps/win-web/src/screens/CustomerDetail.tsx` — extract the body into a reusable pane component that the customers screen embeds on desktop.
- `apps/win-web/src/screens/Upload.tsx` — strip out job-list + history (moves to Inbox); becomes the centered "添加资料" form.
- `apps/win-web/src/screens/Ask.tsx` — desktop three-pane shell with a separate left history rail (existing customer rail moves into history sidebar).
- `apps/win-web/src/screens/Profile.tsx` — card-list aesthetic (no functional change).
- `apps/win-web/src/components/TabBar.tsx` — add "Inbox" tab; reorder.

**Create:**
- `apps/win-web/src/components/URail.tsx` — 64px navy rail used by AppShell on desktop/tablet.
- `apps/win-web/src/components/UHeader.tsx` — 60px header with title/sub + optional search.
- `apps/win-web/src/screens/Inbox.tsx` — new screen showing ingest-job queue (Processing / Pending / History tabs) with right-pane Review preview.
- `apps/win-web/src/components/CustomerDetailPane.tsx` — pure-render customer detail body for embedding inside the customers two-pane and the dedicated `/detail` mobile route.

---

## Task 1: Update design tokens

**Files:**
- Modify: `apps/win-web/src/styles.css`

- [ ] **Step 1: Rewrite token block to match unified palette**

Replace the `:root { ... }` block with the unified palette: light tech blue brand (`--brand-500: #2D9BD8`), AI cyan family, ink slate-leaning, navy rail color (`--navy-900: #0B1F3A`), warn amber, restrained Apple-style shadows. Keep token *names* stable so existing CSS classes (`pill-brand`, `pill-ai`, `card`, `btn-primary`) still render — but the resulting visual changes.

- [ ] **Step 2: Update base button + card + ai-surface CSS to match**

Update `.btn-primary` to use the new brand gradient/shadow. Update `.ai-surface` background gradient to use AI cyan tokens. Update `.tabbar` to use cleaner blur + border. Drop the iOS slide-in `.screen.enter` / `.screen.exit` transitions (unified design uses tab-strip routing inside panes, not iOS-style stacking). Keep `.screen-stack` and `.screen` positioning so mobile still works.

- [ ] **Step 3: Verify build**

Run: `cd apps/win-web && npm run build`
Expected: build succeeds; existing screens render with the new palette (they may look off because of layout — that's OK at this step, the next tasks fix it).

- [ ] **Step 4: Commit**

```bash
git add apps/win-web/src/styles.css
git commit -m "ui(win-web): update design tokens to unified light-tech-blue palette"
```

---

## Task 2: New shell — URail + UHeader

**Files:**
- Create: `apps/win-web/src/components/URail.tsx`
- Create: `apps/win-web/src/components/UHeader.tsx`
- Modify: `apps/win-web/src/components/AppShell.tsx`
- Modify: `apps/win-web/src/App.tsx`
- Modify: `apps/win-web/src/components/TabBar.tsx`

- [ ] **Step 1: Add "inbox" to App routing**

Update `TabName` to include `"inbox"`; add `inbox: "inbox"` to `TAB_TO_SCREEN` and `SCREEN_TO_TAB`. Wire `<InboxScreen go={go} />` as a stub initially (we'll implement in Task 4).

- [ ] **Step 2: Create URail.tsx**

64px dark navy column with a top brand CTA (gradient cyan square + plus), separator, 4 nav icons (`customers, inbox, ask, profile`), bottom avatar. Active item shows translucent cyan background + lighter ink color. Pass `active: TabName`, `onChange: (t: TabName) => void`, `onAdd: () => void`. `onAdd` opens upload as a temporary route.

- [ ] **Step 3: Create UHeader.tsx**

60px white header with `title` + optional `sub` on the left, flex spacer, and an optional ⌘K-style search input on the right (only shown when `view === "customers"` per spec). Take props: `title`, `sub`, `view: TabName`.

- [ ] **Step 4: Rewrite AppShell to use URail + UHeader**

On desktop or tablet (`useIsDesktop || useIsTablet`), render `<URail ... /> + <UHeader ... /> + <main>{children}</main>`. Derive header `title` / `sub` from a `VIEW_META` map. On mobile, keep `<TabBar />` at the bottom, no header (each screen renders its own top bar). Adjust the `<main>` flex column so the content pane fills the remaining height.

- [ ] **Step 5: Update TabBar to include Inbox**

Add inbox tab between customers and upload. Reorder to: customers, inbox, plus-CTA (upload), ask, profile — center 5th becomes a FAB-style plus (the spec mentions this; if it doesn't fit cleanly, keep 5 equal columns and label upload as 添加).

- [ ] **Step 6: Verify build + visual**

Run: `cd apps/win-web && npm run build && npm run dev` (test in browser at 1280×800 + 768×1024 + 390×844). Expected: dark navy rail on desktop, header at top, content area visible. Bottom tab bar on mobile.

- [ ] **Step 7: Commit**

```bash
git add apps/win-web/src/components/URail.tsx \
        apps/win-web/src/components/UHeader.tsx \
        apps/win-web/src/components/AppShell.tsx \
        apps/win-web/src/components/TabBar.tsx \
        apps/win-web/src/App.tsx
git commit -m "ui(win-web): introduce URail + UHeader unified shell"
```

---

## Task 3: Customers two-pane

**Files:**
- Create: `apps/win-web/src/components/CustomerDetailPane.tsx`
- Modify: `apps/win-web/src/screens/CustomerList.tsx`
- Modify: `apps/win-web/src/screens/CustomerDetail.tsx`

- [ ] **Step 1: Extract `CustomerDetailPane` component**

Move the rendering body of `CustomerDetail.tsx` (header → AI summary → metrics → risks → tasks → contacts) into `components/CustomerDetailPane.tsx`. Props: `customer: CustomerDetail`, `onAsk: () => void`, `onClose?: () => void`, `compact?: boolean`. Keep the `EditPanel` private to `CustomerDetail.tsx` (still mounts on mobile / dedicated detail route).

- [ ] **Step 2: Rewrite CustomerList for desktop two-pane**

On `isDesktop`, render a 380px left list (filter tabs: 全部 / 重点 / 注意 / 潜在 with counts, list rows with monogram + risk dot + receivable on the right) + flexible right pane showing `<CustomerDetailPane customer={selectedCustomer} onAsk={() => go("ask", { id })} />`. Selection state lives in the screen. On mobile, keep the existing card list and navigate to `/detail` on click.

- [ ] **Step 3: Update CustomerDetail for mobile / dedicated route**

The dedicated `/detail` route is now only used on tablet/mobile (desktop renders inline). Header gets a back button only on small screens. Edit panel logic unchanged.

- [ ] **Step 4: Verify build + visual**

Run: `cd apps/win-web && npm run build`. Open `/win/` at 1280×800 — confirm list + detail are visible. At 390×844 — confirm list + drill-in works.

- [ ] **Step 5: Commit**

```bash
git add apps/win-web/src/components/CustomerDetailPane.tsx \
        apps/win-web/src/screens/CustomerList.tsx \
        apps/win-web/src/screens/CustomerDetail.tsx
git commit -m "ui(win-web): customers becomes two-pane (380px list + detail)"
```

---

## Task 4: Inbox screen (ingest queue)

**Files:**
- Create: `apps/win-web/src/screens/Inbox.tsx`
- Modify: `apps/win-web/src/App.tsx` (wire screen)

- [ ] **Step 1: Build Inbox shell**

Two-pane on desktop: left 380px list with 3 tabs (`processing / pending / history`) reading from `listIngestJobs("active", 50)` and `listIngestJobs("history", 50)`; right pane shows the Review pane for the selected pending job. Tabs:
- `processing`: `status === "queued" || status === "running"` — show progress bar + stage label
- `pending`: `status === "extracted"` — clickable rows that load review preview on right
- `history`: `status === "confirmed" || "failed" || "canceled"` — grouped by 今天 / 昨天 / 更早

- [ ] **Step 2: Right pane = Review embedded**

Reuse `ReviewScreen` logic by extracting its body into `ReviewPane` (or directly importing `<ReviewScreen ... params={{jobId}} />` as a child). On desktop, the action footer ("忽略 / 修改 / 确认归档") stays at the bottom of the right pane.

- [ ] **Step 3: Tablet/mobile fallback**

On tablet/mobile, Inbox just shows the list; tapping a pending row navigates to `go("review", { jobId })`.

- [ ] **Step 4: Verify build + visual**

Run: `cd apps/win-web && npm run build`. With real backend, upload a doc → see it in processing → wait → see it in pending → click → see Review pane on right.

- [ ] **Step 5: Commit**

```bash
git add apps/win-web/src/screens/Inbox.tsx apps/win-web/src/App.tsx
git commit -m "ui(win-web): add Inbox tab with two-pane ingest queue + review"
```

---

## Task 5: Upload as centered 添加资料 form

**Files:**
- Modify: `apps/win-web/src/screens/Upload.tsx`

- [ ] **Step 1: Strip job-list + history rendering**

Remove `<JobCard>` mapping, history toggle, `clearFailedHistory` button. Keep only: file picker buttons (文件 / 拍照), divider "或文字粘贴", textarea, staged items list, primary CTA.

- [ ] **Step 2: Apply centered modal-style layout**

640px max-width, centered horizontally, generous top padding. Source grid uses the unified "card list with chevron" pattern. CTA reads `导入 · ${total} 项` or `请选择资料来源` when empty.

- [ ] **Step 3: After submit, redirect to Inbox**

After `createIngestJobs` resolves, call `go("inbox")` (instead of staying on the screen). Inbox polling will pick up the new processing job.

- [ ] **Step 4: Verify build + visual**

Run: `cd apps/win-web && npm run build`. Open Upload — confirm centered, no job table.

- [ ] **Step 5: Commit**

```bash
git add apps/win-web/src/screens/Upload.tsx
git commit -m "ui(win-web): upload becomes centered 添加资料 form; jobs live in Inbox"
```

---

## Task 6: Ask three-pane

**Files:**
- Modify: `apps/win-web/src/screens/Ask.tsx`

- [ ] **Step 1: Rebuild desktop layout**

Three columns: 280px left history pane ("最近对话" + new conversation button), flexible center conversation pane (max-width 720px centered with verdict / evidence / next-step sections rendered in cards), bottom composer with cyan-accent send button. Customer rail (existing 280px customer picker) becomes the history list — customer-scoped chats appear as history items.

- [ ] **Step 2: Mobile unchanged**

Mobile keeps current bottom-sheet picker + bubble layout, only the colors/tokens update via the new tokens.

- [ ] **Step 3: Verify + commit**

```bash
git add apps/win-web/src/screens/Ask.tsx
git commit -m "ui(win-web): ask becomes three-pane (history + chat + composer)"
```

---

## Task 7: Profile card-list aesthetic

**Files:**
- Modify: `apps/win-web/src/screens/Profile.tsx`

- [ ] **Step 1: Apply unified Profile layout**

720px max-width, gradient avatar (cyan), white card-list of settings items (账号与安全 / 团队·权限 / 提醒设置 / 数据导出). Footer reads `v1.0 · Five Oranges AI`. Preserve `getMe` + `handleLogout`.

- [ ] **Step 2: Verify + commit**

```bash
git add apps/win-web/src/screens/Profile.tsx
git commit -m "ui(win-web): profile becomes card-list layout"
```

---

## Self-Review

- Spec coverage: Rail ✓ Header ✓ Customers two-pane ✓ Inbox ✓ Upload centered ✓ Ask three-pane ✓ Profile ✓
- All API integration paths preserved (listCustomers, getCustomer, listIngestJobs, askAI, confirmIngestJob, getMe, deleteCustomer, replaceCustomerContacts).
- Mobile + tablet fallbacks defined per screen.
- No new dependencies.
