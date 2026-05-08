-- Cleanup: legacy ACL table replaced by enterprise_members + agent_grants
-- (migration 004). All read paths switched in commit 2b2c3d7. Safe to drop
-- now that the new schema has been live across the test suite.
DROP TABLE IF EXISTS user_tenant;
