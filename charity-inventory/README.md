# Charity Inventory MVP

Mobile-first charity inventory system for field agents to scan UPC barcodes, log quantities, and associate entries with charity centers.

## Stack

| Layer | Technology |
|-------|------------|
| Mobile | Expo + React Native + TypeScript |
| API | Node.js + Fastify + TypeScript |
| Database | MySQL |
| Hosting target | Hostinger (Node.js + MySQL) |

## Repository layout

```
charity-inventory/
├── api/          # Headless JSON API
└── mobile/       # Expo iPhone client
```

## Quick start (local)

### 1. MySQL

Create a database and user:

```sql
CREATE DATABASE charity_inventory CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'charity_user'@'%' IDENTIFIED BY 'change_me';
GRANT ALL PRIVILEGES ON charity_inventory.* TO 'charity_user'@'%';
FLUSH PRIVILEGES;
```

### 2. API

```bash
cd charity-inventory/api
cp .env.example .env
# Edit .env with your MySQL credentials and JWT_SECRET
npm install
npm run migrate
npm run dev
```

API runs at `http://localhost:3000`.

### 3. Mobile (iPhone via Expo Go)

```bash
cd charity-inventory/mobile
cp .env.example .env
# Set EXPO_PUBLIC_API_URL to your machine IP, e.g. http://192.168.1.10:3000
npm install
npm start
```

Scan the QR code with Expo Go on your iPhone. Use your computer's LAN IP (not `localhost`) so the phone can reach the API.

### Demo credentials

| Email | Password | Centers |
|-------|----------|---------|
| `agent1@charity.local` | `password123` | North Distribution Center |
| `agent2@charity.local` | `password123` | South Collection Hub |
| `admin@charity.local` | `password123` | Both centers |

Sample UPCs in seed data: `041331024816`, `071518000012`.

## API endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/auth/login` | Email/password login |
| POST | `/auth/logout` | Logout (audit log) |
| GET | `/me` | Current user |
| GET | `/centers` | Assigned centers |
| GET | `/centers/:id` | Center detail |
| GET | `/centers/:id/inventory` | Center inventory entries |
| POST | `/products/lookup` | UPC lookup |
| POST | `/products` | Create product (+ optional barcode) |
| GET | `/products/:id` | Product detail |
| POST | `/inventory-sessions` | Start or resume active session |
| GET | `/inventory-sessions/:id` | Session with entries |
| POST | `/inventory-sessions/:id/complete` | Complete session |
| POST | `/inventory-entries` | Add or increment entry |
| GET | `/reports/export?centerId=1` | CSV export |

## Business rules

- Every inventory entry belongs to exactly one center and one agent.
- Users may be assigned to multiple centers; centers may have multiple users.
- Quantity must be a positive integer.
- Unknown UPCs do not block the workflow — agents can create products inline.
- Duplicate scans within a session increment quantity on the existing entry.
- Authorization prevents cross-center access.

## Hostinger deployment

### MySQL

1. Create a MySQL database in Hostinger hPanel.
2. Note host, port, database name, user, and password.

### Node.js API

1. Upload or deploy `charity-inventory/api` to Hostinger Node.js hosting.
2. Set environment variables in hPanel:

```
PORT=3000
NODE_ENV=production
DB_HOST=<hostinger-mysql-host>
DB_PORT=3306
DB_USER=<user>
DB_PASSWORD=<password>
DB_NAME=<database>
JWT_SECRET=<long-random-secret>
JWT_EXPIRES_IN=24h
CORS_ORIGIN=*
```

3. Set start command: `npm run migrate && npm start`
4. Build step: `npm install && npm run build`

### Mobile production

Point `EXPO_PUBLIC_API_URL` to your Hostinger API URL (e.g. `https://api.yourdomain.com`).

## Database schema

Tables: `roles`, `users`, `centers`, `center_users`, `products`, `product_barcodes`, `inventory_sessions`, `inventory_entries`, `inventory_adjustments`, `audit_logs`, `schema_migrations`.

Migrations live in `api/src/db/migrations/`. Run with `npm run migrate`.

## Tests

```bash
cd charity-inventory/api
npm test
```

## Mobile workflow

1. Login
2. Select assigned center (creates/resumes inventory session)
3. Scan UPC with iPhone camera
4. Confirm known product or create new one
5. Enter quantity
6. Repeat scan cycle or view session summary
7. Complete session when done
