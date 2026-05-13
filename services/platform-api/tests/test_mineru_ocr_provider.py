"""Tests for ``MineruPreciseOcrProvider``.

Covers the MinerU 精准解析 signed-upload + poll + zip-download flow:

- happy path: POST file-urls/batch → PUT bytes → poll until ``state=done`` →
  GET full_zip_url → extract ``full.md``
- missing token raises ``OcrUnavailable``
- non-zero MinerU response code raises ``OcrUnavailable`` with msg + trace_id
- ``state == "failed"`` raises ``OcrUnavailable`` with err_msg
- polling deadline exhausted raises ``OcrUnavailable``
- result zip without ``full.md`` raises ``OcrUnavailable``

All HTTP calls are mocked with ``respx``. No live network to mineru.net.

The project autouse fixture wants Postgres + Redis; we override with a no-op
because these tests don't touch any DB.
"""

from __future__ import annotations

import io
import zipfile

import httpx
import pytest
import respx


# Override the project-level autouse fixture so we don't need Postgres.
@pytest.fixture(autouse=True)
def _clean_state():  # noqa: PT004 — yield-only no-op replacement fixture
    yield


from yunwei_win.services.ocr.base import OcrInput, OcrUnavailable
from yunwei_win.services.ocr.mineru import MineruPreciseOcrProvider


def _zip_bytes(files: dict[str, str]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, content in files.items():
            zf.writestr(name, content)
    return buf.getvalue()


def _ocr_input(filename: str = "doc.pdf") -> OcrInput:
    return OcrInput(
        file_bytes=b"%PDF-1.4 fake",
        stored_path=f"/tmp/{filename}",
        filename=filename,
        content_type="application/pdf",
        modality="pdf",
        source_hint="file",
    )


def _set_mineru_settings(monkeypatch, **overrides) -> None:
    from yunwei_win.services.ocr import mineru as mineru_module

    defaults = {
        "mineru_api_token": "test-token",
        "mineru_base_url": "https://mineru.net",
        "mineru_poll_interval_seconds": 0,
        "mineru_timeout_seconds": 5,
    }
    defaults.update(overrides)
    for key, value in defaults.items():
        monkeypatch.setattr(mineru_module.settings, key, value)


@pytest.mark.asyncio
async def test_parse_uploads_polls_and_returns_full_markdown(monkeypatch):
    _set_mineru_settings(monkeypatch)

    with respx.mock(assert_all_called=True) as mock:
        apply_route = mock.post(
            "https://mineru.net/api/v4/file-urls/batch"
        ).mock(
            return_value=httpx.Response(
                200,
                json={
                    "code": 0,
                    "msg": "ok",
                    "trace_id": "trace-apply",
                    "data": {
                        "batch_id": "batch-1",
                        "file_urls": ["https://upload.example.com/doc.pdf"],
                    },
                },
            )
        )
        upload_route = mock.put(
            "https://upload.example.com/doc.pdf"
        ).mock(return_value=httpx.Response(200))
        # First poll returns pending, second poll returns done.
        poll_route = mock.get(
            "https://mineru.net/api/v4/extract-results/batch/batch-1"
        ).mock(
            side_effect=[
                httpx.Response(
                    200,
                    json={
                        "code": 0,
                        "msg": "ok",
                        "trace_id": "trace-poll-1",
                        "data": {
                            "batch_id": "batch-1",
                            "extract_result": [
                                {"file_name": "doc.pdf", "state": "pending"}
                            ],
                        },
                    },
                ),
                httpx.Response(
                    200,
                    json={
                        "code": 0,
                        "msg": "ok",
                        "trace_id": "trace-poll-2",
                        "data": {
                            "batch_id": "batch-1",
                            "extract_result": [
                                {
                                    "file_name": "doc.pdf",
                                    "state": "done",
                                    "err_msg": "",
                                    "full_zip_url": "https://cdn.example.com/result.zip",
                                }
                            ],
                        },
                    },
                ),
            ]
        )
        zip_route = mock.get("https://cdn.example.com/result.zip").mock(
            return_value=httpx.Response(
                200,
                content=_zip_bytes(
                    {"full.md": "# Parsed\n\n甲方：测试客户有限公司"}
                ),
            )
        )

        result = await MineruPreciseOcrProvider().parse(_ocr_input())

    assert apply_route.called
    assert upload_route.called
    assert poll_route.call_count == 2
    assert zip_route.called

    # Apply request: bearer token + filename in payload.
    apply_request = apply_route.calls[0].request
    assert apply_request.headers["Authorization"] == "Bearer test-token"
    import json as _json
    apply_body = _json.loads(apply_request.content.decode("utf-8"))
    assert apply_body["files"][0]["name"] == "doc.pdf"
    # Settings flags forwarded.
    assert apply_body["enable_table"] is True
    assert apply_body["enable_formula"] is True
    assert apply_body["is_ocr"] is True
    assert apply_body["language"] == "ch"
    assert apply_body["model_version"] == "vlm"

    # Upload PUT carries the file bytes and no Authorization header.
    upload_request = upload_route.calls[0].request
    assert upload_request.content == b"%PDF-1.4 fake"
    assert "Authorization" not in upload_request.headers

    assert result.provider == "mineru"
    assert result.markdown == "# Parsed\n\n甲方：测试客户有限公司"
    assert result.metadata["batch_id"] == "batch-1"
    # trace_id from the apply-upload or final-poll response is recorded so
    # operators can correlate with MinerU's dashboard.
    assert "trace_id" in result.metadata


@pytest.mark.asyncio
async def test_parse_raises_when_token_is_missing(monkeypatch):
    _set_mineru_settings(monkeypatch, mineru_api_token="")

    with pytest.raises(OcrUnavailable, match="mineru_api_token is not configured"):
        await MineruPreciseOcrProvider().parse(_ocr_input())


@pytest.mark.asyncio
async def test_parse_raises_on_non_zero_code_with_trace_id(monkeypatch):
    _set_mineru_settings(monkeypatch)

    with respx.mock() as mock:
        mock.post("https://mineru.net/api/v4/file-urls/batch").mock(
            return_value=httpx.Response(
                200,
                json={
                    "code": 401,
                    "msg": "invalid token",
                    "trace_id": "trace-err",
                    "data": None,
                },
            )
        )

        with pytest.raises(OcrUnavailable) as exc_info:
            await MineruPreciseOcrProvider().parse(_ocr_input())

    msg = str(exc_info.value)
    assert "401" in msg
    assert "invalid token" in msg
    assert "trace-err" in msg


@pytest.mark.asyncio
async def test_parse_raises_on_failed_state(monkeypatch):
    _set_mineru_settings(monkeypatch)

    with respx.mock() as mock:
        mock.post("https://mineru.net/api/v4/file-urls/batch").mock(
            return_value=httpx.Response(
                200,
                json={
                    "code": 0,
                    "msg": "ok",
                    "data": {
                        "batch_id": "batch-1",
                        "file_urls": ["https://upload.example.com/doc.pdf"],
                    },
                },
            )
        )
        mock.put("https://upload.example.com/doc.pdf").mock(
            return_value=httpx.Response(200)
        )
        mock.get(
            "https://mineru.net/api/v4/extract-results/batch/batch-1"
        ).mock(
            return_value=httpx.Response(
                200,
                json={
                    "code": 0,
                    "msg": "ok",
                    "data": {
                        "extract_result": [
                            {"state": "failed", "err_msg": "bad file"}
                        ]
                    },
                },
            )
        )

        with pytest.raises(OcrUnavailable, match="bad file") as exc_info:
            await MineruPreciseOcrProvider().parse(_ocr_input())

    assert "mineru extraction failed" in str(exc_info.value)


@pytest.mark.asyncio
async def test_parse_raises_on_polling_timeout(monkeypatch):
    # 0-second deadline → first poll already past deadline → timeout error.
    _set_mineru_settings(
        monkeypatch,
        mineru_poll_interval_seconds=0,
        mineru_timeout_seconds=0,
    )

    with respx.mock() as mock:
        mock.post("https://mineru.net/api/v4/file-urls/batch").mock(
            return_value=httpx.Response(
                200,
                json={
                    "code": 0,
                    "msg": "ok",
                    "data": {
                        "batch_id": "batch-1",
                        "file_urls": ["https://upload.example.com/doc.pdf"],
                    },
                },
            )
        )
        mock.put("https://upload.example.com/doc.pdf").mock(
            return_value=httpx.Response(200)
        )
        mock.get(
            "https://mineru.net/api/v4/extract-results/batch/batch-1"
        ).mock(
            return_value=httpx.Response(
                200,
                json={
                    "code": 0,
                    "msg": "ok",
                    "data": {
                        "extract_result": [
                            {"state": "pending", "err_msg": ""}
                        ]
                    },
                },
            )
        )

        with pytest.raises(OcrUnavailable, match="mineru polling timed out"):
            await MineruPreciseOcrProvider().parse(_ocr_input())


@pytest.mark.asyncio
async def test_parse_raises_when_zip_missing_full_md(monkeypatch):
    _set_mineru_settings(monkeypatch)

    with respx.mock() as mock:
        mock.post("https://mineru.net/api/v4/file-urls/batch").mock(
            return_value=httpx.Response(
                200,
                json={
                    "code": 0,
                    "msg": "ok",
                    "data": {
                        "batch_id": "batch-1",
                        "file_urls": ["https://upload.example.com/doc.pdf"],
                    },
                },
            )
        )
        mock.put("https://upload.example.com/doc.pdf").mock(
            return_value=httpx.Response(200)
        )
        mock.get(
            "https://mineru.net/api/v4/extract-results/batch/batch-1"
        ).mock(
            return_value=httpx.Response(
                200,
                json={
                    "code": 0,
                    "msg": "ok",
                    "data": {
                        "extract_result": [
                            {
                                "state": "done",
                                "full_zip_url": "https://cdn.example.com/result.zip",
                            }
                        ]
                    },
                },
            )
        )
        mock.get("https://cdn.example.com/result.zip").mock(
            return_value=httpx.Response(
                200, content=_zip_bytes({"other.md": "no full"})
            )
        )

        with pytest.raises(OcrUnavailable, match="missing full.md"):
            await MineruPreciseOcrProvider().parse(_ocr_input())
