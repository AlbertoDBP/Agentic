# Market Data Service — Reference Architecture
**Version:** 1.2.0
**Updated:** 2026-02-23
**Status:** Production ✅

---

## Overview

The Market Data Service (Agent 01) is the foundational data layer of the Income Fortress Platform. It provides real-time and historical price data to all other agents via a REST API, with Redis caching and PostgreSQL persistence.

---

## System Architecture

```mermaid
graph TB
    Client["External Clients\n(legatoinvest.com)"]
    Nginx["Nginx Reverse Proxy\n(SSL Termination)\nPort 443"]
    MDS["Market Data Service\nFastAPI\nPort 8001"]
    AV["Alpha Vantage API\n(Free Tier)\n5 req/min"]
    Valkey["Managed Valkey\n(DigitalOcean)\nVPC Only"]
    PG["Managed PostgreSQL\n(DigitalOcean)\nVPC Only"]

    Client -->|"HTTPS /api/market-data/*"| Nginx
    Nginx -->|"HTTP /stocks/* (prefix stripped)"| MDS
    MDS -->|"Cache read/write\nTTL: 5min (price)\n4hr (history)"| Valkey
    MDS -->|"Persist + query\nOHLCV data"| PG
    MDS -->|"Fetch on cache miss\n1.1s rate limit"| AV

    style MDS fill:#2196F3,color:#fff
    style Valkey fill:#FF6B6B,color:#fff
    style PG fill:#4CAF50,color:#fff
    style AV fill:#FF9800,color:#fff
```

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Service health with DB and cache status |
| GET | `/stocks/{symbol}/price` | Current price (DB → Cache → Alpha Vantage) |
| GET | `/stocks/{symbol}/history` | OHLCV range query. Params: `start_date`, `end_date`, `limit` (max 365) |
| GET | `/stocks/{symbol}/history/stats` | Min, max, avg, volatility, price change % for period |
| POST | `/stocks/{symbol}/history/refresh` | Force fetch from Alpha Vantage and persist |
| GET | `/api/v1/cache/stats` | Cache hit/miss statistics |

**Public URL pattern:** `https://legatoinvest.com/api/market-data/stocks/{symbol}/price`
**Internal pattern:** `http://localhost:8001/stocks/{symbol}/price`

---

## Data Flow

```mermaid
sequenceDiagram
    participant C as Client
    participant N as Nginx
    participant S as Market Data Service
    participant V as Valkey Cache
    participant D as PostgreSQL
    participant A as Alpha Vantage

    C->>N: GET /api/market-data/stocks/AAPL/history
    N->>S: GET /stocks/AAPL/history (prefix stripped)
    S->>V: Check cache key
    alt Cache hit
        V-->>S: Return cached data
    else Cache miss
        S->>D: Query price_history table
        alt DB has data
            D-->>S: Return OHLCV records
            S->>V: Cache result (4hr TTL)
        else DB miss (within 140-day window)
            S->>A: TIME_SERIES_DAILY compact
            A-->>S: OHLCV JSON
            S->>D: Upsert records
            S->>V: Cache result (4hr TTL)
        end
    end
    S-->>N: JSON response
    N-->>C: HTTPS response
```

---

## Data Model

```mermaid
erDiagram
    STOCK_PRICES {
        uuid id PK
        varchar symbol
        numeric price
        numeric volume
        timestamp timestamp
        varchar source
        timestamp created_at
    }

    PRICE_HISTORY {
        uuid id PK
        varchar symbol
        date date
        numeric open_price
        numeric high_price
        numeric low_price
        numeric close_price
        numeric adjusted_close
        bigint volume
        varchar data_source
        timestamp created_at
    }

    STOCK_PRICES ||--o{ PRICE_HISTORY : "symbol"
```

**Unique constraint:** `price_history(symbol, date)` — prevents duplicate records, enables safe upserts.

---

## Infrastructure

| Component | Provider | Notes |
|-----------|----------|-------|
| Droplet | DigitalOcean NYC3 | 2vCPU, 4GB RAM, Ubuntu LTS |
| PostgreSQL | DigitalOcean Managed | VPC-only, no public exposure |
| Valkey | DigitalOcean Managed | VPC-only, replaces local Redis |
| Firewall | DigitalOcean Cloud Firewall | Allows 22, 80, 443 only |
| SSL | Let's Encrypt via Nginx | Auto-renew |
| Container | Docker (Compose V2) | `income-platform-market-data-service` |

---

## Constraints & Limitations

- **Alpha Vantage free tier:** 5 requests/minute, compact window (~100 days), no adjusted close data
- **140-day history cutoff:** Requests for data older than 140 days return DB-only results
- **`change` and `change_percent` fields:** Return 0.0 — free tier doesn't provide intraday change data
- **Planned migration:** Polygon.io + Financial Modeling Prep after Agent 02, unlocking full history and dividend data

---
