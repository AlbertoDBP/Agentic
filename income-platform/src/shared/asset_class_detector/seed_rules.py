"""
Seed Rules for Asset Class Detection
Rules are DB-driven in production (asset_class_rules table).
This module provides the default seed used during migration and
for the shared utility's in-memory fallback.

Priority = lower number fires first (more specific beats general).
"""

SEED_RULES = [

    # ─────────────────────────────────────────
    # CEF — Closed-End Funds (must beat COVERED_CALL_ETF and BOND)
    # PIMCO, BlackRock, Eaton Vance, Gabelli, Calamos, Cohen & Steers, etc.
    # ─────────────────────────────────────────
    {
        "asset_class": "CEF",
        "rule_type": "ticker_pattern",
        "rule_config": {
            "tickers": [
                # PIMCO CEFs
                "PDO", "PTY", "PDI", "PCN", "PHK", "PCI", "PCM", "PFL", "PFN",
                "PHT", "PKO", "RCS",
                # BlackRock CEFs
                "BGT", "BIT", "BHK", "BST", "BTZ", "BGB", "BIGZ", "BCAT",
                "EHI", "ERC", "EMD", "EDD",
                # Eaton Vance CEFs
                "EV", "EVT", "ETO", "ETB", "ETG", "ETJ", "ETV", "ETW",
                # Gabelli CEFs
                "GAB", "GDV", "GGT", "GUT", "GRX",
                # Calamos CEFs
                "CHW", "CHI", "CHY", "CSQ",
                # Cohen & Steers CEFs
                "UTF", "UTG", "USA", "RQI", "RNP", "RFI", "RVT",
                # Western Asset / Franklin
                "SCD", "SFD", "WIA", "WIW", "FRA", "FAX",
                # Nuveen CEFs
                "JPC", "JPS", "JPT", "JQC", "JHY", "JHB",
                # Other common income CEFs
                "FFC", "FPF", "GHI", "GFY", "IID", "IDE",
                "BCX", "BLW", "BTO", "CIK", "CLD",
            ]
        },
        "priority": 3,
        "confidence_weight": 0.97,
    },
    {
        "asset_class": "CEF",
        "rule_type": "metadata",
        "rule_config": {
            "security_type": ["Closed-End Fund", "CEF", "Closed End Fund"],
            "fund_category": ["Closed-End Fund", "CEF"],
        },
        "priority": 8,
        "confidence_weight": 0.95,
    },
    {
        "asset_class": "CEF",
        "rule_type": "feature",
        "rule_config": {"is_cef": True},
        "priority": 12,
        "confidence_weight": 0.90,
    },

    # ─────────────────────────────────────────
    # COVERED_CALL_ETF — must be ETF + explicit covered-call strategy
    # Tighten: require explicit ticker list or metadata; avoid "option" in description
    # ─────────────────────────────────────────
    {
        "asset_class": "COVERED_CALL_ETF",
        "rule_type": "ticker_pattern",
        "rule_config": {
            "tickers": [
                "JEPI", "JEPQ", "QYLD", "XYLD", "RYLD",
                "DIVO", "SVOL", "GPIQ", "GPIX", "XDTE",
                "ODTE", "CONY", "MSFO", "NVDY", "AMZY",
                "TSLY", "GOOGY", "NFLY", "AMDY", "MSFO",
                "KLIP", "YMAX", "YMAG", "FEAT", "BALI",
                "IWMY", "SPYI", "QQQI", "ISPY", "DJIA",
                "PBP", "BXMX", "HNDL", "GLDI", "SLVO",
            ]
        },
        "priority": 5,
        "confidence_weight": 0.95,
    },
    {
        "asset_class": "COVERED_CALL_ETF",
        "rule_type": "metadata",
        "rule_config": {
            "strategy": ["Covered Call", "Buy-Write", "Equity Premium Income"],
            "fund_category": ["Covered Call", "Buy-Write", "Options Income"],
        },
        "priority": 10,
        "confidence_weight": 0.88,
    },
    # Feature rule: must be ETF AND explicitly covered-call (not just any options user)
    {
        "asset_class": "COVERED_CALL_ETF",
        "rule_type": "feature",
        "rule_config": {"covered_call": True, "is_etf": True},
        "priority": 15,
        "confidence_weight": 0.85,
    },

    # ─────────────────────────────────────────
    # PREFERRED_STOCK — ticker suffix patterns
    # ─────────────────────────────────────────
    {
        "asset_class": "PREFERRED_STOCK",
        "rule_type": "ticker_pattern",
        "rule_config": {
            "suffixes": ["-PA", "-PB", "-PC", "-PD", "-PE", "-PF",
                         ".PR", "^A", "^B", "^C"]
        },
        "priority": 5,
        "confidence_weight": 0.90,
    },
    {
        "asset_class": "PREFERRED_STOCK",
        "rule_type": "metadata",
        "rule_config": {"security_type": ["Preferred Stock", "Preferred"]},
        "priority": 10,
        "confidence_weight": 0.92,
    },
    {
        "asset_class": "PREFERRED_STOCK",
        "rule_type": "feature",
        "rule_config": {"fixed_dividend": True, "par_value_exists": True},
        "priority": 20,
        "confidence_weight": 0.80,
    },

    # ─────────────────────────────────────────
    # BOND — security_type metadata at high priority so it beats suffix matching
    # ─────────────────────────────────────────
    {
        "asset_class": "BOND",
        "rule_type": "metadata",
        "rule_config": {
            "security_type": ["Bond", "Fixed Income", "Treasury", "Corporate Bond",
                               "Municipal Bond", "Agency Bond", "Note"],
            "asset_class": ["Bond", "Fixed Income"],
        },
        "priority": 4,
        "confidence_weight": 0.95,
    },
    {
        "asset_class": "BOND",
        "rule_type": "ticker_pattern",
        "rule_config": {
            "tickers": [
                # Bond ETFs
                "AGG", "BND", "LQD", "HYG", "JNK", "TLT", "IEF", "SHY",
                "VCIT", "VCSH", "BSV", "BIV", "BLV", "VGSH", "VGIT", "VGLT",
                "MUB", "TIP", "SCHZ", "SCHI", "SCHR", "SCHQ",
                "BNDX", "IGIB", "IGSB", "IGLB", "USIG",
                "FALN", "ANGL", "HYDB", "HYLB", "USHY",
                # PIMCO bond ETFs (not CEFs)
                "MINT", "BOND", "LDUR", "MUNI",
            ],
            "suffixes": [".BOND", "-BOND"],
        },
        "priority": 5,
        "confidence_weight": 0.92,
    },
    {
        "asset_class": "BOND",
        "rule_type": "feature",
        "rule_config": {"has_maturity_date": True, "coupon_rate_exists": True},
        "priority": 10,
        "confidence_weight": 0.88,
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
                "EARN", "RC", "TWO", "CHMI", "ARR",
                "IVR", "NYMT", "ACRE", "BXMT", "GPMT",
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
            "sub_sector": ["Mortgage Real Estate Investment Trusts"],
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
            "leverage_ratio_min": 3.0,
        },
        "priority": 20,
        "confidence_weight": 0.75,
    },

    # ─────────────────────────────────────────
    # EQUITY_REIT
    # ─────────────────────────────────────────
    {
        "asset_class": "EQUITY_REIT",
        "rule_type": "metadata",
        "rule_config": {
            "fund_category": ["Real Estate", "REIT"],
            "security_type": ["REIT"],
        },
        "priority": 10,
        "confidence_weight": 0.85,
    },
    {
        "asset_class": "EQUITY_REIT",
        "rule_type": "sector",
        "rule_config": {"sectors": ["Real Estate"]},
        "priority": 15,
        "confidence_weight": 0.70,
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
                "GBDC", "HTGC", "TPVG", "SLRC", "PSEC",
                "CSWC", "KCAP", "NEWT", "GLAD", "GAIN",
                "ORCC", "OCSL", "CCAP", "TCPC", "PFLT",
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
            "security_type": ["BDC"],
        },
        "priority": 10,
        "confidence_weight": 0.90,
    },
    {
        "asset_class": "BDC",
        "rule_type": "sector",
        "rule_config": {
            "sectors": ["Financials"],
            "sub_sectors": ["Asset Management", "Capital Markets"],
        },
        "priority": 20,
        "confidence_weight": 0.55,
    },

    # ─────────────────────────────────────────
    # DIVIDEND_STOCK — broadest, lowest priority
    # ─────────────────────────────────────────
    {
        "asset_class": "DIVIDEND_STOCK",
        "rule_type": "metadata",
        "rule_config": {"security_type": ["Common Stock", "Equity"]},
        "priority": 30,
        "confidence_weight": 0.65,
    },
    {
        "asset_class": "DIVIDEND_STOCK",
        "rule_type": "feature",
        "rule_config": {
            "dividend_yield_min": 0.01,
            "is_common_stock": True,
            "payout_ratio_max": 0.95,
        },
        "priority": 50,
        "confidence_weight": 0.60,
    },
]
