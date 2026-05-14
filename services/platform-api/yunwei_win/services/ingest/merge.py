"""Merge step — fuse the three per-extractor drafts into one ``UnifiedDraft``.

Pipeline step 4: take the outputs of the parallel extractors (identity,
commercial, ops — any of which may be ``None`` if the planner didn't activate
the dimension) and produce:

1. A single ``UnifiedDraft`` that the review form binds to. Fields that come
   from a missing extractor stay ``None`` / empty list.
2. A ``MergeCandidates`` bundle: customer/contact match candidates computed
   against existing rows, so the UI can offer "merge into existing vs create
   new" before any DB write.

Like the contract draft path (``services.ingest.contract``), this module
never writes the structured tables — only the orchestrator's confirm step
does that. Match-candidate computation does run a few read-only queries (via
``services.match.find_*``) so the UI gets a deterministic ranking.

``needs_review_fields`` is the merged equivalent of the legacy
``field_confidence < 0.7`` highlight set: any path whose extractor confidence
fell below the review threshold, plus a few category-specific tripwires (no
customer name, contact missing name, payment-milestone ratios that don't sum
to 1.0). The UI uses this list to render a yellow halo on those fields.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Sequence

from sqlalchemy.ext.asyncio import AsyncSession

# MatchCandidate already lives in ``services.ingest.contract``. Reuse the same
# type so draft merging and contract extraction rank candidates consistently.
from yunwei_win.services.ingest.contract import MatchCandidate
from yunwei_win.services.ingest.unified_schemas import (
    CommercialDraft,
    ContactExtraction,
    CustomerExtraction,
    IdentityDraft,
    OpsDraft,
    UnifiedDraft,
)
from yunwei_win.services.match import find_contact_candidates, find_customer_candidates


# ---------- public dataclass ---------------------------------------------


@dataclass
class MergeCandidates:
    """Match candidates computed during merge.

    ``customer_candidates`` ranks existing customers similar to the merged
    ``UnifiedDraft.customer.full_name``. ``contact_candidates[i]`` is the
    candidate list for the i-th merged contact slot (same indexing as
    ``UnifiedDraft.contacts``).
    """

    customer_candidates: list[MatchCandidate] = field(default_factory=list)
    contact_candidates: list[list[MatchCandidate]] = field(default_factory=list)


# ---------- review-flag heuristics ---------------------------------------


# Fields below this confidence get flagged for review. Matches the legacy
# contract pipeline so a draft routed through /auto highlights the same
# fields it would have via /contract.
_REVIEW_CONFIDENCE_THRESHOLD = 0.7
_RATIO_SUM_LOW = 0.99
_RATIO_SUM_HIGH = 1.01


def _confidence_for_path(
    field_provenance: Iterable, path: str
) -> float | None:
    """Pull the LLM-side confidence (if any) for a given field path.

    The unified schemas don't carry an explicit ``field_confidence`` dict the
    way ``ContractExtractionResult`` does, but the per-extractor
    ``confidence_overall`` plus the per-row ``confidence`` values on
    ``ExtractedEvent`` / ``ExtractedCommitment`` etc. are the same signal.
    Returns ``None`` if no confidence is recorded, so the caller can decide
    whether absence-of-confidence should mean "trust" or "review".
    """
    # Currently unused — kept as the obvious extension point if/when a
    # ``field_confidence`` map is added to the unified schemas.
    return None


def _identity_review_paths(draft: IdentityDraft | None) -> list[str]:
    """Field paths in the identity draft that should be highlighted.

    Triggered by:
    - ``customer.full_name`` is missing — without a name we can't merge or
      create a customer row. The review form prompts the user to provide one.
    - ``contacts[i].name`` is missing — same problem at the contact level.
    - Identity overall confidence below the review threshold — propagated as
      "identity" so the UI can render a panel-level halo.
    """
    if draft is None:
        return []
    paths: list[str] = []
    customer = draft.customer
    if customer is None or not (customer.full_name and customer.full_name.strip()):
        paths.append("customer.full_name")
    for idx, contact in enumerate(draft.contacts):
        if not (contact.name and contact.name.strip()):
            paths.append(f"contacts[{idx}].name")
    if draft.confidence_overall < _REVIEW_CONFIDENCE_THRESHOLD:
        paths.append("identity")
    return paths


def _commercial_review_paths(draft: CommercialDraft | None) -> list[str]:
    """Field paths in the commercial draft that should be highlighted.

    Triggered by:
    - Payment-milestone ratios don't sum to 1.0 ± 0.01 — same tolerance the
      legacy contract pipeline uses. Surface the milestones array path so the
      UI can highlight the table.
    - Commercial overall confidence below the review threshold — surfaced as
      "commercial" for a panel-level halo.
    """
    if draft is None:
        return []
    paths: list[str] = []
    contract = draft.contract
    if contract is not None and contract.payment_milestones:
        total = sum(m.ratio for m in contract.payment_milestones)
        if not (_RATIO_SUM_LOW <= total <= _RATIO_SUM_HIGH):
            paths.append("contract.payment_milestones")
    if draft.confidence_overall < _REVIEW_CONFIDENCE_THRESHOLD:
        paths.append("commercial")
    return paths


def _ops_review_paths(draft: OpsDraft | None) -> list[str]:
    """Field paths in the ops draft that should be highlighted.

    Triggered solely by overall confidence — individual ops rows already
    carry a ``confidence`` field that the UI can highlight per-row, so we
    keep the merge-side flag list short.
    """
    if draft is None:
        return []
    paths: list[str] = []
    if draft.confidence_overall < _REVIEW_CONFIDENCE_THRESHOLD:
        paths.append("ops")
    return paths


# ---------- candidate computation ----------------------------------------


def _candidate_from_customer(c, score, reason) -> MatchCandidate:
    """Project a Customer row into the wire-shape ``MatchCandidate``."""
    return MatchCandidate(
        id=c.id,
        score=score,
        reason=reason,
        fields={
            "full_name": c.full_name,
            "short_name": c.short_name,
            "address": c.address,
            "tax_id": c.tax_id,
        },
    )


def _candidate_from_contact(c, score, reason) -> MatchCandidate:
    """Project a Contact row into the wire-shape ``MatchCandidate``."""
    return MatchCandidate(
        id=c.id,
        score=score,
        reason=reason,
        fields={
            "name": c.name,
            "title": c.title,
            "phone": c.phone,
            "mobile": c.mobile,
            "email": c.email,
            "role": c.role.value,
            "address": c.address,
        },
    )


async def _compute_candidates(
    *,
    session: AsyncSession,
    identity: IdentityDraft | None,
) -> MergeCandidates:
    """Run customer + contact match queries against the DB.

    Skips the queries entirely when no identity draft is supplied — the ops
    extractor alone can't produce match candidates (no name / phone to query
    against), and the orchestrator handles that case by leaving the lists
    empty so the review UI shows "create new customer" only.
    """
    if identity is None:
        return MergeCandidates()

    customer = identity.customer
    customer_name = customer.full_name if customer is not None else None
    customer_hits = await find_customer_candidates(session, customer_name)
    customer_candidates = [
        _candidate_from_customer(c, score, reason)
        for c, score, reason in customer_hits
    ]

    contact_candidate_lists: list[list[MatchCandidate]] = []
    for ct in identity.contacts:
        hits = await find_contact_candidates(
            session,
            phone=ct.phone,
            mobile=ct.mobile,
            email=ct.email,
        )
        contact_candidate_lists.append(
            [_candidate_from_contact(c, score, reason) for c, score, reason in hits]
        )

    return MergeCandidates(
        customer_candidates=customer_candidates,
        contact_candidates=contact_candidate_lists,
    )


async def build_merge_candidates(
    *,
    session: AsyncSession,
    customer: CustomerExtraction | None,
    contacts: Sequence[ContactExtraction] | None,
) -> MergeCandidates:
    """Compute match candidates from already-merged customer/contact drafts.

    The legacy ``merge_drafts`` couples merging and candidate computation;
    the LandingAI flow needs candidates after a separate normalize step, so
    we expose the candidate calc on its own here.
    """
    if customer is None and not contacts:
        return MergeCandidates()
    identity = IdentityDraft(
        customer=customer,
        contacts=list(contacts or []),
        field_provenance=[],
        confidence_overall=1.0,
        parse_warnings=[],
    )
    return await _compute_candidates(session=session, identity=identity)


# ---------- public entrypoint --------------------------------------------


async def merge_drafts(
    *,
    session: AsyncSession,
    identity: IdentityDraft | None,
    commercial: CommercialDraft | None,
    ops: OpsDraft | None,
) -> tuple[UnifiedDraft, MergeCandidates]:
    """Fuse the three drafts into a ``UnifiedDraft`` + match candidates.

    Each draft is independent — different LLM calls produced them, possibly
    with overlapping ``parse_warnings`` and ``field_provenance`` entries.
    We:

    1. Copy the structured fields straight across (identity → customer +
       contacts; commercial → order + contract; ops → events / commitments
       / tasks / risk_signals / memory_items + summary).
    2. Concatenate ``field_provenance`` lists from every draft. Order is
       deterministic: identity → commercial → ops.
    3. Concatenate ``parse_warnings`` from every draft into the merged
       ``warnings`` list.
    4. Compute ``confidence_overall`` as the minimum of the present drafts'
       confidences (a weak link drags the whole thing down). When no draft
       runs we default to 0.0 so the UI knows to ask for review.
    5. Build ``needs_review_fields`` from the per-dimension heuristics.
    6. Look up customer + per-contact match candidates using ``services.match``
       and return them alongside the merged draft.
    """
    customer = identity.customer if identity is not None else None
    contacts = list(identity.contacts) if identity is not None else []
    order = commercial.order if commercial is not None else None
    contract = commercial.contract if commercial is not None else None

    summary = ops.summary if ops is not None else ""
    events = list(ops.events) if ops is not None else []
    commitments = list(ops.commitments) if ops is not None else []
    tasks = list(ops.tasks) if ops is not None else []
    risk_signals = list(ops.risk_signals) if ops is not None else []
    memory_items = list(ops.memory_items) if ops is not None else []

    field_provenance: list = []
    warnings: list[str] = []
    confidences: list[float] = []
    for d in (identity, commercial, ops):
        if d is None:
            continue
        field_provenance.extend(d.field_provenance)
        warnings.extend(d.parse_warnings)
        confidences.append(d.confidence_overall)

    confidence_overall = min(confidences) if confidences else 0.0

    needs_review_fields: list[str] = []
    needs_review_fields.extend(_identity_review_paths(identity))
    needs_review_fields.extend(_commercial_review_paths(commercial))
    needs_review_fields.extend(_ops_review_paths(ops))
    # Dedupe while preserving order — list(dict.fromkeys(...)) is the
    # idiomatic Python 3.7+ way; same item flagged from two heuristics
    # should only appear once in the UI halo set.
    needs_review_fields = list(dict.fromkeys(needs_review_fields))

    draft = UnifiedDraft(
        customer=customer,
        contacts=contacts,
        order=order,
        contract=contract,
        events=events,
        commitments=commitments,
        tasks=tasks,
        risk_signals=risk_signals,
        memory_items=memory_items,
        summary=summary,
        field_provenance=field_provenance,
        confidence_overall=confidence_overall,
        needs_review_fields=needs_review_fields,
        warnings=warnings,
    )

    candidates = await _compute_candidates(session=session, identity=identity)
    return draft, candidates
