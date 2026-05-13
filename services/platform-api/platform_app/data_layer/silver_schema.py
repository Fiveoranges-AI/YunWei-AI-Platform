"""silver-canonical.yaml loader (docs/data-layer.md §5.3).

The yaml itself is owned by the kernel repo
(``yunwei-kernel/lakehouse/silver-canonical.yaml``). A copy lives next to
this module and is refreshed via ``ops/sync_silver_canonical.py``. We
intentionally avoid a git submodule for now (open question §11.1).
"""
from __future__ import annotations
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
import yaml

_YAML_PATH = Path(__file__).parent / "silver-canonical.yaml"


@dataclass(frozen=True)
class Column:
    name: str
    type: str
    nullable: bool
    description: str | None
    values: tuple[str, ...] | None  # for enum


@dataclass(frozen=True)
class Table:
    name: str
    description: str
    primary_key: tuple[str, ...]
    columns: tuple[Column, ...]


@dataclass(frozen=True)
class Schema:
    version: str
    last_updated: str
    tables: dict[str, Table]


def _parse(raw: dict) -> Schema:
    tables: dict[str, Table] = {}
    for name, body in raw["tables"].items():
        cols = tuple(
            Column(
                name=c["name"],
                type=c["type"],
                nullable=c.get("nullable", True),
                description=c.get("description"),
                values=tuple(c["values"]) if c.get("values") else None,
            )
            for c in body["columns"]
        )
        tables[name] = Table(
            name=name,
            description=body.get("description", ""),
            primary_key=tuple(body["primary_key"]),
            columns=cols,
        )
    return Schema(
        version=str(raw["schema_version"]),
        last_updated=str(raw["last_updated"]),
        tables=tables,
    )


@lru_cache(maxsize=1)
def load() -> Schema:
    return _parse(yaml.safe_load(_YAML_PATH.read_text()))


def reload() -> Schema:
    """Drop the cached parse — for tests that swap the yaml file."""
    load.cache_clear()
    return load()
