# Platform Documentation Orchestrator - Skill Summary

## What You've Created

A comprehensive **Claude skill** that instructs Claude to orchestrate the complete documentation generation workflow for AI agentic platforms. This skill transforms a design input into a fully organized, linked set of specifications, diagrams, code scaffolds, and documentation structure.

## Skill Contents

### Core File: SKILL.md
The main orchestration guide that tells Claude:
- What input to expect (design specifications)
- What output to produce (complete documentation set)
- How to structure the repository
- What each document type should contain
- Integration with Google Drive and Mermaid diagrams

### Reference Documents (in `references/` folder)

1. **repository-structure.md** (4.2 KB)
   - Detailed folder organization patterns
   - Naming conventions for files and folders
   - Cross-reference patterns
   - Master Index structure
   - Stability markers for specs

2. **google-drive-setup.md** (5.1 KB)
   - Manual folder setup instructions
   - Automated Python script for Google Drive API
   - Sharing and collaboration workflow
   - Best practices for Drive organization
   - Cross-platform sync strategy (Drive + GitHub)

3. **documentation-standards.md** (6.8 KB)
   - Writing principles and formatting
   - Complete specification templates
   - Code examples in Python, JavaScript
   - Mermaid diagram conventions
   - Validation checklist

4. **testing-specification-patterns.md** (7.2 KB)
   - Unit testing patterns
   - Integration testing scenarios
   - Acceptance criteria formula
   - Edge case documentation format
   - Performance & Reliability SLA patterns
   - Agent-specific testing patterns

5. **iteration-workflow.md** (6.5 KB)
   - When and how to update documentation
   - Change tracking and versioning
   - Revision process with approval workflow
   - Preventing specification drift
   - Common iteration scenarios

6. **mermaid-conventions.md** (5.9 KB)
   - Diagram types and when to use them
   - Color coding standards
   - Naming conventions
   - Layout guidelines
   - Reusable patterns (error handling, retry logic, etc.)

### Scripts (in `scripts/` folder)

1. **validate-documentation.py** (5.1 KB)
   - Validates generated documentation structure
   - Checks for required sections in specs
   - Verifies Mermaid diagram syntax
   - Reports errors and warnings

2. **generate-folder-structure.py** (7.3 KB)
   - Creates recommended folder structure locally
   - Generates placeholder files
   - Interactive CLI interface
   - Creates .gitignore and other dotfiles

## How This Skill Works

### When Claude Sees a Design Request

You provide Claude with a design input like:

```
# Covered Call Income Analyzer Component

## Overview
New component for analyzing portfolio holdings and recommending 
covered call strategies optimized for tax efficiency.

## Key Features
- Evaluate existing holdings
- Calculate ROC vs. ordinary income implications
- Recommend strike prices and expiration dates
- Generate tax projection reports

INSTRUCT CLAUDE: Execute full documentation workflow
```

### Claude Then Automatically:

1. **Analyzes** the design and extracts key components, interfaces, dependencies
2. **Creates** reference architecture diagram (Mermaid) showing system context
3. **Generates** functional specification with purpose, responsibilities, success criteria
4. **Generates** implementation specification with technical design, API details, testing section
5. **Produces** code scaffolds (skeleton implementations)
6. **Creates** comprehensive testing matrix with unit, integration, acceptance criteria
7. **Organizes** everything into proper folder structure
8. **Generates** Google Drive setup instructions
9. **Creates** master index linking all documentation

### Output Includes:

✅ Reference architecture with Mermaid diagram
✅ Functional specifications (one per component)
✅ Implementation specifications with integrated testing specs
✅ Code scaffolds in your target language
✅ Test matrix and edge case documentation
✅ Complete folder structure plan
✅ Google Drive organization instructions
✅ Master index linking everything
✅ CHANGELOG template
✅ Decisions Log template

## Key Features of This Skill

### 1. **Complete Workflow**
Goes from vague design idea to production-ready documentation structure in one orchestration.

### 2. **Testing-First Design**
Testing specifications are integrated into implementation specs, not separated. Ensures testing is planned before coding starts.

### 3. **Google Drive Native**
Generated documentation is formatted for easy upload to Google Drive while maintaining version control in GitHub.

### 4. **Mermaid Diagrams**
All diagrams are text-based (Mermaid format), making them:
- Version controllable in Git
- Easy for Claude to generate
- Updatable without special tools
- Renderable in markdown viewers

### 5. **Traceability**
Every document links to related specs:
- Implementation spec links to functional spec
- Tests link to acceptance criteria
- Diagrams link to written specs
- All cross-referenced in master index

### 6. **Iteration Ready**
Built-in workflow for updating documentation as design evolves:
- Change tracking with dates
- Decision log for rationale
- Changelog for history
- Revision patterns documented

### 7. **Standards-Based**
Includes comprehensive documentation standards:
- Style guide and formatting rules
- Specification templates
- Code documentation patterns
- Validation checklists

## How to Use This Skill with Claude

### Quick Start Pattern

**Step 1: Provide Design**
```
# New Component Design

## Overview
[Your design description]

## Components
[List major components]

## Integration Points
[How it connects]

## Technology Stack
[Languages, frameworks]

INSTRUCT CLAUDE: Use the Platform Documentation Orchestrator skill 
to generate complete documentation.
```

**Step 2: Claude Generates Everything**
Claude produces:
- All specification documents
- Mermaid diagrams
- Code scaffolds
- Folder structure plan
- Google Drive setup guide

**Step 3: You Organize**
- Create folder structure locally or in Google Drive
- Review generated documentation
- Request iterations/refinements
- Upload to Drive for team review

**Step 4: Keep Updated**
- Use iteration workflow to track changes
- Keep specs in sync with implementation
- Use validation script to check quality

### For Revisions

```
INSTRUCT CLAUDE: The [Component] design has changed: [describe change]

Please update:
1. Affected specifications
2. Diagrams
3. CHANGELOG entry
4. Decisions log entry
5. Master index

Provide only changed documents plus updated index.
```

## Example Workflow for Your Use Case

Given your work with covered call ETFs and SaaS platforms, here's how you'd use this:

**1. Design a Tax-Efficient Portfolio Analyzer**
```
# Design Input

## Purpose
Analyze portfolio holdings and recommend covered call strategies 
optimized for Section 1256 treatment and NAV preservation.

## Components
- Holdings Evaluator
- Tax Optimizer
- Strategy Recommender
- Report Generator

INSTRUCT: Generate documentation
```

**2. Claude Produces**
- Functional specs for each component
- Implementation specs with tax-specific testing
- Diagrams showing data flow
- Code scaffolds in Python
- Test matrix covering:
  - Normal cases (standard holdings)
  - Edge cases (mixed SEC positions, margin calls)
  - Failure modes (broker API down, market volatility)

**3. You Can Then**
- Review specs with colleagues in Google Drive
- Start implementation against clear specs
- Use validation script to ensure quality
- Iterate on specs as you learn during implementation
- Keep CHANGELOG and decisions log current

## What Makes This Different

### Traditional Approach:
Design → Code → Documentation → Testing (too late)

### This Skill:
Design → Spec + Tests + Code Structure → Implementation (everything aligned from start)

### Key Differences:

| Aspect | Traditional | This Skill |
|--------|-------------|-----------|
| Testing | Afterthought | Built into specs |
| Architecture | In code | In diagrams + docs |
| Traceability | Unclear | Fully linked |
| Changes | Ad hoc | Systematic workflow |
| Knowledge | Individual | Documented standards |
| Setup time | Manual | Automated |

## Files Included in Skill

```
platform-documentation-orchestrator/
├── SKILL.md (main orchestration guide)
├── references/
│   ├── repository-structure.md
│   ├── google-drive-setup.md
│   ├── documentation-standards.md
│   ├── testing-specification-patterns.md
│   ├── iteration-workflow.md
│   └── mermaid-conventions.md
└── scripts/
    ├── validate-documentation.py
    └── generate-folder-structure.py
```

**Total**: ~45 KB of comprehensive guidance and tooling

## Next Steps

### 1. Enable the Skill
When using Claude, the skill will be available to use. You can trigger it with requests like:
- "Using the Platform Documentation Orchestrator skill..."
- "Generate documentation for this design..."
- "Create complete specs for this component..."

### 2. Customize (Optional)
You can modify the skill to:
- Add company-specific standards
- Adjust folder structure for your team
- Add specific SLA targets
- Include proprietary patterns

### 3. Start Using It
Begin with a simple component design and iterate based on:
- How well specs match implementation
- Whether developers find them useful
- Which documentation types matter most
- What gets out of date fastest

### 4. Refine Over Time
After a few projects:
- You'll discover what works for your team
- You can feedback improvements to the skill
- You'll build institutional knowledge
- Documentation will become second nature

## Integration Points

### With Google Drive
- Directly upload generated docs
- Share with team for collaboration
- Use Drive's comment feature for review
- Archive old versions

### With GitHub
- Store canonical versions in Git
- Version control all specifications
- Use Git history to track evolution
- Link from Drive to GitHub files

### With Your Development Tools
- Reference specs in code reviews
- Link tickets to relevant specs
- Use validation script in CI/CD
- Automate folder structure creation

## Support & Customization

### What's Included:
- Complete documentation workflow
- Specification templates
- Testing frameworks
- Google Drive integration guide
- Validation tools
- Iteration workflow
- Style standards

### What You Can Add:
- Company-specific standards
- Industry-specific patterns
- Custom SLA targets
- Proprietary methodology
- Team-specific workflows

## Questions to Ask Claude When Using the Skill

**For initial generation:**
- "Generate complete documentation for [design]"
- "Create specs and code scaffolds"
- "Give me the folder structure plan"

**For iterations:**
- "Update documentation - [component] changed [how]"
- "The [component] spec needs [modification]"
- "Add edge case [scenario] to test matrix"

**For quality:**
- "Validate this documentation against the standards"
- "Does this spec have all required sections?"
- "Are the acceptance criteria testable?"

## Success Metrics

After implementing with this skill, you should see:

✅ Developers say specs are clear and implementable
✅ Fewer "what did you mean?" questions during development
✅ Fewer bugs from misunderstood requirements
✅ Easier onboarding of new team members
✅ Easier to maintain documentation as code evolves
✅ Clear decision history for why things are the way they are
✅ Faster iterations on design with clear change tracking
✅ Testing planned alongside development, not after

## Final Thoughts

This skill encodes best practices for documentation in agentic platforms. It ensures:
- **Completeness**: Nothing is forgotten
- **Consistency**: Everything follows standards
- **Traceability**: Everything is linked
- **Updatability**: Changes are systematic
- **Collaboration**: Team can review and discuss

The more you use it, the more it becomes automatic documentation practice rather than extra work.

---

Created for: **Alberto** - AI Solutions Architect with deep expertise in platform development, covered call investing, and financial systems.

Built with principles of completeness, clarity, and practical applicability that match your sophisticated approach to design and development.
