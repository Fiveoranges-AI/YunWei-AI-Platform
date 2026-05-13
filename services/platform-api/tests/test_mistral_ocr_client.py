from __future__ import annotations

import pytest

from yunwei_win.config import settings
from yunwei_win.services import mistral_ocr_client


class _FakeResponse:
    status_code = 200
    text = ""

    def json(self):
        return {
            "pages": [
                {"index": 1, "markdown": "第二页"},
                {"index": 0, "markdown": "第一页"},
            ],
            "model": "mistral-ocr-latest",
        }


class _FakeAsyncClient:
    def __init__(self, *, base_url=None, timeout=None):
        self.base_url = base_url
        self.timeout = timeout

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return None

    async def post(self, path, *, json, headers):
        _FakeAsyncClient.last_request = {
            "path": path,
            "json": json,
            "headers": headers,
            "base_url": self.base_url,
        }
        return _FakeResponse()


@pytest.mark.asyncio
async def test_mistral_ocr_pdf_uses_data_url(monkeypatch) -> None:
    monkeypatch.setattr(settings, "mistral_api_key", "test-key")
    monkeypatch.setattr(settings, "mistral_base_url", "https://api.mistral.ai")
    monkeypatch.setattr(mistral_ocr_client.httpx, "AsyncClient", _FakeAsyncClient)

    md = await mistral_ocr_client.parse_pdf_to_markdown(b"%PDF", "contract.pdf")

    req = _FakeAsyncClient.last_request
    assert req["path"] == "/v1/ocr"
    assert req["headers"]["Authorization"] == "Bearer test-key"
    assert req["json"]["model"] == "mistral-ocr-latest"
    assert req["json"]["table_format"] == "markdown"
    assert req["json"]["document"]["type"] == "document_url"
    assert req["json"]["document"]["document_url"].startswith("data:application/pdf;base64,")
    assert "第一页" in md
    assert md.index("第一页") < md.index("第二页")


@pytest.mark.asyncio
async def test_mistral_ocr_image_uses_image_data_url(monkeypatch) -> None:
    monkeypatch.setattr(settings, "mistral_api_key", "test-key")
    monkeypatch.setattr(mistral_ocr_client.httpx, "AsyncClient", _FakeAsyncClient)

    await mistral_ocr_client.parse_image_to_markdown(
        b"image-bytes",
        "card.png",
        "image/png",
    )

    req = _FakeAsyncClient.last_request
    assert "table_format" not in req["json"]
    assert req["json"]["document"]["type"] == "image_url"
    assert req["json"]["document"]["image_url"].startswith("data:image/png;base64,")
