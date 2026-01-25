#!/usr/bin/env python3
"""
Smart Documentation Validator

Distinguishes between:
- ERRORS: Links to files that should exist but are broken
- PLANNED: Links to documentation planned for future (from index.md)
- WARNINGS: Style and formatting issues

Usage:
    python validate-documentation-smart.py                    # Show all issues
    python validate-documentation-smart.py --strict           # Fail on errors only
    python validate-documentation-smart.py --planned-only     # Show only planned docs
    python validate-documentation-smart.py --errors-only      # Show only real errors
"""

import os
import re
import sys
from pathlib import Path
from typing import List, Set, Dict
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
    severity: str  # error, warning, info, planned
    file_path: str
    line_number: int
    message: str
    suggestion: str = ""

class SmartDocumentationValidator:
    """Enhanced validator that understands planned vs broken links"""
    
    def __init__(self, project_root: str, strict: bool = False):
        self.project_root = Path(project_root)
        self.docs_root = self.project_root / "docs"
        self.strict = strict
        self.issues: List[ValidationIssue] = []
        
        # Load planned documentation from index.md
        self.planned_files = self._load_planned_files()
        
        self.stats = {
            'files_checked': 0,
            'errors': 0,
            'warnings': 0,
            'info': 0,
            'planned': 0
        }
    
    def _load_planned_files(self) -> Set[str]:
        """Extract all linked files from index.md that are marked as planned"""
        planned = set()
        index_file = self.docs_root / "index.md"
        
        if not index_file.exists():
            return planned
        
        content = index_file.read_text(encoding='utf-8')
        
        # Pattern: | Component | [Name](path/to/file.md) | ⏳ Pending |
        # or: | Component | [Name](path/to/file.md) | 🚧 In Progress |
        pending_pattern = re.compile(r'\|[^|]*\[([^\]]+)\]\(([^)]+)\)[^|]*\|[^|]*[⏳🚧]')
        
        for match in pending_pattern.finditer(content):
            file_path = match.group(2)
            if not file_path.startswith(('http://', 'https://', '#')):
                planned.add(file_path)
        
        return planned
    
    def validate_all(self) -> bool:
        """Run all validation checks"""
        print(f"{Colors.BLUE}═══════════════════════════════════════════════════════════════{Colors.NC}")
        print(f"{Colors.BLUE}  Smart Documentation Validation{Colors.NC}")
        print(f"{Colors.BLUE}═══════════════════════════════════════════════════════════════{Colors.NC}\n")
        
        if self.planned_files:
            print(f"{Colors.CYAN}ℹ Found {len(self.planned_files)} planned documentation files{Colors.NC}")
        
        print()
        
        # Run validation checks
        self.check_required_files()
        self.check_markdown_files()
        self.check_internal_links()
        
        # Print results
        self.print_results()
        
        # Return success/failure based on real errors only
        return self.stats['errors'] == 0
    
    def check_required_files(self):
        """Check that core required files exist"""
        print(f"{Colors.BLUE}ℹ Checking required core files...{Colors.NC}")
        
        # Only check files that should exist from the start
        required_files = [
            "README.md",
            "docs/index.md",
            "docs/CHANGELOG.md",
            "docs/decisions-log.md",
            "docs/architecture/reference-architecture.md",
            "docs/diagrams/system-architecture.mmd",
            "docs/diagrams/data-model.mmd",
        ]
        
        for file_path in required_files:
            full_path = self.project_root / file_path
            if not full_path.exists():
                self.add_issue(
                    severity="error",
                    file_path=file_path,
                    line_number=0,
                    message=f"Core required file missing: {file_path}",
                    suggestion="This file should exist from initial setup"
                )
            else:
                self.stats['files_checked'] += 1
    
    def check_markdown_files(self):
        """Validate all existing Markdown files"""
        print(f"{Colors.BLUE}ℹ Checking existing Markdown files...{Colors.NC}")
        
        for md_file in self.docs_root.rglob("*.md"):
            self.stats['files_checked'] += 1
            self.validate_markdown_file(md_file)
    
    def validate_markdown_file(self, file_path: Path):
        """Validate a single Markdown file"""
        try:
            content = file_path.read_text(encoding='utf-8')
            lines = content.split('\n')
            
            # Check for title (H1)
            has_title = any(line.startswith('# ') for line in lines[:10])
            
            if not has_title:
                self.add_issue(
                    severity="warning",
                    file_path=str(file_path.relative_to(self.project_root)),
                    line_number=1,
                    message="No H1 title found in first 10 lines"
                )
        
        except Exception as e:
            self.add_issue(
                severity="error",
                file_path=str(file_path.relative_to(self.project_root)),
                line_number=0,
                message=f"Error reading file: {str(e)}"
            )
    
    def check_internal_links(self):
        """Check for broken internal links, distinguishing planned from broken"""
        print(f"{Colors.BLUE}ℹ Checking internal links...{Colors.NC}")
        
        link_pattern = re.compile(r'\[([^\]]+)\]\(([^)]+)\)')
        
        for md_file in self.docs_root.rglob("*.md"):
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
                    
                    # Remove anchor if present
                    target_str = str(target).split('#')[0]
                    target = Path(target_str)
                    
                    if not target.exists():
                        # Check if this is a planned file
                        relative_link = link_path
                        if relative_link in self.planned_files:
                            # This is a planned file - not an error
                            self.add_issue(
                                severity="planned",
                                file_path=str(md_file.relative_to(self.project_root)),
                                line_number=i,
                                message=f"Planned documentation: {link_path}",
                                suggestion="Will be created during development"
                            )
                        else:
                            # This is a real broken link
                            self.add_issue(
                                severity="error",
                                file_path=str(md_file.relative_to(self.project_root)),
                                line_number=i,
                                message=f"Broken link: {link_path}",
                                suggestion=f"File does not exist and is not marked as planned: {target}"
                            )
    
    def add_issue(self, severity: str, file_path: str, line_number: int, 
                  message: str, suggestion: str = ""):
        """Add a validation issue"""
        issue = ValidationIssue(
            severity=severity,
            file_path=file_path,
            line_number=line_number,
            message=message,
            suggestion=suggestion
        )
        self.issues.append(issue)
        
        if severity in ['errors', 'warnings', 'info', 'planned']:
            self.stats[severity] += 1
        else:
            self.stats['errors'] += 1
    
    def print_results(self):
        """Print validation results"""
        print(f"\n{Colors.BLUE}═══════════════════════════════════════════════════════════════{Colors.NC}")
        print(f"{Colors.BLUE}  Validation Results{Colors.NC}")
        print(f"{Colors.BLUE}═══════════════════════════════════════════════════════════════{Colors.NC}\n")
        
        # Group issues by severity
        errors = [i for i in self.issues if i.severity == 'error']
        warnings = [i for i in self.issues if i.severity == 'warning']
        infos = [i for i in self.issues if i.severity == 'info']
        planned = [i for i in self.issues if i.severity == 'planned']
        
        # Print errors (real problems)
        if errors:
            print(f"{Colors.RED}✗ ERRORS ({len(errors)}) - Real Issues:{Colors.NC}")
            for issue in errors[:10]:  # Limit display
                print(f"  {issue.file_path}:{issue.line_number} - {issue.message}")
                if issue.suggestion:
                    print(f"    → {issue.suggestion}")
            if len(errors) > 10:
                print(f"  ... and {len(errors) - 10} more errors")
            print()
        
        # Print warnings
        if warnings:
            print(f"{Colors.YELLOW}⚠ WARNINGS ({len(warnings)}):{Colors.NC}")
            for issue in warnings[:5]:
                print(f"  {issue.file_path}:{issue.line_number} - {issue.message}")
            if len(warnings) > 5:
                print(f"  ... and {len(warnings) - 5} more warnings")
            print()
        
        # Print planned documentation summary
        if planned:
            print(f"{Colors.CYAN}📋 PLANNED Documentation ({len(planned)}):{Colors.NC}")
            print(f"  These files will be created during development:")
            
            # Group by directory
            by_dir: Dict[str, int] = {}
            for issue in planned:
                link = issue.message.replace("Planned documentation: ", "")
                directory = link.split('/')[0] if '/' in link else 'root'
                by_dir[directory] = by_dir.get(directory, 0) + 1
            
            for directory, count in sorted(by_dir.items()):
                print(f"    {directory}/: {count} files")
            print()
        
        # Print summary
        print(f"{Colors.BLUE}Summary:{Colors.NC}")
        print(f"  Files checked: {self.stats['files_checked']}")
        print(f"  Real errors: {Colors.RED}{len(errors)}{Colors.NC}")
        print(f"  Warnings: {Colors.YELLOW}{len(warnings)}{Colors.NC}")
        print(f"  Planned docs: {Colors.CYAN}{len(planned)}{Colors.NC}")
        print()
        
        # Overall status
        if errors:
            print(f"{Colors.RED}✗ VALIDATION FAILED - {len(errors)} real errors found{Colors.NC}")
        elif warnings and self.strict:
            print(f"{Colors.YELLOW}⚠ VALIDATION PASSED with warnings{Colors.NC}")
        else:
            print(f"{Colors.GREEN}✓ VALIDATION PASSED{Colors.NC}")
            if planned:
                print(f"{Colors.CYAN}  ({len(planned)} files planned for future development){Colors.NC}")

def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Smart documentation validator that understands planned files',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        'project_root',
        nargs='?',
        default='.',
        help='Path to project root directory'
    )
    parser.add_argument(
        '--strict',
        action='store_true',
        help='Fail on warnings'
    )
    parser.add_argument(
        '--errors-only',
        action='store_true',
        help='Only show real errors, hide planned docs'
    )
    parser.add_argument(
        '--planned-only',
        action='store_true',
        help='Only show planned documentation'
    )
    
    args = parser.parse_args()
    
    # Validate
    validator = SmartDocumentationValidator(
        project_root=args.project_root,
        strict=args.strict
    )
    
    success = validator.validate_all()
    
    # Custom filtering
    if args.errors_only:
        print(f"\n{Colors.BLUE}Showing only real errors (hiding {validator.stats['planned']} planned files){Colors.NC}")
    elif args.planned_only:
        planned = [i for i in validator.issues if i.severity == 'planned']
        print(f"\n{Colors.CYAN}Planned Documentation ({len(planned)}):{Colors.NC}")
        for issue in planned:
            link = issue.message.replace("Planned documentation: ", "")
            print(f"  • {link}")
    
    sys.exit(0 if success else 1)

if __name__ == '__main__':
    main()
