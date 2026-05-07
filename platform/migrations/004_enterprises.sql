-- Enterprise schema (option-3 design):
--   enterprises          one row per company / customer org
--   enterprise_members   user × enterprise + role (blanket access to all
--                        agents under the enterprise + the data center)
--   agent_grants         per-agent exception grants (consultants etc.);
--                        rare — most users join via enterprise_members
--
-- The legacy ``user_tenant`` table is left in place but no longer
-- referenced by application code; a future cleanup migration drops it.

CREATE TABLE IF NOT EXISTS enterprises (
  id                       TEXT PRIMARY KEY,         -- = legacy client_id
  legal_name               TEXT NOT NULL,
  display_name             TEXT NOT NULL,
  industry                 TEXT,
  region                   TEXT,
  size_tier                TEXT,                     -- small | medium | large
  tax_id                   TEXT,
  primary_contact_user_id  TEXT REFERENCES users(id),
  billing_email            TEXT,
  plan                     TEXT NOT NULL DEFAULT 'trial',
                                                     -- trial | standard | enterprise
  contract_start           BIGINT,
  contract_end             BIGINT,
  onboarding_stage         TEXT NOT NULL DEFAULT 'signed_up',
                                                     -- signed_up | configured | active
  active                   INTEGER NOT NULL DEFAULT 1,
  created_at               BIGINT NOT NULL
);

CREATE TABLE IF NOT EXISTS enterprise_members (
  user_id        TEXT NOT NULL REFERENCES users(id),
  enterprise_id  TEXT NOT NULL REFERENCES enterprises(id),
  role           TEXT NOT NULL DEFAULT 'member',     -- owner | admin | member
  granted_at     BIGINT NOT NULL,
  granted_by     TEXT,
  PRIMARY KEY (user_id, enterprise_id)
);

CREATE TABLE IF NOT EXISTS agent_grants (
  user_id     TEXT NOT NULL REFERENCES users(id),
  client_id   TEXT NOT NULL,
  agent_id    TEXT NOT NULL,
  role        TEXT NOT NULL DEFAULT 'user',
  granted_at  BIGINT NOT NULL,
  granted_by  TEXT,
  PRIMARY KEY (user_id, client_id, agent_id),
  FOREIGN KEY (client_id, agent_id) REFERENCES tenants(client_id, agent_id)
);

CREATE INDEX IF NOT EXISTS idx_enterprise_members_user ON enterprise_members(user_id);
CREATE INDEX IF NOT EXISTS idx_agent_grants_user       ON agent_grants(user_id);

-- Backfill enterprises from existing tenants. The legacy client_id is
-- promoted to enterprise.id; legal_name + display_name fall back to
-- client_id when no better data is available.
INSERT INTO enterprises (id, legal_name, display_name, plan, onboarding_stage, created_at)
SELECT
  client_id,
  client_id,
  COALESCE(MIN(display_name), client_id),
  'trial',
  'active',
  MIN(created_at)
FROM tenants
GROUP BY client_id
ON CONFLICT (id) DO NOTHING;

-- Backfill enterprise_members from legacy user_tenant rows. user_tenant
-- had a role column (typically 'user'); map anything outside the new
-- vocabulary to 'member'.
INSERT INTO enterprise_members (user_id, enterprise_id, role, granted_at, granted_by)
SELECT DISTINCT ON (user_id, client_id)
  user_id,
  client_id,
  CASE WHEN role IN ('owner','admin','member') THEN role ELSE 'member' END,
  granted_at,
  granted_by
FROM user_tenant
ORDER BY user_id, client_id, granted_at DESC
ON CONFLICT (user_id, enterprise_id) DO NOTHING;
