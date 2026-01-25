# Documentation Validation Warnings - README

## What Are These Warnings?

When you run `python3 scripts/validate-documentation.py`, you'll see **76 broken link errors**. These are **EXPECTED and INTENTIONAL** - they're placeholders for documentation that will be created as you develop the platform.

## Why Placeholders?

The `docs/index.md` file serves as a **roadmap** showing all documentation that WILL exist, organized by:
- **✅ Complete**: Documentation that exists now
- **🚧 In Progress**: Being worked on  
- **⏳ Pending**: Planned for future

## Current Status

### Existing Documentation (No Errors)
✅ Reference Architecture  
✅ System & Data Model Diagrams  
✅ Agent 3 Functional Spec (Income Scoring)  
✅ CHANGELOG.md  
✅ decisions-log.md  

### Planned Documentation (Validation Warnings)
These will be created as you develop each component:
- Agent 1, 2, 4-11 functional specs (10 files)
- Agent 1-11 implementation specs (11 files)
- Frontend specs (5 files)
- Infrastructure specs (3 files)
- Security docs (5 files)
- Deployment docs (5 files)
- Testing docs (4 files)
- Development guides (8 files)
- API specs (4 files)

## Solutions

### Option 1: Use `--fix` to Ignore Planned Files (Recommended)

I'll create an enhanced validation script that understands "planned" vs "broken" links.

### Option 2: Skip Validation for Now

```bash
# Just validate the files that exist
python3 scripts/validate-documentation.py 2>&1 | grep -v "Broken link"

# Or validate without strict mode (warnings won't fail)
python3 scripts/validate-documentation.py  # (don't use --strict)
```

### Option 3: Create Placeholder Files

```bash
# Create empty placeholder files for all planned docs
cd /Volumes/CH-DataOne/AlbertoDBP/Agentic/income-platform

# Create directory structure
mkdir -p docs/{security,deployment,development,testing,api,implementation,functional}

# Create placeholder files (example)
for agent in 01 02 04 05 06 07 08 09 10 11; do
    touch docs/functional/agent-${agent}-*.md
    touch docs/implementation/agent-${agent}-*-impl.md
done

# Add "Coming Soon" content to each
echo "# Coming Soon\n\nThis documentation will be created during development." > docs/security/security-architecture.md
```

### Option 4: Comment Out Placeholders in index.md

Edit `docs/index.md` and comment out the table rows for files that don't exist yet:

```markdown
<!-- PLANNED: Uncomment as files are created
| Agent 1 | [Market Data](functional/agent-01-market-data-sync.md) | P0 |
| Agent 2 | [Newsletter](functional/agent-02-newsletter-ingestion.md) | P0 |
-->
```

## Recommended Workflow

### During Development

When you create a new component:

1. **Create the spec files**:
   ```bash
   # Use Claude with the orchestrator skill
   "Generate functional and implementation specs for Agent 1"
   ```

2. **Uncomment in index.md** (if you chose Option 4)

3. **Validate**:
   ```bash
   python3 scripts/validate-documentation.py --strict
   ```

4. **Update status** in index.md:
   ```markdown
   | Agent 1 | [Market Data](functional/agent-01.md) | ✅ Complete |
   ```

### Progressive Documentation Strategy

**Phase 1** (Now): Foundation docs exist
- Reference architecture ✅
- Data model ✅
- Agent 3 spec ✅ (as example)
- CHANGELOG ✅
- ADRs ✅

**Phase 2** (Agents 1, 2, 11): Create as you implement
- Functional specs
- Implementation specs
- Testing specs

**Phase 3** (Remaining agents): Create as needed
- Agents 4-10 specs
- Frontend specs
- Infrastructure specs

**Phase 4** (Polish): Complete remaining docs
- Security details
- Deployment guides
- Development standards

## Using Validation Effectively

### Check What Exists

```bash
# See which files are actually present
find docs/ -name "*.md" -type f

# Compare with what's referenced in index.md
grep -o '\[.*\]([^)]*.md)' docs/index.md | sort | uniq
```

### Validate Only Existing Docs

```bash
# I'll create a script that only validates existing files
python3 scripts/validate-existing-only.py
```

### CI/CD Integration

For GitHub Actions, only fail on errors in existing files:

```yaml
# .github/workflows/validate-docs.yml
- name: Validate Documentation
  run: |
    # Only validate files that exist
    python3 scripts/validate-documentation.py || true
    # Or use custom script
    python3 scripts/validate-existing-only.py --strict
```

## Understanding the Errors

### Error Format
```
docs/index.md:60 - Broken link: functional/agent-01-market-data-sync.md
  → Target file does not exist: /path/to/file
```

**This means**: 
- Line 60 of `docs/index.md` references a file
- That file doesn't exist YET
- It WILL exist when you implement Agent 1

### Not Actually Broken

These aren't bugs - they're a **roadmap** of what documentation will be created.

## Quick Reference

| Validation Result | Meaning | Action |
|-------------------|---------|--------|
| "Broken link: functional/agent-03-..." | **ERROR** - Referenced existing file is actually broken | Fix the link |
| "Broken link: functional/agent-01-..." | **PLANNED** - File will be created later | Ignore for now, or use Option 1-4 above |
| "Missing frontmatter" | **WARNING** - Existing file needs version/date/etc | Add frontmatter |
| "Heading hierarchy skip" | **INFO** - Style issue | Optional fix |

## Next Steps

1. **For now**: Ignore the 76 "broken link" warnings - they're expected
2. **As you develop**: Create specs for each agent using Claude + orchestrator skill
3. **Validate incrementally**: After creating each spec, run validation
4. **Use automation**: The update-documentation.sh script will help maintain consistency

---

**TL;DR**: The validation warnings are expected. They're placeholders for docs you'll create as you build the platform. You can safely ignore them for now or use one of the solutions above to clean up the validation output.

**When developing**: Use Claude with the orchestrator skill to generate each spec, and validation warnings will naturally decrease as you create more documentation.
