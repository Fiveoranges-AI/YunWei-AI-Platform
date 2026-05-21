# parse_pipeline — file → candidate JSON

P0 task ② deliverable. Takes a contract / WeChat screenshot / Excel file
and emits a structured candidate JSON with per-field confidence and source
spans. **Does not write to the database** — task ③ wires confirmation +
writeback. Only the candidate JSON shape is committed-to API.

## Quick start

```python
from pathlib import Path
from yunwei_win.services.parse_pipeline import (
    MockProvider, parse_to_candidates,
)
from yunwei_win.services.parse_pipeline.providers.base import ProviderResult

# Excel — no provider needed.
result = await parse_to_candidates(
    file_path=Path("orders.xlsx"),
    source_type="excel",
    existing_customer_names=["上海建工集团", "中海石油"],
)
print(result.model_dump_json(indent=2))

# Contract / WeChat screenshot — pick a provider.
from yunwei_win.services.parse_pipeline.providers.claude import ClaudeProvider
provider = ClaudeProvider(session=session)   # tests use MockProvider(ProviderResult(...))
result = await parse_to_candidates(
    file_path=Path("hetong.pdf"),
    source_type="contract",
    provider=provider,
)
```

## CandidateJSON shape

```jsonc
{
  "ingestion_id": "uuid",
  "source": {
    "type": "contract|wechat_screenshot|excel",
    "file_ref": "storage://...",
    "uploaded_by": "user-id",
    "uploaded_at": "ISO8601"
  },
  "entities": [
    {
      "entity_type": "Customer|Contact|Contract|Order|OrderLine|Product|Invoice|Payment",
      "temp_id": "本次解析临时ID",
      "fields": [
        {
          "name": "full_name",
          "value": "上海建工集团股份有限公司",
          "confidence": 0.95,
          "source_span": {
            "page": 1,
            "bbox": [88, 142, 410, 168],
            "text": "买方:上海建工集团股份有限公司",
            "cell": null
          }
        }
      ],
      "missing_required": []
    }
  ],
  "relationships": [
    {"from_temp_id": "customer-1", "to_temp_id": "order-1", "type": "Customer-has-Order"}
  ],
  "overall_confidence": 0.91,
  "warnings": ["客户 'XXX' 与已有 'YYY' 高度相似 (相似度 0.91)"]
}
```

## Provider config

Two production providers; both are stateless except for the session
hand-off to `services.llm`.

| Provider          | Used by              | Env keys                                 |
| ----------------- | -------------------- | ---------------------------------------- |
| `ClaudeProvider`  | contract, screenshot | `ANTHROPIC_API_KEY`, `ANTHROPIC_BASE_URL` (optional, swaps to DeepSeek-compat) |
| `MockProvider`    | tests                | (none)                                   |

Add a custom provider by implementing the `ExtractionProvider` Protocol
in `providers/base.py` — return a `ProviderResult` with whatever
`entity_type`s + `field name`s you want; the adapter applies ontology
shaping and confidence math on top.

The Excel adapter doesn't use any provider — it's deterministic header
matching against `ontology.HEADER_ALIASES`.

## Confidence + `missing_required`

**Per-field confidence**:
- *Excel*: `header_match_confidence (1.0 exact alias / 0.85 substring) × value_presence (1.0 / 0.4 if blank)`.
- *Contract/Screenshot*: provider supplies confidence directly; clipped to
  `[0, 1]`. If the provider failed to emit `source_excerpt` /
  `source_page` / `source_ref_id`, confidence is capped at 0.5 minus 0.1
  and a warning is appended.

**overall_confidence**: mean of per-field confidences, scaled down by
`max(0.4, 1.0 - 0.05 × total_missing_required_count)`.

**missing_required per entity**: required ontology fields (`nullable=False`
AND no default; system FKs filtered out) minus the field names that have
a non-empty value in the candidate.

## What this layer **doesn't** do

- DB writes / confirmation UI / entity resolution merging.
- Free-form schema discovery (the existing `services/schema_ingest/`
  pipeline handles that for customer-specific schemas).
- OCR — the contract adapter falls through to pdfplumber text and then
  passes raw bytes to the vision provider; it doesn't run a standalone
  OCR step. Wire `OcrProvider` in task ③ if needed.

## Local smoke test

```bash
cd services/platform-api
python -m pytest tests/test_parse_pipeline.py -q
```
