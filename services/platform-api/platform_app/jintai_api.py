"""锦泰耐火材料 MVP API.

Phase 2 surface:
- read-only production overview / products / flow cards
- AI extraction queue create/list/review

This module intentionally reads from the separate ``jintai_mvp`` schema in the
platform database. It does not touch the existing 智通客户 tenant databases and
does not connect to 用友 or any customer on-premise database.
"""
from __future__ import annotations

import json
import os
import uuid
from datetime import date

from fastapi import APIRouter, Body, HTTPException, Path, Query, Request

from . import db
from .context import AuthContext, require_auth_context

router = APIRouter(prefix="/api/jintai")

_TENANT_SLUG = "jintai-refractory"
_ALLOWED_ENTERPRISE_IDS = {
    item.strip()
    for item in os.environ.get("JINTAI_MVP_ENTERPRISE_IDS", "jintai-demo,jintai").split(",")
    if item.strip()
}
_VALID_QUEUE_ACTIONS = {"confirm", "reject"}
_VALID_QUEUE_STATUSES = {"pending_review", "confirmed", "rejected"}
_QUEUE_STATUS_ALIASES = {"pending": "pending_review"}
_VALID_FLOW_CARD_STATUSES = {
    "created",
    "in_progress",
    "delayed",
    "quantity_exception",
    "completed",
}
_VALID_ORDER_STATUSES = {"created", "in_production", "delayed", "exception", "completed"}
_VALID_STEP_CODES = {"forming", "sintering", "inspection_packaging"}
_VALID_EXTRACTION_TYPES = {
    "ocr_flow_card",
    "excel_sales_order",
    "quality_exception",
    "manual_note",
}
_VALID_TARGET_TABLES = {
    "production_flow_cards",
    "sales_orders",
    "customers",
    "products",
    "production_step_records",
}
_VALID_REVIEW_ROLES = {
    "owner",
    "production_manager",
    "forming_operator",
    "sintering_operator",
    "inspection_packaging_operator",
}
_WRITER_ENTERPRISE_ROLES = {"owner", "admin"}


def _require_context(request: Request) -> AuthContext:
    ctx = require_auth_context(request)
    if db.is_platform_admin(ctx.user_id) or ctx.enterprise_id in _ALLOWED_ENTERPRISE_IDS:
        return ctx
    raise HTTPException(403, {"error": "jintai_access_denied"})


def _require_writer(ctx: AuthContext) -> None:
    if ctx.enterprise_role not in _WRITER_ENTERPRISE_ROLES:
        raise HTTPException(403, {"error": "insufficient_role"})


def _json_object(value: object, field_name: str) -> dict:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise HTTPException(400, {"error": "invalid_json_object", "field": field_name})
    return value


def _confidence(value: object) -> float | None:
    if value is None or value == "":
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        raise HTTPException(400, {"error": "invalid_confidence"})
    if parsed < 0 or parsed > 1:
        raise HTTPException(400, {"error": "invalid_confidence"})
    return parsed


def _optional_allowlist(value: object, valid: set[str], error: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise HTTPException(400, {"error": error})
    clean = value.strip()
    if clean not in valid:
        raise HTTPException(400, {"error": error})
    return clean


def _queue_status(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise HTTPException(400, {"error": "invalid_status"})
    clean = _QUEUE_STATUS_ALIASES.get(value.strip(), value.strip())
    if clean not in _VALID_QUEUE_STATUSES:
        raise HTTPException(400, {"error": "invalid_status"})
    return clean


def _tenant_or_404() -> dict:
    row = db.main().execute(
        "SELECT id, slug, display_name, legal_name, industry, region, website_url, status "
        "FROM jintai_mvp.tenants WHERE slug=%s",
        (_TENANT_SLUG,),
    ).fetchone()
    if not row:
        raise HTTPException(
            404,
            {
                "error": "jintai_seed_missing",
                "message": "锦泰 MVP 数据未初始化，请先运行 seed SQL",
            },
        )
    return dict(row)


def _tenant_id() -> str:
    return str(_tenant_or_404()["id"])


def _profile_id_for_review(ctx: AuthContext, reviewer_role_code: str | None) -> str | None:
    tenant_id = _tenant_id()
    if reviewer_role_code:
        reviewer_role_code = _optional_allowlist(
            reviewer_role_code,
            _VALID_REVIEW_ROLES,
            "invalid_reviewer_role",
        )
        row = db.main().execute(
            "SELECT id FROM jintai_mvp.profiles "
            "WHERE tenant_id=%s AND role_code=%s AND status='active'",
            (tenant_id, reviewer_role_code),
        ).fetchone()
        if not row:
            raise HTTPException(400, {"error": "reviewer_profile_not_found"})
        return str(row["id"])
    row = db.main().execute(
        "SELECT id FROM jintai_mvp.profiles "
        "WHERE tenant_id=%s AND platform_user_id=%s AND status='active'",
        (tenant_id, ctx.user_id),
    ).fetchone()
    if row:
        return str(row["id"])
    row = db.main().execute(
        "SELECT id FROM jintai_mvp.profiles "
        "WHERE tenant_id=%s AND role_code='production_manager' AND status='active'",
        (tenant_id,),
    ).fetchone()
    return str(row["id"]) if row else None


def _profile_id_for_user(ctx: AuthContext) -> str | None:
    row = db.main().execute(
        "SELECT id FROM jintai_mvp.profiles "
        "WHERE tenant_id=%s AND platform_user_id=%s AND status='active'",
        (_tenant_id(), ctx.user_id),
    ).fetchone()
    return str(row["id"]) if row else None


def _queue_row(queue_no: str) -> dict:
    row = db.main().execute(
        "SELECT id, tenant_id, queue_no, attachment_id, source_document_name, "
        "       extraction_type, target_table, payload, extracted_data, confidence, "
        "       reviewed_by_profile_id, reviewed_at, status, source_system, "
        "       source_record_id, created_at, updated_at "
        "FROM jintai_mvp.ai_extraction_queue "
        "WHERE tenant_id=%s AND queue_no=%s",
        (_tenant_id(), queue_no),
    ).fetchone()
    if not row:
        raise HTTPException(404, {"error": "queue_item_not_found"})
    return dict(row)


def _insert_queue_item(
    *,
    tenant_id: str,
    queue_no: str,
    attachment_id: object | None,
    source_document_name: str | None,
    extraction_type: str,
    target_table: str | None,
    payload: dict,
    extracted_data: dict,
    confidence: float | None,
    source_system: str,
    source_record_id: str | None,
) -> dict:
    row = db.main().execute(
        "INSERT INTO jintai_mvp.ai_extraction_queue "
        "(tenant_id, queue_no, attachment_id, source_document_name, extraction_type, "
        " target_table, payload, extracted_data, confidence, status, source_system, "
        " source_record_id) "
        "VALUES (%s,%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s,'pending_review',%s,%s) "
        "RETURNING queue_no",
        (
            tenant_id,
            queue_no,
            attachment_id,
            source_document_name,
            extraction_type,
            target_table,
            json.dumps(payload, ensure_ascii=False),
            json.dumps(extracted_data, ensure_ascii=False),
            confidence,
            source_system,
            source_record_id,
        ),
    ).fetchone()
    return _queue_row(row["queue_no"])


@router.get("/overview")
def overview(request: Request) -> dict:
    _require_context(request)
    tenant = _tenant_or_404()
    tenant_id = tenant["id"]

    flow = db.main().execute(
        "SELECT "
        "  COUNT(*) AS total_flow_cards, "
        "  COUNT(*) FILTER (WHERE status='delayed') AS delayed_flow_cards, "
        "  COUNT(*) FILTER (WHERE current_step_code='sintering') AS sintering_flow_cards, "
        "  COUNT(*) FILTER (WHERE status='quantity_exception') AS quantity_exception_flow_cards, "
        "  COUNT(*) FILTER (WHERE status='completed') AS completed_flow_cards, "
        "  COUNT(*) FILTER (WHERE status='created') AS created_flow_cards, "
        "  COALESCE(SUM(planned_quantity), 0) AS planned_quantity, "
        "  COALESCE(SUM(completed_quantity), 0) AS completed_quantity, "
        "  COALESCE(SUM(defective_quantity), 0) AS defective_quantity "
        "FROM jintai_mvp.production_flow_cards "
        "WHERE tenant_id=%s",
        (tenant_id,),
    ).fetchone()
    queue = db.main().execute(
        "SELECT "
        "  COUNT(*) FILTER (WHERE status='pending_review') AS pending_review, "
        "  COUNT(*) FILTER (WHERE status='confirmed') AS confirmed, "
        "  COUNT(*) FILTER (WHERE status='rejected') AS rejected "
        "FROM jintai_mvp.ai_extraction_queue "
        "WHERE tenant_id=%s",
        (tenant_id,),
    ).fetchone()
    products = db.main().execute(
        "SELECT COUNT(*) AS total_products, "
        "       COUNT(*) FILTER (WHERE quality_risk_level='high') AS high_risk_products "
        "FROM jintai_mvp.products "
        "WHERE tenant_id=%s AND status='active'",
        (tenant_id,),
    ).fetchone()
    return {
        "tenant": tenant,
        "kpis": dict(flow),
        "queue": dict(queue),
        "products": dict(products),
    }


@router.get("/customers")
def list_customers(
    request: Request,
    status: str | None = Query(None, max_length=64),
    limit: int = Query(50, ge=1, le=200),
) -> dict:
    _require_context(request)
    where = ["c.tenant_id=%s"]
    params: list[object] = [_tenant_id()]
    if status is not None:
        status = status.strip()
        if status not in {"active", "inactive"}:
            raise HTTPException(400, {"error": "invalid_status"})
        where.append("c.status=%s")
        params.append(status)
    params.append(limit)
    rows = db.main().execute(
        "SELECT c.id, c.customer_code, c.full_name, c.short_name, c.contact_name, "
        "       c.phone, c.address, c.credit_level, c.status, "
        "       COUNT(so.id) AS order_count, "
        "       COALESCE(SUM(so.amount_total), 0) AS order_amount_total "
        "FROM jintai_mvp.customers c "
        "LEFT JOIN jintai_mvp.sales_orders so ON so.customer_id=c.id "
        f"WHERE {' AND '.join(where)} "
        "GROUP BY c.id "
        "ORDER BY c.customer_code "
        "LIMIT %s",
        tuple(params),
    ).fetchall()
    return {"customers": [dict(r) for r in rows]}


@router.get("/products")
def list_products(request: Request) -> dict:
    _require_context(request)
    rows = db.main().execute(
        "SELECT p.id, p.sku, p.name, p.category, p.specification, p.unit, "
        "       p.quality_risk_level, p.status, "
        "       COUNT(fc.id) AS flow_card_count, "
        "       COALESCE(SUM(fc.planned_quantity), 0) AS planned_quantity, "
        "       COALESCE(SUM(fc.defective_quantity), 0) AS defective_quantity "
        "FROM jintai_mvp.products p "
        "LEFT JOIN jintai_mvp.production_flow_cards fc "
        "  ON fc.product_id=p.id AND fc.tenant_id=p.tenant_id "
        "WHERE p.tenant_id=%s "
        "GROUP BY p.id "
        "ORDER BY p.sku",
        (_tenant_id(),),
    ).fetchall()
    return {"products": [dict(r) for r in rows]}


@router.get("/orders")
def list_orders(
    request: Request,
    status: str | None = Query(None, max_length=64),
    limit: int = Query(50, ge=1, le=200),
) -> dict:
    _require_context(request)
    status = _optional_allowlist(status, _VALID_ORDER_STATUSES, "invalid_status")
    where = ["so.tenant_id=%s"]
    params: list[object] = [_tenant_id()]
    if status is not None:
        where.append("so.status=%s")
        params.append(status)
    params.append(limit)
    rows = db.main().execute(
        "SELECT so.id, so.order_no, so.order_date, so.promised_delivery_date, "
        "       so.quantity, so.unit, so.amount_total, so.currency, so.priority, "
        "       so.status, c.short_name AS customer_name, "
        "       p.sku AS product_sku, p.name AS product_name, "
        "       fc.flow_card_no, fc.current_step_code, fc.status AS flow_card_status "
        "FROM jintai_mvp.sales_orders so "
        "JOIN jintai_mvp.customers c ON c.id=so.customer_id "
        "JOIN jintai_mvp.products p ON p.id=so.product_id "
        "LEFT JOIN jintai_mvp.production_flow_cards fc ON fc.sales_order_id=so.id "
        f"WHERE {' AND '.join(where)} "
        "ORDER BY so.promised_delivery_date NULLS LAST, so.order_no "
        "LIMIT %s",
        tuple(params),
    ).fetchall()
    return {"orders": [dict(r) for r in rows]}


@router.get("/process-routes")
def list_process_routes(
    request: Request,
    product_sku: str | None = Query(None, max_length=128),
) -> dict:
    _require_context(request)
    where = ["pr.tenant_id=%s"]
    params: list[object] = [_tenant_id()]
    if product_sku:
        where.append("p.sku=%s")
        params.append(product_sku.strip())
    routes = db.main().execute(
        "SELECT pr.id, pr.route_code, pr.route_name, pr.version, pr.is_default, "
        "       pr.status, p.sku AS product_sku, p.name AS product_name "
        "FROM jintai_mvp.process_routes pr "
        "JOIN jintai_mvp.products p ON p.id=pr.product_id "
        f"WHERE {' AND '.join(where)} "
        "ORDER BY p.sku, pr.version",
        tuple(params),
    ).fetchall()
    if not routes:
        return {"routes": []}
    route_ids = [r["id"] for r in routes]
    steps = db.main().execute(
        "SELECT route_id, step_code, step_name, step_sequence, workstation, "
        "       standard_hours, required_role_code, qc_points, status "
        "FROM jintai_mvp.process_steps "
        "WHERE tenant_id=%s AND route_id = ANY(%s::uuid[]) "
        "ORDER BY route_id, step_sequence",
        (_tenant_id(), route_ids),
    ).fetchall()
    steps_by_route: dict[object, list[dict]] = {}
    for step in steps:
        steps_by_route.setdefault(step["route_id"], []).append(dict(step))
    return {
        "routes": [
            {**dict(route), "steps": steps_by_route.get(route["id"], [])}
            for route in routes
        ]
    }


@router.get("/process-parameters")
def list_process_parameters(
    request: Request,
    product_sku: str | None = Query(None, max_length=128),
) -> dict:
    _require_context(request)
    where = ["ps.tenant_id=%s"]
    params: list[object] = [_tenant_id()]
    if product_sku:
        where.append("p.sku=%s")
        params.append(product_sku.strip())
    rows = db.main().execute(
        "SELECT p.sku AS product_sku, p.name AS product_name, "
        "       pr.route_code, pr.route_name, pr.version, "
        "       ps.step_code, ps.step_name, ps.step_sequence, ps.workstation, "
        "       ps.standard_hours, ps.required_role_code, ps.qc_points, ps.status "
        "FROM jintai_mvp.process_steps ps "
        "JOIN jintai_mvp.process_routes pr ON pr.id=ps.route_id "
        "JOIN jintai_mvp.products p ON p.id=pr.product_id "
        f"WHERE {' AND '.join(where)} "
        "ORDER BY p.sku, ps.step_sequence",
        tuple(params),
    ).fetchall()
    return {"process_parameters": [dict(r) for r in rows]}


@router.get("/source-mappings")
def list_source_mappings(
    request: Request,
    source_system: str | None = Query(None, max_length=128),
    local_table: str | None = Query(None, max_length=128),
    limit: int = Query(50, ge=1, le=200),
) -> dict:
    _require_context(request)
    where = ["tenant_id=%s"]
    params: list[object] = [_tenant_id()]
    if source_system:
        where.append("source_system=%s")
        params.append(source_system.strip())
    if local_table:
        local_table = _optional_allowlist(
            local_table,
            _VALID_TARGET_TABLES,
            "invalid_local_table",
        )
        where.append("local_table=%s")
        params.append(local_table)
    params.append(limit)
    rows = db.main().execute(
        "SELECT id, source_system, source_table, source_record_id, local_table, "
        "       local_record_id, sync_direction, last_seen_at, metadata, status, "
        "       created_at, updated_at "
        "FROM jintai_mvp.external_source_mappings "
        f"WHERE {' AND '.join(where)} "
        "ORDER BY source_system, source_table, source_record_id "
        "LIMIT %s",
        tuple(params),
    ).fetchall()
    return {"mappings": [dict(r) for r in rows]}


@router.get("/briefing")
def daily_briefing(
    request: Request,
    briefing_date: date | None = Query(None),
) -> dict:
    _require_context(request)
    tenant_id = _tenant_id()
    target_date = briefing_date or date.today()

    risk_cards = db.main().execute(
        "SELECT fc.flow_card_no, fc.status, fc.current_step_code, fc.priority, "
        "       fc.due_at, fc.delay_reason, fc.quantity_variance_reason, "
        "       fc.planned_quantity, fc.completed_quantity, fc.defective_quantity, "
        "       c.short_name AS customer_name, p.sku AS product_sku, p.name AS product_name "
        "FROM jintai_mvp.production_flow_cards fc "
        "JOIN jintai_mvp.sales_orders so ON so.id=fc.sales_order_id "
        "JOIN jintai_mvp.customers c ON c.id=so.customer_id "
        "JOIN jintai_mvp.products p ON p.id=fc.product_id "
        "WHERE fc.tenant_id=%s "
        "  AND (fc.status IN ('delayed','quantity_exception') "
        "       OR fc.current_step_code='sintering' "
        "       OR (fc.due_at IS NOT NULL AND fc.due_at < (%s::date + interval '1 day') "
        "           AND fc.status <> 'completed')) "
        "ORDER BY "
        "  CASE fc.status WHEN 'delayed' THEN 0 WHEN 'quantity_exception' THEN 1 ELSE 2 END, "
        "  fc.due_at NULLS LAST, fc.flow_card_no",
        (tenant_id, target_date.isoformat()),
    ).fetchall()
    high_defect_products = db.main().execute(
        "SELECT p.sku, p.name, "
        "       SUM(sr.defective_quantity) AS defective_quantity, "
        "       NULLIF(SUM(COALESCE(sr.input_quantity, sr.output_quantity, 0)), 0) AS checked_quantity, "
        "       ROUND("
        "         SUM(sr.defective_quantity) / "
        "         NULLIF(SUM(COALESCE(sr.input_quantity, sr.output_quantity, 0)), 0), 4"
        "       ) AS defect_rate "
        "FROM jintai_mvp.production_step_records sr "
        "JOIN jintai_mvp.production_flow_cards fc ON fc.id=sr.flow_card_id "
        "JOIN jintai_mvp.products p ON p.id=fc.product_id "
        "WHERE sr.tenant_id=%s "
        "GROUP BY p.id "
        "HAVING SUM(sr.defective_quantity) >= 3 "
        "ORDER BY defect_rate DESC NULLS LAST, defective_quantity DESC "
        "LIMIT 5",
        (tenant_id,),
    ).fetchall()
    pending_queue = db.main().execute(
        "SELECT queue_no, source_document_name, extraction_type, target_table, "
        "       confidence, created_at "
        "FROM jintai_mvp.ai_extraction_queue "
        "WHERE tenant_id=%s AND status='pending_review' "
        "ORDER BY created_at DESC "
        "LIMIT 10",
        (tenant_id,),
    ).fetchall()
    counters = db.main().execute(
        "SELECT "
        "  COUNT(*) FILTER (WHERE status='delayed') AS delayed_flow_cards, "
        "  COUNT(*) FILTER (WHERE current_step_code='sintering') AS sintering_flow_cards, "
        "  COUNT(*) FILTER (WHERE status='quantity_exception') AS quantity_exception_flow_cards, "
        "  COUNT(*) FILTER (WHERE status='created') AS created_flow_cards "
        "FROM jintai_mvp.production_flow_cards "
        "WHERE tenant_id=%s",
        (tenant_id,),
    ).fetchone()
    return {
        "briefing_date": target_date.isoformat(),
        "counters": dict(counters),
        "risk_flow_cards": [dict(r) for r in risk_cards],
        "high_defect_products": [dict(r) for r in high_defect_products],
        "pending_ai_queue": [dict(r) for r in pending_queue],
        "recommendations": [
            "先处理延期和卡在烧结的急单，确认窑炉排队与温控复核状态。",
            "数量异常单只进入人工复核流程，确认补产或让步接收前不写回正式业务数据。",
            "高不良产品先按产品和工序追溯，不让 AI 直接修改生产记录。",
        ],
    }


@router.post("/ask")
def ask_jintai(
    request: Request,
    body: dict = Body(...),
) -> dict:
    ctx = _require_context(request)
    query_text = (body.get("query_text") or body.get("question") or "").strip()
    if not query_text:
        raise HTTPException(400, {"error": "missing_query_text"})
    if len(query_text) > 500:
        raise HTTPException(400, {"error": "query_too_long"})

    tenant_id = _tenant_id()
    lowered = query_text.lower()
    citations: list[dict] = []
    data: list[dict]
    if "延期" in query_text or "延迟" in query_text or "逾期" in query_text:
        rows = db.main().execute(
            "SELECT fc.id, fc.flow_card_no, fc.status, fc.due_at, fc.delay_reason, "
            "       c.short_name AS customer_name, p.sku AS product_sku, p.name AS product_name "
            "FROM jintai_mvp.production_flow_cards fc "
            "JOIN jintai_mvp.sales_orders so ON so.id=fc.sales_order_id "
            "JOIN jintai_mvp.customers c ON c.id=so.customer_id "
            "JOIN jintai_mvp.products p ON p.id=fc.product_id "
            "WHERE fc.tenant_id=%s AND fc.status='delayed' "
            "ORDER BY fc.due_at NULLS LAST, fc.flow_card_no",
            (tenant_id,),
        ).fetchall()
        data = [dict(r) for r in rows]
        citations = [{"table": "production_flow_cards", "id": str(r["id"])} for r in rows]
        answer = f"当前有 {len(data)} 张延期生产流转单。"
    elif "烧结" in query_text or "sinter" in lowered:
        rows = db.main().execute(
            "SELECT fc.id, fc.flow_card_no, fc.current_step_code, fc.due_at, "
            "       c.short_name AS customer_name, p.sku AS product_sku, p.name AS product_name "
            "FROM jintai_mvp.production_flow_cards fc "
            "JOIN jintai_mvp.sales_orders so ON so.id=fc.sales_order_id "
            "JOIN jintai_mvp.customers c ON c.id=so.customer_id "
            "JOIN jintai_mvp.products p ON p.id=fc.product_id "
            "WHERE fc.tenant_id=%s AND fc.current_step_code='sintering' "
            "ORDER BY fc.due_at NULLS LAST, fc.flow_card_no",
            (tenant_id,),
        ).fetchall()
        data = [dict(r) for r in rows]
        citations = [{"table": "production_flow_cards", "id": str(r["id"])} for r in rows]
        answer = f"当前有 {len(data)} 张生产流转单卡在烧结工序。"
    elif "数量" in query_text or "短少" in query_text:
        rows = db.main().execute(
            "SELECT id, flow_card_no, planned_quantity, completed_quantity, "
            "       defective_quantity, quantity_variance_reason, status "
            "FROM jintai_mvp.production_flow_cards "
            "WHERE tenant_id=%s AND status='quantity_exception' "
            "ORDER BY flow_card_no",
            (tenant_id,),
        ).fetchall()
        data = [dict(r) for r in rows]
        citations = [{"table": "production_flow_cards", "id": str(r["id"])} for r in rows]
        answer = f"当前有 {len(data)} 张数量异常生产流转单，需人工复核后再决定补产或入库。"
    elif "不良" in query_text or "质量" in query_text or "defect" in lowered:
        rows = db.main().execute(
            "SELECT p.id, p.sku, p.name, SUM(sr.defective_quantity) AS defective_quantity, "
            "       ROUND("
            "         SUM(sr.defective_quantity) / "
            "         NULLIF(SUM(COALESCE(sr.input_quantity, sr.output_quantity, 0)), 0), 4"
            "       ) AS defect_rate "
            "FROM jintai_mvp.production_step_records sr "
            "JOIN jintai_mvp.production_flow_cards fc ON fc.id=sr.flow_card_id "
            "JOIN jintai_mvp.products p ON p.id=fc.product_id "
            "WHERE sr.tenant_id=%s "
            "GROUP BY p.id "
            "HAVING SUM(sr.defective_quantity) >= 3 "
            "ORDER BY defect_rate DESC NULLS LAST, defective_quantity DESC "
            "LIMIT 5",
            (tenant_id,),
        ).fetchall()
        data = [dict(r) for r in rows]
        citations = [{"table": "products", "id": str(r["id"])} for r in rows]
        answer = f"当前样例数据中有 {len(data)} 个产品不良数量偏高。"
    else:
        row = db.main().execute(
            "SELECT COUNT(*) AS total_flow_cards, "
            "       COUNT(*) FILTER (WHERE status='delayed') AS delayed_flow_cards, "
            "       COUNT(*) FILTER (WHERE status='quantity_exception') AS quantity_exception_flow_cards, "
            "       COUNT(*) FILTER (WHERE status='completed') AS completed_flow_cards "
            "FROM jintai_mvp.production_flow_cards "
            "WHERE tenant_id=%s",
            (tenant_id,),
        ).fetchone()
        data = [dict(row)]
        answer = (
            f"当前共有 {row['total_flow_cards']} 张生产流转单，"
            f"{row['delayed_flow_cards']} 张延期，"
            f"{row['quantity_exception_flow_cards']} 张数量异常，"
            f"{row['completed_flow_cards']} 张已完成。"
        )
    log_row = db.main().execute(
        "INSERT INTO jintai_mvp.ai_query_logs "
        "(tenant_id, profile_id, query_text, answer_text, cited_entity_refs, "
        " model_name, status, source_system, source_record_id) "
        "VALUES (%s,%s,%s,%s,%s::jsonb,'jintai-rule-based-v0','answered','api:jintai_ask',%s) "
        "RETURNING id",
        (
            tenant_id,
            _profile_id_for_user(ctx),
            query_text,
            answer,
            json.dumps(citations, ensure_ascii=False),
            f"ask:{uuid.uuid4().hex[:12]}",
        ),
    ).fetchone()
    return {
        "answer": answer,
        "data": data,
        "citations": citations,
        "query_log_id": str(log_row["id"]),
    }


@router.get("/flow-cards")
def list_flow_cards(
    request: Request,
    status: str | None = Query(None, max_length=64),
    current_step_code: str | None = Query(None, max_length=64),
    limit: int = Query(50, ge=1, le=200),
) -> dict:
    _require_context(request)
    where = ["fc.tenant_id=%s"]
    params: list[object] = [_tenant_id()]
    status = _optional_allowlist(status, _VALID_FLOW_CARD_STATUSES, "invalid_status")
    current_step_code = _optional_allowlist(
        current_step_code,
        _VALID_STEP_CODES,
        "invalid_current_step_code",
    )
    if status is not None:
        where.append("fc.status=%s")
        params.append(status)
    if current_step_code is not None:
        where.append("fc.current_step_code=%s")
        params.append(current_step_code)
    params.append(limit)
    rows = db.main().execute(
        "SELECT fc.id, fc.flow_card_no, fc.planned_quantity, fc.completed_quantity, "
        "       fc.defective_quantity, fc.unit, fc.current_step_code, fc.priority, "
        "       fc.due_at, fc.started_at, fc.completed_at, fc.delay_reason, "
        "       fc.quantity_variance_reason, fc.status, "
        "       so.order_no, c.short_name AS customer_name, "
        "       p.sku AS product_sku, p.name AS product_name, p.quality_risk_level "
        "FROM jintai_mvp.production_flow_cards fc "
        "JOIN jintai_mvp.sales_orders so ON so.id=fc.sales_order_id "
        "JOIN jintai_mvp.customers c ON c.id=so.customer_id "
        "JOIN jintai_mvp.products p ON p.id=fc.product_id "
        f"WHERE {' AND '.join(where)} "
        "ORDER BY fc.due_at NULLS LAST, fc.flow_card_no "
        "LIMIT %s",
        tuple(params),
    ).fetchall()
    return {"flow_cards": [dict(r) for r in rows]}


@router.get("/flow-cards/{flow_card_no}")
def get_flow_card(
    request: Request,
    flow_card_no: str = Path(..., max_length=80),
) -> dict:
    _require_context(request)
    card = db.main().execute(
        "SELECT fc.*, so.order_no, so.order_date, so.promised_delivery_date, "
        "       c.full_name AS customer_name, p.sku AS product_sku, "
        "       p.name AS product_name, pr.route_code, pr.route_name "
        "FROM jintai_mvp.production_flow_cards fc "
        "JOIN jintai_mvp.sales_orders so ON so.id=fc.sales_order_id "
        "JOIN jintai_mvp.customers c ON c.id=so.customer_id "
        "JOIN jintai_mvp.products p ON p.id=fc.product_id "
        "JOIN jintai_mvp.process_routes pr ON pr.id=fc.process_route_id "
        "WHERE fc.tenant_id=%s AND fc.flow_card_no=%s",
        (_tenant_id(), flow_card_no),
    ).fetchone()
    if not card:
        raise HTTPException(404, {"error": "flow_card_not_found"})
    steps = db.main().execute(
        "SELECT sr.id, sr.step_code, sr.step_name, sr.step_sequence, "
        "       sr.input_quantity, sr.output_quantity, sr.defective_quantity, "
        "       sr.unit, sr.started_at, sr.completed_at, sr.equipment_code, "
        "       sr.exception_reason, sr.qc_result, sr.status, p.display_name AS operator_name "
        "FROM jintai_mvp.production_step_records sr "
        "LEFT JOIN jintai_mvp.profiles p ON p.id=sr.operator_profile_id "
        "WHERE sr.tenant_id=%s AND sr.flow_card_id=%s "
        "ORDER BY sr.step_sequence",
        (_tenant_id(), card["id"]),
    ).fetchall()
    return {"flow_card": dict(card), "step_records": [dict(r) for r in steps]}


@router.get("/ai-extraction-queue")
def list_ai_extraction_queue(
    request: Request,
    status: str | None = Query(None, max_length=64),
    limit: int = Query(50, ge=1, le=200),
) -> dict:
    _require_context(request)
    where = ["q.tenant_id=%s"]
    params: list[object] = [_tenant_id()]
    status = _queue_status(status)
    if status is not None:
        where.append("q.status=%s")
        params.append(status)
    params.append(limit)
    rows = db.main().execute(
        "SELECT q.id, q.queue_no, q.source_document_name, q.extraction_type, "
        "       q.target_table, q.payload, q.extracted_data, q.confidence, "
        "       q.reviewed_at, q.status, q.created_at, q.updated_at, "
        "       p.display_name AS reviewed_by "
        "FROM jintai_mvp.ai_extraction_queue q "
        "LEFT JOIN jintai_mvp.profiles p ON p.id=q.reviewed_by_profile_id "
        f"WHERE {' AND '.join(where)} "
        "ORDER BY q.created_at DESC "
        "LIMIT %s",
        tuple(params),
    ).fetchall()
    return {"items": [dict(r) for r in rows]}


@router.get("/extractions")
def list_extractions(
    request: Request,
    status: str | None = Query(None, max_length=64),
    limit: int = Query(50, ge=1, le=200),
) -> dict:
    return list_ai_extraction_queue(request, status=status, limit=limit)


@router.post("/ai-extraction-queue")
def create_ai_extraction_queue_item(
    request: Request,
    body: dict = Body(...),
) -> dict:
    ctx = _require_context(request)
    _require_writer(ctx)
    extraction_type = (body.get("extraction_type") or "").strip()
    if not extraction_type:
        raise HTTPException(400, {"error": "missing_extraction_type"})
    if extraction_type not in _VALID_EXTRACTION_TYPES:
        raise HTTPException(400, {"error": "invalid_extraction_type"})
    target_table = body.get("target_table")
    target_table = _optional_allowlist(
        target_table,
        _VALID_TARGET_TABLES,
        "invalid_target_table",
    )
    payload = _json_object(body.get("payload"), "payload")
    extracted_data = _json_object(body.get("extracted_data"), "extracted_data")
    confidence = _confidence(body.get("confidence"))
    queue_no = f"AIQ-JT-MANUAL-{uuid.uuid4().hex[:8].upper()}"
    item = _insert_queue_item(
        tenant_id=_tenant_id(),
        queue_no=queue_no,
        attachment_id=None,
        source_document_name=body.get("source_document_name"),
        extraction_type=extraction_type,
        target_table=target_table,
        payload=payload,
        extracted_data=extracted_data,
        confidence=confidence,
        source_system=body.get("source_system") or "manual_upload",
        source_record_id=body.get("source_record_id"),
    )
    return {"ok": True, "queue_no": queue_no, "item": item}


@router.post("/ingest")
def create_ingest_placeholder(
    request: Request,
    body: dict = Body(...),
) -> dict:
    ctx = _require_context(request)
    _require_writer(ctx)
    source_document_name = (body.get("source_document_name") or "").strip()
    if not source_document_name:
        raise HTTPException(400, {"error": "missing_source_document_name"})
    extraction_type = (body.get("extraction_type") or "manual_note").strip()
    if extraction_type not in _VALID_EXTRACTION_TYPES:
        raise HTTPException(400, {"error": "invalid_extraction_type"})
    target_table = _optional_allowlist(
        body.get("target_table"),
        _VALID_TARGET_TABLES,
        "invalid_target_table",
    )
    payload = _json_object(body.get("payload"), "payload")
    storage_url = (
        body.get("storage_url")
        or f"pending://jintai/{uuid.uuid4().hex}/{source_document_name}"
    )
    tenant_id = _tenant_id()
    attachment = db.main().execute(
        "INSERT INTO jintai_mvp.attachments "
        "(tenant_id, file_name, mime_type, storage_url, uploaded_by_profile_id, "
        " status, source_system, source_record_id) "
        "VALUES (%s,%s,%s,%s,%s,'uploaded','api:jintai_ingest',%s) "
        "RETURNING id, file_name, storage_url, status",
        (
            tenant_id,
            source_document_name,
            body.get("mime_type"),
            storage_url,
            _profile_id_for_user(ctx),
            body.get("source_record_id"),
        ),
    ).fetchone()
    queue_no = f"AIQ-JT-INGEST-{uuid.uuid4().hex[:8].upper()}"
    item = _insert_queue_item(
        tenant_id=tenant_id,
        queue_no=queue_no,
        attachment_id=attachment["id"],
        source_document_name=source_document_name,
        extraction_type=extraction_type,
        target_table=target_table,
        payload={
            **payload,
            "ingest_mode": "metadata_only_placeholder",
            "note": "No OCR or ERP connection is executed by this endpoint.",
        },
        extracted_data=_json_object(body.get("extracted_data"), "extracted_data"),
        confidence=_confidence(body.get("confidence")),
        source_system="api:jintai_ingest",
        source_record_id=body.get("source_record_id"),
    )
    return {
        "ok": True,
        "attachment": dict(attachment),
        "queue_no": queue_no,
        "item": item,
    }


@router.post("/extractions/{queue_no}/confirm")
def confirm_extraction(
    request: Request,
    queue_no: str = Path(..., max_length=80),
    body: dict | None = Body(None),
) -> dict:
    payload = {**(body or {}), "action": "confirm"}
    return review_ai_extraction_queue_item(request, queue_no=queue_no, body=payload)


@router.post("/extractions/{queue_no}/reject")
def reject_extraction(
    request: Request,
    queue_no: str = Path(..., max_length=80),
    body: dict | None = Body(None),
) -> dict:
    payload = {**(body or {}), "action": "reject"}
    return review_ai_extraction_queue_item(request, queue_no=queue_no, body=payload)


@router.post("/ai-extraction-queue/{queue_no}/review")
def review_ai_extraction_queue_item(
    request: Request,
    queue_no: str = Path(..., max_length=80),
    body: dict = Body(...),
) -> dict:
    ctx = _require_context(request)
    _require_writer(ctx)
    action = (body.get("action") or "").strip()
    if action not in _VALID_QUEUE_ACTIONS:
        raise HTTPException(400, {"error": "invalid_action"})
    current = _queue_row(queue_no)
    if current["status"] != "pending_review":
        raise HTTPException(409, {"error": "queue_item_not_reviewable"})
    new_status = "confirmed" if action == "confirm" else "rejected"
    reviewer_profile_id = _profile_id_for_review(ctx, body.get("reviewer_role_code"))
    db.main().execute(
        "UPDATE jintai_mvp.ai_extraction_queue "
        "SET status=%s, reviewed_by_profile_id=%s, reviewed_at=now(), "
        "    payload=payload || %s::jsonb "
        "WHERE tenant_id=%s AND queue_no=%s",
        (
            new_status,
            reviewer_profile_id,
            json.dumps(
                {"review_note": body.get("note"), "reviewed_by_user_id": ctx.user_id},
                ensure_ascii=False,
            ),
            _tenant_id(),
            queue_no,
        ),
    )
    return {"ok": True, "item": _queue_row(queue_no)}
