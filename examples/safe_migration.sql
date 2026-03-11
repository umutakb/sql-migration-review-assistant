-- Description: Add users table and safe index
-- Rollback: DROP TABLE users;
CREATE TABLE users (
    id BIGSERIAL PRIMARY KEY,
    email TEXT NOT NULL UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX CONCURRENTLY idx_users_created_at ON users (created_at);
