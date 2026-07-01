-- Seed roles, demo users, centers, and sample products.
-- Default password for all demo users: password123

INSERT INTO roles (name) VALUES ('admin'), ('agent')
ON DUPLICATE KEY UPDATE name = VALUES(name);

INSERT INTO users (email, password_hash, full_name, role_id)
SELECT 'admin@charity.local',
       '$2b$10$UlZB9AWByr0D4G0HsXzH.eLytiohRbZBvv/aHpZm485WKj.8ZG6d6',
       'System Admin',
       r.id
FROM roles r
WHERE r.name = 'admin'
  AND NOT EXISTS (SELECT 1 FROM users WHERE email = 'admin@charity.local');

INSERT INTO users (email, password_hash, full_name, role_id)
SELECT 'agent1@charity.local',
       '$2b$10$UlZB9AWByr0D4G0HsXzH.eLytiohRbZBvv/aHpZm485WKj.8ZG6d6',
       'Agent One',
       r.id
FROM roles r
WHERE r.name = 'agent'
  AND NOT EXISTS (SELECT 1 FROM users WHERE email = 'agent1@charity.local');

INSERT INTO users (email, password_hash, full_name, role_id)
SELECT 'agent2@charity.local',
       '$2b$10$UlZB9AWByr0D4G0HsXzH.eLytiohRbZBvv/aHpZm485WKj.8ZG6d6',
       'Agent Two',
       r.id
FROM roles r
WHERE r.name = 'agent'
  AND NOT EXISTS (SELECT 1 FROM users WHERE email = 'agent2@charity.local');

INSERT INTO centers (name, code, address)
SELECT 'North Distribution Center', 'NDC-01', '100 North Ave, City A'
WHERE NOT EXISTS (SELECT 1 FROM centers WHERE code = 'NDC-01');

INSERT INTO centers (name, code, address)
SELECT 'South Collection Hub', 'SCH-02', '200 South St, City B'
WHERE NOT EXISTS (SELECT 1 FROM centers WHERE code = 'SCH-02');

INSERT INTO center_users (center_id, user_id)
SELECT c.id, u.id
FROM centers c
CROSS JOIN users u
WHERE c.code = 'NDC-01'
  AND u.email IN ('admin@charity.local', 'agent1@charity.local')
  AND NOT EXISTS (
    SELECT 1 FROM center_users cu
    WHERE cu.center_id = c.id AND cu.user_id = u.id
  );

INSERT INTO center_users (center_id, user_id)
SELECT c.id, u.id
FROM centers c
CROSS JOIN users u
WHERE c.code = 'SCH-02'
  AND u.email IN ('admin@charity.local', 'agent2@charity.local')
  AND NOT EXISTS (
    SELECT 1 FROM center_users cu
    WHERE cu.center_id = c.id AND cu.user_id = u.id
  );

INSERT INTO products (name, description, unit, created_by)
SELECT 'Canned Beans', '15 oz canned beans', 'can', u.id
FROM users u
WHERE u.email = 'admin@charity.local'
  AND NOT EXISTS (SELECT 1 FROM products WHERE name = 'Canned Beans');

INSERT INTO product_barcodes (product_id, barcode, barcode_type, is_primary)
SELECT p.id, '041331024816', 'UPC', 1
FROM products p
WHERE p.name = 'Canned Beans'
  AND NOT EXISTS (SELECT 1 FROM product_barcodes WHERE barcode = '041331024816');

INSERT INTO products (name, description, unit, created_by)
SELECT 'Rice Bag 2lb', 'Long grain white rice', 'bag', u.id
FROM users u
WHERE u.email = 'admin@charity.local'
  AND NOT EXISTS (SELECT 1 FROM products WHERE name = 'Rice Bag 2lb');

INSERT INTO product_barcodes (product_id, barcode, barcode_type, is_primary)
SELECT p.id, '071518000012', 'UPC', 1
FROM products p
WHERE p.name = 'Rice Bag 2lb'
  AND NOT EXISTS (SELECT 1 FROM product_barcodes WHERE barcode = '071518000012');
