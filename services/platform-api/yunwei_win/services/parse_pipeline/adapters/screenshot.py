"""WeChat screenshot adapter — image → multimodal LLM → candidate JSON.

Always vision-mode; we never run OCR first because WeChat screenshots
embed mixed Chinese + emoji + system UI text that a generic OCR
mis-segments. A multimodal model handles the visual context (sender vs
receiver bubble, timestamps, voice-message placeholders) in one pass.

The shaping pipe is shared with the contract adapter — same
ProviderResult → CandidateJSON translator. Only the inputs differ.
"""

from __future__ import annotations

import base64
import logging
import mimetypes
from pathlib import Path

from yunwei_win.services.parse_pipeline.adapters.contract import _shape_candidate_json
from yunwei_win.services.parse_pipeline.candidate import CandidateJSON
from yunwei_win.services.parse_pipeline.providers.base import (
    ExtractionPayload,
    ExtractionProvider,
)


logger = logging.getLogger(__name__)


async def parse_screenshot(
    *,
    file_path: Path,
    filename: str,
    content_type: str | None,
    provider: ExtractionProvider,
    file_ref: str = "",
    uploaded_by: str | None = None,
) -> CandidateJSON:
    image_b64 = base64.b64encode(file_path.read_bytes()).decode("ascii")
    media_type = (
        content_type
        or mimetypes.guess_type(filename)[0]
        or "image/png"
    )
    payload = ExtractionPayload(
        source_type="wechat_screenshot",
        filename=filename,
        markdown="",
        image_b64=image_b64,
        image_media_type=media_type,
    )
    result = await provider.extract(payload)
    return _shape_candidate_json(
        result,
        source_type="wechat_screenshot",
        file_ref=file_ref or filename,
        uploaded_by=uploaded_by,
    )
