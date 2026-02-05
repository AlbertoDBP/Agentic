# Automated Documentation Updates - Practical Integration Guide

**How Claude Triggers Your Shell Scripts Automatically**

---

## 🎯 The Vision

**Before (Manual)**:
```
You: "I changed Agent 3 to use XGBoost"
→ You update specs manually
→ You run ./scripts/update-documentation.sh
→ You run validation
→ You commit to Git
→ Time: 20-30 minutes
```

**After (Automated with Claude)**:
```
You: "I changed Agent 3 to use XGBoost. Update docs."
→ Claude generates updated specs
→ Claude runs update-documentation.sh automatically
→ Claude validates
→ Claude shows results
→ You approve and commit
→ Time: 2-5 minutes
```

---

## 🚀 How It Works

### Step-by-Step Integration

#### 1. **Upload Your Repository to Claude**

When you start a conversation:

```
You: "I'm working on the Tax-Efficient Income Platform. 
      Here are the project files."
      
[Upload: income-platform/ directory or .tar.gz]
```

Claude now has access to:
- `/mnt/user-data/uploads/income-platform/`
- All your scripts in `/mnt/user-data/uploads/income-platform/scripts/`
- All your docs in `/mnt/user-data/uploads/income-platform/docs/`

#### 2. **Natural Conversation Triggers Automation**

**Example 1: Design Change**

```
You: "I'm changing Agent 3 to use XGBoost instead of linear regression. 
      The model will have 50+ features and output SHAP values for 
      explainability. Update the documentation."
```

**Claude's Response** (behind the scenes):

```python
# Claude thinks:
# 1. User wants documentation updated
# 2. Files are in /mnt/user-data/uploads/income-platform
# 3. I should use the automation scripts

# Claude executes:
bash_tool(
    command="""
    cd /mnt/user-data/uploads/income-platform
    
    # Make executable if needed
    chmod +x scripts/update-documentation.sh scripts/validate-documentation.py
    
    # First, update the spec files manually (I'll create them)
    # Then run the automation
    
    # Dry run first to see what would change
    ./scripts/update-documentation.sh \\
        --design-change agent-03-income-scoring \\
        --dry-run
    """
)

# Claude shows you the dry run output, then asks:
```

**Claude Shows You**:
```
I've drafted updated specifications for Agent 3 with XGBoost details.

Running automation preview (dry run)...

Would update:
- docs/functional/agent-03-income-scoring.md
- docs/CHANGELOG.md (add "Switched to XGBoost")
- docs/decisions-log.md (create ADR-007)

Proceed with these changes? (yes/no)
```

**You**: "Yes"

**Claude Executes**:
```python
# Now run for real
bash_tool(
    command="""
    cd /mnt/user-data/uploads/income-platform
    
    # Set environment variables for non-interactive mode
    export CHANGE_DESCRIPTION="Switched from linear regression to XGBoost with 50+ features and SHAP values"
    export IS_SIGNIFICANT_DECISION="yes"
    export DECISION_TITLE="XGBoost for Income Scoring"
    export DECISION_RATIONALE="Better accuracy on tabular data, feature importance built-in, SHAP for explainability"
    
    # Run the script
    ./scripts/update-documentation.sh \\
        --design-change agent-03-income-scoring \\
        --non-interactive
    """
)

# Validate
bash_tool(
    command="cd /mnt/user-data/uploads/income-platform && python3 scripts/validate-documentation.py --strict"
)

# Show results
bash_tool(
    command="cd /mnt/user-data/uploads/income-platform && git status --short"
)
```

**Claude Reports**:
```
✅ Documentation updated successfully!

Changes made:
M docs/functional/agent-03-income-scoring.md
M docs/implementation/agent-03-income-scoring-impl.md
M docs/CHANGELOG.md
M docs/decisions-log.md

Validation: PASSED ✓ (0 errors, 0 warnings)

New ADR created:
═══════════════════════════════════════════════════════
ADR-007: XGBoost for Income Scoring

**Context**: Need ML model for income quality prediction

**Decision**: Use XGBoost with 50+ features

**Rationale**: 
- Better accuracy on tabular financial data
- Built-in feature importance
- SHAP values for transparency
- Fast CPU-only inference
═══════════════════════════════════════════════════════

Ready to commit? Suggested message:
"docs(agent-03): switch to XGBoost with SHAP explainability

- Updated functional and implementation specs
- Model details: 50+ features, XGBoost classifier
- Added SHAP values for score transparency
- Created ADR-007 documenting decision
"

Options:
1. Download updated files
2. I'll show you the git diff
3. Commit now (I can run git commands if you're connected)
4. Just save for manual commit
```

---

### Example 2: Development Complete

**You**: "I finished implementing Agent 1. It's fully tested and deployed."

**Claude**:
```python
# Claude executes:
bash_tool(
    command="""
    cd /mnt/user-data/uploads/income-platform
    
    ./scripts/update-documentation.sh \\
        --dev-complete agent-01-market-data-sync \\
        --non-interactive
    """
)

bash_tool(
    command="cd /mnt/user-data/uploads/income-platform && python3 scripts/validate-documentation.py"
)
```

**Claude Reports**:
```
✅ Marked Agent 1 as complete!

Changes:
- docs/index.md: Status ⏳ → ✅
- CHANGELOG: "Agent 1 (Market Data Sync) implementation complete"

Validation: PASSED ✓

The master index now shows Agent 1 as complete. 

Would you like me to:
1. Update README.md with Agent 1 capabilities?
2. Generate API documentation?
3. Create a deployment checklist?
```

---

### Example 3: Full Sync Before Release

**You**: "We're releasing v1.1 tomorrow. Sync everything and validate."

**Claude**:
```python
# Full sync and validation
bash_tool(
    command="""
    cd /mnt/user-data/uploads/income-platform
    
    # Full sync
    ./scripts/update-documentation.sh --full-sync --non-interactive
    
    # Strict validation
    python3 scripts/validate-documentation.py --strict
    """
)

# Extract changelog for release notes
bash_tool(
    command="""
    cd /mnt/user-data/uploads/income-platform
    
    # Get unreleased changes
    sed -n '/^## \[Unreleased\]/,/^## \[/p' docs/CHANGELOG.md | head -n -1
    """
)
```

**Claude Reports**:
```
✅ Full documentation sync complete

Validation: PASSED ✓
- 47 files checked
- 0 errors
- 0 warnings

CHANGELOG summary (Unreleased → v1.1):

### Added
- Agent 3: XGBoost income scoring with SHAP
- Agent 11: Alert classification
- Security: RLS policies complete

### Changed
- Architecture: Hybrid orchestration
- Agent 1: Enhanced error handling

All documentation is consistent and ready for release.

Shall I:
1. Move Unreleased to v1.1 in CHANGELOG?
2. Update version badges in README?
3. Generate release notes?
```

---

## 🔧 Technical Details: How Claude Accesses Scripts

### File System Access Patterns

**When You Upload Files**:
```
User uploads: income-platform.tar.gz
→ Extracted to: /mnt/user-data/uploads/income-platform/
→ Scripts at: /mnt/user-data/uploads/income-platform/scripts/
```

**Claude Can Then**:
```python
# 1. Check if scripts exist
bash_tool(command="ls -la /mnt/user-data/uploads/income-platform/scripts/")

# 2. Make them executable
bash_tool(command="chmod +x /mnt/user-data/uploads/income-platform/scripts/*.sh")

# 3. Run them
bash_tool(
    command="""
    cd /mnt/user-data/uploads/income-platform
    ./scripts/update-documentation.sh --help
    """
)

# 4. Read outputs
bash_tool(command="cat /mnt/user-data/uploads/income-platform/docs/CHANGELOG.md")
```

### Environment Variable Passing

For non-interactive mode, Claude sets variables:

```python
bash_tool(
    command="""
    cd /mnt/user-data/uploads/income-platform
    
    # Set all required variables
    export CHANGE_DESCRIPTION="XGBoost implementation"
    export IS_SIGNIFICANT_DECISION="yes"
    export DECISION_TITLE="Switch to XGBoost"
    export DECISION_RATIONALE="Better accuracy and explainability"
    export UPDATE_DIAGRAMS="no"  # Claude already updated them
    
    # Run script (reads from environment)
    ./scripts/update-documentation.sh \\
        --design-change agent-03-income-scoring \\
        --non-interactive
    """
)
```

### Validation and Error Handling

Claude always validates after updates:

```python
# Run update
result = bash_tool(command="./scripts/update-documentation.sh ...")

# Check if successful
if result.returncode != 0:
    print(f"❌ Script failed: {result.stderr}")
    print("I'll update documentation manually instead.")
    # Fallback to manual file creation
else:
    # Validate
    validation = bash_tool(command="python3 scripts/validate-documentation.py --strict")
    
    if validation.returncode != 0:
        print("⚠️ Validation found issues:")
        print(validation.stdout)
        print("Would you like me to fix them?")
    else:
        print("✅ Validation passed!")
```

---

## 📋 Practical Workflow Examples

### Daily Development Workflow

**Morning** (start work):
```
You: "Load the income platform project"
[Upload files]

Claude: "Income platform loaded. 47 documentation files found.
         Ready to assist with design and development."
```

**During development**:
```
You: "I'm refactoring Agent 3 to split scoring into 5 separate 
      factor models. Update the functional spec."

Claude: [Generates updated spec]
        [Runs automation scripts]
        [Validates]
        [Reports results]
        
        ✅ Done! Updated functional spec with factor model architecture.
```

**End of day**:
```
You: "Sync all documentation changes and validate before I push."

Claude: [Runs full sync]
        [Validates strictly]
        [Shows git status]
        
        ✅ All synced and validated. 3 files changed.
           Ready to commit.
```

### Weekly Documentation Review

**Friday afternoon**:
```
You: "Review all documentation for consistency and completeness."

Claude: [Runs validation with all checks]
        [Generates report]
        
        Validation Results:
        ✅ Required files: All present
        ✅ Markdown structure: Correct
        ✅ Internal links: All valid
        ⚠️ Warnings: 2
           - agent-05.md: Missing priority field
           - README.md: Version badge outdated
        
        Would you like me to fix these warnings?
```

**You**: "Yes, fix them."

**Claude**: 
```
[Fixes frontmatter in agent-05.md]
[Updates version badge in README]
[Re-validates]

✅ All warnings fixed!
✅ Validation: PASSED (0 errors, 0 warnings)

Changes ready to commit.
```

### Release Preparation

**Before release**:
```
You: "We're releasing v1.2 next week. Prepare documentation."

Claude: [Comprehensive checks]
        
        Release Readiness Checklist:
        ✅ All specs up-to-date
        ✅ CHANGELOG has unreleased entries
        ✅ All links valid
        ✅ ADRs documented
        ⚠️ README version still shows v1.1
        
        To prepare for v1.2:
        1. Update README version badge
        2. Move CHANGELOG unreleased → v1.2
        3. Update docs/index.md version
        4. Tag release in Git
        
        Shall I help with these?
```

---

## 🎓 Teaching Claude Your Workflow

### First Conversation (Training)

```
You: "Here's how I want documentation updates to work:

1. When I mention a design change, update the spec and run 
   ./scripts/update-documentation.sh --design-change <component>

2. When I say something is complete, run 
   ./scripts/update-documentation.sh --dev-complete <component>

3. Always validate after updates with 
   python3 scripts/validate-documentation.py --strict

4. Show me what changed before committing

5. Only run git commands if I explicitly approve

Got it?"

Claude: "Understood! I'll follow this workflow:
         
         Design change → Update spec → Run automation → Validate → Show results
         Dev complete → Mark complete → Update CHANGELOG → Validate
         Always seek approval before git commits
         
         I'm ready. Try: 'I changed Agent 3 to use XGBoost'"
```

### Subsequent Conversations (Automatic)

Claude remembers your preferences:

```
You: "Updated Agent 5 to handle Roth IRAs differently. Update docs."

Claude: [Immediately follows learned workflow]
        ✓ Updating Agent 5 functional spec...
        ✓ Running automation scripts...
        ✓ Validating...
        ✅ Done!
```

---

## 💡 Advanced Integration Patterns

### Pattern 1: Branching Logic

```
You: "I'm considering two approaches for Agent 6:
      A) Simple GLM model
      B) Complex neural network
      
      Show me updated specs for both so I can decide."

Claude: "I'll create comparison specs:
        
        [Creates agent-06-scenario-glm.md]
        [Creates agent-06-scenario-nn.md]
        
        Here are both approaches documented.
        
        When you decide, tell me which one and I'll:
        1. Rename the chosen spec to agent-06-scenario.md
        2. Run automation scripts
        3. Create ADR documenting your choice
        
        Which approach do you prefer?"
```

### Pattern 2: Incremental Updates

```
You: "I'm making 3 changes to Agent 3:
      1. Add caching layer
      2. Implement batch scoring
      3. Add SHAP values
      
      Update docs incrementally as I implement each."

Claude: "Got it! I'll track these incrementally.
        
        Tell me as you complete each:
        - 'Done with caching' → I'll update and validate
        - 'Done with batch scoring' → I'll update and validate
        - 'Done with SHAP' → I'll update, validate, mark Agent 3 complete
        
        This way CHANGELOG and ADRs stay accurate."
```

### Pattern 3: Multi-Component Updates

```
You: "I refactored the orchestration layer. This affects:
      - Agent 1 (different trigger mechanism)
      - Agent 3 (different scoring pipeline)  
      - Agent 11 (different alert delivery)
      
      Update all affected components."

Claude: [Updates multiple specs]
        [Runs automation for each]
        [Creates single ADR for architecture change]
        [Validates everything]
        
        ✅ Updated 3 components + architecture docs
        
        Created ADR-008: "Refactor Orchestration Layer"
        
        All validations passed.
        
        Would you like a summary of all changes?
```

---

## 🚦 User Control & Safety

### Claude Always Asks Before:

✅ **Running actual updates** (dry-run shown first)
✅ **Creating ADRs** (confirms it's significant)
✅ **Committing to Git** (shows diff, suggests message)
✅ **Pushing to remote** (explicit approval needed)

### Claude Never Does Automatically:

❌ Git commits without approval
❌ Git pushes without approval
❌ Deleting files
❌ Overwriting without showing diff

### Transparency at Every Step:

```
Claude: "I'm about to:
         1. Update agent-03-income-scoring.md
         2. Run: ./scripts/update-documentation.sh --design-change agent-03
         3. Validate with: python3 scripts/validate-documentation.py
         
         Proceed? (yes/no/show me what would change first)"
```

---

## ✅ Summary: The Complete Integration

**What You Get**:

1. **Natural Conversations**: "I changed X, update docs" → Done
2. **Automatic Updates**: CHANGELOG, ADRs, status tracking
3. **Built-in Validation**: Every change validated
4. **Git Integration**: Suggested commits, but you control
5. **Full Transparency**: See exactly what changed
6. **Fallback Safety**: Manual mode if scripts fail

**Time Savings**:

| Task | Manual | With Claude | Savings |
|------|--------|-------------|---------|
| Design change docs | 20-30 min | 2-5 min | 15-25 min |
| Mark dev complete | 10-15 min | 1-2 min | 8-13 min |
| Pre-release sync | 30-45 min | 5-10 min | 25-35 min |
| **Weekly (5 updates)** | **2-3 hours** | **15-30 min** | **~2 hours** |

**Next Steps**:

1. Upload your `income-platform/` folder to Claude
2. Say: "I'm working on the income platform. Use the automation scripts."
3. Make design/development changes
4. Tell Claude what changed
5. Claude handles the rest!

---

**Ready to try it?** Just upload your project files and start a conversation! 🚀
