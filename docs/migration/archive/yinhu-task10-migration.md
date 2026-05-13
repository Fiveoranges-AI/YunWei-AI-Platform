# Task 10 — yinhu-rebuild 前端 `<base href>` + 相对 fetch（手动应用）

> PLAN.md Task 10：让 agent 前端在被平台反代到 `/yinhu/super-xiaochen/` 这种路径前缀下也能正常加载资源 + 调 API。
>
> 单文件改动集中在 `/Users/eason/yunwei-workspaces/yinhu-rebuild/generated/static/index.html`。
>
> **前置：** 已在 `feat/hmac-platform-integration` 分支（Task 9 那条），继续在这条分支上加 commit 即可。

---

## 工作原理

平台反代后，浏览器看到的 URL 是 `https://app.fiveoranges.ai/yinhu/super-xiaochen/...`。
- 顶层 `index.html` 里如果写 `href="/static/x.css"`，浏览器解析为 `https://app.fiveoranges.ai/static/x.css` → **404**
- 写 `href="static/x.css"` + `<base href="/yinhu/super-xiaochen/">` → 解析为 `https://app.fiveoranges.ai/yinhu/super-xiaochen/static/x.css` → 平台反代到 agent → ✅
- fetch 同理：`fetch('/me')` → 顶层 `/me`（404），`fetch('me')` + base → `/yinhu/super-xiaochen/me`（反代 OK）

`<base>` 标签让浏览器把所有相对 URL 在它指向的前缀下解析。我们不写死前缀，让一段 inline JS 在运行时从 `location.pathname` 推出来——这样同一份代码 docker run 直接跑（前缀为 `/`）也能用，被平台反代时（前缀 `/{client}/{agent}/`）也能用。

---

## Step 1 · 在 `<head>` 最前面插入 `<base>` 自动推断脚本

**当前 head 头几行（line 1-9）：**
```html
<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width,initial-scale=1" />
<title>超级小陈 · 运帷 AI</title>
<link rel="stylesheet" href="/static/blueprint/colors_and_type.css" />
<link rel="stylesheet" href="/static/blueprint/bp.css" />
<link rel="stylesheet" href="/static/blueprint/fonts/alibaba-puhuiti.css" />
```

**改成：**
```html
<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8" />
<script>
(function() {
  // 提取 /yinhu/super-xiaochen/ 前缀；本地直接 docker run 时为 /，platform 反代时为 /{client}/{agent}/
  var m = location.pathname.match(/^(\/[^/]+\/[^/]+\/)/);
  var base = document.createElement('base');
  base.href = m ? m[1] : '/';
  document.head.appendChild(base);
})();
</script>
<meta name="viewport" content="width=device-width,initial-scale=1" />
<title>超级小陈 · 运帷 AI</title>
<link rel="stylesheet" href="static/blueprint/colors_and_type.css" />
<link rel="stylesheet" href="static/blueprint/bp.css" />
<link rel="stylesheet" href="static/blueprint/fonts/alibaba-puhuiti.css" />
```

**关键约束：**
- `<script>` 必须**紧跟 `<meta charset>` 之后**，**所有其他 `<link>/<script>` 之前**——`<base>` 必须在被相对 URL 引用之前生效。
- 三个 css 链接的 `href="/static/..."` 也顺手改成 `href="static/..."`（也可以让下面 Step 2 的 sed 统一处理，但这三行已经在视野里就一起改了）。

---

## Step 2 · 把所有 `/static/...` 改成相对路径

剩下的 23 处 `/static/blueprint/...` 全在 `<img src=...>` 等地方。用 sed 一刀切：

```bash
cd /Users/eason/yunwei-workspaces/yinhu-rebuild/generated/static
# in-place sed (macOS BSD sed 语法 -i ''；如果在 Linux 去掉空字符串)
sed -i '' 's|src="/static/|src="static/|g; s|href="/static/|href="static/|g' index.html

# 验证：应该 0 行
grep -nE 'src="/static|href="/static' index.html
```

**校验：** 跑完后 `grep -c '/static/' index.html` 期望返回的数字应该跟改前不同（少了 26）；唯一可能保留的 `/static/` 形式只在注释或字符串里，不会影响渲染。

---

## Step 3 · 把所有 `fetch('/...')` 改相对

**位置（行号可能稍有偏移，按文本搜）：**

| Line | Before | After |
|---|---|---|
| 1239 | `fetch('/me/memories', {` | `fetch('me/memories', {` |
| 1271 | `fetch('/chat', {` | `fetch('chat', {` |
| 1494 | `fetch('/sessions');` | `fetch('sessions');` |
| 1509 | `fetch('/history?session=' + encodeURIComponent(sessionId));` | `fetch('history?session=' + encodeURIComponent(sessionId));` |
| 1554 | `fetch('/sessions');` | `fetch('sessions');` |
| 1611 | `fetch('/me');` | `fetch('me');` |
| 1697 | `fetch('/me/onboard', {` | `fetch('me/onboard', {` |
| 1734 | `fetch('/me/memories');` | `fetch('me/memories');` |
| 1784 | `` fetch(`/me/memories/${encodeURIComponent(t)}/${encodeURIComponent(n)}`, {method:'DELETE'}); `` | `` fetch(`me/memories/${encodeURIComponent(t)}/${encodeURIComponent(n)}`, {method:'DELETE'}); `` |
| 1958 | `fetch('/sessions/' + encodeURIComponent(sessionId), { method: 'DELETE' });` | `fetch('sessions/' + encodeURIComponent(sessionId), { method: 'DELETE' });` |

**或者一刀切 sed**（更稳）：

```bash
cd /Users/eason/yunwei-workspaces/yinhu-rebuild/generated/static
# 三种字面量起手都处理
sed -i '' "s|fetch('/|fetch('|g; s|fetch(\"/|fetch(\"|g; s|fetch(\`/|fetch(\`|g" index.html

# 验证：期望返回 0 行（除非有 fetch('//' 或 fetch('http... 这种保留绝对的）
grep -nE "fetch\('/[a-z]|fetch\(\"/[a-z]|fetch\(\`/[a-z]" index.html
```

> **不要碰** `fetch('http://...')` 或 `fetch('https://...')` 这种绝对 URL（如果有）——那是调外部域，sed 模式 `'/[a-z]` 不会匹配 `'http`，所以安全。

---

## Step 4 · docker run 自验

```bash
cd /Users/eason/yunwei-workspaces/yinhu-rebuild/generated

# 拷贝 docs 里建议的命令（已在 Task 9 跑过 build 的话直接 docker run）
HMAC_SECRET=$(openssl rand -base64 32)

docker run --rm -p 18000:8000 \
  -e TENANT_CLIENT=yinhu \
  -e TENANT_AGENT=super-xiaochen \
  -e HMAC_SECRET_CURRENT=$HMAC_SECRET \
  -e HMAC_KEY_ID_CURRENT=k-test \
  -e ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY \
  -e ANTHROPIC_BASE_URL=https://api.deepseek.com/anthropic \
  -e MODEL_PRO=deepseek-v4-pro -e MODEL_FLASH=deepseek-v4-flash \
  -v /Users/eason/yunwei-workspaces/yinhu-rebuild/.yunwei-cache/canary:/data \
  agent-yinhu-super-xiaochen:dev &
SERVER_PID=$!
sleep 5

# 1) /healthz 不需要鉴权 → 200
curl -i http://localhost:18000/healthz

# 2) 业务端点没签名 → 401
curl -i http://localhost:18000/chat

# 3) 浏览器打开 http://localhost:18000/
#    - 直接 docker run 的前缀是 /，<base href="/"> 生效
#    - DevTools Network：CSS / 图标 200，业务请求 401（签名是平台注入的，单独 docker 没有）
#    - 主要看 Console 里有没有 404 表明 base 没生效

kill $SERVER_PID 2>/dev/null
docker stop $(docker ps -q --filter ancestor=agent-yinhu-super-xiaochen:dev) 2>/dev/null
```

**验证清单：**
- [ ] `/healthz` 200
- [ ] CSS / 图标加载 200，没有 `/static/` 404
- [ ] Console 干净（没 base 解析错误、没 mixed content 警告）
- [ ] 业务 fetch 401（签名要 platform 注入，docker 单独跑预期 401，是 OK 的）

---

## Step 5 · Commit

```bash
cd /Users/eason/yunwei-workspaces/yinhu-rebuild/generated
git add static/index.html
git commit -m "feat: relative fetch + auto base href so platform reverse proxy works

- Inline <script> at top of <head> infers /{client}/{agent}/ prefix from
  location.pathname and inserts <base>; falls back to / for direct docker
  run.
- All /static/blueprint/... and 10 fetch('/...') call sites converted to
  relative paths so <base> can prepend the prefix at proxy time.
"
```

不开 PR（按之前约定，由你从另一个账号开 PR）。

---

## 应用完成后告诉我

平台这边 Task 11（docker compose 编排）就要把 platform + yinhu-agent + cloudflared 三个容器串起来，是从单 yinhu container 走到完整链路的关键节点。
