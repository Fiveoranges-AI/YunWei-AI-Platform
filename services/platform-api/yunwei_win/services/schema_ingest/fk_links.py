"""Foreign-key fields that confirm auto-fills from same-confirm parents.

The mapping is used in two places:

* ``review_draft.materialize_review_draft`` marks an empty FK cell with
  ``source="linked"`` when the parent table is also being materialized.
  This signals to the UI that the value will be supplied by the system at
  writeback and removes the "missing required" warning for cells that the
  user is not expected to fill.
* ``confirm._persist_row`` reads the same map to actually inject the
  parent's UUID at writeback time, after the parent row has been inserted.

Keeping the map in one module avoids the two sides drifting.
"""

from __future__ import annotations


FK_FIELD_PARENTS: dict[str, str] = {
    "customer_id": "customers",
    "contract_id": "contracts",
    "invoice_id": "invoices",
    "order_id": "orders",
    "shipment_id": "shipments",
    "product_id": "products",
    "document_id": "documents",
    "source_document_id": "documents",
}
