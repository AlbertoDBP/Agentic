#!/bin/bash

# Income Fortress Platform - Auto Documentation Updater (Fixed)
# Version: 2.1.0
# Purpose: Automatically detect new docs in Downloads, update repo, commit to GitHub, backup files
# Usage: ./auto-update-docs.sh

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Configuration
REPO_ROOT="/Volumes/CH-DataOne/AlbertoDBP/Agentic"
PROJECT_DIR="$REPO_ROOT/income-platform"
DOWNLOADS_DIR="/Volumes/CH-DataOne/AlbertoDBP/Downloads"  # Custom location
DOCS_DIR="$PROJECT_DIR/docs"
BACKUP_BASE="$HOME/Documents/income-fortress-docs-backups"
BACKUP_DIR="$BACKUP_BASE/backup-$(date +%Y%m%d-%H%M%S)"

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Income Fortress Auto Documentation Updater${NC}"
echo -e "${BLUE}Version 2.1.0 (Fixed)${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Function: Print step
print_step() {
    echo -e "${GREEN}[$(date +'%H:%M:%S')]${NC} $1"
}

# Function: Print error
print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function: Print warning
print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

# Function: Print info
print_info() {
    echo -e "${CYAN}[INFO]${NC} $1"
}

# Function: Categorize file by name and content
categorize_file() {
    local filepath="$1"
    local filename=$(basename "$filepath")
    
    # Check by filename patterns
    case "$filename" in
        deployment-checklist*.md|operational-runbook*.md|monitoring-guide*.md|disaster-recovery*.md|*ADDENDUM.md|*deployment*.md)
            echo "deployment"
            return
            ;;
        agent-[0-9]*.md|agents-[0-9]*.md)
            echo "functional"
            return
            ;;
        implementation-*.md)
            echo "implementation"
            return
            ;;
        test-*.md|testing-*.md|*-test.md)
            echo "testing"
            return
            ;;
        DOCUMENTATION-MANIFEST.md|PACKAGE-SUMMARY.md|*-README.md)
            echo "root"
            return
            ;;
        *.sh)
            echo "scripts"
            return
            ;;
        circuit-breaker*.md|*-update.md|*-UPDATE.md)
            echo "deployment"
            return
            ;;
    esac
    
    # Fallback: Check content
    if grep -qi "deployment\|docker\|infrastructure\|checklist" "$filepath" 2>/dev/null; then
        echo "deployment"
    elif grep -qi "agent.*specification\|Agent [0-9]" "$filepath" 2>/dev/null; then
        echo "functional"
    elif grep -qi "implementation\|technical design" "$filepath" 2>/dev/null; then
        echo "implementation"
    elif grep -qi "test.*matrix\|testing\|edge.*case" "$filepath" 2>/dev/null; then
        echo "testing"
    else
        echo "misc"
    fi
}

# Function: Get target directory
get_target_dir() {
    local category="$1"
    
    case "$category" in
        deployment)
            echo "$DOCS_DIR/deployment"
            ;;
        functional)
            echo "$DOCS_DIR/functional"
            ;;
        implementation)
            echo "$DOCS_DIR/implementation"
            ;;
        testing)
            echo "$DOCS_DIR/testing"
            ;;
        root)
            echo "$DOCS_DIR"
            ;;
        scripts)
            echo "$PROJECT_DIR/scripts"
            ;;
        *)
            echo "$DOCS_DIR/misc"
            ;;
    esac
}

# Step 1: Verify repository location
print_step "Verifying repository location..."
if [ ! -d "$REPO_ROOT" ]; then
    print_error "Repository root not found: $REPO_ROOT"
    exit 1
fi

cd "$REPO_ROOT" || exit 1
print_info "Repository: $(pwd)"

# Step 2: Verify Git repository
print_step "Verifying Git repository..."
if [ ! -d ".git" ]; then
    print_error "Not a Git repository: $REPO_ROOT"
    exit 1
fi

# Step 3: Pull latest changes
print_step "Pulling latest changes from remote..."
git pull origin main || {
    print_warning "Failed to pull from remote. Continuing anyway..."
}

# Step 4: Scan for new documentation files
print_step "Scanning Downloads for documentation files..."
print_info "Looking in: $DOWNLOADS_DIR"

# Find files (simpler approach - no -print0)
NEW_DOCS=()

# Find markdown files modified in last 24 hours
while IFS= read -r file; do
    # Skip if empty
    [ ! -s "$file" ] && continue
    
    # Skip hidden files
    filename=$(basename "$file")
    [[ "$filename" == .* ]] && continue
    
    NEW_DOCS+=("$file")
done < <(find "$DOWNLOADS_DIR" -maxdepth 1 -type f -name "*.md" -mtime -1 2>/dev/null)

# Find shell scripts
while IFS= read -r file; do
    [ ! -s "$file" ] && continue
    filename=$(basename "$file")
    [[ "$filename" == .* ]] && continue
    NEW_DOCS+=("$file")
done < <(find "$DOWNLOADS_DIR" -maxdepth 1 -type f -name "*.sh" -mtime -1 2>/dev/null)

# Find text files
while IFS= read -r file; do
    [ ! -s "$file" ] && continue
    filename=$(basename "$file")
    [[ "$filename" == .* ]] && continue
    NEW_DOCS+=("$file")
done < <(find "$DOWNLOADS_DIR" -maxdepth 1 -type f -name "*.txt" -mtime -1 2>/dev/null)

NUM_FILES=${#NEW_DOCS[@]}
print_info "Found $NUM_FILES file(s)"

if [ "$NUM_FILES" -eq 0 ]; then
    print_warning "No new documentation files found"
    echo ""
    echo "Looking for:"
    echo "  - *.md (Markdown files)"
    echo "  - *.sh (Shell scripts)"
    echo "  - *.txt (Text files)"
    echo "  - Modified in last 24 hours"
    echo ""
    echo "In: $DOWNLOADS_DIR"
    echo ""
    echo "Tip: If files are older than 24 hours, use quick-update-docs.sh instead"
    exit 0
fi

# Step 5: Categorize and display files
print_step "Categorizing files..."
echo ""

# Using simple arrays instead of associative arrays (bash 3 compatibility)
CATEGORIES=()
TARGET_DIRS=()

for file in "${NEW_DOCS[@]}"; do
    filename=$(basename "$file")
    category=$(categorize_file "$file")
    target_dir=$(get_target_dir "$category")
    
    CATEGORIES+=("$category")
    TARGET_DIRS+=("$target_dir")
    
    # Color code by category
    case $category in
        deployment)
            color=$YELLOW
            ;;
        functional)
            color=$GREEN
            ;;
        implementation)
            color=$BLUE
            ;;
        scripts)
            color=$CYAN
            ;;
        *)
            color=$NC
            ;;
    esac
    
    echo -e "  ${color}[$category]${NC} $filename → $(basename "$target_dir")/"
done

echo ""

# Step 6: Confirm with user
read -p "Copy these files to repository? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    print_error "Aborted by user."
    exit 1
fi

# Step 7: Create directory structure
print_step "Creating documentation directory structure..."
mkdir -p "$DOCS_DIR/deployment"
mkdir -p "$DOCS_DIR/functional"
mkdir -p "$DOCS_DIR/implementation"
mkdir -p "$DOCS_DIR/testing"
mkdir -p "$DOCS_DIR/diagrams"
mkdir -p "$DOCS_DIR/misc"
mkdir -p "$PROJECT_DIR/scripts"

# Step 8: Copy files to repository
print_step "Copying files to repository..."
COPIED_COUNT=0
COPIED_FILES=()

index=0
for file in "${NEW_DOCS[@]}"; do
    filename=$(basename "$file")
    target_dir="${TARGET_DIRS[$index]}"
    category="${CATEGORIES[$index]}"
    
    # Copy file
    cp "$file" "$target_dir/" 2>/dev/null
    
    if [ $? -eq 0 ]; then
        ((COPIED_COUNT++))
        COPIED_FILES+=("$filename")
        print_info "  ✓ Copied: $filename → $(basename "$target_dir")/"
        
        # Make scripts executable
        if [[ "$filename" =~ \.sh$ ]]; then
            chmod +x "$target_dir/$filename"
            print_info "    Made executable: $filename"
        fi
    else
        print_error "  ✗ Failed to copy: $filename"
    fi
    
    ((index++))
done

echo ""
print_step "Successfully copied $COPIED_COUNT file(s)"

# Step 9: Show Git status
print_step "Git status:"
cd "$PROJECT_DIR" || exit 1
git status --short docs/ scripts/ 2>/dev/null || git status --short

echo ""

# Step 10: Generate commit message
print_step "Generating commit message..."

# Count files by category
DEPLOYMENT_COUNT=0
FUNCTIONAL_COUNT=0
IMPLEMENTATION_COUNT=0
TESTING_COUNT=0
SCRIPT_COUNT=0
OTHER_COUNT=0

for category in "${CATEGORIES[@]}"; do
    case "$category" in
        deployment) ((DEPLOYMENT_COUNT++)) ;;
        functional) ((FUNCTIONAL_COUNT++)) ;;
        implementation) ((IMPLEMENTATION_COUNT++)) ;;
        testing) ((TESTING_COUNT++)) ;;
        scripts) ((SCRIPT_COUNT++)) ;;
        *) ((OTHER_COUNT++)) ;;
    esac
done

# Build commit message
COMMIT_MSG="docs: update documentation ($COPIED_COUNT files)

"

# Add deployment files
if [ $DEPLOYMENT_COUNT -gt 0 ]; then
    COMMIT_MSG+="Deployment Documentation ($DEPLOYMENT_COUNT files):
"
    index=0
    for file in "${NEW_DOCS[@]}"; do
        if [ "${CATEGORIES[$index]}" = "deployment" ]; then
            filename=$(basename "$file")
            COMMIT_MSG+="- $filename
"
        fi
        ((index++))
    done
    COMMIT_MSG+="
"
fi

# Add functional specs
if [ $FUNCTIONAL_COUNT -gt 0 ]; then
    COMMIT_MSG+="Functional Specifications ($FUNCTIONAL_COUNT files):
"
    index=0
    for file in "${NEW_DOCS[@]}"; do
        if [ "${CATEGORIES[$index]}" = "functional" ]; then
            filename=$(basename "$file")
            COMMIT_MSG+="- $filename
"
        fi
        ((index++))
    done
    COMMIT_MSG+="
"
fi

# Add implementation specs
if [ $IMPLEMENTATION_COUNT -gt 0 ]; then
    COMMIT_MSG+="Implementation Specifications ($IMPLEMENTATION_COUNT files):
"
    index=0
    for file in "${NEW_DOCS[@]}"; do
        if [ "${CATEGORIES[$index]}" = "implementation" ]; then
            filename=$(basename "$file")
            COMMIT_MSG+="- $filename
"
        fi
        ((index++))
    done
    COMMIT_MSG+="
"
fi

# Add testing docs
if [ $TESTING_COUNT -gt 0 ]; then
    COMMIT_MSG+="Testing Documentation ($TESTING_COUNT files):
"
    index=0
    for file in "${NEW_DOCS[@]}"; do
        if [ "${CATEGORIES[$index]}" = "testing" ]; then
            filename=$(basename "$file")
            COMMIT_MSG+="- $filename
"
        fi
        ((index++))
    done
    COMMIT_MSG+="
"
fi

# Add scripts
if [ $SCRIPT_COUNT -gt 0 ]; then
    COMMIT_MSG+="Scripts ($SCRIPT_COUNT files):
"
    index=0
    for file in "${NEW_DOCS[@]}"; do
        if [ "${CATEGORIES[$index]}" = "scripts" ]; then
            filename=$(basename "$file")
            COMMIT_MSG+="- $filename
"
        fi
        ((index++))
    done
    COMMIT_MSG+="
"
fi

# Add other files
if [ $OTHER_COUNT -gt 0 ]; then
    COMMIT_MSG+="Other Documentation ($OTHER_COUNT files):
"
    index=0
    for file in "${NEW_DOCS[@]}"; do
        category="${CATEGORIES[$index]}"
        if [ "$category" != "deployment" ] && [ "$category" != "functional" ] && \
           [ "$category" != "implementation" ] && [ "$category" != "testing" ] && \
           [ "$category" != "scripts" ]; then
            filename=$(basename "$file")
            COMMIT_MSG+="- $filename
"
        fi
        ((index++))
    done
    COMMIT_MSG+="
"
fi

COMMIT_MSG+="Auto-generated via auto-update-docs.sh v2.1.0"

# Show commit message
echo ""
echo -e "${CYAN}Commit message:${NC}"
echo "---"
echo "$COMMIT_MSG"
echo "---"
echo ""

# Step 11: Confirm commit
read -p "Commit these changes? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    print_warning "Changes copied but not committed."
    echo "To commit manually:"
    echo "  cd $PROJECT_DIR"
    echo "  git add docs/ scripts/"
    echo "  git commit -m \"Your message\""
    exit 0
fi

# Step 12: Stage and commit
print_step "Staging changes..."
cd "$REPO_ROOT" || exit 1
git add income-platform/docs/ 2>/dev/null || true
git add income-platform/scripts/ 2>/dev/null || true

print_step "Committing changes..."
git commit -m "$COMMIT_MSG"

if [ $? -eq 0 ]; then
    print_info "Commit successful!"
else
    print_error "Commit failed!"
    exit 1
fi

# Step 13: Show commit
print_step "Commit details:"
git log -1 --stat

echo ""

# Step 14: Push to GitHub
read -p "Push to GitHub? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    print_warning "Changes committed locally but not pushed."
    echo "To push later:"
    echo "  cd $REPO_ROOT"
    echo "  git push origin main"
    exit 0
fi

print_step "Pushing to GitHub..."
git push origin main

if [ $? -eq 0 ]; then
    echo ""
    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}✓ SUCCESS! Documentation updated on GitHub${NC}"
    echo -e "${GREEN}========================================${NC}"
    echo ""
    echo "View changes: https://github.com/AlbertoDBP/Agentic/tree/main/income-platform/docs"
    echo ""
else
    print_error "Failed to push to GitHub"
    echo "Your commit is saved locally. Push manually when ready:"
    echo "  cd $REPO_ROOT"
    echo "  git push origin main"
    exit 1
fi

# Step 15: Backup processed files
echo ""
read -p "Move processed files to backup folder? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    print_warning "Files remain in Downloads folder."
    exit 0
fi

print_step "Creating backup directory..."
mkdir -p "$BACKUP_DIR"

print_step "Moving processed files to backup..."
MOVED_COUNT=0

for file in "${NEW_DOCS[@]}"; do
    filename=$(basename "$file")
    
    if [ -f "$file" ]; then
        mv "$file" "$BACKUP_DIR/" 2>/dev/null
        if [ $? -eq 0 ]; then
            ((MOVED_COUNT++))
            print_info "  ✓ Moved: $filename"
        else
            print_error "  ✗ Failed to move: $filename"
        fi
    fi
done

echo ""
print_step "Backup complete!"
print_info "Location: $BACKUP_DIR"
print_info "Files backed up: $MOVED_COUNT"

# Cleanup empty backup directory
if [ $MOVED_COUNT -eq 0 ]; then
    rmdir "$BACKUP_DIR" 2>/dev/null
fi

# Final summary
echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}All Done!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "Summary:"
echo "  Files processed: $COPIED_COUNT"
echo "  Files backed up: $MOVED_COUNT"
echo "  Commit: ✓"
echo "  Push: ✓"
echo ""
echo "Next steps:"
echo "  1. Verify on GitHub"
echo "  2. Deploy to staging"
echo ""
