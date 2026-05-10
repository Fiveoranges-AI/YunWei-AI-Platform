"""Small progress callback helper for streamed ingest endpoints."""

from __future__ import annotations

from collections.abc import Awaitable, Callable


ProgressCallback = Callable[[str, str], Awaitable[None]]


async def emit_progress(
    progress: ProgressCallback | None,
    stage: str,
    message: str,
) -> None:
    if progress is not None:
        await progress(stage, message)
