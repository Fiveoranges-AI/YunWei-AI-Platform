-- Data layer (docs/data-layer.md M1 Foundation)
--
-- bronze_files: index of every bronze parquet that landed under
--   data/tenants/<client_id>/bronze/<source_type>/<date>/...
--   Used by 数据中心 Bronze Files 面板, by checksum dedup (AC-D2),
--   and by cascade-delete to silver via source_lineage (AC-D7).
--
-- silver_mappings: bronze→silver column mapping rules built via the
--   sidebar assistant (data-layer.md §3.3 "建映射"). Keyed by filename +
--   sheet pattern so the same template auto-runs next time (§5.1).

CREATE TABLE IF NOT EXISTS bronze_files (
  id                 TEXT PRIMARY KEY,
  client_id          TEXT NOT NULL,
  source_type        TEXT NOT NULL,
  bronze_path        TEXT NOT NULL,
  original_filename  TEXT,
  sheet_name         TEXT,
  row_count          INTEGER NOT NULL DEFAULT 0,
  checksum_sha256    TEXT,
  uploaded_by        TEXT,
  ingested_at        BIGINT NOT NULL,
  meta_json          TEXT NOT NULL DEFAULT '{}',
  deleted_at         BIGINT
);
CREATE INDEX IF NOT EXISTS idx_bronze_files_client_source
  ON bronze_files(client_id, source_type) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_bronze_files_checksum
  ON bronze_files(client_id, checksum_sha256) WHERE deleted_at IS NULL;

CREATE TABLE IF NOT EXISTS silver_mappings (
  id                       TEXT PRIMARY KEY,
  client_id                TEXT NOT NULL,
  source_type              TEXT NOT NULL,
  filename_pattern         TEXT NOT NULL,
  sheet_pattern            TEXT,
  silver_table             TEXT NOT NULL,
  column_map               TEXT NOT NULL,
  bronze_columns_snapshot  TEXT NOT NULL,
  created_at               BIGINT NOT NULL,
  created_by               TEXT,
  status                   TEXT NOT NULL DEFAULT 'active'
);
CREATE INDEX IF NOT EXISTS idx_silver_mappings_client
  ON silver_mappings(client_id, source_type);
