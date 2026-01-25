#!/usr/bin/env python3
"""
Documentation Validation Script

Validates the completeness and consistency of platform documentation.
Checks for broken links, missing sections, inconsistent naming, etc.

Usage:
    python validate-documentation.py /path/to/project
    python validate-documentation.py --strict  # Fail on warnings
    python validate-documentation.py --fix     # Auto-fix issues where possible
"""

import os
import re
import sys
import json
from pathlib import Path
from typing import List, Dict, Tuple, Set
from dataclasses import dataclass
from collections import defaultdict

# Color codes for terminal output
class Colors:
    RED = '\033[0;31m'
    GREEN = '\033[0;32m'
    YELLOW = '\033[1;33m'
    BLUE = '\033[0;34m'
    NC = '\033[0m'  # No Color

@dataclass
class ValidationIssue:
    """Represents a documentation issue"""
    severity: str  # error, warning, info
    file_path: str
    line_number: int
    message: str
    suggestion: str = ""

class DocumentationValidator:
    """Validates documentation structure and content"""
    
    def __init__(self, project_root: str, strict: bool = False, fix: bool = False):
        self.project_root = Path(project_root)
        self.docs_root = self.project_root / "docs"
        self.strict = strict
        self.fix = fix
        self.issues: List[ValidationIssue] = []
        self.stats = {
            'files_checked': 0,
            'errors': 0,
            'warnings': 0,
            'info': 0,
            'fixed': 0
        }
    
    def validate_all(self) -> bool:
        """Run all validation checks"""
        print(f"{Colors.BLUE}═══════════════════════════════════════════════════════════════{Colors.NC}")
        print(f"{Colors.BLUE}  Documentation Validation{Colors.NC}")
        print(f"{Colors.BLUE}═══════════════════════════════════════════════════════════════{Colors.NC}\n")
        
        # Run validation checks
        self.check_required_files()
        self.check_markdown_files()
        self.check_internal_links()
        self.check_mermaid_diagrams()
        self.check_code_blocks()
        self.check_consistency()
        self.check_frontmatter()
        
        # Print results
        self.print_results()
        
        # Return success/failure
        has_errors = self.stats['errors'] > 0
        has_warnings = self.stats['warnings'] > 0
        
        if self.strict:
            return not (has_errors or has_warnings)
        else:
            return not has_errors
    
    def check_required_files(self):
        """Check that all required documentation files exist"""
        print(f"{Colors.BLUE}ℹ Checking required files...{Colors.NC}")
        
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
                    message=f"Required file missing: {file_path}",
                    suggestion="Create this file using the appropriate template"
                )
            else:
                self.stats['files_checked'] += 1
    
    def check_markdown_files(self):
        """Validate all Markdown files"""
        print(f"{Colors.BLUE}ℹ Checking Markdown files...{Colors.NC}")
        
        for md_file in self.docs_root.rglob("*.md"):
            self.stats['files_checked'] += 1
            self.validate_markdown_file(md_file)
    
    def validate_markdown_file(self, file_path: Path):
        """Validate a single Markdown file"""
        try:
            content = file_path.read_text(encoding='utf-8')
            lines = content.split('\n')
            
            # Check for title (H1)
            has_title = False
            for i, line in enumerate(lines[:10]):  # Check first 10 lines
                if line.startswith('# '):
                    has_title = True
                    break
            
            if not has_title:
                self.add_issue(
                    severity="warning",
                    file_path=str(file_path.relative_to(self.project_root)),
                    line_number=1,
                    message="No H1 title found in first 10 lines",
                    suggestion="Add a clear H1 title at the top of the document"
                )
            
            # Check for proper heading hierarchy
            prev_level = 0
            for i, line in enumerate(lines, 1):
                if line.startswith('#'):
                    level = len(line.split()[0])
                    if level > prev_level + 1 and prev_level > 0:
                        self.add_issue(
                            severity="warning",
                            file_path=str(file_path.relative_to(self.project_root)),
                            line_number=i,
                            message=f"Heading hierarchy skip: H{prev_level} to H{level}",
                            suggestion="Use incremental heading levels (H1 → H2 → H3)"
                        )
                    prev_level = level
            
            # Check for very long lines (> 120 chars, excluding code blocks)
            in_code_block = False
            for i, line in enumerate(lines, 1):
                if line.strip().startswith('```'):
                    in_code_block = not in_code_block
                elif not in_code_block and len(line) > 120 and not line.startswith('#'):
                    self.add_issue(
                        severity="info",
                        file_path=str(file_path.relative_to(self.project_root)),
                        line_number=i,
                        message=f"Line too long ({len(line)} chars)",
                        suggestion="Consider breaking into multiple lines for readability"
                    )
        
        except Exception as e:
            self.add_issue(
                severity="error",
                file_path=str(file_path.relative_to(self.project_root)),
                line_number=0,
                message=f"Error reading file: {str(e)}"
            )
    
    def check_internal_links(self):
        """Check for broken internal links"""
        print(f"{Colors.BLUE}ℹ Checking internal links...{Colors.NC}")
        
        # Pattern to match Markdown links: [text](path)
        link_pattern = re.compile(r'\[([^\]]+)\]\(([^)]+)\)')
        
        for md_file in self.docs_root.rglob("*.md"):
            content = md_file.read_text(encoding='utf-8')
            lines = content.split('\n')
            
            for i, line in enumerate(lines, 1):
                for match in link_pattern.finditer(line):
                    link_text = match.group(1)
                    link_path = match.group(2)
                    
                    # Skip external links and anchors
                    if link_path.startswith(('http://', 'https://', '#')):
                        continue
                    
                    # Resolve relative link
                    if link_path.startswith('/'):
                        # Absolute from project root
                        target = self.project_root / link_path.lstrip('/')
                    else:
                        # Relative to current file
                        target = (md_file.parent / link_path).resolve()
                    
                    # Remove anchor if present
                    target_str = str(target).split('#')[0]
                    target = Path(target_str)
                    
                    if not target.exists():
                        self.add_issue(
                            severity="error",
                            file_path=str(md_file.relative_to(self.project_root)),
                            line_number=i,
                            message=f"Broken link: {link_path}",
                            suggestion=f"Target file does not exist: {target}"
                        )
    
    def check_mermaid_diagrams(self):
        """Validate Mermaid diagram syntax"""
        print(f"{Colors.BLUE}ℹ Checking Mermaid diagrams...{Colors.NC}")
        
        for mmd_file in self.docs_root.rglob("*.mmd"):
            self.stats['files_checked'] += 1
            
            try:
                content = mmd_file.read_text(encoding='utf-8')
                
                # Check for proper Mermaid code fence
                if not content.strip().startswith('```mermaid'):
                    self.add_issue(
                        severity="error",
                        file_path=str(mmd_file.relative_to(self.project_root)),
                        line_number=1,
                        message="Mermaid file should start with ```mermaid",
                        suggestion="Add ```mermaid at the beginning and ``` at the end"
                    )
                
                if not content.strip().endswith('```'):
                    self.add_issue(
                        severity="error",
                        file_path=str(mmd_file.relative_to(self.project_root)),
                        line_number=len(content.split('\n')),
                        message="Mermaid file should end with ```",
                        suggestion="Add ``` at the end to close the code fence"
                    )
                
                # Check for common diagram types
                diagram_type = None
                for line in content.split('\n')[1:10]:  # Skip first line (```)
                    line = line.strip()
                    if line.startswith(('graph', 'flowchart', 'sequenceDiagram', 'erDiagram', 
                                       'classDiagram', 'stateDiagram', 'gantt')):
                        diagram_type = line.split()[0]
                        break
                
                if not diagram_type:
                    self.add_issue(
                        severity="warning",
                        file_path=str(mmd_file.relative_to(self.project_root)),
                        line_number=2,
                        message="Could not determine Mermaid diagram type",
                        suggestion="Ensure second line specifies diagram type (graph, flowchart, etc.)"
                    )
            
            except Exception as e:
                self.add_issue(
                    severity="error",
                    file_path=str(mmd_file.relative_to(self.project_root)),
                    line_number=0,
                    message=f"Error reading Mermaid file: {str(e)}"
                )
    
    def check_code_blocks(self):
        """Check code blocks have language identifiers"""
        print(f"{Colors.BLUE}ℹ Checking code blocks...{Colors.NC}")
        
        for md_file in self.docs_root.rglob("*.md"):
            content = md_file.read_text(encoding='utf-8')
            lines = content.split('\n')
            
            for i, line in enumerate(lines, 1):
                if line.strip() == '```':
                    self.add_issue(
                        severity="info",
                        file_path=str(md_file.relative_to(self.project_root)),
                        line_number=i,
                        message="Code block without language identifier",
                        suggestion="Add language after ``` (e.g., ```python, ```bash)"
                    )
    
    def check_consistency(self):
        """Check for consistent naming and terminology"""
        print(f"{Colors.BLUE}ℹ Checking naming consistency...{Colors.NC}")
        
        # Collect all component names mentioned
        component_names = defaultdict(set)
        
        for md_file in self.docs_root.rglob("*.md"):
            content = md_file.read_text(encoding='utf-8')
            
            # Find agent references
            agent_pattern = re.compile(r'Agent\s+(\d+|[IVX]+)', re.IGNORECASE)
            for match in agent_pattern.finditer(content):
                component_names['agents'].add(match.group(0))
            
            # Find service references
            service_pattern = re.compile(r'(\w+[-_]?\w+)\s+[Ss]ervice')
            for match in service_pattern.finditer(content):
                component_names['services'].add(match.group(1))
        
        # Check for inconsistent naming (e.g., Agent 1 vs Agent 01 vs Agent One)
        agent_numbers = component_names.get('agents', set())
        if len(agent_numbers) > 0:
            # Group by number
            agent_by_num = defaultdict(list)
            for agent in agent_numbers:
                # Extract number
                num_match = re.search(r'\d+', agent)
                if num_match:
                    num = int(num_match.group())
                    agent_by_num[num].append(agent)
            
            for num, variants in agent_by_num.items():
                if len(variants) > 1:
                    self.add_issue(
                        severity="warning",
                        file_path="docs/",
                        line_number=0,
                        message=f"Inconsistent agent naming: {', '.join(sorted(variants))}",
                        suggestion=f"Use consistent format (e.g., 'Agent {num:02d}')"
                    )
    
    def check_frontmatter(self):
        """Check for consistent frontmatter in specifications"""
        print(f"{Colors.BLUE}ℹ Checking frontmatter...{Colors.NC}")
        
        required_frontmatter = ['Version', 'Date', 'Status', 'Priority']
        
        spec_dirs = [
            self.docs_root / 'functional',
            self.docs_root / 'implementation'
        ]
        
        for spec_dir in spec_dirs:
            if not spec_dir.exists():
                continue
            
            for md_file in spec_dir.glob("*.md"):
                content = md_file.read_text(encoding='utf-8')
                lines = content.split('\n')
                
                # Check first 10 lines for frontmatter
                frontmatter_found = set()
                for line in lines[:15]:
                    for field in required_frontmatter:
                        if line.startswith(f'**{field}**'):
                            frontmatter_found.add(field)
                
                missing = set(required_frontmatter) - frontmatter_found
                if missing:
                    self.add_issue(
                        severity="warning",
                        file_path=str(md_file.relative_to(self.project_root)),
                        line_number=1,
                        message=f"Missing frontmatter fields: {', '.join(missing)}",
                        suggestion="Add required frontmatter at top of specification"
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
        self.stats[severity if severity in ['errors', 'warnings', 'info'] else 'errors'] += 1
    
    def print_results(self):
        """Print validation results"""
        print(f"\n{Colors.BLUE}═══════════════════════════════════════════════════════════════{Colors.NC}")
        print(f"{Colors.BLUE}  Validation Results{Colors.NC}")
        print(f"{Colors.BLUE}═══════════════════════════════════════════════════════════════{Colors.NC}\n")
        
        # Group issues by severity
        errors = [i for i in self.issues if i.severity == 'error']
        warnings = [i for i in self.issues if i.severity == 'warning']
        infos = [i for i in self.issues if i.severity == 'info']
        
        # Print errors
        if errors:
            print(f"{Colors.RED}✗ Errors ({len(errors)}):{Colors.NC}")
            for issue in errors:
                print(f"  {issue.file_path}:{issue.line_number} - {issue.message}")
                if issue.suggestion:
                    print(f"    → {issue.suggestion}")
            print()
        
        # Print warnings
        if warnings:
            print(f"{Colors.YELLOW}⚠ Warnings ({len(warnings)}):{Colors.NC}")
            for issue in warnings:
                print(f"  {issue.file_path}:{issue.line_number} - {issue.message}")
                if issue.suggestion:
                    print(f"    → {issue.suggestion}")
            print()
        
        # Print info (only if no errors/warnings or in verbose mode)
        if infos and not (errors or warnings):
            print(f"{Colors.BLUE}ℹ Info ({len(infos)}):{Colors.NC}")
            for issue in infos[:5]:  # Limit to first 5
                print(f"  {issue.file_path}:{issue.line_number} - {issue.message}")
            if len(infos) > 5:
                print(f"  ... and {len(infos) - 5} more")
            print()
        
        # Print summary
        print(f"{Colors.BLUE}Summary:{Colors.NC}")
        print(f"  Files checked: {self.stats['files_checked']}")
        print(f"  Errors: {Colors.RED}{len(errors)}{Colors.NC}")
        print(f"  Warnings: {Colors.YELLOW}{len(warnings)}{Colors.NC}")
        print(f"  Info: {Colors.BLUE}{len(infos)}{Colors.NC}")
        
        if self.stats['fixed'] > 0:
            print(f"  Fixed: {Colors.GREEN}{self.stats['fixed']}{Colors.NC}")
        
        print()
        
        # Overall status
        if errors:
            print(f"{Colors.RED}✗ Validation FAILED{Colors.NC}")
        elif warnings and self.strict:
            print(f"{Colors.YELLOW}⚠ Validation PASSED with warnings (strict mode){Colors.NC}")
        else:
            print(f"{Colors.GREEN}✓ Validation PASSED{Colors.NC}")

def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Validate platform documentation',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python validate-documentation.py .
  python validate-documentation.py --strict
  python validate-documentation.py --fix
        """
    )
    parser.add_argument(
        'project_root',
        nargs='?',
        default='.',
        help='Path to project root directory (default: current directory)'
    )
    parser.add_argument(
        '--strict',
        action='store_true',
        help='Fail on warnings (not just errors)'
    )
    parser.add_argument(
        '--fix',
        action='store_true',
        help='Automatically fix issues where possible'
    )
    
    args = parser.parse_args()
    
    # Validate
    validator = DocumentationValidator(
        project_root=args.project_root,
        strict=args.strict,
        fix=args.fix
    )
    
    success = validator.validate_all()
    
    sys.exit(0 if success else 1)

if __name__ == '__main__':
    main()
