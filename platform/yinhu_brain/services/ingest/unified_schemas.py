"""Pydantic schemas for the unified `/api/ingest/auto` pipeline.

The legacy ingest endpoints (`/contract`, `/business_card`, `/wechat`) each
own a single LLM extractor and a single output shape. The unified pipeline
swaps that for a planner-driven fan-out: one OCR pass, a planner that
decides which dimensions are present (identity / commercial / ops),
selective parallel extractors per dimension, and a merge step that
produces a single `UnifiedDraft` for the review form.

This module declares only the *contracts* between those stages. Concrete
extractors, the planner, and the merge logic live in sibling modules.

Existing schemas are reused as-is — `CustomerExtraction`,
`ContactExtraction`, `OrderExtraction`, `ContractExtraction`,
`FieldProvenanceEntry`, `CustomerDecision`, `ContactDecision` from
`schemas.py`; `ExtractedEvent`, `ExtractedCommitment`, `ExtractedTask`,
`ExtractedRiskSignal`, `ExtractedMemoryItem` from `customer_memory_schema.py`.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from yinhu_brain.services.ingest.customer_memory_schema import (
    ExtractedCommitment,
    ExtractedEvent,
    ExtractedMemoryItem,
    ExtractedRiskSignal,
    ExtractedTask,
)
from yinhu_brain.services.ingest.landingai_schemas.registry import PipelineName
from yinhu_brain.services.ingest.schemas import (
    ContactDecision,
    ContactExtraction,
    ContractExtraction,
    CustomerDecision,
    CustomerExtraction,
    FieldProvenanceEntry,
    OrderExtraction,
)


# ---------- planner output ------------------------------------------------

ExtractorName = Literal["identity", "commercial", "ops"]


class ExtractorSelection(BaseModel):
    """One row in the planner's activation list — names an extractor and the
    confidence the planner had that this dimension is actually present in
    the document."""

    model_config = ConfigDict(extra="ignore")

    name: ExtractorName
    confidence: float = Field(ge=0.0, le=1.0)


class IngestPlan(BaseModel):
    """Planner verdict consumed by the orchestrator.

    `targets` is the relevance score per dimension (kept around for telemetry
    and downstream UI hints, even for dimensions not selected). `extractors`
    is the actual activation list — only the extractors named here are run.
    `review_required` lets the planner force a human-in-the-loop pass even
    when confidences look high (e.g. mixed-document red flag).
    """

    model_config = ConfigDict(extra="ignore")

    targets: dict[ExtractorName, float] = Field(default_factory=dict)
    extractors: list[ExtractorSelection] = Field(default_factory=list)
    reason: str = ""
    review_required: bool = False


# ---------- per-extractor draft outputs -----------------------------------

class IdentityDraft(BaseModel):
    """Output of the identity extractor — customer + contacts dimension."""

    model_config = ConfigDict(extra="ignore")

    customer: CustomerExtraction | None = None
    contacts: list[ContactExtraction] = Field(default_factory=list)
    field_provenance: list[FieldProvenanceEntry] = Field(default_factory=list)
    confidence_overall: float = Field(ge=0.0, le=1.0, default=0.5)
    parse_warnings: list[str] = Field(default_factory=list)


class CommercialDraft(BaseModel):
    """Output of the commercial extractor — order + contract dimension."""

    model_config = ConfigDict(extra="ignore")

    order: OrderExtraction | None = None
    contract: ContractExtraction | None = None
    field_provenance: list[FieldProvenanceEntry] = Field(default_factory=list)
    confidence_overall: float = Field(ge=0.0, le=1.0, default=0.5)
    parse_warnings: list[str] = Field(default_factory=list)


class OpsDraft(BaseModel):
    """Output of the ops extractor — events / commitments / tasks /
    risk-signals / memory-items dimension."""

    model_config = ConfigDict(extra="ignore")

    summary: str = ""
    events: list[ExtractedEvent] = Field(default_factory=list)
    commitments: list[ExtractedCommitment] = Field(default_factory=list)
    tasks: list[ExtractedTask] = Field(default_factory=list)
    risk_signals: list[ExtractedRiskSignal] = Field(default_factory=list)
    memory_items: list[ExtractedMemoryItem] = Field(default_factory=list)
    field_provenance: list[FieldProvenanceEntry] = Field(default_factory=list)
    confidence_overall: float = Field(ge=0.0, le=1.0, default=0.5)
    parse_warnings: list[str] = Field(default_factory=list)


# ---------- merged draft (preview payload returned to the frontend) -------

class UnifiedDraft(BaseModel):
    """Merged output of all activated extractors. This is what the review
    form binds to.

    `needs_review_fields` lists field paths whose merged values fell below
    the confidence threshold or carry a conflict warning, so the UI can
    highlight them.
    """

    model_config = ConfigDict(extra="ignore")

    # identity dimension
    customer: CustomerExtraction | None = None
    contacts: list[ContactExtraction] = Field(default_factory=list)
    # commercial dimension
    order: OrderExtraction | None = None
    contract: ContractExtraction | None = None
    # ops dimension
    events: list[ExtractedEvent] = Field(default_factory=list)
    commitments: list[ExtractedCommitment] = Field(default_factory=list)
    tasks: list[ExtractedTask] = Field(default_factory=list)
    risk_signals: list[ExtractedRiskSignal] = Field(default_factory=list)
    memory_items: list[ExtractedMemoryItem] = Field(default_factory=list)
    # meta
    summary: str = ""
    field_provenance: list[FieldProvenanceEntry] = Field(default_factory=list)
    confidence_overall: float = Field(ge=0.0, le=1.0, default=0.5)
    needs_review_fields: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    # LandingAI schema-routed extracts that fed into this draft (one entry per
    # pipeline that ran). Empty when the legacy Mistral path produced the draft.
    pipeline_results: list["PipelineExtractResult"] = Field(default_factory=list)


# ---------- confirm payload ----------------------------------------------

class AutoConfirmRequest(BaseModel):
    """Body of POST /api/ingest/auto/{document_id}/confirm.

    Customer and each contact carry a per-entity decision (new vs merge into
    existing) — same convention as the legacy `ContractConfirmRequest`. The
    ops-side rows (events, commitments, tasks, risk_signals, memory_items)
    do not carry a decision because they are append-only event-log entries
    bound to the customer that confirm produces or merges.
    """

    model_config = ConfigDict(extra="ignore")

    customer: CustomerDecision | None = None
    contacts: list[ContactDecision] = Field(default_factory=list)
    order: OrderExtraction | None = None
    contract: ContractExtraction | None = None
    events: list[ExtractedEvent] = Field(default_factory=list)
    commitments: list[ExtractedCommitment] = Field(default_factory=list)
    tasks: list[ExtractedTask] = Field(default_factory=list)
    risk_signals: list[ExtractedRiskSignal] = Field(default_factory=list)
    memory_items: list[ExtractedMemoryItem] = Field(default_factory=list)
    field_provenance: list[FieldProvenanceEntry] = Field(default_factory=list)
    confidence_overall: float = Field(ge=0.0, le=1.0, default=0.5)
    parse_warnings: list[str] = Field(default_factory=list)


class PipelineSelection(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: PipelineName
    confidence: float = Field(ge=0.0, le=1.0)
    reason: str = ""


class PipelineRoutePlan(BaseModel):
    model_config = ConfigDict(extra="ignore")

    primary_pipeline: PipelineName | None = None
    selected_pipelines: list[PipelineSelection] = Field(default_factory=list)
    rejected_pipelines: list[PipelineSelection] = Field(default_factory=list)
    document_summary: str = ""
    needs_human_review: bool = False


class PipelineExtractResult(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str
    extraction: dict = Field(default_factory=dict)
    extraction_metadata: dict = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)


# Resolve the forward reference on UnifiedDraft.pipeline_results now that
# PipelineExtractResult is defined.
UnifiedDraft.model_rebuild()
