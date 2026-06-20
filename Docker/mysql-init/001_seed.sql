CREATE TABLE IF NOT EXISTS customers (
  id INT PRIMARY KEY,
  name VARCHAR(80) NOT NULL,
  tier VARCHAR(20) NOT NULL
);
INSERT IGNORE INTO customers (id, name, tier) VALUES (1, 'Alice', 'gold'), (2, 'Bob', 'silver');
CREATE TABLE IF NOT EXISTS orders (
  id INT PRIMARY KEY,
  customer_id INT NOT NULL,
  total DECIMAL(10,2) NOT NULL,
  INDEX idx_orders_customer_id (customer_id),
  CONSTRAINT fk_orders_customer FOREIGN KEY (customer_id) REFERENCES customers(id)
);
INSERT IGNORE INTO orders (id, customer_id, total) VALUES (10, 1, 42.50), (11, 2, 18.00);
CREATE USER IF NOT EXISTS 'safy_readonly'@'%' IDENTIFIED BY 'safy_ro_runtime_test_fake';
GRANT SELECT, SHOW VIEW ON safy_runtime_test.* TO 'safy_readonly'@'%';
FLUSH PRIVILEGES;
