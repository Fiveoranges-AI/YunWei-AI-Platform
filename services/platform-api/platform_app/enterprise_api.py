"""Enterprise self-service API (`/api/enterprise/*`).

Customer-facing — for users who are members of an enterprise. The
``owner`` role can edit profile + manage members; ``admin`` can manage
members; ``member`` is read-only. Cross-enterprise operations live in
``admin_api.py``.
"""
from __future__ import annotations
from fastapi import APIRouter, Body, HTTPException, Path, Request
from . import db
from .admin_api import (
    _add_member, _get_enterprise_or_404, _now, _update_enterprise,
    _VALID_ROLES,
)
from .api import _user_from_request

router = APIRouter(prefix="/api/enterprise")


def _require_member(request: Request, eid: str) -> dict:
    """Caller must be a member of `eid` (or platform admin). Returns the
    user dict with an extra ``role`` field carrying the enterprise role
    (or ``"platform_admin"`` for cross-enterprise admins).
    """
    user = _user_from_request(request)
    if db.is_platform_admin(user["id"]):
        return {**user, "role": "platform_admin"}
    role = db.get_enterprise_role(user["id"], eid)
    if role is None:
        raise HTTPException(403, {"error": "not_member"})
    return {**user, "role": role}


def _require_role(role: str, allowed: tuple[str, ...]) -> None:
    if role == "platform_admin":
        return
    if role not in allowed:
        raise HTTPException(403, {"error": "insufficient_role", "required": list(allowed)})


# ─── profile ────────────────────────────────────────────────────

@router.get("/{enterprise_id}")
def get_enterprise(
    request: Request,
    enterprise_id: str = Path(..., pattern=r"^[a-z0-9_-]{1,64}$"),
) -> dict:
    _require_member(request, enterprise_id)
    return _get_enterprise_or_404(enterprise_id)


@router.patch("/{enterprise_id}")
def update_enterprise(
    request: Request,
    enterprise_id: str = Path(..., pattern=r"^[a-z0-9_-]{1,64}$"),
    body: dict = Body(...),
) -> dict:
    user = _require_member(request, enterprise_id)
    _require_role(user["role"], ("owner",))
    return _update_enterprise(enterprise_id, body, scope="owner")


# ─── members ────────────────────────────────────────────────────

@router.get("/{enterprise_id}/members")
def list_members(
    request: Request,
    enterprise_id: str = Path(..., pattern=r"^[a-z0-9_-]{1,64}$"),
) -> dict:
    _require_member(request, enterprise_id)
    rows = db.main().execute(
        "SELECT em.user_id, em.role, em.granted_at, em.granted_by, "
        "       u.username, u.display_name, u.email "
        "FROM enterprise_members em JOIN users u ON u.id = em.user_id "
        "WHERE em.enterprise_id=%s "
        "ORDER BY em.granted_at",
        (enterprise_id,),
    ).fetchall()
    return {"members": [dict(r) for r in rows]}


@router.post("/{enterprise_id}/members")
def add_member(
    request: Request,
    enterprise_id: str = Path(..., pattern=r"^[a-z0-9_-]{1,64}$"),
    body: dict = Body(...),
) -> dict:
    user = _require_member(request, enterprise_id)
    _require_role(user["role"], ("owner", "admin"))
    requested_role = body.get("role", "member")
    # An admin cannot mint a new owner — only platform admin or existing owner can.
    if requested_role == "owner" and user["role"] not in ("owner", "platform_admin"):
        raise HTTPException(403, {"error": "only_owner_can_create_owner"})
    return _add_member(enterprise_id, body, granted_by=user["id"])


@router.patch("/{enterprise_id}/members/{user_id}")
def update_member(
    request: Request,
    enterprise_id: str = Path(..., pattern=r"^[a-z0-9_-]{1,64}$"),
    user_id: str = Path(...),
    body: dict = Body(...),
) -> dict:
    actor = _require_member(request, enterprise_id)
    _require_role(actor["role"], ("owner",))
    role = body.get("role")
    if role not in _VALID_ROLES:
        raise HTTPException(400, {"error": "invalid_role"})
    res = db.main().execute(
        "UPDATE enterprise_members SET role=%s WHERE user_id=%s AND enterprise_id=%s "
        "RETURNING user_id",
        (role, user_id, enterprise_id),
    ).fetchone()
    if not res:
        raise HTTPException(404, {"error": "membership_not_found"})
    db.invalidate_acl_for_enterprise(user_id, enterprise_id)
    return {"ok": True, "role": role}


@router.delete("/{enterprise_id}/members/{user_id}")
def remove_member(
    request: Request,
    enterprise_id: str = Path(..., pattern=r"^[a-z0-9_-]{1,64}$"),
    user_id: str = Path(...),
) -> dict:
    actor = _require_member(request, enterprise_id)
    _require_role(actor["role"], ("owner", "admin"))
    # Don't let an owner-of-a-different-id remove the *last* owner —
    # would leave the enterprise un-administered.
    if actor["role"] != "platform_admin":
        target_role = db.get_enterprise_role(user_id, enterprise_id)
        if target_role == "owner":
            owner_count = db.main().execute(
                "SELECT COUNT(*) AS n FROM enterprise_members "
                "WHERE enterprise_id=%s AND role='owner'",
                (enterprise_id,),
            ).fetchone()["n"]
            if owner_count <= 1:
                raise HTTPException(409, {"error": "last_owner_cannot_be_removed"})
    db.main().execute(
        "DELETE FROM enterprise_members WHERE user_id=%s AND enterprise_id=%s",
        (user_id, enterprise_id),
    )
    db.invalidate_acl_for_enterprise(user_id, enterprise_id)
    return {"ok": True}
