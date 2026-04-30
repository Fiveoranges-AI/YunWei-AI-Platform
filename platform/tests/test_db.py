from platform_app import db

def test_init_creates_tables():
    db.init()
    rows = db.main().execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    names = {r["name"] for r in rows}
    assert {"users", "tenants", "user_tenant", "platform_sessions", "api_keys"} <= names

def test_proxy_log_in_separate_file():
    db.init()
    rows = db.proxy_log_db().execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    assert "proxy_log" in {r["name"] for r in rows}
    # 主 DB 里**没有** proxy_log 表
    assert "proxy_log" not in {r["name"] for r in db.main().execute("SELECT name FROM sqlite_master").fetchall()}
