"""
Seed Rules for Asset Class Detection
Seeded with all 7 MVP classes. Rules are DB-driven in production
(asset_class_rules table). This module provides the default seed
used during migration and for the shared utility's in-memory fallback.
"""

SEED_RULES = [

    # ─────────────────────────────────────────
    # COVERED_CALL_ETF — highest priority (specific tickers)
    # ─────────────────────────────────────────
    {
        "asset_class": "COVERED_CALL_ETF",
        "rule_type": "ticker_pattern",
        "rule_config": {
            "tickers": [
                "JEPI", "JEPQ", "QYLD", "XYLD", "RYLD",
                "DIVO", "SVOL", "GPIQ", "GPIX", "XDTE",
                "ODTE", "CONY", "MSFO", "NVDY", "AMZY"
            ]
        },
        "priority": 5,
        "confidence_weight": 0.95,
    },
    {
        "asset_class": "COVERED_CALL_ETF",
        "rule_type": "metadata",
        "rule_config": {"strategy": ["Covered Call", "Option Income", "Buy-Write"]},
        "priority": 10,
        "confidence_weight": 0.85,
    },
    {
        "asset_class": "COVERED_CALL_ETF",
        "rule_type": "feature",
        "rule_config": {"options_strategy_present": True, "is_etf": True},
        "priority": 20,
        "confidence_weight": 0.75,
    },

    # ─────────────────────────────────────────
    # PREFERRED_STOCK — ticker suffix patterns
    # ─────────────────────────────────────────
    {
        "asset_class": "PREFERRED_STOCK",
        "rule_type": "ticker_pattern",
        "rule_config": {
            "suffixes": ["-PA", "-PB", "-PC", "-PD", "-PE", "-PF",
                         "-A", "-B", "-C", ".PR", "^A", "^B", "^C"]
        },
        "priority": 5,
        "confidence_weight": 0.90,
    },
    {
        "asset_class": "PREFERRED_STOCK",
        "rule_type": "metadata",
        "rule_config": {"security_type": ["Preferred Stock", "Preferred"]},
        "priority": 10,
        "confidence_weight": 0.90,
    },
    {
        "asset_class": "PREFERRED_STOCK",
        "rule_type": "feature",
        "rule_config": {"fixed_dividend": True, "par_value_exists": True},
        "priority": 20,
        "confidence_weight": 0.80,
    },

    # ─────────────────────────────────────────
    # MORTGAGE_REIT — before EQUITY_REIT (more specific)
    # ─────────────────────────────────────────
    {
        "asset_class": "MORTGAGE_REIT",
        "rule_type": "ticker_pattern",
        "rule_config": {
            "tickers": [
                "AGNC", "NLY", "MFA", "RITM", "PMT",
                "EARN", "RC", "TWO", "CHMI", "ARR"
            ]
        },
        "priority": 5,
        "confidence_weight": 0.95,
    },
    {
        "asset_class": "MORTGAGE_REIT",
        "rule_type": "metadata",
        "rule_config": {
            "fund_category": ["Mortgage REIT", "mREIT"],
            "sub_sector": ["Mortgage Real Estate Investment Trusts"]
        },
        "priority": 10,
        "confidence_weight": 0.90,
    },
    {
        "asset_class": "MORTGAGE_REIT",
        "rule_type": "feature",
        "rule_config": {
            "sectors": ["Real Estate"],
            "contains_mortgage": True,
            "leverage_ratio_min": 3.0
        },
        "priority": 20,
        "confidence_weight": 0.75,
    },

    # ─────────────────────────────────────────
    # EQUITY_REIT
    # ─────────────────────────────────────────
    {
        "asset_class": "EQUITY_REIT",
        "rule_type": "sector",
        "rule_config": {"sectors": ["Real Estate"]},
        "priority": 10,
        "confidence_weight": 0.70,
    },
    {
        "asset_class": "EQUITY_REIT",
        "rule_type": "metadata",
        "rule_config": {
            "fund_category": ["Real Estate", "REIT"],
            "security_type": ["REIT"]
        },
        "priority": 10,
        "confidence_weight": 0.85,
    },
    {
        "asset_class": "EQUITY_REIT",
        "rule_type": "feature",
        "rule_config": {"min_payout_ratio": 0.75, "sector": "Real Estate"},
        "priority": 20,
        "confidence_weight": 0.75,
    },

    # ─────────────────────────────────────────
    # BDC
    # ─────────────────────────────────────────
    {
        "asset_class": "BDC",
        "rule_type": "ticker_pattern",
        "rule_config": {
            "tickers": [
                "ARCC", "MAIN", "BXSL", "OBDC", "FSK",
                "GBDC", "HTGC", "TPVG", "SLRC", "PSEC"
            ]
        },
        "priority": 5,
        "confidence_weight": 0.95,
    },
    {
        "asset_class": "BDC",
        "rule_type": "metadata",
        "rule_config": {
            "fund_category": ["Business Development Company", "BDC"],
            "security_type": ["BDC"]
        },
        "priority": 10,
        "confidence_weight": 0.90,
    },
    {
        "asset_class": "BDC",
        "rule_type": "sector",
        "rule_config": {
            "sectors": ["Financials"],
            "sub_sectors": ["Asset Management", "Capital Markets"]
        },
        "priority": 20,
        "confidence_weight": 0.55,
    },

    # ─────────────────────────────────────────
    # BOND
    # ─────────────────────────────────────────
    {
        "asset_class": "BOND",
        "rule_type": "ticker_pattern",
        "rule_config": {
            "tickers": ["AGG", "BND", "LQD", "HYG", "JNK", "TLT", "IEF", "SHY"],
            "suffixes": [".BOND", "-BOND"]
        },
        "priority": 5,
        "confidence_weight": 0.90,
    },
    {
        "asset_class": "BOND",
        "rule_type": "metadata",
        "rule_config": {
            "security_type": ["Bond", "Fixed Income", "Treasury"],
            "asset_class": ["Bond", "Fixed Income"]
        },
        "priority": 10,
        "confidence_weight": 0.90,
    },
    {
        "asset_class": "BOND",
        "rule_type": "feature",
        "rule_config": {"has_maturity_date": True, "coupon_rate_exists": True},
        "priority": 15,
        "confidence_weight": 0.85,
    },

    # ─────────────────────────────────────────
    # DIVIDEND_STOCK — broadest, lowest priority
    # ─────────────────────────────────────────
    {
        "asset_class": "DIVIDEND_STOCK",
        "rule_type": "feature",
        "rule_config": {
            "dividend_yield_min": 0.01,
            "is_common_stock": True,
            "payout_ratio_max": 0.95
        },
        "priority": 50,
        "confidence_weight": 0.60,
    },
    {
        "asset_class": "DIVIDEND_STOCK",
        "rule_type": "metadata",
        "rule_config": {"security_type": ["Common Stock", "Equity"]},
        "priority": 30,
        "confidence_weight": 0.65,
    },
]
