---
name: income-platform
description: Master routing skill for the income-platform agentic project. Routes tasks to the correct domain skill(s) based on task intent. Activate this skill first for any income-platform session to load platform-wide context, then follow routing instructions to co-activate domain skills. Covers covered call ETF strategy, platform architecture, financial due diligence, UI/dashboards, and skill evolution.
---

# Income Platform — Master Router

Entry point for all income-platform sessions. Read this first, then activate the domain skills listed for your task.

## Platform Overview

The income-platform is a multi-layer agentic system for generating consistent income through covered call ETF strategies while preserving principal and optimizing tax efficiency. It consists of:

- **Financial Intelligence Engine** — ETF screening, portfolio construction, tax optimization
- **Platform Architecture Layer** — Documentation, specs, ADRs, code scaffolds
- **UI/Dashboard Layer** — Dashboards, reports, client-facing artifacts
- **Data Integration Layer** — MCP servers, API connections, market data feeds

## Skill Routing Table

| Task | Primary Skill | Co-Activate |
|------|--------------|-------------|
| ETF evaluation & screening | covered-call-income-advisor | forensic-accounting |
| Portfolio construction & rebalancing | covered-call-income-advisor | xlsx |
| Tax optimization analysis | covered-call-income-advisor | docx |
| NAV erosion detection | covered-call-income-advisor | — |
| Architecture design & ADRs | platform-documentation-orchestrator | doc-coauthoring |
| Implementation specs + testing | platform-documentation-orchestrator | — |
| Dashboard / UI build | web-artifacts-builder | frontend-design, theme-factory |
| Data API / MCP integration | mcp-builder | platform-documentation-orchestrator |
| ETF issuer due diligence | forensic-accounting | covered-call-income-advisor |
| Investor reports & decks | pptx | theme-factory |
| Portfolio tracker spreadsheet | xlsx | covered-call-income-advisor |
| Strategy memos & reports | docx | theme-factory |
| Skill refinement or creation | skill-creator | covered-call-income-advisor |
| Voice agent integration | [build: voice-agent-integration] | mcp-builder |
| Multi-agent qualifying platform | [build: multi-agent-qualifying] | mcp-builder |

## Platform-Wide Principles

### Financial Layer
- **Preservation first**: NAV preservation > tax efficiency > yield > risk
- **OTM only**: Covered call strategies must use Out-of-the-Money strikes (10-30% upside capture)
- **Target yield**: 12-18% APY through diversified covered call strategies
- **Tax priority**: Section 1256 (60/40) and ROC distributions preferred over ordinary income

### Architecture Layer
- Testing specifications integrated into implementation specs — tests planned before coding
- All diagrams in Mermaid format (version-controllable)
- CHANGELOG and ADRs maintained via automated scripts
- Google Drive as documentation collaboration layer

### Development Standards
- Skills stored at: `/Volumes/CH-DataOne/AlbertoDBP/Agentic/skills/` (local Mac)
- GitHub repo: `https://github.com/AlbertoDBP/Agentic`
- Every skill has its own subdirectory with SKILL.md at root
- Reference files live in skill's `references/` subdirectory

## Account Structure Context

When doing financial analysis, the platform operates across:
- **IRA/401k accounts**: Prioritize yield; tax treatment deferred
- **Roth accounts**: Prioritize growth-income hybrids; tax-free compounding
- **Taxable accounts**: Prioritize Section 1256 and ROC distributions to minimize tax drag

## Skills Registry

| Skill | Status | Role |
|-------|--------|------|
| income-platform | ✅ Active | Master router (this file) |
| platform-documentation-orchestrator | ✅ Active | Architecture & docs |
| covered-call-income-advisor | ⚠️ Upload needed | Financial intelligence |
| forensic-accounting | ⚠️ Upload needed | Due diligence |
| saas-compensation-design | ⚠️ Upload needed | Comp plan modeling |
| skill-creator | ✅ Ready (examples/) | Skill evolution |
| web-artifacts-builder | ✅ Ready (examples/) | Dashboards & UI |
| mcp-builder | ✅ Ready (examples/) | API integration |
| theme-factory | ✅ Ready (examples/) | Visual branding |
| xlsx / docx / pptx / pdf | ✅ Ready (public/) | Format output |

## Quick Activation Patterns

**Single domain task:**
```
"Using covered-call-income-advisor, evaluate JEPQ for my taxable account"
```

**Multi-domain task:**
```
"Using covered-call-income-advisor AND platform-documentation-orchestrator,
 design the ETF screening module with functional specs"
```

**Full platform context:**
```
"Using the income-platform skill from github.com/AlbertoDBP/Agentic, [task]"
```

## Skills To Build Next

| Skill | Purpose | Priority |
|-------|---------|----------|
| voice-agent-integration | Twilio + Deepgram + ElevenLabs patterns for prospect communication agent | High |
| multi-agent-qualifying-platform | 5-module: contact ID, institutional research, KB analysis, competition positioning, opportunity scoring | High |
