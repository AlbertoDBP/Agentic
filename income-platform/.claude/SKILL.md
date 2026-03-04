# Income Fortress Platform — Documentation Orchestrator
## Project-Specific Skill for Claude Chat + Claude Code

**Version:** 2.1.0
**Last Updated:** 2026-03-04
**Canonical Location:** `income-platform/.claude/SKILL.md`
**Replaces:** SKILL/SKILL.md, SKILL/platform-documentation-orchestrator-v2.md,
             /mnt/skills/user/platform-documentation-orchestrator/SKILL.md

---

## Purpose

This skill governs how Claude generates, updates, and packages documentation for the
Income Fortress Platform. It is the **single source of truth** for documentation
workflow — used in both Claude Chat (claude.ai) and Claude Code (VS Code).

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

## Live Documentation Files (Read Before Updating)

These files must be **fetched and read** at the start of every Document phase.
Never work from memory — always read the current state first.

| File | Purpose | How to Get Current Content |
|---|---|---|
| `documentation/CHANGELOG.md` | Platform version history | Ask user to `cat` on droplet, or read from uploaded file |
| `documentation/decisions-log.md` | All ADRs consolidated | Ask user to `cat` on droplet, or read from uploaded file |
| `documentation/index.md` | Master agent status | Ask user to `cat` on droplet if agent status update needed |

**In Claude Chat:** Ask the user to paste the content if not already in context.
**In Claude Code:** Read directly via file tools from Mac project root.

When generating updated versions of these files, always produce the **complete file**
— never produce patch files or partial content. The user replaces the file entirely.

---

## Documentation Folder Structure (Actual)

```
income-platform/
├── .claude/
│   └── SKILL.md                          ← THIS FILE
├── documentation/
│   ├── CHANGELOG.md                      ← Full platform changelog (replace on update)
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
│   ├── index.md                          ← Master navigation + agent status
│   ├── reference-architecture.md
│   ├── decisions-log.md                  ← ALL ADRs consolidated (replace on update)
│   ├── architecture/                     ← Architecture docs + diagrams
│   ├── functional/                       ← One .md per agent/component
│   ├── implementation/                   ← Implementation specs
│   ├── deployment/                       ← Deployment guides
│   ├── testing/                          ← Test matrices
│   ├── diagrams/                         ← Mermaid .mmd files
│   └── archive/                          ← Deprecated docs
└── src/
    ├── market-data-service/              ← Agent 01
    ├── agent-02-newsletter-ingestion/    ← Agent 02
    ├── income-scoring-service/           ← Agent 03
    ├── asset-classification-service/     ← Agent 04
    ├── tax-optimization-service/         ← Agent 05
    └── shared/                           ← Shared modules (asset_class_detector)
```

---

## Naming Conventions

| Document Type | Pattern | Example |
|---|---|---|
| Agent functional spec | `agent-NN-[name]-functional-spec.md` | `agent-05-tax-optimization-functional-spec.md` |
| Agent implementation spec | `agent-NN-[name]-implementation-spec.md` | `agent-05-tax-optimization-implementation-spec.md` |
| ADR standalone file | `ADR-NNN-[slug].md` in `functional/` | `ADR-007-agent05-portfolio-scope.md` |
| ADR consolidated entry | Section in `decisions-log.md` | `### ADR-007: ...` |
| Service changelog | `CHANGELOG-[service-name].md` | `CHANGELOG-tax-optimization-service.md` |

---

## ADR Conventions

ADRs are maintained in **two places** — always update both:

1. **Standalone file** → `documentation/functional/ADR-NNN-[slug].md`
2. **Consolidated entry** → appended to `documentation/decisions-log.md` ADR Index table + full section

### Current ADR Registry

| ADR | Title | Status |
|---|---|---|
| ADR-001 | Post-Scoring LLM Explanation Layer | ✅ Accepted |
| ADR-002 | NAV Erosion Calculation for Covered Call ETFs | ✅ Accepted |
| ADR-003 | ROC Tax Efficiency Tracking | ✅ Accepted |
| ADR-004 | Granular SAIS Curves (5-Zone Scoring) | ✅ Accepted |
| ADR-005 | Profile-Driven Circuit Breaker Auto-Enable | ✅ Accepted |
| ADR-006 | Preference-Based Configuration System | ✅ Accepted |
| ADR-007 | Agent 05 Portfolio Data Scope Deferral | ✅ Accepted |
| ADR-008 | Celery Queue Specialization (6 Queues) | ✅ Accepted |
| ADR-009 | Structured JSON Logging | ✅ Accepted |
| ADR-010 | Manual Tax Breakdown Mapping (Short-Term) | ✅ Accepted (Interim) |

**Next ADR number: ADR-011**

---

## CHANGELOG Format

File: `documentation/CHANGELOG.md`
Versioning: Semantic — `[MAJOR.MINOR.PATCH] — YYYY-MM-DD — [Title]`

Current version: **0.4.0** (Agent 05 Design Complete — 2026-03-04)
Next version: **0.5.0** (Agent 05 Develop Complete)

```markdown
## [Unreleased]

### Planned
- [next planned item]

---

## [0.5.0] — YYYY-MM-DD — [Title]

### Added
- **Agent NN — [Name]**: [description]
```

---

## Platform Architecture — Current State

| Agent | Service Directory | Port | Status |
|---|---|---|---|
| 01 | `src/market-data-service` | 8001 | ✅ Production |
| 02 | `src/agent-02-newsletter-ingestion` | 8002 | ✅ Production |
| 03 | `src/income-scoring-service` | 8003 | ✅ Production |
| 04 | `src/asset-classification-service` | 8004 | ✅ Production |
| 05 | `src/tax-optimization-service` | 8005 | 🔧 Develop Pending |

Infrastructure: DigitalOcean droplet (2 vCPU / 4GB RAM) at `138.197.78.238`,
managed PostgreSQL, Valkey cache, Nginx + SSL at `legatoinvest.com`.

**Update this table in SKILL.md whenever an agent status changes.**

---

## Document Phase — Full Workflow

When user says **"Document"**, execute this exact sequence:

### Step 1 — Read Live Files First (CRITICAL)

Before generating anything, ensure you have the current content of:
- `documentation/CHANGELOG.md`
- `documentation/decisions-log.md`

If not already in context, ask:
> "Before I generate the documentation package, I need the current content of
> CHANGELOG.md and decisions-log.md. Please run on the droplet:
> `cat /opt/Agentic/income-platform/documentation/CHANGELOG.md`
> `cat /opt/Agentic/income-platform/documentation/decisions-log.md`"

### Step 2 — Generate All Files

Create files in `/home/claude/[agent-NN]-docs/` matching the exact repo structure:

```
[agent-NN]-docs/
├── .claude/
│   └── SKILL.md                          ← Updated SKILL.md (if changed)
└── documentation/
    ├── CHANGELOG.md                      ← COMPLETE updated file (not a patch)
    ├── decisions-log.md                  ← COMPLETE updated file (not a patch)
    ├── functional/
    │   ├── agent-NN-[name]-functional-spec.md
    │   └── ADR-NNN-[slug].md             ← If new ADR this session
    └── implementation/
        └── agent-NN-[name]-implementation-spec.md
```

**Always produce complete replacement files for CHANGELOG.md and decisions-log.md.**
Never produce patch files, diff files, or partial content for these two files.

### Step 3 — Package as TAR

```bash
cd /home/claude
tar -czf agent-NN-[name]-documentation.tar.gz [agent-NN]-docs/
cp agent-NN-[name]-documentation.tar.gz /mnt/user-data/outputs/
```

Verify TAR contents with `tar -tzf` before presenting.

### Step 4 — Present for Download

Call `present_files` with `/mnt/user-data/outputs/[tarfile]`.

### Step 5 — Mac Extraction + File Placement

User downloads TAR to `/Volumes/CH-DataOne/AlbertoDBP/Downloads/`

```bash
# Extract
cd /Volumes/CH-DataOne/AlbertoDBP/Downloads
tar -xzf agent-NN-[name]-documentation.tar.gz

# Copy entire structure into project (replaces existing files)
cp -r [agent-NN]-docs/. \
   /Volumes/CH-DataOne/AlbertoDBP/Agentic/income-platform/
```

### Step 6 — Git Commit + Push

```bash
cd /Volumes/CH-DataOne/AlbertoDBP/Agentic/income-platform

git add .
git commit -m "docs(agent-NN): [description] — DESIGN complete"

# If push is rejected (remote has newer commits):
git pull origin main --rebase
git push origin main
```

### Step 7 — Droplet Sync

```bash
ssh -i ~/.ssh/id_ed25519 root@138.197.78.238
cd /opt/Agentic/income-platform && git pull origin main
```

---

## Updating SKILL.md Itself

When any of the following change, update this file and include it in the TAR:

| Trigger | What to Update |
|---|---|
| New agent deployed to production | Platform Architecture table — change status to ✅ Production |
| New agent design started | Platform Architecture table — add row with 🔧 status |
| New ADR created | ADR Registry table + Next ADR number |
| New CHANGELOG version released | Current version + Next version fields |
| New src/ service directory created | Documentation Folder Structure tree |
| Path changes (Mac, droplet, etc.) | Project Paths table |

---

## Agent File Structure Rule (CRITICAL)

All agent source files must be inside `app/` subdirectory. Never flat in service root.

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
│   └── [domain]/
│       ├── __init__.py
│       └── *.py
├── scripts/
│   └── migrate.py         ← NOT Alembic. sys.path.insert(0, "..") at top.
├── tests/
│   ├── __init__.py
│   └── test_*.py
├── Dockerfile
└── requirements.txt
```

---

## Docker Patterns (CRITICAL — Learned from Agents 01–04)

### Python Version
Always `FROM python:3.11-slim` — never 3.13 (numpy/psycopg2 incompatible).

### Health Check — No curl (not installed in slim images)
```yaml
healthcheck:
  test: ["CMD", "python3", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:PORT/health')"]
  interval: 30s
  timeout: 10s
  retries: 3
  start_period: 30s
```

### Build Context Rules
- Service uses `src/shared/` → `context: .` (income-platform root), explicit dockerfile path
- Self-contained service → `context: src/[service-name]`

### No Alembic
`scripts/migrate.py` only. Always: `sys.path.insert(0, "..")` at top of file.

### Stale Container Cache
If rebuilt container still shows old behavior:
```bash
docker rmi [image-name] --force
docker compose build --no-cache [service]
docker compose up -d --force-recreate [service]
```

---

## Platform Principles

- **Capital preservation** — 70% safety threshold, veto power over yield-chasing
- **No silent blocking** — explicit user acknowledgment for all overrides
- **Proposal-based** — Claude recommends, user approves, never auto-execute
- **Graceful degradation** — every upstream call has a defined fallback
- **Stateless compute** — agents calculate, don't store (unless explicitly designed to)
- **Conservative fallback** — when upstream unavailable, flag it, never fail silently

---

## Session Workflow Directives

| Command | Action | Produces |
|---|---|---|
| `Brainstorm` | Explore options, trade-offs, open questions | Approaches + trade-off analysis |
| `DESIGN` | Architecture specs, schemas, API contracts | Diagrams, specs, component designs |
| `Develop` | Handoff to Claude Code for implementation | Working code + configs |
| `Summarize` | Consolidated decisions + handoff doc | Decision log + implementation notes |
| `Review` | Gap analysis + validation checkpoint | Checklist + open questions resolved |
| `Document` | Execute this skill — generate TAR | Files ready for download + git |
| `Quick Update` | Minor fix without full cycle | Updated specific file only |

---

## Claude Chat vs Claude Code — Tool Differences

### Claude Chat (claude.ai)
- ✅ Has `bash_tool`, `create_file`, `present_files` — use for Document phase
- ✅ Strategic planning, Brainstorm, DESIGN, Review, Summarize
- ❌ Cannot access Mac filesystem directly
- ❌ Cannot read private GitHub repo (authentication required)
- **Workflow:** Generate files → TAR → present_files → user downloads → user extracts + commits

### Claude Code (VS Code)
- ✅ Direct Mac filesystem access — can read/write project files
- ✅ Can run `git` commands directly
- ✅ Develop phase — implementation
- ✅ Can read `.claude/SKILL.md` automatically at session start
- **Workflow:** Read existing files → modify in place → git add/commit/push directly

---

## Skill Consolidation Note

This file is the **single canonical reference** for income-platform documentation.

Supersedes and replaces:
- `/Agentic/SKILL/SKILL.md` (generic, outdated paths — archive or delete)
- `/Agentic/SKILL/platform-documentation-orchestrator-v2.md` (archive or delete)
- `/mnt/skills/user/platform-documentation-orchestrator/SKILL.md` (Claude Chat mount — keep for trigger, but this file governs)
