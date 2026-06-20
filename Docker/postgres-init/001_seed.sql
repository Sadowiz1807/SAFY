CREATE TABLE IF NOT EXISTS customers (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  tier TEXT NOT NULL
);
INSERT INTO customers (id, name, tier) VALUES (1, 'Alice', 'gold'), (2, 'Bob', 'silver') ON CONFLICT (id) DO NOTHING;
CREATE TABLE IF NOT EXISTS orders (
  id INTEGER PRIMARY KEY,
  customer_id INTEGER NOT NULL REFERENCES customers(id),
  total NUMERIC(10,2) NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_orders_customer_id ON orders(customer_id);
INSERT INTO orders (id, customer_id, total) VALUES (10, 1, 42.50), (11, 2, 18.00) ON CONFLICT (id) DO NOTHING;
DO $$ BEGIN
  CREATE ROLE safy_readonly LOGIN PASSWORD 'safy_ro_runtime_test_fake';
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;
GRANT CONNECT ON DATABASE safy_runtime_test TO safy_readonly;
GRANT USAGE ON SCHEMA public TO safy_readonly;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO safy_readonly;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO safy_readonly;
