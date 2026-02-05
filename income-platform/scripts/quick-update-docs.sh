#!/bin/bash

# Quick Documentation Update Script
# Usage: ./quick-update-docs.sh

set -e

# Configuration
REPO="/Volumes/CH-DataOne/AlbertoDBP/Agentic"
DOWNLOADS="/Volumes/CH-DataOne/AlbertoDBP/Downloads"  # Custom location

echo "📚 Income Fortress Documentation Updater"
echo ""

# Navigate to repo
cd "$REPO" || exit 1
echo "✓ Repository: $(pwd)"

# Pull latest
echo "⬇️  Pulling latest changes..."
git pull origin main

# Create directories
echo "📁 Creating documentation structure..."
mkdir -p income-platform/docs/{deployment,functional,implementation,testing,diagrams}

# Copy files
echo "📋 Copying files from Downloads..."
cp "$DOWNLOADS"/deployment-checklist.md income-platform/docs/deployment/ 2>/dev/null || echo "  ⊘ deployment-checklist.md not found"
cp "$DOWNLOADS"/operational-runbook.md income-platform/docs/deployment/ 2>/dev/null || echo "  ⊘ operational-runbook.md not found"
cp "$DOWNLOADS"/monitoring-guide.md income-platform/docs/deployment/ 2>/dev/null || echo "  ⊘ monitoring-guide.md not found"
cp "$DOWNLOADS"/disaster-recovery.md income-platform/docs/deployment/ 2>/dev/null || echo "  ⊘ disaster-recovery.md not found"
cp "$DOWNLOADS"/agent-01-market-data-sync.md income-platform/docs/functional/ 2>/dev/null || echo "  ⊘ agent-01-market-data-sync.md not found"
cp "$DOWNLOADS"/agent-03-income-scoring.md income-platform/docs/functional/ 2>/dev/null || echo "  ⊘ agent-03-income-scoring.md not found"
cp "$DOWNLOADS"/agents-5-6-7-9-summary.md income-platform/docs/functional/ 2>/dev/null || echo "  ⊘ agents-5-6-7-9-summary.md not found"
cp "$DOWNLOADS"/DOCUMENTATION-MANIFEST.md income-platform/docs/ 2>/dev/null || echo "  ⊘ DOCUMENTATION-MANIFEST.md not found"

echo "✓ Files copied"

# Show status
echo ""
echo "📊 Git status:"
git status --short income-platform/docs/

# Confirm commit
echo ""
read -p "Commit and push changes? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Aborted. Files copied but not committed."
    exit 0
fi

# Commit
echo "💾 Committing..."
git add income-platform/docs/
git commit -m "docs: add operational procedures and critical agent specs

- Add deployment checklist, operational runbook, monitoring guide
- Add disaster recovery plan with RTO/RPO targets
- Add Agent 1 (Market Data Sync) and Agent 3 (Income Scoring)
- Add Agents 5, 6, 7, 9 summary specifications

Ready for staging deployment."

# Push
echo "⬆️  Pushing to GitHub..."
git push origin main

echo ""
echo "✅ Done! Documentation updated on GitHub"
echo "🔗 View: https://github.com/AlbertoDBP/Agentic/tree/main/income-platform/docs"
