from platform_app import db


def test_init_creates_tables():
    db.init()
    rows = db.main().execute(
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_schema='public' AND table_type='BASE TABLE'"
    ).fetchall()
    names = {r["table_name"] for r in rows}
    assert {"users", "tenants", "platform_sessions",
            "api_keys", "proxy_log",
            "enterprises", "enterprise_members", "agent_grants"} <= names
    # 006 dropped the legacy ACL table.
    assert "user_tenant" not in names


def test_proxy_log_writable():
    db.init()
    db.write_proxy_log(
        user_id="u_x", client_id="c", agent_id="a",
        method="GET", path="/p", status=200, duration_ms=12, ip="1.2.3.4",
    )
    row = db.main().execute(
        "SELECT path, status FROM proxy_log WHERE user_id=%s ORDER BY id DESC LIMIT 1",
        ("u_x",),
    ).fetchone()
    assert row["path"] == "/p"
    assert row["status"] == 200
