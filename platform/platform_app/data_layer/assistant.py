"""Data center sidebar assistant (docs/data-layer.md §3.3).

A platform-side chat-style agent that wraps the data layer's read/write
APIs as tools. Uses the official ``anthropic`` Python SDK — kernel runtime
is not reused (open question §11.5 resolved in favor of platform-owned).

Design notes:
- The system prompt + tool definitions are stable across requests, so we
  put a ``cache_control`` breakpoint on the last system block. Tenant-
  specific state (current health, bronze listing) is injected as the
  first user message so it lives *after* the cache breakpoint and
  doesn't invalidate the cached prefix.
- Tools call into the data_layer modules directly — the API layer above
  has already validated session + ACL, so the assistant can trust its
  ``client_id`` arg.
- Adaptive thinking is enabled (per Anthropic best practice for tool-
  using agents); thinking content is omitted from responses by default.
"""
from __future__ import annotations
import json
from dataclasses import dataclass, field
from typing import Any
import anthropic
from ..settings import settings
from . import ingest, paths, repo, silver_db, silver_schema, transform


_SYSTEM_PROMPT_TEMPLATE = """\
You are the data import assistant for fiveoranges.ai's 数据中心 (data
center). You help SME staff (operations, finance, owners — NOT data
engineers) get their company data into the lakehouse and verify it's
correct.

Your scope:
1. **拖文件给我** — when a user uploads an Excel/CSV, look at the sheet
   columns and propose a mapping to one of the silver canonical tables.
   Keep the proposal short. Ask the user to confirm before committing.
2. **建映射** — once confirmed, call ``create_mapping_and_transform`` to
   commit the mapping and materialize silver rows.
3. **手填一条** — for now, point users at the assistant flow (M4 wires
   this up properly).
4. **回答"我数据齐了吗"** — read silver health + bronze listing and
   answer in plain language.

Rules:
- Always reply in 简体中文. Brief, direct, no preamble.
- Never invent data. If the user asks about something you can't see,
  call a tool to check.
- Before any write action (mapping commit, bronze delete), state what
  you're about to do and wait for the user's confirmation.
- The 5 silver canonical tables and their columns are documented below;
  use them to ground mapping proposals.

## Silver canonical schema (v{schema_version})

{schema_summary}

## Source types

- ``file_excel`` — uploads in §3.2
- ``file_pdf`` — best-effort OCR (M4)
- ``manual_ui`` — user-entered rows (M4)
- ``erp_kingdee`` / ``erp_yongyou`` — future import-agent

When proposing a mapping, only target ``customers`` or ``orders`` —
``order_items`` / ``order_source_records`` / ``boss_query_logs`` are not
valid transform targets in M3.
"""


def _summarize_schema() -> str:
    """Compact, model-friendly rendering of the canonical schema. Stable
    across requests so it caches well."""
    schema = silver_schema.load()
    lines: list[str] = []
    for tname, table in schema.tables.items():
        cols = []
        for c in table.columns:
            type_hint = c.type
            if c.values:
                type_hint = f"{c.type}[{','.join(c.values)}]"
            null_hint = "" if c.nullable else "*"
            cols.append(f"{c.name}{null_hint}:{type_hint}")
        lines.append(f"### {tname}\n{table.description}\n" +
                     ", ".join(cols))
    return "\n\n".join(lines)


def _system_prompt() -> str:
    schema = silver_schema.load()
    return _SYSTEM_PROMPT_TEMPLATE.format(
        schema_version=schema.version,
        schema_summary=_summarize_schema(),
    )


# ─── Tool schemas ───────────────────────────────────────────────

TOOLS: list[dict[str, Any]] = [
    {
        "name": "data_health",
        "description": (
            "Returns the health of all 5 silver tables for the current "
            "tenant: row counts, latest update timestamp, distribution "
            "by source_type. Returns initialized=false if the silver "
            "database does not exist yet."
        ),
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "list_bronze_files",
        "description": (
            "Lists bronze files (raw uploads + ERP / manual sources) for "
            "the tenant. Optionally filtered by source_type."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "source_type": {
                    "type": "string",
                    "enum": ["erp_kingdee", "erp_yongyou", "file_excel",
                             "file_pdf", "manual_ui"],
                    "description": "Optional filter.",
                },
            },
        },
    },
    {
        "name": "get_bronze_preview",
        "description": (
            "Returns the column list and the first ~50 rows of a bronze "
            "parquet file. Use this to inspect a sheet before proposing "
            "a column mapping."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "bronze_file_id": {"type": "string"},
                "limit": {"type": "integer", "minimum": 1, "maximum": 200,
                          "default": 50},
            },
            "required": ["bronze_file_id"],
        },
    },
    {
        "name": "create_mapping_and_transform",
        "description": (
            "Commit a bronze→silver column mapping and materialize the "
            "silver rows. Idempotent — re-running with the same mapping "
            "produces the same silver state. WRITE OPERATION: confirm "
            "with the user before calling. silver_table must be one of "
            "'customers' or 'orders' (others lack source_lineage in M3)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "bronze_file_id": {"type": "string"},
                "silver_table": {"type": "string",
                                 "enum": ["customers", "orders"]},
                "column_map": {
                    "type": "object",
                    "description": (
                        "Map of bronze column name → silver column name. "
                        "Only include columns the user mapped — system "
                        "columns (source_type, source_lineage, "
                        "created_at, updated_at) and unmapped required "
                        "fields get sensible defaults."
                    ),
                    "additionalProperties": {"type": "string"},
                },
            },
            "required": ["bronze_file_id", "silver_table", "column_map"],
        },
    },
    {
        "name": "cascade_delete_bronze",
        "description": (
            "Soft-deletes a bronze file and removes any silver rows that "
            "originated from it (via source_lineage). WRITE OPERATION: "
            "confirm with the user before calling."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"bronze_file_id": {"type": "string"}},
            "required": ["bronze_file_id"],
        },
    },
]


# ─── Tool dispatch ──────────────────────────────────────────────

def _tool_data_health(client_id: str) -> dict:
    p = paths.silver_live_path(client_id)
    if not p.exists():
        return {"initialized": False, "tables": {}}
    import duckdb
    con = duckdb.connect(str(p), read_only=True)
    try:
        out: dict[str, Any] = {"initialized": True, "tables": {}}
        schema = silver_schema.load()
        for tname in schema.tables:
            row = con.execute(
                "SELECT 1 FROM information_schema.tables "
                "WHERE table_schema='main' AND table_name=?", [tname],
            ).fetchone()
            if not row:
                out["tables"][tname] = {"row_count": 0, "by_source": {}}
                continue
            n = con.execute(f"SELECT COUNT(*) FROM {tname}").fetchone()[0]
            cols = {c[0] for c in con.execute(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema='main' AND table_name=?", [tname],
            ).fetchall()}
            by_source: dict[str, int] = {}
            if "source_type" in cols:
                for src, cnt in con.execute(
                    f"SELECT source_type, COUNT(*) FROM {tname} GROUP BY source_type"
                ).fetchall():
                    by_source[src or "unknown"] = cnt
            out["tables"][tname] = {"row_count": n, "by_source": by_source}
        return out
    finally:
        con.close()


def _tool_list_bronze_files(client_id: str, source_type: str | None = None) -> dict:
    files = repo.list_bronze_files(client_id, source_type)
    return {"files": [{
        "id": f["id"],
        "source_type": f["source_type"],
        "original_filename": f["original_filename"],
        "sheet_name": f["sheet_name"],
        "row_count": f["row_count"],
        "ingested_at": f["ingested_at"],
    } for f in files]}


def _tool_get_bronze_preview(client_id: str, bronze_file_id: str,
                             limit: int = 50) -> dict:
    return ingest.read_bronze_preview(client_id, bronze_file_id, limit=limit)


def _tool_create_mapping_and_transform(
    client_id: str, user_id: str, bronze_file_id: str,
    silver_table: str, column_map: dict,
) -> dict:
    bronze_row = next(
        (r for r in repo.list_bronze_files(client_id) if r["id"] == bronze_file_id),
        None,
    )
    if bronze_row is None:
        return {"error": "bronze_file_not_found"}
    bronze_columns = list(json.loads(bronze_row["meta_json"]).get("columns", []))
    mapping_id = repo.insert_silver_mapping(
        client_id=client_id,
        source_type=bronze_row["source_type"],
        filename_pattern=bronze_row["original_filename"] or "",
        sheet_pattern=bronze_row["sheet_name"],
        silver_table=silver_table,
        column_map=column_map,
        bronze_columns_snapshot=bronze_columns,
        created_by=user_id,
    )
    result = transform.materialize(
        client_id=client_id,
        bronze_file_id=bronze_file_id,
        silver_table=silver_table,
        column_map=column_map,
    )
    return {
        "mapping_id": mapping_id,
        "silver_table": result.silver_table,
        "rows_written": result.rows_written,
        "rows_skipped": result.rows_skipped,
    }


def _tool_cascade_delete_bronze(client_id: str, bronze_file_id: str) -> dict:
    matching = [r for r in repo.list_bronze_files(client_id)
                if r["id"] == bronze_file_id]
    if not matching:
        return {"error": "bronze_file_not_found"}
    silver_deleted = transform.cascade_delete_silver(client_id, bronze_file_id)
    repo.soft_delete_bronze_file(bronze_file_id)
    return {"ok": True, "silver_rows_deleted": silver_deleted}


def _dispatch_tool(name: str, args: dict, *, client_id: str, user_id: str) -> Any:
    """Single switch dispatcher — keeps tool execution explicit + auditable."""
    if name == "data_health":
        return _tool_data_health(client_id)
    if name == "list_bronze_files":
        return _tool_list_bronze_files(client_id, args.get("source_type"))
    if name == "get_bronze_preview":
        return _tool_get_bronze_preview(
            client_id, args["bronze_file_id"], args.get("limit", 50),
        )
    if name == "create_mapping_and_transform":
        return _tool_create_mapping_and_transform(
            client_id, user_id,
            args["bronze_file_id"], args["silver_table"], args["column_map"],
        )
    if name == "cascade_delete_bronze":
        return _tool_cascade_delete_bronze(client_id, args["bronze_file_id"])
    return {"error": f"unknown_tool:{name}"}


# ─── Chat orchestration ─────────────────────────────────────────

class AssistantNotConfigured(RuntimeError):
    """Raised when ANTHROPIC_API_KEY is missing — surfaced to UI as a
    503 so the assistant chat can be hidden / disabled cleanly."""


@dataclass
class ChatTurn:
    role: str                              # "user" | "assistant"
    content: list[dict] | str              # raw blocks or plain text
    tool_calls: list[dict] = field(default_factory=list)


@dataclass
class ChatResult:
    messages: list[dict]                   # full history (incl. tool turns)
    final_text: str
    tool_invocations: list[dict]           # for UI: name + summary per call
    usage: dict


def chat(
    *,
    client_id: str,
    user_id: str,
    history: list[dict],
    user_text: str,
) -> ChatResult:
    """Run one user turn through the model + tool loop and return the
    full updated conversation.

    ``history`` is the accumulated transcript from prior turns (already
    contains user/assistant/tool blocks in the Anthropic message format).
    ``user_text`` is the new turn the user just typed.
    """
    if not settings.anthropic_api_key:
        raise AssistantNotConfigured("ANTHROPIC_API_KEY not set")

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

    # First user turn — prepend tenant context so the assistant has live
    # state without polluting the cached system prompt.
    if not history:
        snapshot_health = _tool_data_health(client_id)
        snapshot_bronze = _tool_list_bronze_files(client_id)
        kickoff_context = (
            "[当前租户状态]\n"
            f"client_id: {client_id}\n"
            f"silver health: {json.dumps(snapshot_health, ensure_ascii=False)}\n"
            f"bronze 文件: {json.dumps(snapshot_bronze, ensure_ascii=False)}\n\n"
            "[用户消息]\n" + user_text
        )
        messages = [{"role": "user", "content": kickoff_context}]
    else:
        messages = [*history, {"role": "user", "content": user_text}]

    tool_invocations: list[dict] = []
    final_text = ""
    cumulative_usage = {
        "input_tokens": 0, "output_tokens": 0,
        "cache_creation_input_tokens": 0, "cache_read_input_tokens": 0,
    }

    for _ in range(settings.assistant_max_tool_iterations):
        response = client.messages.create(
            model=settings.assistant_model,
            max_tokens=4096,
            system=[{
                "type": "text",
                "text": _system_prompt(),
                "cache_control": {"type": "ephemeral"},
            }],
            tools=TOOLS,
            thinking={"type": "adaptive"},
            output_config={"effort": settings.assistant_effort},
            messages=messages,
        )
        for k in cumulative_usage:
            cumulative_usage[k] += getattr(response.usage, k, 0) or 0

        # Always echo the assistant turn into history so subsequent calls
        # see the same conversation Claude saw.
        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason != "tool_use":
            for block in response.content:
                if block.type == "text":
                    final_text += block.text
            break

        # Execute every tool_use block in this turn, then loop.
        tool_results = []
        for block in response.content:
            if block.type != "tool_use":
                continue
            try:
                result = _dispatch_tool(
                    block.name, block.input or {},
                    client_id=client_id, user_id=user_id,
                )
                is_error = False
            except Exception as e:  # surface to model so it can recover
                result = {"error": str(e)}
                is_error = True
            tool_invocations.append({
                "name": block.name,
                "input": block.input,
                "is_error": is_error,
            })
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": json.dumps(result, ensure_ascii=False),
                "is_error": is_error,
            })
        messages.append({"role": "user", "content": tool_results})

    return ChatResult(
        messages=_serialize_messages(messages),
        final_text=final_text or "(assistant did not produce a text response)",
        tool_invocations=tool_invocations,
        usage=cumulative_usage,
    )


def _serialize_messages(messages: list) -> list[dict]:
    """Convert anthropic SDK content blocks to plain JSON-able dicts so
    the frontend can persist + replay conversation history."""
    out = []
    for m in messages:
        if isinstance(m["content"], str):
            out.append({"role": m["role"], "content": m["content"]})
            continue
        blocks = []
        for b in m["content"]:
            if isinstance(b, dict):
                blocks.append(b)
            elif hasattr(b, "model_dump"):
                blocks.append(b.model_dump(mode="json"))
            else:
                # Plain object with attributes (e.g. test mocks); copy
                # public attrs whose value is non-None.
                blocks.append({k: v for k, v in vars(b).items()
                               if not k.startswith("_") and v is not None})
        out.append({"role": m["role"], "content": blocks})
    return out
