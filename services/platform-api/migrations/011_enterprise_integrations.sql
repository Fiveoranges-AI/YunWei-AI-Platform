-- 011 · Per-enterprise integration credentials (DingTalk corp app, Feishu, etc).
--
-- Mirrors the 007_erp_credentials.sql pattern: one row per
-- (enterprise × integration kind), opaque JSON blob for kind-specific
-- credential fields. DingTalk is the first consumer (corp app client_id /
-- client_secret / robot_code); future kinds (`feishu`, `wecom`) reuse the
-- same table.
--
-- Replaces the platform-wide DINGTALK_* env vars (settings.dingtalk_*),
-- which leaked one customer's corp-app credentials across every tenant.

CREATE TABLE IF NOT EXISTS enterprise_integrations (
  enterprise_id  TEXT NOT NULL REFERENCES enterprises(id),
  kind           TEXT NOT NULL,            -- 'dingtalk' | 'feishu' | 'wecom' (future)
  config_json    TEXT NOT NULL,            -- opaque per-kind credentials JSON
  active         INTEGER NOT NULL DEFAULT 1,
  created_at     BIGINT NOT NULL,
  rotated_at     BIGINT,
  PRIMARY KEY (enterprise_id, kind)
);

CREATE INDEX IF NOT EXISTS idx_enterprise_integrations_active
  ON enterprise_integrations(enterprise_id) WHERE active = 1;
