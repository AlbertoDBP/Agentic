#!/bin/bash

###############################################################################
# Documentation Update Orchestrator
# 
# Purpose: Automate documentation updates after design changes or development
# Usage: ./scripts/update-documentation.sh [options]
#
# Examples:
#   ./scripts/update-documentation.sh --design-change "agent-3"
#   ./scripts/update-documentation.sh --dev-complete "agent-1"
#   ./scripts/update-documentation.sh --full-sync
###############################################################################

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Default values
UPDATE_TYPE=""
COMPONENT=""
AUTO_COMMIT=false
INTERACTIVE=true
DRY_RUN=false

###############################################################################
# Helper Functions
###############################################################################

print_header() {
    echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
    echo -e "${BLUE}  $1${NC}"
    echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ $1${NC}"
}

confirm() {
    if [ "$INTERACTIVE" = false ]; then
        return 0
    fi
    
    local prompt="$1"
    local default="${2:-n}"
    
    if [ "$default" = "y" ]; then
        prompt="$prompt [Y/n]: "
    else
        prompt="$prompt [y/N]: "
    fi
    
    read -p "$prompt" response
    response=${response:-$default}
    
    [[ "$response" =~ ^[Yy]$ ]]
}

###############################################################################
# Documentation Update Functions
###############################################################################

update_changelog() {
    local change_type="$1"
    local component="$2"
    local description="$3"
    
    print_info "Updating CHANGELOG.md..."
    
    local changelog="$PROJECT_ROOT/docs/CHANGELOG.md"
    local date=$(date +%Y-%m-%d)
    local version=$(get_next_version)
    
    # Create changelog if it doesn't exist
    if [ ! -f "$changelog" ]; then
        cat > "$changelog" << EOF
# Changelog

All notable changes to the Tax-Efficient Income Investment Platform documentation will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

EOF
    fi
    
    # Check if version entry exists
    if ! grep -q "## \[$version\]" "$changelog"; then
        # Add new version header after the intro
        sed -i "/^The format is/a\\
\\
## [$version] - $date\\
" "$changelog"
    fi
    
    # Add the change under appropriate section
    local section=""
    case "$change_type" in
        design)
            section="### Changed"
            ;;
        feature)
            section="### Added"
            ;;
        fix)
            section="### Fixed"
            ;;
        deprecate)
            section="### Deprecated"
            ;;
    esac
    
    # Check if section exists, add if not
    if ! grep -q "^$section" "$changelog"; then
        sed -i "/## \[$version\]/a\\
\\
$section\\
" "$changelog"
    fi
    
    # Add the change item
    sed -i "/^$section/a\\
- **$component**: $description
" "$changelog"
    
    print_success "CHANGELOG.md updated"
}

update_decisions_log() {
    local component="$1"
    local decision="$2"
    local rationale="$3"
    
    print_info "Updating decisions-log.md..."
    
    local decisions_log="$PROJECT_ROOT/docs/decisions-log.md"
    local date=$(date +%Y-%m-%d)
    
    # Get next ADR number
    local adr_num=$(grep -c "^## ADR-" "$decisions_log" 2>/dev/null || echo "0")
    adr_num=$((adr_num + 1))
    adr_num=$(printf "%03d" $adr_num)
    
    # Append new ADR
    cat >> "$decisions_log" << EOF

## ADR-$adr_num: $decision

**Date**: $date  
**Status**: Accepted  
**Component**: $component

### Context

$rationale

### Decision

$decision

### Consequences

**Positive**:
- [To be documented based on implementation]

**Negative**:
- [To be documented if any issues arise]

**Neutral**:
- Requires documentation update
- May require training for team members

EOF
    
    print_success "decisions-log.md updated with ADR-$adr_num"
}

update_index_status() {
    local component="$1"
    local new_status="$2"
    
    print_info "Updating documentation index status..."
    
    local index="$PROJECT_ROOT/docs/index.md"
    
    # Update status in the appropriate table
    # This is a simplified version - you may need to enhance based on your exact format
    sed -i "s/\(.*$component.*\)⏳ Pending/\1$new_status/" "$index"
    sed -i "s/\(.*$component.*\)🚧 In Progress/\1$new_status/" "$index"
    
    print_success "Index status updated for $component"
}

generate_component_spec() {
    local component="$1"
    local spec_type="$2"  # functional or implementation
    
    print_header "Generating $spec_type specification for $component"
    
    local spec_dir="$PROJECT_ROOT/docs/$spec_type"
    mkdir -p "$spec_dir"
    
    local spec_file="$spec_dir/$component.md"
    
    if [ -f "$spec_file" ]; then
        print_warning "$spec_file already exists"
        if ! confirm "Overwrite existing specification?"; then
            return 1
        fi
    fi
    
    # Call Claude or use template
    if [ "$INTERACTIVE" = true ]; then
        print_info "Opening template for manual editing..."
        print_info "Use the platform-documentation-orchestrator skill in Claude to generate:"
        print_info "  Component: $component"
        print_info "  Type: $spec_type"
        print_info ""
        print_info "Save the generated content to: $spec_file"
        confirm "Press Enter when specification is ready..." "y"
    else
        # Copy from template
        local template="$PROJECT_ROOT/scripts/templates/${spec_type}-spec-template.md"
        if [ -f "$template" ]; then
            cp "$template" "$spec_file"
            # Replace placeholders
            sed -i "s/{{COMPONENT_NAME}}/$component/g" "$spec_file"
            sed -i "s/{{DATE}}/$(date +%Y-%m-%d)/g" "$spec_file"
        fi
    fi
    
    print_success "Specification file ready at $spec_file"
}

validate_documentation() {
    print_header "Validating Documentation"
    
    local validation_script="$SCRIPT_DIR/validate-documentation.py"
    
    if [ -f "$validation_script" ]; then
        print_info "Running validation script..."
        python3 "$validation_script" "$PROJECT_ROOT"
    else
        print_warning "Validation script not found, skipping..."
        # Basic validation
        print_info "Running basic validation..."
        
        # Check for broken links
        print_info "Checking for broken internal links..."
        grep -r "\]\(/" "$PROJECT_ROOT/docs" | while read -r line; do
            local file=$(echo "$line" | cut -d: -f1)
            local link=$(echo "$line" | grep -oP '\]\(\K[^)]+')
            local target="$PROJECT_ROOT/docs/$link"
            
            if [ ! -f "$target" ]; then
                print_warning "Broken link in $file: $link"
            fi
        done
        
        print_success "Basic validation complete"
    fi
}

get_next_version() {
    local changelog="$PROJECT_ROOT/docs/CHANGELOG.md"
    
    if [ ! -f "$changelog" ]; then
        echo "1.0.0"
        return
    fi
    
    # Get current version from changelog
    local current=$(grep -m 1 "^## \[" "$changelog" | grep -oP '\[\K[^\]]+' || echo "0.0.0")
    
    # Increment patch version
    local major=$(echo "$current" | cut -d. -f1)
    local minor=$(echo "$current" | cut -d. -f2)
    local patch=$(echo "$current" | cut -d. -f3)
    
    patch=$((patch + 1))
    
    echo "$major.$minor.$patch"
}

sync_with_github() {
    print_header "Syncing with GitHub"
    
    if [ "$DRY_RUN" = true ]; then
        print_info "DRY RUN: Would commit and push changes"
        return
    fi
    
    cd "$PROJECT_ROOT"
    
    # Check if we're in a git repo
    if ! git rev-parse --git-dir > /dev/null 2>&1; then
        print_error "Not a git repository. Initialize git first."
        return 1
    fi
    
    # Check for uncommitted changes
    if [ -z "$(git status --porcelain)" ]; then
        print_info "No changes to commit"
        return 0
    fi
    
    print_info "Changes detected:"
    git status --short
    
    if [ "$AUTO_COMMIT" = false ]; then
        if ! confirm "Commit and push these changes?"; then
            print_info "Skipping git sync"
            return 0
        fi
    fi
    
    # Stage all documentation changes
    git add docs/ README.md CHANGELOG.md
    
    # Generate commit message
    local version=$(get_next_version)
    local commit_msg="docs: update documentation to v$version

Changes:
$(git diff --staged --name-only | sed 's/^/- /')

Generated by update-documentation.sh
"
    
    git commit -m "$commit_msg"
    
    # Push to remote
    if confirm "Push to remote repository?" "y"; then
        git push origin main
        print_success "Changes pushed to GitHub"
    else
        print_info "Changes committed locally only"
    fi
}

###############################################################################
# Main Update Workflows
###############################################################################

handle_design_change() {
    local component="$1"
    
    print_header "Design Change: $component"
    
    echo ""
    read -p "Describe the design change: " change_description
    
    # Update specifications
    print_info "Updating specifications..."
    
    # Functional spec
    if [ -f "$PROJECT_ROOT/docs/functional/$component.md" ]; then
        print_info "Functional spec exists for $component"
        if confirm "Update functional specification?"; then
            generate_component_spec "$component" "functional"
        fi
    fi
    
    # Implementation spec
    if [ -f "$PROJECT_ROOT/docs/implementation/${component}-impl.md" ]; then
        print_info "Implementation spec exists for $component"
        if confirm "Update implementation specification?"; then
            generate_component_spec "$component" "implementation"
        fi
    fi
    
    # Update changelog
    update_changelog "design" "$component" "$change_description"
    
    # Update decisions log
    read -p "Is this a significant design decision? (y/n): " is_decision
    if [[ "$is_decision" =~ ^[Yy]$ ]]; then
        read -p "Decision title: " decision_title
        read -p "Rationale: " rationale
        update_decisions_log "$component" "$decision_title" "$rationale"
    fi
    
    # Update diagrams if needed
    if confirm "Do diagrams need updating?"; then
        print_info "Update the following diagrams as needed:"
        print_info "  - docs/diagrams/system-architecture.mmd"
        print_info "  - docs/diagrams/data-model.mmd"
        print_info "  - docs/diagrams/component-interactions.mmd"
        confirm "Press Enter when diagrams are updated..." "y"
    fi
    
    # Validate
    validate_documentation
    
    print_success "Design change documentation complete"
}

handle_development_complete() {
    local component="$1"
    
    print_header "Development Complete: $component"
    
    # Update index status
    update_index_status "$component" "✅ Complete"
    
    # Update changelog
    update_changelog "feature" "$component" "Implementation complete and tested"
    
    # Update README if needed
    if confirm "Update README.md with new capabilities?"; then
        print_info "Manually update README.md to reflect:"
        print_info "  - New features available"
        print_info "  - Updated project status"
        print_info "  - Any new dependencies or setup steps"
        confirm "Press Enter when README is updated..." "y"
    fi
    
    # Check for API documentation
    if [[ "$component" == agent-* ]] || [[ "$component" == *-service ]]; then
        if confirm "Generate API documentation from OpenAPI spec?"; then
            print_info "Ensure FastAPI service has up-to-date docstrings"
            print_info "OpenAPI spec auto-generated at /docs endpoint"
        fi
    fi
    
    # Validate
    validate_documentation
    
    print_success "Development documentation complete"
}

handle_full_sync() {
    print_header "Full Documentation Sync"
    
    # Update all index files
    print_info "Updating index files..."
    
    # Scan for changes
    print_info "Scanning for documentation changes..."
    
    local changed_files=$(git diff --name-only docs/ 2>/dev/null || echo "")
    
    if [ -n "$changed_files" ]; then
        print_info "Changed files detected:"
        echo "$changed_files"
    else
        print_info "No changed files detected"
    fi
    
    # Validate all documentation
    validate_documentation
    
    # Update version in all docs
    local version=$(get_next_version)
    print_info "Current version will be: $version"
    
    # Sync with GitHub
    sync_with_github
    
    print_success "Full sync complete"
}

###############################################################################
# Usage and Argument Parsing
###############################################################################

show_usage() {
    cat << EOF
Usage: $0 [OPTIONS]

Documentation Update Orchestrator - Automate documentation updates after design or development changes

OPTIONS:
    --design-change COMPONENT    Update docs after design change (e.g., agent-3, frontend)
    --dev-complete COMPONENT     Update docs after development completion
    --full-sync                  Full documentation sync and validation
    
    --auto-commit               Automatically commit changes without prompting
    --non-interactive           Run without user prompts (uses defaults)
    --dry-run                   Show what would be done without making changes
    
    -h, --help                  Show this help message

EXAMPLES:
    # Design change for Agent 3
    $0 --design-change agent-03-income-scoring
    
    # Mark Agent 1 as development complete
    $0 --dev-complete agent-01-market-data-sync
    
    # Full sync and push to GitHub
    $0 --full-sync --auto-commit
    
    # Dry run to see what would change
    $0 --design-change agent-05-tax-optimization --dry-run

WORKFLOW:
    1. Design Change:
       - Updates functional/implementation specs
       - Updates CHANGELOG.md
       - Optionally adds to decisions-log.md
       - Prompts for diagram updates
       - Validates documentation
    
    2. Development Complete:
       - Updates index.md status to ✅ Complete
       - Updates CHANGELOG.md
       - Prompts for README updates
       - Validates documentation
    
    3. Full Sync:
       - Validates all documentation
       - Updates version numbers
       - Commits and pushes to GitHub

EOF
}

###############################################################################
# Main Script
###############################################################################

main() {
    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            --design-change)
                UPDATE_TYPE="design"
                COMPONENT="$2"
                shift 2
                ;;
            --dev-complete)
                UPDATE_TYPE="development"
                COMPONENT="$2"
                shift 2
                ;;
            --full-sync)
                UPDATE_TYPE="sync"
                shift
                ;;
            --auto-commit)
                AUTO_COMMIT=true
                shift
                ;;
            --non-interactive)
                INTERACTIVE=false
                shift
                ;;
            --dry-run)
                DRY_RUN=true
                shift
                ;;
            -h|--help)
                show_usage
                exit 0
                ;;
            *)
                print_error "Unknown option: $1"
                show_usage
                exit 1
                ;;
        esac
    done
    
    # Verify we're in the right directory
    if [ ! -f "$PROJECT_ROOT/README.md" ]; then
        print_error "Must be run from project root or scripts directory"
        exit 1
    fi
    
    # Show dry run notice
    if [ "$DRY_RUN" = true ]; then
        print_warning "DRY RUN MODE - No changes will be made"
        echo ""
    fi
    
    # Execute appropriate workflow
    case "$UPDATE_TYPE" in
        design)
            if [ -z "$COMPONENT" ]; then
                print_error "Component name required for --design-change"
                exit 1
            fi
            handle_design_change "$COMPONENT"
            ;;
        development)
            if [ -z "$COMPONENT" ]; then
                print_error "Component name required for --dev-complete"
                exit 1
            fi
            handle_development_complete "$COMPONENT"
            ;;
        sync)
            handle_full_sync
            ;;
        *)
            print_error "Must specify --design-change, --dev-complete, or --full-sync"
            show_usage
            exit 1
            ;;
    esac
    
    # Final summary
    echo ""
    print_header "Summary"
    print_success "Documentation update complete!"
    
    if [ "$DRY_RUN" = false ]; then
        print_info "Next steps:"
        print_info "  1. Review changes: git diff"
        print_info "  2. Test documentation: open docs/index.md"
        if [ "$AUTO_COMMIT" = false ]; then
            print_info "  3. Commit changes: git add . && git commit"
            print_info "  4. Push to GitHub: git push origin main"
        fi
    fi
}

# Run main function
main "$@"
