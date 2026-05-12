"""Worker-side tests: ``process_ingest_job`` drives an IngestJob row through
``queued -> running -> extracted``, with progress callbacks updating stage.

We stub ``auto_ingest`` (the heavy auto-flow already has full coverage in
``test_ingest_auto_flow.py``) and stub the Redis-backed enterprise lookup
helper. The real exercise here is the state-machine transitions on the
``IngestJob`` row plus the cancel and failure paths.
"""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _clean_state():  # noqa: PT004 — yield-only override
    yield


import yinhu_brain.models  # noqa: E402, F401 — register mappers
from sqlalchemy import event, select  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine  # noqa: E402

from yinhu_brain.db import Base  # noqa: E402
from yinhu_brain.models.ingest_job import (  # noqa: E402
    IngestBatch,
    IngestJob,
    IngestJobStage,
    IngestJobStatus,
)
from yinhu_brain.workers import ingest_rq as worker_module  # noqa: E402


async def _make_engine():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")

    @event.listens_for(engine.sync_engine, "connect")
    def _fk_on(dbapi_conn, _record):
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA foreign_keys = ON")
        cur.close()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    return engine


def _patch_engine_routing(monkeypatch, engine):
    """Make ``get_engine_for`` return our SQLite engine and stub the
    Redis-backed enterprise lookup so tests don't need a running Redis."""

    async def fake_get_engine_for(_enterprise_id):
        return engine

    async def fake_ensure_tables(_engine):
        return None

    def fake_lookup(_job_id):
        return "tenant_test"

    monkeypatch.setattr(worker_module, "get_engine_for", fake_get_engine_for)
    monkeypatch.setattr(
        worker_module, "ensure_ingest_job_tables", fake_ensure_tables
    )
    monkeypatch.setattr(worker_module, "lookup_enterprise_for", fake_lookup)


# ---------- happy path ----------------------------------------------------


@pytest.mark.asyncio
async def test_worker_marks_running_then_extracted_on_success(monkeypatch):
    engine = await _make_engine()
    _patch_engine_routing(monkeypatch, engine)

    from yinhu_brain.models import Document, DocumentType
    from yinhu_brain.services.ingest.auto import AutoIngestResult
    from yinhu_brain.services.ingest.merge import MergeCandidates
    from yinhu_brain.services.ingest.unified_schemas import (
        IngestPlan,
        PipelineRoutePlan,
        UnifiedDraft,
    )

    captured_stages: list[str] = []

    async def fake_auto_ingest(**kwargs):
        # Insert a real Document row so the FK on IngestJob.document_id is
        # satisfied when the worker writes the result back.
        sess: AsyncSession = kwargs["session"]
        doc = Document(
            type=DocumentType.text_note,
            file_url="/tmp/fake.txt",
            original_filename="x.pdf",
            file_sha256="0" * 64,
            file_size_bytes=0,
            ocr_text="some text content for the extractor",
        )
        sess.add(doc)
        await sess.flush()
        # Exercise the progress callback to confirm stage transitions land.
        progress = kwargs.get("progress")
        if progress is not None:
            await progress("ocr", "OCR")
            await progress("merge", "merge")
            await progress("auto_done", "done")
            captured_stages.append("called")
        # auto_ingest commits the main session before its fan-out; mirror that
        # here so the Document row is visible to the worker's follow-up session.
        await sess.commit()
        return AutoIngestResult(
            document_id=doc.id,
            plan=IngestPlan(),
            draft=UnifiedDraft(),
            candidates=MergeCandidates(),
            route_plan=PipelineRoutePlan(),
        )

    monkeypatch.setattr(worker_module, "auto_ingest", fake_auto_ingest)

    try:
        async with AsyncSession(engine, expire_on_commit=False) as session:
            batch = IngestBatch(enterprise_id="tenant_test", total_jobs=1)
            session.add(batch)
            await session.flush()
            job = IngestJob(
                batch_id=batch.id,
                enterprise_id="tenant_test",
                original_filename="x.pdf",
                content_type="application/pdf",
                source_hint="file",
                staged_file_url=None,
                text_content="some text content for the extractor",
                status=IngestJobStatus.queued,
            )
            session.add(job)
            await session.commit()
            job_id = str(job.id)

        await worker_module.process_ingest_job(job_id)

        async with AsyncSession(engine, expire_on_commit=False) as session:
            j = (await session.execute(select(IngestJob))).scalar_one()
            assert j.status == IngestJobStatus.extracted
            assert j.stage == IngestJobStage.done
            assert j.started_at is not None
            assert j.finished_at is not None
            assert j.result_json is not None
            assert "draft" in j.result_json
            assert "plan" in j.result_json
            assert captured_stages == ["called"]
    finally:
        await engine.dispose()


# ---------- failure path --------------------------------------------------


@pytest.mark.asyncio
async def test_worker_records_failure_on_exception(monkeypatch):
    engine = await _make_engine()
    _patch_engine_routing(monkeypatch, engine)

    async def boom_auto_ingest(**_kwargs):
        raise RuntimeError("simulated extraction blow up")

    monkeypatch.setattr(worker_module, "auto_ingest", boom_auto_ingest)

    try:
        async with AsyncSession(engine, expire_on_commit=False) as session:
            batch = IngestBatch(enterprise_id="tenant_test", total_jobs=1)
            session.add(batch)
            await session.flush()
            job = IngestJob(
                batch_id=batch.id,
                enterprise_id="tenant_test",
                original_filename="x.pdf",
                content_type="application/pdf",
                source_hint="pasted_text",
                text_content="t",
                status=IngestJobStatus.queued,
            )
            session.add(job)
            await session.commit()
            job_id = str(job.id)

        await worker_module.process_ingest_job(job_id)

        async with AsyncSession(engine, expire_on_commit=False) as session:
            j = (await session.execute(select(IngestJob))).scalar_one()
            assert j.status == IngestJobStatus.failed
            assert j.error_message is not None
            assert "simulated extraction blow up" in j.error_message
            assert j.finished_at is not None
    finally:
        await engine.dispose()


# ---------- cancel-before-start ------------------------------------------


@pytest.mark.asyncio
async def test_worker_skips_canceled_job(monkeypatch):
    engine = await _make_engine()
    _patch_engine_routing(monkeypatch, engine)

    called = {"n": 0}

    async def fake_auto_ingest(**_kwargs):
        called["n"] += 1
        # Returning None would crash the result-persist step; assert it isn't reached.
        return None

    monkeypatch.setattr(worker_module, "auto_ingest", fake_auto_ingest)

    try:
        async with AsyncSession(engine, expire_on_commit=False) as session:
            batch = IngestBatch(enterprise_id="tenant_test", total_jobs=1)
            session.add(batch)
            await session.flush()
            job = IngestJob(
                batch_id=batch.id,
                enterprise_id="tenant_test",
                original_filename="x.pdf",
                source_hint="pasted_text",
                text_content="t",
                status=IngestJobStatus.canceled,  # already canceled
            )
            session.add(job)
            await session.commit()
            job_id = str(job.id)

        await worker_module.process_ingest_job(job_id)

        assert called["n"] == 0
        async with AsyncSession(engine, expire_on_commit=False) as session:
            j = (await session.execute(select(IngestJob))).scalar_one()
            assert j.status == IngestJobStatus.canceled
            assert j.started_at is None
    finally:
        await engine.dispose()


# ---------- cancel-mid-flight --------------------------------------------


@pytest.mark.asyncio
async def test_worker_honors_mid_flight_cancel(monkeypatch):
    """When a cancel arrives between progress callbacks, the worker should
    abort without writing ``status=extracted`` or ``result_json``.

    We simulate the cancel by flipping the row to ``canceled`` from inside
    the fake ``auto_ingest`` *before* it would otherwise return a result;
    the next progress() invocation reads the new status and raises
    ``_CanceledMidFlight``, which the worker swallows."""

    engine = await _make_engine()
    _patch_engine_routing(monkeypatch, engine)

    async def fake_auto_ingest(**kwargs):
        progress = kwargs["progress"]
        # First boundary lands normally.
        await progress("ocr", "OCR")
        # External actor cancels the job.
        async with AsyncSession(engine, expire_on_commit=False) as s:
            j = (await s.execute(select(IngestJob))).scalar_one()
            j.status = IngestJobStatus.canceled
            await s.commit()
        # Next progress event triggers the mid-flight bailout.
        await progress("merge", "merge")
        # Never reached.
        raise AssertionError("progress should have raised _CanceledMidFlight")

    monkeypatch.setattr(worker_module, "auto_ingest", fake_auto_ingest)

    try:
        async with AsyncSession(engine, expire_on_commit=False) as session:
            batch = IngestBatch(enterprise_id="tenant_test", total_jobs=1)
            session.add(batch)
            await session.flush()
            job = IngestJob(
                batch_id=batch.id,
                enterprise_id="tenant_test",
                original_filename="x.pdf",
                source_hint="pasted_text",
                text_content="t",
                status=IngestJobStatus.queued,
            )
            session.add(job)
            await session.commit()

        await worker_module.process_ingest_job(str(job.id))

        async with AsyncSession(engine, expire_on_commit=False) as session:
            j = (await session.execute(select(IngestJob))).scalar_one()
            assert j.status == IngestJobStatus.canceled
            assert j.result_json is None
    finally:
        await engine.dispose()


# ---------- no enterprise mapping ----------------------------------------


@pytest.mark.asyncio
async def test_worker_aborts_when_no_enterprise_mapping(monkeypatch):
    engine = await _make_engine()

    async def fake_get_engine_for(_eid):  # pragma: no cover — must not run
        raise AssertionError("get_engine_for should not be called")

    monkeypatch.setattr(worker_module, "get_engine_for", fake_get_engine_for)
    monkeypatch.setattr(worker_module, "lookup_enterprise_for", lambda _job_id: None)

    try:
        # The function should return early without raising.
        await worker_module.process_ingest_job(
            "00000000-0000-0000-0000-000000000001"
        )
    finally:
        await engine.dispose()
