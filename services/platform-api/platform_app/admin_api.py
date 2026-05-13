"""Platform admin API (`/api/admin/*`).

Cross-enterprise operations: list / view / create / update enterprises,
manage their members and agent_grants, view all users, toggle the
``is_platform_admin`` flag. Every endpoint requires
``users.is_platform_admin = 1`` on the caller.

Self-service editing of one's own enterprise lives in ``enterprise_api.py``.
"""
from __future__ import annotations
import time
import uuid
from fastapi import APIRouter, Body, HTTPException, Path, Request
from . import auth, db
from .api import _user_from_request

router = APIRouter(prefix="/api/admin")

_VALID_ROLES = ("owner", "admin", "member")
_VALID_PLANS = ("trial", "standard", "enterprise")
_VALID_STAGES = ("signed_up", "configured", "active")


def _require_platform_admin(request: Request) -> dict:
    user = _user_from_request(request)
    if not db.is_platform_admin(user["id"]):
        raise HTTPException(403, {"error": "not_platform_admin"})
    return user


def _now() -> int:
    return int(time.time())


# ─── enterprises ────────────────────────────────────────────────

@router.get("/enterprises")
def list_enterprises(request: Request) -> dict:
    _require_platform_admin(request)
    rows = db.main().execute(
        "SELECT e.id, e.legal_name, e.display_name, e.industry, e.region, "
        "       e.plan, e.onboarding_stage, e.active, e.created_at, "
        "       (SELECT COUNT(*) FROM enterprise_members em "
        "          WHERE em.enterprise_id = e.id) AS member_count, "
        "       (SELECT COUNT(*) FROM tenants t "
        "          WHERE t.client_id = e.id AND t.active=1) AS agent_count "
        "FROM enterprises e "
        "ORDER BY e.created_at DESC"
    ).fetchall()
    return {"enterprises": [dict(r) for r in rows]}


@router.post("/enterprises")
def create_enterprise(request: Request, body: dict = Body(...)) -> dict:
    _require_platform_admin(request)
    eid = (body.get("id") or "").strip().lower()
    if not eid or not eid.replace("-", "").replace("_", "").isalnum():
        raise HTTPException(400, {"error": "invalid_id",
                                  "message": "id 仅支持小写字母 / 数字 / - / _"})
    legal_name = body.get("legal_name") or eid
    display_name = body.get("display_name") or legal_name
    plan = body.get("plan", "trial")
    if plan not in _VALID_PLANS:
        raise HTTPException(400, {"error": "invalid_plan"})
    db.main().execute(
        "INSERT INTO enterprises (id, legal_name, display_name, industry, "
        "region, size_tier, tax_id, billing_email, plan, onboarding_stage, "
        "created_at) "
        "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,'signed_up',%s) "
        "ON CONFLICT (id) DO NOTHING",
        (eid, legal_name, display_name,
         body.get("industry"), body.get("region"), body.get("size_tier"),
         body.get("tax_id"), body.get("billing_email"), plan, _now()),
    )
    return _get_enterprise_or_404(eid)


@router.get("/enterprises/{enterprise_id}")
def get_enterprise(
    request: Request,
    enterprise_id: str = Path(..., pattern=r"^[a-z0-9_-]{1,64}$"),
) -> dict:
    _require_platform_admin(request)
    return _get_enterprise_or_404(enterprise_id)


@router.patch("/enterprises/{enterprise_id}")
def update_enterprise(
    request: Request,
    enterprise_id: str = Path(..., pattern=r"^[a-z0-9_-]{1,64}$"),
    body: dict = Body(...),
) -> dict:
    _require_platform_admin(request)
    return _update_enterprise(enterprise_id, body, scope="admin")


@router.delete("/enterprises/{enterprise_id}")
def deactivate_enterprise(
    request: Request,
    enterprise_id: str = Path(..., pattern=r"^[a-z0-9_-]{1,64}$"),
) -> dict:
    _require_platform_admin(request)
    db.main().execute(
        "UPDATE enterprises SET active=0 WHERE id=%s", (enterprise_id,),
    )
    return {"ok": True}


def _get_enterprise_or_404(eid: str) -> dict:
    row = db.main().execute(
        "SELECT * FROM enterprises WHERE id=%s", (eid,),
    ).fetchone()
    if not row:
        raise HTTPException(404, {"error": "enterprise_not_found"})
    out = dict(row)

    members = db.main().execute(
        "SELECT em.user_id, em.role, em.granted_at, "
        "       u.username, u.display_name, u.email "
        "FROM enterprise_members em JOIN users u ON u.id = em.user_id "
        "WHERE em.enterprise_id=%s "
        "ORDER BY em.granted_at",
        (eid,),
    ).fetchall()
    out["members"] = [dict(r) for r in members]

    agents = db.main().execute(
        "SELECT agent_id, display_name, container_url, agent_version, "
        "       health, active FROM tenants WHERE client_id=%s "
        "ORDER BY agent_id",
        (eid,),
    ).fetchall()
    out["agents"] = [dict(r) for r in agents]

    grants = db.main().execute(
        "SELECT ag.user_id, ag.agent_id, ag.role, ag.granted_at, "
        "       u.username, u.display_name "
        "FROM agent_grants ag JOIN users u ON u.id = ag.user_id "
        "WHERE ag.client_id=%s "
        "ORDER BY ag.granted_at",
        (eid,),
    ).fetchall()
    out["agent_grants"] = [dict(r) for r in grants]
    return out


# Shared by admin_api.update_enterprise and enterprise_api.update_enterprise.
# scope="owner" only allows a safe subset of fields (no plan / contract /
# onboarding_stage / active manipulation by tenants themselves).
_OWNER_EDITABLE = {"legal_name", "display_name", "industry", "region",
                   "size_tier", "tax_id", "billing_email"}
_ADMIN_EDITABLE = _OWNER_EDITABLE | {"plan", "contract_start", "contract_end",
                                     "onboarding_stage", "active",
                                     "primary_contact_user_id"}


def _update_enterprise(eid: str, body: dict, *, scope: str) -> dict:
    allowed = _ADMIN_EDITABLE if scope == "admin" else _OWNER_EDITABLE
    fields = {k: v for k, v in body.items() if k in allowed}
    if not fields:
        return _get_enterprise_or_404(eid)
    if "plan" in fields and fields["plan"] not in _VALID_PLANS:
        raise HTTPException(400, {"error": "invalid_plan"})
    if "onboarding_stage" in fields and fields["onboarding_stage"] not in _VALID_STAGES:
        raise HTTPException(400, {"error": "invalid_stage"})
    set_sql = ", ".join(f"{k}=%s" for k in fields)
    db.main().execute(
        f"UPDATE enterprises SET {set_sql} WHERE id=%s",
        (*fields.values(), eid),
    )
    return _get_enterprise_or_404(eid)


# ─── enterprise members ─────────────────────────────────────────

@router.post("/enterprises/{enterprise_id}/members")
def add_member(
    request: Request,
    enterprise_id: str = Path(..., pattern=r"^[a-z0-9_-]{1,64}$"),
    body: dict = Body(...),
) -> dict:
    _require_platform_admin(request)
    return _add_member(enterprise_id, body, granted_by="admin_api")


def _add_member(eid: str, body: dict, *, granted_by: str) -> dict:
    user_id = body.get("user_id") or body.get("username")
    role = body.get("role", "member")
    if role not in _VALID_ROLES:
        raise HTTPException(400, {"error": "invalid_role"})
    if not user_id:
        raise HTTPException(400, {"error": "missing_user"})
    # Allow username or user_id; resolve to id.
    row = db.main().execute(
        "SELECT id FROM users WHERE id=%s OR username=%s LIMIT 1",
        (user_id, user_id),
    ).fetchone()
    if not row:
        raise HTTPException(404, {"error": "user_not_found"})
    uid = row["id"]
    db.main().execute(
        "INSERT INTO enterprise_members (user_id, enterprise_id, role, granted_at, granted_by) "
        "VALUES (%s,%s,%s,%s,%s) "
        "ON CONFLICT (user_id, enterprise_id) DO UPDATE "
        "SET role=EXCLUDED.role, granted_at=EXCLUDED.granted_at, granted_by=EXCLUDED.granted_by",
        (uid, eid, role, _now(), granted_by),
    )
    db.invalidate_acl_for_enterprise(uid, eid)
    return {"ok": True, "user_id": uid, "role": role}


@router.patch("/enterprises/{enterprise_id}/members/{user_id}")
def update_member_role(
    request: Request,
    enterprise_id: str = Path(..., pattern=r"^[a-z0-9_-]{1,64}$"),
    user_id: str = Path(...),
    body: dict = Body(...),
) -> dict:
    _require_platform_admin(request)
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


@router.delete("/enterprises/{enterprise_id}/members/{user_id}")
def remove_member(
    request: Request,
    enterprise_id: str = Path(..., pattern=r"^[a-z0-9_-]{1,64}$"),
    user_id: str = Path(...),
) -> dict:
    _require_platform_admin(request)
    db.main().execute(
        "DELETE FROM enterprise_members WHERE user_id=%s AND enterprise_id=%s",
        (user_id, enterprise_id),
    )
    db.invalidate_acl_for_enterprise(user_id, enterprise_id)
    return {"ok": True}


# ─── agent_grants (consultant exception) ────────────────────────

@router.post("/enterprises/{enterprise_id}/agent-grants")
def add_agent_grant(
    request: Request,
    enterprise_id: str = Path(..., pattern=r"^[a-z0-9_-]{1,64}$"),
    body: dict = Body(...),
) -> dict:
    _require_platform_admin(request)
    user_id = body.get("user_id") or body.get("username")
    agent_id = body.get("agent_id")
    role = body.get("role", "user")
    if not (user_id and agent_id):
        raise HTTPException(400, {"error": "missing_fields"})
    row = db.main().execute(
        "SELECT id FROM users WHERE id=%s OR username=%s LIMIT 1",
        (user_id, user_id),
    ).fetchone()
    if not row:
        raise HTTPException(404, {"error": "user_not_found"})
    uid = row["id"]
    if not db.main().execute(
        "SELECT 1 FROM tenants WHERE client_id=%s AND agent_id=%s",
        (enterprise_id, agent_id),
    ).fetchone():
        raise HTTPException(404, {"error": "agent_not_found"})
    db.main().execute(
        "INSERT INTO agent_grants (user_id, client_id, agent_id, role, granted_at, granted_by) "
        "VALUES (%s,%s,%s,%s,%s,%s) "
        "ON CONFLICT (user_id, client_id, agent_id) DO UPDATE "
        "SET role=EXCLUDED.role, granted_at=EXCLUDED.granted_at, granted_by=EXCLUDED.granted_by",
        (uid, enterprise_id, agent_id, role, _now(), "admin_api"),
    )
    db.invalidate_acl(uid, enterprise_id, agent_id)
    return {"ok": True, "user_id": uid, "agent_id": agent_id, "role": role}


@router.delete("/enterprises/{enterprise_id}/agent-grants/{user_id}/{agent_id}")
def remove_agent_grant(
    request: Request,
    enterprise_id: str = Path(..., pattern=r"^[a-z0-9_-]{1,64}$"),
    user_id: str = Path(...),
    agent_id: str = Path(...),
) -> dict:
    _require_platform_admin(request)
    db.main().execute(
        "DELETE FROM agent_grants "
        "WHERE user_id=%s AND client_id=%s AND agent_id=%s",
        (user_id, enterprise_id, agent_id),
    )
    db.invalidate_acl(user_id, enterprise_id, agent_id)
    return {"ok": True}


# ─── users (cross-enterprise) ───────────────────────────────────

@router.get("/users")
def list_users(request: Request) -> dict:
    _require_platform_admin(request)
    rows = db.main().execute(
        "SELECT u.id, u.username, u.display_name, u.email, u.is_platform_admin, "
        "       u.created_at, u.last_login, "
        "       (SELECT COUNT(*) FROM enterprise_members em WHERE em.user_id = u.id) "
        "         AS enterprise_count "
        "FROM users u ORDER BY u.created_at DESC"
    ).fetchall()
    return {"users": [dict(r) for r in rows]}


@router.get("/users/{user_id}")
def get_user(
    request: Request,
    user_id: str = Path(...),
) -> dict:
    _require_platform_admin(request)
    user = db.main().execute(
        "SELECT id, username, display_name, email, is_platform_admin, "
        "created_at, last_login FROM users WHERE id=%s",
        (user_id,),
    ).fetchone()
    if not user:
        raise HTTPException(404, {"error": "user_not_found"})
    out = dict(user)
    memberships = db.main().execute(
        "SELECT em.enterprise_id, em.role, em.granted_at, "
        "       e.display_name AS enterprise_display_name "
        "FROM enterprise_members em JOIN enterprises e ON e.id = em.enterprise_id "
        "WHERE em.user_id=%s ORDER BY em.granted_at",
        (user_id,),
    ).fetchall()
    out["memberships"] = [dict(r) for r in memberships]
    return out


@router.post("/users")
def create_user(request: Request, body: dict = Body(...)) -> dict:
    _require_platform_admin(request)
    username = (body.get("username") or "").strip()
    password = body.get("password") or ""
    display_name = body.get("display_name") or username
    if not username or not password:
        raise HTTPException(400, {"error": "missing_credentials"})
    if not username.replace("_", "").replace("-", "").isalnum():
        raise HTTPException(400, {"error": "invalid_username"})
    user_id = f"u_{username}"
    try:
        db.main().execute(
            "INSERT INTO users (id, username, password_hash, display_name, "
            "email, created_at) VALUES (%s,%s,%s,%s,%s,%s)",
            (user_id, username, auth.hash_password(password), display_name,
             body.get("email"), _now()),
        )
    except Exception as e:
        raise HTTPException(409, {"error": "user_create_failed", "message": str(e)})
    return {"id": user_id, "username": username, "display_name": display_name}


@router.patch("/users/{user_id}/admin")
def set_platform_admin(
    request: Request,
    user_id: str = Path(...),
    body: dict = Body(...),
) -> dict:
    _require_platform_admin(request)
    is_admin = bool(body.get("is_platform_admin"))
    res = db.main().execute(
        "UPDATE users SET is_platform_admin=%s WHERE id=%s RETURNING id",
        (1 if is_admin else 0, user_id),
    ).fetchone()
    if not res:
        raise HTTPException(404, {"error": "user_not_found"})
    return {"ok": True, "is_platform_admin": is_admin}
