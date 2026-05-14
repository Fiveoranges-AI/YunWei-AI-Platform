"""Legacy pipeline-keyed bridge to the vNext selected-tables schema builder.

Old extractor providers and the legacy review-draft materializer key off
``PipelineName`` (``identity``, ``contract_order``, ``finance``, ...).
The vNext extraction schema is built from a list of company-schema
table names instead.

To keep the old call sites alive while the vNext rewrite lands, this
module:
- Keeps ``PIPELINE_TABLES`` mapping pipeline names to canonical table
  lists so old code (review draft, providers) still resolves.
- Delegates ``build_pipeline_schema_json`` to
  ``build_selected_tables_schema_json``, which enforces
  ``field_role in (extractable, identity_key)`` and drops every
  ``system_link`` / ``audit`` field.

Once Task 4+ rewires extractor providers and the orchestrator to call
the vNext API directly, this bridge can be deleted.
"""

from __future__ import annotations

import json
from typing import Any

from yunwei_win.services.ingest.pipeline_schemas import PipelineName
from yunwei_win.services.schema_ingest.extraction_schema import (
    build_selected_tables_schema_json,
)


PIPELINE_TABLES: dict[PipelineName, list[str]] = {
    "identity": ["customers", "contacts"],
    "contract_order": [
        "customers",
        "contacts",
        "contracts",
        "contract_payment_milestones",
        "orders",
    ],
    "finance": ["invoices", "invoice_items", "payments"],
    "logistics": ["shipments", "shipment_items"],
    "manufacturing_requirement": ["products", "product_requirements"],
    "commitment_task_risk": ["customer_journal_items", "customer_tasks"],
}


def build_pipeline_schema_json(pipeline_name: str, catalog: dict[str, Any]) -> str:
    """Legacy pipeline-keyed JSON schema bridge.

    Resolves ``pipeline_name`` to a canonical table list, then defers to the
    vNext selected-tables builder. The builder excludes system/audit fields,
    so the returned schema only contains extractable + identity_key fields.
    """

    table_names = PIPELINE_TABLES.get(pipeline_name, [])  # type: ignore[arg-type]
    if not table_names:
        schema = {
            "type": "object",
            "description": (
                f"No active company schema tables are selected for pipeline "
                f"{pipeline_name}."
            ),
            "properties": {},
        }
        return json.dumps(schema, ensure_ascii=False, sort_keys=True)

    return build_selected_tables_schema_json(table_names, catalog)
