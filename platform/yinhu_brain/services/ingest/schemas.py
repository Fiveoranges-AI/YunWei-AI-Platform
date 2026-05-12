"""Pydantic schemas for the contract & business-card extraction tool calls.

`ContractExtractionResult` is the source of truth — the JSON schema we hand to
Anthropic via `tool_use` is generated from it (`as_anthropic_tool`). Field
validators clean LLM-side messes (commas in numbers, `2025年10月15日` dates,
ratio sums).

A flat `field_provenance: list[FieldProvenanceEntry]` records every extracted
non-null field by path (`customer.full_name`, `contract.payment_milestones[0].ratio`).
"""

from __future__ import annotations

import enum
import re
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


# ---------- core enums ----------------------------------------------------

class TriggerEvent(str, enum.Enum):
    contract_signed = "contract_signed"
    before_shipment = "before_shipment"
    on_delivery = "on_delivery"
    on_acceptance = "on_acceptance"
    invoice_issued = "invoice_issued"
    warranty_end = "warranty_end"
    on_demand = "on_demand"
    other = "other"


class ContactRoleEx(str, enum.Enum):
    seller = "seller"
    buyer = "buyer"
    delivery = "delivery"
    acceptance = "acceptance"
    invoice = "invoice"
    other = "other"


# ---------- shared cleaning helpers ---------------------------------------

_AMOUNT_STRIP = re.compile(r"[,，元RMB￥¥\s]")
_CN_DATE = re.compile(r"^(\d{4})\D{1,2}(\d{1,2})\D{1,2}(\d{1,2}).*$")


def _clean_amount(v: Any) -> Any:
    if v is None or isinstance(v, (int, float, Decimal)):
        return v
    if isinstance(v, str):
        s = _AMOUNT_STRIP.sub("", v)
        if not s:
            return None
        return float(s)
    return v


def _clean_date(v: Any) -> Any:
    if v is None or isinstance(v, date):
        return v
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, str):
        s = v.strip()
        if not s:
            return None
        # ISO already
        try:
            return date.fromisoformat(s[:10])
        except ValueError:
            pass
        # 中文 "2025年10月15日"
        m = _CN_DATE.match(s)
        if m:
            y, mo, d = (int(g) for g in m.groups())
            return date(y, mo, d)
        # "2025/10/15" or "2025.10.15"
        s2 = s.replace("/", "-").replace(".", "-")
        try:
            return date.fromisoformat(s2[:10])
        except ValueError:
            return None
    return v


# ---------- provenance ----------------------------------------------------

class FieldProvenanceEntry(BaseModel):
    model_config = ConfigDict(extra="ignore")

    path: str = Field(description="字段路径，如 customer.full_name 或 contract.payment_milestones[0].ratio")
    source_page: int | None = Field(default=None, description="原文页码 (1-indexed)，没法定位填 null")
    source_excerpt: str | None = Field(default=None, max_length=400, description="原文里能 substring-match 到的连续片段")


# ---------- entity schemas ------------------------------------------------

class CustomerExtraction(BaseModel):
    model_config = ConfigDict(extra="ignore")

    # Tolerate None at parse time — if OCR couldn't read the buyer name we'd
    # rather surface a clean "customer name not extracted" error in the
    # pipeline than a generic Pydantic 422.
    full_name: str | None = Field(
        default=None, description="客户公司全称（合同甲方/买方），实在读不到填 null"
    )
    short_name: str | None = None
    address: str | None = None
    tax_id: str | None = None


class ContactExtraction(BaseModel):
    model_config = ConfigDict(extra="ignore")

    # Same pragmatism as customer.full_name: contacts where OCR garbled the
    # name (illegible signature, blurry stamp) get filtered out by the
    # pipeline rather than rejected at validation time.
    name: str | None = None
    title: str | None = None
    phone: str | None = None
    mobile: str | None = None
    email: str | None = None
    role: ContactRoleEx = ContactRoleEx.other
    address: str | None = None


class OrderExtraction(BaseModel):
    model_config = ConfigDict(extra="ignore")

    amount_total: float | None = Field(default=None, description="含税总金额，纯 number")
    amount_currency: str = "CNY"
    delivery_promised_date: date | None = None
    delivery_address: str | None = None
    description: str | None = None

    @field_validator("amount_total", mode="before")
    @classmethod
    def _amt(cls, v): return _clean_amount(v)

    @field_validator("delivery_promised_date", mode="before")
    @classmethod
    def _date(cls, v): return _clean_date(v)


class PaymentMilestone(BaseModel):
    model_config = ConfigDict(extra="ignore")

    # Stay loose at the model boundary — contract.py fills a "未命名阶段"
    # placeholder if absent so DB constraints still pass.
    name: str | None = Field(
        default=None, description="阶段名（合同原文措辞）"
    )
    ratio: float = Field(ge=0.0, le=1.0, description="0-1 小数")
    trigger_event: TriggerEvent
    trigger_offset_days: int | None = None
    raw_text: str | None = None

    @field_validator("ratio", mode="before")
    @classmethod
    def _ratio(cls, v):
        if isinstance(v, str):
            s = v.strip().replace("%", "").replace("％", "")
            try:
                f = float(s)
                if f > 1.0:
                    f = f / 100.0
                return f
            except ValueError:
                return v
        return v

    @field_validator("trigger_offset_days", mode="before")
    @classmethod
    def _offset_days(cls, v):
        """Tolerate string offsets like ``""``, ``"90"``, ``"90天"`` that
        upstream extractors (LandingAI in particular) emit. Empty / unparseable
        → ``None`` so a single garbage milestone never kills the whole ingest.
        """
        if v is None:
            return None
        if isinstance(v, bool):
            return int(v)
        if isinstance(v, int):
            return v
        if isinstance(v, float):
            try:
                return int(v)
            except (OverflowError, ValueError):
                return None
        if isinstance(v, str):
            s = v.strip().replace("天", "").replace(" ", "")
            if not s:
                return None
            try:
                return int(s)
            except ValueError:
                try:
                    return int(float(s))
                except ValueError:
                    return None
        return None


class ContractExtraction(BaseModel):
    model_config = ConfigDict(extra="ignore")

    contract_no_external: str | None = Field(default=None, description="合同编号（合同里印的那个）")
    payment_milestones: list[PaymentMilestone] = Field(default_factory=list)
    delivery_terms: str | None = None
    penalty_terms: str | None = None
    signing_date: date | None = None
    effective_date: date | None = None
    expiry_date: date | None = None

    @field_validator("signing_date", "effective_date", "expiry_date", mode="before")
    @classmethod
    def _date(cls, v): return _clean_date(v)


# ---------- top-level result ---------------------------------------------

class ContractExtractionResult(BaseModel):
    model_config = ConfigDict(extra="ignore")

    customer: CustomerExtraction
    contacts: list[ContactExtraction] = Field(default_factory=list)
    order: OrderExtraction
    contract: ContractExtraction
    field_provenance: list[FieldProvenanceEntry] = Field(default_factory=list)
    confidence_overall: float = Field(ge=0.0, le=1.0, default=0.5)
    field_confidence: dict[str, float] = Field(default_factory=dict)
    parse_warnings: list[str] = Field(default_factory=list)

    @field_validator("field_confidence", mode="before")
    @classmethod
    def _drop_null_confidences(cls, v):
        # LLM legitimately omits confidence for fields it didn't extract; it
        # often emits the path with a null value rather than skipping the
        # entry. Strip those before strict float validation.
        if isinstance(v, dict):
            return {k: c for k, c in v.items() if c is not None}
        return v

    @model_validator(mode="after")
    def _ratio_sum(self):
        ms = self.contract.payment_milestones
        if ms:
            total = sum(m.ratio for m in ms)
            if not (0.99 <= total <= 1.01):
                self.parse_warnings.append(
                    f"payment_milestones ratio sum = {total:.4f}, expected 1.00 (±0.01)"
                )
        return self


# ---------- decision-aware confirm schema ---------------------------------
# Frontend-driven payload submitted from the review form. `mode=new` →
# INSERT a fresh row; `mode=merge` → UPDATE the row at `existing_id` with
# the values in `final` (which the user has reconciled field-by-field).

from uuid import UUID  # noqa: E402  — kept local to this section


class CustomerDecision(BaseModel):
    model_config = ConfigDict(extra="ignore")

    mode: Literal["new", "merge"]
    existing_id: UUID | None = None
    final: CustomerExtraction


class ContactDecision(BaseModel):
    model_config = ConfigDict(extra="ignore")

    mode: Literal["new", "merge"]
    existing_id: UUID | None = None
    final: ContactExtraction


class ContractConfirmRequest(BaseModel):
    """Body of POST /api/ingest/contract/{document_id}/confirm.

    Customer + each contact carry a per-entity decision (new vs merge into
    existing). Order and contract are always new (single PDF → single new
    contract). field_provenance / field_confidence / parse_warnings are
    threaded through unchanged from preview so write_provenance can record
    the source citations after the user-edited values land in DB.
    """

    model_config = ConfigDict(extra="ignore")

    customer: CustomerDecision
    contacts: list[ContactDecision] = Field(default_factory=list)
    order: OrderExtraction
    contract: ContractExtraction
    field_provenance: list[FieldProvenanceEntry] = Field(default_factory=list)
    confidence_overall: float = Field(ge=0.0, le=1.0, default=0.5)
    field_confidence: dict[str, float] = Field(default_factory=dict)
    parse_warnings: list[str] = Field(default_factory=list)

    def to_extraction_result(self) -> ContractExtractionResult:
        """Project decisions onto a flat ContractExtractionResult that
        write_provenance can walk. Path resolution against this object yields
        the values that actually landed in DB."""
        return ContractExtractionResult(
            customer=self.customer.final,
            contacts=[c.final for c in self.contacts],
            order=self.order,
            contract=self.contract,
            field_provenance=self.field_provenance,
            confidence_overall=self.confidence_overall,
            field_confidence=self.field_confidence,
            parse_warnings=self.parse_warnings,
        )


# ---------- business-card schema ------------------------------------------

class BusinessCardExtraction(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str | None = Field(
        default=None,
        description="Person name as printed on the card. Leave null if unreadable.",
    )
    title: str | None = Field(
        default=None,
        description="Job title as printed on the card. Leave null if unreadable.",
    )
    company_full_name: str | None = Field(
        default=None,
        description=(
            "Company/organization name as printed on the card, copied verbatim. "
            "Leave null if the company text on the card is unreadable or absent. "
            "Do NOT infer from email domains, address park names, watermarks, "
            "case-study logos, or partner brands."
        ),
    )
    company_short_name: str | None = Field(
        default=None,
        description=(
            "Short name, logo text, or English abbreviation printed on the card "
            "as a separate string from the full name. Leave null if the card only "
            "carries one company name."
        ),
    )
    phone: str | None = Field(default=None, description="Landline phone number.")
    mobile: str | None = Field(default=None, description="Mobile phone number.")
    email: str | None = Field(default=None, description="Email address.")
    address: str | None = Field(default=None, description="Mailing or office address.")
    wechat_id: str | None = Field(default=None, description="WeChat ID.")
    website: str | None = Field(default=None, description="Company website URL or domain.")
    field_provenance: list[FieldProvenanceEntry] = Field(default_factory=list)
    confidence_overall: float = Field(ge=0.0, le=1.0, default=0.5)
    parse_warnings: list[str] = Field(default_factory=list)


# ---------- tool descriptors fed to Anthropic -----------------------------

CONTRACT_TOOL_NAME = "submit_contract_extraction"
BUSINESS_CARD_TOOL_NAME = "submit_business_card_extraction"
WECHAT_TOOL_NAME = "submit_wechat_extraction"
QA_TOOL_NAME = "submit_qa_answer"


# ---------- Q&A schema ----------------------------------------------------

class CitationTarget(str, enum.Enum):
    customer = "customer"
    contract = "contract"
    order = "order"
    document = "document"


class QACitation(BaseModel):
    model_config = ConfigDict(extra="ignore")

    target_type: CitationTarget
    target_id: str
    snippet: str | None = None


class QAAnswer(BaseModel):
    model_config = ConfigDict(extra="ignore")

    answer: str = Field(description="对用户问题的中文回答；事实声明都要带引用")
    citations: list[QACitation] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0, default=0.5)
    no_relevant_info: bool = Field(default=False, description="知识库里完全没相关信息时设 true")


def qa_tool() -> dict[str, Any]:
    return {
        "name": QA_TOOL_NAME,
        "description": "Submit the answer to the user's question, with typed citations.",
        "input_schema": _strip_titles(QAAnswer.model_json_schema()),
    }


# ---------- WeChat screenshot schema --------------------------------------

class ChatSenderRole(str, enum.Enum):
    self_ = "self"
    other = "other"
    system = "system"


class ChatMessageType(str, enum.Enum):
    text = "text"
    image = "image"
    voice = "voice"
    file = "file"
    transfer = "transfer"
    link = "link"
    other = "other"


class ChatExtractedKind(str, enum.Enum):
    price = "price"
    date = "date"
    contact = "contact"
    commitment = "commitment"
    complaint = "complaint"
    other = "other"


class ChatMessage(BaseModel):
    model_config = ConfigDict(extra="ignore")

    sender: str | None = None
    sender_role: ChatSenderRole = ChatSenderRole.other
    timestamp: str | None = None
    content: str
    message_type: ChatMessageType = ChatMessageType.text


class ChatExtractedEntity(BaseModel):
    model_config = ConfigDict(extra="ignore")

    kind: ChatExtractedKind
    value: str
    from_message_index: int = Field(ge=0)


class WeChatExtraction(BaseModel):
    model_config = ConfigDict(extra="ignore")

    conversation_title: str | None = None
    messages: list[ChatMessage] = Field(default_factory=list)
    extracted_entities: list[ChatExtractedEntity] = Field(default_factory=list)
    summary: str | None = None
    confidence_overall: float = Field(ge=0.0, le=1.0, default=0.5)
    parse_warnings: list[str] = Field(default_factory=list)


def wechat_tool() -> dict[str, Any]:
    return {
        "name": WECHAT_TOOL_NAME,
        "description": "Submit the structured chat log extracted from a WeChat screenshot.",
        "input_schema": _strip_titles(WeChatExtraction.model_json_schema()),
    }


def _strip_titles(schema: dict[str, Any]) -> dict[str, Any]:
    """Anthropic accepts JSON schema; pydantic emits some fields it tolerates,
    but we drop noise like `title` to keep the input_schema tight."""
    if isinstance(schema, dict):
        schema.pop("title", None)
        for v in schema.values():
            if isinstance(v, dict):
                _strip_titles(v)
            elif isinstance(v, list):
                for item in v:
                    if isinstance(item, dict):
                        _strip_titles(item)
    return schema


def contract_tool() -> dict[str, Any]:
    return {
        "name": CONTRACT_TOOL_NAME,
        "description": "Submit the structured fields extracted from a B2B contract.",
        "input_schema": _strip_titles(ContractExtractionResult.model_json_schema()),
    }


def business_card_tool() -> dict[str, Any]:
    return {
        "name": BUSINESS_CARD_TOOL_NAME,
        "description": "Submit the structured fields extracted from a business card image.",
        "input_schema": _strip_titles(BusinessCardExtraction.model_json_schema()),
    }
