"""Cross-cutting mixin columns for the customer-operations ontology.

These mixins encode the product-soul fields that every core business entity
(customer / contact / contract / order / invoice / payment / shipment /
delivery / risk / next_action ...) must carry so we can answer "where did
this come from? who confirmed it? does it belong to a sales rep? is it
hidden?".

Mixins are composable so a new model can opt into the exact subset it
needs. The full default set for a core business row is::

    class Foo(Base, TimestampMixin, RowProvenanceMixin, HumanVerificationMixin,
              RowAuditMixin, OwnershipMixin, SoftDeleteMixin):
        ...

Per-field provenance (where in the source PDF this exact value came from)
lives in ``field_provenance``. The row-level pointer fields here answer
"which document / message / API call seeded this whole row" and stay on
the row itself so list views and timelines can render without joining.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column


class RowSourceMixin:
    """The "where did this row come from" pointer.

    ``source_type`` is a coarse label (``document`` / ``manual`` /
    ``api`` / ``import`` / ``llm`` ...); ``source_ref`` is an opaque
    pointer (document id, message id, sheet path...); ``source_span``
    is a structured pointer for re-finding (page, bbox, line, etc.).
    ``extracted_by`` is the actor that produced the row (model name,
    worker name, "manual").
    """

    source_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    source_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_span: Mapped[dict[str, Any] | list[Any] | None] = mapped_column(
        JSON, nullable=True
    )
    extracted_by: Mapped[str | None] = mapped_column(String(64), nullable=True)


class RowConfidenceMixin:
    """Row-creation seed confidence (0-1).

    NULL for manual rows or rows where confidence wasn't measured; set to
    ``1.0`` for human-verified rows. Tables that already have their own
    ``confidence`` column (e.g. ``customer_risk_signals``) skip this
    mixin and reuse the existing column.
    """

    confidence: Mapped[Decimal | None] = mapped_column(Numeric(3, 2), nullable=True)


class RowProvenanceMixin(RowSourceMixin, RowConfidenceMixin):
    """Combined source + confidence. The default for new ontology rows.

    Compose ``RowSourceMixin`` directly (without ``RowConfidenceMixin``)
    on tables that already carry their own ``confidence`` column to
    avoid a name collision.
    """


class HumanVerificationMixin:
    """Has a human actually looked at this row and confirmed it?

    ``human_verified=false`` means "AI-proposed, not yet reviewed". The
    inbox-review UI flips this to ``true`` and stamps ``verified_by`` +
    ``verified_at``. Manual entry should set ``human_verified=true``
    on insert.
    """

    human_verified: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    verified_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class RowAuditMixin:
    """Who created / last touched this row.

    Stored as opaque actor strings — usually a platform user id but can
    also be ``system`` / ``llm:claude-sonnet-4`` / a worker name.
    ``created_at`` / ``updated_at`` are on ``TimestampMixin``.
    """

    created_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    updated_by: Mapped[str | None] = mapped_column(String(128), nullable=True)


class OwnershipMixin:
    """Per-row ownership for the future sales-team rollout.

    Only the data model is laid down here — the actual row-filter logic
    (sales sees only their rows, sales-lead sees their team's, owner
    sees all) is intentionally out of scope for P0 and will be wired in
    a separate task once we agree on auth semantics.
    """

    owner_user_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    team_id: Mapped[str | None] = mapped_column(String(128), nullable=True)


class SoftDeleteMixin:
    """Soft delete.

    Rows are never physically removed from these ontology tables;
    listing endpoints filter ``is_deleted=false`` by default. This
    keeps timeline + audit reasoning intact when a user "removes"
    something.
    """

    is_deleted: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, index=True
    )
