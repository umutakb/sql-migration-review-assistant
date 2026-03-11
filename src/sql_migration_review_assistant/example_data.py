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
    "sequence_demo/20260101090000_create_orders.sql": """-- Description: create orders table
-- Rollback: DROP TABLE orders;
CREATE TABLE orders (
    id BIGSERIAL PRIMARY KEY,
    status TEXT,
    customer_id BIGINT
);
""",
    "sequence_demo/20260101091000_drop_orders_status.sql": """-- Description: drop old status column
ALTER TABLE orders DROP COLUMN status;
""",
    "sequence_demo/20260101092000_add_orders_state.sql": (
        """-- Description: add replacement state column
ALTER TABLE orders ADD COLUMN state TEXT;
UPDATE orders SET state = 'new' WHERE state IS NULL;
"""
    ),
    "sequence_demo/20260101093000_alter_orders_state.sql": """-- Description: tighten state column
ALTER TABLE orders ALTER COLUMN state SET NOT NULL;
""",
    "sequence_demo/20260101094000_drop_sessions.sql": """-- Description: cleanup sessions table
DROP TABLE sessions;
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
