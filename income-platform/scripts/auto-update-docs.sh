#!/bin/bash

# Income Fortress Platform - Auto Documentation Updater (COMPREHENSIVE)
# Version: 3.0.0
# Purpose: Automatically detect ALL docs in Downloads, update repo, commit to GitHub
# Supports: MD, PDF, DOCX, PPTX, XLSX, Mermaid, SVG, PNG diagrams, TXT, SH
# Usage: ./auto-update-docs.sh

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
MAGENTA='\033[0;35m'
NC='\033[0m' # No Color

# Configuration
REPO_ROOT="/Volumes/CH-DataOne/AlbertoDBP/Agentic"
PROJECT_DIR="$REPO_ROOT/income-platform"
DOWNLOADS_DIR="/Volumes/CH-DataOne/AlbertoDBP/Downloads"  # Custom location
DOCS_DIR="$PROJECT_DIR/documentation"  # FIXED: Was "docs", now "documentation"
BACKUP_BASE="$HOME/Documents/income-fortress-docs-backups"
BACKUP_DIR="$BACKUP_BASE/backup-$(date +%Y%m%d-%H%M%S)"

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Income Fortress Auto Documentation Updater${NC}"
echo -e "${BLUE}Version 3.0.0 (COMPREHENSIVE)${NC}"
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

# Function: Categorize file by name, extension, and content
categorize_file() {
    local filepath="$1"
    local filename=$(basename "$filepath")
    local extension="${filename##*.}"
    
    # === DIAGRAMS FIRST (Highest Priority) ===
    case "$extension" in
        mmd|mermaid|svg)
            echo "diagrams"
            return
            ;;
        png|jpg|jpeg)
            # Only if filename suggests diagram
            if [[ "$filename" =~ (diagram|architecture|flow|chart|graph) ]]; then
                echo "diagrams"
                return
            fi
            ;;
    esac
    
    # === BINARY DOCUMENTS ===
    case "$extension" in
        pdf)
            # Categorize PDFs by filename patterns
            if [[ "$filename" =~ (deployment|operational|monitoring|disaster|checklist|runbook) ]]; then
                echo "deployment"
            elif [[ "$filename" =~ (agent|functional|specification) ]]; then
                echo "functional"
            elif [[ "$filename" =~ (implementation|technical|design) ]]; then
                echo "implementation"
            elif [[ "$filename" =~ (test|testing) ]]; then
                echo "testing"
            else
                echo "root"  # PDFs go to root by default
            fi
            return
            ;;
        docx|doc)
            # Word docs by filename patterns
            if [[ "$filename" =~ (deployment|operational|monitoring|disaster|checklist|runbook) ]]; then
                echo "deployment"
            elif [[ "$filename" =~ (agent|functional|specification) ]]; then
                echo "functional"
            elif [[ "$filename" =~ (implementation|technical|design) ]]; then
                echo "implementation"
            elif [[ "$filename" =~ (test|testing) ]]; then
                echo "testing"
            else
                echo "root"
            fi
            return
            ;;
        pptx|ppt)
            # Presentations by filename patterns
            if [[ "$filename" =~ (deployment|operational) ]]; then
                echo "deployment"
            elif [[ "$filename" =~ (architecture|design) ]]; then
                echo "implementation"
            else
                echo "root"
            fi
            return
            ;;
        xlsx|xls)
            # Spreadsheets by filename patterns
            if [[ "$filename" =~ (test|testing) ]]; then
                echo "testing"
            elif [[ "$filename" =~ (deployment|operational|checklist) ]]; then
                echo "deployment"
            else
                echo "root"
            fi
            return
            ;;
    esac
    
    # === MARKDOWN FILES ===
    if [[ "$extension" == "md" ]]; then
        case "$filename" in
            deployment-checklist*.md|operational-runbook*.md|monitoring-guide*.md|disaster-recovery*.md|*ADDENDUM.md|*deployment*.md|circuit-breaker*.md)
                echo "deployment"
                return
                ;;
            agent-[0-9]*.md|agents-[0-9]*.md|*functional*.md|*specification*.md)
                echo "functional"
                return
                ;;
            implementation-*.md|*technical*.md|*design*.md)
                echo "implementation"
                return
                ;;
            test-*.md|testing-*.md|*-test.md|*TEST*.md)
                echo "testing"
                return
                ;;
            DOCUMENTATION-MANIFEST.md|PACKAGE-SUMMARY.md|*-README.md|README*.md|CHANGELOG*.md)
                echo "root"
                return
                ;;
        esac
        
        # Fallback: Check content for markdown files
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
        return
    fi
    
    # === SCRIPTS ===
    if [[ "$extension" == "sh" ]]; then
        echo "scripts"
        return
    fi
    
    # === TEXT FILES ===
    if [[ "$extension" == "txt" ]]; then
        echo "misc"
        return
    fi
    
    # Default fallback
    echo "misc"
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
        diagrams)
            echo "$DOCS_DIR/diagrams"
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

# Find files - COMPREHENSIVE SCAN
NEW_DOCS=()

# === MARKDOWN FILES ===
while IFS= read -r file; do
    [ ! -s "$file" ] && continue
    filename=$(basename "$file")
    [[ "$filename" == .* ]] && continue
    NEW_DOCS+=("$file")
done < <(find "$DOWNLOADS_DIR" -maxdepth 1 -type f -name "*.md" -mtime -1 2>/dev/null)

# === BINARY DOCUMENTS ===
# PDF files
while IFS= read -r file; do
    [ ! -s "$file" ] && continue
    filename=$(basename "$file")
    [[ "$filename" == .* ]] && continue
    NEW_DOCS+=("$file")
done < <(find "$DOWNLOADS_DIR" -maxdepth 1 -type f -name "*.pdf" -mtime -1 2>/dev/null)

# Word documents
while IFS= read -r file; do
    [ ! -s "$file" ] && continue
    filename=$(basename "$file")
    [[ "$filename" == .* ]] && continue
    NEW_DOCS+=("$file")
done < <(find "$DOWNLOADS_DIR" -maxdepth 1 -type f \( -name "*.docx" -o -name "*.doc" \) -mtime -1 2>/dev/null)

# PowerPoint presentations
while IFS= read -r file; do
    [ ! -s "$file" ] && continue
    filename=$(basename "$file")
    [[ "$filename" == .* ]] && continue
    NEW_DOCS+=("$file")
done < <(find "$DOWNLOADS_DIR" -maxdepth 1 -type f \( -name "*.pptx" -o -name "*.ppt" \) -mtime -1 2>/dev/null)

# Excel spreadsheets
while IFS= read -r file; do
    [ ! -s "$file" ] && continue
    filename=$(basename "$file")
    [[ "$filename" == .* ]] && continue
    NEW_DOCS+=("$file")
done < <(find "$DOWNLOADS_DIR" -maxdepth 1 -type f \( -name "*.xlsx" -o -name "*.xls" \) -mtime -1 2>/dev/null)

# === DIAGRAM FILES ===
# Mermaid diagrams
while IFS= read -r file; do
    [ ! -s "$file" ] && continue
    filename=$(basename "$file")
    [[ "$filename" == .* ]] && continue
    NEW_DOCS+=("$file")
done < <(find "$DOWNLOADS_DIR" -maxdepth 1 -type f \( -name "*.mmd" -o -name "*.mermaid" \) -mtime -1 2>/dev/null)

# SVG diagrams
while IFS= read -r file; do
    [ ! -s "$file" ] && continue
    filename=$(basename "$file")
    [[ "$filename" == .* ]] && continue
    NEW_DOCS+=("$file")
done < <(find "$DOWNLOADS_DIR" -maxdepth 1 -type f -name "*.svg" -mtime -1 2>/dev/null)

# PNG/JPG diagrams (only if filename suggests diagram)
while IFS= read -r file; do
    [ ! -s "$file" ] && continue
    filename=$(basename "$file")
    [[ "$filename" == .* ]] && continue
    # Only include if filename suggests it's a diagram
    if [[ "$filename" =~ (diagram|architecture|flow|chart|graph) ]]; then
        NEW_DOCS+=("$file")
    fi
done < <(find "$DOWNLOADS_DIR" -maxdepth 1 -type f \( -name "*.png" -o -name "*.jpg" -o -name "*.jpeg" \) -mtime -1 2>/dev/null)

# === SCRIPTS ===
while IFS= read -r file; do
    [ ! -s "$file" ] && continue
    filename=$(basename "$file")
    [[ "$filename" == .* ]] && continue
    NEW_DOCS+=("$file")
done < <(find "$DOWNLOADS_DIR" -maxdepth 1 -type f -name "*.sh" -mtime -1 2>/dev/null)

# === TEXT FILES ===
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
    echo "  Markdown:      *.md"
    echo "  Documents:     *.pdf, *.docx, *.pptx, *.xlsx"
    echo "  Diagrams:      *.mmd, *.mermaid, *.svg, *diagram*.png"
    echo "  Scripts:       *.sh"
    echo "  Text:          *.txt"
    echo "  Modified:      Last 24 hours"
    echo ""
    echo "In: $DOWNLOADS_DIR"
    echo ""
    echo "Tip: If files are older than 24 hours, use quick-update-docs.sh instead"
    exit 0
fi

# Step 5: Categorize and display files
print_step "Categorizing files..."
echo ""

# Using simple arrays
CATEGORIES=()
TARGET_DIRS=()

for file in "${NEW_DOCS[@]}"; do
    filename=$(basename "$file")
    extension="${filename##*.}"
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
        testing)
            color=$MAGENTA
            ;;
        diagrams)
            color=$CYAN
            ;;
        scripts)
            color=$CYAN
            ;;
        root)
            color=$GREEN
            ;;
        *)
            color=$NC
            ;;
    esac
    
    # Show file type badge
    case $extension in
        pdf)
            badge="[PDF]"
            ;;
        docx|doc)
            badge="[DOC]"
            ;;
        pptx|ppt)
            badge="[PPT]"
            ;;
        xlsx|xls)
            badge="[XLS]"
            ;;
        mmd|mermaid)
            badge="[MMD]"
            ;;
        svg)
            badge="[SVG]"
            ;;
        png|jpg|jpeg)
            badge="[IMG]"
            ;;
        sh)
            badge="[SH]"
            ;;
        *)
            badge="[${extension^^}]"
            ;;
    esac
    
    echo -e "  ${color}[$category]${NC} $badge $filename → $(basename "$target_dir")/"
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
git status --short documentation/ scripts/ 2>/dev/null || git status --short

echo ""

# Step 10: Generate commit message
print_step "Generating commit message..."

# Count files by category and type
DEPLOYMENT_COUNT=0
FUNCTIONAL_COUNT=0
IMPLEMENTATION_COUNT=0
TESTING_COUNT=0
DIAGRAMS_COUNT=0
SCRIPT_COUNT=0
OTHER_COUNT=0

PDF_COUNT=0
DOCX_COUNT=0
PPTX_COUNT=0
XLSX_COUNT=0
MD_COUNT=0
DIAGRAM_FILE_COUNT=0

for ((i=0; i<${#NEW_DOCS[@]}; i++)); do
    category="${CATEGORIES[$i]}"
    file="${NEW_DOCS[$i]}"
    filename=$(basename "$file")
    extension="${filename##*.}"
    
    # Count by category
    case "$category" in
        deployment) ((DEPLOYMENT_COUNT++)) ;;
        functional) ((FUNCTIONAL_COUNT++)) ;;
        implementation) ((IMPLEMENTATION_COUNT++)) ;;
        testing) ((TESTING_COUNT++)) ;;
        diagrams) ((DIAGRAMS_COUNT++)) ;;
        scripts) ((SCRIPT_COUNT++)) ;;
        *) ((OTHER_COUNT++)) ;;
    esac
    
    # Count by type
    case "$extension" in
        pdf) ((PDF_COUNT++)) ;;
        docx|doc) ((DOCX_COUNT++)) ;;
        pptx|ppt) ((PPTX_COUNT++)) ;;
        xlsx|xls) ((XLSX_COUNT++)) ;;
        md) ((MD_COUNT++)) ;;
        mmd|mermaid|svg|png|jpg|jpeg) ((DIAGRAM_FILE_COUNT++)) ;;
    esac
done

# Build commit message
COMMIT_MSG="docs: update documentation ($COPIED_COUNT files)

File Types:
"

if [ $MD_COUNT -gt 0 ]; then
    COMMIT_MSG+="- Markdown: $MD_COUNT
"
fi
if [ $PDF_COUNT -gt 0 ]; then
    COMMIT_MSG+="- PDF: $PDF_COUNT
"
fi
if [ $DOCX_COUNT -gt 0 ]; then
    COMMIT_MSG+="- Word: $DOCX_COUNT
"
fi
if [ $PPTX_COUNT -gt 0 ]; then
    COMMIT_MSG+="- PowerPoint: $PPTX_COUNT
"
fi
if [ $XLSX_COUNT -gt 0 ]; then
    COMMIT_MSG+="- Excel: $XLSX_COUNT
"
fi
if [ $DIAGRAM_FILE_COUNT -gt 0 ]; then
    COMMIT_MSG+="- Diagrams: $DIAGRAM_FILE_COUNT
"
fi

COMMIT_MSG+="
"

# Add deployment files
if [ $DEPLOYMENT_COUNT -gt 0 ]; then
    COMMIT_MSG+="Deployment Documentation ($DEPLOYMENT_COUNT files):
"
    for ((i=0; i<${#NEW_DOCS[@]}; i++)); do
        if [ "${CATEGORIES[$i]}" = "deployment" ]; then
            filename=$(basename "${NEW_DOCS[$i]}")
            COMMIT_MSG+="- $filename
"
        fi
    done
    COMMIT_MSG+="
"
fi

# Add functional specs
if [ $FUNCTIONAL_COUNT -gt 0 ]; then
    COMMIT_MSG+="Functional Specifications ($FUNCTIONAL_COUNT files):
"
    for ((i=0; i<${#NEW_DOCS[@]}; i++)); do
        if [ "${CATEGORIES[$i]}" = "functional" ]; then
            filename=$(basename "${NEW_DOCS[$i]}")
            COMMIT_MSG+="- $filename
"
        fi
    done
    COMMIT_MSG+="
"
fi

# Add implementation specs
if [ $IMPLEMENTATION_COUNT -gt 0 ]; then
    COMMIT_MSG+="Implementation Specifications ($IMPLEMENTATION_COUNT files):
"
    for ((i=0; i<${#NEW_DOCS[@]}; i++)); do
        if [ "${CATEGORIES[$i]}" = "implementation" ]; then
            filename=$(basename "${NEW_DOCS[$i]}")
            COMMIT_MSG+="- $filename
"
        fi
    done
    COMMIT_MSG+="
"
fi

# Add testing docs
if [ $TESTING_COUNT -gt 0 ]; then
    COMMIT_MSG+="Testing Documentation ($TESTING_COUNT files):
"
    for ((i=0; i<${#NEW_DOCS[@]}; i++)); do
        if [ "${CATEGORIES[$i]}" = "testing" ]; then
            filename=$(basename "${NEW_DOCS[$i]}")
            COMMIT_MSG+="- $filename
"
        fi
    done
    COMMIT_MSG+="
"
fi

# Add diagrams
if [ $DIAGRAMS_COUNT -gt 0 ]; then
    COMMIT_MSG+="Diagrams ($DIAGRAMS_COUNT files):
"
    for ((i=0; i<${#NEW_DOCS[@]}; i++)); do
        if [ "${CATEGORIES[$i]}" = "diagrams" ]; then
            filename=$(basename "${NEW_DOCS[$i]}")
            COMMIT_MSG+="- $filename
"
        fi
    done
    COMMIT_MSG+="
"
fi

# Add scripts
if [ $SCRIPT_COUNT -gt 0 ]; then
    COMMIT_MSG+="Scripts ($SCRIPT_COUNT files):
"
    for ((i=0; i<${#NEW_DOCS[@]}; i++)); do
        if [ "${CATEGORIES[$i]}" = "scripts" ]; then
            filename=$(basename "${NEW_DOCS[$i]}")
            COMMIT_MSG+="- $filename
"
        fi
    done
    COMMIT_MSG+="
"
fi

# Add other files
if [ $OTHER_COUNT -gt 0 ]; then
    COMMIT_MSG+="Other Documentation ($OTHER_COUNT files):
"
    for ((i=0; i<${#NEW_DOCS[@]}; i++)); do
        category="${CATEGORIES[$i]}"
        if [ "$category" != "deployment" ] && [ "$category" != "functional" ] && \
           [ "$category" != "implementation" ] && [ "$category" != "testing" ] && \
           [ "$category" != "diagrams" ] && [ "$category" != "scripts" ]; then
            filename=$(basename "${NEW_DOCS[$i]}")
            COMMIT_MSG+="- $filename
"
        fi
    done
    COMMIT_MSG+="
"
fi

COMMIT_MSG+="Auto-generated via auto-update-docs.sh v3.0.0"

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
    echo "  git add documentation/ scripts/"
    echo "  git commit -m \"Your message\""
    exit 0
fi

# Step 12: Stage and commit
print_step "Staging changes..."
cd "$REPO_ROOT" || exit 1
git add income-platform/documentation/ 2>/dev/null || true
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
    echo "View changes: https://github.com/AlbertoDBP/Agentic/tree/main/income-platform/documentation"
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
echo "Documentation structure:"
echo "  - Markdown: $MD_COUNT"
echo "  - PDF: $PDF_COUNT"
echo "  - Word: $DOCX_COUNT"
echo "  - PowerPoint: $PPTX_COUNT"
echo "  - Excel: $XLSX_COUNT"
echo "  - Diagrams: $DIAGRAM_FILE_COUNT"
echo ""
echo "Next steps:"
echo "  1. Verify on GitHub"
echo "  2. Review documentation structure"
echo ""
