# Documentation Automation Scripts

This directory contains scripts to automate documentation updates and validation for the Tax-Efficient Income Investment Platform.

## Scripts Overview

| Script | Purpose | Usage |
|--------|---------|-------|
| `update-documentation.sh` | Orchestrate doc updates after design/dev changes | `./update-documentation.sh --design-change agent-3` |
| `validate-documentation.py` | Validate docs for completeness and consistency | `python validate-documentation.py` |
| `templates/` | Templates for generating new documentation | Used by update-documentation.sh |

---

## update-documentation.sh

**Main documentation update orchestrator** - automates the workflow for keeping documentation synchronized with design changes and development progress.

### Features

- ✅ Updates CHANGELOG.md automatically
- ✅ Creates/updates Architecture Decision Records (ADRs)
- ✅ Updates component status in index.md
- ✅ Prompts for diagram updates
- ✅ Validates documentation after changes
- ✅ Commits and pushes to GitHub (optional)

### Usage

#### Design Change
```bash
# When you update a component's design
./scripts/update-documentation.sh --design-change agent-03-income-scoring

# What it does:
# 1. Prompts for change description
# 2. Updates functional/implementation specs
# 3. Adds entry to CHANGELOG.md
# 4. Optionally creates ADR in decisions-log.md
# 5. Prompts for diagram updates
# 6. Validates all documentation
# 7. Offers to commit and push to GitHub
```

#### Development Complete
```bash
# When you finish implementing a component
./scripts/update-documentation.sh --dev-complete agent-01-market-data-sync

# What it does:
# 1. Updates index.md status to ✅ Complete
# 2. Adds entry to CHANGELOG.md
# 3. Prompts for README updates
# 4. Validates documentation
# 5. Offers to commit and push
```

#### Full Sync
```bash
# Sync all documentation and push to GitHub
./scripts/update-documentation.sh --full-sync --auto-commit

# What it does:
# 1. Scans for all documentation changes
# 2. Runs comprehensive validation
# 3. Updates version numbers
# 4. Commits all changes
# 5. Pushes to GitHub (if --auto-commit)
```

### Options

```
--design-change COMPONENT    Update docs after design change
--dev-complete COMPONENT     Update docs after development completion  
--full-sync                  Full documentation sync and validation

--auto-commit               Automatically commit without prompting
--non-interactive           Run without user prompts (uses defaults)
--dry-run                   Show what would be done without changes

-h, --help                  Show detailed help
```

### Examples

```bash
# Interactive design change (prompts for details)
./scripts/update-documentation.sh --design-change agent-05-tax-optimization

# Non-interactive development completion (no prompts)
./scripts/update-documentation.sh --dev-complete agent-11-alerts --non-interactive

# Dry run to preview changes
./scripts/update-documentation.sh --full-sync --dry-run

# Full sync with automatic commit
./scripts/update-documentation.sh --full-sync --auto-commit
```

### Workflow Integration

**After design meetings:**
```bash
# Document design decisions immediately
./scripts/update-documentation.sh --design-change <component>
# Answer prompts about what changed and why
# Creates ADR if it's a significant decision
```

**During development:**
```bash
# When you finish a component
./scripts/update-documentation.sh --dev-complete <component>
# Updates status, adds to changelog
```

**Before releases:**
```bash
# Validate and sync everything
./scripts/update-documentation.sh --full-sync --auto-commit
# Ensures all docs are up-to-date and consistent
```

---

## validate-documentation.py

**Documentation validation and quality checks** - ensures documentation is complete, consistent, and follows standards.

### Features

- ✅ Checks for required files (README, index, architecture docs)
- ✅ Validates Markdown formatting and structure
- ✅ Detects broken internal links
- ✅ Validates Mermaid diagram syntax
- ✅ Checks for language identifiers in code blocks
- ✅ Ensures consistent naming and terminology
- ✅ Verifies frontmatter in specifications

### Usage

#### Basic Validation
```bash
# Validate all documentation from project root
python scripts/validate-documentation.py .

# Validate from docs directory
cd docs
python ../scripts/validate-documentation.py ..
```

#### Strict Mode
```bash
# Fail on warnings (not just errors)
python scripts/validate-documentation.py --strict

# Useful in CI/CD pipelines
```

#### Auto-Fix Mode
```bash
# Automatically fix issues where possible
python scripts/validate-documentation.py --fix

# Fixes:
# - Missing frontmatter
# - Inconsistent naming
# - Code block language identifiers
```

### Validation Checks

**Required Files**:
- README.md
- docs/index.md
- docs/CHANGELOG.md
- docs/decisions-log.md
- docs/architecture/reference-architecture.md
- docs/diagrams/system-architecture.mmd
- docs/diagrams/data-model.mmd

**Markdown Quality**:
- H1 title present in first 10 lines
- Proper heading hierarchy (no skips from H1 to H3)
- Lines under 120 characters (outside code blocks)
- Code blocks have language identifiers

**Link Validation**:
- All internal links point to existing files
- Relative links resolve correctly
- Anchors to headings are valid

**Mermaid Diagrams**:
- Proper code fences (```mermaid ... ```)
- Valid diagram type specified
- Syntax errors detected

**Consistency**:
- Component names consistent (e.g., "Agent 3" vs "Agent 03" vs "Agent Three")
- Service names follow pattern
- Terminology consistent across docs

**Frontmatter**:
- Specifications have Version, Date, Status, Priority
- All required fields present
- Dates in ISO format (YYYY-MM-DD)

### Output

```
═══════════════════════════════════════════════════════════════
  Documentation Validation
═══════════════════════════════════════════════════════════════

ℹ Checking required files...
ℹ Checking Markdown files...
ℹ Checking internal links...
ℹ Checking Mermaid diagrams...
ℹ Checking code blocks...
ℹ Checking naming consistency...
ℹ Checking frontmatter...

═══════════════════════════════════════════════════════════════
  Validation Results
═══════════════════════════════════════════════════════════════

✗ Errors (2):
  docs/functional/agent-05.md:0 - Required file missing: docs/functional/agent-05.md
    → Create this file using the appropriate template

⚠ Warnings (5):
  docs/index.md:45 - Heading hierarchy skip: H2 to H4
    → Use incremental heading levels (H1 → H2 → H3)

ℹ Info (12):
  docs/architecture/reference-architecture.md:156 - Line too long (127 chars)
    → Consider breaking into multiple lines for readability

Summary:
  Files checked: 23
  Errors: 2
  Warnings: 5
  Info: 12

✗ Validation FAILED
```

### Exit Codes

- `0`: Validation passed (no errors, or no errors/warnings if --strict)
- `1`: Validation failed (errors found, or warnings in --strict mode)

### CI/CD Integration

**GitHub Actions Example**:
```yaml
# .github/workflows/validate-docs.yml
name: Validate Documentation

on:
  pull_request:
    paths:
      - 'docs/**'
      - '**.md'

jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      
      - name: Validate Documentation
        run: |
          python scripts/validate-documentation.py --strict
```

---

## Templates

### templates/functional-spec-template.md

Template for creating new functional specifications. Used by `update-documentation.sh` when generating specs for new components.

**Placeholders**:
- `{{COMPONENT_NAME}}` - Component identifier (e.g., agent-03-income-scoring)
- `{{DATE}}` - Current date (YYYY-MM-DD)

**Usage**:
```bash
# Automatically used by update script
./scripts/update-documentation.sh --design-change new-component

# Or manually copy and fill in
cp scripts/templates/functional-spec-template.md docs/functional/my-component.md
# Replace {{COMPONENT_NAME}} with actual name
# Replace {{DATE}} with current date
```

**Sections**:
- Purpose & Scope
- Responsibilities
- Interfaces (Input/Output)
- Dependencies
- Success Criteria
- Non-Functional Requirements
- Workflow & State Machine
- Example Usage Scenarios
- Integration Points
- Error Handling
- Monitoring & Observability
- Future Enhancements
- Acceptance Criteria

### templates/implementation-spec-template.md

Template for implementation specifications (coming soon).

Includes all functional spec sections plus:
- Technical Design
- API/Interface Details
- Database Schema
- Testing & Acceptance
  - Unit Test Requirements
  - Integration Test Scenarios
  - Acceptance Criteria (Testable)
  - Known Edge Cases
  - Performance SLAs
- Implementation Notes
- Code Scaffolds

---

## Best Practices

### When to Run Scripts

**Daily Development**:
```bash
# At end of day if you made doc changes
./scripts/update-documentation.sh --full-sync

# Quick validation before committing
python scripts/validate-documentation.py
```

**After Design Meetings**:
```bash
# Document design decisions immediately
./scripts/update-documentation.sh --design-change <component>
```

**Before Pull Requests**:
```bash
# Ensure everything is valid
python scripts/validate-documentation.py --strict
```

**After Completing Components**:
```bash
# Update status and changelog
./scripts/update-documentation.sh --dev-complete <component>
```

### Git Integration

**Pre-commit Hook** (optional):
```bash
#!/bin/bash
# .git/hooks/pre-commit

# Validate docs before allowing commit
python scripts/validate-documentation.py --strict
if [ $? -ne 0 ]; then
    echo "Documentation validation failed. Fix issues before committing."
    exit 1
fi
```

**Make executable**:
```bash
chmod +x .git/hooks/pre-commit
```

### Automation Tips

1. **Use --non-interactive in CI/CD**:
   ```bash
   ./scripts/update-documentation.sh --full-sync --non-interactive --auto-commit
   ```

2. **Dry run before committing**:
   ```bash
   ./scripts/update-documentation.sh --design-change X --dry-run
   # Review what would change
   ./scripts/update-documentation.sh --design-change X
   ```

3. **Validate in CI pipeline**:
   ```yaml
   - name: Validate Docs
     run: python scripts/validate-documentation.py --strict
   ```

---

## Troubleshooting

### Permission Denied
```bash
# Make scripts executable
chmod +x scripts/update-documentation.sh
```

### Python Not Found
```bash
# Use python3 explicitly
python3 scripts/validate-documentation.py
```

### Git Not Initialized
```bash
# Initialize git if needed
cd /path/to/project
git init
git remote add origin https://github.com/your-org/repo.git
```

### Validation Fails on Valid Docs
```bash
# Check for common issues:
# 1. Missing frontmatter in specs
# 2. Broken relative links
# 3. Mermaid diagrams without proper code fences
# 4. Inconsistent component naming

# Get detailed output
python scripts/validate-documentation.py | tee validation.log
```

---

## Future Enhancements

### Planned Features

**update-documentation.sh**:
- [ ] Auto-generate diagrams from specs (PlantUML/Mermaid)
- [ ] Integration with Claude API for spec generation
- [ ] Dependency graph visualization
- [ ] Change impact analysis

**validate-documentation.py**:
- [ ] Spell checking
- [ ] Grammar checking (LanguageTool)
- [ ] Link validation for external URLs
- [ ] Diagram rendering validation
- [ ] Cross-reference validation (spec → code)

### Contributing

To improve these scripts:

1. **Report Issues**:
   - File GitHub issue with description
   - Include script output and environment details

2. **Submit Improvements**:
   - Fork repository
   - Make changes to scripts/
   - Add tests if applicable
   - Submit pull request

3. **Test Changes**:
   ```bash
   # Test update script
   ./scripts/update-documentation.sh --dry-run --design-change test
   
   # Test validation
   python scripts/validate-documentation.py --strict
   ```

---

## Dependencies

### Bash Script (update-documentation.sh)

**Required**:
- Bash 4.0+
- Git
- Basic Unix utilities (sed, grep, awk)

**Optional**:
- Python 3.7+ (for validation)

### Python Script (validate-documentation.py)

**Required**:
- Python 3.7+
- Standard library only (no external dependencies)

**Optional**:
- `requests` (for future external link validation)
- `markdown` (for future rendering validation)

---

## License

Same as main project license.

---

**Last Updated**: 2026-01-23  
**Maintainer**: Platform Team
