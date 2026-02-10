# GitHub Workflow Deployment Checklist

Use this checklist to ensure successful deployment of the automated documentation workflow.

## ✅ Pre-Installation Checklist

- [ ] Repository is accessible at `/Volumes/CH-DataOne/AlbertoDBP/Agentic`
- [ ] You have write access to the repository
- [ ] Git is configured with your credentials
- [ ] Projects have `scripts/update-documentation.sh`
- [ ] Projects have `scripts/validate-documentation.py`

## ✅ Installation Steps

### Option 1: Automated Installation (Recommended)

- [ ] Download all files from Claude
- [ ] Navigate to download directory
- [ ] Run installation script:
  ```bash
  chmod +x install-workflow.sh
  ./install-workflow.sh /Volumes/CH-DataOne/AlbertoDBP/Agentic
  ```
- [ ] Review files that were installed
- [ ] Commit and push to GitHub

### Option 2: Manual Installation

- [ ] Copy `.github/workflows/auto-documentation.yml` to repo
- [ ] Copy `scripts/trigger-docs-workflow.sh` to repo
- [ ] Make trigger script executable: `chmod +x scripts/github/trigger-docs-workflow.sh`
- [ ] Copy documentation files to repo
- [ ] Commit and push to GitHub

## ✅ GitHub Configuration

- [ ] Go to https://github.com/AlbertoDBP/Agentic/settings/actions
- [ ] Under "Workflow permissions":
  - [ ] Select "Read and write permissions"
  - [ ] Check "Allow GitHub Actions to create and approve pull requests"
  - [ ] Click "Save"
- [ ] Go to Actions tab
- [ ] Verify "Auto-Documentation" workflow appears

## ✅ Token Setup (for Manual Triggers)

- [ ] Visit https://github.com/settings/tokens
- [ ] Click "Generate new token (classic)"
- [ ] Give it a descriptive name (e.g., "Documentation Automation")
- [ ] Select the `repo` scope (full control of private repositories)
- [ ] Click "Generate token"
- [ ] Copy the token (you won't be able to see it again!)
- [ ] Set environment variable:
  ```bash
  export GITHUB_TOKEN="ghp_your_token_here"
  ```
- [ ] Add to shell config (optional):
  ```bash
  echo 'export GITHUB_TOKEN="ghp_your_token_here"' >> ~/.zshrc
  source ~/.zshrc
  ```

## ✅ Testing

### Test 1: Validate Locally

- [ ] Navigate to a project directory:
  ```bash
  cd /Volumes/CH-DataOne/AlbertoDBP/Agentic/income-platform/scripts
  ```
- [ ] Run validation:
  ```bash
  python validate-documentation.py
  ```
- [ ] Verify: Should pass without errors

### Test 2: Manual Trigger

- [ ] Run trigger script:
  ```bash
  ./scripts/github/trigger-docs-workflow.sh --token $GITHUB_TOKEN
  ```
- [ ] Expected output: "✓ Workflow triggered successfully!"
- [ ] Go to https://github.com/AlbertoDBP/Agentic/actions
- [ ] Verify: Workflow run appears and completes

### Test 3: Scheduled Run

- [ ] Wait for next scheduled run (2 AM UTC) OR
- [ ] Temporarily change schedule in workflow file to test sooner
- [ ] Verify workflow runs automatically

### Test 4: Pull Request Validation

- [ ] Create a test branch
- [ ] Make a documentation change
- [ ] Create a pull request
- [ ] Verify: Workflow runs and validates documentation

## ✅ Integration with Claude

### Claude Chat Integration

- [ ] Test workflow in Claude chat:
  1. [ ] Say "Document" to invoke orchestrator skill
  2. [ ] Download generated files
  3. [ ] Copy to local repo
  4. [ ] Commit and push
  5. [ ] Verify GitHub workflow runs

### Claude Code Integration

- [ ] Test from VSCode terminal:
  ```bash
  cd /Volumes/CH-DataOne/AlbertoDBP/Agentic/income-platform
  ../scripts/github/trigger-docs-workflow.sh --project income-platform
  ```
- [ ] Verify: Workflow triggered successfully

## ✅ Documentation Review

- [ ] Read `docs/github-workflow/SETUP_GUIDE.md`
- [ ] Bookmark `docs/github-workflow/QUICK_REFERENCE.md`
- [ ] Understand workflow triggers and behavior
- [ ] Know how to troubleshoot common issues

## ✅ Monitoring Setup

- [ ] Bookmark workflow runs page:
  https://github.com/AlbertoDBP/Agentic/actions/workflows/auto-documentation.yml
- [ ] Set up notifications (optional):
  - [ ] Email notifications for failures
  - [ ] Slack/Discord webhook (if desired)

## ✅ Maintenance

- [ ] Document any custom configuration changes
- [ ] Note any project-specific validation rules
- [ ] Set up periodic review of workflow runs
- [ ] Plan for token rotation (tokens expire)

## 🎉 Completion

When all items are checked:
- [ ] Workflow is fully operational
- [ ] Documentation is complete
- [ ] Team members are informed
- [ ] Testing is successful

## 📝 Notes

Use this space to document any project-specific details, custom configurations, or issues encountered:

```
[Add your notes here]
```

---

**Deployment Date:** _______________  
**Deployed By:** _______________  
**Token Expiration:** _______________  
**Next Review:** _______________
