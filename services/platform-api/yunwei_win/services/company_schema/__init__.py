"""公司 schema 目录服务的对外门面。

Public surface:
- ``DEFAULT_COMPANY_SCHEMA``: 默认 catalog 静态数据，测试和迁移会引用。
- ``ensure_default_company_schema(session)``: 幂等种子。
- ``get_company_schema(session)``: 返回完整 catalog dict。
- ``create_schema_change_proposal``: 新增 schema 改动提案。
- ``approve_schema_change_proposal``: 审批 + 应用提案。
"""

from yunwei_win.services.company_schema.catalog import (
    approve_schema_change_proposal,
    create_schema_change_proposal,
    ensure_default_company_schema,
    get_company_schema,
)
from yunwei_win.services.company_schema.default_catalog import DEFAULT_COMPANY_SCHEMA

__all__ = [
    "DEFAULT_COMPANY_SCHEMA",
    "approve_schema_change_proposal",
    "create_schema_change_proposal",
    "ensure_default_company_schema",
    "get_company_schema",
]
