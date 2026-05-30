"""MockProvider — feeds a canned ProviderResult through the pipeline.

Used by every test so we never burn LLM tokens in CI. Take the canned
result either as a ``ProviderResult`` directly or as a callable that
inspects the payload and returns a tailored response (useful for
asserting the adapter passed the right markdown / image).
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from yunwei_win.services.parse_pipeline.providers.base import (
    ExtractionPayload,
    ExtractionProvider,
    ProviderResult,
)


class MockProvider:
    name = "mock"

    def __init__(
        self,
        result: ProviderResult | Callable[[ExtractionPayload], ProviderResult | Awaitable[ProviderResult]],
    ) -> None:
        self._result = result
        self.calls: list[ExtractionPayload] = []

    async def extract(self, payload: ExtractionPayload) -> ProviderResult:
        self.calls.append(payload)
        result: Any = self._result
        if callable(result):
            result = result(payload)
            if hasattr(result, "__await__"):
                result = await result  # type: ignore[assignment]
        return result


# Type check that MockProvider satisfies the protocol.
_: ExtractionProvider = MockProvider(ProviderResult())  # pragma: no cover
