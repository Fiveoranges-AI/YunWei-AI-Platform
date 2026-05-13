# Per-agent secrets

This directory holds one `<client>-<agent>/.env` file per agent container.
Platform-level secrets (cookie key, tunnel token, admin bootstrap) stay in
the repo-root `.env`; everything that scales O(n_agents) lives here.

## Adding a new agent

1. **Decide the IDs.** `client_id` ≤ 32 chars, `[a-z0-9-]+`. Same for
   `agent_id`. Path on the platform will be `/{client_id}/{agent_id}/`.
2. **Add a docker-compose service** in `ops/docker-compose.yml`:

   ```yaml
   agent-<client>-<agent>:
     build: /path/to/agent/repo
     env_file:
       - ../agents/<client>-<agent>/.env
     networks: [cf-tunnel]
     expose: ["8000"]
   ```
3. **Run platform-admin to register the tenant**, capture the env block:

   ```bash
   docker compose -f ops/docker-compose.yml run --rm platform-app \
     python -m platform_app.admin add-tenant <client> <agent> \
     --display-name "<显示名>" \
     --container-url "http://agent-<client>-<agent>:8000" \
     | tee /tmp/<agent>.out
   ```

   The `== AGENT .env ==` block in stdout has `HMAC_SECRET_CURRENT` etc.
4. **Create `agents/<client>-<agent>/.env`** by copying the .env block from
   step 3 and filling in `ANTHROPIC_API_KEY` plus any agent-specific
   business config.
5. **Grant the user ACL**:

   ```bash
   docker compose -f ops/docker-compose.yml run --rm platform-app \
     python -m platform_app.admin grant <username> <client> <agent>
   ```
6. **Bring the agent up**: `docker compose -f ops/docker-compose.yml up -d
   agent-<client>-<agent>`.

The DB row in `tenants` is the source of truth for the HMAC secret. The
agent .env is a derivative — if they diverge (manual edit, mismatched
restart), the platform's signed request won't verify and the agent rejects
with 401.

## Rotating an HMAC key

```bash
docker compose -f ops/docker-compose.yml run --rm platform-app \
  python -m platform_app.admin rotate-tenant-key <client> <agent>
```

Output prints `new_secret` and `new_kid`. Update the agent's `.env`:
- `HMAC_SECRET_PREV` ← old `HMAC_SECRET_CURRENT`
- `HMAC_KEY_ID_PREV` ← old `HMAC_KEY_ID_CURRENT`
- `HMAC_SECRET_CURRENT` ← new secret
- `HMAC_KEY_ID_CURRENT` ← new kid

Then `docker compose restart agent-<client>-<agent>`. After the rollout
window (≥24h, when no signed request from the platform still uses the
prev key), `clear-prev-key`.

## Files in this directory

- `<client>-<agent>/.env` — committed-via-template-only (real file is
  gitignored at root via the global `.env` rule)
- `<client>-<agent>/.env.example` — committed; documents required keys
