# Platform Documentation Orchestrator - Usage Guide

## How to Use the Skill with Claude

This guide shows you exactly how to interact with Claude to orchestrate documentation generation.

## Basic Usage Pattern

### 1. **Triggering the Skill**

Tell Claude you want to use the Platform Documentation Orchestrator:

```
I'm designing a new component for my agentic platform. 

[Your design description]

Please use the Platform Documentation Orchestrator skill to generate:
1. Complete reference architecture with Mermaid diagrams
2. Functional specifications for each major component
3. Implementation specifications with integrated testing specs
4. Code scaffolds in Python
5. Google Drive folder setup instructions
6. Master index linking everything
```

### 2. **Providing Your Design Input**

Structure your design like this:

```markdown
# [Component/Platform Name] Design Input

## Overview
Brief 2-3 sentence description of what this is and what problem it solves.

## Key Components
- **Component A**: What it does, key responsibilities
- **Component B**: What it does, key responsibilities
- **Component C**: What it does, key responsibilities

## Integration Points
- Upstream dependencies: What feeds into this?
- Downstream consumers: What depends on this?
- External systems: What APIs or services does it call?

## Technology Stack
- Language: Python 3.11+
- Frameworks: FastAPI, Pydantic
- Databases: PostgreSQL
- APIs: REST, WebSocket

## Success Criteria
- Component A processes 1000 requests/second
- Error rate < 0.1%
- Latency P95 < 100ms
- Tax calculations accurate to cent

## Special Constraints or Notes
- Must comply with Section 1256 tax treatment
- Handle concurrent portfolio updates
- Preserve backward compatibility with v1 API
```

### 3. **What Claude Generates**

Claude will produce for each component/design:

**Architecture & Diagrams**
- reference-architecture.md (written overview)
- system-diagram.mmd (component topology)
- component-interactions.mmd (workflow diagram)
- data-model.mmd (data structures)

**Functional Specifications**
- One .md per major component
- Contains: purpose, responsibilities, interfaces, dependencies, success criteria

**Implementation Specifications**
- One .md per implementation component
- Contains: technical design, API details, testing section, edge cases, SLAs

**Code Scaffolds**
- Language-appropriate skeleton files
- Method signatures with docstrings
- Basic structure matching the specification

**Testing Specifications**
- Unit test requirements
- Integration test scenarios
- Acceptance criteria (testable)
- Known edge cases
- Performance SLAs

**Organization**
- Folder structure plan (ready to create)
- Master index document linking everything
- Google Drive setup instructions

## Real-World Examples

### Example 1: Tax-Efficient Portfolio Analyzer

**Your Input:**
```
# Tax-Efficient Portfolio Analyzer

## Overview
New component that analyzes investor holdings and recommends covered call 
strategies optimized for Section 1256 treatment while preserving NAV.

## Key Components
- **Holdings Evaluator**: Analyzes portfolio, calculates ROC distribution impact
- **Tax Optimizer**: Models Section 1256 vs. ordinary income implications
- **Strategy Recommender**: Suggests strike prices and expirations
- **Report Generator**: Creates tax-efficient recommendation reports

## Integration Points
- Upstream: Portfolio data from account management system
- Downstream: Feeds strategy recommendations to order system
- External: Calls broker API for current option chains and pricing

## Technology Stack
- Language: Python 3.11
- Framework: FastAPI
- Database: PostgreSQL for portfolio snapshots
- Integrations: Alpaca API for options chains

## Success Criteria
- Analyzes 1000+ position portfolios in <2 seconds
- Tax projections accurate within $1
- Identifies ROC preservation opportunities automatically
- Provides rationale for each recommendation

## Special Constraints
- Must handle mixed Roth/Traditional accounts
- Preserve cumulative NAV erosion tracking
- Support manual override of recommendations
```

**Claude Would Generate:**
1. Functional specs for each of 4 components
2. Implementation specs with Python code structure
3. Diagrams showing data flow (holdings → evaluation → optimization → recommendation → report)
4. Test matrix covering:
   - Normal case: standard holdings evaluation
   - Edge cases: margin calls, zero-cost collars, REITs
   - Error cases: broker API down, stale pricing
5. Code scaffolds with method signatures for Python classes
6. Google Drive structure recommendation

### Example 2: Agent Router for Multi-Agent Orchestration

**Your Input:**
```
# Agent Router Component

## Overview
Core orchestration component that routes requests to appropriate agents 
based on task type, data available, and system load.

## Key Components
- **Request Classifier**: Determines task type and complexity
- **Agent Selector**: Chooses best agent based on capability and load
- **Load Balancer**: Distributes work across available agents
- **Fallback Manager**: Handles agent failures gracefully

## Technology Stack
- Language: Python
- Frameworks: FastAPI, asyncio
- Message Queue: Redis for pending requests
- Monitoring: Prometheus metrics

## Success Criteria
- Route decisions in <50ms including classification
- Support 10+ concurrent agents
- Graceful degradation under load
- Auto-failover to fallback agent
```

**Claude Would Generate:**
1. Functional specs for agent routing logic
2. Implementation specs with async Python patterns
3. Diagrams showing request → classification → routing flow
4. Testing specs including:
   - Unit tests for classification logic
   - Integration tests for agent selection
   - Load testing scenarios
   - Failure mode tests (agent timeout, agent crash)
5. Code scaffolds for async agent router
6. Performance SLAs (latency, throughput, concurrent capacity)

## Advanced Usage

### Requesting Specific Components Only

If you only want certain types of documentation:

```
Using the Platform Documentation Orchestrator skill, for the [Component] design:

Generate ONLY:
1. Functional specifications (no implementation specs yet)
2. Mermaid architecture diagrams
3. Test matrix outline

[Design input]
```

Claude will scope output accordingly.

### Requesting Diagrams in a Specific Style

```
Using the Platform Documentation Orchestrator skill:

Generate the system architecture diagram with these constraints:
- Show dataflow only, not control flow
- Use sequence diagram format instead of flowchart
- Highlight async operations in red
- Include timing annotations

[Design]
```

### Requesting Code Scaffolds in a Specific Language

```
Using the Platform Documentation Orchestrator skill:

Generate code scaffolds for this design in JavaScript/TypeScript instead of Python.

[Design]
```

### Requesting Integration with Existing System

```
Using the Platform Documentation Orchestrator skill:

This is a new component in an existing platform. 

[Show existing architecture]

[New component design]

Generate documentation showing:
1. Updated reference architecture including both old and new
2. New component specs
3. Integration points with existing components
4. Updated diagrams showing full system
```

## Iterating on Generated Documentation

### When Design Changes

```
The [Component] design has evolved.

**Previous**: [What was specified]
**New**: [What's now needed]
**Why**: [Reason for change]

Please update:
1. Implementation spec for [Component]
2. Diagrams affected by this change
3. Testing spec with new test cases
4. CHANGELOG entry
5. Decisions log entry explaining the change

Don't regenerate unchanged specs, just provide updates.
```

### When You Want to Add Detail

```
The implementation spec for [Component] needs more detail.

Specifically, expand:
1. The "Edge Cases" section - add 5 more scenarios
2. The "Performance SLAs" - add specific metrics
3. The "Integration Test Scenarios" - add 3 more workflows

[Context about what detail is needed]
```

### When You Want to Refine Testing

```
The testing specification for [Component] needs to be more comprehensive.

Please expand the Testing & Acceptance section:
1. Add determinism tests (if this is an agent component)
2. Add failure mode tests for all dependencies
3. Add performance tests under load
4. Make all acceptance criteria measurable and specific

[Details about what testing gaps exist]
```

## Organizing Generated Documentation

### Step-by-Step After Claude Generates

1. **Create Folder Structure**
   - Run: `python scripts/generate-folder-structure.py ./my-platform`
   - Or manually create folders matching the plan Claude provided

2. **Copy/Upload Documents**
   - Copy .md files into appropriate `docs/` subfolders
   - Copy .mmd files into `docs/diagrams/`
   - Copy code scaffolds into `src/[component]/`

3. **Upload to Google Drive**
   - Create folder structure in Drive matching local structure
   - Upload markdown docs as Google Docs (for collaboration)
   - Upload .mmd files as text documents (Mermaid.live for viewing)
   - Or: Keep canonical versions in GitHub, link from Drive

4. **Share with Team**
   - Share the master index document
   - Add team to review specs
   - Use comments for feedback
   - Use decision log for discussion

5. **Validate Documentation**
   - Run: `python scripts/validate-documentation.py ./my-platform`
   - Fix any validation errors
   - Ensure all sections are complete

## Common Requests to Claude

### "Generate Initial Docs"
```
Generate complete documentation for [component design]
following the Platform Documentation Orchestrator workflow.
```

### "Update Specific Component"
```
Component X has changed: [describe change]

Please update only the implementation spec and test matrix,
with a summary of what changed.
```

### "Validate Documentation Quality"
```
Does this specification document have:
- Clear interfaces specified
- Testable acceptance criteria
- All edge cases documented
- Performance SLAs defined

[Paste spec content]
```

### "Generate Code from Spec"
```
Here's the implementation spec for [Component].

Generate Python code scaffolds with:
- Class definitions matching the spec
- Method signatures with full docstrings
- Basic error handling structure
- Placeholder for business logic

[Paste implementation spec]
```

### "Create Testing Code"
```
Here's the testing specification for [Component].

Generate Python pytest code with:
- Unit test functions for each requirement
- Integration test scenarios
- Test fixtures for shared setup
- Comments explaining what each test validates

[Paste testing spec]
```

## Tips for Best Results

### 1. **Be Specific in Your Design Input**
More specific → better output
```
✅ "Component needs to handle 1000 req/s, P95 latency <100ms"
❌ "Component should be fast"
```

### 2. **Include All Context**
Tell Claude about:
- Existing related components
- External systems it integrates with
- Technology constraints
- Performance requirements
- Special considerations (tax compliance, regulatory, etc.)

### 3. **Review Generated Output**
- Check that component names are consistent
- Verify interfaces are what you intended
- Ensure testing specs match your risk tolerance
- Confirm SLAs are realistic

### 4. **Iterate Early**
- Get initial specs quickly
- Review with team
- Request refinements
- Don't wait for perfection

### 5. **Use Master Index**
- Start from master index for navigation
- Keep it current as specs change
- Use it as checklist for completeness

### 6. **Validate Regularly**
- Run validation script after updates
- Check for missing sections
- Ensure cross-references are current
- Verify no specification drift

## Integration with Your Workflow

### With Development
1. Generate specs before coding starts
2. Use acceptance criteria to define "done"
3. Reference specs in code reviews
4. Link tickets to relevant specs

### With Design Reviews
1. Share master index with stakeholders
2. Use diagrams for discussion
3. Document decisions in decision log
4. Update specs based on feedback

### With Testing
1. Use test matrix to plan test cases
2. Reference acceptance criteria
3. Add edge cases discovered during testing
4. Update SLAs based on actual performance

### With Handoffs
1. New team member starts with master index
2. References functional specs for understanding
3. Uses implementation specs for building
4. Follows decision log to understand why

## Troubleshooting

### "Claude isn't generating everything I asked for"
- Break it into smaller requests
- Ask for one type of output at a time (first specs, then code, then diagrams)
- Provide more context in your design input

### "Generated specs are too generic"
- Include more specific details in your design
- Ask Claude to add more detail to specific sections
- Provide examples of what you're trying to accomplish

### "The folder structure doesn't match my needs"
- Customize it! The structure is a recommendation
- Create your own folder layout
- Adapt the script to match your preferences

### "Specs keep getting out of date"
- Use the iteration workflow to update systematically
- Run validation script regularly
- Set a review cadence (monthly for stable components)
- Involve team in keeping specs current

## Getting the Most Value

### Month 1: Getting Started
- Generate docs for first 2-3 components
- Review process and refine workflow
- Set team expectations for using specs
- Establish review and approval process

### Month 2-3: Building Momentum
- Generate docs for most components
- Start seeing benefit in development clarity
- Accumulate decision history
- Build institutional knowledge in specs

### Month 4+: Continuous Evolution
- Specs become natural part of development
- Documentation drift minimal (specs stay current)
- New team members onboard faster
- Design discussions reference specs

## Next Steps

1. **Prepare a design** for your first component
2. **Request documentation** generation from Claude
3. **Review the output** - what works, what could improve
4. **Iterate** based on feedback
5. **Establish process** with your team
6. **Refine** the skill based on experience

---

**Remember**: The skill is a tool to make your life easier. Adapt it to your workflow, not the other way around.
