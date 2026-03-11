-- Description: destructive migration
DROP TABLE legacy_logs;
TRUNCATE TABLE audit_events;
DELETE FROM sessions;
