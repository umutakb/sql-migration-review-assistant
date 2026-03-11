-- Description: add replacement state column
ALTER TABLE orders ADD COLUMN state TEXT;
UPDATE orders SET state = 'new' WHERE state IS NULL;
