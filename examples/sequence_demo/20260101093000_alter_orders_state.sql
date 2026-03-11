-- Description: tighten state column
ALTER TABLE orders ALTER COLUMN state SET NOT NULL;
