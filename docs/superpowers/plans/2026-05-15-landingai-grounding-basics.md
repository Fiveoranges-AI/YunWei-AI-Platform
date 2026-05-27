# LandingAI Grounding Basics Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make LandingAI parse/extract grounding usable by the review flow: real SDK chunks preserve text/page/bbox, LandingAI extraction references become rich `source_refs`, and confirmed provenance keeps page/source metadata.

**Architecture:** Keep this backend-only. Normalize LandingAI SDK objects at the parser/extractor adapter boundary, then let existing `NormalizedExtraction -> ReviewDraft -> Confirm` plumbing carry the richer refs. Do not build PDF/image highlight UI in this plan.

**Tech Stack:** Python 3.14, Pydantic v2, SQLAlchemy async, LandingAI ADE SDK, pytest.

---

## File Structure

- Modify `services/platform-api/yunwei_win/services/schema_ingest/parsers/landingai.py`
  - Responsibility: convert LandingAI ADE parse responses into project `ParseArtifact`.
  - Add SDK-aware normalization for `Chunk.markdown`, `Chunk.grounding.page`, `Chunk.grounding.box`, `Split`, and `grounding`.
- Modify `services/platform-api/yunwei_win/services/schema_ingest/extractors.py`
  - Responsibility: convert LandingAI `extraction_metadata` references into `NormalizedFieldValue.source_refs`.
  - Preserve `references` and `chunk_references`, and enrich refs with page, bbox, excerpt, table_id, row, and col when available.
- Modify `services/platform-api/yunwei_win/services/schema_ingest/confirm.py`
  - Responsibility: persist final field provenance.
  - Derive top-level `FieldProvenance.source_page` from `source_refs`.
- Modify tests:
  - `services/platform-api/tests/test_parser_providers.py`
  - `services/platform-api/tests/test_extraction_normalize_validate.py`
  - `services/platform-api/tests/test_review_draft_vnext.py`
  - `services/platform-api/tests/test_confirm_vnext.py`
  - Optionally `services/platform-api/tests/test_schema_ingest_vnext_auto.py`

Non-goals:
- Do not implement a frontend PDF/image bbox highlighter.
- Do not reintroduce legacy schema ingest paths.
- Do not change the parser/extractor provider matrix.
- Do not remove existing user/uncommitted changes.

---

### Task 1: Normalize LandingAI SDK Parse Chunks And Splits

**Files:**
- Modify: `services/platform-api/yunwei_win/services/schema_ingest/parsers/landingai.py`
- Test: `services/platform-api/tests/test_parser_providers.py`

- [ ] **Step 1: Write the failing parser test**

Append this test to `services/platform-api/tests/test_parser_providers.py`:

```python
@pytest.mark.asyncio
async def test_landingai_parser_normalizes_sdk_chunk_markdown_grounding_and_splits(
    monkeypatch, tmp_path
):
    from landingai_ade.types.parse_response import Chunk, ChunkGrounding, Split
    from landingai_ade.types.shared.parse_grounding_box import ParseGroundingBox

    async def fake_parse(path: Path):
        return SimpleNamespace(
            markdown="# Parsed\n\n客户：测试有限公司",
            chunks=[
                Chunk(
                    id="0-a",
                    type="text",
                    markdown="客户：测试有限公司",
                    grounding=ChunkGrounding(
                        page=0,
                        box=ParseGroundingBox(left=1, top=2, right=3, bottom=4),
                    ),
                )
            ],
            splits=[
                Split(
                    chunks=["0-a"],
                    identifier="page-0",
                    markdown="客户：测试有限公司",
                    pages=[0],
                    **{"class": "page"},
                )
            ],
            grounding={
                "0-a": {
                    "page": 0,
                    "type": "chunkText",
                    "box": {"left": 1, "top": 2, "right": 3, "bottom": 4},
                }
            },
            metadata={"page_count": 1},
        )

    monkeypatch.setattr(
        "yunwei_win.services.schema_ingest.parsers.landingai.parse_file_to_markdown",
        fake_parse,
    )
    path = tmp_path / "contract.pdf"
    path.write_bytes(b"%PDF")

    artifact = await LandingAIParser().parse_file(
        path,
        filename="contract.pdf",
        content_type="application/pdf",
        source_type="pdf",
    )

    assert artifact.provider == "landingai"
    assert artifact.chunks[0].id == "0-a"
    assert artifact.chunks[0].text == "客户：测试有限公司"
    assert artifact.chunks[0].page == 0
    assert artifact.chunks[0].bbox == [1.0, 2.0, 3.0, 4.0]
    assert artifact.pages[0]["id"] == "page:0"
    assert artifact.pages[0]["page_number"] == 0
    assert artifact.pages[0]["chunks"] == ["0-a"]
    assert artifact.pages[0]["identifier"] == "page-0"
    assert artifact.grounding["0-a"]["box"]["left"] == 1
```

- [ ] **Step 2: Run the parser test and verify RED**

Run:

```bash
cd services/platform-api
./.venv/bin/pytest tests/test_parser_providers.py::test_landingai_parser_normalizes_sdk_chunk_markdown_grounding_and_splits -q
```

Expected before implementation:

```text
FAILED ... assert '' == '客户：测试有限公司'
```

or failure showing `page`, `bbox`, or `pages[0]["id"]` is missing.

- [ ] **Step 3: Implement SDK-aware normalization**

In `services/platform-api/yunwei_win/services/schema_ingest/parsers/landingai.py`, replace `_normalize_chunk` and `_normalize_page`, and add helper functions below them:

```python
def _normalize_chunk(raw: Any) -> ParseChunk:
    if isinstance(raw, ParseChunk):
        return raw
    data = _object_to_dict(raw)
    grounding = _object_to_dict(data.get("grounding"))
    return ParseChunk(
        id=str(data.get("id") or ""),
        type=str(data.get("type") or "text"),
        text=str(data.get("markdown") or data.get("text") or ""),
        page=_coerce_int(data.get("page") if data.get("page") is not None else grounding.get("page")),
        bbox=_coerce_box(data.get("bbox")) or _coerce_box(grounding.get("box")),
    )


def _normalize_page(raw: Any) -> dict[str, Any]:
    data = _object_to_dict(raw)
    if not data:
        return {}
    pages = data.get("pages")
    first_page = None
    if isinstance(pages, list) and pages:
        first_page = _coerce_int(pages[0])
    page_number = _coerce_int(data.get("page_number"))
    if page_number is None:
        page_number = first_page
    page_id = data.get("id")
    if not page_id and page_number is not None:
        page_id = f"page:{page_number}"
    out = dict(data)
    out["id"] = page_id
    out["page_number"] = page_number
    return out


def _normalize_grounding(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        return {}
    return {str(k): _object_to_dict(v) for k, v in raw.items()}


def _object_to_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return {
            str(k): _jsonable(v)
            for k, v in value.items()
            if v is not None
        }
    if hasattr(value, "model_dump"):
        data = value.model_dump(mode="json")
        if isinstance(data, dict):
            return {str(k): _jsonable(v) for k, v in data.items() if v is not None}
    return {}


def _jsonable(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, list):
        return [_jsonable(v) for v in value]
    if isinstance(value, tuple):
        return [_jsonable(v) for v in value]
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if hasattr(value, "model_dump"):
        return _jsonable(value.model_dump(mode="json"))
    return value


def _coerce_box(value: Any) -> list[float] | None:
    if isinstance(value, list) and len(value) == 4:
        try:
            return [float(v) for v in value]
        except (TypeError, ValueError):
            return None
    box = _object_to_dict(value)
    if not box:
        return None
    try:
        return [
            float(box["left"]),
            float(box["top"]),
            float(box["right"]),
            float(box["bottom"]),
        ]
    except (KeyError, TypeError, ValueError):
        return None


def _coerce_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
```

Update `parse_file()` to use normalized grounding:

```python
grounding = _normalize_grounding(result.grounding or {})
metadata = _object_to_dict(result.metadata or {})
```

- [ ] **Step 4: Run the parser tests and verify GREEN**

Run:

```bash
cd services/platform-api
./.venv/bin/pytest tests/test_parser_providers.py tests/test_parse_artifact.py -q
```

Expected:

```text
passed
```

- [ ] **Step 5: Commit Task 1**

Run:

```bash
git add services/platform-api/yunwei_win/services/schema_ingest/parsers/landingai.py services/platform-api/tests/test_parser_providers.py
git commit -m "fix(win): normalize landingai parse grounding"
```

---

### Task 2: Enrich LandingAI Extraction References With Visual Fields

**Files:**
- Modify: `services/platform-api/yunwei_win/services/schema_ingest/extractors.py`
- Test: `services/platform-api/tests/test_extraction_normalize_validate.py`

- [ ] **Step 1: Write the failing visual source ref test**

In `services/platform-api/tests/test_extraction_normalize_validate.py`, extend the existing LandingAI reference test or add this new one:

```python
@pytest.mark.asyncio
async def test_extract_from_parse_artifact_maps_landingai_references_to_visual_source_ref_fields(
    monkeypatch,
):
    async def fake_extract_with_schema(*, schema_json: str, markdown: str):
        return SimpleNamespace(
            extraction={"product_requirements": [{"requirement_text": "表面粗糙度 <= Ra1.6"}]},
            extraction_metadata={
                "product_requirements[0].requirement_text": {
                    "references": ["0-a"],
                }
            },
            metadata={},
        )

    artifact = ParseArtifact(
        version=1,
        provider="landingai",
        source_type="pdf",
        markdown="|要求|\n|表面粗糙度 <= Ra1.6|",
        chunks=[
            ParseChunk(
                id="0-a",
                type="table_cell",
                text="表面粗糙度 <= Ra1.6",
                page=0,
                bbox=[1.0, 2.0, 3.0, 4.0],
            )
        ],
        grounding={
            "0-a": {
                "type": "tableCell",
                "page": 0,
                "box": {"left": 1, "top": 2, "right": 3, "bottom": 4},
                "position": {
                    "chunk_id": "table-0",
                    "row": 2,
                    "col": 1,
                    "rowspan": 1,
                    "colspan": 1,
                },
            }
        },
        capabilities=ParseCapabilities(chunks=True, visual_grounding=True, table_cells=True),
    )

    monkeypatch.setattr(
        extractors_module, "extract_with_schema", fake_extract_with_schema
    )

    result = await extract_from_parse_artifact(
        parse_artifact=artifact,
        selected_tables=["product_requirements"],
        catalog=_catalog_with_product_requirements(),
        provider="landingai",
    )

    ref = result.tables["product_requirements"][0].fields["requirement_text"].source_refs[0]
    assert ref.ref_id == "0-a"
    assert ref.ref_type == "table_cell"
    assert ref.page == 0
    assert ref.bbox == [1.0, 2.0, 3.0, 4.0]
    assert ref.excerpt == "表面粗糙度 <= Ra1.6"
    assert ref.table_id == "table-0"
    assert ref.row == 2
    assert ref.col == 1
```

Add this helper near `_catalog()`:

```python
def _catalog_with_product_requirements() -> dict:
    catalog = _catalog()
    catalog["tables"].append(
        {
            "table_name": "product_requirements",
            "label": "产品要求",
            "is_active": True,
            "is_array": True,
            "fields": [
                {
                    "field_name": "requirement_text",
                    "label": "要求内容",
                    "data_type": "text",
                    "field_role": "extractable",
                    "review_visible": True,
                    "is_active": True,
                }
            ],
        }
    )
    return catalog
```

- [ ] **Step 2: Run the extractor test and verify RED**

Run:

```bash
cd services/platform-api
./.venv/bin/pytest tests/test_extraction_normalize_validate.py::test_extract_from_parse_artifact_maps_landingai_references_to_visual_source_ref_fields -q
```

Expected before implementation:

```text
FAILED
```

The failure should show missing `source_refs`, missing `bbox`, missing `row/col`, or missing `excerpt`.

- [ ] **Step 3: Implement minimal enrichment**

In `services/platform-api/yunwei_win/services/schema_ingest/extractors.py`, make sure `_enrich_with_landingai_metadata` supports both current ADE docs and legacy examples:

```python
def _landingai_references(meta: dict[str, Any]) -> list[str]:
    raw_refs = meta.get("references")
    if raw_refs is None:
        raw_refs = meta.get("chunk_references")
    if not isinstance(raw_refs, list):
        return []
    return [ref for ref in raw_refs if isinstance(ref, str) and ref]
```

Make sure `_landingai_source_ref()` derives all visual fields:

```python
def _landingai_source_ref(
    ref_id: str,
    *,
    parse_artifact: ParseArtifact,
) -> ParseSourceRef:
    grounding = (parse_artifact.grounding or {}).get(ref_id)
    grounding_data = _object_to_dict(grounding)
    chunk = next((c for c in parse_artifact.chunks or [] if c.id == ref_id), None)

    ref_type = "chunk"
    grounding_type = grounding_data.get("type")
    if grounding_type in {"table", "tableCell"}:
        ref_type = "table_cell"

    position = _object_to_dict(grounding_data.get("position"))
    return ParseSourceRef(
        ref_type=ref_type,
        ref_id=ref_id,
        page=_coerce_int(
            grounding_data.get("page") if grounding_data else getattr(chunk, "page", None)
        ),
        bbox=_coerce_box(grounding_data.get("box")) or getattr(chunk, "bbox", None),
        excerpt=getattr(chunk, "text", None) or None,
        table_id=position.get("chunk_id") if position else None,
        row=_coerce_int(position.get("row")) if position else None,
        col=_coerce_int(position.get("col")) if position else None,
    )
```

If this code already exists in the working tree, only adjust it to satisfy the richer test. Do not duplicate helper functions.

- [ ] **Step 4: Run extractor tests and verify GREEN**

Run:

```bash
cd services/platform-api
./.venv/bin/pytest tests/test_extraction_normalize_validate.py -q
```

Expected:

```text
passed
```

- [ ] **Step 5: Commit Task 2**

Run:

```bash
git add services/platform-api/yunwei_win/services/schema_ingest/extractors.py services/platform-api/tests/test_extraction_normalize_validate.py
git commit -m "fix(win): map landingai extraction references to source refs"
```

---

### Task 3: Preserve Visual Source Refs Through Review Draft And Provenance

**Files:**
- Modify: `services/platform-api/yunwei_win/services/schema_ingest/confirm.py`
- Test: `services/platform-api/tests/test_review_draft_vnext.py`
- Test: `services/platform-api/tests/test_confirm_vnext.py`

- [ ] **Step 1: Add review draft preservation test**

In `services/platform-api/tests/test_review_draft_vnext.py`, add a focused assertion that a full LandingAI `ParseSourceRef` survives materialization:

```python
def test_review_draft_preserves_landingai_visual_source_ref_fields():
    ref = ParseSourceRef(
        ref_type="table_cell",
        ref_id="0-a",
        page=0,
        bbox=[1.0, 2.0, 3.0, 4.0],
        excerpt="表面粗糙度 <= Ra1.6",
        table_id="table-0",
        row=2,
        col=1,
    )
    normalized = NormalizedExtraction(
        provider="landingai",
        tables={
            "product_requirements": [
                NormalizedRow(
                    client_row_id="product_requirements:0",
                    fields={
                        "requirement_text": NormalizedFieldValue(
                            value="表面粗糙度 <= Ra1.6",
                            confidence=0.95,
                            source_refs=[ref],
                        )
                    },
                )
            ]
        },
    )

    draft = materialize_review_draft_vnext(
        extraction_id=uuid4(),
        document_id=uuid4(),
        parse_id=uuid4(),
        document_filename="spec.pdf",
        parse_artifact=ParseArtifact(provider="landingai", source_type="pdf", markdown=""),
        selected_tables=["product_requirements"],
        normalized_extraction=normalized,
        entity_resolution=EntityResolutionProposal(rows=[]),
        catalog=_catalog_from_default(),
        document_summary=None,
        warnings=[],
    )

    cell = draft.tables[0].rows[0].cells[0]
    assert cell.source_refs[0].ref_id == "0-a"
    assert cell.source_refs[0].page == 0
    assert cell.source_refs[0].bbox == [1.0, 2.0, 3.0, 4.0]
    assert cell.source_refs[0].excerpt == "表面粗糙度 <= Ra1.6"
    assert cell.source_refs[0].table_id == "table-0"
    assert cell.source_refs[0].row == 2
    assert cell.source_refs[0].col == 1
```

If the existing test helper names differ, use the local helper that builds the default catalog. Do not add a second catalog builder if one already exists.

- [ ] **Step 2: Add confirm provenance page test**

In `services/platform-api/tests/test_confirm_vnext.py`, extend the existing provenance test or add a new one that confirms `source_page` is populated from `source_refs`:

```python
async def test_confirm_derives_source_page_from_landingai_source_refs(...):
    # Use the existing confirm test fixture/helper style in this file.
    # Build a review draft cell with:
    source_refs = [
        {
            "ref_type": "table_cell",
            "ref_id": "0-a",
            "page": 0,
            "bbox": [1.0, 2.0, 3.0, 4.0],
            "excerpt": "测试有限公司",
            "table_id": "table-0",
            "row": 2,
            "col": 1,
        }
    ]

    # After confirm, load FieldProvenance for that field and assert:
    assert row.source_page == 0
    assert row.source_refs[0]["ref_id"] == "0-a"
    assert row.source_refs[0]["bbox"] == [1.0, 2.0, 3.0, 4.0]
```

Use the existing fixture helpers in `test_confirm_vnext.py` for tenant session, document, extraction, lock token, and confirm request. Keep this test narrow: one field, one source ref, one provenance row.

- [ ] **Step 3: Run tests and verify RED**

Run:

```bash
cd services/platform-api
./.venv/bin/pytest tests/test_review_draft_vnext.py::test_review_draft_preserves_landingai_visual_source_ref_fields tests/test_confirm_vnext.py -q
```

Expected before implementation:

```text
FAILED
```

The likely failure is `source_page is None` in the confirm provenance test.

- [ ] **Step 4: Implement provenance source page derivation**

In `services/platform-api/yunwei_win/services/schema_ingest/confirm.py`, change `_write_provenance()` payload from:

```python
"source_page": None,
```

to:

```python
"source_page": _first_page(source_refs),
```

Add this helper near `_first_excerpt()`:

```python
def _first_page(source_refs: list[Any]) -> int | None:
    for ref in source_refs:
        if not isinstance(ref, dict):
            continue
        page = ref.get("page")
        if page is None:
            continue
        try:
            return int(page)
        except (TypeError, ValueError):
            continue
    return None
```

- [ ] **Step 5: Run review/provenance tests and verify GREEN**

Run:

```bash
cd services/platform-api
./.venv/bin/pytest tests/test_review_draft_vnext.py tests/test_confirm_vnext.py -q
```

Expected:

```text
passed
```

- [ ] **Step 6: Commit Task 3**

Run:

```bash
git add services/platform-api/yunwei_win/services/schema_ingest/confirm.py services/platform-api/tests/test_review_draft_vnext.py services/platform-api/tests/test_confirm_vnext.py
git commit -m "fix(win): preserve landingai source pages in provenance"
```

---

### Task 4: Add End-To-End Backend Regression For LandingAI Review Source Refs

**Files:**
- Test: `services/platform-api/tests/test_schema_ingest_vnext_auto.py`

- [ ] **Step 1: Add auto ingest regression test**

Add a test that lets `auto_ingest()` run the real LandingAI extractor dispatch while monkeypatching only the external LandingAI client calls.

```python
@pytest.mark.asyncio
async def test_auto_ingest_persists_landingai_review_source_refs(monkeypatch, tenant_session):
    async def fake_parse_file_to_markdown(path):
        return SimpleNamespace(
            markdown="|要求|\n|表面粗糙度 <= Ra1.6|",
            chunks=[
                {
                    "id": "0-a",
                    "type": "table_cell",
                    "markdown": "表面粗糙度 <= Ra1.6",
                    "grounding": {
                        "page": 0,
                        "box": {"left": 1, "top": 2, "right": 3, "bottom": 4},
                    },
                }
            ],
            splits=[],
            grounding={
                "0-a": {
                    "type": "tableCell",
                    "page": 0,
                    "box": {"left": 1, "top": 2, "right": 3, "bottom": 4},
                    "position": {"chunk_id": "table-0", "row": 2, "col": 1},
                }
            },
            metadata={"page_count": 1},
        )

    async def fake_extract_with_schema(*, schema_json: str, markdown: str):
        return SimpleNamespace(
            extraction={
                "product_requirements": [
                    {"requirement_text": "表面粗糙度 <= Ra1.6"}
                ]
            },
            extraction_metadata={
                "product_requirements[0].requirement_text": {
                    "references": ["0-a"]
                }
            },
            metadata={"duration_ms": 10},
        )

    async def fake_route_tables(*, parse_artifact, catalog, llm):
        from yunwei_win.services.schema_ingest.table_router import SelectedTable, TableRouteResult

        return TableRouteResult(
            selected_tables=[
                SelectedTable(table_name="product_requirements", confidence=0.9, reason="test")
            ],
            rejected_tables=[],
            document_summary="test",
            needs_human_attention=False,
            warnings=[],
        )

    monkeypatch.setattr(
        "yunwei_win.services.schema_ingest.parsers.landingai.parse_file_to_markdown",
        fake_parse_file_to_markdown,
    )
    monkeypatch.setattr(
        "yunwei_win.services.schema_ingest.extractors.extract_with_schema",
        fake_extract_with_schema,
    )
    monkeypatch.setattr(
        "yunwei_win.services.schema_ingest.auto.router_module.route_tables",
        fake_route_tables,
    )

    result = await auto_ingest(
        session=tenant_session,
        file_bytes=b"%PDF",
        original_filename="requirements.pdf",
        content_type="application/pdf",
    )

    table = next(t for t in result.review_draft.tables if t.table_name == "product_requirements")
    cell = table.rows[0].cells[0]
    assert cell.field_name == "requirement_text"
    assert cell.source_refs[0].ref_id == "0-a"
    assert cell.source_refs[0].page == 0
    assert cell.source_refs[0].bbox == [1.0, 2.0, 3.0, 4.0]
    assert cell.source_refs[0].excerpt == "表面粗糙度 <= Ra1.6"
```

Adapt fixture names to the existing file. Keep the monkeypatch paths exact.

- [ ] **Step 2: Run test and verify GREEN**

Run:

```bash
cd services/platform-api
./.venv/bin/pytest tests/test_schema_ingest_vnext_auto.py::test_auto_ingest_persists_landingai_review_source_refs -q
```

Expected:

```text
passed
```

- [ ] **Step 3: Run focused backend suite**

Run:

```bash
cd services/platform-api
./.venv/bin/pytest tests/test_parser_providers.py tests/test_extraction_normalize_validate.py tests/test_review_draft_vnext.py tests/test_confirm_vnext.py tests/test_schema_ingest_vnext_auto.py -q
```

Expected:

```text
passed
```

- [ ] **Step 4: Commit Task 4**

Run:

```bash
git add services/platform-api/tests/test_schema_ingest_vnext_auto.py
git commit -m "test(win): cover landingai grounding through review draft"
```

---

## Self-Review Checklist

- Spec coverage:
  - Parser SDK chunk `markdown/grounding` covered by Task 1.
  - Split/page preservation covered by Task 1.
  - Extract `references` to `source_refs` covered by Task 2.
  - Review/provenance persistence covered by Task 3.
  - End-to-end backend regression covered by Task 4.
- Placeholder scan:
  - No `TBD`, no generic "write tests", no unspecified implementation steps.
- Type consistency:
  - `ParseChunk`, `ParseSourceRef`, `NormalizedExtraction`, `ReviewCell.source_refs`, and `FieldProvenance.source_page` names match current code.

## Final Verification

After all tasks:

```bash
cd services/platform-api
./.venv/bin/pytest tests/test_parser_providers.py tests/test_extraction_normalize_validate.py tests/test_review_draft_vnext.py tests/test_confirm_vnext.py tests/test_schema_ingest_vnext_auto.py -q
```

Expected:

```text
passed
```

Also check working tree:

```bash
git status --short
```

Expected:

```text
clean except for intentionally untracked docs/reference/landingai_lib_py.md if it is still meant to stay uncommitted
```
