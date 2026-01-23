---
name: platform-documentation-orchestrator
description: Orchestrate complete documentation generation for AI agentic platforms. Given a design input, this skill generates reference architectures, functional specifications, implementation specifications with integrated testing specs, code scaffolds, folder structures, and comprehensive repository organization. Use when building new AI platform components or features and need all documentation, testing specifications, and code structure generated in a coordinated workflow. Outputs are formatted for Google Drive and Mermaid diagrams.
---

# Platform Documentation Orchestrator

This skill provides a complete workflow for taking a platform design and generating comprehensive, well-organized documentation that drives development. It ensures architecture diagrams, functional specs, implementation specs with testing, code scaffolds, and repository organization are all synchronized and linked.

## Core Workflow

The orchestrator follows these steps in sequence:

1. **Analyze the design input** - Extract key components, interactions, and constraints
2. **Create reference architecture** - Generate system overview diagram (Mermaid) and written specification
3. **Define functional specifications** - One spec per major capability/component
4. **Define implementation specifications** - Detailed specs with integrated testing sections
5. **Generate code scaffolds** - Language-appropriate skeleton implementations
6. **Create folder structure** - Organized repository layout
7. **Produce linking documents** - Master index and navigation
8. **Generate setup instructions** - Google Drive folder creation and organization

## Input Format

When you provide a design, include:

```
# [Platform/Component Name] Design Input

## Overview
[What is this? 2-3 sentence summary]

## Design Description
[Your design - prose, outline, architecture sketch, or structured description]

## Key Components
- Component A: [brief description]
- Component B: [brief description]
- Component C: [brief description]

## Integration Points
[How does this fit with existing systems? What does it depend on?]

## Technology Stack
[Languages, frameworks, databases, APIs]

## Success Criteria
[What defines completion/success for this component?]

## Special Constraints
[Any important limitations or patterns to follow]
```

## Output Organization

Claude generates the following structure (see references/repository-structure.md for detailed breakdown):

```
project-name/
├── docs/
│   ├── architecture/
│   │   ├── reference-architecture.md
│   │   ├── system-diagram.mmd
│   │   ├── component-interactions.mmd
│   │   └── data-model.mmd
│   ├── functional/
│   │   └── [one .md per major component/capability]
│   ├── implementation/
│   │   └── [one .md per implementation task]
│   ├── testing/
│   │   ├── test-matrix.md
│   │   └── edge-cases.md
│   ├── diagrams/
│   │   └── [all .mmd files organized by type]
│   ├── decisions-log.md
│   ├── CHANGELOG.md
│   └── index.md (master navigation)
├── src/
│   ├── [component-name]/
│   │   ├── __init__.py (or equivalent)
│   │   ├── main.py (or entry point)
│   │   └── test_[component].py
│   └── [other components...]
└── README.md
```

## Specification Template Structure

### Functional Specification Format

Each functional spec includes:
- **Purpose & Scope** - What does this component do?
- **Responsibilities** - Specific tasks it owns
- **Interfaces** - Input/output contracts
- **Dependencies** - What it needs from other components
- **Success Criteria** - How to measure it's working correctly
- **Non-Functional Requirements** - Performance, reliability, scalability

### Implementation Specification Format

Each implementation spec includes everything from functional spec, plus:
- **Technical Design** - Architecture details, algorithms, data structures
- **API/Interface Details** - Exact method signatures, parameters, return values
- **Dependencies & Integrations** - Specific systems, libraries, versions
- **Testing & Acceptance**
  - Unit Test Requirements - What functions/methods, what edge cases
  - Integration Test Scenarios - How it works with dependencies
  - Acceptance Criteria (Testable) - Specific, measurable, verifiable
  - Known Edge Cases - Failure modes, boundary conditions
  - Performance/Reliability SLAs - If applicable
- **Implementation Notes** - Gotchas, best practices, references

## Diagram Conventions (Mermaid)

- **System Architecture**: Flowchart showing components and data flows
- **Component Interactions**: Sequence diagrams for key workflows
- **Data Model**: Entity relationship or class diagrams
- **State Machines**: For agent behaviors or complex workflows

All diagrams are stored as `.mmd` files (text-based, version-controllable).

## Incremental Updates

For revisions to existing designs, Claude generates:
- Updated specifications (only changed sections, clearly marked)
- Updated diagrams
- Change Summary document
- CHANGELOG.md entry
- Decisions Log entry
- Updated master index

See references/iteration-workflow.md for detailed revision patterns.

## Google Drive Organization

Claude provides both:
1. **Folder structure specification** - Exactly how to create folders in Drive
2. **Organization script** - Step-by-step instructions or Python script to automate setup

See references/google-drive-setup.md for details.

## Documentation Standards

All generated documentation follows these conventions:
- **Heading hierarchy**: H1 for title, H2 for sections, H3 for subsections
- **Code blocks**: Always include language identifier (```python, ```javascript, etc.)
- **Links**: Use markdown links to other documentation
- **Names**: Use consistent naming throughout (component names, file paths, etc.)
- **Dates**: ISO format (YYYY-MM-DD)

See references/documentation-standards.md for detailed style guide.

## Testing Specifications (Critical)

Testing is integrated into every implementation spec, not separate. Key principles:

- **Determinism testing**: For components with expected consistency, define variance tolerance
- **Failure mode testing**: Cover timeout scenarios, edge case inputs, resource exhaustion
- **Integration testing**: Validate handoffs and data consistency across components
- **Performance testing**: Define SLAs for latency, throughput, resource usage
- **Agent-specific testing**: For agentic components, include behavioral consistency metrics

See references/testing-specification-patterns.md for detailed testing framework.

## Master Index Document

The master index serves as the navigation hub and includes:
- Overview of the platform/component
- Quick links to all specification documents
- Folder structure diagram
- How to navigate the documentation
- Links to code scaffolds
- Status of each component (stable, in-progress, under-review)
- Change history summary

## How to Use This Skill

### For a new component design:

```
INSTRUCTION: "Using the Platform Documentation Orchestrator skill, generate 
complete documentation for this design. I want:
1. Reference architecture with Mermaid diagrams
2. Functional specs for [list components]
3. Implementation specs for [priority components] with testing specs
4. Code scaffolds in Python
5. Google Drive folder setup instructions
6. Master index linking everything"
```

### For revisions to existing design:

```
INSTRUCTION: "Update the documentation for [component name]. Changed: [describe change].
Please generate:
1. Updated functional/implementation specs
2. Updated diagrams
3. Change Summary document
4. Updated CHANGELOG.md entry
5. Updated decisions-log.md entry
6. Updated master index"
```

## Bundled References

- `references/repository-structure.md` - Detailed folder organization patterns
- `references/google-drive-setup.md` - How to organize in Google Drive
- `references/documentation-standards.md` - Style guide and conventions
- `references/testing-specification-patterns.md` - Testing framework and patterns
- `references/iteration-workflow.md` - How to handle revisions
- `references/mermaid-conventions.md` - Diagram styles and patterns
- `scripts/validate-documentation.py` - Validates generated docs for completeness
- `scripts/generate-folder-structure.py` - Creates folder structure script for Drive

## Key Principles

**Integration over Separation**: Testing, architecture decisions, and acceptance criteria are woven into specs, not separated.

**Traceability**: Each implementation spec links to its functional spec; each test links to success criteria.

**Version Control**: All outputs are text-based (Markdown, Mermaid) for easy Git tracking and diffs.

**Progressive Disclosure**: Master index provides navigation; detailed specs provide depth when needed.

**Idempotence**: Running the workflow on the same design produces the same outputs (for stable designs).
