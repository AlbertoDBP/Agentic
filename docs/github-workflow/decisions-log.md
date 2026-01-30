# Architecture Decision Records (ADRs)

This document tracks all significant architectural decisions for the GitHub Actions Documentation Automation system.

## Format

Each ADR follows this structure:
- **Status**: Proposed | Accepted | Deprecated | Superseded
- **Context**: What is the issue we're seeing?
- **Decision**: What did we decide?
- **Rationale**: Why did we decide this?
- **Consequences**: What are the positive, negative, and neutral outcomes?
- **Alternatives Considered**: What other options did we evaluate?

---

## ADR-001: GitHub Actions over Alternative CI/CD Platforms

**Status:** Accepted  
**Date:** 2026-01-29  
**Deciders:** Alberto, Claude

### Context

Need a CI/CD platform to automate documentation workflows for the Agentic monorepo. Must integrate seamlessly with GitHub repository and support scheduled, manual, and event-driven triggers.

### Decision

Use GitHub Actions as the primary automation platform.

### Rationale

1. **Native Integration**: GitHub Actions is built into GitHub, no external service needed
2. **No Additional Cost**: 2000 free minutes/month sufficient for documentation automation
3. **Familiar Workflow**: Team already uses GitHub for version control
4. **Simple Setup**: YAML-based configuration, no separate infrastructure
5. **Repository Access**: Direct access to repository without authentication complexity
6. **Event System**: Rich event system (push, PR, schedule, dispatch) matches requirements

### Consequences

**Positive:**
- ✅ Zero setup time for infrastructure
- ✅ No additional authentication layers
- ✅ Native GitHub integration (API, webhooks, PR comments)
- ✅ Familiar YAML configuration
- ✅ Free tier meets requirements
- ✅ Built-in secrets management
- ✅ Easy debugging through GitHub UI

**Negative:**
- ❌ Vendor lock-in to GitHub ecosystem
- ❌ Limited to GitHub's runner environments
- ❌ Monthly minutes quota (though unlikely to exceed)
- ❌ Cannot use for non-GitHub repositories

**Neutral:**
- ⚖️ Learning curve for GitHub Actions syntax (minimal)
- ⚖️ Debugging requires GitHub UI access

### Alternatives Considered

1. **Jenkins**
   - **Pros**: Self-hosted, highly customizable, no vendor lock-in
   - **Cons**: Requires infrastructure management, authentication complexity, overkill for simple automation
   - **Rejected**: Too much operational overhead for documentation automation

2. **GitLab CI**
   - **Pros**: Similar to GitHub Actions, good feature set
   - **Cons**: Requires GitLab migration or mirroring, additional service to maintain
   - **Rejected**: No reason to leave GitHub ecosystem

3. **CircleCI**
   - **Pros**: Powerful, good GitHub integration
   - **Cons**: External service, limited free tier, authentication complexity
   - **Rejected**: GitHub Actions native integration superior

4. **Local Cron Jobs**
   - **Pros**: Complete control, no cloud dependency
   - **Cons**: Requires always-on machine, no PR validation, manual setup on each machine
   - **Rejected**: Doesn't meet reliability and PR validation requirements

---

## ADR-002: Repository Dispatch for Claude Code Integration

**Status:** Accepted  
**Date:** 2026-01-29  
**Deciders:** Alberto, Claude

### Context

Need a mechanism for Claude Code (running in VSCode terminal) to trigger GitHub Actions workflows remotely. Traditional push-based triggers don't work well for on-demand execution from development environment.

### Decision

Use GitHub's Repository Dispatch API to enable remote workflow triggering via a bash script.

### Rationale

1. **Event-Driven**: Repository dispatch creates custom events that workflows can listen for
2. **Flexible Payload**: Can pass parameters (project name, force update flag) via client_payload
3. **API-Based**: Works from any environment with GitHub API access
4. **Authenticated**: Uses GitHub Personal Access Token for security
5. **Immediate**: No polling required, instant workflow trigger
6. **Standard GitHub**: Official GitHub feature, well-documented

### Consequences

**Positive:**
- ✅ Works from any environment (local machine, VSCode, CLI)
- ✅ Supports parameterized execution (specific project, force mode)
- ✅ Secure via PAT authentication
- ✅ Instant trigger without polling
- ✅ Clean separation between trigger and execution
- ✅ Easy to script and automate

**Negative:**
- ❌ Requires GitHub Personal Access Token setup
- ❌ Token must be manually rotated for security
- ❌ API rate limits (5000/hour, unlikely to hit)
- ❌ Requires network access to GitHub API

**Neutral:**
- ⚖️ User must manage token as environment variable
- ⚖️ One-time setup per developer

### Alternatives Considered

1. **Workflow Dispatch (Manual Trigger)**
   - **Pros**: Built-in GitHub feature, no API calls needed
   - **Cons**: Requires GitHub UI interaction, cannot be scripted from terminal
   - **Rejected**: Doesn't support command-line automation

2. **Push-Based Triggering (Dummy Commit)**
   - **Pros**: No API token needed
   - **Cons**: Pollutes Git history, awkward workflow, no parameters
   - **Rejected**: Poor developer experience, clutters repository

3. **Webhooks**
   - **Pros**: Real-time event delivery
   - **Cons**: Requires webhook endpoint setup, URL management, complex authentication
   - **Rejected**: Overkill for simple trigger mechanism

4. **Polling (Check for Marker File)**
   - **Pros**: Simple, no API needed
   - **Cons**: Delay between trigger and execution, inefficient, requires commit
   - **Rejected**: Slow, inefficient, poor user experience

---

## ADR-003: Monorepo Multi-Project Support Strategy

**Status:** Accepted  
**Date:** 2026-01-29  
**Deciders:** Alberto, Claude

### Context

The Agentic repository contains multiple projects (income-platform, future projects) in a monorepo structure. Need to efficiently handle documentation updates for multiple projects without running unnecessary updates for unchanged projects.

### Decision

Implement intelligent change detection that identifies modified projects and runs update/validation scripts only for those projects.

### Rationale

1. **Efficiency**: Only process projects with actual changes
2. **Scalability**: Performance doesn't degrade as project count grows
3. **Selective Updates**: Users can target specific projects when needed
4. **Monorepo-Aware**: Understands project boundaries within repository
5. **Git-Based Detection**: Leverage Git diff to identify changes accurately

### Consequences

**Positive:**
- ✅ Fast execution (minutes instead of tens of minutes for large repos)
- ✅ Scales to many projects without performance degradation
- ✅ Reduces GitHub Actions minutes consumption
- ✅ Clear reporting on which projects were processed
- ✅ Supports selective updates via project filter parameter
- ✅ No unnecessary validation of unchanged documentation

**Negative:**
- ❌ More complex workflow logic
- ❌ Git history dependency (requires clean repository state)
- ❌ Potential for missing cross-project dependencies (mitigated by force mode)

**Neutral:**
- ⚖️ Requires consistent project structure (scripts/ directory per project)
- ⚖️ Change detection based on file paths

### Alternatives Considered

1. **Process All Projects Always**
   - **Pros**: Simple, ensures all projects validated
   - **Cons**: Slow, inefficient, wastes GitHub Actions minutes
   - **Rejected**: Doesn't scale, poor performance

2. **Separate Workflow Per Project**
   - **Pros**: Complete isolation, can run in parallel
   - **Cons**: Workflow duplication, harder to maintain, no shared logic
   - **Rejected**: Maintenance burden too high

3. **Manual Project Selection Only**
   - **Pros**: User controls exactly what runs
   - **Cons**: No automatic detection, easy to forget projects
   - **Rejected**: Defeats purpose of automation

4. **Matrix Strategy (Parallel Execution)**
   - **Pros**: Fast parallel processing
   - **Cons**: Consumes more GitHub Actions minutes, complex merging of results
   - **Deferred**: Good future enhancement, but adds complexity for v1

---

## ADR-004: Validation-First Approach for Quality Assurance

**Status:** Accepted  
**Date:** 2026-01-29  
**Deciders:** Alberto, Claude

### Context

Need to ensure documentation quality before committing changes to repository. Without validation, broken links, missing files, or syntax errors could slip into production documentation.

### Decision

Implement comprehensive validation before any Git commit operations. Workflow fails and exits if validation detects errors.

### Rationale

1. **Quality Gate**: Prevents broken documentation from being committed
2. **Early Detection**: Catches errors before they reach users
3. **Comprehensive Checks**: Multiple validation dimensions (files, links, syntax, consistency)
4. **Fail-Fast**: Stops workflow immediately on validation errors
5. **Clear Feedback**: Detailed error messages with line numbers and suggestions

### Consequences

**Positive:**
- ✅ Guaranteed documentation quality
- ✅ Catches errors before commit
- ✅ Prevents broken links and missing files
- ✅ Validates Mermaid diagram syntax
- ✅ Ensures naming consistency
- ✅ Clear error reporting for fixes
- ✅ Can run locally before pushing

**Negative:**
- ❌ Adds ~15 seconds to workflow execution
- ❌ Strict validation may reject intentional edge cases (mitigated by lenient mode)
- ❌ False positives possible (planned files flagged as missing)

**Neutral:**
- ⚖️ Requires maintaining validation script alongside workflow
- ⚖️ May need validation rule exceptions for special cases

### Alternatives Considered

1. **Post-Commit Validation with Rollback**
   - **Pros**: Faster initial feedback, can commit speculatively
   - **Cons**: Messy Git history with rollback commits, confusion for users
   - **Rejected**: Creates Git clutter, poor user experience

2. **Validation as Warning Only**
   - **Pros**: Never blocks workflow, flexible
   - **Cons**: Errors can slip through, defeats purpose of quality gate
   - **Rejected**: Doesn't prevent broken documentation

3. **Manual Validation Only**
   - **Pros**: User controls when to validate
   - **Cons**: Easy to forget, inconsistent quality
   - **Rejected**: Defeats purpose of automation

4. **Lint on Pre-Commit Hook**
   - **Pros**: Catches errors before local commit
   - **Cons**: Requires setup on each machine, can be bypassed, doesn't help with web-based edits
   - **Deferred**: Good complement to CI validation, but not replacement

---

## ADR-005: No External Python Dependencies for Validation

**Status:** Accepted  
**Date:** 2026-01-30  
**Deciders:** Alberto, Claude

### Context

Original workflow included pip caching and dependency installation, but validation script only uses Python standard library. This created unnecessary complexity and workflow failures when requirements.txt was missing.

### Decision

Remove pip caching and dependency installation from workflow. Use only Python standard library in validation script.

### Rationale

1. **Simplicity**: Fewer moving parts, less to maintain
2. **No Dependencies**: Validation works anywhere Python is installed
3. **Faster Execution**: Skip pip install step (~10 seconds saved)
4. **No Version Conflicts**: Standard library is stable across Python versions
5. **Fewer Failure Points**: No dependency resolution failures

### Consequences

**Positive:**
- ✅ Simpler workflow configuration
- ✅ Faster execution (no pip install)
- ✅ Works without requirements.txt
- ✅ No dependency version conflicts
- ✅ Portable validation script
- ✅ Reduced maintenance burden

**Negative:**
- ❌ Cannot use advanced validation libraries (e.g., mistune for Markdown parsing)
- ❌ Limited to standard library capabilities
- ❌ More manual parsing logic required

**Neutral:**
- ⚖️ If future needs require dependencies, can re-add
- ⚖️ Standard library sufficient for current validation needs

### Alternatives Considered

1. **Keep Pip Caching with Optional Requirements**
   - **Pros**: Ready if dependencies needed later
   - **Cons**: Unnecessary complexity for current needs
   - **Rejected**: Premature optimization

2. **Use Docker with Pre-installed Dependencies**
   - **Pros**: Consistent environment, can include any dependencies
   - **Cons**: Slower execution, more complex setup
   - **Rejected**: Overkill for simple validation

3. **Inline Tool Installation (pip install without requirements.txt)**
   - **Pros**: Dependencies installed on-demand
   - **Cons**: Slower, version pinning issues, not needed
   - **Rejected**: No dependencies currently needed

---

## ADR-006: Lenient Validation for Planned Documentation

**Status:** Accepted  
**Date:** 2026-01-30  
**Deciders:** Alberto, Claude

### Context

Validation script was failing when users referenced planned documentation files (files that will be created later). This created friction in the workflow where users had to either create placeholder files or accept validation failures.

### Decision

Implement lenient validation mode that treats references to planned files as acceptable rather than errors, while still catching genuine broken links.

### Rationale

1. **Workflow Flexibility**: Allows referencing files before they exist
2. **Reduces Friction**: Don't force placeholder file creation
3. **Intent Recognition**: Distinguish between planned files and actual errors
4. **Documentation-First**: Support documenting architecture before implementation
5. **Still Validates**: Catches real broken links to files that should exist

### Consequences

**Positive:**
- ✅ Can reference planned files in documentation
- ✅ Supports incremental documentation development
- ✅ Reduces need for empty placeholder files
- ✅ Better developer experience
- ✅ Still catches genuine broken links

**Negative:**
- ❌ Slightly more complex validation logic
- ❌ Could mask legitimate errors if file names misspelled
- ❌ Requires clear documentation of "planned" vs "should exist"

**Neutral:**
- ⚖️ Lenient mode can be disabled with --strict flag
- ⚖️ Trade-off between flexibility and strictness

### Alternatives Considered

1. **Strict Validation Always**
   - **Pros**: Catches all missing files
   - **Cons**: Forces placeholder creation, slows development
   - **Rejected**: Too rigid for documentation-first workflow

2. **Ignore All Missing Files**
   - **Pros**: Maximum flexibility
   - **Cons**: Doesn't catch any broken links
   - **Rejected**: Defeats purpose of validation

3. **Marker Comments for Planned Files**
   - **Pros**: Explicit marking of planned vs broken
   - **Cons**: Requires extra syntax, easy to forget markers
   - **Deferred**: Could add as enhancement

4. **Separate Validation Phases**
   - **Pros**: Can validate incrementally as files are created
   - **Cons**: Complex workflow logic, unclear when to run which phase
   - **Rejected**: Overly complex

---

## ADR-007: Automated Commit with Descriptive Messages

**Status:** Accepted  
**Date:** 2026-01-30  
**Deciders:** Alberto, Claude

### Context

After documentation updates and validation, changes need to be committed to the repository. Need to balance automation (no manual commits) with meaningful commit history.

### Decision

Automatically commit all documentation changes with descriptive commit messages that include file count and optional project context.

### Rationale

1. **Full Automation**: No manual commit step required
2. **Traceability**: Clear commit messages show what changed
3. **Consistent Format**: Standardized message prefix (docs(auto):)
4. **Informative**: Include file count and project name
5. **Git History**: Maintains clean, understandable history

### Consequences

**Positive:**
- ✅ Fully automated workflow (no manual Git operations)
- ✅ Consistent commit message format
- ✅ Clear attribution (github-actions[bot])
- ✅ Informative messages for git log
- ✅ Can filter automated commits with prefix
- ✅ Maintains Git best practices

**Negative:**
- ❌ Less control over commit message content
- ❌ All changes in single commit (can't split logically)
- ❌ Potential for large commits if many files changed

**Neutral:**
- ⚖️ Commit author is github-actions[bot], not human
- ⚖️ Can customize message format via environment variable

### Alternatives Considered

1. **Manual Commit After Workflow**
   - **Pros**: User controls commit message, can split changes
   - **Cons**: Not fully automated, easy to forget, inconsistent messages
   - **Rejected**: Defeats purpose of automation

2. **Per-Project Commits**
   - **Pros**: Logical separation, smaller commits
   - **Cons**: Complex merge logic, potential conflicts, slower
   - **Deferred**: Could add as enhancement

3. **Per-File Commits**
   - **Pros**: Maximum granularity
   - **Cons**: Clutters Git history, very slow, complex
   - **Rejected**: Too many commits, poor performance

4. **No Automatic Commit (Validation Only)**
   - **Pros**: User has complete control
   - **Cons**: Requires manual commit, defeats automation purpose
   - **Rejected**: Incomplete automation

---

## ADR-008: Installation Script over Manual Setup

**Status:** Accepted  
**Date:** 2026-01-30  
**Deciders:** Alberto, Claude

### Context

Deploying the GitHub workflow system requires copying multiple files to specific locations in the repository with correct permissions. Manual setup is error-prone and time-consuming.

### Decision

Provide an automated installation script (`install-workflow.sh`) that handles all deployment steps with validation and clear feedback.

### Rationale

1. **Reduced Errors**: Script ensures files go to correct locations
2. **Time Savings**: One command instead of multiple manual steps
3. **Validation**: Checks repository structure before proceeding
4. **Permissions**: Automatically sets executable permissions
5. **Guidance**: Provides clear next steps after installation
6. **Repeatability**: Same process every time, no forgotten steps

### Consequences

**Positive:**
- ✅ Fast deployment (seconds vs minutes)
- ✅ Fewer installation errors
- ✅ Consistent setup across environments
- ✅ Clear validation before installation
- ✅ Post-install guidance for next steps
- ✅ Can be rerun if issues occur

**Negative:**
- ❌ Another script to maintain
- ❌ Assumes Bash environment (doesn't work on Windows without WSL)
- ❌ Less control for advanced users who want custom setup

**Neutral:**
- ⚖️ Still requires manual GitHub configuration (permissions)
- ⚖️ User must commit installed files

### Alternatives Considered

1. **Manual Step-by-Step Instructions**
   - **Pros**: Complete control, no script dependency
   - **Cons**: Error-prone, time-consuming, inconsistent
   - **Rejected**: Poor user experience

2. **Git Submodule**
   - **Pros**: Updates automatically, no copying
   - **Cons**: Complex setup, harder to customize, overkill
   - **Rejected**: Too complex for simple file deployment

3. **NPM Package or Pip Package**
   - **Pros**: Standard distribution method, version management
   - **Cons**: Requires package manager, setup overhead, not needed
   - **Rejected**: Over-engineered for small file set

4. **Download via curl/wget**
   - **Pros**: No local files needed
   - **Cons**: Requires internet, version control issues, less transparent
   - **Rejected**: Less reliable than local installation

---

## Summary of Key Decisions

1. **ADR-001**: GitHub Actions for CI/CD automation
2. **ADR-002**: Repository Dispatch for remote triggering
3. **ADR-003**: Smart change detection for monorepo efficiency
4. **ADR-004**: Validation-first approach for quality
5. **ADR-005**: No external dependencies for portability
6. **ADR-006**: Lenient validation for documentation flexibility
7. **ADR-007**: Automated commits with descriptive messages
8. **ADR-008**: Installation script for deployment automation

---

**Document Maintenance:**

This log should be updated whenever significant architectural decisions are made. Each ADR should include full context, decision rationale, and consequences to support future decision-making and onboarding.

**Review Schedule:** Quarterly review of ADRs to update status, add consequences discovered through use, and ensure decisions remain valid.
