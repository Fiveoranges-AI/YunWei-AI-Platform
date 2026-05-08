# Bootstrap: 银湖日报上线 SQL + env

> Runbook · 2026-05-06 · 触发：platform 侧 daily-report 阶段 1 完成 + 钉钉审批通过
>
> 配套 spec: `docs/superpowers/specs/2026-05-06-ceo-daily-report-platform-design.md`

## 前置

- [ ] platform Postgres 迁移 008 已应用（`daily_reports` / `daily_report_subscriptions` 表存在）
- [ ] yinhu container daily-report 子路由已部署到 Railway（容器侧 spec 阶段 1 完成）
- [ ] 银湖钉钉企业管理员审批通过：「工作消息发送」+「企业群消息读取」+「通讯录读取」
- [ ] 银湖 IT 提供：钉钉 Client ID / Client Secret / AgentId / RobotCode / 许总 userid

## 1. platform Railway env

在 platform Railway service 设置以下 env vars：

```
DINGTALK_CLIENT_ID=<dingxxx...>
DINGTALK_CLIENT_SECRET=<...>
DINGTALK_AGENT_ID=4527131008
DINGTALK_ROBOT_CODE=<...>
```

> ⚠️ Client Secret 不入 git。

## 2. 注册 (yinhu, daily-report) tenant

```sql
-- 生成新的 HMAC secret pair（与 super-xiaochen 不复用）
-- 在本地：
--   python -c "import secrets; print(secrets.token_urlsafe(32))"

INSERT INTO tenants (
  client_id, agent_id, display_name,
  container_url, hmac_secret_current, hmac_key_id_current,
  tenant_uid, active, created_at
) VALUES (
  'yinhu', 'daily-report', '日报',
  'http://customer-yinhu.railway.internal:8000',
  '<新 HMAC secret>', 'k-daily-1',
  'yinhu-daily-report-uid', 1, EXTRACT(EPOCH FROM NOW())::BIGINT
);
```

将相同的 HMAC secret 设置到 yinhu container env：
```
HMAC_SECRET_CURRENT=<同上>
HMAC_KEY_ID_CURRENT=k-daily-1
```

> 容器内 super-xiaochen + daily-report 共用一个 HMAC pair（同一容器只有一对凭证），二者通过 `X-Tenant-Agent` header 区分。

## 3. 给许总授权 ACL（dashboard 可见性）

```sql
-- 假设许总在 platform 已有用户行 user_id='u-xu-zong'
-- 银湖 enterprise 由 migration 004 backfill 自动建好；如未建则先 INSERT enterprises
INSERT INTO enterprise_members (user_id, enterprise_id, role, granted_at)
VALUES ('u-xu-zong', 'yinhu', 'member',
        EXTRACT(EPOCH FROM NOW())::BIGINT)
ON CONFLICT (user_id, enterprise_id) DO NOTHING;
```

## 4. 创建日报订阅

```sql
INSERT INTO daily_report_subscriptions (
  tenant_id, recipient_label, push_channel, push_target, push_cron,
  timezone, sections_enabled, enabled
) VALUES (
  'yinhu', '许总', 'dingtalk', '<许总 userid>', '30 7 * * 1-5',
  'Asia/Shanghai',
  ARRAY['sales','production','chat','customer_news']::TEXT[],
  true
);
```

## 5. 冒烟验证

```bash
# 强制立刻生成一份（dashboard 重生成按钮也行）
curl -X POST -b "app_session=<管理员 session>" \
  -H 'content-type: application/json' \
  -d '{"date":"2026-05-06"}' \
  https://app.fiveoranges.ai/api/daily-report/reports/yinhu/regenerate
# → {"report_id": "..."}

# 浏览器打开 https://app.fiveoranges.ai/daily-report/<rid> 看渲染
# 钉钉 → 许总测试号 → 应收到 markdown 卡片
```

## 6. 启用 cron

环境变量 + 订阅 + tenant 都到位后，scheduler 在下一个 07:30 上海时间自动触发。无需额外操作。
