"""Round 5: 真实文档上传 → parse_pipeline → 候选 JSON (synchronous endpoint).

Mounted at /api/win/parse/upload. multipart/form-data:
  - file: 必需,.jpg/.jpeg/.png/.pdf/.xlsx/.xls/.csv,≤ 20 MB
  - source_type (可选): 不传则按 mime/ext 推断

Routing by ext:
  .xlsx .xls .csv         → excel  (deterministic SpreadsheetParser,no provider needed)
  .pdf                    → contract (provider needed)
  .jpg .jpeg .png         → wechat_screenshot (provider needed for vision)

Provider 选择:
  - 如果 settings.anthropic_api_key 存在 → ClaudeProvider
  - 否则 → DemoMockProvider (deterministic from filename hash + size). 警告写到
    response.warnings 和 ActionLog 让客户/审计透明.

文件落 uploads/jintai/{enterprise_id}/{checksum}.{ext},checksum 是 sha256[:16].
重复上传同文件不会覆盖也不会重写.

返回 CandidateJSON 形状的 dict (entities + relationships + warnings + 元数据),
前端直接拿来渲染字段+置信度卡片 → 编辑 → 调 /confirm/entities 落库.

ActionLog 一条: input_summary="action=parse_upload filename=... provider=... entities=...",
actor_kind=user, target_entity_type=other.
"""

from __future__ import annotations

import hashlib
import logging
import os
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from yunwei_win.db import ensure_schema_ingest_tables_for, get_session
from yunwei_win.models import ActionLog, ActionTargetType, NextActionType
from yunwei_win.services.parse_pipeline import (
    CandidateEntity,
    CandidateJSON,
    ExtractionPayload,
    ExtractionProvider,
    FieldCandidate,
    SourceSpan,
    parse_to_candidates,
)
from yunwei_win.services.parse_pipeline.candidate import SourceInfo
from yunwei_win.services.parse_pipeline.providers.demo import DemoMockProvider


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/parse")


MAX_FILE_BYTES = 20 * 1024 * 1024  # 20 MB

# mime → source_type. 接受 ext 兜底 (浏览器 mime 不可靠).
_EXT_TO_SOURCE_TYPE: dict[str, str] = {
    ".xlsx": "excel",
    ".xls": "excel",
    ".csv": "excel",
    ".pdf": "contract",
    ".jpg": "wechat_screenshot",
    ".jpeg": "wechat_screenshot",
    ".png": "wechat_screenshot",
}

UPLOAD_ROOT = Path(os.environ.get("JINTAI_UPLOAD_ROOT", "uploads/jintai"))

# Canonical on-disk ext per source_type — never trust the client-provided
# filename ext when picking the disk filename, otherwise an attacker can
# stage `evil.php` (with a benign content-type) and land it at
# `uploads/jintai/<tenant>/<sha>.php`. Round 9 self-audit P0-2.
_DISK_EXT_BY_SOURCE_TYPE: dict[str, str] = {
    "excel": ".xlsx",
    "contract": ".pdf",
    "wechat_screenshot": ".jpg",
}

# Allowed exts when the filename's ext IS recognized — preserve it to keep
# variant-specific bytes (.xls vs .xlsx, .png vs .jpg) round-trippable.
_ALLOWED_DISK_EXTS: set[str] = set(_EXT_TO_SOURCE_TYPE.keys())


def _safe_tenant_segment(tenant_id: str) -> str:
    """Return a path-safe tenant directory name.

    `tenant_id` reaches us via ``request.state.enterprise_id`` (server-set
    after auth, never user-controlled) — but defense in depth: refuse anything
    that could escape ``UPLOAD_ROOT`` if upstream ever passes through a bad
    value. Mirrors ``yunwei_win.db._tenant_db_name`` sanitisation.
    """
    if not tenant_id:
        return "default"
    safe = "".join(c if c.isalnum() or c in ("_", "-") else "_" for c in tenant_id)
    return safe or "default"


def _safe_disk_ext(filename: str, source_type: str) -> str:
    """Return the on-disk ext to use for the persisted file.

    Prefer the filename's ext when it is in the allow-list; otherwise fall
    back to the canonical ext for the resolved source_type. Never echoes
    arbitrary client-supplied ext to disk (`.php`, `.sh`, `.html`, ...).
    """
    candidate = Path(filename or "blob").suffix.lower()
    if candidate in _ALLOWED_DISK_EXTS:
        return candidate
    return _DISK_EXT_BY_SOURCE_TYPE.get(source_type, ".bin")


def _actor_from_request(request: Request) -> str:
    actor = getattr(request.state, "actor", None)
    if isinstance(actor, str) and actor:
        return actor
    user = getattr(request.state, "user", None)
    if isinstance(user, dict):
        for key in ("id", "username", "display_name"):
            val = user.get(key)
            if isinstance(val, str) and val:
                return val
    return "unknown"


def _tenant_id_from_request(request: Request) -> str:
    tid = getattr(request.state, "enterprise_id", None)
    if not tid:
        # 不直接 401 — 让 demo 在 dev_jintai_backend 注入 tenant
        return "default"
    return tid


def _infer_source_type(filename: str, content_type: str | None) -> str:
    ext = Path(filename).suffix.lower()
    if ext in _EXT_TO_SOURCE_TYPE:
        return _EXT_TO_SOURCE_TYPE[ext]
    # mime 兜底
    if content_type:
        ct = content_type.lower()
        if "spreadsheet" in ct or "excel" in ct or "csv" in ct:
            return "excel"
        if "pdf" in ct:
            return "contract"
        if "image/" in ct:
            return "wechat_screenshot"
    raise HTTPException(
        status_code=400,
        detail=(
            f"无法识别文件类型 (filename={filename!r}, content_type={content_type!r}). "
            f"支持: .xlsx/.xls/.csv/.pdf/.jpg/.jpeg/.png"
        ),
    )


def _resolve_provider() -> tuple[ExtractionProvider, str]:
    """Pick a real provider if ANTHROPIC_API_KEY exists, else DemoMockProvider."""
    key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if key:
        # 用现有 ClaudeProvider — 注意它依赖 services.llm 的 call_claude
        try:
            from yunwei_win.services.parse_pipeline.providers.claude import ClaudeProvider
            return ClaudeProvider(), "claude"
        except Exception as e:
            logger.warning("ClaudeProvider init failed, fallback to demo-mock: %s", e)
    return DemoMockProvider(), "demo-mock"


async def _save_upload(
    file: UploadFile, tenant_id: str, source_type: str,
) -> tuple[Path, str, int]:
    """Stream upload to disk, return (path, sha256-checksum[:16], size_bytes).

    Enforces MAX_FILE_BYTES; raises 413 if exceeded. Filename ext is
    constrained to the allow-list — see ``_safe_disk_ext``.
    """
    tenant_dir = UPLOAD_ROOT / _safe_tenant_segment(tenant_id)
    tenant_dir.mkdir(parents=True, exist_ok=True)
    ext = _safe_disk_ext(file.filename or "blob", source_type)

    # Stream to tmp then rename to checksum-named final path
    tmp_path = tenant_dir / f".upload-{uuid4().hex}{ext}"
    h = hashlib.sha256()
    total = 0
    try:
        with open(tmp_path, "wb") as out:
            while True:
                chunk = await file.read(64 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > MAX_FILE_BYTES:
                    raise HTTPException(
                        status_code=413,
                        detail=f"file too large ({total} > {MAX_FILE_BYTES} bytes)",
                    )
                h.update(chunk)
                out.write(chunk)
    except HTTPException:
        tmp_path.unlink(missing_ok=True)
        raise
    checksum = h.hexdigest()[:16]
    final_path = tenant_dir / f"{checksum}{ext}"
    if final_path.exists():
        # Already uploaded earlier — keep original, discard tmp
        tmp_path.unlink(missing_ok=True)
    else:
        tmp_path.rename(final_path)
    return final_path, checksum, total


def _candidate_to_dict(candidate: CandidateJSON) -> dict[str, Any]:
    """Convert CandidateJSON (BaseModel) to dict, model_dump compatible."""
    if hasattr(candidate, "model_dump"):
        return candidate.model_dump(mode="json")
    return candidate.dict()  # type: ignore[attr-defined]


async def _run_demo_provider(
    provider: ExtractionProvider,
    *,
    source_type: str,
    filename: str,
    file_ref: str,
    uploaded_by: str,
) -> CandidateJSON:
    """Bypass adapters: call provider directly + wrap into CandidateJSON.

    Used when ANTHROPIC_API_KEY is missing — adapters for pdf/img would fail
    (need real LLM); adapter for xlsx would produce customer ontology entities
    that don't connect to round 4 主线 (IssueVoucher).
    """
    payload = ExtractionPayload(
        source_type=source_type, filename=filename, markdown="",
    )
    pr = await provider.extract(payload)
    # Map ProviderEntity → CandidateEntity. ProviderField has source_excerpt /
    # source_ref_id flat fields; CandidateField uses nested SourceSpan.
    cand_entities: list[CandidateEntity] = []
    for pe in pr.entities:
        fields: list[FieldCandidate] = []
        for f in pe.fields:
            fields.append(FieldCandidate(
                name=f.name, value=f.value, confidence=f.confidence or 0.0,
                source_span=SourceSpan(
                    text=f.source_excerpt, cell=f.source_ref_id,
                    page=f.source_page,
                ),
            ))
        cand_entities.append(CandidateEntity(
            entity_type=pe.entity_type,  # type: ignore[arg-type]
            temp_id=pe.temp_id, fields=fields,
        ))
    overall = (
        sum(f.confidence for e in cand_entities for f in e.fields)
        / max(1, sum(len(e.fields) for e in cand_entities))
    )
    return CandidateJSON(
        source=SourceInfo(
            type=source_type,  # type: ignore[arg-type]
            file_ref=file_ref,
            uploaded_by=uploaded_by,
        ),
        entities=cand_entities,
        relationships=[],
        overall_confidence=round(overall, 3),
        warnings=pr.warnings,
    )


@router.post("/upload")
async def parse_upload(
    request: Request,
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """multipart/form-data → 候选 JSON.

    response 形状 (前端字段卡片直接 render):
      {
        "candidate": {entities, relationships, warnings, overall_confidence},
        "attachment": {path, checksum, size_bytes, filename, content_type},
        "provider": "claude" | "demo-mock",
        "source_type": "excel" | "contract" | "wechat_screenshot",
        "action_log_id": <UUID>,
      }
    """
    enterprise_id = _tenant_id_from_request(request)
    actor = _actor_from_request(request)
    if enterprise_id != "default":
        await ensure_schema_ingest_tables_for(enterprise_id)

    if not file.filename:
        raise HTTPException(status_code=400, detail="file.filename is empty")

    source_type = _infer_source_type(file.filename, file.content_type)
    provider, provider_name = _resolve_provider()

    final_path, checksum, size_bytes = await _save_upload(
        file, enterprise_id, source_type,
    )

    try:
        if provider_name == "demo-mock":
            # No LLM key. Bypass parse_pipeline adapters (which would either need a
            # real LLM for pdf/img or produce customer ontology entities for xlsx).
            # Run DemoMockProvider directly + wrap into CandidateJSON so the
            # downstream contract (confirm_writer) sees the same shape.
            candidate = await _run_demo_provider(
                provider, source_type=source_type, filename=file.filename,
                file_ref=f"upload://{enterprise_id}/{checksum}",
                uploaded_by=actor,
            )
        else:
            candidate = await parse_to_candidates(
                file_path=final_path,
                source_type=source_type,  # type: ignore[arg-type]
                filename=file.filename,
                content_type=file.content_type,
                provider=provider,
                file_ref=f"upload://{enterprise_id}/{checksum}",
                uploaded_by=actor,
            )
    except Exception as e:
        logger.exception(
            "parse_upload failed filename=%s source_type=%s", file.filename, source_type,
        )
        raise HTTPException(
            status_code=500,
            detail=f"parse_pipeline failed: {type(e).__name__}: {e}",
        ) from e

    # ActionLog (one row per upload). target_entity_type=other because no
    # downstream entity persisted yet; entity will be created on /confirm/entities
    # later by the user 'accept' button.
    async with session.begin():
        log = ActionLog(
            target_entity_type=ActionTargetType.other,
            target_entity_id=uuid4(),  # 暂用 random,不指向具体 entity
            action_type=NextActionType.other,
            actor=actor,
            actor_kind="user",
            input_summary=(
                f"action=parse_upload filename={file.filename} "
                f"content_type={file.content_type or 'n/a'} "
                f"size_bytes={size_bytes} checksum={checksum} "
                f"source_type={source_type} provider={provider_name} "
                f"entities={len(candidate.entities)} "
                f"overall_confidence={candidate.overall_confidence:.3f}"
            ),
            output_summary=f"path={final_path} ref=upload://{enterprise_id}/{checksum}",
            executed_at=__import__("datetime").datetime.now(
                tz=__import__("datetime").timezone.utc,
            ),
            succeeded=True,
            created_by=actor,
            updated_by=actor,
        )
        session.add(log)
        await session.flush()
        log_id = log.id

    return {
        "candidate": _candidate_to_dict(candidate),
        "attachment": {
            "path": str(final_path),
            "checksum": checksum,
            "size_bytes": size_bytes,
            "filename": file.filename,
            "content_type": file.content_type,
        },
        "provider": provider_name,
        "source_type": source_type,
        "action_log_id": str(log_id),
    }
