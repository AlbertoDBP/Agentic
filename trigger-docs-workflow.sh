#!/bin/bash
# trigger-docs-workflow.sh
# Triggers the GitHub Actions documentation workflow via repository dispatch

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_OWNER="${GITHUB_REPO_OWNER:-AlbertoDBP}"
REPO_NAME="${GITHUB_REPO_NAME:-Agentic}"
GITHUB_TOKEN="${GITHUB_TOKEN:-}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Usage information
usage() {
    cat << EOF
Usage: $0 [OPTIONS]

Trigger the GitHub Actions documentation workflow remotely.

OPTIONS:
    -p, --project NAME       Specific project to document (optional)
    -f, --force             Force update even if no changes detected
    -t, --token TOKEN       GitHub personal access token (or set GITHUB_TOKEN env var)
    -o, --owner OWNER       Repository owner (default: $REPO_OWNER)
    -r, --repo REPO         Repository name (default: $REPO_NAME)
    -h, --help              Show this help message

EXAMPLES:
    # Trigger documentation update for all projects
    $0 --token ghp_xxxxx

    # Trigger for specific project
    $0 --project income-platform --token ghp_xxxxx

    # Force update
    $0 --force --token ghp_xxxxx

REQUIREMENTS:
    - GitHub Personal Access Token with 'repo' scope
    - curl command-line tool

GETTING A TOKEN:
    1. Go to https://github.com/settings/tokens
    2. Generate new token (classic)
    3. Select 'repo' scope
    4. Copy the token and use with --token flag or set GITHUB_TOKEN environment variable

EOF
    exit 1
}

# Parse command-line arguments
PROJECT=""
FORCE_UPDATE="false"

while [[ $# -gt 0 ]]; do
    case $1 in
        -p|--project)
            PROJECT="$2"
            shift 2
            ;;
        -f|--force)
            FORCE_UPDATE="true"
            shift
            ;;
        -t|--token)
            GITHUB_TOKEN="$2"
            shift 2
            ;;
        -o|--owner)
            REPO_OWNER="$2"
            shift 2
            ;;
        -r|--repo)
            REPO_NAME="$2"
            shift 2
            ;;
        -h|--help)
            usage
            ;;
        *)
            echo -e "${RED}Error: Unknown option: $1${NC}"
            usage
            ;;
    esac
done

# Validate GitHub token
if [ -z "$GITHUB_TOKEN" ]; then
    echo -e "${RED}Error: GitHub token is required${NC}"
    echo "Set GITHUB_TOKEN environment variable or use --token flag"
    echo "Run '$0 --help' for more information"
    exit 1
fi

# Build JSON payload
PAYLOAD='{"event_type": "update-docs"'

if [ -n "$PROJECT" ]; then
    PAYLOAD+=', "client_payload": {"project": "'"$PROJECT"'"'
    if [ "$FORCE_UPDATE" = "true" ]; then
        PAYLOAD+=', "force_update": true'
    fi
    PAYLOAD+='}'
elif [ "$FORCE_UPDATE" = "true" ]; then
    PAYLOAD+=', "client_payload": {"force_update": true}'
fi

PAYLOAD+='}'

echo -e "${YELLOW}Triggering documentation workflow...${NC}"
echo "Repository: $REPO_OWNER/$REPO_NAME"
if [ -n "$PROJECT" ]; then
    echo "Project: $PROJECT"
fi
if [ "$FORCE_UPDATE" = "true" ]; then
    echo "Force update: enabled"
fi
echo ""

# Trigger the workflow
RESPONSE=$(curl -s -w "\n%{http_code}" \
    -X POST \
    -H "Accept: application/vnd.github+json" \
    -H "Authorization: Bearer $GITHUB_TOKEN" \
    -H "X-GitHub-Api-Version: 2022-11-28" \
    "https://api.github.com/repos/$REPO_OWNER/$REPO_NAME/dispatches" \
    -d "$PAYLOAD")

HTTP_CODE=$(echo "$RESPONSE" | tail -n1)
BODY=$(echo "$RESPONSE" | sed '$d')

if [ "$HTTP_CODE" = "204" ]; then
    echo -e "${GREEN}✓ Workflow triggered successfully!${NC}"
    echo ""
    echo "View workflow runs at:"
    echo "https://github.com/$REPO_OWNER/$REPO_NAME/actions/workflows/auto-documentation.yml"
    exit 0
else
    echo -e "${RED}✗ Failed to trigger workflow${NC}"
    echo "HTTP Status: $HTTP_CODE"
    if [ -n "$BODY" ]; then
        echo "Response: $BODY"
    fi
    exit 1
fi
