"""Audio transcription seam.

Voice clips captured in the browser flow through ingest as a first-class file
type. Turning audio into text needs a speech-to-text provider; none is wired by
default, so this degrades gracefully — the clip is stored and a clear "未配置"
warning is surfaced — instead of failing the upload. Set TRANSCRIPTION_PROVIDER
(plus the matching credentials) to enable a real provider later.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from yunwei_win.config import settings

_UNCONFIGURED_WARNING = (
    "语音转写未配置：已保存录音，但暂未转写。"
    "配置 TRANSCRIPTION_PROVIDER 后即可自动转写。"
)


@dataclass
class TranscriptionResult:
    text: str
    provider: str
    warnings: list[str] = field(default_factory=list)


async def transcribe_audio(
    data: bytes,
    *,
    content_type: str | None = None,
    filename: str | None = None,
) -> TranscriptionResult:
    """Transcribe audio bytes to text.

    Degrades to empty text + an actionable warning when no STT provider is
    configured, so an audio upload never hard-fails.
    """

    provider = (settings.transcription_provider or "none").strip().lower()
    if provider in ("", "none"):
        return TranscriptionResult("", "none", [_UNCONFIGURED_WARNING])
    # Future providers (whisper / mistral voxtral / …) dispatch here.
    return TranscriptionResult("", provider, [f"语音转写提供方 “{provider}” 尚未实现。"])
