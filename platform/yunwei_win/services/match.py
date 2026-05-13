"""Fuzzy matching for entity resolution.

Used by the contract preview pipeline to surface "this looks like an
existing row" candidates so the review form can offer side-by-side
edit-or-merge before any DB write.

Customer matching: name normalization (drop common suffixes like 有限公司,
集团股份有限公司, etc.) + character-level Jaccard on the normalized core.
≥ 0.85 similarity → candidate.

Contact matching: exact-match on phone OR mobile OR email (case-insensitive).
Name-only similarity is too noisy (everyone is 许总 / 张工 / 李经理).
"""

from __future__ import annotations

import logging
import re

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from yunwei_win.models import Contact, Customer

logger = logging.getLogger(__name__)


_COMPANY_SUFFIXES = [
    "集团股份有限公司",
    "股份有限公司",
    "有限责任公司",
    "集团有限公司",
    "有限公司",
    "集团",
    "公司",
    "Co., Ltd.",
    "Co.,Ltd.",
    "Co. Ltd.",
    "Ltd.",
    "Inc.",
    "(",
    ")",
    "（",
    "）",
]
_PUNCT_RE = re.compile(r"[\s\.\-_·。，,]+")


def normalize_company_name(name: str) -> str:
    s = name or ""
    for suffix in _COMPANY_SUFFIXES:
        s = s.replace(suffix, "")
    s = _PUNCT_RE.sub("", s)
    return s.strip().lower()


def char_jaccard(a: str, b: str) -> float:
    """Character set Jaccard — fast, language-agnostic, robust to spaces."""
    if not a or not b:
        return 0.0
    sa, sb = set(a), set(b)
    inter = len(sa & sb)
    union = len(sa | sb)
    return inter / union if union else 0.0


def char_bigram_jaccard(a: str, b: str) -> float:
    """Bigram Jaccard — better discrimination than unigram."""
    if not a or not b:
        return 0.0
    bg_a = {a[i : i + 2] for i in range(len(a) - 1)} | set(a)
    bg_b = {b[i : i + 2] for i in range(len(b) - 1)} | set(b)
    inter = len(bg_a & bg_b)
    union = len(bg_a | bg_b)
    return inter / union if union else 0.0


def customer_similarity(a: str, b: str) -> float:
    na = normalize_company_name(a)
    nb = normalize_company_name(b)
    if not na or not nb:
        return 0.0
    if na == nb:
        return 1.0
    if na in nb or nb in na:
        return 0.95
    return char_bigram_jaccard(na, nb)


CUSTOMER_THRESHOLD = 0.85


async def find_customer_candidates(
    session: AsyncSession, full_name: str | None
) -> list[tuple[Customer, float, str]]:
    """Find existing customers similar to ``full_name``. Returns
    (existing, score, reason). Used by the contract preview pipeline before
    any DB row exists for the incoming customer."""
    if not full_name or not full_name.strip():
        return []
    others = (await session.execute(select(Customer))).scalars().all()
    out: list[tuple[Customer, float, str]] = []
    for other in others:
        score = customer_similarity(full_name, other.full_name)
        if score >= CUSTOMER_THRESHOLD:
            reason = (
                f"name similarity {score:.2f} vs {other.full_name!r}"
            )
            out.append((other, score, reason))
    out.sort(key=lambda x: x[1], reverse=True)
    return out


async def find_contact_candidates(
    session: AsyncSession,
    *,
    phone: str | None = None,
    mobile: str | None = None,
    email: str | None = None,
) -> list[tuple[Contact, float, str]]:
    """Find existing contacts sharing phone/mobile/email with the given
    identifiers. Used by the contract preview pipeline."""
    if not (phone or mobile or email):
        return []
    p = phone.strip() if phone else None
    m = mobile.strip() if mobile else None
    e = email.lower().strip() if email else None

    others = (await session.execute(select(Contact))).scalars().all()
    out: list[tuple[Contact, float, str]] = []
    for other in others:
        reasons: list[str] = []
        if m and other.mobile and m == other.mobile.strip():
            reasons.append(f"shared mobile {m!r}")
        if p and other.phone and p == other.phone.strip():
            reasons.append(f"shared phone {p!r}")
        if e and other.email and e == other.email.lower().strip():
            reasons.append(f"shared email {e!r}")
        if reasons:
            out.append((other, 0.95, "; ".join(reasons)))
    return out


