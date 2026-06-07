"""Slice ④ — audio detection + transcription seam (DB-free unit tests)."""

import pytest

from yunwei_win.services.schema_ingest.file_type import detect_source_type
from yunwei_win.services.schema_ingest.parsers.transcribe import TranscribeParser
from yunwei_win.services.transcription import transcribe_audio


@pytest.fixture(autouse=True)
def _clean_state():
    # Override conftest's DB-truncating autouse fixture (same name).
    yield


@pytest.mark.parametrize(
    "filename,content_type",
    [
        ("recording.webm", "audio/webm"),
        ("voice.m4a", "audio/mp4"),
        ("memo.mp3", None),  # by extension when content-type is absent
        ("clip.ogg", "audio/ogg"),
    ],
)
def test_audio_routes_to_transcribe(filename, content_type):
    d = detect_source_type(
        filename=filename, content_type=content_type, source_hint="file"
    )
    assert d.source_type == "audio"
    assert d.parser_provider == "transcribe"
    assert d.extractor_provider == "deepseek"


def test_non_audio_is_unaffected():
    d = detect_source_type(
        filename="contract.pdf", content_type="application/pdf", source_hint="file"
    )
    assert d.source_type == "pdf"
    assert d.parser_provider == "landingai"


@pytest.mark.asyncio
async def test_transcription_degrades_without_provider():
    res = await transcribe_audio(
        b"\x00\x01fake-audio", content_type="audio/webm", filename="r.webm"
    )
    assert res.text == ""
    assert res.provider == "none"
    assert res.warnings and "未配置" in res.warnings[0]


@pytest.mark.asyncio
async def test_transcribe_parser_surfaces_warning(tmp_path):
    p = tmp_path / "r.webm"
    p.write_bytes(b"\x00\x01\x02")
    art = await TranscribeParser().parse_file(
        p, filename="r.webm", content_type="audio/webm", source_type="audio"
    )
    assert art.provider == "transcribe"
    assert art.markdown == ""
    assert art.metadata.get("warnings")
