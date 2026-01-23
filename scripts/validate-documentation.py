#!/usr/bin/env python3
"""
Validation script for Platform Documentation Orchestrator output.

This script checks that generated documentation meets quality standards.
"""

import os
import re
from pathlib import Path
from typing import List, Tuple


class DocumentationValidator:
    """Validates documentation structure and content."""
    
    def __init__(self, root_dir: str):
        self.root_dir = Path(root_dir)
        self.errors: List[str] = []
        self.warnings: List[str] = []
        
    def validate_all(self) -> bool:
        """Run all validation checks."""
        self._validate_folder_structure()
        self._validate_specs()
        self._validate_diagrams()
        self._validate_index()
        
        return self._report_results()
    
    def _validate_folder_structure(self) -> None:
        """Check that required folders exist."""
        required_folders = [
            'docs/architecture',
            'docs/functional',
            'docs/implementation',
            'docs/testing',
            'docs/diagrams',
            'src',
        ]
        
        for folder in required_folders:
            path = self.root_dir / folder
            if not path.exists():
                self.errors.append(f"Missing required folder: {folder}")
    
    def _validate_specs(self) -> None:
        """Validate specification documents."""
        spec_dir = self.root_dir / 'docs' / 'implementation'
        
        if not spec_dir.exists():
            return
        
        for spec_file in spec_dir.glob('*.md'):
            self._validate_spec_file(spec_file)
    
    def _validate_spec_file(self, filepath: Path) -> None:
        """Validate individual spec file."""
        content = filepath.read_text()
        filename = filepath.name
        
        # Check for required sections
        required_sections = [
            'Overview',
            'Technical Design',
            'Testing & Acceptance',
            'Dependencies & Integrations',
        ]
        
        for section in required_sections:
            if f'## {section}' not in content and f'### {section}' not in content:
                self.warnings.append(
                    f"{filename}: Missing section '{section}'"
                )
        
        # Check for testing section details
        if '## Testing & Acceptance' in content:
            if 'Unit Test' not in content:
                self.warnings.append(
                    f"{filename}: Testing section missing unit test requirements"
                )
            if 'Acceptance Criteria' not in content:
                self.warnings.append(
                    f"{filename}: Testing section missing acceptance criteria"
                )
            if 'Edge Case' not in content:
                self.warnings.append(
                    f"{filename}: Testing section missing edge case documentation"
                )
        
        # Check for proper formatting
        if not content.startswith('# '):
            self.errors.append(f"{filename}: Missing H1 title")
        
        if '**Status**:' not in content:
            self.warnings.append(f"{filename}: Missing status indicator")
        
        if '**Last Updated**:' not in content:
            self.warnings.append(f"{filename}: Missing last updated date")
    
    def _validate_diagrams(self) -> None:
        """Validate diagram files."""
        diagram_dir = self.root_dir / 'docs' / 'diagrams'
        
        if not diagram_dir.exists():
            self.warnings.append("No diagrams folder found")
            return
        
        mermaid_files = list(diagram_dir.glob('**/*.mmd'))
        
        if not mermaid_files:
            self.warnings.append("No Mermaid diagrams (.mmd files) found")
        
        for mermaid_file in mermaid_files:
            self._validate_mermaid_file(mermaid_file)
    
    def _validate_mermaid_file(self, filepath: Path) -> None:
        """Validate individual Mermaid file."""
        content = filepath.read_text()
        filename = filepath.name
        
        # Check for valid Mermaid syntax start
        valid_starts = [
            'graph',
            'flowchart',
            'sequenceDiagram',
            'stateDiagram',
            'classDiagram',
            'erDiagram',
        ]
        
        if not any(content.strip().startswith(start) for start in valid_starts):
            self.errors.append(
                f"{filename}: Invalid Mermaid syntax - doesn't start with valid diagram type"
            )
    
    def _validate_index(self) -> None:
        """Validate master index file."""
        index_file = self.root_dir / 'docs' / 'index.md'
        
        if not index_file.exists():
            self.errors.append("Missing master index file: docs/index.md")
            return
        
        content = index_file.read_text()
        
        # Check for required sections in index
        if 'Architecture' not in content:
            self.warnings.append("Master index missing Architecture section")
        if 'Specifications' not in content:
            self.warnings.append("Master index missing Specifications section")
        if 'Component Status' not in content:
            self.warnings.append("Master index missing Component Status table")
    
    def _report_results(self) -> bool:
        """Print validation results."""
        print("\n" + "="*60)
        print("DOCUMENTATION VALIDATION REPORT")
        print("="*60)
        
        if self.errors:
            print(f"\n❌ ERRORS ({len(self.errors)}):")
            for error in self.errors:
                print(f"  • {error}")
        
        if self.warnings:
            print(f"\n⚠️  WARNINGS ({len(self.warnings)}):")
            for warning in self.warnings:
                print(f"  • {warning}")
        
        if not self.errors and not self.warnings:
            print("\n✅ All validation checks passed!")
            return True
        
        print("\n" + "="*60)
        
        if self.errors:
            print("❌ VALIDATION FAILED")
            print("Please fix errors before proceeding.")
            return False
        else:
            print("⚠️  VALIDATION PASSED WITH WARNINGS")
            print("Please review warnings and address if needed.")
            return True


def main():
    """Main entry point."""
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python validate-documentation.py <project_root_dir>")
        print("\nExample:")
        print("  python validate-documentation.py ./my-platform/")
        sys.exit(1)
    
    project_dir = sys.argv[1]
    
    if not Path(project_dir).exists():
        print(f"Error: Directory not found: {project_dir}")
        sys.exit(1)
    
    validator = DocumentationValidator(project_dir)
    success = validator.validate_all()
    
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
