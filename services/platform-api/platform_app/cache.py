"""Redis-backed TTL cache layer (replaces v1.2 in-memory TTLCache).

Multi-instance safe: any platform-app worker writes/reads the same Redis,
so cache invalidation from admin CLI or another worker is immediately
visible to all.
"""
from __future__ import annotations
import json
from typing import Any
import redis
from .settings import settings

_r = redis.from_url(settings.redis_url, decode_responses=True)


class _Cache:
    def __init__(self, prefix: str, ttl: int) -> None:
        self.prefix = prefix
        self.ttl = ttl

    def _k(self, key: str) -> str:
        return f"{self.prefix}:{key}"

    def get(self, key: str) -> Any | None:
        raw = _r.get(self._k(key))
        return json.loads(raw) if raw else None

    def set(self, key: str, value: Any) -> None:
        _r.set(self._k(key), json.dumps(value, default=str), ex=self.ttl)

    def delete(self, key: str) -> None:
        _r.delete(self._k(key))

    def clear(self) -> None:
        for k in _r.scan_iter(f"{self.prefix}:*"):
            _r.delete(k)


tenant_cache = _Cache("tenant", 60)
session_cache = _Cache("session", 30)
acl_cache = _Cache("acl", 60)
