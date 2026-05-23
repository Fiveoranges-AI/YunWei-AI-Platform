# 用友集成占位设计

本目录是“锦泰耐火材料 AI 生产流转助手 MVP”第一阶段的用友集成占位。当前只做 schema 发现、字段映射和导入草稿设计，不连接真实客户数据库，不读取 on-premise 生产库，不写回用友。

## 边界

- 不替换用友，不做完整 ERP。
- 不直接连接锦泰内网 / on-premise 数据库。
- 不让 AI 直接修改正式业务数据。
- 所有 AI 识别、Excel/照片/单据解析结果，未来先进入 `jintai_mvp.ai_extraction_queue`，人工确认后再进入业务表。
- 用友来源数据只作为外部来源，通过 `jintai_mvp.external_source_mappings` 保留来源系统、来源表、来源记录号与本地记录的映射。

## 文件说明

- `schema_discovery.ts`：生成未来 schema 盘点清单，当前不执行数据库连接。
- `import_customers.ts`：客户资料导入草稿映射。
- `import_orders.ts`：销售订单导入草稿映射。
- `import_products.ts`：产品档案导入草稿映射。
- `import_inventory.ts`：库存快照导入草稿映射。
- `mapping_config.example.json`：字段映射配置样例。

## 推荐后续接入方式

1. 第一优先：锦泰从用友导出 CSV/Excel，平台离线导入并进入待确认队列。
2. 第二优先：客户提供只读中间库或只读视图，平台只拉取必要字段。
3. 最后才考虑 VPN/专线/内网代理，并且必须只读、审计、限表、限字段。

本轮没有任何真实连接参数，也没有任何导入任务会被自动执行。
