import time
from platform_app import auth, db


def test_authenticate_unknown_user_returns_none():
    db.init()
    assert auth.authenticate("nobody", "anything") is None


def test_authenticate_wrong_password():
    db.init()
    db.main().execute(
        "INSERT INTO users (id, username, password_hash, display_name, created_at) VALUES (%s,%s,%s,%s,%s)",
        ("u_a", "alice", auth.hash_password("correct"), "Alice", int(time.time())),
    )
    assert auth.authenticate("alice", "wrong") is None
    assert auth.authenticate("alice", "correct") == "u_a"


def test_create_session_then_lookup():
    db.init()
    db.main().execute(
        "INSERT INTO users (id, username, password_hash, display_name, created_at) VALUES (%s,%s,%s,%s,%s)",
        ("u_a", "alice", auth.hash_password("p"), "Alice", int(time.time())),
    )
    sid, csrf = auth.create_session("u_a", "127.0.0.1", "test-ua")
    me = auth.current_user_from_request(sid)
    assert me is not None
    assert me["id"] == "u_a"
    assert me["csrf"] == csrf


def test_revoke_session_invalidates_lookup():
    db.init()
    db.main().execute(
        "INSERT INTO users (id, username, password_hash, display_name, created_at) VALUES (%s,%s,%s,%s,%s)",
        ("u_a", "alice", auth.hash_password("p"), "Alice", int(time.time())),
    )
    sid, _ = auth.create_session("u_a", None, None)
    assert auth.current_user_from_request(sid) is not None
    auth.revoke_session(sid)
    assert auth.current_user_from_request(sid) is None
