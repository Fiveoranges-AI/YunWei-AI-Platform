from __future__ import annotations

import json

import pytest

from yinhu_brain.api.ingest import _stream_with_progress


class _DummySession:
    committed = False
    rolled_back = False

    async def commit(self) -> None:
        self.committed = True

    async def rollback(self) -> None:
        self.rolled_back = True


@pytest.mark.asyncio
async def test_stream_with_progress_emits_stage_events_before_done() -> None:
    session = _DummySession()

    async def work(emit):
        await emit("stored", "原始文件已保存")
        await emit("ocr", "正在 OCR")
        return {"document_id": "doc-1"}

    chunks = [
        json.loads(chunk.decode("utf-8"))
        async for chunk in _stream_with_progress(
            work,
            session=session,
            label="test ingest",
        )
    ]

    assert [chunk["status"] for chunk in chunks] == [
        "progress",
        "progress",
        "done",
    ]
    assert [chunk.get("stage") for chunk in chunks[:2]] == ["stored", "ocr"]
    assert chunks[-1]["document_id"] == "doc-1"
    assert session.committed is True
    assert session.rolled_back is False
