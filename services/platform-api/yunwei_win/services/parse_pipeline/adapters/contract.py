"""Contract adapter — PDF/image → text/vision → provider → candidate JSON.

Flow:

  1. If file is a text-extractable PDF (``pdfplumber.extract_text`` returns
     non-trivial text), extract markdown directly and skip OCR.
  2. Otherwise, read raw bytes as image (PNG/JPG) or push through OCR
     (callers wire OcrProvider via ``ocr_provider`` parameter); the
     provider receives ``image_b64`` and decides.
  3. Hand the payload to the ExtractionProvider (Claude in prod, Mock in
     tests). The provider returns ProviderResult with entities + fields.
  4. Shape ProviderResult into CandidateJSON: stamp source_span from
     ``source_excerpt`` / ``source_page`` / ``source_bbox``, compute
     missing_required from ontology, penalise confidence when the
     provider failed to supply provenance, compute overall_confidence.

The adapter never touches the SQLAlchemy DB — it just translates shapes.
"""

from __future__ import annotations

import base64
import logging
import mimetypes
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from yunwei_win.services.parse_pipeline.candidate import (
    CandidateEntity,
    CandidateJSON,
    EntityType,
    FieldCandidate,
    Relationship,
    SourceInfo,
    SourceSpan,
)
from yunwei_win.services.parse_pipeline.ontology import (
    known_fields,
    required_fields,
)
from yunwei_win.services.parse_pipeline.providers.base import (
    ExtractionPayload,
    ExtractionProvider,
    ProviderResult,
)


logger = logging.getLogger(__name__)


_VALID_ENTITY_TYPES = {
    "Customer", "Contact", "Contract", "Order", "OrderLine",
    "Product", "Invoice", "Payment",
}


async def parse_contract(
    *,
    file_path: Path,
    filename: str,
    content_type: str | None,
    provider: ExtractionProvider,
    file_ref: str = "",
    uploaded_by: str | None = None,
) -> CandidateJSON:
    markdown, image_b64, image_mt = _read_contract_inputs(file_path, filename, content_type)
    payload = ExtractionPayload(
        source_type="contract",
        filename=filename,
        markdown=markdown,
        image_b64=image_b64,
        image_media_type=image_mt,
    )
    result = await provider.extract(payload)
    return _shape_candidate_json(
        result,
        source_type="contract",
        file_ref=file_ref or filename,
        uploaded_by=uploaded_by,
    )


def _read_contract_inputs(
    file_path: Path,
    filename: str,
    content_type: str | None,
) -> tuple[str, str | None, str | None]:
    """Return (markdown, image_b64, image_media_type).

    PDFs: try pdfplumber text extraction first; fall back to base64
    of the file bytes if extraction yields nothing useful.
    Images: skip text; return base64 only.
    Other: read as text best-effort.
    """
    ext = file_path.suffix.lower()
    ct = (content_type or "").lower()

    if ext in {".png", ".jpg", ".jpeg", ".webp"} or ct.startswith("image/"):
        mt = ct or mimetypes.guess_type(filename)[0] or "image/png"
        return "", _b64(file_path), mt

    if ext == ".pdf" or ct == "application/pdf":
        markdown = _pdf_text(file_path)
        if markdown.strip():
            return markdown, None, None
        # Scanned/empty PDF: pass bytes so the provider can vision-extract.
        return "", _b64(file_path), "application/pdf"

    # Text/other — read as utf-8 best-effort.
    try:
        return file_path.read_text(encoding="utf-8", errors="replace"), None, None
    except OSError:
        return "", _b64(file_path), ct or "application/octet-stream"


def _pdf_text(path: Path) -> str:
    try:
        import pdfplumber  # type: ignore[import-not-found]
    except ImportError:
        return ""
    try:
        with pdfplumber.open(str(path)) as pdf:
            parts = []
            for page in pdf.pages:
                t = page.extract_text() or ""
                if t.strip():
                    parts.append(t)
            return "\n\n".join(parts)
    except Exception as exc:  # pdfplumber raises a host of errors
        logger.warning("pdfplumber failed for %s: %s", path, exc)
        return ""


def _b64(path: Path) -> str:
    return base64.b64encode(path.read_bytes()).decode("ascii")


def _shape_candidate_json(
    result: ProviderResult,
    *,
    source_type: str,
    file_ref: str,
    uploaded_by: str | None,
) -> CandidateJSON:
    """Translate ProviderResult → CandidateJSON, computing missing_required + overall."""
    entities: list[CandidateEntity] = []
    warnings: list[str] = list(result.warnings)
    field_confidences: list[float] = []

    for prov_ent in result.entities:
        if prov_ent.entity_type not in _VALID_ENTITY_TYPES:
            warnings.append(f"provider 返回未知 entity_type '{prov_ent.entity_type}',跳过")
            continue
        ent_type: EntityType = prov_ent.entity_type  # type: ignore[assignment]
        accepted_fields = known_fields(ent_type)
        cand = CandidateEntity(entity_type=ent_type, temp_id=prov_ent.temp_id or f"{ent_type.lower()}-{len(entities)}")
        for pf in prov_ent.fields:
            if accepted_fields and pf.name not in accepted_fields:
                warnings.append(
                    f"{ent_type}.{pf.name} 不在本体字段表,已跳过"
                )
                continue
            span_text = pf.source_excerpt
            has_provenance = bool(pf.source_excerpt or pf.source_ref_id or pf.source_page)
            base_conf = pf.confidence if pf.confidence is not None else (0.6 if pf.value not in (None, "") else 0.0)
            if not has_provenance and pf.value not in (None, ""):
                base_conf = max(0.0, min(base_conf, 0.5) - 0.1)
                warnings.append(
                    f"{ent_type}.{pf.name} 未提供原文出处,置信度已下调"
                )
            cand.fields.append(FieldCandidate(
                name=pf.name,
                value=pf.value,
                confidence=round(base_conf, 3),
                source_span=SourceSpan(
                    page=pf.source_page,
                    bbox=pf.source_bbox,
                    text=span_text,
                ),
            ))
            field_confidences.append(round(base_conf, 3))
        present_field_names = {f.name for f in cand.fields if f.value not in (None, "")}
        cand.missing_required = sorted(required_fields(ent_type) - present_field_names)
        entities.append(cand)

    relationships: list[Relationship] = []
    for rel in result.relationships:
        try:
            relationships.append(Relationship(
                from_temp_id=str(rel["from_temp_id"]),
                to_temp_id=str(rel["to_temp_id"]),
                type=str(rel["type"]),
            ))
        except (KeyError, TypeError):
            warnings.append("provider 返回了形式不合法的 relationship,已跳过")

    overall = _overall_confidence(field_confidences, entities)

    return CandidateJSON(
        source=SourceInfo(
            type=source_type,  # type: ignore[arg-type]
            file_ref=file_ref,
            uploaded_by=uploaded_by,
            uploaded_at=datetime.now(timezone.utc),
        ),
        entities=entities,
        relationships=relationships,
        overall_confidence=overall,
        warnings=warnings,
    )


def _overall_confidence(
    confidences: list[float],
    entities: list[CandidateEntity],
) -> float:
    if not confidences:
        return 0.0
    base = sum(confidences) / len(confidences)
    missing_count = sum(len(e.missing_required) for e in entities)
    if missing_count:
        base *= max(0.4, 1.0 - 0.05 * missing_count)
    return round(min(1.0, max(0.0, base)), 3)


# Re-exported so the screenshot adapter can share the shaping logic.
__all__ = ["parse_contract", "_shape_candidate_json"]
