-- Description: risky migration
ALTER TABLE orders ALTER COLUMN status TYPE VARCHAR(32);
ALTER TABLE orders ADD COLUMN processed_at TIMESTAMPTZ NOT NULL;
UPDATE orders SET status = 'processed';
CREATE INDEX idx_orders_status ON orders(status);
