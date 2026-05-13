"""Tests for the identity extractor (``services/ingest/extractors/identity.py``).

Covers:
- LLM happy path → ``IdentityDraft`` with customer + contacts
- LLM returns ``customer=None`` (chat with no company) → draft.customer is None
- Multiple contacts on one document → all preserved
- Bad mobile format → parse_warnings flagged (value not rewritten)
- Bad email format → parse_warnings flagged (value not rewritten)
- ``call_claude`` is invoked text-only (no image content blocks)
- The LLM is called with the right tool name + model + document_id

The project autouse fixture wants Postgres + Redis; we override with a no-op
because these tests use in-memory SQLite, mirroring ``test_planner.py`` /
``test_evidence.py``.
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
from yunwei_win.services.ingest.extractors import identity as identity_module
from yunwei_win.services.ingest.extractors.identity import (
    IDENTITY_TOOL_NAME,
    _EMAIL_RE,
    _MOBILE_RE,
    _validate_contacts,
    extract_identity,
    identity_tool,
)
from yunwei_win.services.ingest.unified_schemas import IdentityDraft


# ---------- helpers -------------------------------------------------------


async def _make_session() -> tuple[AsyncSession, Any]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session = AsyncSession(engine, expire_on_commit=False)
    return session, engine


async def _make_doc(session: AsyncSession, ocr: str = "") -> Document:
    doc = Document(
        type=DocumentType.text_note,
        file_url="/tmp/note.txt",
        original_filename="note.txt",
        content_type="text/plain",
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
        name=IDENTITY_TOOL_NAME,
        input=tool_input,
    )
    return SimpleNamespace(content=[block])


# ---------- regex sanity --------------------------------------------------


def test_mobile_regex_accepts_valid_chinese_mobile() -> None:
    assert _MOBILE_RE.match("13800000000")
    assert _MOBILE_RE.match("19912345678")


def test_mobile_regex_rejects_bad_values() -> None:
    assert not _MOBILE_RE.match("12800000000")  # 12 prefix is invalid
    assert not _MOBILE_RE.match("1380000000")   # 10 digits
    assert not _MOBILE_RE.match("138000000000")  # 12 digits
    assert not _MOBILE_RE.match("abc12345678")
    assert not _MOBILE_RE.match("")


def test_email_regex_accepts_valid_email() -> None:
    assert _EMAIL_RE.match("alice@example.com")
    assert _EMAIL_RE.match("a+tag@sub.domain.co")


def test_email_regex_rejects_bad_email() -> None:
    assert not _EMAIL_RE.match("alice")
    assert not _EMAIL_RE.match("alice@")
    assert not _EMAIL_RE.match("alice@nocom")
    assert not _EMAIL_RE.match("@example.com")


# ---------- _validate_contacts -------------------------------------------


def test_validate_contacts_flags_bad_mobile_without_rewriting() -> None:
    draft = IdentityDraft.model_validate(
        {
            "customer": None,
            "contacts": [
                {
                    "name": "王经理",
                    "mobile": "12800000000",  # invalid 12 prefix
                    "email": None,
                    "role": "other",
                },
            ],
            "field_provenance": [],
            "confidence_overall": 0.7,
            "parse_warnings": [],
        }
    )
    _validate_contacts(draft)
    # Value preserved verbatim — reviewer sees the raw OCR string.
    assert draft.contacts[0].mobile == "12800000000"
    # Warning surfaced.
    assert any("contacts[0].mobile" in w for w in draft.parse_warnings)


def test_validate_contacts_flags_bad_email_without_rewriting() -> None:
    draft = IdentityDraft.model_validate(
        {
            "customer": None,
            "contacts": [
                {
                    "name": "Alice",
                    "mobile": None,
                    "email": "not-an-email",
                    "role": "other",
                },
            ],
            "field_provenance": [],
            "confidence_overall": 0.5,
            "parse_warnings": [],
        }
    )
    _validate_contacts(draft)
    assert draft.contacts[0].email == "not-an-email"
    assert any("contacts[0].email" in w for w in draft.parse_warnings)


def test_validate_contacts_quiet_for_valid_values() -> None:
    draft = IdentityDraft.model_validate(
        {
            "customer": None,
            "contacts": [
                {
                    "name": "Bob",
                    "mobile": "13912345678",
                    "email": "bob@example.com",
                    "role": "other",
                },
            ],
            "field_provenance": [],
            "confidence_overall": 0.9,
            "parse_warnings": [],
        }
    )
    _validate_contacts(draft)
    assert draft.parse_warnings == []


# ---------- identity_tool schema -----------------------------------------


def test_identity_tool_schema_shape() -> None:
    tool = identity_tool()
    assert tool["name"] == IDENTITY_TOOL_NAME
    schema = tool["input_schema"]
    props = schema["properties"]
    # Must surface the four IdentityDraft top-level fields.
    for key in ("customer", "contacts", "field_provenance", "confidence_overall"):
        assert key in props, f"identity_tool schema missing {key}"
    # ``_strip_titles`` should have removed the ``title`` keys pydantic emits.
    assert "title" not in schema


# ---------- extract_identity happy paths ---------------------------------


@pytest.mark.asyncio
async def test_extract_identity_returns_customer_and_contacts(monkeypatch) -> None:
    """Standard flow: LLM returns clean tool_use input → parsed IdentityDraft."""
    captured: dict[str, Any] = {}

    async def fake_call_claude(messages, *, purpose, session, **kwargs):
        captured["purpose"] = purpose
        captured["model"] = kwargs.get("model")
        captured["tools"] = kwargs.get("tools")
        captured["document_id"] = kwargs.get("document_id")
        captured["max_tokens"] = kwargs.get("max_tokens")
        captured["temperature"] = kwargs.get("temperature")
        captured["messages"] = messages
        return _make_response(
            {
                "customer": {
                    "full_name": "测试客户有限公司",
                    "short_name": "测试客户",
                    "address": "上海市测试路 1 号",
                    "tax_id": None,
                },
                "contacts": [
                    {
                        "name": "王强",
                        "title": "销售经理",
                        "phone": None,
                        "mobile": "13800000000",
                        "email": "wang@example.com",
                        "role": "buyer",
                        "address": None,
                    }
                ],
                "field_provenance": [
                    {
                        "path": "customer.full_name",
                        "source_page": None,
                        "source_excerpt": "测试客户有限公司",
                    },
                    {
                        "path": "contacts[0].name",
                        "source_page": None,
                        "source_excerpt": "王强",
                    },
                ],
                "confidence_overall": 0.92,
                "parse_warnings": [],
            }
        )

    monkeypatch.setattr(identity_module, "call_claude", fake_call_claude)

    session, engine = await _make_session()
    try:
        doc = await _make_doc(
            session, ocr="测试客户有限公司 王强 13800000000 wang@example.com"
        )
        draft = await extract_identity(
            session=session,
            document_id=doc.id,
            ocr_text=doc.ocr_text or "",
        )
        await session.commit()

        assert isinstance(draft, IdentityDraft)
        assert draft.customer is not None
        assert draft.customer.full_name == "测试客户有限公司"
        assert draft.customer.short_name == "测试客户"
        assert len(draft.contacts) == 1
        assert draft.contacts[0].name == "王强"
        assert draft.contacts[0].mobile == "13800000000"
        assert draft.confidence_overall == pytest.approx(0.92)
        # No malformed values → post-validation added no warnings.
        assert draft.parse_warnings == []
        # Provenance threaded through unchanged.
        paths = {entry.path for entry in draft.field_provenance}
        assert "customer.full_name" in paths
        assert "contacts[0].name" in paths

        # The LLM was called with the expected purpose + model + tool.
        assert captured["purpose"] == "identity_extraction"
        assert captured["document_id"] == doc.id
        assert captured["temperature"] == 0
        assert captured["max_tokens"] == 4096
        tools = captured["tools"]
        assert tools[0]["name"] == IDENTITY_TOOL_NAME

        # Critically: messages must be text-only (no image content block).
        assert len(captured["messages"]) == 1
        content = captured["messages"][0]["content"]
        assert isinstance(content, list)
        assert all(block.get("type") == "text" for block in content)
        # OCR text must be substituted into the prompt.
        joined = "".join(b.get("text", "") for b in content)
        assert "测试客户有限公司" in joined
    finally:
        await session.close()
        await engine.dispose()


@pytest.mark.asyncio
async def test_extract_identity_returns_none_when_no_company(monkeypatch) -> None:
    """Pure chat / memo with no company → customer is None, contacts may still
    be present."""

    async def fake_call_claude(messages, *, purpose, session, **kwargs):
        return _make_response(
            {
                "customer": None,
                "contacts": [
                    {
                        "name": "李工",
                        "title": None,
                        "phone": None,
                        "mobile": None,
                        "email": None,
                        "role": "other",
                        "address": None,
                    }
                ],
                "field_provenance": [
                    {
                        "path": "contacts[0].name",
                        "source_page": None,
                        "source_excerpt": "李工",
                    },
                ],
                "confidence_overall": 0.45,
                "parse_warnings": [],
            }
        )

    monkeypatch.setattr(identity_module, "call_claude", fake_call_claude)

    session, engine = await _make_session()
    try:
        doc = await _make_doc(session, ocr="李工说周五前来一下")
        draft = await extract_identity(
            session=session,
            document_id=doc.id,
            ocr_text=doc.ocr_text or "",
        )
        await session.commit()

        assert draft.customer is None
        assert len(draft.contacts) == 1
        assert draft.contacts[0].name == "李工"
        assert draft.confidence_overall == pytest.approx(0.45)
    finally:
        await session.close()
        await engine.dispose()


@pytest.mark.asyncio
async def test_extract_identity_preserves_multiple_contacts(monkeypatch) -> None:
    """Contract-style document with seller + buyer + delivery contacts → all
    three land on the draft, in order."""

    async def fake_call_claude(messages, *, purpose, session, **kwargs):
        return _make_response(
            {
                "customer": {
                    "full_name": "甲方有限公司",
                    "short_name": None,
                    "address": None,
                    "tax_id": None,
                },
                "contacts": [
                    {
                        "name": "张三",
                        "title": "销售",
                        "mobile": "13800000001",
                        "role": "seller",
                    },
                    {
                        "name": "李四",
                        "title": "采购",
                        "mobile": "13800000002",
                        "role": "buyer",
                    },
                    {
                        "name": "王五",
                        "title": "收货",
                        "mobile": "13800000003",
                        "role": "delivery",
                    },
                ],
                "field_provenance": [],
                "confidence_overall": 0.81,
                "parse_warnings": [],
            }
        )

    monkeypatch.setattr(identity_module, "call_claude", fake_call_claude)

    session, engine = await _make_session()
    try:
        doc = await _make_doc(session, ocr="甲方有限公司 张三 李四 王五")
        draft = await extract_identity(
            session=session,
            document_id=doc.id,
            ocr_text=doc.ocr_text or "",
        )
        await session.commit()

        assert [c.name for c in draft.contacts] == ["张三", "李四", "王五"]
        assert [c.role.value for c in draft.contacts] == ["seller", "buyer", "delivery"]
    finally:
        await session.close()
        await engine.dispose()


# ---------- post-validation paths ----------------------------------------


@pytest.mark.asyncio
async def test_extract_identity_warns_on_bad_mobile(monkeypatch) -> None:
    """LLM returned a mobile that doesn't match Chinese mobile pattern →
    parse_warnings flagged, value preserved."""

    async def fake_call_claude(messages, *, purpose, session, **kwargs):
        return _make_response(
            {
                "customer": None,
                "contacts": [
                    {
                        "name": "张三",
                        "mobile": "12345",  # obviously bad
                        "role": "other",
                    }
                ],
                "field_provenance": [],
                "confidence_overall": 0.5,
                "parse_warnings": [],
            }
        )

    monkeypatch.setattr(identity_module, "call_claude", fake_call_claude)

    session, engine = await _make_session()
    try:
        doc = await _make_doc(session, ocr="张三 12345")
        draft = await extract_identity(
            session=session,
            document_id=doc.id,
            ocr_text=doc.ocr_text or "",
        )
        await session.commit()

        # Value not rewritten — reviewer needs to see the raw OCR string.
        assert draft.contacts[0].mobile == "12345"
        # But a warning is surfaced for the UI to highlight.
        assert any(
            "contacts[0].mobile" in w and "12345" in w for w in draft.parse_warnings
        )
    finally:
        await session.close()
        await engine.dispose()


@pytest.mark.asyncio
async def test_extract_identity_warns_on_bad_email(monkeypatch) -> None:
    """LLM returned a malformed email → parse_warnings flagged, value preserved."""

    async def fake_call_claude(messages, *, purpose, session, **kwargs):
        return _make_response(
            {
                "customer": None,
                "contacts": [
                    {
                        "name": "李四",
                        "email": "not-an-email",
                        "role": "other",
                    }
                ],
                "field_provenance": [],
                "confidence_overall": 0.5,
                "parse_warnings": [],
            }
        )

    monkeypatch.setattr(identity_module, "call_claude", fake_call_claude)

    session, engine = await _make_session()
    try:
        doc = await _make_doc(session, ocr="李四 not-an-email")
        draft = await extract_identity(
            session=session,
            document_id=doc.id,
            ocr_text=doc.ocr_text or "",
        )
        await session.commit()

        assert draft.contacts[0].email == "not-an-email"
        assert any(
            "contacts[0].email" in w and "not-an-email" in w
            for w in draft.parse_warnings
        )
    finally:
        await session.close()
        await engine.dispose()


# ---------- progress callbacks -------------------------------------------


@pytest.mark.asyncio
async def test_extract_identity_emits_progress(monkeypatch) -> None:
    """Both ``identity_extract`` (start) and ``identity_done`` (finish) stages
    must reach the progress callback."""

    async def fake_call_claude(messages, *, purpose, session, **kwargs):
        return _make_response(
            {
                "customer": None,
                "contacts": [],
                "field_provenance": [],
                "confidence_overall": 0.1,
                "parse_warnings": [],
            }
        )

    monkeypatch.setattr(identity_module, "call_claude", fake_call_claude)

    session, engine = await _make_session()
    progress_events: list[tuple[str, str]] = []

    async def progress(stage: str, message: str) -> None:
        progress_events.append((stage, message))

    try:
        doc = await _make_doc(session, ocr="just a memo")
        await extract_identity(
            session=session,
            document_id=doc.id,
            ocr_text=doc.ocr_text or "",
            progress=progress,
        )
        await session.commit()

        stages = [stage for stage, _ in progress_events]
        assert "identity_extract" in stages
        assert "identity_done" in stages
    finally:
        await session.close()
        await engine.dispose()
