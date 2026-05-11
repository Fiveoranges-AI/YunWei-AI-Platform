# LandingAI Schema-Routed Ingest Runbook

## What This Does

The `/api/ingest/auto` endpoint normally runs Mistral OCR → DeepSeek/Claude
extractors (identity / commercial / ops). Setting `DOCUMENT_AI_PROVIDER=landingai`
swaps the **extract step** for LandingAI schema-routed extraction:

```
upload → Mistral OCR (always) → pipeline_router → selected LandingAI Extract calls
       → normalize → UnifiedDraft → confirm → DB writeback (V1: identity / contract_order
       / commitment_task_risk only; finance / logistics / manufacturing_requirement
       are preserved in raw pipeline_results until win.* tables exist)
```

Parse is **always Mistral OCR** — LandingAI is only the extract provider.

## Enable In Staging

Set in Railway dashboard:

```env
DOCUMENT_AI_PROVIDER=landingai
VISION_AGENT_API_KEY=<LandingAI key>
LANDINGAI_ENVIRONMENT=us
```

Restart the platform service.

## Smoke Test Inputs

1. Business card image → expect `identity`.
2. Contract PDF → expect `identity + contract_order`.
3. Payment proof or invoice → expect `identity + finance`.
4. Delivery note → expect `identity + logistics`.
5. Customer chat screenshot / text note → expect `identity + commitment_task_risk`.

## Success Criteria

- `/win/api/ingest/auto` streams progress events `ocr`, `route`, `extract`,
  `merge`, `auto_done`.
- Final response includes `pipeline_results` with one entry per selected
  pipeline.
- Confirm still writes customers / contacts / order / contract / memory rows
  for supported pipelines.
- Unsupported preview pipelines (finance / logistics / manufacturing_requirement)
  appear in raw `pipeline_results` and do not break confirm.
- Contract / order extraction stays Party A only — Party B / supplier / seller
  is never written into `customers.full_name`.

## Rollback

Set:

```env
DOCUMENT_AI_PROVIDER=mistral
```

Restart the platform service. The legacy planner + identity/commercial/ops
extractors take over again.

## Cost Notes

LandingAI Extract bills per schema call. Pipeline router caps at 3 schemas
per upload; identity is auto-included whenever any non-identity pipeline
fires. For a typical contract PDF, expect 2 extract calls (identity +
contract_order).
