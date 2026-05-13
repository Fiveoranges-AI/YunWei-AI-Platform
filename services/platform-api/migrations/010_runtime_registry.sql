-- 010 · Runtime registry.
--
-- Expresses the binding between enterprises and the runtime that serves
-- a given capability (e.g. `assistant`, `daily_report`, `erp_sync`).
--   - Free / Lite share a pooled runtime row.
--   - Pro / Max get a dedicated runtime row.
--
-- This migration only adds the registry tables; the legacy
-- `tenants(client_id, agent_id, container_url)` model and the HMAC
-- proxy remain untouched. A future task wires the proxy to look up the
-- runtime endpoint here instead of `tenants.container_url`.

CREATE TABLE IF NOT EXISTS runtimes (
  id           TEXT PRIMARY KEY,
  mode         TEXT NOT NULL,                       -- pooled | dedicated
  provider     TEXT NOT NULL,                       -- e.g. railway | k8s | local
  endpoint_url TEXT NOT NULL,
  health       TEXT NOT NULL DEFAULT 'unknown',
  version      TEXT NOT NULL DEFAULT 'unknown',
  created_at   BIGINT NOT NULL
);

CREATE TABLE IF NOT EXISTS runtime_bindings (
  enterprise_id TEXT NOT NULL REFERENCES enterprises(id),
  capability    TEXT NOT NULL,                      -- assistant | daily_report | erp_sync | ...
  runtime_id    TEXT NOT NULL REFERENCES runtimes(id),
  enabled       INTEGER NOT NULL DEFAULT 1,
  created_at    BIGINT NOT NULL,
  PRIMARY KEY (enterprise_id, capability)
);

CREATE INDEX IF NOT EXISTS idx_runtime_bindings_runtime
  ON runtime_bindings(runtime_id);
