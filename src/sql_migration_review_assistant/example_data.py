"""Packaged example content for bootstrap command."""

from __future__ import annotations

EXAMPLE_FILES: dict[str, str] = {
    "safe_migration.sql": """-- Description: Add users table and safe index
-- Rollback: DROP TABLE users;
CREATE TABLE users (
    id BIGSERIAL PRIMARY KEY,
    email TEXT NOT NULL UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX CONCURRENTLY idx_users_created_at ON users (created_at);
""",
    "risky_migration.sql": """-- Description: risky changes for demonstration
ALTER TABLE orders ALTER COLUMN status TYPE VARCHAR(32);
ALTER TABLE orders ADD COLUMN processed_at TIMESTAMPTZ NOT NULL;
UPDATE orders SET status = 'processed';
CREATE INDEX idx_orders_status ON orders(status);
""",
    "destructive_migration.sql": """-- Description: destructive migration
DROP TABLE legacy_logs;
TRUNCATE TABLE audit_events;
DELETE FROM sessions;
""",
    "config.yaml": """report_title: SQL Migration Review Report (Examples)
dialect: postgres
enabled_rules:
  safety.description_comment_missing: true
  safety.rollback_comment_missing: true
disabled_rules:
  - schema.rename_drop_add_heuristic
severity_mapping:
  safety.transaction_safety: warning
fail_on: error
fail_threshold:
  severity: error
  risk_score: 20
risk_weights:
  severity.error: 9
  severity.warning: 3
  severity.info: 1
ignored_paths:
  - archive/*.sql
exclude_patterns:
  - legacy/**/*.sql
""",
}
