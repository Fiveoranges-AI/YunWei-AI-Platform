"""M2 console read-only API tests (docs/data-layer.md §3.2).

Covers /api/data/clients, /health, /tables/<t>/rows, /bronze:
- 401 without session, 403 without ACL on the queried client
- empty/uninitialized tenant returns initialized=false (no silver yet)
- populated silver returns row counts + by_source distribution
- table browser pagination + ?q= search
- bronze listing + source_type filter
"""
from __future__ import annotations
import time
from datetime import datetime
from pathlib import Path
import duckdb
import pytest
from fastapi.testclient import TestClient
from platform_app import auth, db
from platform_app.data_layer import paths, repo, silver_schema
from platform_app.main import app
from platform_app.settings import settings


# ─── fixtures ───────────────────────────────────────────────────

@pytest.fixture
def tmp_data_root(tmp_path, monkeypatch) -> Path:
    monkeypatch.setattr(settings, "data_root", str(tmp_path))
    return tmp_path


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def user_with_acl(tmp_data_root):
    """Create a user, seed user_tenant ACL on (yinhu, super-xiaochen),
    return (user_id, session_id)."""
    db.init()
    user_id = "u_eason"
    db.main().execute(
        "INSERT INTO users (id, username, password_hash, display_name, created_at) "
        "VALUES (%s,%s,%s,%s,%s)",
        (user_id, "eason", auth.hash_password("p"), "Eason", int(time.time())),
    )
    db.main().execute(
        "INSERT INTO tenants (client_id, agent_id, display_name, container_url, "
        "hmac_secret_current, hmac_key_id_current, tenant_uid, created_at) "
        "VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
        ("yinhu", "super-xiaochen", "银湖", "http://x", "s", "k", "uid_yinhu_x", int(time.time())),
    )
    db.main().execute(
        "INSERT INTO user_tenant (user_id, client_id, agent_id, role, granted_at) "
        "VALUES (%s,%s,%s,%s,%s)",
        (user_id, "yinhu", "super-xiaochen", "user", int(time.time())),
    )
    sid, _csrf = auth.create_session(user_id, "127.0.0.1", "test")
    return user_id, sid


def _seed_silver(client_id: str, *, customers: int = 0, orders: int = 0) -> None:
    """Create silver-live.duckdb + insert N rows in customers/orders."""
    paths.ensure_tenant_dirs(client_id)
    db_path = paths.silver_live_path(client_id)
    schema = silver_schema.load()
    con = duckdb.connect(str(db_path))
    try:
        # Minimal subset of canonical schema for the tables we touch.
        con.execute("""
            CREATE TABLE IF NOT EXISTS customers (
                customer_id VARCHAR PRIMARY KEY,
                display_name VARCHAR NOT NULL,
                source_type VARCHAR NOT NULL,
                created_at TIMESTAMP NOT NULL,
                updated_at TIMESTAMP NOT NULL
            )
        """)
        con.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                order_id VARCHAR PRIMARY KEY,
                customer_id VARCHAR NOT NULL,
                customer_name_snapshot VARCHAR NOT NULL,
                order_date DATE NOT NULL,
                total_amount_cny DECIMAL(18,2) NOT NULL,
                paid_amount_cny DECIMAL(18,2) NOT NULL DEFAULT 0,
                outstanding_amount_cny DECIMAL(18,2) NOT NULL,
                payment_status VARCHAR NOT NULL,
                status VARCHAR NOT NULL,
                source_type VARCHAR NOT NULL,
                created_at TIMESTAMP NOT NULL,
                updated_at TIMESTAMP NOT NULL
            )
        """)
        now = datetime(2026, 5, 6, 12, 0, 0)
        for i in range(customers):
            src = "manual_ui" if i % 2 == 0 else "file_excel"
            con.execute(
                "INSERT INTO customers VALUES (?, ?, ?, ?, ?)",
                [f"c_{i}", f"客户{i}", src, now, now],
            )
        for i in range(orders):
            con.execute(
                "INSERT INTO orders VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                [f"o_{i}", "c_0", "客户0", now.date(), 100.00, 0, 100.00,
                 "unpaid", "draft", "file_excel", now, now],
            )
    finally:
        con.close()


# ─── auth gating ────────────────────────────────────────────────

def test_endpoints_require_session(client):
    db.init()
    for path in [
        "/api/data/clients",
        "/api/data/health?client=yinhu",
        "/api/data/tables/customers/rows?client=yinhu",
        "/api/data/bronze?client=yinhu",
    ]:
        r = client.get(path)
        assert r.status_code == 401, f"{path} should require auth, got {r.status_code}"


def test_endpoints_check_acl(client, user_with_acl):
    _, sid = user_with_acl
    r = client.get("/api/data/health?client=somebody_else", cookies={"app_session": sid})
    assert r.status_code == 403


# ─── /clients ───────────────────────────────────────────────────

def test_clients_returns_distinct_user_clients(client, user_with_acl):
    _, sid = user_with_acl
    r = client.get("/api/data/clients", cookies={"app_session": sid})
    assert r.status_code == 200
    assert r.json() == {"clients": ["yinhu"]}


# ─── /health ────────────────────────────────────────────────────

def test_health_uninitialized_for_new_tenant(client, user_with_acl):
    _, sid = user_with_acl
    r = client.get("/api/data/health?client=yinhu", cookies={"app_session": sid})
    assert r.status_code == 200
    body = r.json()
    assert body["initialized"] is False
    assert set(body["tables"]) == {"customers", "orders", "order_items",
                                   "order_source_records", "boss_query_logs"}
    for h in body["tables"].values():
        assert h["row_count"] == 0


def test_health_populated_returns_counts_and_source_dist(client, user_with_acl):
    _, sid = user_with_acl
    _seed_silver("yinhu", customers=4)
    r = client.get("/api/data/health?client=yinhu", cookies={"app_session": sid})
    body = r.json()
    assert body["initialized"] is True
    cust = body["tables"]["customers"]
    assert cust["row_count"] == 4
    # 4 customers split manual_ui / file_excel evenly (i%2)
    assert cust["by_source"] == {"manual_ui": 2, "file_excel": 2}
    assert cust["latest_updated_at"] is not None


# ─── /tables/<t>/rows ───────────────────────────────────────────

def test_table_rows_unknown_table_404(client, user_with_acl):
    _, sid = user_with_acl
    r = client.get("/api/data/tables/no_such/rows?client=yinhu",
                   cookies={"app_session": sid})
    assert r.status_code == 404


def test_table_rows_empty_when_silver_missing(client, user_with_acl):
    _, sid = user_with_acl
    r = client.get("/api/data/tables/customers/rows?client=yinhu",
                   cookies={"app_session": sid})
    assert r.status_code == 200
    body = r.json()
    assert body == {"columns": [], "rows": [], "total": 0}


def test_table_rows_pagination_and_search(client, user_with_acl):
    _, sid = user_with_acl
    _seed_silver("yinhu", customers=12)

    r = client.get("/api/data/tables/customers/rows?client=yinhu&limit=5&offset=0",
                   cookies={"app_session": sid})
    body = r.json()
    assert body["total"] == 12
    assert len(body["rows"]) == 5
    assert "customer_id" in body["columns"]

    # offset
    r2 = client.get("/api/data/tables/customers/rows?client=yinhu&limit=5&offset=10",
                    cookies={"app_session": sid})
    assert len(r2.json()["rows"]) == 2

    # ?q= ILIKE on string columns: "客户7" matches one row
    r3 = client.get("/api/data/tables/customers/rows?client=yinhu&q=%E5%AE%A2%E6%88%B77",
                    cookies={"app_session": sid})
    body3 = r3.json()
    assert body3["total"] == 1
    assert body3["rows"][0]["customer_id"] == "c_7"


# ─── /bronze ────────────────────────────────────────────────────

def test_bronze_lists_and_filters_by_source(client, user_with_acl):
    _, sid = user_with_acl
    repo.insert_bronze_file(
        client_id="yinhu", source_type="file_excel",
        bronze_path="bronze/file_excel/x.parquet",
        original_filename="sales.xlsx", sheet_name="Sheet1", row_count=10,
        checksum_sha256="aaa", uploaded_by="u_eason", meta={},
    )
    repo.insert_bronze_file(
        client_id="yinhu", source_type="manual_ui",
        bronze_path="bronze/manual_ui/y.parquet",
        original_filename=None, sheet_name=None, row_count=1,
        checksum_sha256=None, uploaded_by="u_eason", meta={},
    )

    r = client.get("/api/data/bronze?client=yinhu", cookies={"app_session": sid})
    assert r.status_code == 200
    files = r.json()["files"]
    assert {f["source_type"] for f in files} == {"file_excel", "manual_ui"}

    r2 = client.get("/api/data/bronze?client=yinhu&source_type=file_excel",
                    cookies={"app_session": sid})
    assert {f["source_type"] for f in r2.json()["files"]} == {"file_excel"}


def test_bronze_unknown_source_type_400(client, user_with_acl):
    _, sid = user_with_acl
    r = client.get("/api/data/bronze?client=yinhu&source_type=ftp_zone",
                   cookies={"app_session": sid})
    assert r.status_code == 400


# ─── /data page route ───────────────────────────────────────────

def test_data_page_redirects_to_login_when_unauth(client):
    r = client.get("/data", follow_redirects=False)
    # main.py serves login.html (200) when no session cookie — same pattern as "/"
    assert r.status_code == 200
    assert b"login" in r.content.lower() or b"\xe7\x99\xbb\xe5\xbd\x95" in r.content  # 登录


def test_data_page_serves_console_when_authed(client, user_with_acl):
    _, sid = user_with_acl
    r = client.get("/data", cookies={"app_session": sid})
    assert r.status_code == 200
    assert b"data-layer" in r.content or b"\xe6\x95\xb0\xe6\x8d\xae\xe4\xb8\xad\xe5\xbf\x83" in r.content  # 数据中心
