"""Pusher abstraction. Each channel (DingTalk, email, etc.) implements this."""
from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass
from ..storage import Subscription


@dataclass
class PushResult:
    success: bool
    error: str | None


class Pusher(ABC):
    """One implementation per push channel."""

    @abstractmethod
    async def push(
        self, *,
        subscription: Subscription,
        markdown_body: str,
        link_url: str,
        title: str,
    ) -> PushResult: ...
