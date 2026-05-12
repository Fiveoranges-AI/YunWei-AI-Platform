"""OCR provider contracts.

The OCR layer normalizes external parsers (Mistral, MinerU, etc.) into a
single internal shape so the ingest orchestrator does not branch per provider.
Providers produce markdown/text; they do not decide which business schema
applies.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Protocol


@dataclass
class OcrInput:
    file_bytes: bytes
    stored_path: str
    filename: str
    content_type: str | None
    modality: Literal["image", "pdf", "office"]
    source_hint: Literal["file", "camera"]


@dataclass
class OcrResult:
    markdown: str
    provider: str
    metadata: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)


class OcrUnavailable(RuntimeError):
    """Raised when an OCR provider cannot service a request.

    Examples: missing API token, upstream failure, timeout, or a response that
    cannot be parsed. Callers should treat this as an actionable config /
    upstream error rather than a generic exception.
    """


class OcrProvider(Protocol):
    async def parse(self, input: OcrInput) -> OcrResult: ...
