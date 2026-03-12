# Architecture Decision Records (ADRs)

**Version:** 1.3.0
**Last Updated:** 2026-03-09

---

## Overview

This directory contains Architecture Decision Records (ADRs) documenting critical design decisions for the Income Fortress Platform. Each ADR captures the context, decision, and consequences of significant technical choices.

---

## ADR Index

### Core Scoring Architecture

| ADR | Title | Status | Date |
|-----|-------|--------|------|
| [ADR-P01](decisions-log.md#adr-p01) | Monte Carlo NAV Erosion in Agent 03 | Accepted | 2025-12-XX |
| [ADR-P02](decisions-log.md#adr-p02) | Asset Classification Shared Detector | Accepted | 2026-01-XX |
| [ADR-P03](decisions-log.md#adr-p03) | Tax Efficiency as Parallel Output | Accepted | 2026-01-XX |
| [ADR-P04](decisions-log.md#adr-p04) | Proposal-Only Architecture (No Auto-Execution) | Accepted | 2025-12-XX |
| [ADR-P05](decisions-log.md#adr-p05) | Analyst Signal Storage Schema | Accepted | 2026-01-XX |

### Data Providers & Integration

| ADR | Title | Status | Date |
|-----|-------|--------|------|
| [ADR-A01](decisions-log.md#adr-a01) | Finnhub as 4th Credit Rating Provider | Accepted | 2026-03-09 |

### Post-Scoring & Explanation

| ADR | Title | Status | Date |
|-----|-------|--------|------|
| [ADR-001](../agents/agent-03/decisions/decisions-log.md) | Post-Scoring LLM Explanation Layer | Accepted | 2026-02-25 |

### Platform-Level Decisions

| ADR | Title | Status | Date |
|-----|-------|--------|------|
| [ADR-P09/P10](decisions-log.md) | Portfolio Management & Rebalancing | Accepted | TBD |
| [ADR-P11](decisions-log.md) | Chowder Number Thresholds | Accepted | TBD |
| [ADR-P12](decisions-log.md) | Scenario Simulation Model | Accepted | TBD |
| [ADR-007](decisions-log.md) | Agent 05 Portfolio Scope | Accepted | TBD |

---

## Decision Categories

### Architectural

- **ADR-P01**: Monte Carlo NAV erosion prevents yield traps
- **ADR-P02**: Shared asset classifier ensures consistent taxonomy
- **ADR-P04**: Proposal-only avoids regulatory friction

### Data Strategy

- **ADR-P05**: Analyst signals stored with full provenance
- **ADR-A01**: Multi-provider credit rating fallback chain

### Scoring & Output

- **ADR-P03**: Tax output decoupled from income score
- **ADR-001**: LLM explanation translates scores to plain English

---

## Document Locations

- **consolidated-log**: `decisions-log.md`
- **individual-ADRs**: See links in index above
- **agent-specific ADRs**: See `docs/agents/*/decisions/`

---

## How to Contribute

When proposing a new architectural decision:

1. Copy the ADR template below
2. Assign next ADR number (platform = P-XX, agent = ADR-XXX)
3. Write decision record in Markdown
4. Submit as PR for team review
5. Upon approval, move to canonical location and update this index

---

## ADR Template

```markdown
# ADR-XXX: Decision Title

**Status:** Proposed | Accepted | Deprecated
**Date:** YYYY-MM-DD
**Deciders:** [Names]
**Component:** [Agent/System Name]

## Context

[Describe the situation that motivated this decision.]

## Decision

[State the decision clearly.]

## Rationale

[Explain why this decision was chosen over alternatives.]

## Consequences

[List positive and negative impacts of this decision.]

## Alternatives Considered

[Document rejected options and why they were not chosen.]

## References

[Link to related docs, code, or external references.]
```

---

**For detailed decisions, see:**
- [decisions-log.md](decisions-log.md) — consolidated platform ADRs
- Each agent folder: `docs/agents/agent-XX/decisions/` — agent-specific ADRs
