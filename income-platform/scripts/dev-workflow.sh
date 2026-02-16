#!/bin/bash

# Income Fortress Platform - Development Workflow Helper
# Ensures consistency across Local → GitHub → Production

set -e

REPO_ROOT="/Volumes/CH-DataOne/AlbertoDBP/Agentic"
PROJECT_DIR="$REPO_ROOT/income-platform"

echo "=== Income Fortress Development Workflow ==="
echo ""

# Function: Show current environment status
show_status() {
    echo "📊 Environment Status:"
    echo ""
    echo "Local (Mac):"
    cd "$PROJECT_DIR"
    echo "  Branch: $(git branch --show-current)"
    echo "  Last commit: $(git log -1 --pretty=format:'%h - %s')"
    echo "  Uncommitted changes: $(git status --short | wc -l | xargs)"
    echo ""
    
    echo "GitHub:"
    git fetch origin main --quiet
    LOCAL=$(git rev-parse @)
    REMOTE=$(git rev-parse @{u})
    if [ $LOCAL = $REMOTE ]; then
        echo "  ✅ In sync with remote"
    else
        echo "  ⚠️  Out of sync - need to pull/push"
    fi
    echo ""
    
    echo "Production (Droplet):"
    ssh root@138.197.78.238 "cd /opt/Agentic/income-platform && git log -1 --pretty=format:'  Last deploy: %h - %s%n'"
    echo ""
}

# Function: Development cycle
dev_cycle() {
    echo "🔄 Starting Development Cycle..."
    echo ""
    
    # 1. Pull latest from GitHub
    echo "1️⃣ Pulling latest from GitHub..."
    cd "$PROJECT_DIR"
    git pull origin main
    
    # 2. Show what changed
    echo ""
    echo "2️⃣ Recent changes:"
    git log -3 --oneline
    
    # 3. Check for uncommitted work
    echo ""
    echo "3️⃣ Checking local changes..."
    if [ -n "$(git status --short)" ]; then
        echo "⚠️  You have uncommitted changes:"
        git status --short
    else
        echo "✅ Working directory clean"
    fi
    
    echo ""
    echo "Ready to develop!"
}

# Function: Deploy workflow
deploy_workflow() {
    echo "🚀 Deployment Workflow..."
    echo ""
    
    # 1. Update documentation
    echo "1️⃣ Running auto-update-docs..."
    "$PROJECT_DIR/scripts/auto-update-docs.sh"
    
    # 2. Deploy to production (Git handles sync)
    echo ""
    echo "2️⃣ Deploying to production..."
    ssh root@138.197.78.238 << 'DEPLOY'
cd /opt/Agentic/income-platform
git pull origin main
docker compose down
docker compose up -d
docker compose ps
DEPLOY
    
    echo ""
    echo "✅ Deployment complete!"
}

# Menu
case "$1" in
    status)
        show_status
        ;;
    dev)
        dev_cycle
        ;;
    deploy)
        deploy_workflow
        ;;
    *)
        echo "Usage: $0 {status|dev|deploy}"
        echo ""
        echo "Commands:"
        echo "  status  - Show environment sync status"
        echo "  dev     - Start development cycle (pull latest)"
        echo "  deploy  - Full deployment (docs → GitHub → production)"
        exit 1
        ;;
esac
