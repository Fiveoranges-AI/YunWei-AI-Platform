-- 012 · 锦泰耐火材料 AI 生产流转助手 MVP data foundation.
--
-- Scope for phase 1:
--   - schema and indexes only, no API wiring and no UI wiring
--   - no direct customer ERP / on-premise connection
--   - AI extraction results land in ai_extraction_queue first
--
-- The platform database already has public.users/public.tenants for auth and
-- runtime routing. Keeping this MVP under a separate schema avoids changing
-- existing auth, /win/, or 智通客户 customer-profile tables while preserving the
-- business table names requested by the project brief.

CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE SCHEMA IF NOT EXISTS jintai_mvp;

CREATE TABLE IF NOT EXISTS jintai_mvp.tenants (
  id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  slug             TEXT NOT NULL UNIQUE,
  display_name     TEXT NOT NULL,
  legal_name       TEXT,
  industry         TEXT,
  region           TEXT,
  website_url      TEXT,
  status           TEXT NOT NULL DEFAULT 'active',
  source_system    TEXT,
  source_record_id TEXT,
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS jintai_mvp.profiles (
  id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id        UUID NOT NULL REFERENCES jintai_mvp.tenants(id) ON DELETE CASCADE,
  platform_user_id TEXT REFERENCES public.users(id) ON DELETE SET NULL,
  role_code        TEXT NOT NULL,
  role_name        TEXT NOT NULL,
  display_name     TEXT NOT NULL,
  phone            TEXT,
  email            TEXT,
  status           TEXT NOT NULL DEFAULT 'active',
  source_system    TEXT,
  source_record_id TEXT,
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, role_code)
);

CREATE TABLE IF NOT EXISTS jintai_mvp.customers (
  id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id        UUID NOT NULL REFERENCES jintai_mvp.tenants(id) ON DELETE CASCADE,
  customer_code    TEXT NOT NULL,
  full_name        TEXT NOT NULL,
  short_name       TEXT,
  contact_name     TEXT,
  phone            TEXT,
  address          TEXT,
  tax_id           TEXT,
  credit_level     TEXT,
  status           TEXT NOT NULL DEFAULT 'active',
  source_system    TEXT,
  source_record_id TEXT,
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, customer_code)
);

CREATE TABLE IF NOT EXISTS jintai_mvp.products (
  id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id          UUID NOT NULL REFERENCES jintai_mvp.tenants(id) ON DELETE CASCADE,
  sku                TEXT NOT NULL,
  name               TEXT NOT NULL,
  category           TEXT,
  specification      TEXT,
  unit               TEXT NOT NULL DEFAULT '件',
  drawing_no         TEXT,
  quality_risk_level TEXT NOT NULL DEFAULT 'normal',
  status             TEXT NOT NULL DEFAULT 'active',
  source_system      TEXT,
  source_record_id   TEXT,
  created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, sku)
);

CREATE TABLE IF NOT EXISTS jintai_mvp.sales_orders (
  id                     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id              UUID NOT NULL REFERENCES jintai_mvp.tenants(id) ON DELETE CASCADE,
  customer_id            UUID NOT NULL REFERENCES jintai_mvp.customers(id) ON DELETE RESTRICT,
  product_id             UUID NOT NULL REFERENCES jintai_mvp.products(id) ON DELETE RESTRICT,
  order_no               TEXT NOT NULL,
  order_date             DATE NOT NULL,
  promised_delivery_date DATE,
  quantity               NUMERIC(18, 4) NOT NULL,
  unit                   TEXT NOT NULL DEFAULT '件',
  unit_price             NUMERIC(18, 4),
  amount_total           NUMERIC(18, 4),
  currency               TEXT NOT NULL DEFAULT 'CNY',
  priority               TEXT NOT NULL DEFAULT 'normal',
  status                 TEXT NOT NULL DEFAULT 'created',
  source_system          TEXT,
  source_record_id       TEXT,
  created_at             TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at             TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, order_no)
);

CREATE TABLE IF NOT EXISTS jintai_mvp.process_routes (
  id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id        UUID NOT NULL REFERENCES jintai_mvp.tenants(id) ON DELETE CASCADE,
  product_id       UUID NOT NULL REFERENCES jintai_mvp.products(id) ON DELETE CASCADE,
  route_code       TEXT NOT NULL,
  route_name       TEXT NOT NULL,
  version          TEXT NOT NULL DEFAULT 'v1',
  is_default       BOOLEAN NOT NULL DEFAULT true,
  status           TEXT NOT NULL DEFAULT 'active',
  source_system    TEXT,
  source_record_id TEXT,
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, route_code)
);

CREATE TABLE IF NOT EXISTS jintai_mvp.process_steps (
  id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id          UUID NOT NULL REFERENCES jintai_mvp.tenants(id) ON DELETE CASCADE,
  route_id           UUID NOT NULL REFERENCES jintai_mvp.process_routes(id) ON DELETE CASCADE,
  step_code          TEXT NOT NULL,
  step_name          TEXT NOT NULL,
  step_sequence      INTEGER NOT NULL,
  workstation        TEXT,
  standard_hours     NUMERIC(10, 2),
  required_role_code TEXT,
  qc_points          JSONB NOT NULL DEFAULT '{}'::jsonb,
  status             TEXT NOT NULL DEFAULT 'active',
  source_system      TEXT,
  source_record_id   TEXT,
  created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, route_id, step_code)
);

CREATE TABLE IF NOT EXISTS jintai_mvp.production_flow_cards (
  id                       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id                UUID NOT NULL REFERENCES jintai_mvp.tenants(id) ON DELETE CASCADE,
  sales_order_id           UUID NOT NULL REFERENCES jintai_mvp.sales_orders(id) ON DELETE RESTRICT,
  product_id               UUID NOT NULL REFERENCES jintai_mvp.products(id) ON DELETE RESTRICT,
  process_route_id         UUID NOT NULL REFERENCES jintai_mvp.process_routes(id) ON DELETE RESTRICT,
  flow_card_no             TEXT NOT NULL,
  planned_quantity         NUMERIC(18, 4) NOT NULL,
  completed_quantity       NUMERIC(18, 4) NOT NULL DEFAULT 0,
  defective_quantity       NUMERIC(18, 4) NOT NULL DEFAULT 0,
  unit                     TEXT NOT NULL DEFAULT '件',
  current_step_code        TEXT,
  priority                 TEXT NOT NULL DEFAULT 'normal',
  due_at                   TIMESTAMPTZ,
  started_at               TIMESTAMPTZ,
  completed_at             TIMESTAMPTZ,
  delay_reason             TEXT,
  quantity_variance_reason TEXT,
  status                   TEXT NOT NULL DEFAULT 'created',
  source_system            TEXT,
  source_record_id         TEXT,
  created_at               TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at               TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, flow_card_no)
);

CREATE TABLE IF NOT EXISTS jintai_mvp.production_step_records (
  id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id           UUID NOT NULL REFERENCES jintai_mvp.tenants(id) ON DELETE CASCADE,
  flow_card_id        UUID NOT NULL REFERENCES jintai_mvp.production_flow_cards(id) ON DELETE CASCADE,
  process_step_id     UUID NOT NULL REFERENCES jintai_mvp.process_steps(id) ON DELETE RESTRICT,
  operator_profile_id UUID REFERENCES jintai_mvp.profiles(id) ON DELETE SET NULL,
  step_code           TEXT NOT NULL,
  step_name           TEXT NOT NULL,
  step_sequence       INTEGER NOT NULL,
  input_quantity      NUMERIC(18, 4),
  output_quantity     NUMERIC(18, 4),
  defective_quantity  NUMERIC(18, 4) NOT NULL DEFAULT 0,
  unit                TEXT NOT NULL DEFAULT '件',
  started_at          TIMESTAMPTZ,
  completed_at        TIMESTAMPTZ,
  equipment_code      TEXT,
  exception_reason    TEXT,
  qc_result           JSONB NOT NULL DEFAULT '{}'::jsonb,
  status              TEXT NOT NULL DEFAULT 'queued',
  source_system       TEXT,
  source_record_id    TEXT,
  created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, flow_card_id, process_step_id)
);

CREATE TABLE IF NOT EXISTS jintai_mvp.document_templates (
  id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id        UUID NOT NULL REFERENCES jintai_mvp.tenants(id) ON DELETE CASCADE,
  template_code    TEXT NOT NULL,
  template_name    TEXT NOT NULL,
  document_type    TEXT NOT NULL,
  version          TEXT NOT NULL DEFAULT 'v1',
  content_schema   JSONB NOT NULL DEFAULT '{}'::jsonb,
  status           TEXT NOT NULL DEFAULT 'active',
  source_system    TEXT,
  source_record_id TEXT,
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, template_code, version)
);

CREATE TABLE IF NOT EXISTS jintai_mvp.attachments (
  id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id            UUID NOT NULL REFERENCES jintai_mvp.tenants(id) ON DELETE CASCADE,
  entity_table         TEXT,
  entity_id            UUID,
  file_name            TEXT NOT NULL,
  mime_type            TEXT,
  storage_url          TEXT NOT NULL,
  uploaded_by_profile_id UUID REFERENCES jintai_mvp.profiles(id) ON DELETE SET NULL,
  checksum             TEXT,
  status               TEXT NOT NULL DEFAULT 'uploaded',
  source_system        TEXT,
  source_record_id     TEXT,
  created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at           TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS jintai_mvp.ai_extraction_queue (
  id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id            UUID NOT NULL REFERENCES jintai_mvp.tenants(id) ON DELETE CASCADE,
  queue_no             TEXT NOT NULL,
  attachment_id        UUID REFERENCES jintai_mvp.attachments(id) ON DELETE SET NULL,
  source_document_name TEXT,
  extraction_type      TEXT NOT NULL,
  target_table         TEXT,
  payload              JSONB NOT NULL DEFAULT '{}'::jsonb,
  extracted_data       JSONB NOT NULL DEFAULT '{}'::jsonb,
  confidence           NUMERIC(5, 4),
  reviewed_by_profile_id UUID REFERENCES jintai_mvp.profiles(id) ON DELETE SET NULL,
  reviewed_at          TIMESTAMPTZ,
  status               TEXT NOT NULL DEFAULT 'pending_review',
  source_system        TEXT,
  source_record_id     TEXT,
  created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, queue_no)
);

CREATE TABLE IF NOT EXISTS jintai_mvp.ai_query_logs (
  id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id        UUID NOT NULL REFERENCES jintai_mvp.tenants(id) ON DELETE CASCADE,
  profile_id       UUID REFERENCES jintai_mvp.profiles(id) ON DELETE SET NULL,
  query_text       TEXT NOT NULL,
  answer_text      TEXT,
  cited_entity_refs JSONB NOT NULL DEFAULT '[]'::jsonb,
  model_name       TEXT,
  latency_ms       INTEGER,
  status           TEXT NOT NULL DEFAULT 'answered',
  source_system    TEXT,
  source_record_id TEXT,
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS jintai_mvp.external_source_mappings (
  id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id        UUID NOT NULL REFERENCES jintai_mvp.tenants(id) ON DELETE CASCADE,
  source_system    TEXT NOT NULL,
  source_table     TEXT NOT NULL,
  source_record_id TEXT NOT NULL,
  local_table      TEXT NOT NULL,
  local_record_id  UUID NOT NULL,
  sync_direction   TEXT NOT NULL DEFAULT 'import',
  last_seen_at     TIMESTAMPTZ,
  metadata         JSONB NOT NULL DEFAULT '{}'::jsonb,
  status           TEXT NOT NULL DEFAULT 'active',
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, source_system, source_table, source_record_id, local_table)
);

CREATE INDEX IF NOT EXISTS idx_jintai_profiles_tenant
  ON jintai_mvp.profiles(tenant_id);
CREATE INDEX IF NOT EXISTS idx_jintai_customers_tenant_status
  ON jintai_mvp.customers(tenant_id, status);
CREATE INDEX IF NOT EXISTS idx_jintai_sales_orders_customer
  ON jintai_mvp.sales_orders(tenant_id, customer_id);
CREATE INDEX IF NOT EXISTS idx_jintai_products_tenant_status
  ON jintai_mvp.products(tenant_id, status);
CREATE INDEX IF NOT EXISTS idx_jintai_routes_product
  ON jintai_mvp.process_routes(tenant_id, product_id);
CREATE INDEX IF NOT EXISTS idx_jintai_steps_route_sequence
  ON jintai_mvp.process_steps(route_id, step_sequence);
CREATE INDEX IF NOT EXISTS idx_jintai_flow_cards_status_due
  ON jintai_mvp.production_flow_cards(tenant_id, status, due_at);
CREATE INDEX IF NOT EXISTS idx_jintai_flow_cards_current_step
  ON jintai_mvp.production_flow_cards(tenant_id, current_step_code);
CREATE INDEX IF NOT EXISTS idx_jintai_step_records_card_sequence
  ON jintai_mvp.production_step_records(flow_card_id, step_sequence);
CREATE INDEX IF NOT EXISTS idx_jintai_extraction_queue_status
  ON jintai_mvp.ai_extraction_queue(tenant_id, status, created_at);
CREATE INDEX IF NOT EXISTS idx_jintai_source_mappings_lookup
  ON jintai_mvp.external_source_mappings(tenant_id, local_table, local_record_id);

CREATE OR REPLACE FUNCTION jintai_mvp.set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DO $$
DECLARE
  table_name TEXT;
BEGIN
  FOREACH table_name IN ARRAY ARRAY[
    'tenants',
    'profiles',
    'customers',
    'products',
    'sales_orders',
    'process_routes',
    'process_steps',
    'production_flow_cards',
    'production_step_records',
    'document_templates',
    'attachments',
    'ai_extraction_queue',
    'ai_query_logs',
    'external_source_mappings'
  ]
  LOOP
    EXECUTE format('DROP TRIGGER IF EXISTS set_updated_at ON jintai_mvp.%I', table_name);
    EXECUTE format(
      'CREATE TRIGGER set_updated_at BEFORE UPDATE ON jintai_mvp.%I FOR EACH ROW EXECUTE FUNCTION jintai_mvp.set_updated_at()',
      table_name
    );
  END LOOP;
END $$;
