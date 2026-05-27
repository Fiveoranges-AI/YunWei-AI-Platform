# super-xiaochen Session Auth — 设计文档

> 起草：2026-05-27 · 状态：待实现 · 仓库：`Fiveorangesltd/YunWei-AI-Platform` + `Fiveoranges-AI/yinhu-super-xiaochen`
>
> 范围：让用户能从 win-web 入口直接进入 super-xiaochen，不再依赖已下线的 platform-app HMAC 反向代理。

---

## 1. 背景与问题

PR #commit ab5119c 在 win-web 加了一个进入 super-xiaochen 的入口（URail 侧栏 + Profile 卡片），`href` 直接指向 Railway 上游：

```
https://agent-yinhu-super-xiaochen-production.up.railway.app
```

打开后返回 `{"detail":"auth: unknown key id"}`。

**根因**：super-xiaochen `web_agent.py:124` 每个路由都过 `require_auth`，校验 HMAC 头（`X-Auth-Key-Id` 等）。原本是 platform-app 内部的反向代理在转发时用 `hmac_sign.sign()` 注入这些头，但该代理早已从 platform-app 移除（`platform_app/` 不再有 `proxy.py`，`main.py` 不存在 `/yinhu/super-xiaochen/` 路由）。浏览器直跳 Railway URL 不会带任何 HMAC 头，必然 401。

## 2. 目标 / 非目标

**目标**
- 已登录 agent-platform 的用户点击入口能进入 super-xiaochen，**保留每人独立的 `user_id`**（不破坏 `chat_turns` / `user_memories` / `sessions` 的个人化数据）。
- 不重新引入运行时反向代理。
- 不在 super-xiaochen 维护用户名/密码表。
- 现有 HMAC 通路（daily-report 等服务器对服务器调用）继续可用。

**非目标**
- 不做 super-xiaochen 的多租户改造（按 [[project_super_xiaochen]] 已被推迟）。
- 不做 logout 体验优化（提供最小 `/logout` 端点即可）。
- 不做"无 ACL 用户隐藏入口"的前端权限判断（沿用现 commit "all signed-in users see the button" 语义，由 SSO 端点 ACL 拒绝）。

## 3. 整体流程

```
[win-web]                    [agent-platform]                       [super-xiaochen]
点入口  ──GET /sso/super-xiaochen──▶
                              用 app_session cookie 解出 user_id/name/role
                              has_acl(user, "yinhu", "super-xiaochen") 拦
                              用 _HMAC_SECRETS 签 60s bootstrap token
                            ◀── 303 到 https://...railway.app/sso/accept?t=<token>
       ───────────────────── 浏览器跟随 303 ─────────────────────────▶
                                                                  验签 token (HMAC + exp + nonce)
                                                                  写 Cookie: sx_session=<HMAC 签名会话>
                                                                ◀── 303 到 /
       ◀── 进入 super-xiaochen 首页，后续每个请求带 sx_session ──────
```

要点：
- **不再有运行时反向代理。** agent-platform 只在登录跳转那一刻签 token，跳完就放手；后续 super-xiaochen 自己用 cookie 鉴权。
- **HMAC 不删。** `require_auth` 改成"先看 cookie，没 cookie 再走 HMAC"。daily-report 之类服务器对服务器调用继续走 HMAC，不受影响。
- **共享密钥已就位。** `_HMAC_SECRETS` 在两边 Railway 和 platform-app 已经同步，不新增 env。

## 4. Token 与 Cookie 格式

两者都用现有 HMAC-SHA256 原语签，不引入 JWT 库。

### 4.1 Bootstrap token（一次性，URL 里跑）

```
payload  = base64url(json({sub, name, role, exp, jti, kid}))
sig      = base64url(hmac_sha256(secrets[kid], payload))
token    = f"{payload}.{sig}"
```

| 字段 | 含义 |
|---|---|
| `sub`  | user_id，如 `u_xuzong` |
| `name` | 显示名，原值（不 URL-encode；payload 已经 base64） |
| `role` | `user` / `admin` 等，复用 agent-platform 既有角色 |
| `exp`  | unix ts，签发时 `now + 60` |
| `jti`  | uuid4，super-xiaochen `NonceStore` 防重放 |
| `kid`  | 选用的 HMAC key id（明文写在 payload，由 sig 保护） |

TTL 60s 足够浏览器 303 跳转；窗口短 = 即便日志泄漏也几乎无窗口可重放，加上 jti nonce 即"用完作废"。

### 4.2 Session cookie（super-xiaochen 自己用，长期）

```
cookie_value = base64url(json({sub, name, role, exp, kid})) + "." + sig
```

属性：`HttpOnly; Secure; SameSite=Lax; Path=/; Max-Age=604800`（7 天）。

`verify_session_cookie` 与 token 验签共用 `_verify_signed_payload` 内部函数 —— 拆分点：cookie 不查 `NonceStore`（用户日常访问每次都用同一个 cookie，不是一次性），token 查。

`SameSite=Lax` 足够：
- 跨站 303 跳到 `/sso/accept?t=...` 是 GET 顶层导航，Lax 允许后续 set-cookie 生效。
- 后续 super-xiaochen 内部的 fetch 都是同站请求，Lax 通过。

### 4.3 `require_auth` 改造

```python
async def require_auth(request: Request) -> str:
    # 1. cookie 优先（浏览器路径）
    cookie = request.cookies.get("sx_session")
    if cookie:
        try:
            claims = verify_session_cookie(cookie, secrets=_HMAC_SECRETS)
            return claims["sub"]
        except ValueError:
            pass  # 落空就试 HMAC
    # 2. 现有 HMAC 路径（服务端 → 服务端调用，比如 daily-report）
    body = await request.body()
    headers = {k.lower(): v for k, v in request.headers.items()}
    try:
        verify(headers={...}, secrets=_HMAC_SECRETS, ...)
    except ValueError as e:
        raise HTTPException(401, f"auth: {e}")
    return headers.get("x-user-id", "")
```

## 5. 端点

| 服务 | 路由 | 行为 |
|---|---|---|
| agent-platform | `GET /sso/super-xiaochen` | cookie 解 user → 检 ACL → 签 token → 303 到 `<railway>/sso/accept?t=...` |
| super-xiaochen | `GET /sso/accept?t=...` | 验 token + nonce → 写 `sx_session` cookie → 303 到 `/` |
| super-xiaochen | `POST /logout` | 清 cookie → 303 到 `/` |

### 5.1 agent-platform `/sso/super-xiaochen`

错误处理：
- 无 `app_session` cookie → 302 到 `/`（让登录页接管）
- `has_acl(user, "yinhu", "super-xiaochen")` 返回 False → 403 + HTML 文案 "无权访问超级小陈"
- 签名异常 → 500

环境变量：
- `SUPER_XIAOCHEN_PUBLIC_URL`（新增）= `https://agent-yinhu-super-xiaochen-production.up.railway.app`，便于未来切换 Railway 域名而不改代码。fallback 到硬编码默认值，方便本地开发。

### 5.2 super-xiaochen `/sso/accept`

错误处理：
- `t` 缺失/格式错/签名错/过期/重放 → 401 + HTML 文案 "登录链接已过期，请回到平台重新进入。"

### 5.3 super-xiaochen `/logout`

清 `sx_session`，303 到 `/`。落到 `/` 又会因为没 cookie 进入 `require_auth` 失败路径——返回的是 401 JSON。考虑到 super-xiaochen 暂没有自己的登录页，logout 实际效果就是"下次再点入口才能进"。这个最小行为可接受。

## 6. 前端改动（win-web）

在 `apps/win-web/src/components/URail.tsx` 和 `apps/win-web/src/screens/Profile.tsx`：

- `href` 从 `https://agent-yinhu-super-xiaochen-production.up.railway.app` 改成相对路径 `/sso/super-xiaochen`
- 移除 `target="_blank"` 与 `rel="noopener noreferrer"`（同标签跳转）

按钮对所有登录用户可见，权限失败由 agent-platform 的 `/sso/super-xiaochen` 端点返回 403。如果将来要按 ACL 隐藏按钮，需要在 `/api/me` 返回里加 `agents: ["yinhu/super-xiaochen", ...]` 字段，前端按此决定渲染——本期不做。

## 7. 实现拆分

| # | 仓库 | 改动 | 估算 |
|---|---|---|---|
| 1 | yinhu-super-xiaochen | 新增 `session_cookie.py`（签/验 cookie + bootstrap token）；改造 `require_auth`；加 `/sso/accept` 和 `/logout` 路由 | ~80 行 |
| 2 | yinhu-super-xiaochen | 单元测试（test_session_cookie.py、test_sso_accept.py） | ~120 行 |
| 3 | agent-platform | `platform_app/sso.py` 新模块（签 bootstrap token）；`main.py` 挂 `/sso/super-xiaochen` 路由 | ~50 行 |
| 4 | agent-platform | 单元测试（test_sso.py） | ~80 行 |
| 5 | agent-platform | win-web 两处 `href` + `target` 修改 | ~6 行 |

总计 ~340 行代码 + 测试。

## 8. 测试清单

每条对应一个 pytest：

1. `/sso/super-xiaochen` 无 cookie → 302 到 `/`
2. `/sso/super-xiaochen` cookie 有效 + ACL 通过 → 303 到 `<SUPER_XIAOCHEN_PUBLIC_URL>/sso/accept?t=...`，token 字段格式 `<payload>.<sig>`
3. `/sso/super-xiaochen` cookie 有效 + ACL 拒 → 403
4. super-xiaochen `/sso/accept` 收合法 token → 200 + `Set-Cookie: sx_session=...; HttpOnly; Secure; SameSite=Lax`
5. super-xiaochen `/sso/accept` token 过期 → 401
6. super-xiaochen `/sso/accept` 同 jti 二次提交 → 401（NonceStore 拦截）
7. super-xiaochen `/sso/accept` 签名被改 → 401
8. `require_auth` cookie 通路：合法 cookie → 通过，返回 `sub`
9. `require_auth` 双通路：cookie 缺失 → fallback HMAC 仍然工作
10. `require_auth` cookie 过期 → 401

## 9. 部署 / 上线步骤

1. **先合 super-xiaochen 那边**（PR 1 + 2）。Railway 自动发布。新代码兼容旧调用（HMAC 通路保留），不影响 daily-report。
2. **再合 agent-platform 那边**（PR 3 + 4 + 5），同一个 PR 三组改动一起上：新增 `/sso/super-xiaochen` 端点 + win-web 链接 + 测试。Vercel 发布后入口生效。
3. 验证：用一个 yinhu 测试账号登录 → 点入口 → 应进入 super-xiaochen 首页且不再 401。
4. 监控：观察一周 `/sso/super-xiaochen` 与 `/sso/accept` 的 401 比例，>5% 需要看具体失败原因。

## 10. 已知限制 / 后续

- **没有 super-xiaochen 内的"重新登录"按钮。** cookie 过期后，用户看到的是后端 401 JSON。要修就给 super-xiaochen 加个简易登录引导页（"请回到平台入口重新进入"+ 跳回 `https://app.fiveoranges.ai/sso/super-xiaochen`）。本期不做。
- **没做按 ACL 隐藏前端按钮。** 见 §6。
- **多租户支持仍未做。** 见 [[project_super_xiaochen]]。这次设计保留了 `X-Tenant-Client` / `X-Tenant-Agent` HMAC 通路；将来多租户化只需要在 SSO 签名时塞 tenant_id，super-xiaochen 端按 tenant 分库即可。
