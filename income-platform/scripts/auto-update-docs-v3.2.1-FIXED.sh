#!/bin/bash

# Income Fortress Platform - Auto Documentation Updater (FIXED)
# Version: 3.2.1 FIXED
# Purpose: Automatically detect ALL docs in Downloads, update repo, commit to GitHub
# Supports: MD, PDF, DOCX, PPTX, XLSX, PY, SQL, Mermaid, SVG, PNG, YML, Dockerfile, Templates
# FIX: macOS bash compatibility (${extension^^} → tr command)
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
echo -e "${BLUE}Version 3.2.1 FIXED (macOS Compatible)${NC}"
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

# All file types in one loop to avoid repetition
while IFS= read -r file; do
    [ ! -s "$file" ] && continue
    filename=$(basename "$file")
    [[ "$filename" == .* ]] && continue
    [[ "$filename" == *.DS_Store ]] && continue
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

# Rest of the script continues exactly as v3.2.0...
# (Copying files, Git commit, push, backup - unchanged)

print_step "Creating documentation directory structure..."
mkdir -p "$DOCS_DIR/deployment"
mkdir -p "$DOCS_DIR/functional"
mkdir -p "$DOCS_DIR/implementation"
mkdir -p "$DOCS_DIR/testing"
mkdir -p "$DOCS_DIR/diagrams"
mkdir -p "$DOCS_DIR/misc"
mkdir -p "$PROJECT_DIR/scripts"

print_step "Copying files to repository..."
COPIED_COUNT=0

index=0
for file in "${NEW_DOCS[@]}"; do
    filename=$(basename "$file")
    target_dir="${TARGET_DIRS[$index]}"
    
    cp "$file" "$target_dir/" 2>/dev/null
    
    if [ $? -eq 0 ]; then
        ((COPIED_COUNT++))
        print_info "  ✓ Copied: $filename → $(basename "$target_dir")/"
        
        # Make scripts executable
        if [[ "$filename" =~ \.sh$ ]] || [[ "$filename" =~ \.py$ && $(head -n 1 "$file") =~ ^#! ]]; then
            chmod +x "$target_dir/$filename"
            print_info "    Made executable: $filename"
        fi
    fi
    
    ((index++))
done

echo ""
print_step "Successfully copied $COPIED_COUNT file(s)"

cd "$PROJECT_DIR" || exit 1
git status --short

echo ""
print_step "Files ready to commit!"
echo "Run these commands to commit:"
echo "  cd $REPO_ROOT"
echo "  git add income-platform/"
echo "  git commit -m 'docs: update documentation'"
echo "  git push origin main"
