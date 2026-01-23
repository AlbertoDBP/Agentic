# Repository Structure Specification

## Standard Structure

```
project-name/
├── docs/
│   ├── architecture/
│   │   ├── reference-architecture.md
│   │   ├── system-diagram.mmd
│   │   ├── component-interactions.mmd
│   │   ├── data-model.mmd
│   │   └── [other architecture diagrams].mmd
│   ├── functional/
│   │   ├── component-a-functional.md
│   │   ├── component-b-functional.md
│   │   └── [one per major component]
│   ├── implementation/
│   │   ├── component-a-impl.md
│   │   ├── component-b-impl.md
│   │   └── [one per implementation task]
│   ├── testing/
│   │   ├── test-matrix.md
│   │   ├── edge-cases.md
│   │   └── sla-definitions.md
│   ├── diagrams/
│   │   ├── [all-mermaid-diagrams-organized-by-type]
│   ├── decisions-log.md
│   ├── CHANGELOG.md
│   └── index.md
├── src/
│   ├── core/
│   │   ├── __init__.py
│   │   ├── orchestrator.py
│   │   └── base-classes.py
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── base-agent.py
│   │   └── [specific-agents]
│   ├── utils/
│   │   ├── __init__.py
│   │   └── [utility-modules]
│   └── tests/
│       ├── unit/
│       │   ├── test-core.py
│       │   └── test-[components].py
│       └── integration/
│           ├── test-orchestration.py
│           └── test-[integration-scenarios].py
├── README.md
├── requirements.txt (or pyproject.toml)
└── .gitignore
```

## Folder Naming Conventions

- **Use kebab-case** for folder names: `api-clients`, `data-models`, `ml-models`
- **Use snake_case** for Python files: `base_agent.py`, `test_orchestrator.py`
- **Use UPPERCASE** for documentation that's critical navigation: `README.md`, `CHANGELOG.md`
- **Use lowercase** for section-specific docs: `index.md`, `reference-architecture.md`

## Docs Folder Organization

### architecture/
Central location for all architectural diagrams and specifications.

- `reference-architecture.md` - Written system overview, components, relationships
- `system-diagram.mmd` - High-level component diagram
- `component-interactions.mmd` - How components communicate
- `data-model.mmd` - Data structures and relationships
- `[other-diagrams].mmd` - Specific workflows, state machines, etc.

### functional/
One document per major capability or component. Name format: `[component-name]-functional.md`

Contains:
- Purpose & Scope
- Responsibilities
- Interfaces
- Dependencies
- Success Criteria

### implementation/
One document per development task or component needing implementation. Name format: `[component-name]-impl.md`

Contains:
- Everything from functional spec
- Technical Design
- API Details
- Testing & Acceptance section

### testing/
Centralized testing specifications and matrices.

- `test-matrix.md` - Overall testing strategy, which components need what testing
- `edge-cases.md` - Known edge cases across components
- `sla-definitions.md` - Performance, reliability, scalability targets

### diagrams/
All Mermaid diagram files, organized by type:

```
diagrams/
├── architecture/
│   ├── system-overview.mmd
│   └── component-topology.mmd
├── workflows/
│   ├── agent-orchestration.mmd
│   ├── data-processing.mmd
│   └── error-handling.mmd
├── state-machines/
│   ├── agent-states.mmd
│   └── workflow-states.mmd
└── data/
    ├── entity-relationships.mmd
    └── data-flow.mmd
```

### Top-level docs/

- `index.md` - Master navigation and overview
- `decisions-log.md` - Design decisions and rationale
- `CHANGELOG.md` - History of changes, dated entries

## Src Folder Organization

### core/
Framework and infrastructure code.

- `orchestrator.py` - Main orchestration logic
- `base-classes.py` - Abstract base classes for extension
- `config.py` - Configuration management

### agents/
Agent implementations (for agentic platforms).

- `base-agent.py` - Abstract Agent class
- `routing-agent.py` - Example implementation
- `evaluation-agent.py` - Example implementation
- `[domain-specific-agents]`

### utils/
Utility modules for common functionality.

- `logging.py` - Logging utilities
- `decorators.py` - Common decorators
- `validators.py` - Input validation
- `api-clients.py` - External API integration

### tests/

**unit/** - Test individual functions/methods
```
test_core.py - Tests for core module
test_agents.py - Tests for agent implementations
test_utils.py - Tests for utilities
```

**integration/** - Test component interactions
```
test_orchestration.py - End-to-end orchestration
test_agent_handoff.py - How agents communicate
test_data_flow.py - Data consistency across components
```

## File Naming Patterns

| Type | Pattern | Example |
|------|---------|---------|
| Spec Document | `[component]-[type].md` | `agent-routing-impl.md` |
| Functional Spec | `[component]-functional.md` | `orchestrator-functional.md` |
| Implementation Spec | `[component]-impl.md` | `event-processor-impl.md` |
| Diagram | `[purpose].mmd` | `system-architecture.mmd` |
| Test File | `test_[module].py` | `test_orchestrator.py` |
| Source File | `[module_name].py` | `base_agent.py` |

## Cross-References in Documentation

**From implementation specs to functional specs:**
```markdown
See [Component Name Functional Spec](../functional/component-name-functional.md)
for higher-level design.
```

**From specs to diagrams:**
```markdown
See [System Architecture Diagram](../architecture/system-diagram.mmd)
for visual overview.
```

**From diagrams to implementation specs:**
```markdown
For implementation details, see [Component Implementation](../implementation/component-impl.md).
```

**From tests to acceptance criteria:**
```markdown
These tests validate the acceptance criteria defined in 
[Component Implementation Spec](../implementation/component-impl.md#acceptance-criteria).
```

## Master Index (index.md) Structure

```markdown
# [Platform/Component Name] - Master Index

## Overview
[Quick summary]

## Navigation

### Architecture
- [Reference Architecture](architecture/reference-architecture.md)
- [System Diagrams](diagrams/)
- [Data Model](architecture/data-model.mmd)

### Specifications
- Functional Specs: [List with links]
- Implementation Specs: [List with links]

### Code
- [Source Structure](../src/)
- [Code Scaffolds](code-scaffolds.md)

### Testing
- [Test Matrix](testing/test-matrix.md)
- [Edge Cases](testing/edge-cases.md)

### Operations & History
- [Decisions Log](decisions-log.md)
- [Changelog](CHANGELOG.md)

## Component Status
| Component | Status | Spec | Code |
|-----------|--------|------|------|
| Component A | Stable | [Link] | [Link] |
| Component B | In Progress | [Link] | [Link] |
```

## Conventions for Stability Markers

Mark sections with status badges:

```markdown
## Component X - Agent Routing
**Status**: Stable | **Last Updated**: 2025-01-23

## Component Y - Evaluation Engine
**Status**: In Progress | **Last Updated**: 2025-01-20

## Component Z - Data Model
**Status**: Under Review | **Last Updated**: 2025-01-22
```

This allows quick identification of what's settled vs. in flux.
