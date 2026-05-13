# Dedicated runtimes — contract

Pro/Max enterprises get a per-tenant assistant runtime container (a
"dedicated runtime"). Free/Lite tiers share a pooled runtime instead.
The platform routes between them via the `runtime_registry` table in the
platform metadata database (see `platform_app/runtime_registry.py`).

Customer-facing code never sees a dedicated runtime URL. The Win SPA
calls `POST /win/api/assistant/chat` on the platform; the platform
resolves the runtime binding for the caller's enterprise and forwards
server-side. A runtime URL leaking to the browser is a security bug.

## Endpoints

A dedicated runtime MUST expose:

### `GET /healthz`

Returns `{"status": "ok"}` (or `"degraded"` / `"down"`). The platform
health probe polls this and flips the `runtimes.health` column; an
`unhealthy` binding is skipped in favour of the shared assistant
(`yunwei_win.assistant.router` falls back transparently).

A `200` status code with the JSON body above is enough — additional
fields are ignored.

**Probe semantics** (`platform_app.health.probe_all_runtimes_once`):

- Frequency: every `settings.health_probe_interval_seconds` (default
  30s, env `HEALTH_PROBE_INTERVAL_SECONDS`). The loop driver
  `probe_loop()` is started from `platform_app.main` lifespan; one
  uvicorn worker covers both the legacy `tenants` probe and the
  runtime registry probe.
- Timeout per probe: 5 seconds (shared `httpx.AsyncClient`).
- Status mapping:
  - HTTP 2xx + `{"status": "ok"}` → `healthy`
  - HTTP 2xx + `{"status": "degraded"}` → `degraded`
  - HTTP 2xx + `{"status": "down"}` → `unhealthy`
  - HTTP non-2xx, timeout, DNS/connect error → `unhealthy`
  - HTTP 2xx + unrecognised body / non-JSON → `unknown`
    (conservative: we do **not** flip `unhealthy` for a body we can't
    parse, so a runtime with a custom `/healthz` shape keeps serving
    traffic until we either fix the shape or add it to the mapping).
- One bad runtime never aborts the round — each row is wrapped in
  try/except both for the HTTP call and the `UPDATE`.

### `POST /assistant/chat`

Request body:

```json
{
  "question":     "string (1-2000 chars)",
  "customer_id":  "string | null  (UUID of a customer profile, or 'all')",
  "user_id":      "string  (opaque platform user id)"
}
```

Response body (200):

```json
{
  "answer":           "string",
  "citations":        [ { "source": "...", "snippet": "..." } ],
  "confidence":       0.0,
  "no_relevant_info": false
}
```

The shape mirrors the shared assistant in `yunwei_win.assistant.service`
so the Win SPA can render either response without branching. Missing
fields are filled in defensively by `yunwei_win.assistant.dedicated`:
`citations` defaults to `[]`, `confidence` to `0.5`, `no_relevant_info`
to `false`.

Status codes:

- `2xx` → response normalised and returned to the SPA.
- `4xx` → the platform returns a degraded payload to the SPA
  (`no_relevant_info=true`); it does NOT fall back to the shared path
  because a 4xx is a client-shape problem on the runtime side.
- `5xx`, connection error, timeout → the platform falls back to the
  shared assistant. The runtime URL is never logged in the failure
  message — only `enterprise_id`. Pro users still get an answer.

## Auth

The current `POST /win/api/assistant/chat` → dedicated-runtime hop uses
a private network (Railway internal DNS or a VPC peering); the runtime
trusts the platform on the basis of network reachability.

When dedicated runtimes are exposed over the public internet (or a
shared network), they must adopt the same HMAC scheme that
`platform_app/proxy.py` uses for the customer-agent gateway. The
signing module is `platform_app/hmac_sign.py`:

- Headers: `X-Tenant-Client`, `X-Tenant-Agent`, `X-User-Id`,
  `X-User-Name`, `X-User-Role`, `X-Auth-Timestamp`, `X-Auth-Nonce`,
  `X-Auth-Key-Id`, `X-Auth-Signature`.
- Payload: `v1 \n ts \n nonce \n METHOD \n host \n path \n client \n
  agent \n user_id \n user_role \n sha256(body)`.
- Verification: `hmac_sign.verify()` with a Redis-backed `NonceStore`
  for replay protection.

Until that lands, dedicated runtimes must:

1. Only bind to a private network interface (no public ingress).
2. Reject any request that doesn't carry an `X-User-Id` header set by
   the platform.

### Identity headers (current contract)

Every `POST /assistant/chat` from the platform carries:

- `X-Platform-Service: yunwei-win` — identifies the caller as the
  `yunwei_win` service. Runtimes MAY use this to reject calls that
  didn't come from a known platform service once more callers exist.
- `X-User-Id: <platform user id>` — opaque per-user identifier the
  runtime SHOULD record in its audit log. The platform does not send
  `X-Enterprise-Id`: a dedicated runtime is bound 1:1 to an enterprise
  via the registry, and enterprise scope is enforced server-side
  *before* the runtime is called. Treating a header as the source of
  tenant truth would defeat that gate.

Future HMAC support will add `X-Auth-Timestamp`, `X-Auth-Nonce`, and
`X-Auth-Signature` (see `platform_app/hmac_sign.py`); the identity
headers above will remain.

## Registering a runtime

```python
from platform_app.runtime_registry import upsert_runtime, bind_runtime

upsert_runtime(
    runtime_id="rt_yinhu_super_xiaochen",
    mode="dedicated",
    provider="super-xiaochen",
    endpoint_url="http://agent-yinhu-super-xiaochen:8000",
    version="v1",
)
bind_runtime(
    enterprise_id="yinhu",
    capability="assistant",
    runtime_id="rt_yinhu_super_xiaochen",
)
```

`mode` is `dedicated` for per-tenant or `pooled` for the shared Free/Lite
runtime. `capability` is currently always `assistant` but will expand
(e.g. `daily_report`, `ingest`) as more flows move behind the registry.

## Why no customer-facing URL

The customer's only entry point is the Win SPA at `/win/`, which makes
same-origin XHRs to `/win/api/*`. The platform decides per request
whether to use the shared assistant or forward to a dedicated runtime.

This means:

- A dedicated runtime can move (different host, different port,
  different region) without any SPA change.
- The runtime never sees an end-user cookie or session, so a runtime
  compromise can't impersonate the user against `/win/api/*`.
- Entitlement enforcement (`platform_app.entitlements`) happens once,
  server-side, on the platform — runtimes don't need to re-implement
  plan checks.

See also:

- `runtimes/examples/yinhu-super-xiaochen.compose.yml` — example
  docker-compose snippet for running a dedicated runtime locally.
- `docs/architecture/platform-v3.md` — full request flow and component
  boundaries.
