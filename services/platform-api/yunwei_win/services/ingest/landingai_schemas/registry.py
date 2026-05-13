from __future__ import annotations

import json
from importlib.resources import files
from typing import Any, Literal


PipelineName = Literal[
    "identity",
    "contract_order",
    "finance",
    "logistics",
    "manufacturing_requirement",
    "commitment_task_risk",
]

PIPELINE_NAMES: tuple[PipelineName, ...] = (
    "identity",
    "contract_order",
    "finance",
    "logistics",
    "manufacturing_requirement",
    "commitment_task_risk",
)

_SUPPORTED_KEYS = {
    "type",
    "properties",
    "description",
    "items",
    "enum",
    "format",
    "x-alternativeNames",
}


def _walk_schema(node: Any, path: str = "$") -> None:
    if isinstance(node, dict):
        for key, value in node.items():
            if key not in _SUPPORTED_KEYS:
                raise ValueError(f"unsupported LandingAI schema keyword {key!r} at {path}")
            if key == "properties":
                if not isinstance(value, dict):
                    raise ValueError(f"properties must be object at {path}")
                for prop_name, prop_schema in value.items():
                    _walk_schema(prop_schema, f"{path}.properties.{prop_name}")
            elif key == "items":
                _walk_schema(value, f"{path}.items")
            elif key == "enum":
                if not all(isinstance(item, str) for item in value):
                    raise ValueError(f"enum values must be strings at {path}")


def validate_landingai_schema(schema: dict[str, Any]) -> None:
    if schema.get("type") != "object":
        raise ValueError("LandingAI schema top-level type must be object")
    if not isinstance(schema.get("properties"), dict):
        raise ValueError("LandingAI schema must include object properties")
    _walk_schema(schema)


def load_schema_json(name: PipelineName) -> str:
    if name not in PIPELINE_NAMES:
        raise ValueError(f"unknown LandingAI pipeline schema: {name}")
    raw = (
        files(__package__)
        .joinpath(f"{name}.schema.json")
        .read_text(encoding="utf-8")
    )
    validate_landingai_schema(json.loads(raw))
    return raw
