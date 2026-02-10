# GitHub Workflow Quick Reference

## 🚀 Common Operations

### Trigger Documentation Update

```bash
# From anywhere in your repo
./scripts/github/trigger-docs-workflow.sh --token $GITHUB_TOKEN

# For specific project
./scripts/github/trigger-docs-workflow.sh \
  --project income-platform \
  --token $GITHUB_TOKEN

# Force update (ignore change detection)
./scripts/github/trigger-docs-workflow.sh \
  --force \
  --token $GITHUB_TOKEN
```

### Check Workflow Status

```bash
# Open in browser
open https://github.com/AlbertoDBP/Agentic/actions

# Or use GitHub CLI
gh run list --workflow=auto-documentation.yml
```

### Validate Documentation Locally

```bash
cd income-platform/scripts
python validate-documentation.py
```

## 📁 File Locations

```
.github/workflows/auto-documentation.yml    # Main workflow
scripts/github/trigger-docs-workflow.sh     # Trigger script
docs/SETUP_GUIDE.md                         # Full documentation
```

## 🔧 Setup Token

```bash
# 1. Get token from GitHub
open https://github.com/settings/tokens

# 2. Set environment variable
export GITHUB_TOKEN="ghp_your_token_here"

# 3. Add to shell config (optional)
echo 'export GITHUB_TOKEN="ghp_your_token_here"' >> ~/.zshrc
```

## ⚡ Quick Troubleshooting

### Workflow not running?
- Check: Settings → Actions → Workflow permissions → "Read and write"

### Trigger script fails?
```bash
# Test token
curl -H "Authorization: Bearer $GITHUB_TOKEN" https://api.github.com/user
```

### Validation fails?
```bash
# Run locally to see errors
cd your-project/scripts
python validate-documentation.py
```

### No changes committed?
```bash
# Force update
./scripts/github/trigger-docs-workflow.sh --force --token $GITHUB_TOKEN
```

## 📊 Workflow Triggers

| Trigger | When | How |
|---------|------|-----|
| Schedule | Daily 2 AM UTC | Automatic |
| Manual | On demand | GitHub UI or trigger script |
| Pull Request | When docs change | Automatic |
| Repository Dispatch | From Claude Code | trigger script |

## 🔗 Useful Links

- [Workflow Runs](https://github.com/AlbertoDBP/Agentic/actions/workflows/auto-documentation.yml)
- [Setup Guide](./SETUP_GUIDE.md)
- [GitHub Tokens](https://github.com/settings/tokens)

---

**Need help?** Check SETUP_GUIDE.md for detailed documentation.
