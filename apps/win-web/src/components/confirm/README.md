# Confirm cards — P0 task ③

人机确认卡片组件。把任务② 解析出来的候选 JSON 渲染成可编辑的卡片，由用户确认/改值后调
`POST /api/win/confirm/entities` 写入本体表（带审计标记 + ActionLog）。

## 分层

- **展示层**（pure presentational, 无 fetch）
  - `ConfirmCard.tsx` — 一个 entity 一张卡。
  - `DuplicateWarningDialog.tsx` — 提交前的"新建 / 关联已有"对话框。
- **逻辑层**
  - `useConfirmSubmit.ts` — 编辑状态、提交流水、单条/全部确认。
- **数据契约**
  - `apps/win-web/src/data/candidate.ts` — `CandidateJSON` / `ConfirmEntitiesRequest` / `WrittenEntity`。
  - 对应后端：`yunwei_win/services/parse_pipeline/candidate.py` (来源) +
    `yunwei_win/api/confirm.py` (目的地)。

## ConfirmCard props

```ts
type ConfirmCardProps = {
  entity: CandidateEntity;                  // 任务② 候选 JSON 里的一个 entity
  edits: Record<string, unknown>;           // fieldName → 用户改后的值
  confirmed: boolean;                       // 是否已成功入库
  busy: boolean;                            // 提交进行中
  onEditField: (e: { fieldName: string; value: unknown }) => void;
  onConfirm: () => void;                    // 单条入库按钮
};
```

字段行渲染：`字段名 | 受控编辑框 | 置信度药丸 | "查看原文" 切换`。

- 置信度 ≥ 0.8 → 绿；0.6 ≤ x < 0.8 → 黄；< 0.6 → 红 + 行底色高亮。
- 用户编辑后字段：边框 + 底色变蓝，置信度药丸变为「人工修改」。
- `missing_required` 字段在卡片底部以「+ 字段名」按钮形式呈现，引导补填。
- 「查看原文」点开浮窗：page / cell / bbox / text，文字片段 fallback。

## useConfirmSubmit hook

```ts
const submit = useConfirmSubmit(candidate);
// submit.edits[tempId][fieldName] —— 当前编辑值
// submit.confirmed[tempId]        —— 是否已写入
// submit.writtenByTempId[tempId]  —— 后端返回的 WrittenEntity（含 verified_by / entity_id）
// submit.editField(tempId, fieldName, value)
// submit.submitOne(tempId, { duplicateResolutions })
// submit.submitAll({ duplicateResolutions })
```

`duplicateResolutions`：`{ [tempId]: "create" | "<existing-uuid>" }`，由
`DuplicateWarningDialog` 的选择产生。Hook 自己不识别重复——只忠实地把用户的决定带到后端。

## 提交语义（关键）

每次 submit 调 `POST /api/win/confirm/entities`，请求体：

```jsonc
{
  "ingestion_id": "demo-ing-2026-05-21",
  "source_type": "contract",
  "source_ref": "storage://...",
  "entities": [
    {
      "entity_type": "Customer",
      "temp_id": "cust-1",
      "existing_entity_id": null,  // or a UUID → 关联既有, 不再插入
      "fields": [
        {
          "name": "full_name",
          "value": "...",
          "confidence": 0.95,      // 若 was_edited=true 则改成 null
          "was_edited": false,
          "source_span": { "page": 1, "text": "..." }
        }
      ]
    }
  ],
  "relationships": [
    { "from_temp_id": "cust-1", "to_temp_id": "ct-1", "type": "Customer-has-Contact" }
  ]
}
```

后端写入时强制设置：
- `human_verified = true`
- `verified_by = <当前用户>`，`verified_at = now()`
- `source_type` / `source_ref` / `source_span` 透传自候选 JSON
- `confidence` = min(未被编辑的字段置信度)；如全部被改 → null
- 每条记录追加一条 `ActionLog`（`actor` = 用户，`input_summary` 含 ingestion_id + 改了哪些字段）

## Demo 路径

`apps/win-web/?screen=confirmDemo`

或在生产环境通过该 URL 参数访问。Demo 页喂硬编码 CandidateJSON（含 Customer +
Contact + Order + 一个 "疑似重复" 警告），用户点确认即调真实后端入库。

## 复用到其它端

`ConfirmCard` + `useConfirmSubmit` 是分层的：把 `ConfirmCard` 换成小程序 / 企微 H5
的渲染器，hook 不变；只要环境能 `fetch /api/win/confirm/entities` 就能复用。
