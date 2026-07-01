# Hostinger Deployment Guide

This guide covers deploying the **Charity Inventory API** to Hostinger. Only the backend is hosted on Hostinger — the Expo mobile app runs on iPhones and connects to your API over HTTPS.

## What you deploy

| Component | Host on Hostinger? |
|-----------|-------------------|
| `charity-inventory/api/` | Yes |
| MySQL database | Provision in hPanel (not uploaded as code) |
| `charity-inventory/mobile/` | No — build/distribute via Expo or App Store |

---

## Prerequisites

- Hostinger plan with **Node.js** support (Business Web Hosting or VPS)
- A domain or subdomain (e.g. `api.yourdomain.com`)
- Git access to this repo, or ability to upload files via hPanel / SSH

---

## Step 1: Create the MySQL database

1. Log in to **Hostinger hPanel**.
2. Go to **Databases → MySQL Databases**.
3. Create a new database (e.g. `charity_inventory`).
4. Create a database user with a strong password.
5. Assign the user to the database with **full privileges**.
6. Note these values — you will need them for environment variables:

   | Variable | Example | Where to find it |
   |----------|---------|------------------|
   | `DB_HOST` | `mysql123.hostinger.com` | hPanel database details |
   | `DB_PORT` | `3306` | Usually 3306 |
   | `DB_NAME` | `u123456789_charity` | Database name shown in hPanel |
   | `DB_USER` | `u123456789_charity` | Database username |
   | `DB_PASSWORD` | *(your password)* | Set when creating the user |

> **Tip:** On Hostinger shared hosting, `DB_HOST` is typically **not** `localhost`. Use the hostname shown in hPanel.

---

## Step 2: Deploy the API code

Deploy only the `charity-inventory/api/` directory.

### Option A: Git deploy (recommended)

If Hostinger supports Git deployment for Node.js apps:

1. Connect your GitHub repo.
2. Set the **application root** to `charity-inventory/api`.
3. Set the branch (e.g. `main` or your feature branch).

### Option B: Manual upload

1. On your machine, build locally:
   ```bash
   cd charity-inventory/api
   npm install
   npm run build
   ```
2. Upload the entire `api/` folder to Hostinger, including:
   - `dist/` (compiled JavaScript)
   - `src/db/migrations/` (SQL migration files — required at runtime)
   - `package.json` and `package-lock.json`
3. Run `npm install --omit=dev` on the server (or let Hostinger's build step do it).

### Option C: VPS via SSH

```bash
git clone https://github.com/AlbertoDBP/Agentic.git
cd Agentic/charity-inventory/api
npm install
npm run build
```

---

## Step 3: Configure environment variables

In hPanel → your Node.js app → **Environment Variables**, set:

```env
PORT=3000
HOST=0.0.0.0
NODE_ENV=production

DB_HOST=<from hPanel>
DB_PORT=3306
DB_USER=<from hPanel>
DB_PASSWORD=<your password>
DB_NAME=<from hPanel>

JWT_SECRET=<generate a long random string, at least 32 characters>
JWT_EXPIRES_IN=24h

CORS_ORIGIN=*
```

Generate a JWT secret locally:

```bash
node -e "console.log(require('crypto').randomBytes(32).toString('hex'))"
```

> For production, you can tighten `CORS_ORIGIN` later. A native mobile app is less sensitive to CORS than a browser app, but restricting origins is still good practice if you add a web admin later.

---

## Step 4: Build and start commands

Set these in hPanel for your Node.js application:

| Setting | Value |
|---------|-------|
| **Node.js version** | 18 or higher |
| **Install command** | `npm install` |
| **Build command** | `npm run build` |
| **Start command** | `npm run start:prod` |

The `start:prod` script runs migrations then starts the server:

```bash
node dist/db/migrate.js && node dist/index.js
```

This uses the **compiled** migration runner (`dist/db/migrate.js`), which works in production without dev dependencies like `tsx`.

### First deploy only (alternative)

If you prefer to run migrations manually once:

```bash
cd charity-inventory/api
npm run build
node dist/db/migrate.js    # run once
npm start                  # subsequent restarts
```

Migrations are idempotent — re-running `migrate.js` skips already-applied files.

---

## Step 5: Configure domain and SSL

1. In hPanel, add a subdomain (e.g. `api.yourdomain.com`) pointing to your Node.js app.
2. Enable **SSL** (Let's Encrypt) for HTTPS.
3. Confirm the app is reachable:

   ```bash
   curl https://api.yourdomain.com/health
   ```

   Expected response:

   ```json
   {"status":"ok"}
   ```

---

## Step 6: Verify the API

Test login with seeded demo credentials (created by migration `002_seed_data.sql`):

```bash
curl -X POST https://api.yourdomain.com/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"agent1@charity.local","password":"password123"}'
```

You should receive a JWT token and user object.

Test centers (replace `<TOKEN>`):

```bash
curl https://api.yourdomain.com/centers \
  -H "Authorization: Bearer <TOKEN>"
```

---

## Step 7: Connect the mobile app

In `charity-inventory/mobile/.env` (or your EAS build config):

```env
EXPO_PUBLIC_API_URL=https://api.yourdomain.com
```

Rebuild or restart Expo after changing this value. On a physical iPhone, the URL must be your **public HTTPS API URL** — not `localhost`.

---

## Post-deployment checklist

- [ ] `GET /health` returns `{"status":"ok"}`
- [ ] `POST /auth/login` works with a seeded user
- [ ] `GET /centers` returns assigned centers with a valid token
- [ ] Mobile app can log in and scan against the live API
- [ ] SSL is active (HTTPS only)
- [ ] Demo passwords changed or seed users replaced with real accounts
- [ ] MySQL backups enabled in hPanel

---

## Updating the API

For each new release:

1. Deploy updated code (git pull or re-upload).
2. Run build: `npm install && npm run build`
3. Run migrations: `node dist/db/migrate.js`
4. Restart the app: `npm start` (or `npm run start:prod` to migrate + start in one step)

---

## Troubleshooting

### Migration fails: "Access denied for user"

- Verify `DB_HOST`, `DB_USER`, `DB_PASSWORD`, and `DB_NAME` match hPanel exactly.
- Confirm the database user has privileges on the database.

### Migration fails: "Cannot find module" or `tsx` not found

- Do **not** use `npm run migrate` in production — it depends on `tsx` (a dev dependency).
- Use `node dist/db/migrate.js` after `npm run build`.

### API starts but returns 503 / config errors

- Check that `JWT_SECRET` is set and at least 16 characters.
- Confirm all required env vars are present (see `.env.example`).

### Mobile app cannot connect

- Use HTTPS, not HTTP, in production.
- Confirm `EXPO_PUBLIC_API_URL` has no trailing slash.
- On iOS, App Transport Security blocks plain HTTP — HTTPS is required.

### `EADDRINUSE` or port errors

- Hostinger may assign `PORT` automatically. If so, use the port hPanel provides instead of hardcoding `3000`.

---

## Security recommendations

1. **Replace demo users** — seed data includes `agent1@charity.local` / `password123`. Create real users and disable or delete demo accounts before go-live.
2. **Strong JWT secret** — use at least 32 random bytes; never commit it to git.
3. **MySQL access** — keep credentials only in hPanel env vars, not in code.
4. **Backups** — enable automatic MySQL backups in hPanel.
5. **Logs** — monitor Node.js application logs after deploy for connection or auth errors.

---

## Related docs

- [README.md](./README.md) — project overview and local development
- [api/.env.example](./api/.env.example) — all environment variables
