"""MinerU OCR client.

Two upstream modes:

  1. Cloud (preferred) — `MINERU_API_TOKEN` set. Goes through mineru.net's
     v4 batch flow: ask for an upload URL, PUT the file, poll for the
     parse result, download the resulting zip, return the markdown inside.

  2. Local sidecar — `MINERU_BASE_URL` set (e.g. http://mineru:8765). Posts
     directly to mineru-api's `/file_parse` synchronous endpoint.

Both return concatenated markdown so the caller (contract pipeline) can
hand it to the LLM as plain text. Empty string means "no MinerU
configured", caller should degrade. `MineruUnavailable` raises on real
failures (network, auth, server error, timeout, parse failure).
"""

from __future__ import annotations

import asyncio
import io
import logging
import zipfile
from typing import Any

import httpx

from yinhu_brain.config import settings

logger = logging.getLogger(__name__)


class MineruUnavailable(Exception):
    """MinerU upstream isn't reachable / parse failed. Caller decides
    whether to fall back to vision-only or surface the error."""


# ---------- shared response → markdown -------------------------------------

def _extract_markdown_from_payload(payload: dict[str, Any]) -> str:
    """Pull markdown out of mineru-api's sidecar response shape."""
    results = payload.get("results")
    if isinstance(results, dict):
        chunks: list[str] = []
        for val in results.values():
            if isinstance(val, dict):
                md = val.get("md_content") or val.get("markdown") or ""
                if md:
                    chunks.append(md)
        return "\n\n".join(chunks)
    if isinstance(results, list):
        chunks = [
            r.get("md_content") or r.get("markdown") or ""
            for r in results
            if isinstance(r, dict)
        ]
        return "\n\n".join(c for c in chunks if c)
    if isinstance(payload.get("md_content"), str):
        return payload["md_content"]
    return ""


def _markdown_from_zip(zip_bytes: bytes) -> str:
    """mineru.net cloud returns a zip with full.md / *.md plus images.
    Pull every .md file and concat; fall back to any text-ish file."""
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        md_names = [n for n in zf.namelist() if n.lower().endswith(".md")]
        if not md_names:
            raise MineruUnavailable(
                f"mineru zip had no .md files (got: {zf.namelist()[:10]})"
            )
        # Prefer full.md / output.md / something with 'full' in it.
        md_names.sort(key=lambda n: (0 if "full" in n.lower() else 1, n))
        chunks: list[str] = []
        for name in md_names:
            try:
                chunks.append(zf.read(name).decode("utf-8"))
            except UnicodeDecodeError:
                chunks.append(zf.read(name).decode("utf-8", errors="replace"))
        return "\n\n".join(chunks)


# ---------- cloud (mineru.net) ---------------------------------------------

async def _cloud_parse(pdf_bytes: bytes, filename: str) -> str:
    base = settings.mineru_cloud_base_url.rstrip("/")
    token = settings.mineru_api_token.strip()
    timeout = httpx.Timeout(
        connect=10.0,
        read=120.0,
        write=120.0,
        pool=10.0,
    )
    headers = {"Authorization": f"Bearer {token}"}
    deadline_seconds = float(settings.mineru_request_timeout_seconds)

    async with httpx.AsyncClient(timeout=timeout, headers=headers) as client:
        # 1. Request batch + upload URL.
        try:
            r = await client.post(
                f"{base}/api/v4/file-urls/batch",
                json={
                    "language": "ch",
                    "enable_formula": False,
                    "enable_table": True,
                    "files": [
                        {"name": filename, "is_ocr": True, "data_id": filename}
                    ],
                },
            )
        except (httpx.ConnectError, httpx.TimeoutException) as exc:
            raise MineruUnavailable(f"cloud unreachable: {exc!r}") from exc

        if r.status_code != 200:
            raise MineruUnavailable(
                f"cloud /file-urls/batch HTTP {r.status_code}: {r.text[:300]}"
            )

        try:
            data = r.json()
        except Exception as exc:
            raise MineruUnavailable(f"cloud non-JSON: {r.text[:200]}") from exc

        # Standard envelope: {"code":0,"data":{"batch_id":"...","file_urls":[...]}}
        if data.get("code") not in (0, 200, "0", None):
            raise MineruUnavailable(
                f"cloud batch reject: code={data.get('code')} msg={data.get('msg') or data.get('message')}"
            )
        body = data.get("data") or data
        batch_id = body.get("batch_id") or body.get("batchId")
        upload_urls = body.get("file_urls") or body.get("fileUrls") or []
        if not batch_id or not upload_urls:
            raise MineruUnavailable(
                f"cloud batch response missing fields: keys={list(body.keys())}"
            )

        # 2. PUT the PDF to its presigned URL. Send no extra headers — OSS
        # signs specific headers and any mismatch (incl. Content-Type) gives
        # back SignatureDoesNotMatch. The presigned URL carries its own auth
        # in the query string, so the bearer token is also explicitly
        # excluded by using a separate client.
        async with httpx.AsyncClient(timeout=timeout) as upload_client:
            try:
                ur = await upload_client.put(upload_urls[0], content=pdf_bytes)
            except (httpx.ConnectError, httpx.TimeoutException) as exc:
                raise MineruUnavailable(
                    f"presigned PUT failed: {exc!r}"
                ) from exc
            if ur.status_code not in (200, 201, 204):
                raise MineruUnavailable(
                    f"presigned PUT HTTP {ur.status_code}: {ur.text[:200]}"
                )

        # 3. Poll for the parse result.
        poll_url = f"{base}/api/v4/extract-results/batch/{batch_id}"
        poll_interval = 5.0
        elapsed = 0.0
        zip_url: str | None = None
        last_state: str | None = None

        while elapsed < deadline_seconds:
            await asyncio.sleep(poll_interval)
            elapsed += poll_interval
            try:
                pr = await client.get(poll_url)
            except (httpx.ConnectError, httpx.TimeoutException) as exc:
                logger.warning("mineru poll connect issue, retrying: %s", exc)
                continue
            if pr.status_code != 200:
                logger.warning(
                    "mineru poll HTTP %d body=%s", pr.status_code, pr.text[:200]
                )
                continue
            try:
                pdata = pr.json()
            except Exception:
                continue
            pbody = pdata.get("data") or pdata
            results = (
                pbody.get("extract_result")
                or pbody.get("extractResult")
                or pbody.get("results")
                or []
            )
            if not results:
                continue
            first = results[0]
            last_state = (first.get("state") or "").lower()
            if last_state in ("done", "success", "succeed", "succeeded"):
                zip_url = (
                    first.get("full_zip_url")
                    or first.get("zip_url")
                    or first.get("fullZipUrl")
                )
                if not zip_url:
                    # Maybe cloud inlines markdown
                    inline_md = first.get("md_content") or first.get("markdown")
                    if inline_md:
                        return inline_md
                    raise MineruUnavailable(
                        f"cloud done but no result URL: keys={list(first.keys())}"
                    )
                break
            if last_state in ("failed", "error", "fail"):
                raise MineruUnavailable(
                    f"cloud parse failed: {first.get('err_msg') or first.get('errMsg') or first}"
                )
            # else: pending / running / queued — keep polling

        if zip_url is None:
            raise MineruUnavailable(
                f"cloud parse timed out after {deadline_seconds}s "
                f"(last state={last_state!r})"
            )

        # 4. Fetch zip + extract markdown.
        async with httpx.AsyncClient(timeout=timeout) as dl:
            zr = await dl.get(zip_url)
            if zr.status_code != 200:
                raise MineruUnavailable(
                    f"zip download HTTP {zr.status_code}: {zr.text[:200]}"
                )
            md = _markdown_from_zip(zr.content)
            logger.info(
                "mineru.net parsed %s in ~%.0fs (md %d chars)",
                filename, elapsed, len(md),
            )
            return md


# ---------- local sidecar ---------------------------------------------------

async def _sidecar_parse(pdf_bytes: bytes, filename: str) -> str:
    base_url = settings.mineru_base_url.strip().rstrip("/")
    timeout = httpx.Timeout(
        connect=10.0,
        read=float(settings.mineru_request_timeout_seconds),
        write=120.0,
        pool=10.0,
    )
    async with httpx.AsyncClient(base_url=base_url, timeout=timeout) as client:
        try:
            resp = await client.post(
                "/file_parse",
                files={"files": (filename, pdf_bytes, "application/pdf")},
                data={
                    "backend": "pipeline",
                    "parse_method": "auto",
                    "lang_list": "ch",
                    "return_md": "true",
                    "table_enable": "true",
                    "formula_enable": "false",
                    "image_analysis": "false",
                },
            )
        except (httpx.ConnectError, httpx.ReadTimeout) as exc:
            raise MineruUnavailable(
                f"sidecar unreachable at {base_url}: {exc!r}"
            ) from exc

    if resp.status_code >= 500:
        raise MineruUnavailable(
            f"sidecar 5xx {resp.status_code}: {resp.text[:300]}"
        )
    if resp.status_code >= 400:
        raise MineruUnavailable(
            f"sidecar 4xx {resp.status_code}: {resp.text[:300]}"
        )

    try:
        payload = resp.json()
    except Exception as exc:
        raise MineruUnavailable(
            f"sidecar non-JSON: {resp.text[:200]}"
        ) from exc

    md = _extract_markdown_from_payload(payload)
    logger.info("mineru sidecar parsed %s: %d chars", filename, len(md))
    return md


# ---------- public entry ----------------------------------------------------

async def parse_pdf_to_markdown(
    pdf_bytes: bytes, filename: str = "doc.pdf"
) -> str:
    """Route to cloud (token set) or sidecar (URL set), return markdown."""
    if settings.mineru_api_token.strip():
        return await _cloud_parse(pdf_bytes, filename)
    if settings.mineru_base_url.strip():
        return await _sidecar_parse(pdf_bytes, filename)
    return ""
