"""M3 pipeline tests (docs/data-layer.md §8 M3 + §9 AC-D1/D2/D3/D6/D7).

Covers the upload → mapping → transform path end-to-end without LLM:
- AC-D1: Excel upload lands bronze parquet + _meta.json + bronze_files row
- AC-D2: same checksum twice → deduped, no second parquet written
- AC-D3: after mapping built, silver row count == bronze row count
- AC-D6: Bronze Files panel listing works (already in test_data_api.py)
- AC-D7: deleting a bronze file cascades silver rows via source_lineage
- Idempotency: re-running transform leaves silver state unchanged
- Drift: missing required silver columns are auto-defaulted, not crashed
"""
from __future__ import annotations
import io
import time
from pathlib import Path
import duckdb
import pandas as pd
import pytest
from fastapi.testclient import TestClient
from platform_app import auth, db
from platform_app.data_layer import ingest, paths, repo, silver_db, transform
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
    db.init()
    now = int(time.time())
    db.main().execute(
        "INSERT INTO users (id, username, password_hash, display_name, created_at) "
        "VALUES (%s,%s,%s,%s,%s)",
        ("u_eason", "eason", auth.hash_password("p"), "Eason", now),
    )
    db.main().execute(
        "INSERT INTO enterprises (id, legal_name, display_name, plan, "
        "onboarding_stage, created_at) "
        "VALUES (%s,%s,%s,'trial','active',%s)",
        ("yinhu", "Yinhu", "Yinhu", now),
    )
    db.main().execute(
        "INSERT INTO tenants (client_id, agent_id, display_name, container_url, "
        "hmac_secret_current, hmac_key_id_current, tenant_uid, created_at) "
        "VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
        ("yinhu", "x", "Yinhu", "http://x", "s", "k", "u_x", now),
    )
    db.main().execute(
        "INSERT INTO enterprise_members (user_id, enterprise_id, role, granted_at) "
        "VALUES (%s,%s,%s,%s)",
        ("u_eason", "yinhu", "member", now),
    )
    sid, _ = auth.create_session("u_eason", "127.0.0.1", "test")
    return sid


def _make_xlsx(rows: list[dict], sheet: str = "Sheet1") -> bytes:
    buf = io.BytesIO()
    pd.DataFrame(rows).to_excel(buf, sheet_name=sheet, index=False)
    return buf.getvalue()


# ─── AC-D1: bronze parquet + meta + bronze_files row ────────────

def test_upload_lands_bronze_parquet_meta_and_db_row(tmp_data_root):
    db.init()
    blob = _make_xlsx([
        {"客户名": "甲公司", "订单号": "S-001", "金额": 1000},
        {"客户名": "乙公司", "订单号": "S-002", "金额": 2500},
    ])
    result = ingest.ingest_excel(
        client_id="yinhu", original_filename="sales.xlsx",
        file_bytes=blob, uploaded_by="u_eason",
    )
    assert not result.duplicate
    assert len(result.sheets) == 1
    sheet = result.sheets[0]

    parquet = tmp_data_root / sheet.bronze_path
    assert parquet.is_file()
    assert parquet.with_suffix(".json").is_file()
    assert pd.read_parquet(parquet).shape[0] == 2

    rows = repo.list_bronze_files("yinhu", "file_excel")
    assert len(rows) == 1
    assert rows[0]["original_filename"] == "sales.xlsx"
    assert rows[0]["row_count"] == 2


# ─── AC-D2: checksum dedup ──────────────────────────────────────

def test_upload_same_file_twice_dedupes(tmp_data_root):
    db.init()
    blob = _make_xlsx([{"a": 1}])
    first = ingest.ingest_excel(
        client_id="yinhu", original_filename="x.xlsx",
        file_bytes=blob, uploaded_by="u",
    )
    second = ingest.ingest_excel(
        client_id="yinhu", original_filename="x.xlsx",
        file_bytes=blob, uploaded_by="u",
    )
    assert first.duplicate is False
    assert second.duplicate is True
    assert second.existing_file_ids == [first.sheets[0].bronze_file_id]
    assert len(repo.list_bronze_files("yinhu")) == 1


# ─── AC-D3: silver row count matches bronze ─────────────────────

def test_mapping_then_transform_lands_silver_rows(tmp_data_root):
    db.init()
    rows = [
        {"客户名": "甲公司", "订单号": "S-001", "金额": "1000"},
        {"客户名": "乙公司", "订单号": "S-002", "金额": "2500"},
        {"客户名": "丙公司", "订单号": "S-003", "金额": "999"},
    ]
    result = ingest.ingest_excel(
        client_id="yinhu", original_filename="sales.xlsx",
        file_bytes=_make_xlsx(rows), uploaded_by="u",
    )
    bronze_id = result.sheets[0].bronze_file_id

    tr = transform.materialize(
        client_id="yinhu",
        bronze_file_id=bronze_id,
        silver_table="orders",
        column_map={
            "客户名": "customer_name_snapshot",
            "订单号": "order_number",
            "金额": "total_amount_cny",
        },
    )
    assert tr.rows_written == 3
    assert tr.rows_skipped == 0

    con = duckdb.connect(str(paths.silver_live_path("yinhu")), read_only=True)
    try:
        n = con.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
        assert n == 3
        # Defaults filled for unmapped required columns
        statuses = {r[0] for r in con.execute("SELECT payment_status FROM orders").fetchall()}
        assert statuses == {"unknown"}
    finally:
        con.close()


# ─── Idempotent re-run (§5.2) ───────────────────────────────────

def test_transform_is_idempotent(tmp_data_root):
    db.init()
    result = ingest.ingest_excel(
        client_id="yinhu", original_filename="x.xlsx",
        file_bytes=_make_xlsx([{"k": "a"}, {"k": "b"}]), uploaded_by="u",
    )
    bid = result.sheets[0].bronze_file_id
    args = dict(
        client_id="yinhu", bronze_file_id=bid, silver_table="customers",
        column_map={"k": "display_name"},
    )
    transform.materialize(**args)
    transform.materialize(**args)
    transform.materialize(**args)

    con = duckdb.connect(str(paths.silver_live_path("yinhu")), read_only=True)
    try:
        n = con.execute("SELECT COUNT(*) FROM customers").fetchone()[0]
        assert n == 2
    finally:
        con.close()


# ─── AC-D7: cascade delete ──────────────────────────────────────

def test_delete_bronze_cascades_silver_via_source_lineage(tmp_data_root):
    db.init()
    result = ingest.ingest_excel(
        client_id="yinhu", original_filename="x.xlsx",
        file_bytes=_make_xlsx([{"k": "a"}, {"k": "b"}, {"k": "c"}]), uploaded_by="u",
    )
    bid = result.sheets[0].bronze_file_id
    transform.materialize(
        client_id="yinhu", bronze_file_id=bid, silver_table="customers",
        column_map={"k": "display_name"},
    )

    deleted = transform.cascade_delete_silver("yinhu", bid)
    assert deleted == 3

    con = duckdb.connect(str(paths.silver_live_path("yinhu")), read_only=True)
    try:
        n = con.execute("SELECT COUNT(*) FROM customers").fetchone()[0]
        assert n == 0
    finally:
        con.close()


# ─── HTTP path: full flow via /api/data/* ───────────────────────

def test_http_upload_then_mapping_returns_silver_count(client, user_with_acl):
    sid = user_with_acl
    blob = _make_xlsx([
        {"name": "a"},
        {"name": "b"},
        {"name": "c"},
    ])
    r = client.post(
        "/api/data/upload",
        data={"client": "yinhu"},
        files={"file": ("test.xlsx", blob,
                        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        cookies={"app_session": sid},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert not body["duplicate"]
    sheet = body["sheets"][0]
    assert sheet["row_count"] == 3
    bronze_id = sheet["bronze_file_id"]

    r2 = client.post(
        "/api/data/mapping",
        json={
            "client": "yinhu",
            "bronze_file_id": bronze_id,
            "silver_table": "customers",
            "column_map": {"name": "display_name"},
        },
        cookies={"app_session": sid},
    )
    assert r2.status_code == 200, r2.text
    assert r2.json()["rows_written"] == 3


def test_http_upload_dedupe_returns_existing_ids(client, user_with_acl):
    sid = user_with_acl
    blob = _make_xlsx([{"a": 1}])
    r1 = client.post(
        "/api/data/upload",
        data={"client": "yinhu"},
        files={"file": ("a.xlsx", blob, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        cookies={"app_session": sid},
    )
    r2 = client.post(
        "/api/data/upload",
        data={"client": "yinhu"},
        files={"file": ("a.xlsx", blob, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        cookies={"app_session": sid},
    )
    assert r1.json()["duplicate"] is False
    body2 = r2.json()
    assert body2["duplicate"] is True
    assert body2["existing_file_ids"] == [r1.json()["sheets"][0]["bronze_file_id"]]


def test_http_upload_rejects_unsupported_format(client, user_with_acl):
    sid = user_with_acl
    r = client.post(
        "/api/data/upload",
        data={"client": "yinhu"},
        files={"file": ("a.txt", b"hello", "text/plain")},
        cookies={"app_session": sid},
    )
    assert r.status_code == 400


def test_http_bronze_delete_cascades(client, user_with_acl):
    sid = user_with_acl
    r = client.post(
        "/api/data/upload",
        data={"client": "yinhu"},
        files={"file": ("a.xlsx", _make_xlsx([{"k": "a"}, {"k": "b"}]),
                        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        cookies={"app_session": sid},
    )
    bid = r.json()["sheets"][0]["bronze_file_id"]
    client.post(
        "/api/data/mapping",
        json={"client": "yinhu", "bronze_file_id": bid,
              "silver_table": "customers", "column_map": {"k": "display_name"}},
        cookies={"app_session": sid},
    )

    rd = client.delete(f"/api/data/bronze/{bid}?client=yinhu",
                       cookies={"app_session": sid})
    assert rd.status_code == 200
    assert rd.json()["silver_rows_deleted"] == 2
    # bronze listing now excludes it
    rl = client.get("/api/data/bronze?client=yinhu",
                    cookies={"app_session": sid})
    assert rl.json()["files"] == []
