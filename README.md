# Agentic Development

Complete documentation and orchestration system for AI agentic platform development using Claude.

## Overview

This repository contains a comprehensive **Claude Skill** for orchestrating complete documentation generation for AI agentic platforms. It transforms design inputs into production-ready documentation, specifications, diagrams, code scaffolds, and organized repository structures.

## Quick Start

### For Claude Users

1. **Access the SKILL**: Reference `SKILL/SKILL.md` when working with Claude
2. **Tell Claude**: "Use the Platform Documentation Orchestrator skill to generate documentation for [your design]"
3. **Claude generates**: Complete architecture, specs, tests, and code scaffolds

### For GitHub Users

1. **Clone this repository**:
   ```bash
   git clone https://github.com/AlbertoDBP/Agentic.git
   cd Agentic
   ```

2. **Review the SKILL**:
   ```bash
   cat SKILL/SKILL.md
   ```

3. **Read the documentation**:
   - `docs/README.md` - Navigation guide
   - `docs/EXECUTIVE_SUMMARY.md` - What this system provides
   - `docs/USAGE_GUIDE.md` - How to use with Claude

## Repository Structure

```
Agentic/
├── SKILL/                          # Core orchestration skill
│   └── SKILL.md                    # Main skill guide for Claude
│
├── references/                     # Detailed reference documents
│   ├── repository-structure.md     # Folder organization patterns
│   ├── google-drive-setup.md       # Collaboration setup (optional)
│   ├── documentation-standards.md  # Writing standards & templates
│   ├── testing-specification-patterns.md  # Testing frameworks
│   ├── iteration-workflow.md       # How to update specs
│   └── mermaid-conventions.md      # Diagram standards
│
├── scripts/                        # Automation tools
│   ├── validate-documentation.py   # Check documentation quality
│   └── generate-folder-structure.py # Create folder structure
│
├── docs/                           # Documentation & guides
│   ├── README.md                   # Navigation guide
│   ├── EXECUTIVE_SUMMARY.md        # Overview
│   ├── SKILL_SUMMARY.md           # Skill components
│   ├── USAGE_GUIDE.md             # How to use
│   ├── COMPLETE_DELIVERABLES.md   # Detailed breakdown
│   └── DELIVERY_SUMMARY.md        # What was delivered
│
└── README.md                       # This file
```

## What This Provides

### Core Skill (`SKILL/`)
Complete orchestration guide that tells Claude to:
- ✅ Analyze platform/component designs
- ✅ Generate reference architecture (Mermaid diagrams)
- ✅ Create functional specifications
- ✅ Create implementation specifications with **integrated testing specs**
- ✅ Generate code scaffolds
- ✅ Organize everything in proper structure
- ✅ Provide master index linking all docs

### Reference Documents (`references/`)
Comprehensive guidance on:
- **Documentation standards** - Writing rules, templates, code examples
- **Testing patterns** - Unit, integration, acceptance criteria frameworks
- **Mermaid conventions** - Diagram styles and patterns
- **Repository structure** - Folder organization and naming
- **Iteration workflow** - How to update specs as design evolves

### Automation Scripts (`scripts/`)
- **validate-documentation.py** - Check generated docs for completeness
- **generate-folder-structure.py** - Create recommended folder structure

### Documentation (`docs/`)
- Complete guides on how to use the system
- Examples and patterns
- Executive summaries and detailed breakdowns

## Key Features

### 1. **Complete Workflow**
Takes a design description and generates:
- Architecture diagrams (Mermaid)
- Functional specifications
- Implementation specifications
- Testing specifications (integrated)
- Code scaffolds
- Organized folder structure
- Master index linking everything

### 2. **Testing-First Design**
Testing specifications are integrated into implementation specs, ensuring:
- Tests are planned before coding starts
- Acceptance criteria are clear and testable
- Edge cases are documented
- Performance SLAs are defined

### 3. **Comprehensive Documentation**
Every component includes:
- Purpose and scope
- Interfaces and dependencies
- Technical design
- Testing requirements
- Performance targets
- Known edge cases
- Integration points

### 4. **Text-Based Diagrams**
All diagrams use Mermaid format:
- Version controllable (Git friendly)
- Easy for Claude to generate
- Renderable in markdown viewers
- Professional quality

### 5. **Systematic Updates**
Built-in workflow for evolving designs:
- Change tracking with dates
- Decision log for rationale
- CHANGELOG for history
- Revision procedures

## How to Use

### For Design → Documentation

1. **Prepare your design** (2-3 paragraphs describing what you're building)
2. **Tell Claude**:
   ```
   I'm designing a new [component/platform].
   
   [Your design description]
   
   Using the Platform Documentation Orchestrator skill 
   (from github.com/AlbertoDBP/Agentic),
   generate complete documentation.
   ```
3. **Claude generates** complete documentation package
4. **You organize** using provided guides
5. **You iterate** as design evolves

### For Updating Specifications

When design changes:
```
The [Component] design has changed: [what changed]

Please update the documentation using the Platform 
Documentation Orchestrator skill. Update:
1. Functional specs
2. Implementation specs  
3. Test matrix
4. CHANGELOG and decisions log
```

## Example Use Cases

### 1. New Agent Component
```
Design: "I'm building a Tax-Efficient Portfolio Analyzer agent that..."
Result: Complete specs with testing matrix for all 4 sub-components
```

### 2. Distributed System
```
Design: "I'm designing a multi-agent orchestration system..."
Result: Architecture diagrams, functional specs, integration patterns
```

### 3. Platform Feature
```
Design: "I need to add a covered call recommendation engine..."
Result: Implementation specs with Python scaffolds and test cases
```

## Starting Your First Project

1. **Read** `docs/EXECUTIVE_SUMMARY.md` (5 min)
2. **Review** `SKILL/SKILL.md` (10 min)
3. **Prepare** a component design
4. **Tell Claude** to use the skill
5. **Get** complete documentation
6. **Organize** using provided tools

**Total time: ~60 minutes to production-ready documentation**

## Integration with Claude

### Direct Usage
```
"Use the Platform Documentation Orchestrator skill to generate 
documentation for [design]"
```

### With File References
```
"I'm using the Platform Documentation Orchestrator from 
https://github.com/AlbertoDBP/Agentic

[Your design]

Generate complete documentation following the SKILL workflow."
```

## File Descriptions

### `SKILL/SKILL.md`
The core orchestration guide. This is what Claude reads to understand the workflow.
- Input format specification
- Output organization
- 7-step workflow
- Diagram conventions
- Master index structure

### Reference Documents
**documentation-standards.md** - How to write specs
- Templates for functional and implementation specs
- Code documentation patterns
- Validation checklists

**testing-specification-patterns.md** - Testing frameworks
- Unit test requirements patterns
- Integration test scenarios
- Acceptance criteria formula
- Performance SLA patterns
- Agent-specific testing

**iteration-workflow.md** - Updating specs
- When to update documentation
- Change tracking procedures
- Revision processes
- Preventing specification drift

**mermaid-conventions.md** - Diagrams
- Diagram types and when to use
- Color coding standards
- Naming conventions
- Layout guidelines
- Example patterns

**repository-structure.md** - Organization
- Standard folder hierarchy
- Naming conventions
- Cross-reference patterns
- Master index structure

**google-drive-setup.md** - Collaboration (optional)
- How to organize in Google Drive
- Sharing and collaboration
- GitHub sync strategy

### Scripts

**validate-documentation.py**
```bash
python scripts/validate-documentation.py ./my-project/
```
Checks generated documentation for:
- Required sections
- Proper formatting
- Completeness
- Cross-references

**generate-folder-structure.py**
```bash
python scripts/generate-folder-structure.py ./my-project/
```
Creates recommended folder structure with:
- All required folders
- Placeholder templates
- .gitignore file

## Requirements

- **For using with Claude**: Access to Claude (free or paid)
- **For running scripts**: Python 3.7+
- **For Git**: Git installed locally

## Python Dependencies

For running the scripts:
```bash
pip install --break-system-packages requests google-auth-oauthlib google-api-python-client
```

(If using the Google Drive setup option)

## Documentation Reading Order

1. **Start**: `docs/README.md` (navigation guide)
2. **Quick**: `docs/EXECUTIVE_SUMMARY.md` (5-minute overview)
3. **Learn**: `docs/USAGE_GUIDE.md` (detailed examples)
4. **Deep**: `docs/COMPLETE_DELIVERABLES.md` (comprehensive breakdown)
5. **Detailed**: Reference documents as needed

## Customization

You can customize:
- Folder structure (edit `references/repository-structure.md`)
- Specification templates (edit `references/documentation-standards.md`)
- Diagram styles (edit `references/mermaid-conventions.md`)
- Testing patterns (edit `references/testing-specification-patterns.md`)
- Update workflow (edit `references/iteration-workflow.md`)

## Best Practices

1. **Keep SKILL.md as reference** - Don't modify this unless improving the workflow
2. **Use reference docs as guides** - Customize but keep originals for reference
3. **Version control everything** - Use Git to track all changes
4. **Update decision log** - Document why design decisions were made
5. **Keep CHANGELOG current** - Track all changes with dates

## Contributing

If you improve the skill or find issues:
1. Test the improvements with real projects
2. Document what changed and why
3. Update relevant reference documents
4. Commit with clear messages

## License

This skill and all documentation is provided as-is for platform development purposes.

## Contact & Support

This system was created for sophisticated platform development with Claude.

For questions about:
- **How the skill works**: See `SKILL/SKILL.md`
- **How to use it**: See `docs/USAGE_GUIDE.md`
- **Writing specifications**: See `references/documentation-standards.md`
- **Testing patterns**: See `references/testing-specification-patterns.md`
- **Diagrams**: See `references/mermaid-conventions.md`

## Quick Links

- **Main Skill**: `SKILL/SKILL.md`
- **Getting Started**: `docs/README.md`
- **Executive Summary**: `docs/EXECUTIVE_SUMMARY.md`
- **Usage Guide**: `docs/USAGE_GUIDE.md`
- **Documentation Standards**: `references/documentation-standards.md`
- **Testing Patterns**: `references/testing-specification-patterns.md`

---

**Ready to use?** Start with `docs/README.md` for navigation, or go directly to `SKILL/SKILL.md` to see how Claude will orchestrate your documentation.
