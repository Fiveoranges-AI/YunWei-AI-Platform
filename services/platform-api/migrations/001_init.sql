CREATE TABLE IF NOT EXISTS users (
  id            TEXT PRIMARY KEY,
  username      TEXT UNIQUE NOT NULL,
  password_hash TEXT NOT NULL,
  display_name  TEXT NOT NULL,
  email         TEXT,
  created_at    BIGINT NOT NULL,
  last_login    BIGINT
);

CREATE TABLE IF NOT EXISTS tenants (
  client_id                TEXT NOT NULL,
  agent_id                 TEXT NOT NULL,
  display_name             TEXT NOT NULL,
  container_url            TEXT NOT NULL,
  hmac_secret_current      TEXT NOT NULL,
  hmac_key_id_current      TEXT NOT NULL,
  hmac_secret_prev         TEXT NOT NULL DEFAULT '',
  hmac_key_id_prev         TEXT NOT NULL DEFAULT '',
  hmac_rotated_at          BIGINT,
  agent_version            TEXT NOT NULL DEFAULT 'unknown',
  health                   TEXT NOT NULL DEFAULT 'unknown',
  health_checked_at        BIGINT,
  allowed_response_headers TEXT NOT NULL DEFAULT '[]',
  icon_url                 TEXT,
  description              TEXT,
  visibility               TEXT NOT NULL DEFAULT 'private',
  active                   INTEGER NOT NULL DEFAULT 1,
  tenant_uid               TEXT NOT NULL UNIQUE,
  created_at               BIGINT NOT NULL,
  PRIMARY KEY (client_id, agent_id)
);

CREATE TABLE IF NOT EXISTS user_tenant (
  user_id    TEXT NOT NULL REFERENCES users(id),
  client_id  TEXT NOT NULL,
  agent_id   TEXT NOT NULL,
  role       TEXT NOT NULL DEFAULT 'user',
  granted_at BIGINT NOT NULL,
  granted_by TEXT,
  PRIMARY KEY (user_id, client_id, agent_id),
  FOREIGN KEY (client_id, agent_id) REFERENCES tenants(client_id, agent_id)
);

CREATE TABLE IF NOT EXISTS platform_sessions (
  id         TEXT PRIMARY KEY,
  user_id    TEXT NOT NULL REFERENCES users(id),
  csrf_token TEXT NOT NULL,
  created_at BIGINT NOT NULL,
  expires_at BIGINT NOT NULL,
  ip         TEXT,
  user_agent TEXT
);

CREATE TABLE IF NOT EXISTS api_keys (
  id                TEXT PRIMARY KEY,
  user_id           TEXT NOT NULL REFERENCES users(id),
  client_id         TEXT NOT NULL,
  agent_id          TEXT NOT NULL,
  name              TEXT NOT NULL,
  prefix            TEXT NOT NULL,
  hash              TEXT NOT NULL,
  scope             TEXT NOT NULL DEFAULT 'rw',
  source_session_id TEXT REFERENCES platform_sessions(id),
  expires_at        BIGINT,
  created_at        BIGINT NOT NULL,
  last_used         BIGINT,
  revoked_at        BIGINT,
  FOREIGN KEY (client_id, agent_id) REFERENCES tenants(client_id, agent_id)
);

CREATE INDEX IF NOT EXISTS idx_sessions_user ON platform_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_keys_user ON api_keys(user_id);
