"""MinerU 精准解析 OCR provider.

Implements the signed-upload + poll + zip-download flow against MinerU's
``/api/v4`` endpoints:

1. ``POST /api/v4/file-urls/batch``        — apply for a signed upload URL.
2. ``PUT  <signed file_urls[0]>``          — upload the original file bytes
   (no auth header; the URL is already signed).
3. ``GET  /api/v4/extract-results/batch/{batch_id}`` — poll until the first
   extract_result reports ``state == "done"`` (or ``failed`` / deadline).
4. ``GET  <full_zip_url>``                  — download the result zip and
   read ``full.md`` from it.

All failures surface as :class:`OcrUnavailable` so the orchestrator can treat
provider errors as actionable config/upstream issues rather than generic
exceptions. V1 is poll-only; callback support is intentionally out of scope.
"""

from __future__ import annotations

import asyncio
import io
import time
import zipfile
from typing import Any

import httpx

from yunwei_win.config import settings

from .base import OcrInput, OcrProvider, OcrResult, OcrUnavailable


class MineruPreciseOcrProvider(OcrProvider):
    async def parse(self, input: OcrInput) -> OcrResult:
        token = settings.mineru_api_token.strip()
        if not token:
            raise OcrUnavailable("mineru_api_token is not configured")

        base_url = settings.mineru_base_url.rstrip("/")
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        # Generous timeouts: upload can be slow on large PDFs; reads are short.
        timeout = httpx.Timeout(connect=10.0, read=60.0, write=120.0, pool=10.0)
        warnings: list[str] = []

        async with httpx.AsyncClient(timeout=timeout) as client:
            batch_id, upload_url, apply_trace_id = await self._create_upload_task(
                client=client,
                base_url=base_url,
                headers=headers,
                filename=input.filename,
            )
            await self._upload_file(
                client=client, upload_url=upload_url, file_bytes=input.file_bytes
            )
            result, poll_trace_id = await self._poll_done(
                client=client,
                base_url=base_url,
                headers=headers,
                batch_id=batch_id,
            )
            full_zip_url = str(result.get("full_zip_url") or "")
            markdown = await self._download_full_markdown(
                client=client, full_zip_url=full_zip_url
            )

        return OcrResult(
            markdown=markdown,
            provider="mineru",
            metadata={
                "batch_id": batch_id,
                "trace_id": poll_trace_id or apply_trace_id,
                "full_zip_url": full_zip_url,
                "file_name": result.get("file_name"),
                "state": result.get("state"),
            },
            warnings=warnings,
        )

    async def _create_upload_task(
        self,
        *,
        client: httpx.AsyncClient,
        base_url: str,
        headers: dict[str, str],
        filename: str,
    ) -> tuple[str, str, str | None]:
        payload = {
            "files": [{"name": filename}],
            "model_version": settings.mineru_model_version,
            "language": settings.mineru_language,
            "enable_table": settings.mineru_enable_table,
            "enable_formula": settings.mineru_enable_formula,
            "is_ocr": settings.mineru_is_ocr,
        }
        body = await self._request_json(
            client.post(
                f"{base_url}/api/v4/file-urls/batch",
                headers=headers,
                json=payload,
            )
        )
        data = body.get("data") or {}
        batch_id = data.get("batch_id")
        file_urls = data.get("file_urls") or []
        upload_url = file_urls[0] if file_urls else None
        if not isinstance(batch_id, str) or not isinstance(upload_url, str):
            raise OcrUnavailable(
                "mineru upload task response missing batch_id or file_urls[0]"
            )
        return batch_id, upload_url, body.get("trace_id")

    async def _upload_file(
        self,
        *,
        client: httpx.AsyncClient,
        upload_url: str,
        file_bytes: bytes,
    ) -> None:
        # Signed URL — do NOT send the bearer token header.
        try:
            resp = await client.put(upload_url, content=file_bytes)
        except httpx.HTTPError as exc:
            raise OcrUnavailable(f"mineru upload request failed: {exc!r}") from exc
        if resp.status_code >= 400:
            raise OcrUnavailable(
                f"mineru upload failed HTTP {resp.status_code}: {resp.text[:300]}"
            )

    async def _poll_done(
        self,
        *,
        client: httpx.AsyncClient,
        base_url: str,
        headers: dict[str, str],
        batch_id: str,
    ) -> tuple[dict[str, Any], str | None]:
        timeout_seconds = float(settings.mineru_timeout_seconds)
        deadline = time.monotonic() + timeout_seconds
        interval = float(settings.mineru_poll_interval_seconds)
        last_trace_id: str | None = None
        while True:
            body = await self._request_json(
                client.get(
                    f"{base_url}/api/v4/extract-results/batch/{batch_id}",
                    headers=headers,
                )
            )
            last_trace_id = body.get("trace_id") or last_trace_id
            data = body.get("data") or {}
            results = data.get("extract_result") or []
            result = results[0] if results else {}
            state = result.get("state")
            if state == "done":
                if not result.get("full_zip_url"):
                    raise OcrUnavailable(
                        "mineru done result missing full_zip_url"
                    )
                return result, last_trace_id
            if state == "failed":
                err_msg = result.get("err_msg") or "unknown error"
                raise OcrUnavailable(f"mineru extraction failed: {err_msg}")
            if time.monotonic() >= deadline:
                raise OcrUnavailable(
                    f"mineru polling timed out after {int(timeout_seconds)}s"
                )
            await asyncio.sleep(interval)

    async def _download_full_markdown(
        self,
        *,
        client: httpx.AsyncClient,
        full_zip_url: str,
    ) -> str:
        if not full_zip_url:
            raise OcrUnavailable("mineru result missing full_zip_url")
        try:
            resp = await client.get(full_zip_url)
        except httpx.HTTPError as exc:
            raise OcrUnavailable(
                f"mineru result zip download failed: {exc!r}"
            ) from exc
        if resp.status_code >= 400:
            raise OcrUnavailable(
                f"mineru result zip download failed HTTP {resp.status_code}: "
                f"{resp.text[:300]}"
            )
        try:
            with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
                with zf.open("full.md") as f:
                    return f.read().decode("utf-8").strip()
        except KeyError as exc:
            raise OcrUnavailable(
                "mineru result zip is missing full.md"
            ) from exc
        except zipfile.BadZipFile as exc:
            raise OcrUnavailable(
                "mineru result was not a valid zip file"
            ) from exc

    async def _request_json(self, awaitable) -> dict[str, Any]:
        try:
            resp = await awaitable
        except httpx.HTTPError as exc:
            raise OcrUnavailable(f"mineru request failed: {exc!r}") from exc
        if resp.status_code >= 400:
            raise OcrUnavailable(
                f"mineru HTTP {resp.status_code}: {resp.text[:300]}"
            )
        try:
            body = resp.json()
        except ValueError as exc:
            raise OcrUnavailable(
                f"mineru non-JSON response: {resp.text[:200]}"
            ) from exc
        code = body.get("code")
        if code != 0:
            trace_id = body.get("trace_id")
            msg = body.get("msg")
            raise OcrUnavailable(
                f"mineru returned code={code}: {msg} (trace_id={trace_id})"
            )
        return body
