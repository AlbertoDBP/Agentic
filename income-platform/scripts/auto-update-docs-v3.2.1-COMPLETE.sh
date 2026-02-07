#!/bin/bash

# Income Fortress Platform - Auto Documentation Updater (COMPLETE)
# Version: 3.2.1 COMPLETE
# Purpose: Automatically detect ALL docs in Downloads, update repo, commit to GitHub
# Supports: MD, PDF, DOCX, PPTX, XLSX, PY, SQL, Mermaid, SVG, PNG, YML, Dockerfile, Templates
# FIX: macOS bash compatibility (${extension^^} → tr command)
# RESTORED: Full workflow with Git commit/push and file backup
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
DOWNLOADS_DIR="/Volumes/CH-DataOne/AlbertoDBP/Downloads"
DOCS_DIR="$PROJECT_DIR/documentation"
BACKUP_BASE="$HOME/Documents/income-fortress-docs-backups"
BACKUP_DIR="$BACKUP_BASE/backup-$(date +%Y%m%d-%H%M%S)"

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Income Fortress Auto Documentation Updater${NC}"
echo -e "${BLUE}Version 3.2.1 COMPLETE (Full Workflow)${NC}"
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
    
    # Special case: Dockerfile (no extension)
    if [[ "$filename" =~ ^Dockerfile ]]; then
        echo "deployment"
        return
    fi
    
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
    
    # === CONFIGURATION FILES ===
    case "$extension" in
        yml|yaml)
            # YAML files - check filename patterns
            if [[ "$filename" =~ (docker-compose|compose) ]]; then
                echo "deployment"
            elif [[ "$filename" =~ (ci|deploy|workflow) ]]; then
                echo "deployment"
            elif [[ "$filename" =~ (test) ]]; then
                echo "testing"
            elif [[ "$filename" =~ (config) ]]; then
                echo "implementation"
            else
                echo "deployment"  # Default for YAML
            fi
            return
            ;;
        json)
            # JSON files
            if [[ "$filename" =~ (package\.json|tsconfig\.json|pyproject\.json) ]]; then
                echo "implementation"
            elif [[ "$filename" =~ (test) ]]; then
                echo "testing"
            elif [[ "$filename" =~ (schema|config) ]]; then
                echo "implementation"
            else
                echo "implementation"  # Default for JSON
            fi
            return
            ;;
        toml)
            # TOML files
            if [[ "$filename" =~ (pyproject\.toml) ]]; then
                echo "implementation"
            elif [[ "$filename" =~ (config) ]]; then
                echo "implementation"
            else
                echo "implementation"
            fi
            return
            ;;
        ini|cfg)
            # Config files
            if [[ "$filename" =~ (setup\.cfg) ]]; then
                echo "implementation"
            elif [[ "$filename" =~ (config) ]]; then
                echo "implementation"
            else
                echo "implementation"
            fi
            return
            ;;
        template)
            # Template files - check filename patterns
            if [[ "$filename" =~ (env|environment) ]]; then
                echo "deployment"
            elif [[ "$filename" =~ (sql|query) ]]; then
                echo "implementation"
            elif [[ "$filename" =~ (email|notification) ]]; then
                echo "misc"
            else
                echo "misc"
            fi
            return
            ;;
    esac
    
    # === CODE FILES (Python, SQL) ===
    case "$extension" in
        py)
            # Python files - check filename patterns
            if [[ "$filename" =~ (test_|_test\.py|test\.py) ]]; then
                echo "testing"
            elif [[ "$filename" =~ (deploy|migration|setup) ]]; then
                echo "deployment"
            elif [[ "$filename" =~ (agent|scorer|analyzer) ]]; then
                echo "implementation"
            else
                echo "implementation"  # Default for Python
            fi
            return
            ;;
        sql)
            # SQL files - check filename patterns
            if [[ "$filename" =~ (test|sample) ]]; then
                echo "testing"
            elif [[ "$filename" =~ (migration|schema|ddl|setup|init) ]]; then
                echo "deployment"
            elif [[ "$filename" =~ (query|view|procedure|function) ]]; then
                echo "implementation"
            else
                echo "implementation"  # Default for SQL
            fi
            return
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
        csv)
            # CSV files
            if [[ "$filename" =~ (test|sample) ]]; then
                echo "testing"
            elif [[ "$filename" =~ (data) ]]; then
                echo "misc"
            else
                echo "misc"
            fi
            return
            ;;
    esac
    
    # === MARKDOWN FILES ===
    if [[ "$extension" == "md" ]]; then
        case "$filename" in
            deployment-checklist*.md|operational-runbook*.md|monitoring-guide*.md|disaster-recovery*.md|*ADDENDUM.md|*deployment*.md|circuit-breaker*.md|DIGITALOCEAN*.md)
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

while IFS= read -r file; do
    [ ! -s "$file" ] && continue
    filename=$(basename "$file")
    [[ "$filename" == .* ]] && continue
    [[ "$filename" == *.DS_Store ]] && continue
    # SECURITY: Never upload .env files (contain secrets)
    [[ "$filename" == .env ]] && continue
    [[ "$filename" == .env.* ]] && [[ "$filename" != .env.example ]] && continue
    NEW_DOCS+=("$file")
done < <(find "$DOWNLOADS_DIR" -maxdepth 1 -type f -mtime -1 \
    \( -name "*.md" -o -name "*.pdf" -o -name "*.docx" -o -name "*.doc" \
    -o -name "*.pptx" -o -name "*.ppt" -o -name "*.xlsx" -o -name "*.xls" \
    -o -name "*.py" -o -name "*.sql" -o -name "*.yml" -o -name "*.yaml" \
    -o -name "*.json" -o -name "*.toml" -o -name "*.ini" -o -name "*.cfg" \
    -o -name "*.template" -o -name "*.csv" -o -name "*.mmd" -o -name "*.mermaid" \
    -o -name "*.svg" -o -name "*.png" -o -name "*.jpg" -o -name "*.jpeg" \
    -o -name "*.sh" -o -name "*.txt" -o -name "Dockerfile*" \) 2>/dev/null)

NUM_FILES=${#NEW_DOCS[@]}
print_info "Found $NUM_FILES file(s)"

if [ "$NUM_FILES" -eq 0 ]; then
    print_warning "No new documentation files found"
    echo ""
    echo "Looking for files modified in last 24 hours in:"
    echo "  $DOWNLOADS_DIR"
    echo ""
    echo "Supported file types:"
    echo "  Documents:  MD, PDF, DOCX, PPTX, XLSX"
    echo "  Code:       PY, SQL, SH"
    echo "  Config:     YML, JSON, TOML, INI, CFG, template"
    echo "  Container:  Dockerfile"
    echo "  Diagrams:   MMD, Mermaid, SVG, PNG"
    echo "  Data:       CSV, TXT"
    exit 0
fi

# Step 5: Categorize and display files
print_step "Categorizing files..."
echo ""

CATEGORIES=()
TARGET_DIRS=()

for file in "${NEW_DOCS[@]}"; do
    filename=$(basename "$file")
    
    # Get extension (handle Dockerfile specially)
    if [[ "$filename" =~ ^Dockerfile ]]; then
        extension="Dockerfile"
    else
        extension="${filename##*.}"
    fi
    
    category=$(categorize_file "$file")
    target_dir=$(get_target_dir "$category")
    
    CATEGORIES+=("$category")
    TARGET_DIRS+=("$target_dir")
    
    # Color code by category
    case $category in
        deployment) color=$YELLOW ;;
        functional) color=$GREEN ;;
        implementation) color=$BLUE ;;
        testing) color=$MAGENTA ;;
        diagrams) color=$CYAN ;;
        scripts) color=$CYAN ;;
        root) color=$GREEN ;;
        *) color=$NC ;;
    esac
    
    # Show file type badge - FIXED: Use tr instead of ${extension^^}
    case $extension in
        pdf) badge="[PDF]" ;;
        docx|doc) badge="[DOC]" ;;
        pptx|ppt) badge="[PPT]" ;;
        xlsx|xls) badge="[XLS]" ;;
        py) badge="[PY]" ;;
        sql) badge="[SQL]" ;;
        yml|yaml) badge="[YML]" ;;
        json) badge="[JSON]" ;;
        toml) badge="[TOML]" ;;
        ini|cfg) badge="[CFG]" ;;
        template) badge="[TMPL]" ;;
        csv) badge="[CSV]" ;;
        Dockerfile) badge="[DOCKER]" ;;
        mmd|mermaid) badge="[MMD]" ;;
        svg) badge="[SVG]" ;;
        png|jpg|jpeg) badge="[IMG]" ;;
        sh) badge="[SH]" ;;
        md) badge="[MD]" ;;
        txt) badge="[TXT]" ;;
        *) badge="[$(echo $extension | tr '[:lower:]' '[:upper:]')]" ;;
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
        
        # Make Python files executable if they have shebang
        if [[ "$filename" =~ \.py$ ]]; then
            if head -n 1 "$file" | grep -q "^#!"; then
                chmod +x "$target_dir/$filename"
                print_info "    Made executable: $filename"
            fi
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
PY_COUNT=0
SQL_COUNT=0
YML_COUNT=0
JSON_COUNT=0
CONFIG_COUNT=0
DIAGRAM_FILE_COUNT=0

for ((i=0; i<${#NEW_DOCS[@]}; i++)); do
    category="${CATEGORIES[$i]}"
    file="${NEW_DOCS[$i]}"
    filename=$(basename "$file")
    
    # Get extension
    if [[ "$filename" =~ ^Dockerfile ]]; then
        extension="Dockerfile"
    else
        extension="${filename##*.}"
    fi
    
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
        py) ((PY_COUNT++)) ;;
        sql) ((SQL_COUNT++)) ;;
        yml|yaml) ((YML_COUNT++)) ;;
        json|toml|ini|cfg|template|csv|Dockerfile) ((CONFIG_COUNT++)) ;;
        mmd|mermaid|svg|png|jpg|jpeg) ((DIAGRAM_FILE_COUNT++)) ;;
    esac
done

# Build commit message
COMMIT_MSG="docs: update documentation ($COPIED_COUNT files)

File Types:
"

if [ $MD_COUNT -gt 0 ]; then COMMIT_MSG+="- Markdown: $MD_COUNT
"; fi
if [ $PDF_COUNT -gt 0 ]; then COMMIT_MSG+="- PDF: $PDF_COUNT
"; fi
if [ $DOCX_COUNT -gt 0 ]; then COMMIT_MSG+="- Word: $DOCX_COUNT
"; fi
if [ $PPTX_COUNT -gt 0 ]; then COMMIT_MSG+="- PowerPoint: $PPTX_COUNT
"; fi
if [ $XLSX_COUNT -gt 0 ]; then COMMIT_MSG+="- Excel: $XLSX_COUNT
"; fi
if [ $PY_COUNT -gt 0 ]; then COMMIT_MSG+="- Python: $PY_COUNT
"; fi
if [ $SQL_COUNT -gt 0 ]; then COMMIT_MSG+="- SQL: $SQL_COUNT
"; fi
if [ $YML_COUNT -gt 0 ]; then COMMIT_MSG+="- YAML: $YML_COUNT
"; fi
if [ $CONFIG_COUNT -gt 0 ]; then COMMIT_MSG+="- Config: $CONFIG_COUNT
"; fi
if [ $DIAGRAM_FILE_COUNT -gt 0 ]; then COMMIT_MSG+="- Diagrams: $DIAGRAM_FILE_COUNT
"; fi

COMMIT_MSG+="
Categories:
"

if [ $DEPLOYMENT_COUNT -gt 0 ]; then COMMIT_MSG+="- Deployment: $DEPLOYMENT_COUNT
"; fi
if [ $FUNCTIONAL_COUNT -gt 0 ]; then COMMIT_MSG+="- Functional: $FUNCTIONAL_COUNT
"; fi
if [ $IMPLEMENTATION_COUNT -gt 0 ]; then COMMIT_MSG+="- Implementation: $IMPLEMENTATION_COUNT
"; fi
if [ $TESTING_COUNT -gt 0 ]; then COMMIT_MSG+="- Testing: $TESTING_COUNT
"; fi
if [ $DIAGRAMS_COUNT -gt 0 ]; then COMMIT_MSG+="- Diagrams: $DIAGRAMS_COUNT
"; fi
if [ $SCRIPT_COUNT -gt 0 ]; then COMMIT_MSG+="- Scripts: $SCRIPT_COUNT
"; fi

COMMIT_MSG+="
Auto-generated via auto-update-docs.sh v3.2.1"

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
echo "🎉 Documentation updated and published!"
echo ""
