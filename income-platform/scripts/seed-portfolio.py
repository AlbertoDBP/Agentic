"""
Seed script: Create account, portfolio, and insert 80 positions.
Run: DATABASE_URL=<prod> python3 scripts/seed-portfolio.py
"""
import asyncio
import os
import sys

import asyncpg

DATABASE_URL = os.environ.get("DATABASE_URL", "")
if "?sslmode=require" in DATABASE_URL:
    DATABASE_URL = DATABASE_URL.split("?sslmode=require")[0]

TENANT_ID = "11111111-1111-1111-1111-111111111111"
ACCOUNT_NAME = "Primary Income Account"
PORTFOLIO_NAME = "Income Fortress"

# fmt: off
POSITIONS = [
    # (symbol, quantity, avg_cost_basis)
    ("ACRE",     827,       6.73),
    ("AGNC",     401.9,     9.90),
    ("AGNCZ",    78,       25.34),
    ("AHL/PRD",  205,      18.92),
    ("AQN",      386,      10.61),
    ("ARCC",     281.516,  18.32),
    ("ARI",      491,      10.11),
    ("ATH/PRD",  305.982,  17.87),
    ("BPYPP",    398,      15.99),
    ("BRSP",    1101,       5.39),
    ("BWNB",     170,      21.44),
    ("CHMI/PRA", 180,      21.04),
    ("CIM/PRC",  230,      18.32),
    ("CIM/PRD",  210,      19.07),
    ("CSWC",     283,      18.70),
    ("DMLP",     215,      23.10),
    ("EPD",      215,      24.65),
    ("EPR",      134,      39.86),
    ("EPR/PRC",  245,      19.17),
    ("ET",       352,      16.99),
    ("GHI",      708,      14.60),
    ("IVR/PRC",  155,      17.67),
    ("KRP",      304,      13.11),
    ("MPT",      671,       9.78),
    ("NLY",      397,      19.28),
    ("O",         80,      60.60),
    ("OBDC",     771,      11.73),
    ("ONL",     1905,       4.25),
    ("OXLCL",    220,      23.16),
    ("PMT/PRB",  145,      21.74),
    ("PMT/PRC",  126,      19.75),
    ("PMTU",     155,      25.65),
    ("PRIF/PRL", 200,      22.31),
    ("SLRC",     365.889,  14.09),
    ("TDS/PRU",  291,      15.25),
    ("TPVG",     547.959,  11.22),
    ("TRINZ",    117,      25.50),
    ("VZ",        75,      39.96),
    ("WES",      206,      36.97),
    ("XIFR",     265,      33.18),
    ("AWP",      846,       9.22),
    ("BCX",      616.78,    8.06),
    ("BIZD",     481,      13.45),
    ("BTO",      228,      29.17),
    ("CCD",      239,      21.05),
    ("DFP",      195.512,  19.19),
    ("DMB",      408,      10.85),
    ("ECC",     1152,       8.14),
    ("HQH",      490,      17.22),
    ("IWMI",      39,      50.20),
    ("JPC",      765,       7.04),
    ("NIHI",      38,      52.28),
    ("OXLC",     433,      25.40),
    ("PDI",      472,      18.40),
    ("PDO",      716,      13.48),
    ("PFFA",     349.716,  19.03),
    ("PTY",      460.029,  12.75),
    ("QQQJ",      57,      52.51),  # Listed as QQQJ (was QQQI in image)
    ("RNP",      281.532,  20.97),
    ("RQI",      460.779,  12.58),
    ("RVT",      202.242,  14.00),
    ("THQ",      613.55,   17.19),
    ("THW",      535.887,  12.16),
    ("USA",      945,       6.05),
    ("UTF",      250,      22.68),
    ("UTG",      151.351,  27.84),
    ("XFLT",    1269.304,   6.60),
    # Bonds (CUSIP-based)
    ("427096AH5", 4000,    84.33),
    ("55342UAH7", 8000,    86.19),
    ("74348TAW2", 5000,    75.46),
]
# fmt: on


async def seed():
    conn = await asyncpg.connect(DATABASE_URL, ssl="require")
    print("Connected to database")

    try:
        await conn.execute("BEGIN")

        # ── 1. Upsert securities ──
        print("\n[1/4] Upserting securities...")
        for symbol, _, _ in POSITIONS:
            await conn.execute(
                """
                INSERT INTO platform_shared.securities (symbol, is_active)
                VALUES ($1, TRUE)
                ON CONFLICT (symbol) DO NOTHING
                """,
                symbol,
            )
        print(f"  {len(POSITIONS)} securities ensured")

        # ── 2. Create account ──
        print("\n[2/4] Creating account...")
        account_id = await conn.fetchval(
            """
            INSERT INTO platform_shared.accounts
                (tenant_id, account_name, account_type, broker)
            VALUES ($1, $2, 'taxable', 'Schwab')
            ON CONFLICT DO NOTHING
            RETURNING id
            """,
            TENANT_ID,
            ACCOUNT_NAME,
        )
        if account_id is None:
            account_id = await conn.fetchval(
                """
                SELECT id FROM platform_shared.accounts
                WHERE tenant_id = $1 AND account_name = $2
                """,
                TENANT_ID,
                ACCOUNT_NAME,
            )
            print(f"  Account already exists: {account_id}")
        else:
            print(f"  Created account: {account_id}")

        # ── 3. Create portfolio ──
        print("\n[3/4] Creating portfolio...")
        portfolio_id = await conn.fetchval(
            """
            INSERT INTO platform_shared.portfolios
                (tenant_id, account_id, portfolio_name, status)
            VALUES ($1, $2, $3, 'ACTIVE')
            ON CONFLICT DO NOTHING
            RETURNING id
            """,
            TENANT_ID,
            account_id,
            PORTFOLIO_NAME,
        )
        if portfolio_id is None:
            portfolio_id = await conn.fetchval(
                """
                SELECT id FROM platform_shared.portfolios
                WHERE tenant_id = $1 AND portfolio_name = $2
                """,
                TENANT_ID,
                PORTFOLIO_NAME,
            )
            print(f"  Portfolio already exists: {portfolio_id}")
        else:
            print(f"  Created portfolio: {portfolio_id}")

        # ── 4. Insert positions ──
        print("\n[4/4] Inserting positions...")
        inserted = 0
        skipped = 0
        total_value = 0.0

        for symbol, qty, cost in POSITIONS:
            total_cost = round(qty * cost, 2)
            total_value += total_cost
            try:
                await conn.execute(
                    """
                    INSERT INTO platform_shared.positions
                        (portfolio_id, symbol, status, quantity,
                         avg_cost_basis, total_cost_basis,
                         current_price, current_value,
                         acquired_date)
                    VALUES ($1, $2, 'ACTIVE', $3, $4, $5, $4, $5, CURRENT_DATE)
                    ON CONFLICT (portfolio_id, symbol, status) DO NOTHING
                    """,
                    portfolio_id,
                    symbol,
                    qty,
                    cost,
                    total_cost,
                )
                inserted += 1
            except Exception as e:
                print(f"  SKIP {symbol}: {e}")
                skipped += 1

        # Update portfolio total value
        await conn.execute(
            """
            UPDATE platform_shared.portfolios
            SET total_value = $1, updated_at = NOW()
            WHERE id = $2
            """,
            round(total_value, 2),
            portfolio_id,
        )

        await conn.execute("COMMIT")

        print(f"\n  Inserted: {inserted}")
        print(f"  Skipped:  {skipped}")
        print(f"  Total portfolio value (at cost): ${total_value:,.2f}")
        print(f"\n  Portfolio ID: {portfolio_id}")
        print(f"  Account ID:   {account_id}")
        print(f"  Tenant ID:    {TENANT_ID}")

    except Exception as e:
        await conn.execute("ROLLBACK")
        print(f"\nFailed (rolled back): {e}")
        raise
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(seed())
