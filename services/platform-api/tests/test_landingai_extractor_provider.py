"""Tests for ``LandingAIExtractorProvider``.

The provider wraps LandingAI ``extract_with_schema`` behind the generic
``ExtractorProvider`` contract:

- For each ``PipelineSelection``: build a canonical schema from the tenant
  company catalog, call LandingAI Extract with ``markdown=input.markdown``,
  and return one ``PipelineExtractResult``.
- Per-schema LandingAI failures are soft: empty extraction + a warning string
  formatted as
  ``"LandingAI extract failed for {name}: {error}"``. Other selections still
  complete.
- A ``progress`` callback, if provided, is invoked with
  ``("pipeline_started", {"name": ...})`` before each schema and
  ``("pipeline_done", {"name": ..., "ok": bool})`` after.

We monkeypatch ``extract_with_schema`` — no live LandingAI calls, no DB. The
project autouse ``_clean_state`` fixture wants Postgres + Redis; we override
with a no-op.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest


# Override the project-level autouse fixture so we don't need Postgres.
@pytest.fixture(autouse=True)
def _clean_state():  # noqa: PT004 — yield-only no-op replacement fixture
    yield


import uuid

from yunwei_win.services.ingest.extractors.providers import landingai as provider_module
from yunwei_win.services.ingest.extractors.providers.base import ExtractionInput
from yunwei_win.services.ingest.extractors.providers.landingai import (
    LandingAIExtractorProvider,
)
from yunwei_win.services.ingest.pipeline_schemas import PipelineSelection
from yunwei_win.services.landingai_ade_client import (
    LandingAIExtractResult,
    LandingAIUnavailable,
)
from tests.test_ingest_review_draft import _catalog_from_default


def _make_input(selections: list[PipelineSelection], markdown: str = "甲方：测试客户有限公司") -> ExtractionInput:
    """Build an ``ExtractionInput`` with a stub session — provider does not
    touch the DB, so a ``SimpleNamespace`` placeholder is enough."""
    return ExtractionInput(
        document_id=uuid.uuid4(),
        session=SimpleNamespace(),  # type: ignore[arg-type]
        markdown=markdown,
        selections=selections,
        company_schema=_catalog_from_default(),
    )


@pytest.mark.asyncio
async def test_extract_selected_runs_each_schema(monkeypatch):
    """Happy path: each selection gets one PipelineExtractResult, schema JSON
    is generated from company schema and forwarded to extract_with_schema."""
    calls: list[tuple[str, str]] = []

    async def fake_extract_with_schema(*, schema_json: str, markdown: str) -> LandingAIExtractResult:
        calls.append((schema_json, markdown))
        return LandingAIExtractResult(
            extraction={"ok": True, "schema": schema_json},
            extraction_metadata={"duration_ms": 42},
            metadata={"model": "fake"},
        )

    monkeypatch.setattr(provider_module, "extract_with_schema", fake_extract_with_schema)

    provider = LandingAIExtractorProvider()
    results = await provider.extract_selected(
        _make_input(
            [
                PipelineSelection(name="identity", confidence=0.9),
                PipelineSelection(name="contract_order", confidence=0.8),
            ]
        )
    )

    assert [r.name for r in results] == ["identity", "contract_order"]
    assert all(r.warnings == [] for r in results)
    assert results[0].extraction["ok"] is True
    assert '"customers"' in results[0].extraction["schema"]
    assert '"contacts"' in results[0].extraction["schema"]
    assert results[0].extraction_metadata == {"duration_ms": 42}
    assert '"orders"' in results[1].extraction["schema"]
    assert '"amount_total"' in results[1].extraction["schema"]
    # Markdown forwarded unchanged to every call.
    assert all(md == "甲方：测试客户有限公司" for _, md in calls)
    assert len(calls) == 2


@pytest.mark.asyncio
async def test_extract_selected_uses_company_schema(monkeypatch):
    calls: list[str] = []

    async def fake_extract_with_schema(*, schema_json: str, markdown: str) -> LandingAIExtractResult:
        calls.append(schema_json)
        return LandingAIExtractResult(
            extraction={"orders": {"amount_total": "30000"}},
            extraction_metadata={},
            metadata={},
        )

    monkeypatch.setattr(provider_module, "extract_with_schema", fake_extract_with_schema)

    provider = LandingAIExtractorProvider()
    results = await provider.extract_selected(
        _make_input([PipelineSelection(name="contract_order", confidence=0.9)])
    )

    assert results[0].extraction == {"orders": {"amount_total": "30000"}}
    assert len(calls) == 1
    assert '"orders"' in calls[0]
    assert '"amount_total"' in calls[0]
    assert '"total_amount"' not in calls[0]


@pytest.mark.asyncio
async def test_extract_selected_soft_fails_on_extract_error(monkeypatch):
    """When ``extract_with_schema`` raises for one selection, the provider
    must return a soft-fail PipelineExtractResult (empty extraction + warning)
    for that schema and still complete the remaining selections normally."""

    async def fake_extract_with_schema(*, schema_json: str, markdown: str) -> LandingAIExtractResult:
        if '"orders"' in schema_json:
            raise LandingAIUnavailable("upstream 500")
        return LandingAIExtractResult(
            extraction={"ok": True},
            extraction_metadata={},
            metadata={},
        )

    monkeypatch.setattr(provider_module, "extract_with_schema", fake_extract_with_schema)

    provider = LandingAIExtractorProvider()
    results = await provider.extract_selected(
        _make_input(
            [
                PipelineSelection(name="identity", confidence=0.9),
                PipelineSelection(name="contract_order", confidence=0.8),
                PipelineSelection(name="finance", confidence=0.7),
            ]
        )
    )

    by_name = {r.name: r for r in results}

    # Non-failing schemas come back populated.
    assert by_name["identity"].extraction == {"ok": True}
    assert by_name["identity"].warnings == []
    assert by_name["finance"].extraction == {"ok": True}
    assert by_name["finance"].warnings == []

    # Failing schema is soft: empty extraction + warning string in the
    # canonical "LandingAI extract failed for {name}: {error}" shape.
    failed = by_name["contract_order"]
    assert failed.extraction == {}
    assert failed.extraction_metadata == {}
    assert len(failed.warnings) == 1
    assert failed.warnings[0].startswith(
        "LandingAI extract failed for contract_order:"
    )
    assert "upstream 500" in failed.warnings[0]

@pytest.mark.asyncio
async def test_extract_selected_emits_progress_events(monkeypatch):
    """If ``progress`` is supplied, the provider emits a ``pipeline_started``
    event before each selection and a ``pipeline_done`` event after, with
    ``ok=True`` for success and ``ok=False`` for soft-failed selections."""

    async def fake_extract_with_schema(*, schema_json: str, markdown: str) -> LandingAIExtractResult:
        if '"invoices"' in schema_json:
            raise LandingAIUnavailable("boom")
        return LandingAIExtractResult(
            extraction={"ok": True},
            extraction_metadata={},
            metadata={},
        )

    monkeypatch.setattr(provider_module, "extract_with_schema", fake_extract_with_schema)

    events: list[tuple[str, dict[str, Any]]] = []

    async def progress(event: str, payload: dict[str, Any]) -> None:
        events.append((event, payload))

    provider = LandingAIExtractorProvider()
    await provider.extract_selected(
        _make_input(
            [
                PipelineSelection(name="identity", confidence=0.9),
                PipelineSelection(name="finance", confidence=0.7),
            ]
        ),
        progress=progress,
    )

    # Both schemas should emit started + done, regardless of failure.
    started = [(name, payload) for name, payload in events if name == "pipeline_started"]
    done = [(name, payload) for name, payload in events if name == "pipeline_done"]

    assert {p["name"] for _, p in started} == {"identity", "finance"}
    done_by_name = {p["name"]: p for _, p in done}
    assert done_by_name["identity"]["ok"] is True
    assert done_by_name["finance"]["ok"] is False
