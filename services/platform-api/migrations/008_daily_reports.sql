-- 008 · CEO daily report storage + subscriptions.
-- Spec: docs/superpowers/specs/2026-05-06-ceo-daily-report-platform-design.md §4.1

CREATE TABLE IF NOT EXISTS daily_reports (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id       TEXT NOT NULL,
  report_date     DATE NOT NULL,
  status          TEXT NOT NULL,
  content_md      TEXT,
  content_html    TEXT,
  sections_json   JSONB,
  raw_collectors  JSONB,
  push_status     TEXT,
  push_error      TEXT,
  error           TEXT,
  generated_at    TIMESTAMPTZ,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, report_date)
);

CREATE INDEX IF NOT EXISTS idx_daily_reports_tenant_date
  ON daily_reports(tenant_id, report_date DESC);

CREATE TABLE IF NOT EXISTS daily_report_subscriptions (
  id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id         TEXT NOT NULL,
  recipient_label   TEXT NOT NULL,
  push_channel      TEXT NOT NULL,
  push_target       TEXT NOT NULL,
  push_cron         TEXT NOT NULL,
  timezone          TEXT NOT NULL DEFAULT 'Asia/Shanghai',
  sections_enabled  TEXT[] NOT NULL,
  enabled           BOOLEAN NOT NULL DEFAULT true,
  created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_subs_tenant
  ON daily_report_subscriptions(tenant_id) WHERE enabled = true;
