#!/usr/bin/env python3
"""One-shot migration: Mac mini sqlite → Railway Postgres.

Source files (Mac mini docker volume):
  ~/agent-platform/data/platform.db    → all main tables
  ~/agent-platform/data/proxy_log.db   → proxy_log table

Target: $DATABASE_URL (Railway Postgres external URL).

Idempotent: uses INSERT ... ON CONFLICT DO NOTHING so re-running won't
duplicate rows. Safe to interrupt and resume.

Usage:
    DATABASE_URL='postgresql://postgres:xxx@xxxxx.up.railway.app:xxxxx/railway' \\
        python3 ops/migrate-platform-to-postgres.py

Pre-requisites:
    - psycopg installed locally:  pip install 'psycopg[binary]>=3.2'
    - Railway Postgres schema applied (run platform-app once or
      psql -f platform/migrations/001_init.sql && 002_proxy_log.sql)
"""
from __future__ import annotations
import os
import sqlite3
import sys
from pathlib import Path
import psycopg

HOME = Path(os.environ.get("HOME", "/Users/eason"))
SQLITE_MAIN = HOME / "agent-platform" / "data" / "platform.db"
SQLITE_LOG = HOME / "agent-platform" / "data" / "proxy_log.db"

# Order matters because of FK references.
MAIN_TABLES = [
    ("users", ["id"]),
    ("tenants", ["client_id", "agent_id"]),
    ("user_tenant", ["user_id", "client_id", "agent_id"]),
    ("platform_sessions", ["id"]),
    ("api_keys", ["id"]),
]
LOG_TABLES = [
    ("proxy_log", []),  # serial PK; let postgres auto-assign new ids
]


def copy_table(sqlite_path: Path, table: str, pg, pk_cols: list[str]) -> int:
    if not sqlite_path.exists():
        print(f"  ⚠  {sqlite_path} missing, skip")
        return 0
    src = sqlite3.connect(str(sqlite_path))
    src.row_factory = sqlite3.Row
    rows = src.execute(f'SELECT * FROM "{table}"').fetchall()
    if not rows:
        print(f"  {table}: empty")
        return 0
    cols = list(rows[0].keys())
    if table == "proxy_log":
        # Drop sqlite's id column so Postgres BIGSERIAL re-assigns.
        cols = [c for c in cols if c != "id"]
    placeholders = ",".join(["%s"] * len(cols))
    col_list = ",".join(f'"{c}"' for c in cols)
    if pk_cols:
        sql = (
            f'INSERT INTO "{table}" ({col_list}) VALUES ({placeholders}) '
            f'ON CONFLICT ({",".join(pk_cols)}) DO NOTHING'
        )
    else:
        sql = f'INSERT INTO "{table}" ({col_list}) VALUES ({placeholders})'
    n = 0
    with pg.cursor() as cur:
        for r in rows:
            cur.execute(sql, tuple(r[c] for c in cols))
            n += 1
    print(f"  {table}: {n} rows")
    return n


def main() -> int:
    pg_url = os.environ.get("DATABASE_URL")
    if not pg_url:
        print("ERROR: DATABASE_URL env required (Railway external URL).", file=sys.stderr)
        return 2
    if "railway.internal" in pg_url:
        print("ERROR: that's the internal URL — only reachable from a Railway service.", file=sys.stderr)
        print("Use the EXTERNAL URL from dashboard → Postgres → Connect → Public Network.", file=sys.stderr)
        return 2

    pg = psycopg.connect(pg_url, autocommit=True)
    print(f"→ connected to {pg.info.host}:{pg.info.port}/{pg.info.dbname}")

    print(f"→ migrating {SQLITE_MAIN}")
    for table, pk in MAIN_TABLES:
        copy_table(SQLITE_MAIN, table, pg, pk)

    print(f"→ migrating {SQLITE_LOG}")
    for table, pk in LOG_TABLES:
        copy_table(SQLITE_LOG, table, pg, pk)

    print("\n✓ done. Verify row counts:")
    with pg.cursor() as cur:
        for table, _ in MAIN_TABLES + LOG_TABLES:
            cur.execute(f'SELECT COUNT(*) AS n FROM "{table}"')
            print(f"  {table}: {cur.fetchone()[0]}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
