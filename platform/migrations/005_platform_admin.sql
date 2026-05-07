-- Platform admin flag: cross-cutting role for YunWei AI staff who manage
-- ALL enterprises. Not a member of any specific enterprise — orthogonal
-- to enterprise_members.role. Set via `platform-admin promote-admin`.
ALTER TABLE users ADD COLUMN IF NOT EXISTS is_platform_admin INTEGER NOT NULL DEFAULT 0;
