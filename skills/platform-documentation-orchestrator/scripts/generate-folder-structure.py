#!/usr/bin/env python3
"""
Generate folder structure for Platform Documentation Orchestrator.

This script creates the recommended folder structure locally or in Google Drive.
"""

import os
import sys
from pathlib import Path
from typing import List


class FolderStructureGenerator:
    """Generate recommended folder structure."""
    
    FOLDER_STRUCTURE = {
        'docs': {
            'architecture': None,
            'functional': None,
            'implementation': None,
            'testing': None,
            'diagrams': {
                'architecture-diagrams': None,
                'workflow-diagrams': None,
                'state-machines': None,
                'data-diagrams': None,
            }
        },
        'src': {
            'core': None,
            'agents': None,
            'utils': None,
            'tests': {
                'unit': None,
                'integration': None,
            }
        }
    }
    
    def __init__(self, root_path: str = '.'):
        self.root_path = Path(root_path)
    
    def create_structure(self) -> bool:
        """Create the folder structure."""
        try:
            self._create_folders(self.root_path, self.FOLDER_STRUCTURE)
            self._create_placeholder_files()
            self._create_dotfiles()
            print(f"✅ Folder structure created at: {self.root_path}")
            return True
        except Exception as e:
            print(f"❌ Error creating structure: {e}")
            return False
    
    def _create_folders(self, base_path: Path, structure: dict) -> None:
        """Recursively create folders."""
        for name, subfolders in structure.items():
            folder_path = base_path / name
            folder_path.mkdir(parents=True, exist_ok=True)
            
            if isinstance(subfolders, dict):
                self._create_folders(folder_path, subfolders)
    
    def _create_placeholder_files(self) -> None:
        """Create placeholder/template files."""
        placeholders = [
            ('docs/index.md', self._template_master_index()),
            ('docs/CHANGELOG.md', self._template_changelog()),
            ('docs/decisions-log.md', self._template_decisions_log()),
            ('docs/architecture/reference-architecture.md', 
             self._template_reference_architecture()),
            ('README.md', self._template_readme()),
        ]
        
        for filepath, content in placeholders:
            full_path = self.root_path / filepath
            full_path.parent.mkdir(parents=True, exist_ok=True)
            if not full_path.exists():
                full_path.write_text(content)
                print(f"  Created: {filepath}")
    
    def _create_dotfiles(self) -> None:
        """Create .gitignore and other dotfiles."""
        gitignore_path = self.root_path / '.gitignore'
        if not gitignore_path.exists():
            gitignore_path.write_text(self._template_gitignore())
            print(f"  Created: .gitignore")
    
    @staticmethod
    def _template_master_index() -> str:
        return """# Master Index

## Overview

[Project Name] - Documentation and Architecture

This is the master navigation hub for all documentation, specifications, 
and technical architecture.

## Quick Navigation

### Architecture & Design
- [Reference Architecture](architecture/reference-architecture.md)
- [System Architecture Diagram](diagrams/architecture-diagrams/)
- [Component Interactions](diagrams/workflow-diagrams/)
- [Data Model](architecture/data-model.mmd)

### Specifications
- **Functional Specifications**: [docs/functional/](functional/)
- **Implementation Specifications**: [docs/implementation/](implementation/)

### Code
- **Source Code**: [src/](../src/)

### Testing
- [Test Matrix](testing/test-matrix.md)
- [Edge Cases](testing/edge-cases.md)
- [SLA Definitions](testing/sla-definitions.md)

### History & Decisions
- [Decisions Log](decisions-log.md)
- [CHANGELOG](CHANGELOG.md)

## Component Status

| Component | Status | Spec |
|-----------|--------|------|
| [Add components] | TBD | [Link] |

## How to Use This Documentation

1. **New to the project?** Start with [Reference Architecture](architecture/reference-architecture.md)
2. **Understanding a component?** Check [Functional Specs](functional/)
3. **Building something?** See [Implementation Specs](implementation/)
4. **Need to know why?** Check [Decisions Log](decisions-log.md)

## Documentation Standards

All documentation follows the patterns in:
- [Documentation Standards](../docs/documentation-standards.md)
- [Mermaid Conventions](../docs/mermaid-conventions.md)
- [Testing Patterns](../docs/testing-specification-patterns.md)

Last Updated: [Date]
"""
    
    @staticmethod
    def _template_changelog() -> str:
        return """# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added
- Initial project structure

### Changed
- (none yet)

### Fixed
- (none yet)

### Deprecated
- (none yet)

## Guidelines

- Link to relevant spec when documenting changes
- Include date for significant changes
- Group related changes
- Explain WHY, not just WHAT
"""
    
    @staticmethod
    def _template_decisions_log() -> str:
        return """# Decisions Log

Record of important architectural and design decisions.

## Format

```
## Decision: [Title] - [Date]

**Status**: Approved | In Review | Proposed

**Context**: 
[What problem were we solving?]

**Options Considered**:
1. [Option A] - Pros/Cons
2. [Option B] - Pros/Cons  
3. [Option C] - **Selected** - Why selected

**Consequences**: 
[What does this enable/prevent?]

**Related Specs**: 
- [Link to affected specs]
```

## Decisions

### To be added during development...
"""
    
    @staticmethod
    def _template_reference_architecture() -> str:
        return """# Reference Architecture

## System Overview

[Project Name] consists of the following major components:

### Components

1. **[Component A]** - [Purpose]
2. **[Component B]** - [Purpose]
3. **[Component C]** - [Purpose]

## Architecture Diagram

See [system-diagram.mmd](diagrams/architecture-diagrams/system-diagram.mmd)

## Data Model

See [data-model.mmd](diagrams/data-diagrams/data-model.mmd)

## Key Principles

- [Principle 1]
- [Principle 2]
- [Principle 3]

## Technology Stack

- **Language**: [e.g., Python 3.11+]
- **Framework**: [e.g., FastAPI, etc.]
- **Database**: [e.g., PostgreSQL, etc.]
- **API**: [e.g., REST, GraphQL, etc.]

## Integration Points

- **[External System A]**: [How integrated]
- **[External System B]**: [How integrated]

See individual component specs for detailed integration information.

## Constraints & Considerations

- [Constraint 1]
- [Constraint 2]
- [Constraint 3]

Last Updated: [Date]
"""
    
    @staticmethod
    def _template_readme() -> str:
        return """# [Project Name]

[Brief project description]

## Quick Start

1. Clone repository
2. Read [docs/index.md](docs/index.md) for navigation
3. Start with [Reference Architecture](docs/architecture/reference-architecture.md)

## Structure

```
.
├── docs/                    # All documentation
│   ├── architecture/        # System architecture & diagrams
│   ├── functional/          # Functional specifications
│   ├── implementation/      # Implementation specifications
│   ├── testing/             # Testing specifications
│   ├── diagrams/            # Mermaid diagrams
│   ├── index.md            # Master index
│   ├── CHANGELOG.md        # Change history
│   └── decisions-log.md    # Design decisions
├── src/                     # Source code
│   ├── core/               # Core framework
│   ├── agents/             # Agent implementations
│   ├── utils/              # Utilities
│   └── tests/              # Test files
└── README.md               # This file
```

## Documentation

- **[Master Index](docs/index.md)** - Start here
- **[Reference Architecture](docs/architecture/reference-architecture.md)** - System overview
- **[Implementation Specs](docs/implementation/)** - Detailed specifications

## Development

[Add development setup instructions]

## Contributing

[Add contribution guidelines]

## License

[Add license]
"""
    
    @staticmethod
    def _template_gitignore() -> str:
        return """# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
env/
venv/
ENV/
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
*.egg-info/
.installed.cfg
*.egg

# IDE
.vscode/
.idea/
*.swp
*.swo
*~
.DS_Store

# Testing
.pytest_cache/
.coverage
htmlcov/

# Project specific
.env
local/
temp/
tmp/

# Documentation build artifacts
site/
"""
    
    def print_structure(self) -> None:
        """Print the folder structure."""
        print("\nFolder structure to be created:")
        self._print_tree(self.FOLDER_STRUCTURE, "", "  ")
    
    @staticmethod
    def _print_tree(structure: dict, prefix: str, indent: str) -> None:
        """Print tree representation of structure."""
        items = list(structure.items())
        for i, (name, subfolders) in enumerate(items):
            is_last = i == len(items) - 1
            current = "└── " if is_last else "├── "
            print(f"{prefix}{current}{name}/")
            
            if isinstance(subfolders, dict):
                extension = "    " if is_last else "│   "
                FolderStructureGenerator._print_tree(
                    subfolders, 
                    prefix + extension, 
                    indent
                )


def main():
    """Main entry point."""
    if len(sys.argv) > 1:
        root_path = sys.argv[1]
    else:
        root_path = '.'
    
    generator = FolderStructureGenerator(root_path)
    
    print(f"Creating folder structure at: {root_path}")
    generator.print_structure()
    
    if input("\nProceed? (y/n): ").lower() == 'y':
        success = generator.create_structure()
        sys.exit(0 if success else 1)
    else:
        print("Cancelled.")
        sys.exit(0)


if __name__ == '__main__':
    main()
