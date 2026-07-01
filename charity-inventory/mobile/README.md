# Charity Inventory — Mobile App

Expo + React Native iPhone client for scanning UPC barcodes and logging charity center inventory.

## Prerequisites

- Node.js 18+
- [Expo Go](https://expo.dev/go) on your iPhone (for development)
- API running and reachable (see [../README.md](../README.md))

## Setup

```bash
cd charity-inventory/mobile
cp .env.example .env
npm install
```

Set your API URL in `.env`:

```env
# Use your computer's LAN IP for physical iPhone testing — not localhost
EXPO_PUBLIC_API_URL=http://192.168.1.10:3000

# Production (after Hostinger deploy)
# EXPO_PUBLIC_API_URL=https://api.yourdomain.com
```

## Run on iPhone (Expo Go)

```bash
npm start
```

1. Scan the QR code with your iPhone camera or Expo Go.
2. Ensure phone and computer are on the same Wi‑Fi network.
3. Sign in with `agent1@charity.local` / `password123`.

## Screens

| Screen | Route | Purpose |
|--------|-------|---------|
| Sign In | `/login` | Email/password authentication |
| Select Center | `/centers` | Pick assigned center, start session |
| Scan | `/scan` | Camera UPC scan + manual entry fallback |
| Product | `/product` | Confirm known product or create new |
| Quantity | `/quantity` | Enter count with quick-pick buttons |
| Summary | `/summary` | Review session, complete or continue |

## Field workflow features

- Camera permission handling with manual barcode fallback
- Scan cooldown to prevent duplicate rapid reads
- Unknown UPC inline product creation (name + unit)
- Duplicate product scans increment session quantity via API
- Session summary with total units
- Route guards — protected screens redirect if not logged in

## Scripts

| Command | Description |
|---------|-------------|
| `npm start` | Start Expo dev server |
| `npm run ios` | Start with iOS simulator (macOS only) |
| `npm run typecheck` | TypeScript check |
| `npm run build:ios` | EAS internal iOS build (requires EAS account) |

## Production iOS build (EAS)

1. Install EAS CLI: `npm install -g eas-cli`
2. Log in: `eas login`
3. Configure project: `eas init` (updates `app.json` project ID)
4. Edit `eas.json` with your API URL and Apple credentials
5. Build: `npm run build:ios:prod`

See [Expo EAS Build docs](https://docs.expo.dev/build/introduction/) for Apple Developer setup.

## Troubleshooting

### Cannot connect to API

- Use LAN IP, not `localhost`, when testing on a physical iPhone.
- Confirm API is running: `curl http://<ip>:3000/health`
- Check firewall allows port 3000.

### Camera not working

- Grant camera permission in iOS Settings → Expo Go.
- Use **Enter Barcode Manually** on the scan screen as fallback.

### Login fails

- Verify `EXPO_PUBLIC_API_URL` in `.env` and restart Expo (`r` in terminal).
- Confirm API migrations ran and seed users exist.

## Related

- [Project README](../README.md)
- [Hostinger deployment](../DEPLOYMENT.md)
