"""Tests for the commercial extractor (``services/ingest/extractors/commercial.py``).

Covers:
- LLM happy path: contract OCR → ``CommercialDraft`` with order + contract +
  payment milestones
- Non-commercial document (business card) → ``order=None`` + ``contract=None``
  + the LLM's "非商务文档" warning is preserved
- Non-commercial fallback: if both order and contract are null but the LLM
  forgot to say "非商务", we add a synthetic warning so the reviewer knows
  why the panel is empty
- Imbalanced payment_milestones ratios → post-validation warning
- ``call_claude`` is invoked text-only (no image content blocks)
- LLM-side errors propagate up

The project autouse fixture wants Postgres + Redis; we override with a no-op
because these tests use in-memory SQLite, mirroring ``test_planner.py`` /
``test_evidence.py`` / ``test_identity_extractor.py``.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest


# Override the project-level autouse fixture so we don't need Postgres.
@pytest.fixture(autouse=True)
def _clean_state():  # noqa: PT004 — yield-only no-op replacement fixture
    yield


from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

import yunwei_win.models  # noqa: F401 — register SQLAlchemy mappers
from yunwei_win.db import Base
from yunwei_win.models import (
    Document,
    DocumentProcessingStatus,
    DocumentReviewStatus,
    DocumentType,
)
from yunwei_win.services.ingest.extractors import commercial as commercial_module
from yunwei_win.services.ingest.extractors.commercial import (
    COMMERCIAL_TOOL_NAME,
    _validate_milestones,
    _validate_non_commercial_warning,
    commercial_tool,
    extract_commercial,
)
from yunwei_win.services.ingest.unified_schemas import CommercialDraft


# ---------- helpers -------------------------------------------------------


async def _make_session() -> tuple[AsyncSession, Any]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session = AsyncSession(engine, expire_on_commit=False)
    return session, engine


async def _make_doc(session: AsyncSession, ocr: str = "") -> Document:
    doc = Document(
        type=DocumentType.contract,
        file_url="/tmp/contract.pdf",
        original_filename="contract.pdf",
        content_type="application/pdf",
        file_sha256="0" * 64,
        file_size_bytes=len(ocr.encode("utf-8")) or 1,
        ocr_text=ocr,
        processing_status=DocumentProcessingStatus.parsed,
        review_status=DocumentReviewStatus.pending_review,
    )
    session.add(doc)
    await session.flush()
    return doc


def _make_response(tool_input: dict[str, Any]) -> Any:
    """Build a fake Anthropic SDK response with a single ``tool_use`` block.

    ``extract_tool_use_input`` reads ``response.content[i].type``,
    ``.name``, and ``.input`` — a SimpleNamespace is plenty.
    """
    block = SimpleNamespace(
        type="tool_use",
        name=COMMERCIAL_TOOL_NAME,
        input=tool_input,
    )
    return SimpleNamespace(content=[block])


# ---------- commercial_tool schema ---------------------------------------


def test_commercial_tool_schema_shape() -> None:
    tool = commercial_tool()
    assert tool["name"] == COMMERCIAL_TOOL_NAME
    schema = tool["input_schema"]
    props = schema["properties"]
    # Must surface the four CommercialDraft top-level fields (matches the
    # schema declared in unified_schemas.CommercialDraft).
    for key in ("order", "contract", "field_provenance", "confidence_overall"):
        assert key in props, f"commercial_tool schema missing {key}"
    # Must NOT surface identity-side fields (those belong to the identity
    # extractor — keeping them out is the whole point of splitting them up).
    assert "customer" not in props
    assert "contacts" not in props
    # ``_strip_titles`` should have removed the ``title`` keys pydantic emits.
    assert "title" not in schema


# ---------- _validate_milestones -----------------------------------------


def test_validate_milestones_quiet_for_balanced_ratios() -> None:
    draft = CommercialDraft.model_validate(
        {
            "order": None,
            "contract": {
                "contract_no_external": "T-2025-001",
                "payment_milestones": [
                    {
                        "name": "预付款",
                        "ratio": 0.30,
                        "trigger_event": "contract_signed",
                    },
                    {
                        "name": "发货款",
                        "ratio": 0.40,
                        "trigger_event": "before_shipment",
                    },
                    {
                        "name": "调试款",
                        "ratio": 0.20,
                        "trigger_event": "on_acceptance",
                    },
                    {
                        "name": "质保款",
                        "ratio": 0.10,
                        "trigger_event": "warranty_end",
                    },
                ],
            },
            "field_provenance": [],
            "confidence_overall": 0.9,
            "parse_warnings": [],
        }
    )
    _validate_milestones(draft)
    assert draft.parse_warnings == []


def test_validate_milestones_flags_imbalanced_ratios() -> None:
    draft = CommercialDraft.model_validate(
        {
            "order": None,
            "contract": {
                "contract_no_external": None,
                "payment_milestones": [
                    {
                        "name": "预付款",
                        "ratio": 0.30,
                        "trigger_event": "contract_signed",
                    },
                    {
                        "name": "发货款",
                        "ratio": 0.40,
                        "trigger_event": "before_shipment",
                    },
                    # Missing 0.30 — sum is only 0.70.
                ],
            },
            "field_provenance": [],
            "confidence_overall": 0.6,
            "parse_warnings": [],
        }
    )
    _validate_milestones(draft)
    assert any("ratio sum" in w for w in draft.parse_warnings)


def test_validate_milestones_quiet_when_no_contract() -> None:
    """Pure non-commercial doc, contract=None: no milestone warning."""
    draft = CommercialDraft.model_validate(
        {
            "order": None,
            "contract": None,
            "field_provenance": [],
            "confidence_overall": 0.1,
            "parse_warnings": [],
        }
    )
    _validate_milestones(draft)
    assert draft.parse_warnings == []


# ---------- _validate_non_commercial_warning -----------------------------


def test_non_commercial_warning_added_when_silent() -> None:
    """Both order and contract null but no "非商务" warning → we add one."""
    draft = CommercialDraft.model_validate(
        {
            "order": None,
            "contract": None,
            "field_provenance": [],
            "confidence_overall": 0.2,
            "parse_warnings": [],
        }
    )
    _validate_non_commercial_warning(draft)
    assert any(
        "未抽出 order/contract" in w or "非商务" in w
        for w in draft.parse_warnings
    )


def test_non_commercial_warning_preserves_existing_declaration() -> None:
    """If the LLM already added a 非商务 warning, we don't pile on a duplicate."""
    draft = CommercialDraft.model_validate(
        {
            "order": None,
            "contract": None,
            "field_provenance": [],
            "confidence_overall": 0.1,
            "parse_warnings": ["非商务文档"],
        }
    )
    _validate_non_commercial_warning(draft)
    assert draft.parse_warnings == ["非商务文档"]


def test_non_commercial_warning_quiet_when_extraction_present() -> None:
    """Order or contract present → no synthetic warning."""
    draft = CommercialDraft.model_validate(
        {
            "order": {
                "amount_total": 100000.0,
                "amount_currency": "CNY",
            },
            "contract": None,
            "field_provenance": [],
            "confidence_overall": 0.7,
            "parse_warnings": [],
        }
    )
    _validate_non_commercial_warning(draft)
    assert draft.parse_warnings == []


# ---------- extract_commercial happy paths -------------------------------


@pytest.mark.asyncio
async def test_extract_commercial_returns_full_draft(monkeypatch) -> None:
    """Standard contract flow: LLM returns clean tool_use input → parsed
    CommercialDraft with both order and contract dimensions populated."""
    captured: dict[str, Any] = {}

    async def fake_call_claude(messages, *, purpose, session, **kwargs):
        captured["purpose"] = purpose
        captured["model"] = kwargs.get("model")
        captured["tools"] = kwargs.get("tools")
        captured["tool_choice"] = kwargs.get("tool_choice")
        captured["document_id"] = kwargs.get("document_id")
        captured["max_tokens"] = kwargs.get("max_tokens")
        captured["temperature"] = kwargs.get("temperature")
        captured["messages"] = messages
        return _make_response(
            {
                "order": {
                    "amount_total": 2220000.00,
                    "amount_currency": "CNY",
                    "delivery_promised_date": "2025-10-15",
                    "delivery_address": "上海市奉贤区某某园区",
                    "description": "石墨匣钵 3000 个",
                },
                "contract": {
                    "contract_no_external": "YH-2025-001",
                    "payment_milestones": [
                        {
                            "name": "预付款",
                            "ratio": 0.30,
                            "trigger_event": "contract_signed",
                            "trigger_offset_days": None,
                            "raw_text": "合同签订后 7 天内支付 30%",
                        },
                        {
                            "name": "发货款",
                            "ratio": 0.40,
                            "trigger_event": "before_shipment",
                            "trigger_offset_days": None,
                            "raw_text": "发货前支付 40%",
                        },
                        {
                            "name": "验收款",
                            "ratio": 0.20,
                            "trigger_event": "on_acceptance",
                            "trigger_offset_days": None,
                            "raw_text": "验收合格后支付 20%",
                        },
                        {
                            "name": "质保款",
                            "ratio": 0.10,
                            "trigger_event": "warranty_end",
                            "trigger_offset_days": 365,
                            "raw_text": "质保期满后支付 10%",
                        },
                    ],
                    "delivery_terms": "FOB 上海",
                    "penalty_terms": "逾期交货按每日 0.5% 收取违约金",
                    "signing_date": "2025-08-01",
                    "effective_date": "2025-08-01",
                    "expiry_date": "2026-08-01",
                },
                "field_provenance": [
                    {
                        "path": "order.amount_total",
                        "source_page": 1,
                        "source_excerpt": "总金额 2,220,000.00 元",
                    },
                    {
                        "path": "contract.contract_no_external",
                        "source_page": 1,
                        "source_excerpt": "合同编号 YH-2025-001",
                    },
                ],
                "confidence_overall": 0.88,
                "parse_warnings": [],
            }
        )

    monkeypatch.setattr(commercial_module, "call_claude", fake_call_claude)

    session, engine = await _make_session()
    try:
        doc = await _make_doc(
            session,
            ocr="合同编号 YH-2025-001 总金额 2,220,000.00 元 30% 预付 40% 发货",
        )
        draft = await extract_commercial(
            session=session,
            document_id=doc.id,
            ocr_text=doc.ocr_text or "",
        )
        await session.commit()

        assert isinstance(draft, CommercialDraft)
        # order dimension
        assert draft.order is not None
        assert draft.order.amount_total == pytest.approx(2220000.00)
        assert draft.order.amount_currency == "CNY"
        assert str(draft.order.delivery_promised_date) == "2025-10-15"
        # contract dimension
        assert draft.contract is not None
        assert draft.contract.contract_no_external == "YH-2025-001"
        assert len(draft.contract.payment_milestones) == 4
        ratios = [m.ratio for m in draft.contract.payment_milestones]
        assert ratios == [0.30, 0.40, 0.20, 0.10]
        assert str(draft.contract.signing_date) == "2025-08-01"
        # confidence + warnings
        assert draft.confidence_overall == pytest.approx(0.88)
        # No imbalance / no missing-extraction → no post-validation warnings.
        assert draft.parse_warnings == []
        # Provenance threaded through unchanged.
        paths = {entry.path for entry in draft.field_provenance}
        assert "order.amount_total" in paths
        assert "contract.contract_no_external" in paths

        # The LLM was called with the expected purpose + model + tool spec.
        assert captured["purpose"] == "commercial_extraction"
        assert captured["document_id"] == doc.id
        assert captured["temperature"] == 0
        assert captured["max_tokens"] == 8192
        tools = captured["tools"]
        assert tools[0]["name"] == COMMERCIAL_TOOL_NAME
        assert captured["tool_choice"] == {
            "type": "tool",
            "name": COMMERCIAL_TOOL_NAME,
        }

        # Critically: messages must be text-only (no image content block).
        assert len(captured["messages"]) == 1
        content = captured["messages"][0]["content"]
        assert isinstance(content, list)
        assert all(block.get("type") == "text" for block in content)
        # OCR text must be substituted into the prompt.
        joined = "".join(b.get("text", "") for b in content)
        assert "YH-2025-001" in joined
    finally:
        await session.close()
        await engine.dispose()


@pytest.mark.asyncio
async def test_extract_commercial_business_card_returns_nulls(monkeypatch) -> None:
    """Business card / non-commercial doc → LLM returns ``order=None`` and
    ``contract=None`` and a "非商务文档" warning. The post-validation pass
    must NOT pile a duplicate warning on top."""

    async def fake_call_claude(messages, *, purpose, session, **kwargs):
        return _make_response(
            {
                "order": None,
                "contract": None,
                "field_provenance": [],
                "confidence_overall": 0.1,
                "parse_warnings": ["非商务文档"],
            }
        )

    monkeypatch.setattr(commercial_module, "call_claude", fake_call_claude)

    session, engine = await _make_session()
    try:
        doc = await _make_doc(
            session,
            ocr="王经理 销售总监 13800000000 wang@example.com 北京 XX 公司",
        )
        draft = await extract_commercial(
            session=session,
            document_id=doc.id,
            ocr_text=doc.ocr_text or "",
        )
        await session.commit()

        assert draft.order is None
        assert draft.contract is None
        # The original 非商务文档 declaration is preserved verbatim.
        assert "非商务文档" in draft.parse_warnings
        # And NOT duplicated by the synthetic fallback.
        assert len(draft.parse_warnings) == 1
    finally:
        await session.close()
        await engine.dispose()


@pytest.mark.asyncio
async def test_extract_commercial_silent_null_adds_fallback_warning(
    monkeypatch,
) -> None:
    """LLM returned both null but forgot to say 非商务文档 → we add a
    synthetic warning so the reviewer knows the extractor was consulted."""

    async def fake_call_claude(messages, *, purpose, session, **kwargs):
        return _make_response(
            {
                "order": None,
                "contract": None,
                "field_provenance": [],
                "confidence_overall": 0.2,
                "parse_warnings": [],
            }
        )

    monkeypatch.setattr(commercial_module, "call_claude", fake_call_claude)

    session, engine = await _make_session()
    try:
        doc = await _make_doc(session, ocr="一些没什么内容的文本")
        draft = await extract_commercial(
            session=session,
            document_id=doc.id,
            ocr_text=doc.ocr_text or "",
        )
        await session.commit()

        assert draft.order is None
        assert draft.contract is None
        assert any(
            "未抽出 order/contract" in w for w in draft.parse_warnings
        )
    finally:
        await session.close()
        await engine.dispose()


# ---------- post-validation paths ----------------------------------------


@pytest.mark.asyncio
async def test_extract_commercial_warns_on_imbalanced_ratios(monkeypatch) -> None:
    """LLM returned milestones whose ratios don't sum to 1.0 → post-validation
    appends a warning, but values are NOT rewritten."""

    async def fake_call_claude(messages, *, purpose, session, **kwargs):
        return _make_response(
            {
                "order": {
                    "amount_total": 500000.0,
                    "amount_currency": "CNY",
                },
                "contract": {
                    "contract_no_external": "T-2025-002",
                    "payment_milestones": [
                        {
                            "name": "预付款",
                            "ratio": 0.50,
                            "trigger_event": "contract_signed",
                        },
                        {
                            "name": "尾款",
                            "ratio": 0.30,  # 0.50 + 0.30 = 0.80, not 1.0
                            "trigger_event": "on_acceptance",
                        },
                    ],
                },
                "field_provenance": [],
                "confidence_overall": 0.55,
                "parse_warnings": [],
            }
        )

    monkeypatch.setattr(commercial_module, "call_claude", fake_call_claude)

    session, engine = await _make_session()
    try:
        doc = await _make_doc(session, ocr="50% 预付 30% 尾款")
        draft = await extract_commercial(
            session=session,
            document_id=doc.id,
            ocr_text=doc.ocr_text or "",
        )
        await session.commit()

        # Values preserved unchanged — reviewer must see the raw ratios.
        ratios = [m.ratio for m in draft.contract.payment_milestones]
        assert ratios == [0.50, 0.30]
        assert any("ratio sum" in w for w in draft.parse_warnings)
    finally:
        await session.close()
        await engine.dispose()


# ---------- error propagation --------------------------------------------


@pytest.mark.asyncio
async def test_extract_commercial_propagates_llm_error(monkeypatch) -> None:
    """When ``call_claude`` raises, the extractor lets the exception bubble
    up — the orchestrator decides how to handle a failed dimension."""

    class BoomError(RuntimeError):
        pass

    async def fake_call_claude(messages, *, purpose, session, **kwargs):
        raise BoomError("upstream LLM is down")

    monkeypatch.setattr(commercial_module, "call_claude", fake_call_claude)

    session, engine = await _make_session()
    try:
        doc = await _make_doc(session, ocr="anything")
        with pytest.raises(BoomError):
            await extract_commercial(
                session=session,
                document_id=doc.id,
                ocr_text=doc.ocr_text or "",
            )
    finally:
        await session.close()
        await engine.dispose()


# ---------- progress callbacks -------------------------------------------


@pytest.mark.asyncio
async def test_extract_commercial_emits_progress(monkeypatch) -> None:
    """Both ``commercial_extract`` (start) and ``commercial_done`` (finish)
    stages must reach the progress callback."""

    async def fake_call_claude(messages, *, purpose, session, **kwargs):
        return _make_response(
            {
                "order": None,
                "contract": None,
                "field_provenance": [],
                "confidence_overall": 0.1,
                "parse_warnings": ["非商务文档"],
            }
        )

    monkeypatch.setattr(commercial_module, "call_claude", fake_call_claude)

    session, engine = await _make_session()
    progress_events: list[tuple[str, str]] = []

    async def progress(stage: str, message: str) -> None:
        progress_events.append((stage, message))

    try:
        doc = await _make_doc(session, ocr="just a memo")
        await extract_commercial(
            session=session,
            document_id=doc.id,
            ocr_text=doc.ocr_text or "",
            progress=progress,
        )
        await session.commit()

        stages = [stage for stage, _ in progress_events]
        assert "commercial_extract" in stages
        assert "commercial_done" in stages
    finally:
        await session.close()
        await engine.dispose()
