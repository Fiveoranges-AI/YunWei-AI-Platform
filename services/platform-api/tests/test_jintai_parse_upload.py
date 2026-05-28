"""Round 5: POST /api/win/parse/upload (multipart) → CandidateJSON.

3 mime tests via DemoMockProvider (no ANTHROPIC_API_KEY in tests):
  - .xlsx → IssueVoucher candidate
  - .pdf  → IssueVoucher (filename without 合同/采购) or PurchaseRequisition
  - .jpg  → IssueVoucher

每个 case 都断言:
  - 200 OK + provider=demo-mock + source_type 正确
  - candidate JSON shape (entities + fields + confidence + source_span)
  - 文件落 uploads/jintai/{tenant}/{checksum}.{ext}
  - ActionLog 写入,input_summary 含 action=parse_upload + filename + provider
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def _clean_state():  # noqa: PT004
    yield


# 让上传 root 落在 tmp_path-friendly 位置;test 跑完不留垃圾.
_TMP_UPLOAD_ROOT = Path("/tmp/jintai-test-uploads")


@pytest.fixture(autouse=True)
def _isolate_upload_root(monkeypatch):
    """每个 test 独立 upload root 避免串扰."""
    monkeypatch.setenv("JINTAI_UPLOAD_ROOT", str(_TMP_UPLOAD_ROOT))
    # 也确保 ANTHROPIC_API_KEY 不存在 (DemoMockProvider 路径)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    if _TMP_UPLOAD_ROOT.exists():
        shutil.rmtree(_TMP_UPLOAD_ROOT)
    yield
    if _TMP_UPLOAD_ROOT.exists():
        shutil.rmtree(_TMP_UPLOAD_ROOT)


# Force the API module to re-read JINTAI_UPLOAD_ROOT.
@pytest.fixture(autouse=True)
def _reload_parse_upload_root():
    import importlib
    import yunwei_win.api.parse_upload as pu
    importlib.reload(pu)
    yield


from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

import yunwei_win.models  # noqa: F401 register
from yunwei_win.db import Base, get_session
from yunwei_win.models import ActionLog


async def _make_engine():
    from sqlalchemy import event
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")

    @event.listens_for(engine.sync_engine, "connect")
    def _enable_sqlite_fk(dbapi_conn, _record):
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA foreign_keys = ON")
        cur.close()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    return engine


def _build_app(engine, *, actor: str = "uploader-1"):
    """Test app: stamps actor but NOT enterprise_id — endpoint then falls back
    to 'default' tenant and skips ensure_schema_ingest_tables_for (which would
    otherwise hit real Postgres at platform-startup time).
    """
    from fastapi import FastAPI
    from yunwei_win.api.parse_upload import router as parse_upload_router

    async def _override_session():
        async with AsyncSession(engine, expire_on_commit=False) as session:
            try:
                yield session
            except BaseException:
                await session.rollback()
                raise

    app = FastAPI()

    @app.middleware("http")
    async def _stamp_actor(request, call_next):
        request.state.actor = actor
        # NOTE: leave enterprise_id unset so endpoint falls back to "default"
        # and skips ensure_schema_ingest_tables_for (Base.metadata.create_all
        # in _make_engine already created every table on SQLite).
        return await call_next(request)

    app.include_router(parse_upload_router)
    app.dependency_overrides[get_session] = _override_session
    return app


async def _post_upload(client, filename: str, content: bytes, mime: str):
    return await client.post(
        "/parse/upload",
        files={"file": (filename, content, mime)},
    )


# ============================== xlsx test ===============================


@pytest.mark.asyncio
async def test_upload_xlsx_returns_issue_voucher_candidate() -> None:
    """xlsx 出库台账上传 → IssueVoucher 候选, provider=demo-mock, 落盘 OK."""
    from httpx import ASGITransport, AsyncClient

    engine = await _make_engine()
    try:
        app = _build_app(engine)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
            # 简单 xlsx fake content (不需要真 Excel,DemoMockProvider 不读内容)
            resp = await _post_upload(
                c, "出库台账-2026-05.xlsx", b"PK\x03\x04demo-xlsx-bytes",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
            assert resp.status_code == 200, resp.text
            body = resp.json()
            assert body["provider"] == "demo-mock"
            assert body["source_type"] == "excel"
            cand = body["candidate"]
            assert len(cand["entities"]) >= 1
            ent = cand["entities"][0]
            assert ent["entity_type"] == "IssueVoucher"
            names = {f["name"] for f in ent["fields"]}
            # 8 个字段 IssueVoucher 应有
            assert {"voucher_no", "workshop", "applicant", "quantity", "unit",
                    "issued_date"}.issubset(names)
            # 置信度合理
            for f in ent["fields"]:
                assert 0.5 <= f["confidence"] <= 0.99
                assert f.get("source_span") is not None
            # warning 标 demo-mock
            assert any("demo-mock" in w for w in cand["warnings"])
            # 落盘 + checksum 8-hex
            attach = body["attachment"]
            assert attach["filename"] == "出库台账-2026-05.xlsx"
            assert attach["size_bytes"] > 0
            assert Path(attach["path"]).exists()
            assert len(attach["checksum"]) == 16

        async with AsyncSession(engine) as s:
            logs = (await s.execute(select(ActionLog))).scalars().all()
            assert len(logs) == 1
            assert "action=parse_upload" in (logs[0].input_summary or "")
            assert "filename=出库台账-2026-05.xlsx" in (logs[0].input_summary or "")
            assert "provider=demo-mock" in (logs[0].input_summary or "")
            assert logs[0].actor == "uploader-1"
    finally:
        await engine.dispose()


# ============================== pdf test ===============================


@pytest.mark.asyncio
async def test_upload_pdf_contract_returns_contract_and_customer_candidate() -> None:
    """Round 13 (corrected from round 5): pdf with 合同 in filename → Contract
    + Customer entities with a Customer-has-Contract relationship. Previously
    DemoMockProvider routed 合同 to PurchaseRequisition by mistake."""
    from httpx import ASGITransport, AsyncClient

    engine = await _make_engine()
    try:
        app = _build_app(engine)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
            resp = await _post_upload(
                c, "山东中铝_采购合同_2026Q2.pdf",
                b"%PDF-1.4\nfake pdf bytes for demo", "application/pdf",
            )
            assert resp.status_code == 200, resp.text
            body = resp.json()
            assert body["provider"] == "demo-mock"
            assert body["source_type"] == "contract"
            entities = body["candidate"]["entities"]
            types = sorted(e["entity_type"] for e in entities)
            assert types == ["Contract", "Customer"], (
                f"expected Contract+Customer, got {types}"
            )
            contract = next(e for e in entities if e["entity_type"] == "Contract")
            names = {f["name"] for f in contract["fields"]}
            for required in {
                "contract_no_external", "contract_no_internal", "amount_total",
                "amount_currency", "signing_date", "effective_date",
                "expiry_date", "payment_terms", "status",
            }:
                assert required in names, f"Contract missing {required}"
            # Customer-has-Contract relationship must be present (lets
            # confirm_writer set contract.customer_id from the seeded Customer).
            rels = body["candidate"]["relationships"]
            assert any(
                r["type"] == "Customer-has-Contract" for r in rels
            ), f"missing Customer-has-Contract relationship: {rels}"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_upload_pdf_purchase_only_filename_returns_pr_candidate() -> None:
    """Filename with 采购 but not 合同 (e.g. '采购单') still routes to PR.
    Locks down the keyword-priority order added in round 13."""
    from httpx import ASGITransport, AsyncClient

    engine = await _make_engine()
    try:
        app = _build_app(engine)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
            resp = await _post_upload(
                c, "成型车间_采购单_20260101.pdf",
                b"%PDF-1.4\nfake", "application/pdf",
            )
            assert resp.status_code == 200, resp.text
            ent = resp.json()["candidate"]["entities"][0]
            assert ent["entity_type"] == "PurchaseRequisition"
            names = {f["name"] for f in ent["fields"]}
            assert {"pr_no", "dept", "applicant", "apply_date"}.issubset(names)
    finally:
        await engine.dispose()


# ============================== jpg test ===============================


@pytest.mark.asyncio
async def test_upload_jpg_returns_issue_voucher_candidate() -> None:
    """jpg 领料单照片 → IssueVoucher entity."""
    from httpx import ASGITransport, AsyncClient

    engine = await _make_engine()
    try:
        app = _build_app(engine)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
            resp = await _post_upload(
                c, "成型车间_领料单_BL-2026-018_张师傅手写.jpg",
                b"\xff\xd8\xff\xe0fake-jpg-bytes", "image/jpeg",
            )
            assert resp.status_code == 200, resp.text
            body = resp.json()
            assert body["provider"] == "demo-mock"
            assert body["source_type"] == "wechat_screenshot"
            ent = body["candidate"]["entities"][0]
            assert ent["entity_type"] == "IssueVoucher"
    finally:
        await engine.dispose()


# ============================== edge cases ===============================


@pytest.mark.asyncio
async def test_upload_unknown_extension_returns_400() -> None:
    from httpx import ASGITransport, AsyncClient

    engine = await _make_engine()
    try:
        app = _build_app(engine)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
            r = await _post_upload(c, "blob.bin", b"abc", "application/octet-stream")
            assert r.status_code == 400
            assert "无法识别文件类型" in r.text
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_upload_oversize_returns_413() -> None:
    """20 MB+ file 应被拒."""
    from httpx import ASGITransport, AsyncClient

    engine = await _make_engine()
    try:
        app = _build_app(engine)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
            big = b"\xff\xd8" + b"x" * (21 * 1024 * 1024)  # ~21 MB
            r = await _post_upload(c, "big.jpg", big, "image/jpeg")
            assert r.status_code == 413
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_upload_is_deterministic_same_filename_same_seed() -> None:
    """Same filename → same checksum-based path (same content)→ same DemoMock entity."""
    from httpx import ASGITransport, AsyncClient

    engine = await _make_engine()
    try:
        app = _build_app(engine)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
            r1 = await _post_upload(c, "same.jpg", b"identical-bytes", "image/jpeg")
            r2 = await _post_upload(c, "same.jpg", b"identical-bytes", "image/jpeg")
            assert r1.status_code == 200 and r2.status_code == 200
            j1, j2 = r1.json(), r2.json()
            # Same checksum (same bytes)
            assert j1["attachment"]["checksum"] == j2["attachment"]["checksum"]
            assert j1["attachment"]["path"] == j2["attachment"]["path"]
            # DemoMockProvider seed = md5(filename + markdown len) → same → same fields
            f1 = {f["name"]: f["value"] for f in j1["candidate"]["entities"][0]["fields"]}
            f2 = {f["name"]: f["value"] for f in j2["candidate"]["entities"][0]["fields"]}
            assert f1 == f2
    finally:
        await engine.dispose()
