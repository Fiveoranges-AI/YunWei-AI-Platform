"""M4 tests — manual entry (AC-D4) + PDF best-effort + ERP scaffold.

Covers docs/data-layer.md §4.3, §4.4 and §8 M4 deliverables:
- AC-D4: manual_ui entry double-writes to silver + bronze audit
- Manual upsert: re-entry of same PK replaces silver, appends bronze
- PDF parsing: success + best-effort failure semantics (§4.3)
- 007 erp_credentials migration applied
- assistant manual_entry / get_silver_table_schema tools
- HTTP /api/data/manual/<table> + /api/data/schema/<table>
"""
from __future__ import annotations
import io
import time
from datetime import date
from pathlib import Path
import duckdb
import pandas as pd
import pytest
from fastapi.testclient import TestClient
from platform_app import auth, db
from platform_app.data_layer import (
    assistant as assistant_mod, ingest, manual, paths,
)
from platform_app.main import app
from platform_app.settings import settings


# ─── fixtures ───────────────────────────────────────────────────

@pytest.fixture
def tmp_data_root(tmp_path, monkeypatch) -> Path:
    monkeypatch.setattr(settings, "data_root", str(tmp_path))
    return tmp_path


@pytest.fixture
def http_client():
    return TestClient(app)


@pytest.fixture
def user_session(tmp_data_root):
    db.init()
    now = int(time.time())
    db.main().execute(
        "INSERT INTO users (id, username, password_hash, display_name, created_at) "
        "VALUES (%s,%s,%s,%s,%s)",
        ("u_eason", "eason", auth.hash_password("p"), "Eason", now),
    )
    db.main().execute(
        "INSERT INTO enterprises (id, legal_name, display_name, plan, "
        "onboarding_stage, created_at) VALUES (%s,%s,%s,'trial','active',%s)",
        ("yinhu", "Yinhu", "Yinhu", now),
    )
    db.main().execute(
        "INSERT INTO tenants (client_id, agent_id, display_name, container_url, "
        "hmac_secret_current, hmac_key_id_current, tenant_uid, created_at) "
        "VALUES (%s,%s,%s,'http://x','s','k',%s,%s)",
        ("yinhu", "x", "Yinhu", "u_x", now),
    )
    db.main().execute(
        "INSERT INTO enterprise_members (user_id, enterprise_id, role, granted_at) "
        "VALUES ('u_eason','yinhu','member',%s)", (now,),
    )
    sid, _ = auth.create_session("u_eason", "127.0.0.1", "test")
    return sid


# ─── 007 migration ──────────────────────────────────────────────

def test_007_creates_erp_credentials_table():
    db.init()
    rows = db.main().execute(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_schema='public' AND table_name='erp_credentials'"
    ).fetchall()
    cols = {r["column_name"] for r in rows}
    assert {"enterprise_id", "vendor", "secret_json", "active",
            "created_at", "rotated_at"} <= cols


def test_erp_credentials_inserts_keyed_by_enterprise_vendor(tmp_data_root):
    db.init()
    now = int(time.time())
    db.main().execute(
        "INSERT INTO users (id, username, password_hash, display_name, created_at) "
        "VALUES ('u', 'a', 's', 'A', %s)", (now,),
    )
    db.main().execute(
        "INSERT INTO enterprises (id, legal_name, display_name, plan, "
        "onboarding_stage, created_at) VALUES "
        "('yinhu','Y','Y','trial','active',%s)", (now,),
    )
    db.main().execute(
        "INSERT INTO erp_credentials (enterprise_id, vendor, display_name, "
        "secret_json, created_at, created_by) "
        "VALUES (%s,%s,%s,%s,%s,%s)",
        ("yinhu", "kingdee", "金蝶", '{"api_key":"x"}', now, "u"),
    )
    row = db.main().execute(
        "SELECT vendor, secret_json FROM erp_credentials "
        "WHERE enterprise_id='yinhu'"
    ).fetchone()
    assert row["vendor"] == "kingdee"
    assert row["secret_json"] == '{"api_key":"x"}'


# ─── manual.schema_for_form ─────────────────────────────────────

def test_schema_for_form_marks_system_columns_and_pk(tmp_data_root):
    s = manual.schema_for_form("customers")
    assert s["table"] == "customers"
    assert s["primary_key"] == ["customer_id"]
    by_name = {f["name"]: f for f in s["fields"]}
    assert by_name["customer_id"]["is_primary_key"] is True
    assert by_name["source_type"]["system_managed"] is True
    assert by_name["created_at"]["system_managed"] is True
    assert by_name["display_name"]["system_managed"] is False


def test_schema_for_form_unknown_table_raises(tmp_data_root):
    with pytest.raises(ValueError):
        manual.schema_for_form("no_such_table")


# ─── AC-D4: manual entry double-writes ──────────────────────────

def test_manual_entry_double_writes_silver_and_bronze(tmp_data_root):
    db.init()
    result = manual.record_manual_entry(
        client_id="yinhu",
        silver_table="customers",
        fields={"display_name": "甲公司", "contact_phone": "13800000000"},
        user_id="u_eason",
    )
    # bronze parquet present
    bronze_path = tmp_data_root / "tenants/yinhu/bronze/manual_ui"
    assert bronze_path.is_dir()
    parquets = list(bronze_path.rglob("*.parquet"))
    assert len(parquets) == 1
    df = pd.read_parquet(parquets[0])
    assert df.iloc[0]["display_name"] == "甲公司"

    # bronze_files row present
    from platform_app.data_layer import repo
    rows = repo.list_bronze_files("yinhu", "manual_ui")
    assert len(rows) == 1
    assert rows[0]["sheet_name"] == "customers"
    assert rows[0]["row_count"] == 1

    # silver row present
    con = duckdb.connect(str(paths.silver_live_path("yinhu")), read_only=True)
    try:
        n = con.execute("SELECT COUNT(*) FROM customers").fetchone()[0]
        assert n == 1
        row = con.execute(
            "SELECT display_name, source_type FROM customers"
        ).fetchone()
        assert row[0] == "甲公司"
        assert row[1] == "manual_ui"
    finally:
        con.close()


def test_manual_entry_reentry_upserts_silver_and_appends_bronze(tmp_data_root):
    db.init()
    first = manual.record_manual_entry(
        client_id="yinhu", silver_table="customers",
        fields={"customer_id": "c_001", "display_name": "甲"},
        user_id="u",
    )
    # Re-entry with same PK, different display_name
    manual.record_manual_entry(
        client_id="yinhu", silver_table="customers",
        fields={"customer_id": "c_001", "display_name": "甲公司(更名)"},
        user_id="u",
    )
    con = duckdb.connect(str(paths.silver_live_path("yinhu")), read_only=True)
    try:
        rows = con.execute(
            "SELECT customer_id, display_name FROM customers"
        ).fetchall()
        assert len(rows) == 1
        assert rows[0][0] == "c_001"
        assert rows[0][1] == "甲公司(更名)"
    finally:
        con.close()
    # Bronze: 2 audit copies preserved
    from platform_app.data_layer import repo
    assert len(repo.list_bronze_files("yinhu", "manual_ui")) == 2


def test_manual_entry_unknown_table_raises(tmp_data_root):
    with pytest.raises(ValueError):
        manual.record_manual_entry(
            client_id="yinhu", silver_table="no_such",
            fields={"x": 1}, user_id="u",
        )


def test_manual_entry_health_panel_increments(tmp_data_root, http_client,
                                               user_session):
    """AC-D4: after manual entry, health panel reports the new row."""
    h0 = http_client.get(
        "/api/data/health?client=yinhu", cookies={"app_session": user_session}
    ).json()
    assert h0["initialized"] is False

    manual.record_manual_entry(
        client_id="yinhu", silver_table="customers",
        fields={"display_name": "甲"}, user_id="u_eason",
    )
    h1 = http_client.get(
        "/api/data/health?client=yinhu", cookies={"app_session": user_session}
    ).json()
    assert h1["initialized"] is True
    assert h1["tables"]["customers"]["row_count"] == 1
    assert h1["tables"]["customers"]["by_source"] == {"manual_ui": 1}


# ─── PDF best-effort ────────────────────────────────────────────

def _make_pdf_with_table() -> bytes:
    """Build a minimal PDF containing a 2-row table that pdfplumber
    can extract — uses reportlab if available, else a hand-rolled
    PDF. Skip the test if neither path works."""
    try:
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import letter
    except ImportError:
        pytest.skip("reportlab not installed — skipping PDF table test")
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    # Draw a grid that pdfplumber recognizes as a table
    x0, y0, w, h = 100, 700, 100, 20
    headers = ["客户名", "金额"]
    rows = [["甲公司", "1000"], ["乙公司", "2500"]]
    all_rows = [headers] + rows
    for i, row in enumerate(all_rows):
        for j, cell in enumerate(row):
            c.rect(x0 + j * w, y0 - i * h, w, h, stroke=1, fill=0)
            c.drawString(x0 + j * w + 5, y0 - i * h + 5, cell)
    c.save()
    return buf.getvalue()


def test_ingest_pdf_success_path(tmp_data_root):
    db.init()
    pdf_bytes = _make_pdf_with_table()
    result = ingest.ingest_pdf(
        client_id="yinhu", original_filename="invoice.pdf",
        file_bytes=pdf_bytes, uploaded_by="u",
    )
    assert not result.duplicate
    assert len(result.sheets) >= 1
    sheet = result.sheets[0]
    assert sheet.row_count >= 2
    parquet = tmp_data_root / sheet.bronze_path
    assert parquet.is_file()


def test_ingest_pdf_no_tables_raises(tmp_data_root):
    """A blank/text-only PDF should hit the best-effort failure path."""
    try:
        from reportlab.pdfgen import canvas
    except ImportError:
        pytest.skip("reportlab not installed")
    db.init()
    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    c.drawString(100, 700, "Just some prose, no table here.")
    c.save()
    with pytest.raises(ingest.PDFParseError):
        ingest.ingest_pdf(
            client_id="yinhu", original_filename="prose.pdf",
            file_bytes=buf.getvalue(), uploaded_by="u",
        )


# ─── HTTP /api/data/schema/<table> + /api/data/manual/<table> ───

def test_schema_endpoint_returns_field_list(http_client, user_session):
    r = http_client.get("/api/data/schema/customers",
                        cookies={"app_session": user_session})
    assert r.status_code == 200
    body = r.json()
    assert body["primary_key"] == ["customer_id"]
    assert any(f["name"] == "display_name" for f in body["fields"])


def test_schema_endpoint_unknown_table_404(http_client, user_session):
    r = http_client.get("/api/data/schema/no_such",
                        cookies={"app_session": user_session})
    assert r.status_code == 404


def test_manual_endpoint_creates_row(http_client, user_session):
    r = http_client.post(
        "/api/data/manual/customers",
        json={"client": "yinhu", "fields": {"display_name": "甲公司"}},
        cookies={"app_session": user_session},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["silver_table"] == "customers"
    assert body["primary_key"] == "customer_id"


def test_manual_endpoint_requires_acl(http_client, user_session):
    r = http_client.post(
        "/api/data/manual/customers",
        json={"client": "somebody_else", "fields": {"display_name": "x"}},
        cookies={"app_session": user_session},
    )
    assert r.status_code == 403


def test_upload_endpoint_supports_pdf_or_returns_422(http_client, user_session):
    """A blank PDF should return 422 (best-effort failure surface) rather
    than 400 (unsupported format) — proves PDF is now an accepted type."""
    try:
        from reportlab.pdfgen import canvas
    except ImportError:
        pytest.skip("reportlab not installed")
    buf = io.BytesIO()
    canvas.Canvas(buf).save()
    r = http_client.post(
        "/api/data/upload",
        data={"client": "yinhu"},
        files={"file": ("x.pdf", buf.getvalue(), "application/pdf")},
        cookies={"app_session": user_session},
    )
    # PDF was accepted (not 400 unsupported); blank PDF then fails parse
    assert r.status_code == 422
    assert r.json()["detail"]["error"] == "pdf_parse_failed"


# ─── assistant tool dispatch ────────────────────────────────────

def test_dispatch_get_silver_table_schema(tmp_data_root):
    db.init()
    out = assistant_mod._dispatch_tool(
        "get_silver_table_schema", {"silver_table": "orders"},
        client_id="yinhu", user_id="u",
    )
    assert out["table"] == "orders"
    assert out["primary_key"] == ["order_id"]


def test_dispatch_manual_entry_writes_silver_via_assistant(tmp_data_root):
    db.init()
    out = assistant_mod._dispatch_tool(
        "manual_entry",
        {"silver_table": "customers", "fields": {"display_name": "丙公司"}},
        client_id="yinhu", user_id="u_eason",
    )
    assert "primary_key_value" in out
    assert out["silver_table"] == "customers"
    con = duckdb.connect(str(paths.silver_live_path("yinhu")), read_only=True)
    try:
        n = con.execute("SELECT COUNT(*) FROM customers").fetchone()[0]
        assert n == 1
    finally:
        con.close()
