# Documentation Update Scripts - Quick Start Guide

**Complete automation for keeping documentation in sync with design and development**

---

## 🚀 Quick Start

### 1. Initial Setup (One-Time)

```bash
# After cloning/extracting the repository
cd income-platform

# Make scripts executable
chmod +x scripts/update-documentation.sh
chmod +x scripts/validate-documentation.py

# Validate everything works
python3 scripts/validate-documentation.py
```

---

## 📝 Common Workflows

### Workflow 1: Design Changed

**When**: You update a component's design (architecture, interfaces, features)

```bash
./scripts/update-documentation.sh --design-change agent-03-income-scoring
```

**What happens**:
1. ✅ Prompts you for change description
2. ✅ Offers to update functional/implementation specs
3. ✅ Updates CHANGELOG.md automatically
4. ✅ Asks if it's a significant decision → Creates ADR if yes
5. ✅ Prompts for diagram updates (system, data model, etc.)
6. ✅ Validates all documentation
7. ✅ Offers to commit and push to GitHub

**Time**: ~2-5 minutes (depending on how much detail you add)

---

### Workflow 2: Development Complete

**When**: You finish implementing a component and want to update docs

```bash
./scripts/update-documentation.sh --dev-complete agent-01-market-data-sync
```

**What happens**:
1. ✅ Updates index.md status: ⏳ Pending → ✅ Complete
2. ✅ Adds entry to CHANGELOG.md
3. ✅ Prompts for README updates (new capabilities, setup steps)
4. ✅ Validates documentation
5. ✅ Offers to commit and push

**Time**: ~1-2 minutes

---

### Workflow 3: Before Pushing to GitHub

**When**: You made doc changes and want to ensure everything is valid before pushing

```bash
# Validate first
python3 scripts/validate-documentation.py --strict

# If validation passes, sync and commit
./scripts/update-documentation.sh --full-sync --auto-commit
```

**What happens**:
1. ✅ Scans for all documentation changes
2. ✅ Runs comprehensive validation
3. ✅ Updates version numbers
4. ✅ Commits all changes with generated message
5. ✅ Pushes to GitHub

**Time**: ~1 minute

---

## 🎯 Specific Scenarios

### Scenario: Added New Feature to Existing Agent

```bash
# 1. Update the component spec
./scripts/update-documentation.sh --design-change agent-03-income-scoring

# When prompted:
# - Change description: "Added SHAP explainability to income scoring"
# - Update functional spec? Yes
# - Significant decision? Yes
#   - Decision title: "Add SHAP for Explainability"
#   - Rationale: "Users need to understand score factors"
# - Update diagrams? No (no architecture change)

# 2. Validate
python3 scripts/validate-documentation.py
```

---

### Scenario: Completed Agent Implementation

```bash
# 1. Mark as complete
./scripts/update-documentation.sh --dev-complete agent-01-market-data-sync

# 2. Update API docs (if FastAPI service)
# - Ensure docstrings are up-to-date
# - OpenAPI spec auto-generated at /docs endpoint

# 3. Full sync and push
./scripts/update-documentation.sh --full-sync --auto-commit
```

---

### Scenario: Weekly Documentation Review

```bash
# Every Friday before week-end

# 1. Validate everything
python3 scripts/validate-documentation.py --strict > validation-report.txt

# 2. Review report
cat validation-report.txt

# 3. Fix any issues
# - Broken links
# - Missing frontmatter
# - Inconsistent naming

# 4. Sync and push
./scripts/update-documentation.sh --full-sync --auto-commit
```

---

### Scenario: Major Architecture Change

```bash
# Example: Switching from n8n-only to hybrid orchestration

# 1. Update architecture docs manually
# Edit docs/architecture/reference-architecture.md
# Edit docs/diagrams/system-architecture.mmd

# 2. Document the decision
./scripts/update-documentation.sh --design-change orchestration-layer

# When prompted:
# - Change: "Switched to hybrid orchestration (n8n + Prefect)"
# - Update specs? Yes (update all affected agents)
# - Significant decision? YES
#   - Decision: "Hybrid Orchestration Strategy"
#   - Rationale: "n8n for integrations, Prefect for ML pipelines..."
# - Update diagrams? Already done

# 3. Update affected components
for agent in agent-01 agent-03 agent-11; do
    ./scripts/update-documentation.sh --design-change $agent --non-interactive
done

# 4. Validate and push
python3 scripts/validate-documentation.py --strict
./scripts/update-documentation.sh --full-sync --auto-commit
```

---

## 🔧 Advanced Usage

### Non-Interactive Mode (CI/CD)

```bash
# For automated pipelines
./scripts/update-documentation.sh \
    --design-change agent-05 \
    --non-interactive \
    --auto-commit
```

### Dry Run (Preview Changes)

```bash
# See what would change without actually changing anything
./scripts/update-documentation.sh --full-sync --dry-run
```

### Auto-Fix Validation Issues

```bash
# Automatically fix issues where possible
python3 scripts/validate-documentation.py --fix
```

---

## 📋 Cheat Sheet

| Task | Command |
|------|---------|
| Design changed | `./scripts/update-documentation.sh --design-change <component>` |
| Dev complete | `./scripts/update-documentation.sh --dev-complete <component>` |
| Full sync | `./scripts/update-documentation.sh --full-sync` |
| Validate | `python3 scripts/validate-documentation.py` |
| Validate strict | `python3 scripts/validate-documentation.py --strict` |
| Auto-fix | `python3 scripts/validate-documentation.py --fix` |
| Dry run | `./scripts/update-documentation.sh --full-sync --dry-run` |
| Auto-commit | `./scripts/update-documentation.sh --full-sync --auto-commit` |

---

## 🎨 What Gets Updated Automatically

### CHANGELOG.md
```markdown
## [Unreleased]

### Added
- **Agent 3**: New SHAP explainability feature

### Changed
- **Architecture**: Switched to hybrid orchestration
```

### decisions-log.md
```markdown
## ADR-006: Add SHAP Explainability

**Date**: 2026-01-23
**Status**: Accepted
**Component**: Agent 3 (Income Scoring)

[Full ADR with context, decision, consequences]
```

### docs/index.md
```markdown
| Agent 3 | [Income Scoring](functional/agent-03-income-scoring.md) | ✅ Complete |
```
(Status updated from ⏳ Pending or 🚧 In Progress)

---

## ✅ Best Practices

### DO

✅ **Run scripts after each design meeting**
```bash
./scripts/update-documentation.sh --design-change <component>
```

✅ **Validate before committing**
```bash
python3 scripts/validate-documentation.py --strict
git add .
git commit -m "docs: update agent-03 specification"
```

✅ **Use --dry-run to preview**
```bash
./scripts/update-documentation.sh --full-sync --dry-run
# Review output
./scripts/update-documentation.sh --full-sync  # Actually run
```

✅ **Document significant decisions as ADRs**
- Answer "yes" when prompted about significant decisions
- Provide clear rationale
- List alternatives considered

✅ **Keep diagrams up-to-date**
- When prompted about diagrams, actually update them
- Mermaid files in `docs/diagrams/*.mmd`

### DON'T

❌ **Don't skip validation**
```bash
# Bad: Commit without validating
git commit -am "updated docs"

# Good: Validate first
python3 scripts/validate-documentation.py
git commit -am "docs: update agent specs"
```

❌ **Don't manually edit CHANGELOG without script**
- Let the script handle it for consistency
- Manual edits okay for releases

❌ **Don't use --auto-commit without reviewing**
```bash
# Bad: Blind auto-commit
./scripts/update-documentation.sh --full-sync --auto-commit

# Good: Review first
./scripts/update-documentation.sh --full-sync --dry-run
./scripts/update-documentation.sh --full-sync  # Review git diff
git push
```

---

## 🐛 Troubleshooting

### "Permission denied" when running scripts

```bash
chmod +x scripts/update-documentation.sh
chmod +x scripts/validate-documentation.py
```

### Validation fails on valid docs

Check for:
1. Missing frontmatter in specs (Version, Date, Status, Priority)
2. Broken relative links
3. Mermaid diagrams without ```mermaid code fences
4. Inconsistent component naming (Agent 3 vs Agent 03)

### Git conflicts after auto-commit

```bash
# Pull latest first
git pull origin main

# Then run script
./scripts/update-documentation.sh --full-sync --auto-commit
```

### Script can't find files

```bash
# Make sure you're in project root
cd /path/to/income-platform

# Or run from anywhere with full path
/path/to/income-platform/scripts/update-documentation.sh --full-sync
```

---

## 📚 More Information

- **Detailed docs**: See [scripts/README.md](scripts/README.md)
- **Script source**: See [scripts/update-documentation.sh](scripts/update-documentation.sh)
- **Validation logic**: See [scripts/validate-documentation.py](scripts/validate-documentation.py)
- **Templates**: See [scripts/templates/](scripts/templates/)

---

## 🔄 Typical Day-to-Day Usage

**Morning** (after standup):
```bash
# Sync with latest changes
git pull origin main

# Validate documentation
python3 scripts/validate-documentation.py
```

**During development**:
```bash
# When design changes
./scripts/update-documentation.sh --design-change <component>

# When implementation complete
./scripts/update-documentation.sh --dev-complete <component>
```

**Before leaving** (end of day):
```bash
# Full sync and push
./scripts/update-documentation.sh --full-sync --auto-commit
```

**Weekly** (Friday):
```bash
# Comprehensive validation
python3 scripts/validate-documentation.py --strict

# Review CHANGELOG and ADRs
cat docs/CHANGELOG.md
cat docs/decisions-log.md
```

---

**Happy Documenting! 🎉**

*These scripts save 10-20 minutes per documentation update and ensure consistency across the entire platform.*
