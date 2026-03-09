# Agent Read/Write Matrix — Income Fortress Platform

**Version:** 1.3.0
**Date:** 2026-03-09

R = Read, W = Write, RW = Read + Write, — = No access

## Foundation & Asset Tables

| Table | Agent 01 | Agent 02 | Agent 03 | Agent 04 | Agent 05 | Agent 07 | Agent 08 | Agent 09 | Agent 10 | Agent 11 | Agent 12 |
|-------|----------|----------|----------|----------|----------|----------|----------|----------|----------|----------|----------|
| securities | RW | R | R | R | R | R | R | R | R | R | R |
| features_historical | RW | — | RW | R | R | R | R | R | — | R | R |
| user_preferences | R | — | R | — | R | R | R | R | R | R | R |
| nav_snapshots | W | — | R | — | — | R | R | R | W | R | R |
| income_scores | — | — | W | — | R | R | R | R | — | R | R |
| asset_classifications | — | — | R | W | R | — | R | R | — | R | R |
| scoring_runs | — | — | RW | — | — | — | — | — | — | — | R |
| quality_gate_results | — | — | W | — | — | — | — | — | — | — | R |

## Analyst Tables

| Table | Agent 01 | Agent 02 | Agent 03 | Agent 04 | Agent 05 | Agent 07 | Agent 08 | Agent 09 | Agent 10 | Agent 11 | Agent 12 |
|-------|----------|----------|----------|----------|----------|----------|----------|----------|----------|----------|----------|
| analysts | — | RW | R | — | — | — | — | — | — | — | R |
| analyst_articles | — | W | R | — | — | — | — | — | — | — | R |
| analyst_recommendations | — | W | R | — | — | — | R | — | — | — | R |
| analyst_accuracy_log | — | RW | R | — | — | — | — | — | — | — | R |

## Portfolio & Position Tables

| Table | Agent 01 | Agent 02 | Agent 03 | Agent 04 | Agent 05 | Agent 07 | Agent 08 | Agent 09 | Agent 10 | Agent 11 | Agent 12 |
|-------|----------|----------|----------|----------|----------|----------|----------|----------|----------|----------|----------|
| accounts | — | — | — | — | — | — | RW | — | — | — | R |
| portfolios | — | — | R | — | R | R | RW | R | R | RW | R |
| portfolio_constraints | — | — | R | — | R | R | RW | R | R | R | R |
| positions | R | — | R | — | RW | R | RW | R | R | R | R |
| transactions | — | — | — | — | RW | R | R | R | — | R | R |
| dividend_events | — | — | — | — | RW | R | R | R | — | R | R |
| portfolio_income_metrics | — | — | — | — | R | R | R | W | — | R | R |
| portfolio_health_scores | — | — | — | — | — | R | R | R | — | W | R |

## Notes

- **Agent 01** is the primary owner of `securities` — it upserts on new ticker discovery
- **Agent 03** writes `features_historical` after scoring run
- **Agent 04** is sole writer to `asset_classifications`
- **Agent 08** is sole writer to `accounts`, `portfolios`, `portfolio_constraints` (creates/updates)
- **Agent 09** is sole writer to `portfolio_income_metrics`
- **Agent 10** is sole writer to `nav_snapshots` (Agent 01 also writes for ETFs)
- **Agent 11** is sole writer to `portfolio_health_scores`
- **Agent 12** reads everything but writes nothing — output is proposals (API response only)
- **No agent auto-executes transactions** — `transactions` written by Agent 05 on DRIP/tax
  events only after user approval
