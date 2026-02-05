#!/bin/bash

# Income Fortress Documentation Migration Script
# Version: 1.0.0
# Purpose: Consolidate docs/, Documentation V1.0/, and files/ into documentation/
# Usage: ./migrate-documentation.sh

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

PROJECT_ROOT="/Volumes/CH-DataOne/AlbertoDBP/Agentic/income-platform"
BACKUP_DIR="$HOME/Documents/income-platform-migration-backup-$(date +%Y%m%d-%H%M%S)"

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Income Fortress Documentation Migration${NC}"
echo -e "${BLUE}Version 1.0.0${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

print_step() {
    echo -e "${GREEN}[$(date +'%H:%M:%S')]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_info() {
    echo -e "${CYAN}[INFO]${NC} $1"
}

# Verify project directory
if [ ! -d "$PROJECT_ROOT" ]; then
    print_error "Project root not found: $PROJECT_ROOT"
    exit 1
fi

cd "$PROJECT_ROOT" || exit 1
print_info "Working directory: $(pwd)"
echo ""

# Show current structure
print_step "Current documentation structure:"
echo ""
echo "📁 Current locations:"
echo "  1. docs/                      - $(find docs -type f 2>/dev/null | wc -l | tr -d ' ') files"
echo "  2. Documentation V1.0/        - $(find "Documentation V1.0" -type f 2>/dev/null | wc -l | tr -d ' ') files"
echo "  3. files/                     - $(find files -type f 2>/dev/null | wc -l | tr -d ' ') files"
echo "  4. (root)                     - Scattered files"
echo ""
echo "🎯 Target location:"
echo "  → documentation/              - Will contain all consolidated docs"
echo ""

# Confirm migration
read -p "Proceed with migration? This will reorganize all documentation. (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    print_error "Migration cancelled."
    exit 1
fi

# Step 1: Create backup
print_step "Creating backup..."
mkdir -p "$BACKUP_DIR"
[ -d "docs" ] && cp -R docs "$BACKUP_DIR/"
[ -d "Documentation V1.0" ] && cp -R "Documentation V1.0" "$BACKUP_DIR/"
[ -d "files" ] && cp -R files "$BACKUP_DIR/"

# Backup root-level docs
mkdir -p "$BACKUP_DIR/root-files"
for file in *.md DEPLOYMENT.md QUICKSTART.md INTEGRATION_GUIDE.md VSCODE_SETUP_GUIDE.md; do
    [ -f "$file" ] && cp "$file" "$BACKUP_DIR/root-files/" 2>/dev/null || true
done

print_info "Backup created: $BACKUP_DIR"
echo ""

# Step 2: Create new documentation structure
print_step "Creating new documentation/ structure..."
mkdir -p documentation/deployment
mkdir -p documentation/functional
mkdir -p documentation/implementation
mkdir -p documentation/testing
mkdir -p documentation/diagrams
mkdir -p documentation/architecture
mkdir -p documentation/archive

print_info "Created directory structure"
echo ""

# Step 3: Migrate files from docs/
print_step "Migrating from docs/..."

if [ -d "docs" ]; then
    # Deployment docs
    if [ -d "docs/deployment" ]; then
        print_info "  → Copying deployment docs..."
        cp -r docs/deployment/* documentation/deployment/ 2>/dev/null || true
    fi
    
    # Functional specs
    if [ -d "docs/functional" ]; then
        print_info "  → Copying functional specs..."
        cp -r docs/functional/* documentation/functional/ 2>/dev/null || true
    fi
    
    # Architecture docs
    if [ -d "docs/architecture" ]; then
        print_info "  → Copying architecture docs..."
        cp -r docs/architecture/* documentation/architecture/ 2>/dev/null || true
    fi
    
    # Root-level docs from docs/
    for file in docs/*.md; do
        if [ -f "$file" ]; then
            filename=$(basename "$file")
            case "$filename" in
                CHANGELOG.md|DOCUMENTATION-MANIFEST.md|DOCUMENTATION-STATUS.md|index.md|AUTO-UPDATE-README.md|decisions-log.md)
                    print_info "  → Copying $filename to documentation/"
                    cp "$file" "documentation/" 2>/dev/null || true
                    ;;
            esac
        fi
    done
fi

echo ""

# Step 4: Archive old versions
print_step "Archiving old versions..."

if [ -d "Documentation V1.0" ]; then
    print_info "  → Moving Documentation V1.0/ to archive/"
    mkdir -p "documentation/archive/Documentation-V1.0"
    cp -r "Documentation V1.0"/* "documentation/archive/Documentation-V1.0/" 2>/dev/null || true
fi

if [ -d "files" ]; then
    print_info "  → Moving files/ to archive/"
    mkdir -p "documentation/archive/files-old"
    cp -r files/* "documentation/archive/files-old/" 2>/dev/null || true
fi

echo ""

# Step 5: Copy important root-level docs
print_step "Copying important root-level documentation..."

# Master documents that should be in documentation/
for file in README.md DESIGN-SUMMARY.md DEPLOYMENT.md QUICKSTART.md INTEGRATION_GUIDE.md reference-architecture.md; do
    if [ -f "$file" ]; then
        print_info "  → Copying $file to documentation/"
        cp "$file" "documentation/" 2>/dev/null || true
    fi
done

# Root CHANGELOG if different from docs/CHANGELOG
if [ -f "CHANGELOG.md" ]; then
    if ! cmp -s "CHANGELOG.md" "documentation/CHANGELOG.md" 2>/dev/null; then
        print_info "  → Merging root CHANGELOG.md"
        cp "CHANGELOG.md" "documentation/CHANGELOG-root.md" 2>/dev/null || true
    fi
fi

echo ""

# Step 6: Create master index
print_step "Creating master documentation index..."

cat > documentation/README.md << 'EOF'
# Income Fortress Platform - Documentation

**Version:** 1.0.0  
**Last Updated:** $(date +%Y-%m-%d)

## 📚 Documentation Structure

```
documentation/
├── README.md                          # This file
├── DOCUMENTATION-MANIFEST.md          # Complete file inventory
├── CHANGELOG.md                       # Change history
├── index.md                           # Master index
│
├── deployment/                        # Operational Documentation
│   ├── deployment-checklist.md       # Pre-launch checklist
│   ├── operational-runbook.md        # Day-to-day operations
│   ├── monitoring-guide.md           # Monitoring & alerts
│   ├── disaster-recovery.md          # DR procedures
│   └── README.md                     # Deployment index
│
├── functional/                        # Functional Specifications
│   ├── agent-*.md                    # Individual agent specs
│   ├── feature-store-v2.md           # Feature store design
│   └── income-scorer-v6.md           # Scoring system
│
├── implementation/                    # Technical Specifications
│   └── (To be populated)
│
├── testing/                           # Testing Documentation
│   └── (To be populated)
│
├── diagrams/                          # System Diagrams
│   └── (Mermaid, SVG, PNG files)
│
├── architecture/                      # Architecture Documents
│   └── reference-architecture.md     # System architecture
│
└── archive/                           # Historical Versions
    ├── Documentation-V1.0/           # Old version
    └── files-old/                    # Old files folder

```

## 🚀 Quick Start

1. **New Users**: Start with `QUICKSTART.md`
2. **Deployment**: See `deployment/deployment-checklist.md`
3. **Architecture**: Read `architecture/reference-architecture.md`
4. **Agents**: Browse `functional/agent-*.md`

## 📋 Key Documents

### Getting Started
- [Quick Start Guide](QUICKSTART.md)
- [Integration Guide](INTEGRATION_GUIDE.md)
- [VS Code Setup](../VSCODE_SETUP_GUIDE.md)

### Architecture & Design
- [Design Summary](DESIGN-SUMMARY.md)
- [Reference Architecture](architecture/reference-architecture.md)
- [System Deployment](DEPLOYMENT.md)

### Operations
- [Deployment Checklist](deployment/deployment-checklist.md)
- [Operational Runbook](deployment/operational-runbook.md)
- [Monitoring Guide](deployment/monitoring-guide.md)
- [Disaster Recovery](deployment/disaster-recovery.md)

### Agents & Features
- [Agent 01: Market Data Sync](functional/agent-01-market-data-sync.md)
- [Agent 03: Income Scoring](functional/agent-03-income-scoring.md)
- [Agents 5-6-7-9 Summary](functional/agents-5-6-7-9-summary.md)
- [Feature Store V2](functional/feature-store-v2.md)
- [Income Scorer V6](functional/income-scorer-v6.md)

## 🔄 Updates

See [CHANGELOG.md](CHANGELOG.md) for version history and updates.

## 📝 Contributing

When adding documentation:
1. Place in appropriate subfolder
2. Update this README
3. Update DOCUMENTATION-MANIFEST.md
4. Add entry to CHANGELOG.md

## 🏗️ Migration Notes

This documentation structure was migrated from multiple sources:
- `docs/` - Primary documentation
- `Documentation V1.0/` - Archived version
- `files/` - Old files (archived)
- Root-level scattered files

All historical versions preserved in `archive/`.
EOF

print_info "Created documentation/README.md"
echo ""

# Step 7: Show summary
print_step "Migration Summary:"
echo ""

DEPLOYMENT_COUNT=$(find documentation/deployment -type f 2>/dev/null | wc -l | tr -d ' ')
FUNCTIONAL_COUNT=$(find documentation/functional -type f 2>/dev/null | wc -l | tr -d ' ')
ARCHITECTURE_COUNT=$(find documentation/architecture -type f 2>/dev/null | wc -l | tr -d ' ')
ROOT_COUNT=$(find documentation -maxdepth 1 -type f 2>/dev/null | wc -l | tr -d ' ')
TOTAL_COUNT=$(find documentation -type f 2>/dev/null | wc -l | tr -d ' ')

echo "📊 Files by category:"
echo "  Deployment:      $DEPLOYMENT_COUNT files"
echo "  Functional:      $FUNCTIONAL_COUNT files"
echo "  Architecture:    $ARCHITECTURE_COUNT files"
echo "  Root-level:      $ROOT_COUNT files"
echo "  ────────────────────────"
echo "  Total:           $TOTAL_COUNT files"
echo ""
echo "💾 Backup location:"
echo "  $BACKUP_DIR"
echo ""

# Step 8: Confirm cleanup
print_warning "Ready to clean up old directories"
echo ""
echo "This will:"
echo "  1. Remove docs/ folder"
echo "  2. Remove Documentation V1.0/ folder"
echo "  3. Remove files/ folder"
echo "  (All backed up to $BACKUP_DIR)"
echo ""

read -p "Proceed with cleanup? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    print_warning "Cleanup skipped. Old directories remain."
    print_info "You can manually remove them later:"
    echo "  rm -rf docs/"
    echo "  rm -rf \"Documentation V1.0\""
    echo "  rm -rf files/"
    exit 0
fi

# Step 9: Cleanup
print_step "Cleaning up old directories..."

[ -d "docs" ] && rm -rf docs && print_info "  ✓ Removed docs/"
[ -d "Documentation V1.0" ] && rm -rf "Documentation V1.0" && print_info "  ✓ Removed Documentation V1.0/"
[ -d "files" ] && rm -rf files && print_info "  ✓ Removed files/"

echo ""

# Step 10: Git status
print_step "Git status:"
cd "$PROJECT_ROOT" || exit 1
git status --short

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}✓ Migration Complete!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "Next steps:"
echo "  1. Review new structure: cd documentation && ls -la"
echo "  2. Test auto-update script with new structure"
echo "  3. Commit changes:"
echo "     git add ."
echo "     git commit -m 'refactor: consolidate documentation into documentation/ folder'"
echo "     git push origin main"
echo ""
echo "Backup preserved at:"
echo "  $BACKUP_DIR"
echo ""
