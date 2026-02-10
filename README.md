# Agentic Development Platform

Income-platform skills repository for AI agentic development with Claude.

<<<<<<< Updated upstream
=======
## Quick Start

Tell Claude:
```
"Using the income-platform skill from github.com/AlbertoDBP/Agentic, [describe your task]"
```

Claude reads the master router (`skills/income-platform/SKILL.md`) and activates the correct domain skill(s) automatically.

>>>>>>> Stashed changes
## Repository Structure

```
Agentic/
<<<<<<< Updated upstream
├── skills/                                          # All Claude skills
│   ├── income-platform/                             # ← START HERE (master router)
│   │   ├── SKILL.md
│   │   └── references/
│   │       └── skills-registry.md
│   │
│   ├── platform-documentation-orchestrator/         # Architecture & docs
│   │   ├── SKILL.md
│   │   ├── references/
│   │   ├── scripts/
│   │   └── docs/
│   │
│   ├── covered-call-income-advisor/                 # ETF strategy & portfolio
│   │   └── SKILL.md  (+ references/ when uploaded)
│   │
│   ├── forensic-accounting/                         # Financial due diligence
│   │   └── SKILL.md  (+ references/ when uploaded)
│   │
│   └── saas-compensation-design/                    # Sales comp modeling
│       └── SKILL.md  (+ references/ when uploaded)
│
└── scripts/
    └── restructure-repo.sh                          # This script
```

## Quick Start

Tell Claude:
> "Using the income-platform skill from github.com/AlbertoDBP/Agentic,
>  [describe your task]"

Claude will read the master router and activate the correct domain skill(s).

## Skills Registry

See `skills/income-platform/references/skills-registry.md` for full inventory.

## GitHub

https://github.com/AlbertoDBP/Agentic
=======
├── skills/                                            # All Claude skills
│   │
│   ├── income-platform/                              ← START HERE (master router)
│   │   ├── SKILL.md                                  # Task routing + platform context
│   │   └── references/
│   │       └── skills-registry.md                    # Full skill inventory + status
│   │
│   ├── platform-documentation-orchestrator/          # Architecture & docs skill
│   │   ├── SKILL.md
│   │   ├── references/                               # Standards, patterns, Mermaid
│   │   ├── scripts/                                  # validate + generate scripts
│   │   └── docs/                                     # Usage guides
│   │
│   ├── covered-call-income-advisor/                  # ETF strategy & portfolio skill
│   │   └── SKILL.md  (upload .skill package)
│   │
│   ├── forensic-accounting/                          # Financial due diligence skill
│   │   └── SKILL.md  (upload .skill package)
│   │
│   └── saas-compensation-design/                     # Sales comp modeling skill
│       └── SKILL.md  (upload .skill package)
│
└── scripts/
    └── restructure-repo.sh                           # Repo migration utility
```

## Skills Status

| Skill | Status |
|-------|--------|
| income-platform (master router) | ✅ Active |
| platform-documentation-orchestrator | ✅ Active |
| covered-call-income-advisor | ⚠️ Stub — upload needed |
| forensic-accounting | ⚠️ Stub — upload needed |
| saas-compensation-design | ⚠️ Stub — upload needed |

See [`skills/income-platform/references/skills-registry.md`](skills/income-platform/references/skills-registry.md) for full inventory.

## Skills To Build Next

- `voice-agent-integration` — Twilio + Deepgram + ElevenLabs real-time agent
- `multi-agent-qualifying-platform` — 5-module contact qualifying system

## Local Development

Skills live locally at:
```
/Volumes/CH-DataOne/AlbertoDBP/Agentic/skills/
```

Push to GitHub to make them accessible to Claude via raw URL fetch.
>>>>>>> Stashed changes
