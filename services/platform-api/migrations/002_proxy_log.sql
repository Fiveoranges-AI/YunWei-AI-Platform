CREATE TABLE IF NOT EXISTS proxy_log (
  id          BIGSERIAL PRIMARY KEY,
  ts          BIGINT NOT NULL,
  user_id     TEXT,
  client_id   TEXT,
  agent_id    TEXT,
  method      TEXT,
  path        TEXT,
  status      INTEGER,
  duration_ms INTEGER,
  ip          TEXT
);
CREATE INDEX IF NOT EXISTS idx_proxy_log_ts ON proxy_log(ts);
