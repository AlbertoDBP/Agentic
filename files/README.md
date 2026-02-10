# GitHub Actions Documentation Automation Package

Automated documentation workflow for the Agentic monorepo, designed to work seamlessly with the platform-documentation-orchestrator skill.

## 📦 What's Included

This package contains:

1. **GitHub Actions Workflow** (`.github/workflows/auto-documentation.yml`)
   - Automatically generates and validates documentation
   - Runs on schedule, manual trigger, or code changes
   - Commits and pushes changes automatically

2. **Trigger Script** (`scripts/trigger-docs-workflow.sh`)
   - Trigger workflow from command line or Claude Code
   - Supports project-specific updates
   - Force update capability

3. **Documentation** (`docs/`)
   - Complete setup guide
   - Quick reference card
   - Troubleshooting tips

## 🎯 Quick Start

### 1. Install

```bash
cd /Volumes/CH-DataOne/AlbertoDBP/Agentic

# Copy workflow file
mkdir -p .github/workflows
cp auto-documentation.yml .github/workflows/

# Copy trigger script
mkdir -p scripts/github
cp trigger-docs-workflow.sh scripts/github/
chmod +x scripts/github/trigger-docs-workflow.sh

# Commit and push
git add .github/workflows/auto-documentation.yml scripts/github/
git commit -m "feat: add automated documentation workflow"
git push origin main
```

### 2. Configure GitHub

Enable workflow permissions:
1. Go to repo Settings → Actions → General
2. Under "Workflow permissions", select "Read and write permissions"
3. Save

### 3. Get GitHub Token (for manual triggers)

```bash
# 1. Create token at https://github.com/settings/tokens
# 2. Select 'repo' scope
# 3. Set environment variable
export GITHUB_TOKEN="ghp_your_token_here"
```

### 4. Trigger Workflow

```bash
# Trigger documentation update
./scripts/github/trigger-docs-workflow.sh --token $GITHUB_TOKEN

# Or for specific project
./scripts/github/trigger-docs-workflow.sh \
  --project income-platform \
  --token $GITHUB_TOKEN
```

## 🔄 Workflow Overview

```
┌─────────────────────────────────────────────┐
│ Trigger Sources                             │
├─────────────────────────────────────────────┤
│ • Schedule (Daily 2 AM UTC)                 │
│ • Manual (GitHub UI or trigger script)      │
│ • Pull Request (validates docs)             │
│ • Repository Dispatch (from Claude Code)    │
└─────────────────┬───────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────┐
│ Workflow Execution                          │
├─────────────────────────────────────────────┤
│ 1. Detect changes in project directories    │
│ 2. Run update-documentation.sh scripts      │
│ 3. Validate with validate-documentation.py  │
│ 4. Commit and push if changes detected      │
│ 5. Create summary report                    │
└─────────────────────────────────────────────┘
```

## 📚 Documentation

- **[Setup Guide](docs/SETUP_GUIDE.md)** - Complete installation and configuration
- **[Quick Reference](docs/QUICK_REFERENCE.md)** - Common operations and commands

## 🔧 Integration with Claude

This workflow is designed to work with your platform-documentation-orchestrator skill:

### In Claude Chat

1. Complete your design/development work
2. Say "Document" to invoke the orchestrator skill
3. Download generated files
4. Copy to your local repo and commit

### In Claude Code (VSCode)

1. Complete your work in VSCode with Claude Code
2. Run the trigger script:
   ```bash
   ./scripts/github/trigger-docs-workflow.sh --project your-project
   ```
3. Workflow automatically validates and commits

### Automated Workflow

You can also add the trigger to your local update scripts:

```bash
# In your-project/scripts/update-documentation.sh
if [ -f "../scripts/github/trigger-docs-workflow.sh" ]; then
    ../scripts/github/trigger-docs-workflow.sh --project $(basename $(pwd))
fi
```

## 🎯 Features

- ✅ **Automatic Scheduling** - Runs daily to catch any missed updates
- ✅ **Manual Triggering** - Run on-demand from GitHub UI or command line
- ✅ **PR Validation** - Validates documentation in pull requests
- ✅ **Multi-Project Support** - Handles all projects in monorepo
- ✅ **Smart Detection** - Only updates projects with actual changes
- ✅ **Force Update** - Override change detection when needed
- ✅ **Detailed Reporting** - Shows exactly what changed
- ✅ **Claude Code Integration** - Trigger from terminal or VSCode

## 🚨 Requirements

Your repository must have:
- ✅ Projects with `scripts/update-documentation.sh`
- ✅ Projects with `scripts/validate-documentation.py`
- ✅ Python 3.11+ installed
- ✅ Git configured

## 🆘 Troubleshooting

### Workflow not appearing in Actions?
Check that `.github/workflows/auto-documentation.yml` is committed to your main branch.

### Trigger script fails?
```bash
# Verify token
curl -H "Authorization: Bearer $GITHUB_TOKEN" https://api.github.com/user

# Check token has 'repo' scope
```

### No changes committed?
The workflow only commits if it detects actual documentation changes. Use `--force` flag to override:
```bash
./scripts/github/trigger-docs-workflow.sh --force --token $GITHUB_TOKEN
```

### Validation errors?
Run validation locally to see detailed errors:
```bash
cd your-project/scripts
python validate-documentation.py
```

## 📖 Learn More

- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [Repository Dispatch Events](https://docs.github.com/en/rest/repos/repos#create-a-repository-dispatch-event)
- [Workflow Syntax](https://docs.github.com/en/actions/using-workflows/workflow-syntax-for-github-actions)

## 🔗 Links

- **Workflow Runs**: https://github.com/AlbertoDBP/Agentic/actions/workflows/auto-documentation.yml
- **Create Token**: https://github.com/settings/tokens
- **Repo Settings**: https://github.com/AlbertoDBP/Agentic/settings/actions

---

**Version:** 1.0.0  
**Created:** 2026-01-29  
**Maintained By:** Automated Documentation System
