# Income Platform — Skills Registry

Last updated: 2026-02-10

## User Skills (custom — skills/)

| Skill | Status | Directory | Built |
|-------|--------|-----------|-------|
| income-platform | ✅ Active | skills/income-platform/ | 2026-02-10 |
| platform-documentation-orchestrator | ✅ Active | skills/platform-documentation-orchestrator/ | 2026-01-18 |
| covered-call-income-advisor | ⚠️ Stub — upload .skill package | skills/covered-call-income-advisor/ | 2026-01-18 |
| forensic-accounting | ⚠️ Stub — upload .skill package | skills/forensic-accounting/ | 2026-01-06 |
| saas-compensation-design | ⚠️ Stub — upload .skill package | skills/saas-compensation-design/ | TBD |

## Skills To Build (next sprint)

| Skill | Purpose | Priority | Build Via |
|-------|---------|----------|-----------|
| voice-agent-integration | Twilio + Deepgram + ElevenLabs real-time voice agent | High | skill-creator |
| multi-agent-qualifying-platform | 5-module qualifying: contact ID, institutional research, KB analysis, competition positioning, opportunity scoring | High | skill-creator |

## Example Skills (Anthropic-provided — /mnt/skills/examples/)

| Skill | Primary Use Case for Income Platform |
|-------|--------------------------------------|
| skill-creator | Build and iterate all custom skills |
| web-artifacts-builder | Income dashboards, portfolio UIs |
| mcp-builder | Alpaca API, market data feeds, Twilio |
| doc-coauthoring | Collaborative spec and design doc writing |
| theme-factory | Branded reports, client artifacts |
| algorithmic-art | (Optional) Visualization prototypes |

## Public Skills (Anthropic format output — /mnt/skills/public/)

| Skill | Primary Use Case for Income Platform |
|-------|--------------------------------------|
| xlsx | Portfolio trackers, ETF screening models, ACB tracking |
| docx | Strategy memos, due diligence reports, implementation specs |
| pptx | Investor decks, platform architecture presentations |
| pdf | Final client deliverables, regulatory summaries |
| frontend-design | UI quality elevation for dashboards |

## How to Upload a Skill Package

1. Locate the `.skill` file on Mac at `/Volumes/CH-DataOne/AlbertoDBP/Agentic/`
2. Extract contents to the appropriate `skills/<skill-name>/` directory
3. Replace the stub `SKILL.md` with the full package SKILL.md
4. `git add skills/<skill-name>/` and commit
5. Update this registry status to ✅ Active

## How to Build a New Skill

1. Open a Claude session with the `skill-creator` skill active
2. Describe the skill's purpose and key workflows
3. Iterate through draft → test → refine loop
4. Export as `.skill` package
5. Add to `skills/` directory following the structure above
6. Update this registry
