# Income Fortress Platform — Documentation Orchestrator
## Project-Specific Skill for Claude Chat + Claude Code

**Version:** 2.0.0
**Last Updated:** 2026-03-04
**Replaces:** SKILL/SKILL.md, SKILL/platform-documentation-orchestrator-v2.md (repo root)
**Canonical Location:** `/Agentic/income-platform/.claude/SKILL.md`

---

## Purpose

This skill governs how Claude generates, updates, and packages documentation for the
Income Fortress Platform. It is the single source of truth for documentation workflow —
used in both Claude Chat (claude.ai) and Claude Code (VS Code).

---

## Project Paths (Canonical)

| Location | Path |
|---|---|
| Mac project root | `/Volumes/CH-DataOne/AlbertoDBP/Agentic/income-platform` |
| Mac downloads | `/Volumes/CH-DataOne/AlbertoDBP/Downloads` |
| GitHub repo | `https://github.com/AlbertoDBP/Agentic` (private) |
| Droplet project | `/opt/Agentic/income-platform` |
| Droplet SSH | `ssh -i ~/.ssh/id_ed25519 root@138.197.78.238` |
| Claude Chat outputs | `/mnt/user-data/outputs/` |
| Claude Chat work dir | `/home/claude/` |

---

## Documentation Folder Structure (Actual — income-platform)

```
income-platform/
├── .claude/
│   └── SKILL.md                          ← THIS FILE
├── documentation/
│   ├── CHANGELOG.md                      ← Single changelog for platform
│   ├── CHANGELOG-market-data-service.md  ← Service-level changelogs
│   ├── CHANGELOG-root.md
│   ├── DOCUMENTATION-MANIFEST.md
│   ├── DOCUMENTATION-STATUS.md
│   ├── DESIGN-SUMMARY.md
│   ├── AUTO-UPDATE-README.md
│   ├── INTEGRATION_GUIDE.md
│   ├── DEPLOYMENT.md
│   ├── QUICKSTART.md
│   ├── README.md
│   ├── index.md                          ← Master navigation
│   ├── reference-architecture.md
│   ├── decisions-log.md                  ← ALL ADRs consolidated here
│   ├── architecture/                     ← Architecture docs + diagrams
│   ├── functional/                       ← One .md per agent/component
│   │   ├── agent-01-market-data-functional-spec.md
│   │   ├── agent-01-market-data-sync.md
│   │   ├── agent-01-multi-provider-architecture.md
│   │   ├── agent-01-historical-price-queries.md
│   │   ├── agent-02-newsletter-ingestion.md
│   │   ├── agent-02-api-layer.md
│   │   ├── agent-03-functional-spec.md
│   │   ├── agent-03-income-scoring.md
│   │   ├── agent-03-implementation-spec.md
│   │   ├── agent-12-proposal-agent.md
│   │   ├── agents-5-6-7-9-summary.md
│   │   ├── ADR-001-post-scoring-llm-explanation.md
│   │   ├── feature-store-v2.md
│   │   ├── income-scorer-v6.md
│   │   └── reference-architecture.md
│   ├── implementation/                   ← Implementation specs
│   │   ├── implementation-01-market-data.md
│   │   ├── V2.0__nav_erosion_analysis.sql
│   │   ├── V3.0__complete_platform_schema.sql
│   │   ├── data_collector.py
│   │   ├── examples.py
│   │   ├── monte_carlo_engine.py
│   │   └── service.py
│   ├── deployment/                       ← Deployment guides
│   ├── testing/                          ← Test matrices
│   ├── diagrams/                         ← Mermaid .mmd files
│   ├── archive/                          ← Deprecated docs
│   └── decisions-log.md                  ← ADR index + all records
└── src/
    ├── market-data-service/
    ├── agent-02-newsletter-ingestion/
    ├── income-scoring-service/
    ├── asset-classification-service/
    ├── tax-optimization-service/         ← Agent 05 (Develop pending)
    └── shared/
```

---

## Naming Conventions

| Document Type | Pattern | Example |
|---|---|---|
| Agent functional spec | `agent-NN-[name]-functional-spec.md` | `agent-05-tax-optimization-functional-spec.md` |
| Agent implementation spec | `agent-NN-[name]-implementation-spec.md` | `agent-05-tax-optimization-implementation-spec.md` |
| ADR (standalone) | `ADR-NNN-[slug].md` in `functional/` | `ADR-007-agent05-portfolio-scope.md` |
| ADR (consolidated) | Append to `decisions-log.md` | New section `### ADR-007` |
| Service changelog | `CHANGELOG-[service-name].md` | `CHANGELOG-tax-optimization-service.md` |

---

## ADR Conventions

ADRs are maintained in **two places** — always update both:

1. **Standalone file** in `documentation/functional/ADR-NNN-[slug].md`
2. **Consolidated entry** appended to `documentation/decisions-log.md`

Current ADR index (from decisions-log.md):
- ADR-001: Post-Scoring LLM Explanation Layer
- ADR-002: NAV Erosion Calculation for Covered Call ETFs
- ADR-003: ROC Tax Efficiency Tracking
- ADR-004: Granular SAIS Curves (5-Zone Scoring)
- ADR-005: Profile-Driven Circuit Breaker Auto-Enable
- ADR-006: Preference-Based Configuration System
- ADR-007: Agent 05 Portfolio Data Scope Deferral ← NEW (this session)
- ADR-008: Celery Queue Specialization
- ADR-009: Structured JSON Logging
- ADR-010: Manual Tax Breakdown Mapping

Next ADR: **ADR-011**

---

## CHANGELOG Format

File: `documentation/CHANGELOG.md`

```markdown
## [Unreleased]

### Added
- **Agent 05 (Tax Optimization)**: Functional spec, implementation spec — DESIGN complete
- **ADR-007**: Agent 05 portfolio data scope deferral

---

## [0.4.0] — 2026-03-04 — Agent 05 Design Complete
...
```

---

## Document Phase Workflow

When user says **"Document"**, Claude executes this exact sequence:

### Step 1 — Generate Files (Claude Chat)

Claude creates all documentation files in `/home/claude/[session-dir]/`:

```
/home/claude/agent-NN-docs/
└── documentation/
    ├── functional/
    │   ├── agent-NN-[name]-functional-spec.md
    │   └── ADR-NNN-[slug].md
    └── implementation/
        └── agent-NN-[name]-implementation-spec.md
```

Plus patch files for existing docs:
```
/home/claude/agent-NN-docs/
├── CHANGELOG-patch.md        ← New entry to prepend to CHANGELOG.md
└── decisions-log-patch.md    ← New ADR entry to append to decisions-log.md
```

### Step 2 — Package as TAR

```bash
cd /home/claude
tar -czf agent-NN-[name]-documentation.tar.gz agent-NN-docs/
cp agent-NN-[name]-documentation.tar.gz /mnt/user-data/outputs/
```

### Step 3 — Present for Download

Claude calls `present_files` with the TAR path.

### Step 4 — Mac Extraction Instructions

User downloads TAR to `/Volumes/CH-DataOne/AlbertoDBP/Downloads/`

```bash
# Extract
cd /Volumes/CH-DataOne/AlbertoDBP/Downloads
tar -xzf agent-NN-[name]-documentation.tar.gz

# Copy new files to project
cp documentation/functional/*.md \
   /Volumes/CH-DataOne/AlbertoDBP/Agentic/income-platform/documentation/functional/

cp documentation/implementation/*.md \
   /Volumes/CH-DataOne/AlbertoDBP/Agentic/income-platform/documentation/implementation/

# Manually prepend CHANGELOG-patch.md content to CHANGELOG.md
# Manually append decisions-log-patch.md content to decisions-log.md
```

### Step 5 — Git Commit + Push

```bash
cd /Volumes/CH-DataOne/AlbertoDBP/Agentic/income-platform

git add documentation/
git commit -m "docs(agent-NN): [description] — DESIGN complete"
git push origin main
```

### Step 6 — Droplet Sync

```bash
ssh -i ~/.ssh/id_ed25519 root@138.197.78.238
cd /opt/Agentic/income-platform
git pull origin main
```

---

## Agent File Structure Rule (CRITICAL)

All agent source files must be inside `app/` subdirectory:

```
src/[service-name]/
├── app/
│   ├── __init__.py
│   ├── main.py
│   ├── config.py
│   ├── database.py
│   ├── models.py
│   ├── api/
│   │   ├── __init__.py
│   │   └── routes.py
│   └── [domain]/          ← domain logic (tax/, scoring/, etc.)
│       ├── __init__.py
│       └── *.py
├── scripts/
│   └── migrate.py         ← NOT Alembic. Run from service root.
├── tests/
│   └── test_*.py
├── Dockerfile
└── requirements.txt
```

**Never generate files flat in the service root.**

---

## Docker Patterns (CRITICAL — Learned from Agents 01-04)

### Python Version
Always use `FROM python:3.11-slim` — never 3.13 (numpy/psycopg2 incompatibility).

### Health Check — No curl
```yaml
healthcheck:
  test: ["CMD", "python3", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:PORT/health')"]
  interval: 30s
  timeout: 10s
  retries: 3
  start_period: 30s
```

### Build Context
- If service uses `src/shared/`: `context: .` (income-platform root), dockerfile path explicit
- If service is self-contained: `context: src/[service-name]`

### No Alembic
Use `scripts/migrate.py` only. Run from service root with `sys.path.insert(0, "..")`.

### Service Dependencies
```yaml
depends_on:
  [upstream-service]:
    condition: service_healthy
```

---

## Platform Architecture Summary

| Agent | Service | Port | Status |
|---|---|---|---|
| 01 | market-data-service | 8001 | ✅ Production |
| 02 | agent-02-newsletter-ingestion | 8002 | ✅ Production |
| 03 | income-scoring-service | 8003 | ✅ Production |
| 04 | asset-classification-service | 8004 | ✅ Production |
| 05 | tax-optimization-service | 8005 | 🔧 Develop Pending |

Infrastructure: DigitalOcean droplet (2 vCPU / 4GB RAM), managed PostgreSQL,
Valkey cache, Nginx reverse proxy + SSL at legatoinvest.com.

---

## Platform Principles

- **Capital preservation** — 70% safety threshold, veto power over yield-chasing
- **No silent blocking** — explicit user acknowledgment for overrides
- **Proposal-based** — Claude recommends, user approves, never auto-execute
- **Graceful degradation** — every upstream call has a fallback
- **Stateless compute** — agents calculate, don't store (unless explicitly designed to)

---

## Session Workflow Directives

| Command | Action |
|---|---|
| `Brainstorm` | Explore options, trade-offs, open questions |
| `DESIGN` | Architecture specs, schemas, API contracts |
| `Develop` | Implementation in Claude Code |
| `Summarize` | Consolidated decisions + handoff doc |
| `Review` | Gap analysis + validation checkpoint |
| `Document` | Execute this skill → generate files → TAR → download |
| `Quick Update` | Minor fix without full cycle |

---

## Skill Consolidation Note

This file replaces and supersedes:
- `/Agentic/SKILL/SKILL.md` (generic, outdated paths)
- `/Agentic/SKILL/platform-documentation-orchestrator-v2.md` (enhanced but generic)
- `/mnt/skills/user/platform-documentation-orchestrator/SKILL.md` (Claude Chat mount)

Those files can be archived or deleted. This `.claude/SKILL.md` is the single
canonical reference for the income-platform project.
