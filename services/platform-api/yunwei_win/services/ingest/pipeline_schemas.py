"""Pydantic contracts for schema-first pipeline routing and extraction."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


PipelineName = Literal[
    "identity",
    "contract_order",
    "finance",
    "logistics",
    "manufacturing_requirement",
    "commitment_task_risk",
]

PIPELINE_NAMES: tuple[PipelineName, ...] = (
    "identity",
    "contract_order",
    "finance",
    "logistics",
    "manufacturing_requirement",
    "commitment_task_risk",
)


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
