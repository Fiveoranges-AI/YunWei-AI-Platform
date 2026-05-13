-- 009 · Invite codes for self-service trial registration.
-- Each code is single-use. Redeeming creates a brand-new user + a new
-- per-user enterprise + the enterprise_members link in one transaction.
-- The new user can immediately access /win/ (智通客户) — the middleware
-- looks up their single enterprise via enterprise_members.

CREATE TABLE IF NOT EXISTS invite_codes (
  code                    TEXT PRIMARY KEY,
  created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by              TEXT,                                 -- admin user_id
  note                    TEXT,                                 -- optional context for admin
  expires_at              TIMESTAMPTZ,                          -- NULL = never
  redeemed_at             TIMESTAMPTZ,                          -- NULL = still active
  redeemed_by_user_id     TEXT REFERENCES users(id) ON DELETE SET NULL,
  redeemed_enterprise_id  TEXT REFERENCES enterprises(id) ON DELETE SET NULL,
  revoked_at              TIMESTAMPTZ                           -- admin disabled
);

-- Index helps the "redeem" UPDATE find an active code quickly.
CREATE INDEX IF NOT EXISTS idx_invite_codes_active
  ON invite_codes(code)
  WHERE redeemed_at IS NULL AND revoked_at IS NULL;
