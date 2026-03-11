-- Description: create orders table
-- Rollback: DROP TABLE orders;
CREATE TABLE orders (
    id BIGSERIAL PRIMARY KEY,
    status TEXT,
    customer_id BIGINT
);
