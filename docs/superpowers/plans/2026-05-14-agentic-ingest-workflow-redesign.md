# Agentic Ingest Workflow Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild Win schema ingest around durable parse artifacts, provider-aware extraction, deterministic entity resolution, progressive human review, and atomic tenant DB writeback.

**Architecture:** Keep the current `/api/win/ingest` job entry points, but replace the internals with `upload -> file type detection -> parser -> ParseArtifact -> selected_tables router -> extractor -> validation -> entity resolution -> ReviewDraft vNext -> confirm writeback`. LandingAI Parse and LandingAI Extract are paired for PDF/image/PPTX, while text/DOCX/spreadsheets use native parsers plus DeepSeek extraction.

**Tech Stack:** FastAPI, SQLAlchemy async ORM, Pydantic, LandingAI ADE SDK, DeepSeek via existing LLM service, React/Vite/TypeScript, pytest, SQLite in-memory tests for tenant DB coverage.

---

## Assumptions

- Backward compatibility is not required for schema ingest data contracts, tenant tables, or review draft JSON.
- Existing tenant business data can be discarded; destructive tenant schema cleanup is allowed.
- Platform auth, enterprise registration, sessions, routing, and storage stay outside this rewrite.
- The first version supports LandingAI Parse + LandingAI Extract for visual documents and native parser + DeepSeek Extract for text/DOCX/spreadsheet documents.
- MinerU, Mistral, real-time collaborative editing, and mixed LandingAI/MinerU parse-extract pipelines are excluded from this implementation.
- The untracked `docs/reference/` directory is reference material only and must not be added to commits unless explicitly requested.

## Success Criteria

- Every ingest job persists a `documents` row, a `document_parses` row, and a `document_extractions` row before human review.
- Extractor schemas include only `field_role in ("extractable", "identity_key")`.
- Review UI never shows UUID foreign keys, audit fields, raw parser payloads, model metadata, or timestamps as normal editable cells.
- Router selects table names, not legacy pipeline names.
- Entity resolution proposes create/update/link decisions for customers, contacts, contracts, orders, and invoices before review.
- Review is progressive in the fixed step order: 客户, 联系人, 合同 / 订单, 发票 / 付款, 物流 / 产品, 时间线 / 待办, 总览确认.
- Multiple users may view the same review, but only one user can autosave or confirm with a valid lock token and matching `review_version`.
- Confirm writes only selected rows, fills system links from row decisions, writes provenance with parse/extraction/source refs, and never lets AI nulls overwrite existing values.
- Backend pytest targets and frontend type check pass.

## File Structure

Create these backend files:

- `services/platform-api/yunwei_win/models/document_parse.py`  
  SQLAlchemy model for durable parse attempts.
- `services/platform-api/yunwei_win/services/schema_ingest/parse_artifact.py`  
  Pydantic `ParseArtifact` contract, source refs, chunks, table refs, and capabilities.
- `services/platform-api/yunwei_win/services/schema_ingest/file_type.py`  
  Physical file type detection and parser/extractor provider selection.
- `services/platform-api/yunwei_win/services/schema_ingest/parsers/__init__.py`  
  Parser provider exports.
- `services/platform-api/yunwei_win/services/schema_ingest/parsers/base.py`  
  Parser input/result protocols.
- `services/platform-api/yunwei_win/services/schema_ingest/parsers/landingai.py`  
  LandingAI ADE Parse adapter into `ParseArtifact`.
- `services/platform-api/yunwei_win/services/schema_ingest/parsers/text.py`  
  Plain text and pasted text parser.
- `services/platform-api/yunwei_win/services/schema_ingest/parsers/docx.py`  
  DOCX parser using `python-docx`.
- `services/platform-api/yunwei_win/services/schema_ingest/parsers/spreadsheet.py`  
  XLSX/XLS/CSV parser using `openpyxl`, `pandas`, and stdlib `csv` where useful.
- `services/platform-api/yunwei_win/services/schema_ingest/parsers/factory.py`  
  Parser selection and execution facade.
- `services/platform-api/yunwei_win/services/schema_ingest/table_router.py`  
  DeepSeek-backed table router with deterministic fail-open fallback.
- `services/platform-api/yunwei_win/services/schema_ingest/extraction_schema.py`  
  Selected-table JSON schema builder from catalog field roles.
- `services/platform-api/yunwei_win/services/schema_ingest/extractors.py`  
  Provider matrix, extraction input/output normalization, and LandingAI/DeepSeek dispatch.
- `services/platform-api/yunwei_win/services/schema_ingest/extraction_normalize.py`  
  Normalized extraction table/field/value/source-ref envelope.
- `services/platform-api/yunwei_win/services/schema_ingest/entity_resolution.py`  
  Deterministic match proposals and row decisions.
- `services/platform-api/yunwei_win/services/schema_ingest/review_lock.py`  
  Lock acquire, refresh, version check, and release helpers.
- `services/platform-api/yunwei_win/services/schema_ingest/review_autosave.py`  
  Server-side draft patching for cells, row decisions, and step state.

Modify these backend files:

- `services/platform-api/pyproject.toml`  
  Add `python-docx>=1.1` and `xlrd>=2.0` if `.docx` and `.xls` parsing tests fail because imports are unavailable.
- `services/platform-api/yunwei_win/models/__init__.py`  
  Register `DocumentParse` and remove vNext mainline registrations for dropped customer memory/inbox target tables when they are no longer referenced.
- `services/platform-api/yunwei_win/models/company_schema.py`  
  Add `field_role` and `review_visible`.
- `services/platform-api/yunwei_win/models/document_extraction.py`  
  Replace legacy route/raw fields with `parse_id`, `selected_tables`, `extraction`, `extraction_metadata`, `validation_warnings`, `entity_resolution`, review lock fields, and reviewer audit fields.
- `services/platform-api/yunwei_win/models/customer.py`  
  Keep `industry` and `notes` if profile/read surfaces expose them.
- `services/platform-api/yunwei_win/models/contact.py`  
  Standardize on free-text `title`, `phone`, `mobile`, `email`, `wechat_id`, `address`; keep `role` as a system/default enum if still needed by read APIs; drop `needs_review` from vNext ingest use.
- `services/platform-api/yunwei_win/models/contract.py`  
  Ensure `delivery_terms` and `penalty_terms` exist on the canonical model and are writable.
- `services/platform-api/yunwei_win/models/company_data.py`  
  Keep canonical product, finance, logistics, journal, and milestone tables; remove old duplicate memory/inbox targets from ingest write maps.
- `services/platform-api/yunwei_win/models/field_provenance.py`  
  Add `parse_id`, `extraction_id`, `source_refs`, and `review_action`.
- `services/platform-api/yunwei_win/db.py`  
  Ensure tenant table creation includes `document_parses` and vNext model metadata.
- `services/platform-api/yunwei_win/services/company_schema/default_catalog.py`  
  Rewrite seed catalog with first-principles field classifications.
- `services/platform-api/yunwei_win/services/company_schema/catalog.py`  
  Return `field_role` and `review_visible` in catalog JSON and seed idempotently.
- `services/platform-api/yunwei_win/services/landingai_ade_client.py`  
  Expose parse metadata needed by LandingAI adapter without flattening to markdown only.
- `services/platform-api/yunwei_win/services/schema_ingest/schemas.py`  
  Replace current draft schemas with vNext review, lock, autosave, source-ref, and row-decision contracts.
- `services/platform-api/yunwei_win/services/schema_ingest/review_draft.py`  
  Materialize selected table drafts with presentation, steps, row decisions, source refs, and review-visible fields only.
- `services/platform-api/yunwei_win/services/schema_ingest/extraction_validation.py`  
  Validate normalized extraction against generated selected-table schema and `ParseArtifact` refs.
- `services/platform-api/yunwei_win/services/schema_ingest/confirm.py`  
  Rewrite writeback around row decisions, explicit links, system fields, provenance, lock/version checks, and null-overwrite rules.
- `services/platform-api/yunwei_win/services/schema_ingest/auto.py`  
  Replace legacy evidence/route/pipeline flow with parse/router/extract/validate/resolve/materialize.
- `services/platform-api/yunwei_win/workers/ingest_rq.py`  
  Persist vNext stage progress and result fields.
- `services/platform-api/yunwei_win/api/schema_ingest.py`  
  Replace review endpoints with `/review`, `/review/lock`, autosave PATCH, confirm with lock token, and review envelope response.
- `services/platform-api/yunwei_win/api/customer_profile/reads.py`  
  Expose every table allowed by first-version review, including source document references.
- `services/platform-api/yunwei_win/api/read.py`  
  Align read API with vNext confirmed facts if it is still used by frontend screens.
- `services/platform-api/yunwei_win/assistant/context.py`  
  Read vNext confirmed facts and journal/task tables, not dropped legacy memory targets.

Modify these frontend files:

- `apps/win-web/src/data/types.ts`  
  Add vNext review contracts, lock state, row decisions, source refs, and read/profile table types.
- `apps/win-web/src/api/ingest.ts`  
  Add `getReview`, `acquireReviewLock`, `autosaveReview`, and confirm request with lock token/base version.
- `apps/win-web/src/screens/Review.tsx`  
  Load the review endpoint, acquire lock, handle read-only mode, autosave conflicts, and final confirm.
- `apps/win-web/src/components/review/ReviewWizard.tsx`  
  New progressive step shell.
- `apps/win-web/src/components/review/ReviewCard.tsx`  
  New card presentation for master rows.
- `apps/win-web/src/components/review/ReviewDetailTable.tsx`  
  New table presentation for detail rows.
- `apps/win-web/src/components/review/ReviewSourcePanel.tsx`  
  New source evidence panel.
- `apps/win-web/src/components/review/ReviewSummary.tsx`  
  New final summary view.
- `apps/win-web/src/components/review/ReviewTableWorkspace.tsx`  
  Replace or reduce to compatibility wrapper around the wizard.
- `apps/win-web/src/screens/CustomerDetail.tsx`, `apps/win-web/src/screens/Profile.tsx`, `apps/win-web/src/components/CustomerDetailPane.tsx`  
  Surface confirmed vNext tables that are review-visible.

Create or replace these tests:

- `services/platform-api/tests/test_vnext_tenant_schema.py`
- `services/platform-api/tests/test_parse_artifact.py`
- `services/platform-api/tests/test_file_type_detection.py`
- `services/platform-api/tests/test_parser_providers.py`
- `services/platform-api/tests/test_table_router_vnext.py`
- `services/platform-api/tests/test_extraction_schema_vnext.py`
- `services/platform-api/tests/test_extraction_normalize_validate.py`
- `services/platform-api/tests/test_entity_resolution.py`
- `services/platform-api/tests/test_review_draft_vnext.py`
- `services/platform-api/tests/test_review_lock_api.py`
- `services/platform-api/tests/test_review_autosave_api.py`
- `services/platform-api/tests/test_confirm_vnext.py`
- `services/platform-api/tests/test_schema_ingest_vnext_auto.py`
- `services/platform-api/tests/test_vnext_profile_visibility.py`

## Task 1: Tenant Schema and Catalog Roles

**Files:**
- Create: `services/platform-api/yunwei_win/models/document_parse.py`
- Create: `services/platform-api/tests/test_vnext_tenant_schema.py`
- Modify: `services/platform-api/yunwei_win/models/__init__.py`
- Modify: `services/platform-api/yunwei_win/models/company_schema.py`
- Modify: `services/platform-api/yunwei_win/models/document_extraction.py`
- Modify: `services/platform-api/yunwei_win/models/field_provenance.py`
- Modify: `services/platform-api/yunwei_win/services/company_schema/default_catalog.py`
- Modify: `services/platform-api/yunwei_win/services/company_schema/catalog.py`
- Modify: `services/platform-api/yunwei_win/db.py`

- [ ] **Step 1: Write tenant schema tests**

Add these tests to `services/platform-api/tests/test_vnext_tenant_schema.py`:

```python
from __future__ import annotations

import json

import pytest
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession

import yunwei_win.models  # noqa: F401
from yunwei_win.db import Base
from yunwei_win.models.company_schema import CompanySchemaField
from yunwei_win.models.document_extraction import DocumentExtraction
from yunwei_win.models.document_parse import DocumentParse
from yunwei_win.models.field_provenance import FieldProvenance
from yunwei_win.services.company_schema import DEFAULT_COMPANY_SCHEMA, ensure_default_company_schema, get_company_schema


@pytest.fixture(autouse=True)
def _clean_state():
    yield


async def _session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session = AsyncSession(engine, expire_on_commit=False)
    return engine, session


def test_vnext_models_are_registered():
    assert "document_parses" in Base.metadata.tables
    assert "document_extractions" in Base.metadata.tables
    assert "company_schema_fields" in Base.metadata.tables
    assert "field_provenance" in Base.metadata.tables


def test_document_parse_model_has_artifact_columns():
    cols = DocumentParse.__table__.columns
    assert {"document_id", "provider", "model", "status", "artifact", "raw_metadata", "warnings", "error_message"}.issubset(cols.keys())


def test_document_extraction_model_has_vnext_review_columns():
    cols = DocumentExtraction.__table__.columns
    assert {
        "document_id",
        "parse_id",
        "provider",
        "model",
        "selected_tables",
        "extraction",
        "extraction_metadata",
        "validation_warnings",
        "entity_resolution",
        "review_draft",
        "review_version",
        "locked_by",
        "lock_token",
        "lock_expires_at",
        "last_reviewed_by",
        "last_reviewed_at",
        "confirmed_by",
        "confirmed_at",
    }.issubset(cols.keys())


def test_company_schema_fields_have_roles_and_visibility():
    cols = CompanySchemaField.__table__.columns
    assert "field_role" in cols.keys()
    assert "review_visible" in cols.keys()


def test_field_provenance_records_parse_extraction_and_review_action():
    cols = FieldProvenance.__table__.columns
    assert {"parse_id", "extraction_id", "source_refs", "review_action"}.issubset(cols.keys())


@pytest.mark.asyncio
async def test_default_catalog_classifies_system_fields_as_hidden():
    engine, session = await _session()
    try:
        await ensure_default_company_schema(session)
        catalog = await get_company_schema(session)
        fields = {
            (table["table_name"], field["field_name"]): field
            for table in catalog["tables"]
            for field in table["fields"]
        }
        assert fields[("orders", "customer_id")]["field_role"] == "system_link"
        assert fields[("orders", "customer_id")]["review_visible"] is False
        assert fields[("customers", "full_name")]["field_role"] == "identity_key"
        assert fields[("customers", "full_name")]["review_visible"] is True
        assert fields[("contacts", "title")]["field_role"] == "extractable"
        assert ("contacts", "needs_review") not in fields
        assert fields[("customer_tasks", "assignee")]["field_role"] == "extractable"
        assert ("customer_tasks", "owner") not in fields
    finally:
        await session.close()
        await engine.dispose()


def test_default_catalog_contains_only_vnext_target_tables():
    names = {entry["table_name"] for entry in DEFAULT_COMPANY_SCHEMA}
    assert names == {
        "customers",
        "contacts",
        "products",
        "product_requirements",
        "orders",
        "contracts",
        "contract_payment_milestones",
        "invoices",
        "invoice_items",
        "payments",
        "shipments",
        "shipment_items",
        "customer_journal_items",
        "customer_tasks",
    }
```

- [ ] **Step 2: Run tests and confirm expected failure**

Run:

```bash
cd services/platform-api
./.venv/bin/pytest tests/test_vnext_tenant_schema.py -q
```

Expected: FAIL because `yunwei_win.models.document_parse` does not exist and `CompanySchemaField.field_role` is not defined.

- [ ] **Step 3: Implement `DocumentParse` model**

Create `services/platform-api/yunwei_win/models/document_parse.py` with:

```python
from __future__ import annotations

import enum
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import JSON, DateTime, Enum as SQLEnum, ForeignKey, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from yunwei_win.db import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class DocumentParseStatus(str, enum.Enum):
    parsed = "parsed"
    failed = "failed"


class DocumentParse(Base):
    __tablename__ = "document_parses"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    provider: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    status: Mapped[DocumentParseStatus] = mapped_column(
        SQLEnum(DocumentParseStatus, name="document_parse_status"),
        nullable=False,
        default=DocumentParseStatus.parsed,
        index=True,
    )
    artifact: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    raw_metadata: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    warnings: Mapped[list[Any] | None] = mapped_column(JSON, nullable=True)
    error_message: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, server_default=func.now(), nullable=False)
```

- [ ] **Step 4: Register vNext models**

Modify `services/platform-api/yunwei_win/models/__init__.py` so it imports `DocumentParse`. Keep existing model imports needed by tests, and remove imports only after all direct references to dropped memory/inbox models are removed in later tasks.

- [ ] **Step 5: Add company schema field roles**

Modify `services/platform-api/yunwei_win/models/company_schema.py` by adding these columns to `CompanySchemaField` after `data_type`:

```python
field_role: Mapped[str] = mapped_column(String(32), nullable=False, default="extractable")
review_visible: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
```

- [ ] **Step 6: Replace `DocumentExtraction` columns with vNext shape**

Modify `services/platform-api/yunwei_win/models/document_extraction.py` so `DocumentExtraction` contains the columns asserted by the test. Keep `DocumentExtractionStatus` values `pending_review`, `confirmed`, `ignored`, `failed`.

Use this column layout:

```python
parse_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("document_parses.id", ondelete="SET NULL"), nullable=True, index=True)
provider: Mapped[str | None] = mapped_column(String(64), nullable=True)
model: Mapped[str | None] = mapped_column(String(128), nullable=True)
selected_tables: Mapped[list[Any] | None] = mapped_column(JSON, nullable=True)
extraction: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
extraction_metadata: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
validation_warnings: Mapped[list[Any] | None] = mapped_column(JSON, nullable=True)
entity_resolution: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
review_draft: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
review_version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
locked_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
lock_token: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
lock_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
last_reviewed_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
last_reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
confirmed_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
```

- [ ] **Step 7: Add vNext provenance columns**

Modify `services/platform-api/yunwei_win/models/field_provenance.py` to add:

```python
parse_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("document_parses.id", ondelete="SET NULL"), nullable=True, index=True)
extraction_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("document_extractions.id", ondelete="SET NULL"), nullable=True, index=True)
source_refs: Mapped[list[Any] | None] = mapped_column(JSON, nullable=True)
review_action: Mapped[str | None] = mapped_column(String(32), nullable=True)
```

- [ ] **Step 8: Rewrite default catalog with vNext field classifications**

Modify every field entry in `services/platform-api/yunwei_win/services/company_schema/default_catalog.py` to include:

```python
{"field_name": "full_name", "label": "公司全称", "data_type": "text", "required": True, "field_role": "identity_key", "review_visible": True}
{"field_name": "customer_id", "label": "客户", "data_type": "uuid", "required": True, "field_role": "system_link", "review_visible": False}
{"field_name": "document_id", "label": "来源文档", "data_type": "uuid", "field_role": "audit", "review_visible": False}
```

Use the field classification table from `docs/superpowers/specs/2026-05-14-agentic-ingest-workflow-redesign.md`. Remove `contacts.needs_review` and `customer_tasks.owner`. Add `contacts.title`, `contacts.phone`, `contacts.address`, `contracts.delivery_terms`, and `contracts.penalty_terms`.

- [ ] **Step 9: Return field role metadata in catalog API**

Modify `services/platform-api/yunwei_win/services/company_schema/catalog.py` so `_field_to_dict` returns `field_role` and `review_visible`, and `ensure_default_company_schema` seeds those values.

- [ ] **Step 10: Run tenant schema tests**

Run:

```bash
cd services/platform-api
./.venv/bin/pytest tests/test_vnext_tenant_schema.py tests/test_company_schema_catalog.py -q
```

Expected: PASS.

- [ ] **Step 11: Commit**

```bash
git add services/platform-api/yunwei_win/models/document_parse.py services/platform-api/yunwei_win/models/__init__.py services/platform-api/yunwei_win/models/company_schema.py services/platform-api/yunwei_win/models/document_extraction.py services/platform-api/yunwei_win/models/field_provenance.py services/platform-api/yunwei_win/services/company_schema/default_catalog.py services/platform-api/yunwei_win/services/company_schema/catalog.py services/platform-api/yunwei_win/db.py services/platform-api/tests/test_vnext_tenant_schema.py services/platform-api/tests/test_company_schema_catalog.py
git commit -m "feat(win): add vnext ingest tenant schema"
```

## Task 2: ParseArtifact Contract and Parser Providers

**Files:**
- Create: `services/platform-api/yunwei_win/services/schema_ingest/parse_artifact.py`
- Create: `services/platform-api/yunwei_win/services/schema_ingest/file_type.py`
- Create: `services/platform-api/yunwei_win/services/schema_ingest/parsers/__init__.py`
- Create: `services/platform-api/yunwei_win/services/schema_ingest/parsers/base.py`
- Create: `services/platform-api/yunwei_win/services/schema_ingest/parsers/landingai.py`
- Create: `services/platform-api/yunwei_win/services/schema_ingest/parsers/text.py`
- Create: `services/platform-api/yunwei_win/services/schema_ingest/parsers/docx.py`
- Create: `services/platform-api/yunwei_win/services/schema_ingest/parsers/spreadsheet.py`
- Create: `services/platform-api/yunwei_win/services/schema_ingest/parsers/factory.py`
- Create: `services/platform-api/tests/test_parse_artifact.py`
- Create: `services/platform-api/tests/test_file_type_detection.py`
- Create: `services/platform-api/tests/test_parser_providers.py`
- Modify: `services/platform-api/pyproject.toml`
- Modify: `services/platform-api/yunwei_win/services/landingai_ade_client.py`

- [ ] **Step 1: Write ParseArtifact tests**

Add `services/platform-api/tests/test_parse_artifact.py`:

```python
from __future__ import annotations

from yunwei_win.services.schema_ingest.parse_artifact import ParseArtifact, ParseCapabilities, ParseChunk, ParseSourceRef


def test_parse_artifact_round_trips_visual_grounding():
    artifact = ParseArtifact(
        version=1,
        provider="landingai",
        source_type="pdf",
        markdown="# Contract\n\nAmount 30000",
        pages=[{"id": "page:1", "page_number": 1}],
        chunks=[ParseChunk(id="chunk:1", type="text", text="Amount 30000", page=1)],
        grounding={"chunk:1": {"bbox": [1, 2, 3, 4], "page": 1}},
        tables=[],
        metadata={"page_count": 1},
        capabilities=ParseCapabilities(pages=True, chunks=True, visual_grounding=True, table_cells=True),
    )

    dumped = artifact.model_dump(mode="json")

    assert dumped["chunks"][0]["id"] == "chunk:1"
    assert dumped["grounding"]["chunk:1"]["bbox"] == [1, 2, 3, 4]
    assert dumped["capabilities"]["visual_grounding"] is True


def test_parse_source_ref_accepts_sheet_cells_and_text_spans():
    sheet_ref = ParseSourceRef(ref_type="spreadsheet_cell", ref_id="sheet:报价单!R3C5", sheet="报价单", row=3, col=5)
    text_ref = ParseSourceRef(ref_type="text_span", ref_id="text:0-10", start=0, end=10, excerpt="客户名称")

    assert sheet_ref.ref_id == "sheet:报价单!R3C5"
    assert text_ref.excerpt == "客户名称"
```

- [ ] **Step 2: Write file type detection tests**

Add `services/platform-api/tests/test_file_type_detection.py`:

```python
from __future__ import annotations

import pytest

from yunwei_win.services.schema_ingest.file_type import detect_source_type


@pytest.mark.parametrize(
    ("filename", "content_type", "source_hint", "expected_source", "expected_parser", "expected_extractor"),
    [
        ("contract.pdf", "application/pdf", "file", "pdf", "landingai", "landingai"),
        ("scan.png", "image/png", "file", "image", "landingai", "landingai"),
        ("deck.pptx", "application/vnd.openxmlformats-officedocument.presentationml.presentation", "file", "pptx", "landingai", "landingai"),
        ("note.txt", "text/plain", "file", "text", "text", "deepseek"),
        ("note.md", "text/markdown", "file", "text", "text", "deepseek"),
        ("contacts.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "file", "docx", "docx", "deepseek"),
        ("quote.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "file", "spreadsheet", "spreadsheet", "deepseek"),
        ("quote.xls", "application/vnd.ms-excel", "file", "spreadsheet", "spreadsheet", "deepseek"),
        ("quote.csv", "text/csv", "file", "spreadsheet", "spreadsheet", "deepseek"),
        ("pasted.txt", "text/plain", "pasted_text", "text", "text", "deepseek"),
    ],
)
def test_detect_source_type_routes_to_parser_and_extractor(filename, content_type, source_hint, expected_source, expected_parser, expected_extractor):
    detected = detect_source_type(filename=filename, content_type=content_type, source_hint=source_hint)
    assert detected.source_type == expected_source
    assert detected.parser_provider == expected_parser
    assert detected.extractor_provider == expected_extractor


def test_detect_source_type_rejects_unsupported_binary():
    with pytest.raises(ValueError, match="unsupported file type"):
        detect_source_type(filename="archive.zip", content_type="application/zip", source_hint="file")
```

- [ ] **Step 3: Write parser provider tests**

Add `services/platform-api/tests/test_parser_providers.py`:

```python
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from yunwei_win.services.schema_ingest.parsers.landingai import LandingAIParser
from yunwei_win.services.schema_ingest.parsers.text import TextParser
from yunwei_win.services.schema_ingest.parsers.spreadsheet import SpreadsheetParser


@pytest.mark.asyncio
async def test_text_parser_creates_single_chunk_artifact():
    artifact = await TextParser().parse_text("客户：测试有限公司\n金额：30000", filename="note.txt")
    assert artifact.provider == "text"
    assert artifact.source_type == "text"
    assert artifact.markdown.startswith("客户：")
    assert artifact.chunks[0].id == "text:0"
    assert artifact.capabilities.text_spans is True


@pytest.mark.asyncio
async def test_landingai_parser_preserves_chunks_splits_and_grounding(monkeypatch, tmp_path):
    async def fake_parse(path: Path):
        return SimpleNamespace(
            markdown="# Parsed",
            chunks=[{"id": "c1", "text": "客户"}],
            splits=[{"id": "page:1", "page_number": 1}],
            grounding={"c1": {"page": 1, "bbox": [0, 0, 10, 10]}},
            metadata={"page_count": 1},
        )

    monkeypatch.setattr("yunwei_win.services.schema_ingest.parsers.landingai.parse_file_to_markdown", fake_parse)
    path = tmp_path / "contract.pdf"
    path.write_bytes(b"%PDF")

    artifact = await LandingAIParser().parse_file(path, filename="contract.pdf", content_type="application/pdf", source_type="pdf")

    assert artifact.provider == "landingai"
    assert artifact.markdown == "# Parsed"
    assert artifact.chunks[0].id == "c1"
    assert artifact.grounding["c1"]["bbox"] == [0, 0, 10, 10]
    assert artifact.capabilities.visual_grounding is True


@pytest.mark.asyncio
async def test_spreadsheet_parser_emits_sheet_cell_refs(tmp_path):
    import openpyxl

    path = tmp_path / "quote.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "报价单"
    ws["A1"] = "客户"
    ws["B1"] = "金额"
    ws["A2"] = "测试有限公司"
    ws["B2"] = 30000
    wb.save(path)

    artifact = await SpreadsheetParser().parse_file(path, filename="quote.xlsx", content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", source_type="spreadsheet")

    assert "报价单" in artifact.markdown
    ids = {chunk.id for chunk in artifact.chunks}
    assert "sheet:报价单!R2C2" in ids
    assert artifact.capabilities.spreadsheet_cells is True
```

- [ ] **Step 4: Run parser tests and confirm expected failure**

Run:

```bash
cd services/platform-api
./.venv/bin/pytest tests/test_parse_artifact.py tests/test_file_type_detection.py tests/test_parser_providers.py -q
```

Expected: FAIL because new parser modules do not exist.

- [ ] **Step 5: Implement ParseArtifact models**

Create `services/platform-api/yunwei_win/services/schema_ingest/parse_artifact.py` with Pydantic models named exactly:

```python
ParseCapabilities
ParseSourceRef
ParseChunk
ParseTableCell
ParseTable
ParseArtifact
```

Use `version: int = 1`, `provider: Literal["landingai", "text", "docx", "spreadsheet"]`, `source_type: str`, `markdown: str`, `pages: list[dict[str, Any]]`, `chunks: list[ParseChunk]`, `grounding: dict[str, Any]`, `tables: list[ParseTable]`, `metadata: dict[str, Any]`, and `capabilities: ParseCapabilities`.

- [ ] **Step 6: Implement physical file type detection**

Create `services/platform-api/yunwei_win/services/schema_ingest/file_type.py` with:

```python
@dataclass(frozen=True)
class DetectedSourceType:
    source_type: Literal["pdf", "image", "pptx", "text", "docx", "spreadsheet"]
    parser_provider: Literal["landingai", "text", "docx", "spreadsheet"]
    extractor_provider: Literal["landingai", "deepseek"]
```

`detect_source_type()` must use `source_hint == "pasted_text"` before MIME or extension, then route by lowercased filename extension and content type.

- [ ] **Step 7: Implement parser providers**

Implement parser classes with these public methods:

```python
class TextParser:
    async def parse_text(self, text: str, *, filename: str) -> ParseArtifact:
        raise NotImplementedError

class LandingAIParser:
    async def parse_file(self, path: Path, *, filename: str, content_type: str | None, source_type: str) -> ParseArtifact:
        raise NotImplementedError

class DocxParser:
    async def parse_file(self, path: Path, *, filename: str, content_type: str | None, source_type: str = "docx") -> ParseArtifact:
        raise NotImplementedError

class SpreadsheetParser:
    async def parse_file(self, path: Path, *, filename: str, content_type: str | None, source_type: str = "spreadsheet") -> ParseArtifact:
        raise NotImplementedError
```

Use stable source IDs:

```text
text:0
docx:p1
docx:table1:R2C3
sheet:报价单!R3C5
```

- [ ] **Step 8: Add missing dependencies only when required**

If `python-docx` import fails, add `"python-docx>=1.1"` to `services/platform-api/pyproject.toml`. If `.xls` parsing fails through pandas due missing engine, add `"xlrd>=2.0"`.

- [ ] **Step 9: Run parser tests**

Run:

```bash
cd services/platform-api
./.venv/bin/pytest tests/test_parse_artifact.py tests/test_file_type_detection.py tests/test_parser_providers.py tests/test_landingai_ade_client.py -q
```

Expected: PASS.

- [ ] **Step 10: Commit**

```bash
git add services/platform-api/pyproject.toml services/platform-api/yunwei_win/services/landingai_ade_client.py services/platform-api/yunwei_win/services/schema_ingest/parse_artifact.py services/platform-api/yunwei_win/services/schema_ingest/file_type.py services/platform-api/yunwei_win/services/schema_ingest/parsers services/platform-api/tests/test_parse_artifact.py services/platform-api/tests/test_file_type_detection.py services/platform-api/tests/test_parser_providers.py services/platform-api/tests/test_landingai_ade_client.py
git commit -m "feat(win): add parse artifacts and parser providers"
```

## Task 3: Selected-Table Router and Extraction Schema

**Files:**
- Create: `services/platform-api/yunwei_win/services/schema_ingest/table_router.py`
- Create: `services/platform-api/yunwei_win/services/schema_ingest/extraction_schema.py`
- Create: `services/platform-api/tests/test_table_router_vnext.py`
- Create: `services/platform-api/tests/test_extraction_schema_vnext.py`
- Modify: `services/platform-api/yunwei_win/services/schema_ingest/__init__.py`
- Modify: `services/platform-api/yunwei_win/services/ingest/extractors/canonical_schema.py`

- [ ] **Step 1: Write router tests**

Add `services/platform-api/tests/test_table_router_vnext.py`:

```python
from __future__ import annotations

import pytest

from yunwei_win.services.schema_ingest.parse_artifact import ParseArtifact, ParseCapabilities
from yunwei_win.services.schema_ingest.table_router import route_tables


class FakeRouterLLM:
    async def complete_json(self, *, prompt: str, response_schema: dict):
        assert "customers" in prompt
        return {
            "selected_tables": [{"table_name": "customers", "confidence": 0.94, "reason": "包含客户名称"}],
            "rejected_tables": [{"table_name": "shipments", "reason": "无物流信息"}],
            "document_summary": "客户资料",
            "needs_human_attention": False,
        }


class FailingRouterLLM:
    async def complete_json(self, *, prompt: str, response_schema: dict):
        raise RuntimeError("llm down")


def _artifact():
    return ParseArtifact(version=1, provider="text", source_type="text", markdown="客户：测试有限公司", capabilities=ParseCapabilities(text_spans=True))


def _catalog():
    return {
        "tables": [
            {"table_name": "customers", "label": "客户", "purpose": "客户主档", "is_active": True, "fields": []},
            {"table_name": "contacts", "label": "联系人", "purpose": "联系人", "is_active": True, "fields": []},
            {"table_name": "shipments", "label": "发货", "purpose": "物流", "is_active": True, "fields": []},
        ]
    }


@pytest.mark.asyncio
async def test_route_tables_returns_selected_table_names():
    result = await route_tables(parse_artifact=_artifact(), catalog=_catalog(), llm=FakeRouterLLM())
    assert result.selected_tables[0].table_name == "customers"
    assert result.document_summary == "客户资料"
    assert result.warnings == []


@pytest.mark.asyncio
async def test_route_tables_fail_open_to_core_tables():
    result = await route_tables(parse_artifact=_artifact(), catalog=_catalog(), llm=FailingRouterLLM())
    assert [t.table_name for t in result.selected_tables] == ["customers", "contacts", "customer_journal_items"]
    assert result.needs_human_attention is True
    assert "router failed" in result.warnings[0]
```

- [ ] **Step 2: Write extraction schema tests**

Add `services/platform-api/tests/test_extraction_schema_vnext.py`:

```python
from __future__ import annotations

import json

from yunwei_win.services.company_schema import DEFAULT_COMPANY_SCHEMA
from yunwei_win.services.schema_ingest.extraction_schema import build_selected_tables_schema_json


def _catalog_from_default() -> dict:
    tables = []
    for table_idx, table in enumerate(DEFAULT_COMPANY_SCHEMA):
        table_is_array = bool(table.get("is_array", False))
        fields = []
        for field_idx, field in enumerate(table["fields"]):
            fields.append({
                **field,
                "required": bool(field.get("required", False)),
                "is_array": bool(field.get("is_array", table_is_array)),
                "is_active": True,
                "sort_order": field.get("sort_order", field_idx),
            })
        tables.append({**table, "fields": fields, "is_active": True, "sort_order": table.get("sort_order", table_idx)})
    return {"tables": tables}


def test_selected_table_schema_excludes_system_and_audit_fields():
    schema = json.loads(build_selected_tables_schema_json(["orders", "customer_journal_items"], _catalog_from_default()))
    assert "orders" in schema["properties"]
    order_props = schema["properties"]["orders"]["properties"]
    journal_props = schema["properties"]["customer_journal_items"]["items"]["properties"]
    assert "amount_total" in order_props
    assert "customer_id" not in order_props
    assert "document_id" not in journal_props
    assert "confidence" not in journal_props


def test_selected_table_schema_keeps_identity_keys():
    schema = json.loads(build_selected_tables_schema_json(["customers"], _catalog_from_default()))
    props = schema["properties"]["customers"]["properties"]
    assert "full_name" in props
    assert "tax_id" in props
    assert props["full_name"]["description"].startswith("公司全称")
```

- [ ] **Step 3: Run tests and confirm expected failure**

Run:

```bash
cd services/platform-api
./.venv/bin/pytest tests/test_table_router_vnext.py tests/test_extraction_schema_vnext.py -q
```

Expected: FAIL because `table_router.py` and `extraction_schema.py` do not exist.

- [ ] **Step 4: Implement router contracts**

Create Pydantic models in `table_router.py`:

```python
SelectedTable
RejectedTable
TableRouteResult
```

Implement:

```python
async def route_tables(*, parse_artifact: ParseArtifact, catalog: dict[str, Any], llm: Any | None = None) -> TableRouteResult:
    raise NotImplementedError
```

Build the prompt from `parse_artifact.markdown[:12000]`, active table names, labels, purposes, source type, and capabilities. On exception or empty selected table list, return selected tables `customers`, `contacts`, `customer_journal_items` with warning text starting `router failed`.

- [ ] **Step 5: Implement selected-table schema builder**

Create `build_selected_tables_schema_json(selected_tables: list[str], catalog: dict[str, Any]) -> str`. Include only active fields where `field_role` is `extractable` or `identity_key`. Keep table array semantics from `table["is_array"]` and field `is_array`.

- [ ] **Step 6: Bridge old canonical schema imports**

Modify `services/platform-api/yunwei_win/services/ingest/extractors/canonical_schema.py` to either delegate to `build_selected_tables_schema_json` or become unused after Task 4. Tests from old code should assert no system fields are emitted.

- [ ] **Step 7: Run router and schema tests**

Run:

```bash
cd services/platform-api
./.venv/bin/pytest tests/test_table_router_vnext.py tests/test_extraction_schema_vnext.py tests/test_canonical_extractor_schema.py -q
```

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add services/platform-api/yunwei_win/services/schema_ingest/table_router.py services/platform-api/yunwei_win/services/schema_ingest/extraction_schema.py services/platform-api/yunwei_win/services/schema_ingest/__init__.py services/platform-api/yunwei_win/services/ingest/extractors/canonical_schema.py services/platform-api/tests/test_table_router_vnext.py services/platform-api/tests/test_extraction_schema_vnext.py services/platform-api/tests/test_canonical_extractor_schema.py
git commit -m "feat(win): route ingest by selected tables"
```

## Task 4: Extraction Provider Matrix and Normalization

**Files:**
- Create: `services/platform-api/yunwei_win/services/schema_ingest/extractors.py`
- Create: `services/platform-api/yunwei_win/services/schema_ingest/extraction_normalize.py`
- Create: `services/platform-api/tests/test_extraction_normalize_validate.py`
- Modify: `services/platform-api/yunwei_win/services/schema_ingest/extraction_validation.py`
- Modify: `services/platform-api/yunwei_win/services/landingai_ade_client.py`
- Modify: `services/platform-api/yunwei_win/services/ingest/extractors/providers/landingai.py`
- Modify: `services/platform-api/yunwei_win/services/ingest/extractors/providers/deepseek.py`

- [ ] **Step 1: Write normalization and validation tests**

Add `services/platform-api/tests/test_extraction_normalize_validate.py`:

```python
from __future__ import annotations

import pytest

from yunwei_win.services.schema_ingest.extraction_normalize import normalize_extraction
from yunwei_win.services.schema_ingest.extraction_validation import validate_normalized_extraction
from yunwei_win.services.schema_ingest.parse_artifact import ParseArtifact, ParseCapabilities, ParseChunk


def _artifact():
    return ParseArtifact(
        version=1,
        provider="spreadsheet",
        source_type="spreadsheet",
        markdown="|金额|\n|30000|",
        chunks=[ParseChunk(id="sheet:报价单!R2C1", type="table_cell", text="30000", sheet="报价单", row=2, col=1)],
        capabilities=ParseCapabilities(spreadsheet_cells=True),
    )


def _catalog():
    return {
        "tables": [
            {
                "table_name": "orders",
                "label": "订单",
                "is_active": True,
                "is_array": False,
                "fields": [
                    {"field_name": "amount_total", "label": "订单金额", "data_type": "decimal", "field_role": "extractable", "review_visible": True, "is_active": True},
                    {"field_name": "customer_id", "label": "客户", "data_type": "uuid", "field_role": "system_link", "review_visible": False, "is_active": True},
                ],
            }
        ]
    }


def test_normalize_deepseek_value_confidence_source_refs():
    raw = {"tables": {"orders": [{"amount_total": {"value": "30000", "confidence": 0.91, "source_refs": ["sheet:报价单!R2C1"]}}]}}
    normalized = normalize_extraction(raw, selected_tables=["orders"], provider="deepseek")
    row = normalized.tables["orders"][0]
    assert row.fields["amount_total"].value == "30000"
    assert row.fields["amount_total"].confidence == 0.91
    assert row.fields["amount_total"].source_refs[0].ref_id == "sheet:报价单!R2C1"


def test_validate_rejects_unknown_system_field_and_bad_source_ref():
    raw = {"tables": {"orders": [{"customer_id": {"value": "not-from-file"}, "amount_total": {"value": "30000", "source_refs": ["missing:ref"]}}]}}
    normalized = normalize_extraction(raw, selected_tables=["orders"], provider="deepseek")
    warnings = validate_normalized_extraction(normalized, selected_tables=["orders"], catalog=_catalog(), parse_artifact=_artifact())
    assert any("unknown or non-extractable field orders.customer_id" in w for w in warnings)
    assert any("source ref missing:ref not found" in w for w in warnings)
```

- [ ] **Step 2: Run tests and confirm expected failure**

Run:

```bash
cd services/platform-api
./.venv/bin/pytest tests/test_extraction_normalize_validate.py -q
```

Expected: FAIL because `extraction_normalize.py` does not exist.

- [ ] **Step 3: Implement normalized extraction models**

Create Pydantic models:

```python
NormalizedFieldValue
NormalizedRow
NormalizedExtraction
```

`NormalizedFieldValue` must contain:

```python
value: Any | None
confidence: float | None = None
source_refs: list[ParseSourceRef] = Field(default_factory=list)
raw: Any | None = None
```

`normalize_extraction()` must accept LandingAI style `{"customers": {"full_name": "测试有限公司"}}` and DeepSeek style `{"tables": {"customers": [{"full_name": {"value": "测试有限公司"}}]}}`.

- [ ] **Step 4: Implement provider matrix**

Create `services/platform-api/yunwei_win/services/schema_ingest/extractors.py` with:

```python
async def extract_from_parse_artifact(
    *,
    parse_artifact: ParseArtifact,
    selected_tables: list[str],
    catalog: dict[str, Any],
    provider: Literal["landingai", "deepseek"],
    session: AsyncSession | None = None,
) -> NormalizedExtraction:
    raise NotImplementedError
```

For `provider == "landingai"`, call `extract_with_schema(schema_json, parse_artifact.markdown)` and map `extraction_metadata` to source refs. For `provider == "deepseek"`, call the existing DeepSeek provider or LLM service with schema JSON and explicit instruction to return `value`, `confidence`, and `source_refs`.

- [ ] **Step 5: Implement validation against ParseArtifact refs**

Modify `extraction_validation.py` to export:

```python
def validate_normalized_extraction(normalized: NormalizedExtraction, *, selected_tables: list[str], catalog: dict[str, Any], parse_artifact: ParseArtifact) -> list[str]:
    raise NotImplementedError
```

Validate table membership, field membership, `field_role`, primitive data types, enum membership, and source ref existence against `chunk.id`, table cell IDs, text spans, and `grounding` keys.

- [ ] **Step 6: Run extraction tests**

Run:

```bash
cd services/platform-api
./.venv/bin/pytest tests/test_extraction_normalize_validate.py tests/test_landingai_extractor_provider.py tests/test_deepseek_schema_extractor_provider.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add services/platform-api/yunwei_win/services/schema_ingest/extractors.py services/platform-api/yunwei_win/services/schema_ingest/extraction_normalize.py services/platform-api/yunwei_win/services/schema_ingest/extraction_validation.py services/platform-api/yunwei_win/services/landingai_ade_client.py services/platform-api/yunwei_win/services/ingest/extractors/providers/landingai.py services/platform-api/yunwei_win/services/ingest/extractors/providers/deepseek.py services/platform-api/tests/test_extraction_normalize_validate.py services/platform-api/tests/test_landingai_extractor_provider.py services/platform-api/tests/test_deepseek_schema_extractor_provider.py
git commit -m "feat(win): normalize vnext extraction outputs"
```

## Task 5: Entity Resolution Proposals

**Files:**
- Create: `services/platform-api/yunwei_win/services/schema_ingest/entity_resolution.py`
- Create: `services/platform-api/tests/test_entity_resolution.py`
- Modify: `services/platform-api/yunwei_win/services/schema_ingest/schemas.py`

- [ ] **Step 1: Write entity resolution tests**

Add `services/platform-api/tests/test_entity_resolution.py`:

```python
from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

import yunwei_win.models  # noqa: F401
from yunwei_win.db import Base
from yunwei_win.models.customer import Customer
from yunwei_win.models.contact import Contact
from yunwei_win.services.schema_ingest.entity_resolution import propose_entity_resolution
from yunwei_win.services.schema_ingest.extraction_normalize import NormalizedExtraction, NormalizedFieldValue, NormalizedRow


@pytest.fixture(autouse=True)
def _clean_state():
    yield


async def _session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session = AsyncSession(engine, expire_on_commit=False)
    return engine, session


def _field(value):
    return NormalizedFieldValue(value=value, confidence=0.95, source_refs=[])


@pytest.mark.asyncio
async def test_customer_tax_id_strong_match_defaults_to_update():
    engine, session = await _session()
    try:
        existing = Customer(full_name="测试有限公司", tax_id="91330000X")
        session.add(existing)
        await session.flush()
        extraction = NormalizedExtraction(
            provider="deepseek",
            tables={"customers": [NormalizedRow(client_row_id="customers:0", fields={"full_name": _field("测试有限公司"), "tax_id": _field("91330000X")})]},
            metadata={},
        )
        proposal = await propose_entity_resolution(session=session, extraction=extraction)
        row = proposal.rows[0]
        assert row.table_name == "customers"
        assert row.proposed_operation == "update"
        assert row.selected_entity_id == existing.id
        assert row.match_level == "strong"
        assert row.match_keys == ["tax_id"]
    finally:
        await session.close()
        await engine.dispose()


@pytest.mark.asyncio
async def test_contact_name_only_candidate_defaults_to_create():
    engine, session = await _session()
    try:
        customer = Customer(full_name="测试有限公司")
        session.add(customer)
        await session.flush()
        contact = Contact(customer_id=customer.id, name="张三")
        session.add(contact)
        await session.flush()
        extraction = NormalizedExtraction(
            provider="deepseek",
            tables={"contacts": [NormalizedRow(client_row_id="contacts:0", fields={"name": _field("张三")})]},
            metadata={},
        )
        proposal = await propose_entity_resolution(session=session, extraction=extraction, selected_customer_id=customer.id)
        row = proposal.rows[0]
        assert row.proposed_operation == "create"
        assert row.match_level == "weak"
        assert row.candidates[0].entity_id == contact.id
    finally:
        await session.close()
        await engine.dispose()
```

- [ ] **Step 2: Run tests and confirm expected failure**

Run:

```bash
cd services/platform-api
./.venv/bin/pytest tests/test_entity_resolution.py -q
```

Expected: FAIL because `entity_resolution.py` does not exist.

- [ ] **Step 3: Implement entity resolution models and rules**

Create Pydantic models:

```python
EntityCandidate
EntityResolutionRow
EntityResolutionProposal
```

Implement deterministic strong rules:

```text
customers: exact tax_id, then exact normalized full_name
contacts: exact mobile/email within selected customer
contracts: contract_no_external + selected customer
invoices: invoice_no + selected customer
orders: external order number only if that field exists in catalog/extraction
```

Implement weak rules:

```text
contacts: name + selected customer
orders: selected customer + amount_total + date
```

Strong match defaults to `update`; weak match defaults to `create` with candidates; no match defaults to `create`.

- [ ] **Step 4: Export row-decision types in ReviewDraft schemas**

Modify `services/platform-api/yunwei_win/services/schema_ingest/schemas.py` to add:

```python
ReviewRowDecision
ReviewEntityCandidate
```

Fields must align with the entity resolution JSON:

```python
operation: Literal["create", "update", "link_existing", "ignore"]
selected_entity_id: UUID | None
candidate_entities: list[ReviewEntityCandidate]
match_level: Literal["strong", "weak", "none"] | None
match_keys: list[str]
reason: str | None
```

- [ ] **Step 5: Run entity resolution tests**

Run:

```bash
cd services/platform-api
./.venv/bin/pytest tests/test_entity_resolution.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add services/platform-api/yunwei_win/services/schema_ingest/entity_resolution.py services/platform-api/yunwei_win/services/schema_ingest/schemas.py services/platform-api/tests/test_entity_resolution.py
git commit -m "feat(win): propose ingest entity resolution"
```

## Task 6: ReviewDraft vNext Materialization

**Files:**
- Create: `services/platform-api/tests/test_review_draft_vnext.py`
- Modify: `services/platform-api/yunwei_win/services/schema_ingest/schemas.py`
- Modify: `services/platform-api/yunwei_win/services/schema_ingest/review_draft.py`

- [ ] **Step 1: Write ReviewDraft vNext tests**

Add `services/platform-api/tests/test_review_draft_vnext.py`:

```python
from __future__ import annotations

from uuid import uuid4

from yunwei_win.services.company_schema import DEFAULT_COMPANY_SCHEMA
from yunwei_win.services.schema_ingest.entity_resolution import EntityResolutionProposal, EntityResolutionRow
from yunwei_win.services.schema_ingest.extraction_normalize import NormalizedExtraction, NormalizedFieldValue, NormalizedRow
from yunwei_win.services.schema_ingest.parse_artifact import ParseArtifact, ParseCapabilities, ParseChunk, ParseSourceRef
from yunwei_win.services.schema_ingest.review_draft import materialize_review_draft_vnext


def _catalog():
    tables = []
    for table_idx, table in enumerate(DEFAULT_COMPANY_SCHEMA):
        fields = []
        for field_idx, field in enumerate(table["fields"]):
            fields.append({**field, "is_active": True, "sort_order": field.get("sort_order", field_idx), "is_array": field.get("is_array", table.get("is_array", False))})
        tables.append({**table, "fields": fields, "is_active": True, "sort_order": table.get("sort_order", table_idx)})
    return {"tables": tables}


def test_review_draft_hides_system_fields_and_assigns_steps():
    extraction = NormalizedExtraction(
        provider="deepseek",
        tables={"orders": [NormalizedRow(client_row_id="orders:0", fields={"amount_total": NormalizedFieldValue(value="30000", confidence=0.91, source_refs=[ParseSourceRef(ref_type="spreadsheet_cell", ref_id="sheet:报价单!R2C2")])})]},
        metadata={},
    )
    parse = ParseArtifact(version=1, provider="spreadsheet", source_type="spreadsheet", markdown="|金额|\n|30000|", chunks=[ParseChunk(id="sheet:报价单!R2C2", type="table_cell", text="30000")], capabilities=ParseCapabilities(spreadsheet_cells=True))
    proposal = EntityResolutionProposal(rows=[EntityResolutionRow(table_name="orders", client_row_id="orders:0", proposed_operation="create", match_level="none", match_keys=[], confidence=None, reason=None, candidates=[])])

    draft = materialize_review_draft_vnext(
        extraction_id=uuid4(),
        document_id=uuid4(),
        parse_id=uuid4(),
        document_filename="quote.xlsx",
        parse_artifact=parse,
        selected_tables=["orders"],
        normalized_extraction=extraction,
        entity_resolution=proposal,
        catalog=_catalog(),
        document_summary="报价单",
        warnings=[],
    )

    assert draft.steps[0].key == "commercial"
    table = draft.tables[0]
    assert table.review_step == "commercial"
    assert table.presentation == "card"
    cells = {cell.field_name: cell for cell in table.rows[0].cells}
    assert "amount_total" in cells
    assert "customer_id" not in cells
    assert cells["amount_total"].source_refs[0].ref_id == "sheet:报价单!R2C2"


def test_default_only_row_is_not_writable():
    extraction = NormalizedExtraction(provider="deepseek", tables={"orders": [NormalizedRow(client_row_id="orders:0", fields={})]}, metadata={})
    parse = ParseArtifact(version=1, provider="text", source_type="text", markdown="", capabilities=ParseCapabilities(text_spans=True))
    proposal = EntityResolutionProposal(rows=[EntityResolutionRow(table_name="orders", client_row_id="orders:0", proposed_operation="create", match_level="none", match_keys=[], confidence=None, reason=None, candidates=[])])

    draft = materialize_review_draft_vnext(
        extraction_id=uuid4(),
        document_id=uuid4(),
        parse_id=uuid4(),
        document_filename="note.txt",
        parse_artifact=parse,
        selected_tables=["orders"],
        normalized_extraction=extraction,
        entity_resolution=proposal,
        catalog=_catalog(),
        document_summary=None,
        warnings=[],
    )

    assert draft.tables[0].rows[0].is_writable is False
    assert draft.tables[0].rows[0].row_decision.operation == "ignore"
```

- [ ] **Step 2: Run tests and confirm expected failure**

Run:

```bash
cd services/platform-api
./.venv/bin/pytest tests/test_review_draft_vnext.py -q
```

Expected: FAIL because `materialize_review_draft_vnext` and vNext schema fields do not exist.

- [ ] **Step 3: Replace ReviewDraft schemas**

Modify `services/platform-api/yunwei_win/services/schema_ingest/schemas.py` to define these public classes:

```python
ReviewSourceRef
ReviewCell
ReviewRowDecision
ReviewRow
ReviewTable
ReviewStep
ReviewDraftDocument
ReviewDraft
ReviewCellPatch
ReviewRowDecisionPatch
AutosaveReviewRequest
AutosaveReviewResponse
AcquireReviewLockResponse
ConfirmExtractionRequest
ConfirmExtractionResponse
```

Required field additions:

```python
ReviewDraft.parse_id
ReviewDraft.review_version
ReviewDraft.current_step
ReviewDraft.steps
ReviewTable.presentation
ReviewTable.review_step
ReviewRow.row_decision
ReviewRow.is_writable
ReviewCell.source_refs
ReviewCell.review_visible
```

- [ ] **Step 4: Implement materializer**

Modify `review_draft.py` to add `materialize_review_draft_vnext()`. It must:

```text
include only selected tables
include only fields with review_visible true
skip ordinary system_link and audit cells
map master rows to card presentation
map detail rows to table presentation
assign fixed review steps
attach entity resolution as row_decision
mark default-only rows is_writable false and row_decision.operation ignore
copy source refs from NormalizedFieldValue
skip review steps with no materialized rows
```

- [ ] **Step 5: Run ReviewDraft tests**

Run:

```bash
cd services/platform-api
./.venv/bin/pytest tests/test_review_draft_vnext.py tests/test_ingest_review_draft.py -q
```

Expected: PASS after updating or replacing old `test_ingest_review_draft.py` assertions to match vNext.

- [ ] **Step 6: Commit**

```bash
git add services/platform-api/yunwei_win/services/schema_ingest/schemas.py services/platform-api/yunwei_win/services/schema_ingest/review_draft.py services/platform-api/tests/test_review_draft_vnext.py services/platform-api/tests/test_ingest_review_draft.py
git commit -m "feat(win): materialize progressive ingest review drafts"
```

## Task 7: Review Lock and Autosave API

**Files:**
- Create: `services/platform-api/yunwei_win/services/schema_ingest/review_lock.py`
- Create: `services/platform-api/yunwei_win/services/schema_ingest/review_autosave.py`
- Create: `services/platform-api/tests/test_review_lock_api.py`
- Create: `services/platform-api/tests/test_review_autosave_api.py`
- Modify: `services/platform-api/yunwei_win/api/schema_ingest.py`
- Modify: `services/platform-api/yunwei_win/services/schema_ingest/schemas.py`

- [ ] **Step 1: Write review lock API tests**

Add `services/platform-api/tests/test_review_lock_api.py` with ASGI app setup copied from `tests/test_company_schema_catalog.py`. The core assertions:

```python
async def test_acquire_lock_returns_token_for_unlocked_pending_review(ac):
    res = await ac.post(f"/api/win/ingest/extractions/{extraction_id}/review/lock", json={"user": "user_a"})
    assert res.status_code == 200
    body = res.json()
    assert body["mode"] == "edit"
    assert body["locked_by"] == "user_a"
    assert body["lock_token"]
    assert body["review_version"] == 0


async def test_acquire_lock_by_other_user_returns_read_only(ac):
    first = await ac.post(f"/api/win/ingest/extractions/{extraction_id}/review/lock", json={"user": "user_a"})
    second = await ac.post(f"/api/win/ingest/extractions/{extraction_id}/review/lock", json={"user": "user_b"})
    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["mode"] == "read_only"
    assert second.json()["locked_by"] == "user_a"
```

- [ ] **Step 2: Write autosave API tests**

Add `services/platform-api/tests/test_review_autosave_api.py` with assertions:

```python
async def test_autosave_requires_matching_lock_and_version(ac):
    lock = (await ac.post(f"/api/win/ingest/extractions/{extraction_id}/review/lock", json={"user": "user_a"})).json()
    bad = await ac.patch(f"/api/win/ingest/extractions/{extraction_id}/review", json={"lock_token": lock["lock_token"], "base_version": 99, "cell_patches": []})
    assert bad.status_code == 409


async def test_autosave_updates_draft_and_increments_version(ac):
    lock = (await ac.post(f"/api/win/ingest/extractions/{extraction_id}/review/lock", json={"user": "user_a"})).json()
    res = await ac.patch(
        f"/api/win/ingest/extractions/{extraction_id}/review",
        json={
            "lock_token": lock["lock_token"],
            "base_version": lock["review_version"],
            "cell_patches": [{"table_name": "customers", "client_row_id": "customers:0", "field_name": "short_name", "value": "测试", "status": "edited"}],
            "row_patches": [],
            "current_step": "customer",
        },
    )
    assert res.status_code == 200
    assert res.json()["review_version"] == lock["review_version"] + 1
```

- [ ] **Step 3: Run tests and confirm expected failure**

Run:

```bash
cd services/platform-api
./.venv/bin/pytest tests/test_review_lock_api.py tests/test_review_autosave_api.py -q
```

Expected: FAIL because endpoints do not exist.

- [ ] **Step 4: Implement review lock helper**

Create `review_lock.py` with:

```python
LOCK_TTL_SECONDS = 15 * 60
async def acquire_review_lock(session: AsyncSession, *, extraction_id: UUID, user: str | None) -> AcquireReviewLockResponse:
    raise NotImplementedError

def assert_valid_review_lock(extraction: DocumentExtraction, *, lock_token: UUID, base_version: int) -> None:
    raise NotImplementedError

def release_review_lock(extraction: DocumentExtraction) -> None:
    raise NotImplementedError
```

Expired locks are treated as unlocked. Existing same-user locks return edit mode and refresh expiry.

- [ ] **Step 5: Implement autosave helper**

Create `review_autosave.py` with:

```python
async def autosave_review(session: AsyncSession, *, extraction_id: UUID, request: AutosaveReviewRequest, reviewed_by: str | None) -> AutosaveReviewResponse:
    raise NotImplementedError
```

Apply cell patches, row decision patches, current step, and step status in the server-stored `review_draft`. Increment `review_version` by one on success.

- [ ] **Step 6: Wire API endpoints**

Modify `api/schema_ingest.py`:

```text
GET /extractions/{id}/review
POST /extractions/{id}/review/lock
PATCH /extractions/{id}/review
POST /extractions/{id}/confirm
```

Keep older `/extractions/{id}` route as a thin alias only if frontend callers still use it during this task; remove the alias in Task 12.

- [ ] **Step 7: Run lock/autosave tests**

Run:

```bash
cd services/platform-api
./.venv/bin/pytest tests/test_review_lock_api.py tests/test_review_autosave_api.py tests/test_ingest_jobs.py -q
```

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add services/platform-api/yunwei_win/services/schema_ingest/review_lock.py services/platform-api/yunwei_win/services/schema_ingest/review_autosave.py services/platform-api/yunwei_win/api/schema_ingest.py services/platform-api/yunwei_win/services/schema_ingest/schemas.py services/platform-api/tests/test_review_lock_api.py services/platform-api/tests/test_review_autosave_api.py
git commit -m "feat(win): add ingest review locking and autosave"
```

## Task 8: Confirm Writeback vNext

**Files:**
- Create: `services/platform-api/tests/test_confirm_vnext.py`
- Modify: `services/platform-api/yunwei_win/services/schema_ingest/confirm.py`
- Modify: `services/platform-api/yunwei_win/services/schema_ingest/fk_links.py`
- Modify: `services/platform-api/yunwei_win/models/field_provenance.py`
- Modify: `services/platform-api/yunwei_win/services/schema_ingest/review_lock.py`

- [ ] **Step 1: Write confirm tests**

Add `services/platform-api/tests/test_confirm_vnext.py` with these cases:

```python
async def test_confirm_requires_valid_lock_token_and_latest_version(ac):
    lock = await acquire_lock()
    res = await ac.post(f"/api/win/ingest/extractions/{extraction_id}/confirm", json={"lock_token": lock["lock_token"], "base_version": lock["review_version"] + 1})
    assert res.status_code == 409


async def test_confirm_writes_customer_then_child_system_links(session):
    response = await confirm_with_draft_containing_customer_and_contact()
    assert response.status == "confirmed"
    contact = await load_written_contact()
    assert contact.customer_id == written_customer.id


async def test_confirm_skips_default_only_rows(session):
    response = await confirm_with_order_row_containing_only_default_currency()
    assert response.written_rows.get("orders", []) == []


async def test_confirm_does_not_overwrite_existing_value_with_ai_null(session):
    existing = await create_customer(full_name="测试有限公司", address="旧地址")
    response = await confirm_update_customer_with_ai_null_address(existing.id)
    refreshed = await load_customer(existing.id)
    assert refreshed.address == "旧地址"


async def test_confirm_writes_final_value_provenance_with_parse_and_source_refs(session):
    response = await confirm_customer_short_name_with_source_ref()
    provenance = await load_provenance("customers", response.written_rows["customers"][0], "short_name")
    assert provenance.parse_id == parse_id
    assert provenance.extraction_id == extraction_id
    assert provenance.review_action == "ai"
    assert provenance.source_refs[0]["ref_id"] == "chunk:1"
```

- [ ] **Step 2: Run tests and confirm expected failure**

Run:

```bash
cd services/platform-api
./.venv/bin/pytest tests/test_confirm_vnext.py -q
```

Expected: FAIL because confirm still uses legacy cells and does not require lock token/version.

- [ ] **Step 3: Rewrite confirm write order and row selection**

Modify `confirm.py` to:

```text
load DocumentExtraction
assert status pending_review
assert lock_token and base_version match
validate latest server ReviewDraft
write parent rows first
resolve row_decision.operation create/update/link_existing/ignore
fill system_link fields from row decisions and row_uuid_map
skip rows where is_writable false unless user explicitly changed row_decision to create/update/link_existing
apply defaults only after row is selected for write
write child/detail rows
write field provenance for final persisted values
mark extraction confirmed
release lock
commit once
```

- [ ] **Step 4: Implement null-overwrite policy**

Update writes so:

```text
AI null or missing value never overwrites an existing DB value
edited null overwrites only when ReviewCell has explicit_clear true
rejected cells are ignored
default cells are written only for new rows or empty existing fields
linked/system cells are written from system context, not extractor values
```

If `ReviewCell` lacks `explicit_clear`, add `explicit_clear: bool = False` in `schemas.py`.

- [ ] **Step 5: Write provenance**

Every persisted field must create or update a `FieldProvenance` row containing:

```text
document_id
parse_id
extraction_id
entity_type
entity_id
field_name
source_refs
confidence
review_action
value
```

Map review action:

```text
cell.source == ai -> ai
cell.source == edited -> edited
cell.source == default -> default
system link -> linked
system audit -> system
```

- [ ] **Step 6: Run confirm tests**

Run:

```bash
cd services/platform-api
./.venv/bin/pytest tests/test_confirm_vnext.py tests/test_ingest_confirm.py -q
```

Expected: PASS after replacing legacy `test_ingest_confirm.py` expectations with vNext lock/version and row-decision behavior.

- [ ] **Step 7: Commit**

```bash
git add services/platform-api/yunwei_win/services/schema_ingest/confirm.py services/platform-api/yunwei_win/services/schema_ingest/fk_links.py services/platform-api/yunwei_win/services/schema_ingest/schemas.py services/platform-api/yunwei_win/models/field_provenance.py services/platform-api/tests/test_confirm_vnext.py services/platform-api/tests/test_ingest_confirm.py
git commit -m "feat(win): confirm ingest drafts with row decisions"
```

## Task 9: Auto Ingest Orchestrator and Worker Integration

**Files:**
- Create: `services/platform-api/tests/test_schema_ingest_vnext_auto.py`
- Modify: `services/platform-api/yunwei_win/services/schema_ingest/auto.py`
- Modify: `services/platform-api/yunwei_win/workers/ingest_rq.py`
- Modify: `services/platform-api/yunwei_win/workers/ingest_rq_worker.py`
- Modify: `services/platform-api/yunwei_win/api/schema_ingest.py`

- [ ] **Step 1: Write auto pipeline tests**

Add `services/platform-api/tests/test_schema_ingest_vnext_auto.py`:

```python
from __future__ import annotations

import pytest

from yunwei_win.models.document_parse import DocumentParse
from yunwei_win.models.document_extraction import DocumentExtraction
from yunwei_win.services.schema_ingest.auto import auto_ingest


@pytest.mark.asyncio
async def test_auto_ingest_text_persists_parse_extraction_and_review(session, monkeypatch):
    async def fake_route_tables(**kwargs):
        return route_result(["customers"])

    async def fake_extract_from_parse_artifact(**kwargs):
        return normalized_customers("测试有限公司")

    monkeypatch.setattr("yunwei_win.services.schema_ingest.auto.route_tables", fake_route_tables)
    monkeypatch.setattr("yunwei_win.services.schema_ingest.auto.extract_from_parse_artifact", fake_extract_from_parse_artifact)

    result = await auto_ingest(session=session, text_content="客户：测试有限公司", original_filename="note.txt", content_type="text/plain", source_hint="pasted_text", uploader="user_a")

    parse = await session.get(DocumentParse, result.parse_id)
    extraction = await session.get(DocumentExtraction, result.extraction_id)
    assert parse.provider == "text"
    assert extraction.parse_id == parse.id
    assert extraction.selected_tables[0]["table_name"] == "customers"
    assert extraction.review_draft["steps"][0]["key"] == "customer"
```

Use local helper fixtures in the test file for `session`, `route_result`, and `normalized_customers`.

- [ ] **Step 2: Run test and confirm expected failure**

Run:

```bash
cd services/platform-api
./.venv/bin/pytest tests/test_schema_ingest_vnext_auto.py -q
```

Expected: FAIL because `auto_ingest` still uses legacy evidence and pipeline routing.

- [ ] **Step 3: Rewrite orchestrator**

Modify `auto.py` so the pipeline is exactly:

```python
detected = detect_source_type(filename=original_filename, content_type=content_type, source_hint=source_hint)
document = await create_document_for_ingest(session=session, detected=detected, file_metadata=file_metadata, uploader=uploader)
parse_artifact = await parse_document(detected=detected, file_path=file_path, text_content=text_content)
document_parse = DocumentParse(document_id=document.id, provider=detected.parser_provider, model=parse_model, status=DocumentParseStatus.parsed, artifact=parse_artifact.model_dump(mode="json"))
route_result = await route_tables(parse_artifact=parse_artifact, catalog=catalog)
normalized = await extract_from_parse_artifact(parse_artifact=parse_artifact, selected_tables=[t.table_name for t in route_result.selected_tables], catalog=catalog, provider=detected.extractor_provider, session=session)
warnings = validate_normalized_extraction(normalized, selected_tables=[t.table_name for t in route_result.selected_tables], catalog=catalog, parse_artifact=parse_artifact)
entity_resolution = await propose_entity_resolution(session=session, extraction=normalized)
review_draft = materialize_review_draft_vnext(extraction_id=extraction_id, document_id=document.id, parse_id=document_parse.id, document_filename=original_filename or "upload", parse_artifact=parse_artifact, selected_tables=[t.table_name for t in route_result.selected_tables], normalized_extraction=normalized, entity_resolution=entity_resolution, catalog=catalog, document_summary=route_result.document_summary, warnings=warnings + route_result.warnings)
document_extraction = DocumentExtraction(id=extraction_id, document_id=document.id, parse_id=document_parse.id, provider=detected.extractor_provider, selected_tables=[t.model_dump(mode="json") for t in route_result.selected_tables], extraction=normalized.model_dump(mode="json"), validation_warnings=warnings, entity_resolution=entity_resolution.model_dump(mode="json"), review_draft=review_draft.model_dump(mode="json"))
```

Return `AutoIngestResult(document_id, parse_id, extraction_id, selected_tables, review_draft)`.

- [ ] **Step 4: Wire worker stages**

Modify `workers/ingest_rq.py` to report stages:

```text
received
parsing
routing
extracting
validating
resolving
review_ready
confirmed
failed
```

Store `document_id` and `extraction_id` from the new `AutoIngestResult`.

- [ ] **Step 5: Update API job envelope**

Modify `_job_dict()` and `GET /jobs/{job_id}` in `api/schema_ingest.py` to return the vNext review draft envelope from `GET /extractions/{id}/review`, not legacy `result_json`.

- [ ] **Step 6: Run orchestrator and worker tests**

Run:

```bash
cd services/platform-api
./.venv/bin/pytest tests/test_schema_ingest_vnext_auto.py tests/test_ingest_rq_worker.py tests/test_ingest_jobs.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add services/platform-api/yunwei_win/services/schema_ingest/auto.py services/platform-api/yunwei_win/workers/ingest_rq.py services/platform-api/yunwei_win/workers/ingest_rq_worker.py services/platform-api/yunwei_win/api/schema_ingest.py services/platform-api/tests/test_schema_ingest_vnext_auto.py services/platform-api/tests/test_ingest_rq_worker.py services/platform-api/tests/test_ingest_jobs.py
git commit -m "feat(win): run vnext ingest pipeline end to end"
```

## Task 10: Profile, Read API, and Assistant Visibility

**Files:**
- Create: `services/platform-api/tests/test_vnext_profile_visibility.py`
- Modify: `services/platform-api/yunwei_win/api/customer_profile/reads.py`
- Modify: `services/platform-api/yunwei_win/api/read.py`
- Modify: `services/platform-api/yunwei_win/api/customer_management.py`
- Modify: `services/platform-api/yunwei_win/assistant/context.py`
- Modify: `services/platform-api/yunwei_win/schemas/customer.py`

- [ ] **Step 1: Write visibility tests**

Add `services/platform-api/tests/test_vnext_profile_visibility.py` with assertions:

```python
async def test_customer_profile_returns_all_first_version_review_visible_tables(ac):
    seed_customer_with_contacts_contract_invoice_payment_shipment_product_journal_task()
    res = await ac.get(f"/api/win/customer-profile/{customer_id}")
    assert res.status_code == 200
    body = res.json()
    assert body["customer"]["industry"] == "制造业"
    assert body["contacts"][0]["title"] == "采购经理"
    assert body["contracts"][0]["delivery_terms"]
    assert body["invoices"][0]["invoice_no"]
    assert body["payments"][0]["amount"]
    assert body["shipments"][0]["tracking_no"]
    assert body["products"][0]["name"]
    assert body["journal_items"][0]["item_type"]
    assert body["tasks"][0]["assignee"]
    assert body["source_documents"][0]["document_id"]
```

- [ ] **Step 2: Run test and confirm expected failure**

Run:

```bash
cd services/platform-api
./.venv/bin/pytest tests/test_vnext_profile_visibility.py -q
```

Expected: FAIL because current profile/read surfaces do not expose every vNext table.

- [ ] **Step 3: Extend customer/profile schemas**

Modify `schemas/customer.py` and read helpers to include:

```text
customers.industry
customers.notes
contacts.title
contacts.phone
contacts.address
contracts.delivery_terms
contracts.penalty_terms
contract_payment_milestones
invoices
invoice_items
payments
shipments
shipment_items
products
product_requirements
customer_journal_items
customer_tasks.assignee
source_documents
```

- [ ] **Step 4: Update assistant context**

Modify `assistant/context.py` to read `customer_journal_items` and `customer_tasks` as the memory/task source. Do not read dropped legacy memory/inbox tables for vNext ingest facts.

- [ ] **Step 5: Run visibility tests**

Run:

```bash
cd services/platform-api
./.venv/bin/pytest tests/test_vnext_profile_visibility.py tests/test_yunwei_win_assistant.py tests/test_customer_management.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add services/platform-api/yunwei_win/api/customer_profile/reads.py services/platform-api/yunwei_win/api/read.py services/platform-api/yunwei_win/api/customer_management.py services/platform-api/yunwei_win/assistant/context.py services/platform-api/yunwei_win/schemas/customer.py services/platform-api/tests/test_vnext_profile_visibility.py services/platform-api/tests/test_yunwei_win_assistant.py services/platform-api/tests/test_customer_management.py
git commit -m "feat(win): expose vnext confirmed ingest facts"
```

## Task 11: Frontend Progressive Review Wizard

**Files:**
- Create: `apps/win-web/src/components/review/ReviewWizard.tsx`
- Create: `apps/win-web/src/components/review/ReviewCard.tsx`
- Create: `apps/win-web/src/components/review/ReviewDetailTable.tsx`
- Create: `apps/win-web/src/components/review/ReviewSourcePanel.tsx`
- Create: `apps/win-web/src/components/review/ReviewSummary.tsx`
- Modify: `apps/win-web/src/data/types.ts`
- Modify: `apps/win-web/src/api/ingest.ts`
- Modify: `apps/win-web/src/screens/Review.tsx`
- Modify: `apps/win-web/src/components/review/ReviewTableWorkspace.tsx`
- Modify: `apps/win-web/src/styles.css`

- [ ] **Step 1: Add frontend vNext types**

Modify `apps/win-web/src/data/types.ts` with TypeScript types matching backend:

```ts
export type ReviewStepKey =
  | "customer"
  | "contacts"
  | "commercial"
  | "finance"
  | "logistics_product"
  | "memory"
  | "summary";

export type ReviewPresentation = "card" | "table";
export type ReviewRowOperation = "create" | "update" | "link_existing" | "ignore";
export type ReviewLockMode = "edit" | "read_only";
```

Add `ReviewSourceRef`, `ReviewRowDecision`, `ReviewStep`, `AutosaveReviewRequest`, `AutosaveReviewResponse`, `AcquireReviewLockResponse`, and update `ReviewDraft`.

- [ ] **Step 2: Add API client methods**

Modify `apps/win-web/src/api/ingest.ts`:

```ts
export async function getReview(extractionId: string): Promise<ExtractionEnvelope> {
  const res = await fetch(`${API_BASE}/ingest/extractions/${extractionId}/review`, { credentials: "include", cache: "no-store" });
  return jsonOrThrow(res);
}

export async function acquireReviewLock(extractionId: string, user?: string): Promise<AcquireReviewLockResponse> {
  const res = await fetch(`${API_BASE}/ingest/extractions/${extractionId}/review/lock`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ user }),
  });
  return jsonOrThrow(res);
}

export async function autosaveReview(extractionId: string, payload: AutosaveReviewRequest): Promise<AutosaveReviewResponse> {
  const res = await fetch(`${API_BASE}/ingest/extractions/${extractionId}/review`, {
    method: "PATCH",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return jsonOrThrow(res);
}

export async function confirmReviewDraft(extractionId: string, payload: ConfirmExtractionRequest): Promise<ConfirmExtractionResponse> {
  const res = await fetch(`${API_BASE}/ingest/extractions/${extractionId}/confirm`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return jsonOrThrow(res);
}
```

Use:

```text
GET /api/win/ingest/extractions/{id}/review
POST /api/win/ingest/extractions/{id}/review/lock
PATCH /api/win/ingest/extractions/{id}/review
POST /api/win/ingest/extractions/{id}/confirm
```

- [ ] **Step 3: Implement wizard shell**

Create `ReviewWizard.tsx` with:

```text
left or top step navigation from draft.steps
single active step content
Back and Next buttons
Summary confirm button only on summary step
read-only banner when lock mode is read_only
autosave conflict banner for HTTP 409
```

Do not show instructional feature text inside the app beyond concise state labels and errors.

- [ ] **Step 4: Implement card, detail table, source panel, and summary components**

`ReviewCard.tsx` renders master rows with field labels, values, row decision selector, and candidates.

`ReviewDetailTable.tsx` renders detail rows with stable column widths and cell editors.

`ReviewSourcePanel.tsx` renders source refs as excerpts, sheet/cell IDs, and page/bbox metadata when present.

`ReviewSummary.tsx` lists creates, updates, linked rows, ignored rows, edited fields, missing required cells, and warnings.

- [ ] **Step 5: Wire `ReviewScreen`**

Modify `Review.tsx` to:

```text
load job
load review by extraction_id
acquire lock
store lock_token and review_version
autosave on cell/row/step changes
handle 409 by reloading review and switching to read-only until user reacquires lock
confirm with lock_token and base_version
```

- [ ] **Step 6: Run frontend type check**

Run:

```bash
cd apps/win-web
npm run check
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add apps/win-web/src/data/types.ts apps/win-web/src/api/ingest.ts apps/win-web/src/screens/Review.tsx apps/win-web/src/components/review/ReviewWizard.tsx apps/win-web/src/components/review/ReviewCard.tsx apps/win-web/src/components/review/ReviewDetailTable.tsx apps/win-web/src/components/review/ReviewSourcePanel.tsx apps/win-web/src/components/review/ReviewSummary.tsx apps/win-web/src/components/review/ReviewTableWorkspace.tsx apps/win-web/src/styles.css
git commit -m "feat(win): add progressive ingest review wizard"
```

## Task 12: Frontend Confirmed Fact Visibility

**Files:**
- Modify: `apps/win-web/src/data/types.ts`
- Modify: `apps/win-web/src/screens/CustomerDetail.tsx`
- Modify: `apps/win-web/src/screens/Profile.tsx`
- Modify: `apps/win-web/src/components/CustomerDetailPane.tsx`
- Modify: `apps/win-web/src/screens/Inbox.tsx`
- Modify: `apps/win-web/src/data/mock.ts`

- [ ] **Step 1: Update frontend customer/profile types**

Add first-version vNext visible entities:

```ts
Product
ProductRequirement
ContractPaymentMilestone
Invoice
InvoiceItem
Payment
Shipment
ShipmentItem
CustomerJournalItem
CustomerTask
SourceDocumentRef
```

Include `industry`, `notes`, `title`, `phone`, `address`, `delivery_terms`, `penalty_terms`, and `assignee`.

- [ ] **Step 2: Render vNext profile sections**

Modify profile/detail screens so first-version review-visible tables have a readable home. Use existing dense operational UI patterns, with small sections for:

```text
基本信息
联系人
合同 / 订单
发票 / 付款
物流 / 产品
时间线 / 待办
来源资料
```

- [ ] **Step 3: Remove mock-era ingest dependency on customer tags**

Modify `Inbox.tsx` and customer filters so `tag` is not treated as a schema-ingest field. Keep any local visual filter only if backed by existing mock data and clearly outside ingest writeback.

- [ ] **Step 4: Run frontend type check and build**

Run:

```bash
cd apps/win-web
npm run build
```

Expected: PASS with `tsc --noEmit` and Vite build success.

- [ ] **Step 5: Commit**

```bash
git add apps/win-web/src/data/types.ts apps/win-web/src/screens/CustomerDetail.tsx apps/win-web/src/screens/Profile.tsx apps/win-web/src/components/CustomerDetailPane.tsx apps/win-web/src/screens/Inbox.tsx apps/win-web/src/data/mock.ts
git commit -m "feat(win): show vnext ingest facts in customer profile"
```

## Task 13: Remove Legacy Mainline Ingest Paths and Run Full Verification

**Files:**
- Modify: `services/platform-api/yunwei_win/services/ingest/llm_schema_router.py`
- Modify: `services/platform-api/yunwei_win/services/ingest/evidence.py`
- Modify: `services/platform-api/yunwei_win/services/ingest/pipeline_schemas.py`
- Modify: `services/platform-api/yunwei_win/services/ocr/factory.py`
- Modify: `services/platform-api/yunwei_win/services/ocr/mistral.py`
- Modify: `services/platform-api/yunwei_win/services/ocr/mineru.py`
- Modify: `services/platform-api/yunwei_win/api/ingest.py`
- Modify: `services/platform-api/yunwei_win/api/ingest_v2.py`
- Modify: tests that still import removed legacy ingest contracts.

- [ ] **Step 1: Search for legacy ingest dependencies**

Run:

```bash
rg -n "mistral|mineru|ocr_text|route_plan|raw_pipeline_results|selected_pipelines|owner|needs_review|customer_events|customer_commitments|customer_risk_signals|customer_memory_items|customer_inbox_items" services/platform-api/yunwei_win services/platform-api/tests apps/win-web/src
```

Expected: output lists all remaining legacy references. Classify each as one of:

```text
delete from vNext path
keep as unrelated legacy API outside /api/win/ingest
rename to vNext contract
```

- [ ] **Step 2: Remove or isolate obsolete ingest contracts**

Remove references that still affect `/api/win/ingest` mainline:

```text
Mistral OCR provider selection for schema ingest
MinerU provider selection for schema ingest
legacy selected_pipelines route plan in vNext review draft
raw_pipeline_results as the extraction source of truth
contacts.needs_review review behavior
customer_tasks.owner
dropped memory/inbox target tables from confirm write maps
```

- [ ] **Step 3: Update tests that still assert legacy behavior**

Replace legacy tests with vNext assertions when they cover the same product surface:

```text
test_ingest_auto_flow.py -> parse/router/extract/review_ready
test_ingest_canonical_api.py -> selected_tables and review endpoint
test_ingest_v2_review_draft.py -> remove if v2 route is deleted
test_ocr_provider_factory.py -> keep only if OCR module remains outside vNext ingest
```

- [ ] **Step 4: Run backend focused verification**

Run:

```bash
cd services/platform-api
./.venv/bin/pytest tests/test_vnext_tenant_schema.py tests/test_parse_artifact.py tests/test_file_type_detection.py tests/test_parser_providers.py tests/test_table_router_vnext.py tests/test_extraction_schema_vnext.py tests/test_extraction_normalize_validate.py tests/test_entity_resolution.py tests/test_review_draft_vnext.py tests/test_review_lock_api.py tests/test_review_autosave_api.py tests/test_confirm_vnext.py tests/test_schema_ingest_vnext_auto.py tests/test_vnext_profile_visibility.py -q
```

Expected: PASS.

- [ ] **Step 5: Run backend broader verification**

Run:

```bash
cd services/platform-api
./.venv/bin/pytest tests/test_company_schema_catalog.py tests/test_ingest_jobs.py tests/test_ingest_rq_worker.py tests/test_yunwei_win_tenant_isolation.py tests/test_yunwei_win_assistant.py tests/test_customer_management.py -q
```

Expected: PASS.

- [ ] **Step 6: Run frontend verification**

Run:

```bash
cd apps/win-web
npm run build
```

Expected: PASS.

- [ ] **Step 7: Run final repository status check**

Run:

```bash
git status --short
```

Expected: only intentional modified files from the final cleanup task are listed; `docs/reference/` remains untracked unless the user explicitly asked to commit it.

- [ ] **Step 8: Commit**

```bash
git add services/platform-api/yunwei_win apps/win-web/src services/platform-api/tests services/platform-api/pyproject.toml
git commit -m "chore(win): remove legacy schema ingest paths"
```

## Final Verification

Run these commands after Task 13:

```bash
cd services/platform-api
./.venv/bin/pytest tests/test_vnext_tenant_schema.py tests/test_parse_artifact.py tests/test_file_type_detection.py tests/test_parser_providers.py tests/test_table_router_vnext.py tests/test_extraction_schema_vnext.py tests/test_extraction_normalize_validate.py tests/test_entity_resolution.py tests/test_review_draft_vnext.py tests/test_review_lock_api.py tests/test_review_autosave_api.py tests/test_confirm_vnext.py tests/test_schema_ingest_vnext_auto.py tests/test_vnext_profile_visibility.py tests/test_company_schema_catalog.py tests/test_ingest_jobs.py tests/test_ingest_rq_worker.py tests/test_yunwei_win_tenant_isolation.py tests/test_yunwei_win_assistant.py tests/test_customer_management.py -q
```

Expected: PASS.

```bash
cd apps/win-web
npm run build
```

Expected: PASS.

```bash
git log --oneline --max-count=15
```

Expected: one commit per task, in the same order as this plan.

## Implementation Notes

- Do not flatten `ParseArtifact` into `documents.ocr_text`; markdown can be copied into a review/read envelope, but the durable parse home is `document_parses.artifact`.
- Do not ask extractors for UUID FKs, source IDs, timestamps, confidence columns, or raw payload fields.
- Keep the row link contract explicit: child rows link to `client_row_id` or a selected existing entity, never to an LLM-generated UUID placeholder.
- Required system links are validated through row decisions and parent links, not through extractor output.
- Defaults do not make rows writable. A row is writable only with AI value, user edit, explicit row decision, or selected existing entity link.
- Review-visible first-version tables must have a post-confirm read/profile surface. If a table is not visible after writeback, mark it not review-visible before shipping.
- LandingAI Parse and LandingAI Extract stay paired for visual documents to preserve full grounding. Text, DOCX, and spreadsheet files use native parse artifacts and DeepSeek extraction.
