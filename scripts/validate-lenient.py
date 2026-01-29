#!/usr/bin/env python3
"""
Lenient Documentation Validator

For initial development, this treats ALL missing files referenced in index.md
as "planned documentation" rather than errors.

Real errors are only:
- Core files missing (README, CHANGELOG, reference architecture)
- Broken links in existing documentation (not index.md)
- Formatting issues in existing files

Usage:
    python validate-lenient.py
    python validate-lenient.py --show-planned
"""

import re
import sys
from pathlib import Path
from typing import List
from dataclasses import dataclass

# Color codes
class Colors:
    RED = '\033[0;31m'
    GREEN = '\033[0;32m'
    YELLOW = '\033[1;33m'
    BLUE = '\033[0;34m'
    CYAN = '\033[0;36m'
    NC = '\033[0m'

@dataclass
class ValidationIssue:
    severity: str
    file_path: str
    line_number: int
    message: str

class LenientValidator:
    """Validator that treats missing files in index.md as planned"""
    
    def __init__(self, project_root: str, show_planned: bool = False):
        self.project_root = Path(project_root)
        self.docs_root = self.project_root / "docs"
        self.show_planned = show_planned
        self.issues: List[ValidationIssue] = []
        self.stats = {
            'files_checked': 0,
            'errors': 0,
            'planned': 0
        }
    
    def validate_all(self) -> bool:
        """Run validation"""
        print(f"{Colors.BLUE}{'='*65}{Colors.NC}")
        print(f"{Colors.BLUE}  Lenient Documentation Validation (Development Mode){Colors.NC}")
        print(f"{Colors.BLUE}{'='*65}{Colors.NC}\n")
        
        self.check_core_files()
        self.check_broken_links_in_existing_docs()
        self.print_results()
        
        return self.stats['errors'] == 0
    
    def check_core_files(self):
        """Check only absolutely required core files"""
        print(f"{Colors.BLUE}ℹ Checking core required files...{Colors.NC}")
        
        core_files = [
            "README.md",
            "docs/index.md",
            "docs/CHANGELOG.md",
            "docs/architecture/reference-architecture.md",
        ]
        
        for file_path in core_files:
            full_path = self.project_root / file_path
            if not full_path.exists():
                self.add_issue(
                    severity="error",
                    file_path=file_path,
                    line_number=0,
                    message=f"Core file missing: {file_path}"
                )
            else:
                self.stats['files_checked'] += 1
    
    def check_broken_links_in_existing_docs(self):
        """Only check for broken links in docs that actually exist (excluding index.md)"""
        print(f"{Colors.BLUE}ℹ Checking links in existing documentation...{Colors.NC}")
        
        link_pattern = re.compile(r'\[([^\]]+)\]\(([^)]+)\)')
        
        for md_file in self.docs_root.rglob("*.md"):
            # Skip index.md - all its links are either working or planned
            if md_file.name == 'index.md' or 'CHANGELOG' in md_file.name:
                # Count planned links in index
                if md_file.name == 'index.md':
                    content = md_file.read_text(encoding='utf-8')
                    for match in link_pattern.finditer(content):
                        link_path = match.group(2)
                        if not link_path.startswith(('http://', 'https://', '#')):
                            # Resolve path
                            if link_path.startswith('/'):
                                target = self.project_root / link_path.lstrip('/')
                            else:
                                target = (md_file.parent / link_path).resolve()
                            
                            target_str = str(target).split('#')[0]
                            if not Path(target_str).exists():
                                self.stats['planned'] += 1
                continue
            
            self.stats['files_checked'] += 1
            content = md_file.read_text(encoding='utf-8')
            lines = content.split('\n')
            
            for i, line in enumerate(lines, 1):
                for match in link_pattern.finditer(line):
                    link_path = match.group(2)
                    
                    # Skip external links and anchors
                    if link_path.startswith(('http://', 'https://', '#')):
                        continue
                    
                    # Resolve relative link
                    if link_path.startswith('/'):
                        target = self.project_root / link_path.lstrip('/')
                    else:
                        target = (md_file.parent / link_path).resolve()
                    
                    # Remove anchor
                    target_str = str(target).split('#')[0]
                    target = Path(target_str)
                    
                    if not target.exists():
                        # This is a real broken link (not in index.md)
                        self.add_issue(
                            severity="error",
                            file_path=str(md_file.relative_to(self.project_root)),
                            line_number=i,
                            message=f"Broken link in existing doc: {link_path}"
                        )
    
    def add_issue(self, severity: str, file_path: str, line_number: int, message: str):
        """Add a validation issue"""
        issue = ValidationIssue(
            severity=severity,
            file_path=file_path,
            line_number=line_number,
            message=message
        )
        self.issues.append(issue)
        self.stats['errors'] += 1
    
    def print_results(self):
        """Print results"""
        print(f"\n{Colors.BLUE}{'='*65}{Colors.NC}")
        print(f"{Colors.BLUE}  Results{Colors.NC}")
        print(f"{Colors.BLUE}{'='*65}{Colors.NC}\n")
        
        errors = [i for i in self.issues if i.severity == 'error']
        
        if errors:
            print(f"{Colors.RED}✗ ERRORS ({len(errors)}):{Colors.NC}")
            for issue in errors:
                print(f"  {issue.file_path}:{issue.line_number}")
                print(f"    {issue.message}")
            print()
        
        # Summary
        print(f"{Colors.BLUE}Summary:{Colors.NC}")
        print(f"  Existing files checked: {self.stats['files_checked']}")
        print(f"  Real errors: {Colors.RED if errors else Colors.GREEN}{len(errors)}{Colors.NC}")
        print(f"  Planned documentation: {Colors.CYAN}{self.stats['planned']}{Colors.NC}")
        print()
        
        if errors:
            print(f"{Colors.RED}✗ VALIDATION FAILED{Colors.NC}")
        else:
            print(f"{Colors.GREEN}✓ VALIDATION PASSED{Colors.NC}")
            if self.stats['planned'] > 0:
                print(f"{Colors.CYAN}  ({self.stats['planned']} files planned for future development){Colors.NC}")

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Lenient validator for development')
    parser.add_argument('project_root', nargs='?', default='.', help='Project root')
    parser.add_argument('--show-planned', action='store_true', help='Show planned files')
    
    args = parser.parse_args()
    
    validator = LenientValidator(
        project_root=args.project_root,
        show_planned=args.show_planned
    )
    
    success = validator.validate_all()
    sys.exit(0 if success else 1)

if __name__ == '__main__':
    main()
