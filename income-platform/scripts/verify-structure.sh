#!/bin/bash

# Verification script for documentation structure
# Works without tree command

echo "========================================="
echo "Income Platform Documentation Structure"
echo "========================================="
echo ""

cd /Volumes/CH-DataOne/AlbertoDBP/Agentic/income-platform

# Function to show directory contents
show_dir() {
    local dir=$1
    local indent=$2
    
    if [ -d "$dir" ]; then
        file_count=$(find "$dir" -maxdepth 1 -type f | wc -l | tr -d ' ')
        subdir_count=$(find "$dir" -maxdepth 1 -type d | grep -v "^$dir$" | wc -l | tr -d ' ')
        
        echo "${indent}📁 $(basename "$dir")/"
        echo "${indent}   Files: $file_count | Subdirectories: $subdir_count"
        
        # Show first 5 files
        find "$dir" -maxdepth 1 -type f | head -5 | while read file; do
            echo "${indent}   ├─ $(basename "$file")"
        done
        
        if [ $file_count -gt 5 ]; then
            echo "${indent}   └─ ... and $(($file_count - 5)) more files"
        fi
    fi
}

echo "✅ Main documentation/ structure:"
echo ""
show_dir "documentation" ""

echo ""
echo "✅ Subdirectories:"
echo ""
show_dir "documentation/deployment" "  "
echo ""
show_dir "documentation/functional" "  "
echo ""
show_dir "documentation/implementation" "  "
echo ""
show_dir "documentation/testing" "  "
echo ""
show_dir "documentation/diagrams" "  "
echo ""
show_dir "documentation/architecture" "  "
echo ""
show_dir "documentation/archive" "  "

echo ""
echo "========================================="
echo "📊 Summary Statistics"
echo "========================================="
echo ""

DEPLOYMENT_COUNT=$(find documentation/deployment -type f 2>/dev/null | wc -l | tr -d ' ')
FUNCTIONAL_COUNT=$(find documentation/functional -type f 2>/dev/null | wc -l | tr -d ' ')
IMPLEMENTATION_COUNT=$(find documentation/implementation -type f 2>/dev/null | wc -l | tr -d ' ')
TESTING_COUNT=$(find documentation/testing -type f 2>/dev/null | wc -l | tr -d ' ')
DIAGRAMS_COUNT=$(find documentation/diagrams -type f 2>/dev/null | wc -l | tr -d ' ')
ARCHITECTURE_COUNT=$(find documentation/architecture -type f 2>/dev/null | wc -l | tr -d ' ')
ARCHIVE_COUNT=$(find documentation/archive -type f 2>/dev/null | wc -l | tr -d ' ')
ROOT_COUNT=$(find documentation -maxdepth 1 -type f 2>/dev/null | wc -l | tr -d ' ')
TOTAL_COUNT=$(find documentation -type f 2>/dev/null | wc -l | tr -d ' ')

echo "Files by category:"
echo "  📋 Deployment:      $DEPLOYMENT_COUNT files"
echo "  🔧 Functional:      $FUNCTIONAL_COUNT files"
echo "  🏗️  Implementation:  $IMPLEMENTATION_COUNT files"
echo "  🧪 Testing:         $TESTING_COUNT files"
echo "  📊 Diagrams:        $DIAGRAMS_COUNT files"
echo "  🏛️  Architecture:    $ARCHITECTURE_COUNT files"
echo "  📦 Archive:         $ARCHIVE_COUNT files"
echo "  📄 Root-level:      $ROOT_COUNT files"
echo "  ────────────────────────────────"
echo "  📚 Total:           $TOTAL_COUNT files"

echo ""
echo "========================================="
echo "🎯 Old directories status"
echo "========================================="
echo ""

if [ -d "docs" ]; then
    echo "  ⚠️  docs/ still exists"
else
    echo "  ✅ docs/ removed"
fi

if [ -d "Documentation V1.0" ]; then
    echo "  ⚠️  Documentation V1.0/ still exists"
else
    echo "  ✅ Documentation V1.0/ removed"
fi

if [ -d "files" ]; then
    echo "  ⚠️  files/ still exists"
else
    echo "  ✅ files/ removed"
fi

echo ""
echo "========================================="
echo "✅ Verification Complete!"
echo "========================================="
echo ""
echo "Next steps:"
echo "  1. Review the structure above"
echo "  2. Install auto-update-docs-FIXED.sh"
echo "  3. Commit changes to GitHub"
echo ""
