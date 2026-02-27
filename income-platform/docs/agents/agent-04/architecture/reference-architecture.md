# Agent 04 — Reference Architecture

**Component:** Asset Classification Service  
**Port:** 8004  
**Last Updated:** 2026-02-27

---

## System Overview

```mermaid
graph TB
    subgraph Clients["Clients"]
        A03[Agent 03\nIncome Scorer\nPort 8003]
        EXT[External Callers]
    end

    subgraph Agent04["Agent 04 — Asset Classification Service (Port 8004)"]
        API[FastAPI Layer\n/classify /rules /health]
        ENGINE[Classification Engine\norchestrates pipeline]
        
        subgraph Pipeline["Classification Pipeline"]
            OVR[1. Override Check\nconfidence=1.0]
            CACHE[2. Cache Check\n24hr TTL]
            DETECT[3. Rule Detection\nShared Detector]
            ENRICH[4. Enrichment\nif confidence < 0.70]
            BENCH[5. Benchmarks\nPeer Group + Values]
            TAX[6. Tax Profile\nDrag + Account]
            PERSIST[7. Persist + Cache\nPostgreSQL]
        end
    end

    subgraph Shared["Shared Utility"]
        DET[AssetClassDetector]
        TAX2[Taxonomy\n7 Classes]
        RULES[RuleMatcher\n4 Rule Types]
        SEED[SeedRules\n19 Rules]
    end

    subgraph External["External"]
        A01[Agent 01\nMarket Data\nPort 8001]
        DB[(PostgreSQL\nplatform_shared)]
        A05[Agent 05\nTax Optimizer\nPort 8005]
    end

    A03 -->|POST /classify| API
    EXT -->|POST /classify| API
    API --> ENGINE
    ENGINE --> OVR --> CACHE --> DETECT --> ENRICH --> BENCH --> TAX --> PERSIST
    DETECT --> DET
    DET --> TAX2
    DET --> RULES
    RULES --> SEED
    ENRICH -->|confidence < 0.70| A01
    PERSIST --> DB
    TAX -->|tax_efficiency| A05

    style Agent04 fill:#1a1a2e,stroke:#4a9eff,color:#fff
    style Shared fill:#16213e,stroke:#4a9eff,color:#fff
    style Pipeline fill:#0f3460,stroke:#4a9eff,color:#fff
```

---

## Classification Pipeline Detail

```mermaid
sequenceDiagram
    participant C as Caller
    participant API as API Layer
    participant E as Engine
    participant DB as PostgreSQL
    participant DET as Shared Detector
    participant A01 as Agent 01

    C->>API: POST /classify {ticker}
    API->>E: classify(ticker)
    E->>DB: check override
    alt Override exists
        DB-->>E: override record
        E-->>API: confidence=1.0 result
    else No override
        E->>DB: check cache (valid_until > now)
        alt Cache hit
            DB-->>E: cached classification
            E-->>API: cached result
        else Cache miss
            E->>DET: detect(ticker, security_data)
            DET-->>E: DetectionResult + confidence
            alt confidence < 0.70
                E->>A01: GET /stocks/{ticker}/fundamentals
                E->>A01: GET /stocks/{ticker}/etf
                A01-->>E: enriched data
                E->>DET: detect(ticker, enriched_data)
                DET-->>E: improved DetectionResult
            end
            E->>E: get_benchmark(asset_class)
            E->>E: build_tax_profile(asset_class)
            E->>DB: persist classification
            E-->>API: full classification result
        end
    end
    API-->>C: ClassificationResponse
```

---

## Data Model

```mermaid
erDiagram
    asset_classifications {
        uuid id PK
        varchar ticker
        varchar asset_class
        varchar parent_class
        float confidence
        bool is_hybrid
        jsonb characteristics
        jsonb benchmarks
        jsonb sub_scores
        jsonb tax_efficiency
        jsonb matched_rules
        varchar source
        bool is_override
        timestamptz classified_at
        timestamptz valid_until
    }

    asset_class_rules {
        uuid id PK
        varchar asset_class
        varchar rule_type
        jsonb rule_config
        int priority
        float confidence_weight
        bool active
        timestamptz created_at
    }

    classification_overrides {
        uuid id PK
        varchar ticker
        varchar asset_class
        text reason
        varchar created_by
        timestamptz effective_from
        timestamptz effective_until
        timestamptz created_at
    }
```

---

## Shared Utility Architecture

```mermaid
graph LR
    subgraph SharedUtil["src/shared/asset_class_detector/"]
        INIT[__init__.py\nexports: AssetClassDetector]
        TAX[taxonomy.py\nAssetClass enum\nAssetClassInfo\nHIERARCHY dict]
        RULES[rule_matcher.py\nRuleMatcher\n4 rule types\nconfidence scoring]
        SEED[seed_rules.py\n19 seed rules\n7 asset classes]
        DET[detector.py\nAssetClassDetector\ndetect()\ndetect_with_fallback()]
    end

    A03[Agent 03] -->|from shared.asset_class_detector import| INIT
    A04[Agent 04] -->|from shared.asset_class_detector import| INIT
    AN[Agent N...] -->|from shared.asset_class_detector import| INIT
    INIT --> DET
    DET --> TAX
    DET --> RULES
    RULES --> SEED
```

---

## Rule Priority System

| Priority | Rule Type | Confidence Weight | Example |
|---|---|---|---|
| 5 | ticker_pattern (known list) | 0.90–0.95 | JEPI → COVERED_CALL_ETF |
| 5 | ticker_pattern (suffix) | 0.90 | BAC-PA → PREFERRED_STOCK |
| 10 | metadata | 0.85–0.90 | fund_category=Mortgage REIT |
| 10 | sector | 0.70–0.85 | sector=Real Estate |
| 20+ | feature | 0.55–0.80 | has_maturity_date=True |
| 50 | DIVIDEND_STOCK fallback | 0.60 | common stock + yield |

Lower priority number = evaluated first = higher specificity.

---

## Deployment

| Item | Value |
|---|---|
| Service root | `src/asset-classification-service/` |
| Start command | `PYTHONPATH=src:src/asset-classification-service python3 -m uvicorn app.main:app --port 8004` |
| Migration | `python3 scripts/migrate.py` (run from service root) |
| Credentials | Root `.env` at `income-platform/` |
| DB schema | `platform_shared` (shared with Agent 03) |
| Tables | `asset_classifications`, `asset_class_rules`, `classification_overrides` |
