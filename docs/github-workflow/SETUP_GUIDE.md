# GitHub Actions Documentation Automation

Complete setup guide for automated documentation workflow in your Agentic monorepo.

## 📋 Table of Contents

- [Overview](#overview)
- [Quick Start](#quick-start)
- [Installation](#installation)
- [Configuration](#configuration)
- [Usage](#usage)
- [Triggering from Claude Code](#triggering-from-claude-code)
- [Workflow Details](#workflow-details)
- [Troubleshooting](#troubleshooting)

## Overview

This GitHub Actions workflow automatically:
- ✅ Generates documentation when changes are detected
- ✅ Validates all documentation files
- ✅ Commits and pushes changes automatically
- ✅ Runs on schedule (daily)
- ✅ Can be triggered manually or from Claude Code
- ✅ Validates documentation in pull requests

## Quick Start

### 1. Install Workflow Files

Copy the files to your repository:

```bash
cd /Volumes/CH-DataOne/AlbertoDBP/Agentic

# Create GitHub workflows directory if it doesn't exist
mkdir -p .github/workflows

# Copy the main workflow file
cp /path/to/auto-documentation.yml .github/workflows/

# Copy the trigger script (optional, for manual triggering)
mkdir -p scripts/github
cp /path/to/trigger-docs-workflow.sh scripts/github/
chmod +x scripts/github/trigger-docs-workflow.sh
```

### 2. Commit and Push

```bash
git add .github/workflows/auto-documentation.yml
git add scripts/github/trigger-docs-workflow.sh
git commit -m "feat: add automated documentation workflow"
git push origin main
```

### 3. Verify Installation

Go to your GitHub repository → Actions tab. You should see the "Auto-Documentation" workflow.

## Installation

### Prerequisites

Your repository must have:
- ✅ Projects with `scripts/update-documentation.sh`
- ✅ Projects with `scripts/validate-documentation.py`
- ✅ Python 3.11+ (for validation)
- ✅ Git configuration

### Repository Structure

The workflow expects this structure:

```
Agentic/
├── .github/
│   └── workflows/
│       └── auto-documentation.yml
├── income-platform/
│   ├── docs/
│   └── scripts/
│       ├── update-documentation.sh
│       └── validate-documentation.py
├── another-platform/
│   ├── docs/
│   └── scripts/
│       ├── update-documentation.sh
│       └── validate-documentation.py
└── scripts/
    └── github/
        └── trigger-docs-workflow.sh
```

## Configuration

### Workflow Schedule

Edit `.github/workflows/auto-documentation.yml` to change the schedule:

```yaml
schedule:
  - cron: '0 2 * * *'  # Daily at 2 AM UTC
```

Common schedules:
- `0 */6 * * *` - Every 6 hours
- `0 0 * * 0` - Weekly on Sunday
- `0 9 * * 1-5` - Weekdays at 9 AM

### Environment Variables

Set in the workflow file or GitHub repository settings:

```yaml
env:
  PYTHON_VERSION: '3.11'
  DOCS_PATH: '.'
  COMMIT_MESSAGE_PREFIX: 'docs(auto):'
```

### GitHub Token Permissions

The workflow needs write permissions. In your repo:
1. Go to Settings → Actions → General
2. Under "Workflow permissions", select "Read and write permissions"
3. Save

## Usage

### Automatic Triggers

The workflow runs automatically:

1. **Schedule**: Daily at 2 AM UTC (configurable)
2. **Pull Requests**: When docs files are changed
3. **Repository Changes**: When project files are modified

### Manual Trigger (GitHub UI)

1. Go to Actions → Auto-Documentation
2. Click "Run workflow"
3. Optional: Specify a project name
4. Optional: Enable "Force update"
5. Click "Run workflow"

### Manual Trigger (Command Line)

Using the trigger script:

```bash
# Trigger for all projects
./scripts/github/trigger-docs-workflow.sh --token ghp_your_token_here

# Trigger for specific project
./scripts/github/trigger-docs-workflow.sh \
  --project income-platform \
  --token ghp_your_token_here

# Force update (even if no changes)
./scripts/github/trigger-docs-workflow.sh \
  --force \
  --token ghp_your_token_here
```

## Triggering from Claude Code

### Setup

1. **Get GitHub Personal Access Token**
   ```
   1. Go to https://github.com/settings/tokens
   2. Click "Generate new token (classic)"
   3. Select 'repo' scope
   4. Generate and copy the token
   ```

2. **Set Environment Variable**
   ```bash
   # Add to your ~/.zshrc or ~/.bashrc
   export GITHUB_TOKEN="ghp_your_token_here"
   ```

3. **Create Alias (Optional)**
   ```bash
   # Add to your shell config
   alias trigger-docs='~/path/to/Agentic/scripts/github/trigger-docs-workflow.sh'
   ```

### Usage in Claude Code

After completing work in Claude Code:

```bash
# From VSCode terminal
cd /Volumes/CH-DataOne/AlbertoDBP/Agentic/income-platform

# Trigger documentation update
../scripts/github/trigger-docs-workflow.sh --project income-platform

# Or if you set the alias
trigger-docs --project income-platform
```

### Automated Integration

Add to your platform's update script:

```bash
# In income-platform/scripts/update-documentation.sh

# ... existing documentation generation ...

# Trigger GitHub workflow
if [ -f "../scripts/github/trigger-docs-workflow.sh" ]; then
    echo "Triggering GitHub workflow..."
    ../scripts/github/trigger-docs-workflow.sh --project income-platform
fi
```

## Workflow Details

### What the Workflow Does

1. **Detect Changes**
   - Checks git history for modified files
   - Identifies which projects changed

2. **Generate Documentation**
   - Runs `update-documentation.sh` for each changed project
   - Updates CHANGELOG, ADRs, and other docs

3. **Validate**
   - Runs `validate-documentation.py`
   - Checks for broken links, missing files, etc.

4. **Commit & Push**
   - Creates commit with all changes
   - Pushes to the same branch
   - Uses descriptive commit message

5. **Report**
   - Creates workflow summary
   - Lists modified files
   - Shows validation results

### Workflow Outputs

Check workflow runs:
1. Go to Actions → Auto-Documentation
2. Click on a workflow run
3. View the summary and logs

## Troubleshooting

### Workflow Not Running

**Check permissions:**
```
Settings → Actions → General → Workflow permissions
✓ Read and write permissions
```

**Verify workflow file:**
```bash
# Check if file exists
ls -la .github/workflows/auto-documentation.yml

# Validate YAML syntax
cat .github/workflows/auto-documentation.yml | python -m yaml
```

### Validation Failures

**Run validation locally:**
```bash
cd income-platform/scripts
python validate-documentation.py
```

**Common issues:**
- Missing required files
- Broken internal links
- Invalid YAML in frontmatter
- Inconsistent naming

### Trigger Script Fails

**Check token:**
```bash
# Test token validity
curl -H "Authorization: Bearer $GITHUB_TOKEN" \
  https://api.github.com/user
```

**Debug mode:**
```bash
# Run with verbose output
bash -x ./scripts/github/trigger-docs-workflow.sh --token $GITHUB_TOKEN
```

### No Changes Committed

**Possible reasons:**
1. No actual documentation changes detected
2. Validation failed (check logs)
3. Git configuration issues

**Force update:**
```bash
./scripts/github/trigger-docs-workflow.sh --force --token $GITHUB_TOKEN
```

## Advanced Configuration

### Multiple Branches

Modify workflow to run on specific branches:

```yaml
on:
  push:
    branches:
      - main
      - develop
```

### Conditional Project Updates

Only update specific projects:

```yaml
env:
  ALLOWED_PROJECTS: "income-platform,another-platform"
```

### Custom Commit Messages

Change the commit message format:

```yaml
env:
  COMMIT_MESSAGE_PREFIX: 'docs:'
```

### Notifications

Add Slack/Discord notifications:

```yaml
- name: Notify on Failure
  if: failure()
  uses: 8398a7/action-slack@v3
  with:
    status: ${{ job.status }}
    webhook_url: ${{ secrets.SLACK_WEBHOOK }}
```

## Integration with platform-documentation-orchestrator

The GitHub workflow complements your Claude skill:

```
┌─────────────────────────────────────────────┐
│ Claude (chat or VSCode)                     │
│ ↓                                           │
│ 1. User: "Document"                        │
│ 2. Skill generates docs locally            │
│ 3. Files saved to /mnt/user-data/outputs   │
└─────────────────┬───────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────┐
│ Local Machine                               │
│ ↓                                           │
│ 4. User copies files to repo               │
│ 5. git commit && git push                  │
│    OR                                       │
│ 6. Run trigger-docs-workflow.sh            │
└─────────────────┬───────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────┐
│ GitHub Actions                              │
│ ↓                                           │
│ 7. Workflow triggers                       │
│ 8. Validates documentation                 │
│ 9. Auto-commits if changes detected        │
└─────────────────────────────────────────────┘
```

## Support

For issues or questions:

1. Check GitHub Actions logs
2. Run validation scripts locally
3. Review this documentation
4. Check GitHub Issues in your repo

---

**Setup Date:** 2026-01-29
**Maintained By:** GitHub Actions Automation
**Version:** 1.0.0
