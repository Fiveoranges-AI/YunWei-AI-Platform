"""Documents — original uploaded files (PDF, image, etc.). Permanent (PRD).

raw_llm_response stores the full Claude response so we can re-run extraction
when the model upgrades, without re-uploading.
"""

from __future__ import annotations

import enum
import uuid

from sqlalchemy import JSON, BigInteger, Enum as SQLEnum
from sqlalchemy import ForeignKey, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from yinhu_brain.db import Base
from yinhu_brain.models._base import TimestampMixin
from yinhu_brain.models.customer_memory import (
    DocumentProcessingStatus,
    DocumentReviewStatus,
    InputChannel,
    InputModality,
)


class DocumentType(str, enum.Enum):
    contract = "contract"
    business_card = "business_card"
    chat_log = "chat_log"
    invoice = "invoice"
    shipping_doc = "shipping_doc"
    text_note = "text_note"
    other = "other"


class Document(Base, TimestampMixin):
    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    type: Mapped[DocumentType] = mapped_column(
        SQLEnum(DocumentType, name="document_type"), nullable=False
    )
    file_url: Mapped[str] = mapped_column(String, nullable=False)
    original_filename: Mapped[str] = mapped_column(String, nullable=False)
    content_type: Mapped[str | None] = mapped_column(String, nullable=True)
    file_sha256: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    file_size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)

    ocr_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_llm_response: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)
    parse_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    parse_warnings: Mapped[list] = mapped_column(
        JSON, nullable=False, default=list
    )

    uploader: Mapped[str | None] = mapped_column(String, nullable=True)

    # --- Customer-profile linkage + review state -----------------------
    # Set when uploaded via /api/customers/{id}/ingest; the LLM may also
    # *detect* a different customer to surface in the inbox UI.
    assigned_customer_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("customers.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    detected_customer_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("customers.id", ondelete="SET NULL"),
        nullable=True,
    )
    processing_status: Mapped[DocumentProcessingStatus] = mapped_column(
        SQLEnum(DocumentProcessingStatus, name="document_processing_status"),
        nullable=False,
        default=DocumentProcessingStatus.parsed,
    )
    review_status: Mapped[DocumentReviewStatus] = mapped_column(
        SQLEnum(DocumentReviewStatus, name="document_review_status"),
        nullable=False,
        default=DocumentReviewStatus.not_applicable,
    )
    input_channel: Mapped[InputChannel] = mapped_column(
        SQLEnum(InputChannel, name="input_channel"),
        nullable=False,
        default=InputChannel.web_upload,
    )
    input_modality: Mapped[InputModality] = mapped_column(
        SQLEnum(InputModality, name="input_modality"),
        nullable=False,
        default=InputModality.other,
    )
