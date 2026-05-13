-- ERP credentials store (docs/data-layer.md §3.1, §4.1).
--
-- M4 scope: define the storage + contract only. No actual ERP connector
-- runs from platform — the future import-agent reads these rows when
-- starting per-tenant sync jobs (platform injects the row's secret_json
-- into the import-agent container as ERP_CREDENTIALS env var).
--
-- One row per (enterprise × vendor) pair. secret_json is opaque to
-- platform — vendor-specific fields (api_key / app_id / token / etc).

CREATE TABLE IF NOT EXISTS erp_credentials (
  enterprise_id  TEXT NOT NULL REFERENCES enterprises(id),
  vendor         TEXT NOT NULL,                  -- kingdee | yongyou | ...
  display_name   TEXT,                           -- e.g. "金蝶 K/3 - 母公司"
  secret_json    TEXT NOT NULL,                  -- opaque vendor creds
  active         INTEGER NOT NULL DEFAULT 1,
  created_at     BIGINT NOT NULL,
  created_by     TEXT,
  rotated_at     BIGINT,
  PRIMARY KEY (enterprise_id, vendor)
);

CREATE INDEX IF NOT EXISTS idx_erp_credentials_active
  ON erp_credentials(enterprise_id) WHERE active = 1;
