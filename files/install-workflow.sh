#!/bin/bash
# install-workflow.sh
# Installs the GitHub Actions documentation workflow to your Agentic repository

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
REPO_PATH="${1:-/Volumes/CH-DataOne/AlbertoDBP/Agentic}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo -e "${BLUE}═══════════════════════════════════════════════${NC}"
echo -e "${BLUE}  GitHub Workflow Installation Script${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════${NC}"
echo ""

# Validate repository path
if [ ! -d "$REPO_PATH" ]; then
    echo -e "${RED}✗ Error: Repository not found at $REPO_PATH${NC}"
    echo "Usage: $0 [repository-path]"
    exit 1
fi

if [ ! -d "$REPO_PATH/.git" ]; then
    echo -e "${RED}✗ Error: $REPO_PATH is not a git repository${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Repository found: $REPO_PATH${NC}"
echo ""

# Check for required files
echo -e "${YELLOW}Checking for required workflow files...${NC}"

REQUIRED_FILES=(
    ".github/workflows/auto-documentation.yml"
    "scripts/trigger-docs-workflow.sh"
)

MISSING_FILES=()
for file in "${REQUIRED_FILES[@]}"; do
    if [ ! -f "$SCRIPT_DIR/$file" ]; then
        MISSING_FILES+=("$file")
    fi
done

if [ ${#MISSING_FILES[@]} -gt 0 ]; then
    echo -e "${RED}✗ Missing required files:${NC}"
    for file in "${MISSING_FILES[@]}"; do
        echo "  - $file"
    done
    exit 1
fi

echo -e "${GREEN}✓ All required files found${NC}"
echo ""

# Install workflow file
echo -e "${YELLOW}Installing workflow file...${NC}"

mkdir -p "$REPO_PATH/.github/workflows"
cp "$SCRIPT_DIR/.github/workflows/auto-documentation.yml" \
   "$REPO_PATH/.github/workflows/auto-documentation.yml"

echo -e "${GREEN}✓ Workflow file installed${NC}"
echo ""

# Install trigger script
echo -e "${YELLOW}Installing trigger script...${NC}"

mkdir -p "$REPO_PATH/scripts/github"
cp "$SCRIPT_DIR/scripts/trigger-docs-workflow.sh" \
   "$REPO_PATH/scripts/github/trigger-docs-workflow.sh"
chmod +x "$REPO_PATH/scripts/github/trigger-docs-workflow.sh"

echo -e "${GREEN}✓ Trigger script installed${NC}"
echo ""

# Install documentation
echo -e "${YELLOW}Installing documentation...${NC}"

mkdir -p "$REPO_PATH/docs/github-workflow"
if [ -f "$SCRIPT_DIR/docs/SETUP_GUIDE.md" ]; then
    cp "$SCRIPT_DIR/docs/SETUP_GUIDE.md" \
       "$REPO_PATH/docs/github-workflow/"
fi
if [ -f "$SCRIPT_DIR/docs/QUICK_REFERENCE.md" ]; then
    cp "$SCRIPT_DIR/docs/QUICK_REFERENCE.md" \
       "$REPO_PATH/docs/github-workflow/"
fi

echo -e "${GREEN}✓ Documentation installed${NC}"
echo ""

# Summary
echo -e "${BLUE}═══════════════════════════════════════════════${NC}"
echo -e "${BLUE}  Installation Summary${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════${NC}"
echo ""
echo "Files installed:"
echo "  • .github/workflows/auto-documentation.yml"
echo "  • scripts/github/trigger-docs-workflow.sh"
echo "  • docs/github-workflow/SETUP_GUIDE.md"
echo "  • docs/github-workflow/QUICK_REFERENCE.md"
echo ""

# Next steps
echo -e "${YELLOW}Next Steps:${NC}"
echo ""
echo "1. Review the installed files:"
echo "   ${BLUE}cd $REPO_PATH${NC}"
echo "   ${BLUE}git status${NC}"
echo ""
echo "2. Commit and push to GitHub:"
echo "   ${BLUE}git add .github/workflows/ scripts/github/ docs/github-workflow/${NC}"
echo "   ${BLUE}git commit -m 'feat: add automated documentation workflow'${NC}"
echo "   ${BLUE}git push origin main${NC}"
echo ""
echo "3. Enable workflow permissions on GitHub:"
echo "   • Go to repo Settings → Actions → General"
echo "   • Select 'Read and write permissions'"
echo "   • Save"
echo ""
echo "4. Get a GitHub token for manual triggers:"
echo "   • Visit: https://github.com/settings/tokens"
echo "   • Create token with 'repo' scope"
echo "   • Set environment variable:"
echo "   ${BLUE}export GITHUB_TOKEN='ghp_your_token_here'${NC}"
echo ""
echo "5. Test the workflow:"
echo "   ${BLUE}./scripts/github/trigger-docs-workflow.sh --token \$GITHUB_TOKEN${NC}"
echo ""
echo -e "${GREEN}Installation complete!${NC}"
echo ""
echo "For detailed documentation, see:"
echo "  ${BLUE}$REPO_PATH/docs/github-workflow/SETUP_GUIDE.md${NC}"
echo ""
