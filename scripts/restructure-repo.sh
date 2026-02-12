#!/usr/bin/env bash
# =============================================================================
# restructure-repo.sh
# Reorganizes AlbertoDBP/Agentic repo from single-skill layout to
# multi-skill income-platform structure.
#
# Run from repo root: bash scripts/restructure-repo.sh
# Safe: dry-run by default. Pass --execute to make real changes.
# =============================================================================

set -euo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
DRY_RUN=true

# Parse flags
for arg in "$@"; do
  case $arg in
    --execute) DRY_RUN=false ;;
    --help)
      echo "Usage: bash scripts/restructure-repo.sh [--execute]"
      echo "  Default: dry-run (shows what would happen)"
      echo "  --execute: performs actual git mv operations"
      exit 0 ;;
  esac
done

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info()    { echo -e "${BLUE}[INFO]${NC}  $1"; }
log_action()  { echo -e "${GREEN}[MV]${NC}    $1"; }
log_create()  { echo -e "${YELLOW}[CREATE]${NC} $1"; }
log_warn()    { echo -e "${RED}[WARN]${NC}  $1"; }

run() {
  if [ "$DRY_RUN" = true ]; then
    echo -e "  ${YELLOW}[DRY-RUN]${NC} $*"
  else
    eval "$@"
  fi
}

echo ""
echo "============================================================"
echo "  Agentic Repo Restructure — Income Platform Layout"
echo "  Mode: $([ "$DRY_RUN" = true ] && echo 'DRY RUN (safe)' || echo 'EXECUTE')"
echo "  Root: $REPO_ROOT"
echo "============================================================"
echo ""

cd "$REPO_ROOT"

# ------------------------------------------------------------------
# STEP 1: Verify preconditions
# ------------------------------------------------------------------
log_info "Step 1: Checking preconditions..."

if [ ! -d "SKILL" ]; then
  log_warn "SKILL/ directory not found. Are you running from repo root?"
  exit 1
fi

if [ ! -f "SKILL/SKILL.md" ]; then
  log_warn "SKILL/SKILL.md not found. Cannot proceed."
  exit 1
fi

# Check for uncommitted changes
if ! git diff --quiet 2>/dev/null || ! git diff --cached --quiet 2>/dev/null; then
  log_warn "Uncommitted changes detected. Commit or stash before restructuring."
  exit 1
fi

log_info "Preconditions OK."
echo ""

# ------------------------------------------------------------------
# STEP 2: Create new skills/ directory structure
# ------------------------------------------------------------------
log_info "Step 2: Creating skills/ directory structure..."

SKILL_DIRS=(
  "skills/platform-documentation-orchestrator"
  "skills/covered-call-income-advisor"
  "skills/forensic-accounting"
  "skills/saas-compensation-design"
  "skills/income-platform"
  "skills/income-platform/references"
)

for dir in "${SKILL_DIRS[@]}"; do
  if [ ! -d "$dir" ]; then
    log_create "$dir/"
    run "mkdir -p '$dir'"
  else
    log_info "$dir/ already exists — skipping"
  fi
done

echo ""

# ------------------------------------------------------------------
# STEP 3: Move SKILL/ → skills/platform-documentation-orchestrator/
# ------------------------------------------------------------------
log_info "Step 3: Moving SKILL/ → skills/platform-documentation-orchestrator/"
log_action "git mv SKILL/SKILL.md skills/platform-documentation-orchestrator/SKILL.md"
run "git mv SKILL/SKILL.md skills/platform-documentation-orchestrator/SKILL.md"

# Move any additional files in SKILL/ (future-proof)
if [ -d "SKILL" ]; then
  for f in SKILL/*; do
    fname=$(basename "$f")
    if [ "$fname" != "SKILL.md" ]; then
      log_action "git mv $f skills/platform-documentation-orchestrator/$fname"
      run "git mv '$f' 'skills/platform-documentation-orchestrator/$fname'"
    fi
  done
  log_action "rmdir SKILL/"
  run "git rm -r --ignore-unmatch SKILL/"
fi

echo ""

# ------------------------------------------------------------------
# STEP 4: Move references/ → skills/platform-documentation-orchestrator/references/
# ------------------------------------------------------------------
log_info "Step 4: Moving references/ → skills/platform-documentation-orchestrator/references/"

REF_FILES=(
  "repository-structure.md"
  "google-drive-setup.md"
  "documentation-standards.md"
  "testing-specification-patterns.md"
  "iteration-workflow.md"
  "mermaid-conventions.md"
)

run "mkdir -p skills/platform-documentation-orchestrator/references"

for f in "${REF_FILES[@]}"; do
  if [ -f "references/$f" ]; then
    log_action "git mv references/$f skills/platform-documentation-orchestrator/references/$f"
    run "git mv 'references/$f' 'skills/platform-documentation-orchestrator/references/$f'"
  else
    log_warn "references/$f not found — skipping"
  fi
done

# Any remaining files in references/
for f in references/*; do
  [ -f "$f" ] || continue
  fname=$(basename "$f")
  log_action "git mv $f skills/platform-documentation-orchestrator/references/$fname"
  run "git mv '$f' 'skills/platform-documentation-orchestrator/references/$fname'"
done

run "git rm -r --ignore-unmatch references/"
echo ""

# ------------------------------------------------------------------
# STEP 5: Move scripts/ → skills/platform-documentation-orchestrator/scripts/
# ------------------------------------------------------------------
log_info "Step 5: Moving scripts/ → skills/platform-documentation-orchestrator/scripts/"

run "mkdir -p skills/platform-documentation-orchestrator/scripts"

for f in scripts/*; do
  [ -f "$f" ] || continue
  fname=$(basename "$f")
  # Keep restructure-repo.sh at top-level scripts/
  if [ "$fname" = "restructure-repo.sh" ]; then
    log_info "Keeping scripts/restructure-repo.sh at repo root scripts/"
    continue
  fi
  log_action "git mv $f skills/platform-documentation-orchestrator/scripts/$fname"
  run "git mv '$f' 'skills/platform-documentation-orchestrator/scripts/$fname'"
done

echo ""

# ------------------------------------------------------------------
# STEP 6: Move docs/ → skills/platform-documentation-orchestrator/docs/
# ------------------------------------------------------------------
log_info "Step 6: Moving docs/ → skills/platform-documentation-orchestrator/docs/"

run "mkdir -p skills/platform-documentation-orchestrator/docs"

for f in docs/*; do
  [ -f "$f" ] || continue
  fname=$(basename "$f")
  log_action "git mv $f skills/platform-documentation-orchestrator/docs/$fname"
  run "git mv '$f' 'skills/platform-documentation-orchestrator/docs/$fname'"
done

run "git rm -r --ignore-unmatch docs/"
echo ""

# ------------------------------------------------------------------
# STEP 7: Create placeholder SKILL.md stubs for skills not yet uploaded
# ------------------------------------------------------------------
log_info "Step 7: Creating placeholder stubs for undeployed skills..."

create_stub() {
  local skill_dir="$1"
  local skill_name="$2"
  local description="$3"

  local stub_path="$skill_dir/SKILL.md"

  if [ -f "$stub_path" ]; then
    log_info "$stub_path already exists — skipping stub creation"
    return
  fi

  log_create "$stub_path (stub)"
  if [ "$DRY_RUN" = false ]; then
    cat > "$stub_path" << STUBEOF
---
name: $skill_name
description: $description
status: STUB — replace with full skill package
---

# $skill_name

> ⚠️ This is a placeholder stub. Upload the full skill package to replace this file.

## Skill Location

This skill was built in a Claude skill-creator session.
Upload the .skill package or paste the SKILL.md content here.

## Quick Reference

See the income-platform master skill at skills/income-platform/SKILL.md
for routing instructions and when to activate this skill.
STUBEOF
    git add "$stub_path"
  else
    echo -e "  ${YELLOW}[DRY-RUN]${NC} Would create stub: $stub_path"
  fi
}

create_stub \
  "skills/covered-call-income-advisor" \
  "covered-call-income-advisor" \
  "Strategic advisor for OTM covered call ETF portfolio construction, NAV preservation, tax optimization (Section 1256, ROC), and income barbell framework. Activate for ETF screening, portfolio construction, tax analysis, and platform architecture guidance."

create_stub \
  "skills/forensic-accounting" \
  "forensic-accounting" \
  "7-step GAAP-compliant forensic analysis for SaaS and master distributor companies. Covers ASC 606 revenue recognition, journal entry red flags, balance sheet scrutiny, and correcting entries. Activate for ETF issuer due diligence and vendor financial vetting."

create_stub \
  "skills/saas-compensation-design" \
  "saas-compensation-design" \
  "SaaS sales compensation plan design and optimization. Covers quota allocation, variable pay structures, SVP/AE/SDR plan modeling, and structural misalignment diagnosis. Activate for compensation plan reviews and redesigns."

echo ""

# ------------------------------------------------------------------
# STEP 8: Create income-platform master skill
# ------------------------------------------------------------------
log_info "Step 8: Creating income-platform master skill..."

MASTER_SKILL="skills/income-platform/SKILL.md"
if [ -f "$MASTER_SKILL" ]; then
  log_info "$MASTER_SKILL already exists — skipping"
else
  log_create "$MASTER_SKILL"
  if [ "$DRY_RUN" = false ]; then
    cat > "$MASTER_SKILL" << 'MASTEREOF'
---
name: income-platform
description: Master routing skill for the income-platform agentic project. Routes tasks to the correct domain skill(s) based on task intent. Activate this skill first for any income-platform session to load platform-wide context, then follow routing instructions to co-activate domain skills. Covers covered call ETF strategy, platform architecture, financial due diligence, UI/dashboards, and skill evolution.
---

# Income Platform — Master Router

Entry point for all income-platform sessions. Read this first, then activate the domain skills listed for your task.

## Platform Overview

The income-platform is a multi-layer agentic system for generating consistent income through covered call ETF strategies while preserving principal and optimizing tax efficiency. It consists of:

- **Financial Intelligence Engine** — ETF screening, portfolio construction, tax optimization
- **Platform Architecture Layer** — Documentation, specs, ADRs, code scaffolds
- **UI/Dashboard Layer** — Dashboards, reports, client-facing artifacts
- **Data Integration Layer** — MCP servers, API connections, market data feeds

## Skill Routing Table

| Task | Primary Skill | Co-Activate |
|------|--------------|-------------|
| ETF evaluation & screening | covered-call-income-advisor | forensic-accounting |
| Portfolio construction & rebalancing | covered-call-income-advisor | xlsx |
| Tax optimization analysis | covered-call-income-advisor | docx |
| NAV erosion detection | covered-call-income-advisor | — |
| Architecture design & ADRs | platform-documentation-orchestrator | doc-coauthoring |
| Implementation specs + testing | platform-documentation-orchestrator | — |
| Dashboard / UI build | web-artifacts-builder | frontend-design, theme-factory |
| Data API / MCP integration | mcp-builder | platform-documentation-orchestrator |
| ETF issuer due diligence | forensic-accounting | covered-call-income-advisor |
| Investor reports & decks | pptx | theme-factory |
| Portfolio tracker spreadsheet | xlsx | covered-call-income-advisor |
| Strategy memos & reports | docx | theme-factory |
| Skill refinement or creation | skill-creator | covered-call-income-advisor |
| Voice agent integration | [build: voice-agent-integration] | mcp-builder |
| Multi-agent qualifying platform | [build: multi-agent-qualifying] | mcp-builder |

## Platform-Wide Principles

### Financial Layer
- **Preservation first**: NAV preservation > tax efficiency > yield > risk
- **OTM only**: Covered call strategies must use Out-of-the-Money strikes (10-30% upside capture)
- **Target yield**: 12-18% APY through diversified covered call strategies
- **Tax priority**: Section 1256 (60/40) and ROC distributions preferred over ordinary income

### Architecture Layer
- Testing specifications integrated into implementation specs — tests planned before coding
- All diagrams in Mermaid format (version-controllable)
- CHANGELOG and ADRs maintained via automated scripts
- Google Drive as documentation collaboration layer

### Development Standards
- Skills stored at: `/Volumes/CH-DataOne/AlbertoDBP/Agentic/skills/` (local)
- GitHub repo: `https://github.com/AlbertoDBP/Agentic`
- Every skill has its own subdirectory with SKILL.md at root
- Reference files live in skill's `references/` subdirectory

## Account Structure Context

When doing financial analysis, the platform operates across:
- **IRA/401k accounts**: Prioritize yield; tax treatment deferred
- **Roth accounts**: Prioritize growth-income hybrids; tax-free compounding
- **Taxable accounts**: Prioritize Section 1256 and ROC distributions to minimize tax drag

## Skills Registry

See `references/skills-registry.md` for full skill inventory with deployment status.

## Quick Activation Patterns

**Single domain task:**
> "Using covered-call-income-advisor, evaluate JEPQ for my taxable account"

**Multi-domain task:**
> "Using covered-call-income-advisor AND platform-documentation-orchestrator,
>  design the ETF screening module with functional specs"

**Full platform context:**
> "Using the income-platform skill, [describe task]"
> Claude will route to the correct skill(s) automatically
MASTEREOF
    git add "$MASTER_SKILL"
  else
    echo -e "  ${YELLOW}[DRY-RUN]${NC} Would create: $MASTER_SKILL"
  fi
fi

echo ""

# ------------------------------------------------------------------
# STEP 9: Create skills registry reference
# ------------------------------------------------------------------
log_info "Step 9: Creating skills/income-platform/references/skills-registry.md..."

REGISTRY="skills/income-platform/references/skills-registry.md"
if [ "$DRY_RUN" = false ] && [ ! -f "$REGISTRY" ]; then
  cat > "$REGISTRY" << 'REGEOF'
# Income Platform — Skills Registry

Last updated: 2026-02-10

## User Skills (custom — /skills/)

| Skill | Status | Location | Built |
|-------|--------|----------|-------|
| income-platform | ✅ Active | skills/income-platform/ | 2026-02-10 |
| platform-documentation-orchestrator | ✅ Active | skills/platform-documentation-orchestrator/ | 2026-01-18 |
| covered-call-income-advisor | ⚠️ Stub — upload package | skills/covered-call-income-advisor/ | 2026-01-18 |
| forensic-accounting | ⚠️ Stub — upload package | skills/forensic-accounting/ | 2026-01-06 |
| saas-compensation-design | ⚠️ Stub — upload package | skills/saas-compensation-design/ | TBD |

## Skills To Build (next sprint)

| Skill | Purpose | Priority |
|-------|---------|----------|
| voice-agent-integration | Twilio + Deepgram + ElevenLabs patterns | High |
| multi-agent-qualifying-platform | 5-module qualifying agent architecture | High |

## Example Skills (Anthropic-provided)

| Skill | Use Case |
|-------|---------|
| skill-creator | Build and iterate skills |
| web-artifacts-builder | Dashboards and UI components |
| mcp-builder | API/data integration |
| doc-coauthoring | Collaborative spec writing |
| theme-factory | Visual branding for artifacts |

## Public Skills (Anthropic format output)

| Skill | Use Case |
|-------|---------|
| docx | Word docs, reports, memos |
| xlsx | Spreadsheets, portfolio trackers |
| pptx | Decks, presentations |
| pdf | Final client deliverables |
| frontend-design | UI quality elevation |
REGEOF
  git add "$REGISTRY"
  log_create "$REGISTRY"
else
  [ "$DRY_RUN" = true ] && echo -e "  ${YELLOW}[DRY-RUN]${NC} Would create: $REGISTRY"
fi

echo ""

# ------------------------------------------------------------------
# STEP 10: Update root README.md
# ------------------------------------------------------------------
log_info "Step 10: Updating root README.md..."

if [ "$DRY_RUN" = false ]; then
  cat > "README.md" << 'READMEEOF'
# Agentic Development Platform

Income-platform skills repository for AI agentic development with Claude.

## Repository Structure

```
Agentic/
├── skills/                                          # All Claude skills
│   ├── income-platform/                             # ← START HERE (master router)
│   │   ├── SKILL.md
│   │   └── references/
│   │       └── skills-registry.md
│   │
│   ├── platform-documentation-orchestrator/         # Architecture & docs
│   │   ├── SKILL.md
│   │   ├── references/
│   │   ├── scripts/
│   │   └── docs/
│   │
│   ├── covered-call-income-advisor/                 # ETF strategy & portfolio
│   │   └── SKILL.md  (+ references/ when uploaded)
│   │
│   ├── forensic-accounting/                         # Financial due diligence
│   │   └── SKILL.md  (+ references/ when uploaded)
│   │
│   └── saas-compensation-design/                    # Sales comp modeling
│       └── SKILL.md  (+ references/ when uploaded)
│
└── scripts/
    └── restructure-repo.sh                          # This script
```

## Quick Start

Tell Claude:
> "Using the income-platform skill from github.com/AlbertoDBP/Agentic,
>  [describe your task]"

Claude will read the master router and activate the correct domain skill(s).

## Skills Registry

See `skills/income-platform/references/skills-registry.md` for full inventory.

## GitHub

https://github.com/AlbertoDBP/Agentic
READMEEOF
  git add README.md
  log_action "Updated README.md"
else
  echo -e "  ${YELLOW}[DRY-RUN]${NC} Would update README.md"
fi

echo ""

# ------------------------------------------------------------------
# STEP 11: Summary
# ------------------------------------------------------------------
echo "============================================================"
echo "  Restructure $([ "$DRY_RUN" = true ] && echo 'PREVIEW' || echo 'COMPLETE')"
echo "============================================================"
echo ""
echo "  Changes made:"
echo "  • SKILL/          → skills/platform-documentation-orchestrator/"
echo "  • references/     → skills/platform-documentation-orchestrator/references/"
echo "  • scripts/        → skills/platform-documentation-orchestrator/scripts/"
echo "  • docs/           → skills/platform-documentation-orchestrator/docs/"
echo "  • Created:          skills/income-platform/SKILL.md (master router)"
echo "  • Created:          skills/income-platform/references/skills-registry.md"
echo "  • Created stubs:    covered-call-income-advisor, forensic-accounting,"
echo "                      saas-compensation-design"
echo "  • Updated:          README.md"
echo ""

if [ "$DRY_RUN" = true ]; then
  echo -e "  ${YELLOW}This was a DRY RUN. No changes were made.${NC}"
  echo "  Run with --execute to apply:"
  echo "  bash scripts/restructure-repo.sh --execute"
else
  echo -e "  ${GREEN}All changes staged. Review then commit:${NC}"
  echo ""
  echo "  git status"
  echo "  git diff --cached --stat"
  echo "  git commit -m 'restructure: reorganize into multi-skill income-platform layout'"
  echo "  git push origin main"
fi
echo ""
