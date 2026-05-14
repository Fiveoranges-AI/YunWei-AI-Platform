from __future__ import annotations

import pytest

from yunwei_win.services.schema_ingest.file_type import detect_source_type


@pytest.fixture(autouse=True)
def _clean_state():
    yield


@pytest.mark.parametrize(
    (
        "filename",
        "content_type",
        "source_hint",
        "expected_source",
        "expected_parser",
        "expected_extractor",
    ),
    [
        ("contract.pdf", "application/pdf", "file", "pdf", "landingai", "landingai"),
        ("scan.png", "image/png", "file", "image", "landingai", "landingai"),
        (
            "deck.pptx",
            "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            "file",
            "pptx",
            "landingai",
            "landingai",
        ),
        ("note.txt", "text/plain", "file", "text", "text", "deepseek"),
        ("note.md", "text/markdown", "file", "text", "text", "deepseek"),
        (
            "contacts.docx",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "file",
            "docx",
            "docx",
            "deepseek",
        ),
        (
            "quote.xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "file",
            "spreadsheet",
            "spreadsheet",
            "deepseek",
        ),
        (
            "quote.xls",
            "application/vnd.ms-excel",
            "file",
            "spreadsheet",
            "spreadsheet",
            "deepseek",
        ),
        ("quote.csv", "text/csv", "file", "spreadsheet", "spreadsheet", "deepseek"),
        ("pasted.txt", "text/plain", "pasted_text", "text", "text", "deepseek"),
    ],
)
def test_detect_source_type_routes_to_parser_and_extractor(
    filename,
    content_type,
    source_hint,
    expected_source,
    expected_parser,
    expected_extractor,
):
    detected = detect_source_type(
        filename=filename, content_type=content_type, source_hint=source_hint
    )
    assert detected.source_type == expected_source
    assert detected.parser_provider == expected_parser
    assert detected.extractor_provider == expected_extractor


def test_detect_source_type_rejects_unsupported_binary():
    with pytest.raises(ValueError, match="unsupported file type"):
        detect_source_type(
            filename="archive.zip", content_type="application/zip", source_hint="file"
        )
