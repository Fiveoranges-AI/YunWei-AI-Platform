from __future__ import annotations

import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from platform_app import auth, db
from platform_app.main import app


@pytest.fixture
def client():
    return TestClient(app)


def _seed_jintai() -> None:
    seed_sql = (
        Path(__file__).resolve().parent.parent
        / "seeds"
        / "001_jintai_mvp_seed.sql"
    ).read_text()
    with db.main()._get().cursor() as cur:
        cur.execute(seed_sql)


def _logged_in_member(role: str = "owner", enterprise_id: str = "jintai-demo") -> str:
    now = int(time.time())
    db.main().execute(
        "INSERT INTO users (id, username, password_hash, display_name, created_at) "
        "VALUES (%s,%s,%s,%s,%s)",
        (f"u_jintai_{role}", f"jintai_{role}", auth.hash_password("p"), "Jintai User", now),
    )
    db.main().execute(
        "INSERT INTO enterprises (id, legal_name, display_name, plan, onboarding_stage, created_at) "
        "VALUES (%s,'锦泰耐火材料','锦泰耐火材料','trial','active',%s)",
        (enterprise_id, now),
    )
    db.main().execute(
        "INSERT INTO enterprise_members (user_id, enterprise_id, role, granted_at) "
        "VALUES (%s,%s,%s,%s)",
        (f"u_jintai_{role}", enterprise_id, role, now),
    )
    sid, _ = auth.create_session(f"u_jintai_{role}", "127.0.0.1", "test")
    return sid


@pytest.fixture
def session_cookie() -> str:
    db.init()
    sid = _logged_in_member()
    _seed_jintai()
    return sid


def test_jintai_api_requires_auth(client):
    db.init()
    r = client.get("/api/jintai/overview")
    assert r.status_code == 401


def test_jintai_api_rejects_other_enterprise(client):
    db.init()
    sid = _logged_in_member("owner", enterprise_id="other-demo")
    _seed_jintai()
    r = client.get("/api/jintai/overview", cookies={"app_session": sid})
    assert r.status_code == 403
    assert r.json()["detail"]["error"] == "jintai_access_denied"


def test_overview_exposes_seeded_production_kpis(client, session_cookie):
    r = client.get("/api/jintai/overview", cookies={"app_session": session_cookie})
    assert r.status_code == 200
    body = r.json()
    assert body["tenant"]["display_name"] == "锦泰耐火材料"
    assert body["kpis"]["total_flow_cards"] == 15
    assert body["kpis"]["delayed_flow_cards"] == 3
    assert body["kpis"]["sintering_flow_cards"] == 4
    assert body["kpis"]["quantity_exception_flow_cards"] == 2
    assert body["kpis"]["completed_flow_cards"] == 2
    assert body["kpis"]["created_flow_cards"] == 2
    assert body["products"]["high_risk_products"] == 2
    assert body["queue"]["pending_review"] == 2


def test_flow_card_filters_and_detail(client, session_cookie):
    delayed = client.get(
        "/api/jintai/flow-cards?status=delayed",
        cookies={"app_session": session_cookie},
    )
    assert delayed.status_code == 200
    assert len(delayed.json()["flow_cards"]) == 3

    sintering = client.get(
        "/api/jintai/flow-cards?current_step_code=sintering",
        cookies={"app_session": session_cookie},
    )
    assert sintering.status_code == 200
    assert len(sintering.json()["flow_cards"]) == 4

    detail = client.get(
        "/api/jintai/flow-cards/FC-JT-202605-005",
        cookies={"app_session": session_cookie},
    )
    assert detail.status_code == 200
    body = detail.json()
    assert body["flow_card"]["status"] == "quantity_exception"
    assert body["flow_card"]["product_sku"] == "JT-AM-SP-001"
    assert [s["step_code"] for s in body["step_records"]] == [
        "forming",
        "sintering",
        "inspection_packaging",
    ]


def test_daily_briefing_returns_risks_and_pending_queue(client, session_cookie):
    r = client.get(
        "/api/jintai/briefing?briefing_date=2026-05-17",
        cookies={"app_session": session_cookie},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["briefing_date"] == "2026-05-17"
    assert body["counters"]["delayed_flow_cards"] == 3
    assert body["counters"]["sintering_flow_cards"] == 4
    assert body["counters"]["quantity_exception_flow_cards"] == 2
    assert len(body["risk_flow_cards"]) >= 6
    assert len(body["high_defect_products"]) >= 2
    assert len(body["pending_ai_queue"]) == 2
    assert body["recommendations"]


def test_orders_and_process_routes_are_readable(client, session_cookie):
    orders = client.get(
        "/api/jintai/orders?status=delayed",
        cookies={"app_session": session_cookie},
    )
    assert orders.status_code == 200
    assert len(orders.json()["orders"]) == 3
    assert orders.json()["orders"][0]["flow_card_no"].startswith("FC-JT-")

    routes = client.get(
        "/api/jintai/process-routes?product_sku=JT-AM-SP-001",
        cookies={"app_session": session_cookie},
    )
    assert routes.status_code == 200
    assert len(routes.json()["routes"]) == 1
    assert [s["step_code"] for s in routes.json()["routes"][0]["steps"]] == [
        "forming",
        "sintering",
        "inspection_packaging",
    ]

    parameters = client.get(
        "/api/jintai/process-parameters?product_sku=JT-AM-SP-001",
        cookies={"app_session": session_cookie},
    )
    assert parameters.status_code == 200
    assert [p["step_code"] for p in parameters.json()["process_parameters"]] == [
        "forming",
        "sintering",
        "inspection_packaging",
    ]


def test_customers_and_source_mappings_are_readable(client, session_cookie):
    customers = client.get(
        "/api/jintai/customers",
        cookies={"app_session": session_cookie},
    )
    assert customers.status_code == 200
    assert len(customers.json()["customers"]) == 5
    assert customers.json()["customers"][0]["order_count"] > 0

    mappings = client.get(
        "/api/jintai/source-mappings?local_table=products",
        cookies={"app_session": session_cookie},
    )
    assert mappings.status_code == 200
    assert len(mappings.json()["mappings"]) == 2
    assert mappings.json()["mappings"][0]["source_system"] == "yonyou_placeholder"


def test_ask_returns_traceable_answer_and_logs_query(client, session_cookie):
    r = client.post(
        "/api/jintai/ask",
        json={"query_text": "今天哪些生产单延期？"},
        cookies={"app_session": session_cookie},
    )
    assert r.status_code == 200
    body = r.json()
    assert "3 张延期" in body["answer"]
    assert len(body["data"]) == 3
    assert len(body["citations"]) == 3

    log = db.main().execute(
        "SELECT query_text, answer_text, model_name FROM jintai_mvp.ai_query_logs "
        "WHERE id=%s",
        (body["query_log_id"],),
    ).fetchone()
    assert log["query_text"] == "今天哪些生产单延期？"
    assert log["model_name"] == "jintai-rule-based-v0"


def test_flow_card_rejects_unknown_filters(client, session_cookie):
    r = client.get(
        "/api/jintai/flow-cards?status=unknown",
        cookies={"app_session": session_cookie},
    )
    assert r.status_code == 400
    assert r.json()["detail"]["error"] == "invalid_status"


def test_review_queue_confirms_without_direct_business_write(client, session_cookie):
    pending = client.get(
        "/api/jintai/extractions?status=pending",
        cookies={"app_session": session_cookie},
    )
    assert pending.status_code == 200
    assert len(pending.json()["items"]) == 2

    reviewed = client.post(
        "/api/jintai/extractions/AIQ-JT-202605-001/confirm",
        json={
            "reviewer_role_code": "production_manager",
            "note": "人工确认 OCR 结果属实",
        },
        cookies={"app_session": session_cookie},
    )
    assert reviewed.status_code == 200
    assert reviewed.json()["item"]["status"] == "confirmed"
    assert reviewed.json()["item"]["reviewed_by_profile_id"] is not None

    detail = client.get(
        "/api/jintai/flow-cards/FC-JT-202605-005",
        cookies={"app_session": session_cookie},
    )
    assert detail.status_code == 200
    assert detail.json()["flow_card"]["status"] == "quantity_exception"


def test_review_queue_is_single_step(client, session_cookie):
    first = client.post(
        "/api/jintai/ai-extraction-queue/AIQ-JT-202605-001/review",
        json={"action": "reject", "reviewer_role_code": "production_manager"},
        cookies={"app_session": session_cookie},
    )
    assert first.status_code == 200

    second = client.post(
        "/api/jintai/ai-extraction-queue/AIQ-JT-202605-001/review",
        json={"action": "confirm", "reviewer_role_code": "production_manager"},
        cookies={"app_session": session_cookie},
    )
    assert second.status_code == 409
    assert second.json()["detail"]["error"] == "queue_item_not_reviewable"


def test_create_queue_item_stays_pending_review(client, session_cookie):
    r = client.post(
        "/api/jintai/ai-extraction-queue",
        json={
            "source_document_name": "manual-flow-card.jpg",
            "extraction_type": "ocr_flow_card",
            "target_table": "production_flow_cards",
            "payload": {"source": "manual_test"},
            "extracted_data": {"flow_card_no": "FC-JT-MANUAL-001"},
            "confidence": 0.88,
        },
        cookies={"app_session": session_cookie},
    )
    assert r.status_code == 200
    assert r.json()["queue_no"].startswith("AIQ-JT-MANUAL-")
    assert r.json()["item"]["status"] == "pending_review"


def test_ingest_placeholder_creates_attachment_and_queue_item(client, session_cookie):
    r = client.post(
        "/api/jintai/ingest",
        json={
            "source_document_name": "flow-card-placeholder.jpg",
            "mime_type": "image/jpeg",
            "extraction_type": "ocr_flow_card",
            "target_table": "production_flow_cards",
            "payload": {"source": "unit_test"},
            "extracted_data": {"flow_card_no": "FC-JT-PLACEHOLDER"},
            "confidence": 0.75,
        },
        cookies={"app_session": session_cookie},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["attachment"]["file_name"] == "flow-card-placeholder.jpg"
    assert body["attachment"]["storage_url"].startswith("pending://jintai/")
    assert body["queue_no"].startswith("AIQ-JT-INGEST-")
    assert body["item"]["status"] == "pending_review"
    assert body["item"]["attachment_id"] == body["attachment"]["id"]


def test_create_queue_item_rejects_invalid_target_table(client, session_cookie):
    r = client.post(
        "/api/jintai/ai-extraction-queue",
        json={
            "extraction_type": "ocr_flow_card",
            "target_table": "production_flow_cards;drop table",
            "payload": {},
            "extracted_data": {},
        },
        cookies={"app_session": session_cookie},
    )
    assert r.status_code == 400
    assert r.json()["detail"]["error"] == "invalid_target_table"


def test_member_can_read_but_not_write_queue(client):
    db.init()
    sid = _logged_in_member("member")
    _seed_jintai()
    read = client.get("/api/jintai/overview", cookies={"app_session": sid})
    assert read.status_code == 200

    write = client.post(
        "/api/jintai/ai-extraction-queue",
        json={
            "extraction_type": "ocr_flow_card",
            "target_table": "production_flow_cards",
            "payload": {},
            "extracted_data": {},
        },
        cookies={"app_session": sid},
    )
    assert write.status_code == 403
