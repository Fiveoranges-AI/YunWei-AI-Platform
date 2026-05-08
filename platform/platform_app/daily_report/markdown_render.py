"""Markdown → HTML for the daily report dashboard.

CommonMark via markdown-it-py with html: False so any inline <script>/<iframe>
the LLM might emit becomes literal text, not executable HTML.
"""
from __future__ import annotations
from markdown_it import MarkdownIt

_MD = MarkdownIt("commonmark", {"html": False, "linkify": True, "breaks": False})


def render(markdown_source: str) -> str:
    """Render trusted-but-defensive markdown. Strips raw HTML."""
    return _MD.render(markdown_source)
