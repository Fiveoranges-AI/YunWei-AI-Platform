"""vNext schema-first auto-ingest orchestrator.

Pipeline:

    detect_source_type
      -> create Document (file/text path, sha256, size, file_url)
      -> parse via parsers.factory
      -> persist DocumentParse
      -> ensure_default_company_schema + get_company_schema
      -> route_tables
      -> extract_from_parse_artifact (provider per detected pair)
      -> validate_normalized_extraction
      -> propose_entity_resolution
      -> materialize_review_draft_vnext
      -> persist DocumentExtraction (vNext column shape)

The session is owned by the caller (the worker / API endpoint). We
``flush`` so the new Document / DocumentParse / DocumentExtraction rows
are visible inside this session, but the surrounding commit is the
caller's responsibility — matches the legacy contract.
"""

from __future__ import annotations

import hashlib
import logging
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from sqlalchemy.ext.asyncio import AsyncSession

from yunwei_win.config import settings
from yunwei_win.models.customer_memory import (
    DocumentProcessingStatus,
    InputChannel,
    InputModality,
)
from yunwei_win.models.document import Document, DocumentType
from yunwei_win.models.document_extraction import (
    DocumentExtraction,
    DocumentExtractionStatus,
)
from yunwei_win.models.document_parse import DocumentParse, DocumentParseStatus
from yunwei_win.services.company_schema import (
    ensure_default_company_schema,
    get_company_schema,
)
from yunwei_win.services.ingest.progress import ProgressCallback, emit_progress
from yunwei_win.services.schema_ingest.upload import PreStoredFile
from yunwei_win.services.schema_ingest import entity_resolution as entity_resolution_module
from yunwei_win.services.schema_ingest import extraction_validation as validation_module
from yunwei_win.services.schema_ingest import extractors as extractors_module
from yunwei_win.services.schema_ingest import table_router as router_module
from yunwei_win.services.schema_ingest.file_type import (
    DetectedSourceType,
    detect_source_type,
)
from yunwei_win.services.schema_ingest.llm_adapter import DeepSeekCompleteJsonLLM
from yunwei_win.services.schema_ingest.parse_artifact import ParseArtifact
from yunwei_win.services.schema_ingest.parsers.factory import (
    parse_file as parse_file_factory,
    parse_pasted_text,
)
from yunwei_win.services.schema_ingest.review_draft import materialize_review_draft_vnext
from yunwei_win.services.schema_ingest.schemas import ReviewDraft
from yunwei_win.services.storage import open_for_read, store_upload

logger = logging.getLogger(__name__)


@dataclass
class AutoIngestResult:
    """Bundle returned to the worker. The worker persists these onto
    the IngestJob row + uses ``review_draft`` for the API response."""

    document_id: uuid.UUID
    parse_id: uuid.UUID
    extraction_id: uuid.UUID
    selected_tables: list[dict[str, Any]] = field(default_factory=list)
    review_draft: ReviewDraft | None = None


# Map vNext source_type → legacy ``Document.type`` so existing read paths
# that branch on contract/invoice/etc still work. Anything we don't classify
# falls through to ``other``.
_SOURCE_TYPE_TO_DOCUMENT_TYPE: dict[str, DocumentType] = {
    "pdf": DocumentType.other,
    "image": DocumentType.business_card,
    "pptx": DocumentType.other,
    "text": DocumentType.text_note,
    "docx": DocumentType.other,
    "spreadsheet": DocumentType.other,
}

_SOURCE_TYPE_TO_MODALITY: dict[str, InputModality] = {
    "pdf": InputModality.image,
    "image": InputModality.image,
    "pptx": InputModality.image,
    "text": InputModality.text,
    "docx": InputModality.text,
    "spreadsheet": InputModality.text,
}


async def auto_ingest(
    *,
    session: AsyncSession,
    file_bytes: bytes | None = None,
    original_filename: str | None = None,
    content_type: str | None = None,
    text_content: str | None = None,
    source_hint: Literal["file", "camera", "pasted_text"] = "file",
    uploader: str | None = None,
    progress: ProgressCallback | None = None,
    pre_stored: PreStoredFile | None = None,
) -> AutoIngestResult:
    await emit_progress(progress, "auto", "开始 vNext schema-first 流水线")

    # --- 1. Detect physical source type --------------------------------
    detected = detect_source_type(
        filename=original_filename or (pre_stored.original_filename if pre_stored else None),
        content_type=content_type or (pre_stored.content_type if pre_stored else None),
        source_hint=source_hint,
    )

    # --- 2. Document row (with stored bytes / text payload) ------------
    document = await _persist_document(
        session=session,
        detected=detected,
        file_bytes=file_bytes,
        text_content=text_content,
        original_filename=original_filename,
        content_type=content_type,
        uploader=uploader,
        pre_stored=pre_stored,
    )

    # --- 3. Parse ------------------------------------------------------
    await emit_progress(progress, "parsing", f"使用 {detected.parser_provider} 解析")
    parse_artifact = await _run_parse(
        detected=detected,
        text_content=text_content,
        file_bytes=file_bytes,
        original_filename=original_filename,
        content_type=content_type,
        pre_stored=pre_stored,
        document=document,
    )

    parse = DocumentParse(
        document_id=document.id,
        provider=detected.parser_provider,
        model=parse_artifact.metadata.get("model") if isinstance(parse_artifact.metadata, dict) else None,
        status=DocumentParseStatus.parsed,
        artifact=parse_artifact.model_dump(mode="json"),
        raw_metadata=dict(parse_artifact.metadata or {}),
        warnings=[],
    )
    session.add(parse)
    await session.flush()

    # The same complete_json adapter powers both the table router and the
    # DeepSeek extractor — one tool round-trip per stage, all writing into
    # ``llm_calls`` against the same Document for audit.
    llm = DeepSeekCompleteJsonLLM(session=session, document_id=document.id)

    # --- 4. Catalog ----------------------------------------------------
    await ensure_default_company_schema(session)
    catalog = await get_company_schema(session)

    # --- 5. Route ------------------------------------------------------
    await emit_progress(progress, "routing", "选择目标表")
    route_result = await router_module.route_tables(
        parse_artifact=parse_artifact,
        catalog=catalog,
        llm=llm,
    )
    selected_table_names = [t.table_name for t in route_result.selected_tables]
    selected_tables_dump = [t.model_dump(mode="json") for t in route_result.selected_tables]

    # --- 6. Extract ----------------------------------------------------
    await emit_progress(
        progress, "extracting", f"使用 {detected.extractor_provider} 抽取"
    )
    extraction_warnings: list[str] = list(route_result.warnings or [])
    try:
        normalized = await extractors_module.extract_from_parse_artifact(
            parse_artifact=parse_artifact,
            selected_tables=selected_table_names,
            catalog=catalog,
            provider=detected.extractor_provider,
            session=session,
            llm=llm if detected.extractor_provider == "deepseek" else None,
        )
    except Exception as exc:  # noqa: BLE001 — degrade gracefully
        logger.exception("vNext extract failed for document %s", document.id)
        extraction_warnings.append(
            f"extraction failed: {type(exc).__name__}: {exc!s}"
        )
        from yunwei_win.services.schema_ingest.extraction_normalize import (
            NormalizedExtraction,
        )

        normalized = NormalizedExtraction(
            provider=detected.extractor_provider,
            tables={},
            metadata={"error": str(exc)},
        )

    # --- 7. Validate ---------------------------------------------------
    await emit_progress(progress, "validating", "校验抽取结果")
    extraction_warnings.extend(
        validation_module.validate_normalized_extraction(
            normalized,
            selected_tables=selected_table_names,
            catalog=catalog,
            parse_artifact=parse_artifact,
        )
    )

    # --- 8. Entity resolution -----------------------------------------
    await emit_progress(progress, "resolving", "对齐实体")
    proposal = await entity_resolution_module.propose_entity_resolution(
        session=session, extraction=normalized
    )

    # --- 9. Materialize ReviewDraft -----------------------------------
    extraction_id = uuid.uuid4()
    review_draft = materialize_review_draft_vnext(
        extraction_id=extraction_id,
        document_id=document.id,
        parse_id=parse.id,
        document_filename=document.original_filename or "",
        parse_artifact=parse_artifact,
        selected_tables=selected_table_names,
        normalized_extraction=normalized,
        entity_resolution=proposal,
        catalog=catalog,
        document_summary=route_result.document_summary,
        warnings=extraction_warnings,
    )

    # --- 10. Persist DocumentExtraction (vNext column shape) ----------
    extraction = DocumentExtraction(
        id=extraction_id,
        document_id=document.id,
        parse_id=parse.id,
        provider=detected.extractor_provider,
        model=None,
        status=DocumentExtractionStatus.pending_review,
        selected_tables=selected_tables_dump,
        extraction=normalized.model_dump(mode="json"),
        extraction_metadata=dict(normalized.metadata or {}),
        validation_warnings=extraction_warnings or None,
        entity_resolution=proposal.model_dump(mode="json"),
        review_draft=review_draft.model_dump(mode="json"),
        review_version=0,
    )
    session.add(extraction)

    document.raw_llm_response = {
        "workflow": "vnext",
        "extraction_id": str(extraction_id),
        "parse_id": str(parse.id),
        "extractor_provider": detected.extractor_provider,
        "parser_provider": detected.parser_provider,
        "selected_tables": selected_table_names,
    }
    await session.flush()

    await emit_progress(progress, "review_ready", "已生成 vNext 草稿，待人工确认")

    return AutoIngestResult(
        document_id=document.id,
        parse_id=parse.id,
        extraction_id=extraction_id,
        selected_tables=selected_tables_dump,
        review_draft=review_draft,
    )


# ---------------------------------------------------------------------------
# Document persistence
# ---------------------------------------------------------------------------


async def _persist_document(
    *,
    session: AsyncSession,
    detected: DetectedSourceType,
    file_bytes: bytes | None,
    text_content: str | None,
    original_filename: str | None,
    content_type: str | None,
    uploader: str | None,
    pre_stored: PreStoredFile | None,
) -> Document:
    """Create the Document row + (re)stage bytes so file_url / sha256 / size
    are real. Text mode encodes the text payload as UTF-8 so audit / replay
    can still find what the user typed."""

    if text_content is not None and text_content.strip():
        payload = text_content.encode("utf-8")
        filename = original_filename or "pasted.txt"
        stored = store_upload(payload, filename, default_ext=".txt")
        doc_type = DocumentType.text_note
        modality = InputModality.text
        ct = content_type or "text/plain"
    elif pre_stored is not None:
        filename = original_filename or pre_stored.original_filename or "upload.bin"
        ct = content_type or pre_stored.content_type
        sha = pre_stored.sha256
        size = pre_stored.size
        # No restage — just take the descriptor as-is.
        stored = type(pre_stored)(  # mirror StoredFile shape
            path=pre_stored.path,
            sha256=sha,
            size=size,
        )
        doc_type = _SOURCE_TYPE_TO_DOCUMENT_TYPE.get(detected.source_type, DocumentType.other)
        modality = _SOURCE_TYPE_TO_MODALITY.get(detected.source_type, InputModality.other)
    elif file_bytes is not None and len(file_bytes) > 0:
        filename = original_filename or f"upload.{detected.source_type}"
        stored = store_upload(file_bytes, filename)
        doc_type = _SOURCE_TYPE_TO_DOCUMENT_TYPE.get(detected.source_type, DocumentType.other)
        modality = _SOURCE_TYPE_TO_MODALITY.get(detected.source_type, InputModality.other)
        ct = content_type
    else:
        raise ValueError(
            "auto_ingest needs one of text_content / file_bytes / pre_stored"
        )

    document = Document(
        type=doc_type,
        file_url=stored.path,
        original_filename=filename,
        content_type=ct,
        file_sha256=stored.sha256 or hashlib.sha256(b"").hexdigest(),
        file_size_bytes=stored.size or 0,
        uploader=uploader,
        processing_status=DocumentProcessingStatus.parsed,
        input_channel=InputChannel.web_upload,
        input_modality=modality,
        ocr_text=text_content if text_content is not None else None,
    )
    session.add(document)
    await session.flush()
    return document


# ---------------------------------------------------------------------------
# Parse dispatch
# ---------------------------------------------------------------------------


async def _run_parse(
    *,
    detected: DetectedSourceType,
    text_content: str | None,
    file_bytes: bytes | None,
    original_filename: str | None,
    content_type: str | None,
    pre_stored: PreStoredFile | None,
    document: Document,
) -> ParseArtifact:
    """Route the input to the correct parser provider."""

    if detected.parser_provider == "text":
        text = text_content if text_content is not None else ""
        return await parse_pasted_text(
            text=text, filename=original_filename or "pasted.txt"
        )

    # File-based parsers need a real path on disk. Prefer pre_stored, otherwise
    # write a tmp file from file_bytes.
    if pre_stored is not None:
        path = Path(pre_stored.path.replace("file://", ""))
    elif document.file_url and not document.file_url.startswith("s3://"):
        path = Path(document.file_url.replace("file://", ""))
    else:
        # Last-resort: write bytes to a tmp path so the parser can read.
        import tempfile

        suffix = "." + detected.source_type
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as fh:
            if file_bytes is None:
                file_bytes = open_for_read(document.file_url)
            fh.write(file_bytes)
            path = Path(fh.name)

    return await parse_file_factory(
        detected=detected,
        path=path,
        filename=original_filename or document.original_filename,
        content_type=content_type or document.content_type,
    )
