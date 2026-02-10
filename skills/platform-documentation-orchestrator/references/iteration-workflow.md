# Iteration Workflow for Design Updates

## When to Update Documentation

Update documentation when:
- **Design changes** - Architectural decisions modified
- **New components added** - Extending the platform
- **Interfaces change** - API contracts updated
- **Requirements clarified** - Better understanding of needs
- **Edge cases discovered** - During implementation or testing
- **Performance targets updated** - SLAs changed based on learnings

## Update Process

### Step 1: Identify What Changed

Before updating documentation, be clear about what changed:

```
Component: [Name]
What changed: [Describe change]
Why: [Reason for change - performance issue, new requirement, discovered edge case, etc.]
Impact: [What downstream components are affected?]
Risk: [Low / Medium / High]
```

### Step 2: Update Affected Specifications

**For functional specs:**
- Update interfaces if changed
- Update success criteria if redefined
- Update dependencies if added/removed
- Add change note with date and reason

**For implementation specs:**
- Update technical design section
- Update API details if interfaces changed
- Add/update edge cases if discovered
- Update testing requirements
- Update SLAs if targets changed

**For diagrams:**
- Update system architecture if topology changed
- Update component interactions if workflows changed
- Update data model if schema changed

### Step 3: Update Supporting Documents

**CHANGELOG.md** - Add entry:
```markdown
## [2025-01-23]

### Changed
- **[Component Name]**: Updated interface to support [change reason]
  - See [Implementation Spec](docs/implementation/component-name-impl.md)
  - Impact: Affects downstream [Component X]
  - Risk: Medium

### Added
- New edge case handling for [scenario]

### Why
[Brief explanation of business/technical reason]
```

**Decisions Log** - Add entry:
```markdown
## Decision: [Decision Title] - 2025-01-23

**Status**: Approved | In Review | Proposed

**Context**: [What problem were we solving?]

**Options Considered**:
1. Option A - [pros/cons]
2. Option B - [pros/cons]
3. Option C - Chosen - [why selected]

**Consequences**: [What does this enable/prevent?]

**Related Specs**: 
- [Component Implementation](docs/implementation/component-impl.md)
- [Related Component](docs/implementation/related-impl.md)
```

### Step 4: Review & Approval

For significant changes:
1. Share updated specs with stakeholders
2. Document feedback in decision log
3. Update specs based on feedback
4. Get explicit approval before implementation

### Step 5: Communicate Changes

1. Update master index with dates of changes
2. Highlight changed sections in relevant specs (use bold, date)
3. Notify team of changes (Slack, email, meeting)
4. Link to updated specs in communication

## Types of Changes

### Type A: Small Update (No Workflow Impact)

**Examples**: Fixed typo, added clarification, updated example

**Process**:
1. Update relevant spec
2. Update CHANGELOG
3. Increment minor version only
4. No approval needed

**Example**:
```markdown
## [Component Name] - Implementation Specification

### API Details (Clarified 2025-01-23)
Previously: "accepts JSON payload"
**Updated**: Now accepts JSON or MessagePack format
See [testing spec] for format validation tests.
```

### Type B: Medium Update (Interface or Implementation Change)

**Examples**: Changed method signature, added error handling, new edge case discovered

**Process**:
1. Update functional spec (if interface changed)
2. Update implementation spec with all details
3. Update diagrams if topology changed
4. Update testing spec with new test cases
5. Add decision log entry
6. Update CHANGELOG
7. Request review from tech lead
8. Communicate change to team

**Example Change Flow**:
```
DISCOVERED: During testing, agent can receive conflicting signals

UPDATED:
- Implementation Spec → Added edge case to Known Edge Cases table
- Testing Spec → Added new test scenario "conflicting signals"
- Decisions Log → Documented decision to escalate vs. auto-resolve
- CHANGELOG → "Added escalation logic for conflicting signals"

COMMUNICATED:
- Slack: "Component X now escalates conflicting signals - see updated spec"
- Updated spec links in team wiki
```

### Type C: Large Update (Architecture or Design Change)

**Examples**: New component added, major workflow redesign, technology stack changed

**Process**:
1. Create comprehensive change proposal (1-page summary)
2. Discuss with architecture team
3. Document decision in decisions log
4. Update reference architecture diagram
5. Create/update all affected specs
6. Create new test matrix entries
7. Update repository structure if needed
8. Update CHANGELOG with significant change note
9. Schedule team sync to discuss impact
10. Maintain old version for reference

**Large Change Checklist**:
- [ ] Change proposal reviewed and approved
- [ ] Reference architecture updated
- [ ] All affected functional specs updated
- [ ] All affected implementation specs updated
- [ ] New diagrams created/updated
- [ ] Testing specifications updated
- [ ] Decisions log entry created
- [ ] CHANGELOG entry written
- [ ] Repository structure updated if needed
- [ ] Master index updated
- [ ] Team notified
- [ ] Old versions archived for reference

## Handling Revisions During Development

### When Developer Discovers Issue

1. **Developer documents issue**:
```
Component: [Name]
Issue: [What's wrong with current spec]
Severity: [Critical / High / Medium / Low]
Proposed Fix: [What should change]
```

2. **Update spec** with issue and fix
3. **Note in spec**: "Issue discovered during implementation [date]"
4. **Track in testing spec**: Add to edge cases if applicable
5. **Document in decisions log** if it represents a learning

### Conflict Resolution

If developer disagrees with spec:

1. **Document disagreement** in spec as comment
2. **Create decision log entry**:
   - What spec says
   - What developer found
   - Why they differ
   - Resolution chosen
3. **Update spec** based on decision
4. **Update code** to match updated spec

## Revision Checklist

Before marking a component as "Stable":

- [ ] Functional spec is complete and clear
- [ ] Implementation spec is detailed with all interfaces
- [ ] Testing spec has comprehensive test cases
- [ ] All edge cases documented
- [ ] SLAs defined and realistic
- [ ] Diagrams are current and accurate
- [ ] Code scaffolds match spec
- [ ] Dependencies are all documented
- [ ] Integration points verified
- [ ] Team review completed
- [ ] CHANGELOG updated
- [ ] Decisions log updated
- [ ] Master index current

## Tracking Changes

### Version Numbering (Optional)

If using semantic versioning for documentation:

- **Major (X.0.0)**: Architecture or interface breaking changes
- **Minor (x.Y.0)**: New components, new capabilities, backward compatible
- **Patch (x.y.Z)**: Clarifications, bug fixes, no behavior change

### Change Tracking in Google Drive

If using Google Drive:

1. **Name convention**: `[Component] Implementation - v2.1.0 [2025-01-23].md`
2. **Keep history**: Archive old versions with date
3. **Version history**: Use Drive's version history for detailed diffs
4. **Latest note**: Always note which is "current" version
5. **Link from master index**: Always point to current version

### Change Tracking in GitHub

If using GitHub:

1. **Commit messages**: "docs: Update Component X impl spec - add edge case handling"
2. **PR descriptions**: Link to decision log, explain why
3. **Git history**: Full history of changes with diffs
4. **Tags**: Use tags for major version markers
5. **CHANGELOG.md**: Maintain narrative history for humans

## Common Iteration Scenarios

### Scenario 1: Testing Reveals Bug in Spec

```
Situation: QA finds that component behavior doesn't match spec

Steps:
1. QA documents finding with evidence
2. Development team investigates
3. If spec is wrong:
   a. Update implementation spec
   b. Update test cases
   c. Note "Bug in original spec" in decisions log
   d. Update code to match corrected spec
4. If code is wrong:
   a. Fix code
   b. Add test case to prevent regression
5. Document learning in edge cases section
```

### Scenario 2: Performance Doesn't Meet SLA

```
Situation: Component runs 2x slower than SLA after implementation

Steps:
1. Document performance finding
2. Root cause analysis
3. If SLA is unrealistic:
   a. Discuss and update SLA
   b. Document in decisions log why (hardware limits, algorithm complexity, etc.)
   c. Note change date in implementation spec
4. If optimization possible:
   a. Implement optimization
   b. Update technical design section in spec
   c. Document what was optimized
5. Add performance test case to prevent regression
```

### Scenario 3: New Integration Point Discovered

```
Situation: During development, need to integrate with unexpected system

Steps:
1. Document new integration requirement
2. Update implementation spec with new dependency
3. Update diagrams to show new component
4. Update testing spec with integration test
5. Create decisions log entry explaining why not caught earlier
6. Add to integration testing requirements
```

### Scenario 4: Design Evolves Based on Learning

```
Situation: After building prototype, team realizes better approach

Steps:
1. Document learning and proposed change
2. Create change proposal
3. Get approval from tech lead/architect
4. Decisions log: "Learning from prototype → updated design"
5. Update all affected specs with marked changes (dates)
6. Update diagrams
7. Communicate to team with summary of why
8. Archive old versions for reference
```

## Preventing Specification Drift

**Specification drift** = Specs become outdated compared to actual implementation

### Prevention Strategies

1. **Update specs before coding** - Not after
2. **Code reviews check specs** - Verify implementation matches
3. **Regular audits** - Monthly check that specs match code
4. **Single source of truth** - No duplicate specs
5. **Link everything** - Diagrams → specs → code → tests
6. **Version together** - When code version changes, update spec version
7. **Automated validation** - See scripts/validate-documentation.py

### Audit Checklist (Monthly)

- [ ] Pull latest code
- [ ] Spot-check 3-5 components
- [ ] Do specs match actual implementation?
- [ ] Are SLAs being met?
- [ ] Were new edge cases discovered and not documented?
- [ ] Have dependencies changed?
- [ ] Update any specs that drift found

## Documentation Maintenance Policy

**Review Cadence**:
- **In Progress**: Every 2 weeks
- **Stable**: Every quarter or when changes needed
- **Deprecated**: Archive after 6 months

**Owner**: Component owner is responsible for keeping spec current

**Review Process**:
1. Owner checks spec vs. actual code
2. Note any discrepancies
3. Update if needed
4. Note review date in spec
5. Report status in team sync

**Escalation**: If spec significantly out of date (>3 months old), flag for team discussion
