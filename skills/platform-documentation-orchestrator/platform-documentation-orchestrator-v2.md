---
name: platform-documentation-orchestrator-v2
description: Enhanced orchestrator that automatically updates documentation and runs validation after design/development changes. Integrates with automation scripts to maintain documentation consistency without manual intervention.
---

# Platform Documentation Orchestrator v2 (Automated)

This enhanced skill integrates documentation generation with automated update scripts, enabling Claude to keep documentation synchronized with design and development progress automatically.

## Key Enhancement: Automated Script Execution

After generating or updating documentation, Claude can now:
1. ✅ Run validation checks automatically
2. ✅ Update CHANGELOG.md via script
3. ✅ Create ADRs in decisions-log.md
4. ✅ Update component status in index.md
5. ✅ Optionally commit changes to Git

## Workflow Integration

### Traditional Workflow (Manual)
```
User: "Update Agent 3 documentation"
→ Claude generates specs
→ User manually runs update-documentation.sh
→ User manually validates
→ User manually commits
```

### Enhanced Workflow (Automated)
```
User: "Update Agent 3 documentation"
→ Claude generates specs
→ Claude runs bash_tool to execute update-documentation.sh
→ Claude validates documentation
→ Claude reports results
→ User reviews and optionally pushes
```

## How to Use This Skill

### Option 1: Design Change with Auto-Update

```
User: "I changed Agent 3 to use XGBoost instead of linear regression. 
       Update the documentation."

Claude response:
1. Uses bash_tool to check if scripts exist
2. Generates updated functional/implementation specs
3. Runs: ./scripts/update-documentation.sh --design-change agent-03-income-scoring --non-interactive
4. Runs: python scripts/validate-documentation.py --strict
5. Reports validation results
6. Asks: "Ready to commit? I can run git commands or you can review first."
```

### Option 2: Development Complete with Auto-Update

```
User: "I finished implementing Agent 1. Update docs to reflect completion."

Claude response:
1. Runs: ./scripts/update-documentation.sh --dev-complete agent-01-market-data-sync --non-interactive
2. Validates documentation
3. Shows what changed (CHANGELOG, index.md status)
4. Asks: "Commit and push? Or would you like to review first?"
```

### Option 3: Full Documentation Sync

```
User: "Sync all documentation before release"

Claude response:
1. Runs validation first
2. If validation passes, runs full sync
3. Shows summary of changes
4. Optionally commits with generated message
```

## Claude's Approach to Script Execution

When executing automation scripts, Claude will:

### 1. **Check Prerequisites**
```python
# First, verify scripts exist and are executable
bash_tool(command="ls -la /mnt/user-data/uploads/income-platform/scripts/")
bash_tool(command="test -x /mnt/user-data/uploads/income-platform/scripts/update-documentation.sh && echo 'executable' || echo 'not executable'")

# Make executable if needed
bash_tool(command="chmod +x /mnt/user-data/uploads/income-platform/scripts/*.sh")
```

### 2. **Run Update Script (Non-Interactive Mode)**
```python
# For design changes
bash_tool(
    command="""
    cd /mnt/user-data/uploads/income-platform
    ./scripts/update-documentation.sh \\
        --design-change agent-03-income-scoring \\
        --non-interactive \\
        --dry-run  # First see what would change
    """
)

# If user approves, run without --dry-run
bash_tool(
    command="""
    cd /mnt/user-data/uploads/income-platform
    ./scripts/update-documentation.sh \\
        --design-change agent-03-income-scoring \\
        --non-interactive
    """
)
```

### 3. **Validate Documentation**
```python
bash_tool(
    command="""
    cd /mnt/user-data/uploads/income-platform
    python3 scripts/validate-documentation.py --strict
    """
)
```

### 4. **Report Results**
Claude will parse script output and present:
- ✅ What was updated (CHANGELOG entries, ADRs created, status changes)
- ✅ Validation results (errors, warnings, info)
- ✅ Suggested next steps (review changes, commit, push)

## Limitations and Workarounds

### Limitation 1: Scripts Require User Input (Interactive Mode)

**Problem**: Original scripts prompt for user input
```bash
read -p "Describe the design change: " change_description
```

**Solution**: Non-interactive mode with environment variables
```bash
# Enhanced script accepts pre-set values
export CHANGE_DESCRIPTION="Added SHAP explainability"
export IS_SIGNIFICANT_DECISION="yes"
export DECISION_TITLE="Add SHAP for Transparency"
export DECISION_RATIONALE="Users need to understand score drivers"

./scripts/update-documentation.sh --design-change agent-03 --non-interactive
```

**Claude's Approach**: 
1. Ask user for key information upfront
2. Set environment variables
3. Run script in non-interactive mode

### Limitation 2: Git Operations Require Confirmation

**Problem**: Committing to Git should be deliberate
```bash
git commit -m "docs: update agent-03"
git push origin main
```

**Solution**: Separate validation from commit
```bash
# Claude runs up to validation
./scripts/update-documentation.sh --design-change agent-03 --non-interactive

# User reviews changes
git diff

# User decides to commit
git add .
git commit -m "docs: update agent-03 with SHAP"
git push
```

**Claude's Approach**:
1. Run scripts to update files
2. Show what changed (git diff)
3. Ask user: "Ready to commit? I can generate commit message."
4. Only execute git commands if user explicitly approves

### Limitation 3: File System Access

**Problem**: Scripts need access to repository files

**Solution**: Claude uses bash_tool with proper paths
```python
# Check if files exist in uploads
bash_tool(command="ls -la /mnt/user-data/uploads/income-platform/")

# If exists, run scripts there
bash_tool(command="cd /mnt/user-data/uploads/income-platform && ./scripts/update-documentation.sh --help")

# If not in uploads, copy from outputs
bash_tool(command="cp -r /mnt/user-data/outputs/income-platform /mnt/user-data/uploads/")
```

## Enhanced Workflow Examples

### Example 1: Complete Design Change Workflow

**User Request**:
```
"I'm changing Agent 3 to use XGBoost with 50+ features instead of the 
simple linear model. Update all documentation and validate."
```

**Claude's Execution**:

```python
# Step 1: Generate updated specs (using computer tools)
create_file(
    path="/mnt/user-data/outputs/income-platform/docs/functional/agent-03-income-scoring.md",
    content="[Updated specification with XGBoost details]"
)

# Step 2: Copy to working directory if needed
bash_tool(
    command="cp -r /mnt/user-data/outputs/income-platform /mnt/user-data/uploads/"
)

# Step 3: Set environment variables for non-interactive mode
bash_tool(
    command="""
    cd /mnt/user-data/uploads/income-platform
    export CHANGE_DESCRIPTION="Switched from linear model to XGBoost with 50+ features"
    export IS_SIGNIFICANT_DECISION="yes"
    export DECISION_TITLE="XGBoost for Income Scoring"
    export DECISION_RATIONALE="Better accuracy on tabular data, built-in feature importance"
    
    ./scripts/update-documentation.sh --design-change agent-03-income-scoring --non-interactive
    """
)

# Step 4: Validate
bash_tool(
    command="""
    cd /mnt/user-data/uploads/income-platform
    python3 scripts/validate-documentation.py --strict
    """
)

# Step 5: Show results
bash_tool(
    command="""
    cd /mnt/user-data/uploads/income-platform
    git status --short
    """
)
```

**Claude's Response**:
```
✅ Updated documentation for Agent 3 (Income Scoring)

Changes made:
- Updated functional specification with XGBoost details
- Updated CHANGELOG.md: "Switched from linear model to XGBoost"
- Created ADR-006: "XGBoost for Income Scoring" in decisions-log.md
- Validation: PASSED ✓

Modified files:
M docs/functional/agent-03-income-scoring.md
M docs/CHANGELOG.md
M docs/decisions-log.md

Ready to commit? I can generate a commit message like:
"docs(agent-03): switch to XGBoost with 50+ features

- Updated functional spec with XGBoost model details
- Added ADR-006 documenting decision rationale
- CHANGELOG reflects algorithm change
"

Would you like me to:
1. Show the git diff for review
2. Commit with the suggested message
3. Just leave changes for you to commit manually
```

### Example 2: Development Complete Workflow

**User Request**:
```
"I finished implementing Agent 1 (Market Data Sync). Mark it as complete."
```

**Claude's Execution**:

```python
# Step 1: Run dev-complete script
bash_tool(
    command="""
    cd /mnt/user-data/uploads/income-platform
    ./scripts/update-documentation.sh --dev-complete agent-01-market-data-sync --non-interactive
    """
)

# Step 2: Validate
bash_tool(
    command="""
    cd /mnt/user-data/uploads/income-platform
    python3 scripts/validate-documentation.py
    """
)

# Step 3: Check what changed
bash_tool(
    command="""
    cd /mnt/user-data/uploads/income-platform
    git diff docs/index.md docs/CHANGELOG.md
    """
)
```

**Claude's Response**:
```
✅ Marked Agent 1 (Market Data Sync) as complete

Changes:
- docs/index.md: Status updated from ⏳ Pending → ✅ Complete
- docs/CHANGELOG.md: Added "Agent 1 implementation complete"

Validation: PASSED ✓

The component is now tracked as complete in the master index.

Next steps:
1. Ensure OpenAPI docs are current (if it's a FastAPI service)
2. Update README if new capabilities were added
3. Commit changes

Ready to proceed?
```

### Example 3: Pre-Release Documentation Sync

**User Request**:
```
"We're releasing v1.1 tomorrow. Sync and validate all documentation."
```

**Claude's Execution**:

```python
# Step 1: Run full sync (dry run first)
bash_tool(
    command="""
    cd /mnt/user-data/uploads/income-platform
    ./scripts/update-documentation.sh --full-sync --dry-run
    """
)

# If dry run looks good, run actual sync
bash_tool(
    command="""
    cd /mnt/user-data/uploads/income-platform
    ./scripts/update-documentation.sh --full-sync --non-interactive
    """
)

# Step 2: Strict validation
bash_tool(
    command="""
    cd /mnt/user-data/uploads/income-platform
    python3 scripts/validate-documentation.py --strict
    """
)

# Step 3: Generate release summary
bash_tool(
    command="""
    cd /mnt/user-data/uploads/income-platform
    # Extract latest version changes from CHANGELOG
    sed -n '/^## \[Unreleased\]/,/^## \[/p' docs/CHANGELOG.md
    """
)
```

**Claude's Response**:
```
✅ Full documentation sync complete for v1.1 release

Validation: PASSED ✓ (0 errors, 0 warnings)

CHANGELOG summary for v1.1:

### Added
- Agent 3: XGBoost income scoring with SHAP
- Agent 11: Alert classification with ML
- Security: Complete RLS policies

### Changed
- Architecture: Hybrid orchestration (n8n + Prefect)
- Agent 1: Enhanced error handling

All documentation is consistent and ready for release.

Suggested actions:
1. Review CHANGELOG.md for v1.1 completeness
2. Update README.md version badge
3. Tag release: git tag -a v1.1 -m "Release v1.1"
4. Push: git push origin main --tags

Shall I help with any of these steps?
```

## Integration with Existing Orchestrator Workflow

The enhanced skill follows the same 8-step workflow as the original, with automation added:

### Original Workflow
1. Analyze design input
2. Create reference architecture
3. Define functional specifications
4. Define implementation specifications
5. Generate code scaffolds
6. Create folder structure
7. Produce linking documents
8. Generate setup instructions

### Enhanced Workflow (Automated)
1. Analyze design input
2. Create reference architecture
3. Define functional specifications
4. Define implementation specifications
5. Generate code scaffolds
6. Create folder structure
7. Produce linking documents
8. Generate setup instructions
9. **✨ Run update-documentation.sh (NEW)**
10. **✨ Validate with validate-documentation.py (NEW)**
11. **✨ Present results and offer Git integration (NEW)**

## When Claude Uses Automation Scripts

Claude should trigger scripts when:

### ✅ Trigger Automation
- User says: "update documentation for [component]"
- User says: "I finished implementing [component]"
- User says: "validate documentation"
- User says: "sync documentation"
- User asks: "what changed in the docs?"

### ❌ Don't Trigger Automation
- User is just asking questions about design
- User wants to see examples without updating
- User is exploring options (not making decisions)
- Scripts don't exist in the file system

## Script Execution Safety

Claude follows these safety principles:

### 1. **Always Use --dry-run First**
```python
# First: dry run to preview
bash_tool(command="./scripts/update-documentation.sh --design-change X --dry-run")

# Then: ask user if output looks good
# Only then: run actual command
bash_tool(command="./scripts/update-documentation.sh --design-change X --non-interactive")
```

### 2. **Never Auto-Commit to Git Without Explicit Approval**
```python
# Claude runs up to validation
bash_tool(command="./scripts/update-documentation.sh --design-change X --non-interactive")

# Claude shows changes
bash_tool(command="git diff docs/")

# Claude asks user
print("Changes look good. Ready to commit? (I'll wait for your approval)")
```

### 3. **Validate After Every Change**
```python
# After any documentation update
bash_tool(command="python3 scripts/validate-documentation.py --strict")

# If validation fails, report issues
# Don't proceed to commit
```

### 4. **Handle Script Errors Gracefully**
```python
result = bash_tool(command="./scripts/update-documentation.sh --design-change X")

if result.returncode != 0:
    print(f"❌ Script failed: {result.stderr}")
    print("I'll update documentation manually instead.")
    # Fall back to manual file creation
```

## User Control and Transparency

Claude maintains transparency by:

### Before Execution
```
I'm about to run:
  ./scripts/update-documentation.sh --design-change agent-03-income-scoring

This will:
1. Update agent-03-income-scoring.md
2. Add entry to CHANGELOG.md
3. Create ADR in decisions-log.md
4. Validate all docs

Proceed? (yes/no)
```

### During Execution
```
✓ Running update script...
✓ Validating documentation...
✓ Checking for errors...
```

### After Execution
```
✅ Complete! Here's what changed:

Modified files:
  M docs/functional/agent-03-income-scoring.md
  M docs/CHANGELOG.md
  M docs/decisions-log.md

Validation: PASSED ✓

What would you like to do next?
1. Review changes (I'll show git diff)
2. Commit changes (I'll generate commit message)
3. Nothing (changes saved, ready for manual commit)
```

## Fallback: Manual Mode

If scripts aren't available or fail, Claude falls back to manual mode:

```python
# Try automated mode first
try:
    result = bash_tool(command="./scripts/update-documentation.sh --help")
    use_automation = True
except:
    use_automation = False
    print("Automation scripts not found. I'll update documentation manually.")

if use_automation:
    # Run scripts as above
else:
    # Original workflow: create files directly
    create_file(path="docs/CHANGELOG.md", content="...")
    create_file(path="docs/decisions-log.md", content="...")
```

## Benefits of Integrated Automation

### 1. **Consistency**
✅ CHANGELOG always updated  
✅ ADRs always created for significant decisions  
✅ Status always reflects reality  
✅ Validation always run before completion  

### 2. **Speed**
✅ Single command triggers full workflow  
✅ No context switching  
✅ Immediate feedback  

### 3. **Quality**
✅ Validation catches issues immediately  
✅ No forgetting to update files  
✅ Standardized commit messages  

### 4. **User Experience**
✅ Natural conversation ("I changed X, update docs")  
✅ Claude handles mechanics  
✅ User stays in design/development flow  

## Example Conversations

### Conversation 1: Natural Design Update

**User**: "I'm adding SHAP explainability to the income scoring agent. Update the docs."

**Claude**: 
```
Got it! I'll update the documentation for Agent 3 with SHAP explainability.

First, let me update the functional specification...
[creates updated spec]

Now running automation scripts...
✓ Executing: ./scripts/update-documentation.sh --design-change agent-03-income-scoring
✓ Validating documentation...

✅ Documentation updated successfully!

Changes:
- Updated functional spec with SHAP details
- CHANGELOG: "Added SHAP explainability to Agent 3"
- Created ADR-007: "SHAP for Transparency"
- Validation: PASSED ✓

Ready to commit with message:
"docs(agent-03): add SHAP explainability

- Users can now see feature importance
- SHAP values explain each score
- Added to functional specification
"

Approve commit? (yes/no)
```

### Conversation 2: Development Milestone

**User**: "Agent 1 is done. Mark it complete."

**Claude**:
```
Excellent! Marking Agent 1 (Market Data Sync) as complete.

✓ Running: ./scripts/update-documentation.sh --dev-complete agent-01-market-data-sync
✓ Validating...

✅ Complete!

Updated:
- docs/index.md: Agent 1 status ⏳ → ✅
- CHANGELOG: "Agent 1 implementation complete and tested"

Validation: PASSED ✓

Next steps:
1. Ensure API docs are current (/docs endpoint)
2. Update README if new features added
3. Commit changes

What would you like to do?
```

### Conversation 3: Pre-Release Check

**User**: "Validate everything before we release."

**Claude**:
```
Running comprehensive validation...

✓ Checking required files...
✓ Validating Markdown structure...
✓ Checking internal links...
✓ Validating Mermaid diagrams...
✓ Checking consistency...

✅ Validation PASSED

Summary:
- Files checked: 47
- Errors: 0
- Warnings: 0
- Info: 3 (minor formatting suggestions)

All documentation is ready for release v1.1!

Shall I generate a release summary from the CHANGELOG?
```

## Summary

This enhanced orchestrator skill enables Claude to:

✅ **Execute automation scripts** via bash_tool  
✅ **Update documentation automatically** after design/dev changes  
✅ **Validate quality** before completion  
✅ **Maintain Git hygiene** (with user approval)  
✅ **Provide transparency** at every step  
✅ **Fall back gracefully** if scripts unavailable  

The result: **Seamless documentation workflow** where users focus on design and development while Claude handles documentation mechanics.

---
```
