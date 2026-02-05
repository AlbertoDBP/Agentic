# Income Fortress Platform - Documentation

**Version:** 1.0.0  
**Last Updated:** $(date +%Y-%m-%d)

## 📚 Documentation Structure

```
documentation/
├── README.md                          # This file
├── DOCUMENTATION-MANIFEST.md          # Complete file inventory
├── CHANGELOG.md                       # Change history
├── index.md                           # Master index
│
├── deployment/                        # Operational Documentation
│   ├── deployment-checklist.md       # Pre-launch checklist
│   ├── operational-runbook.md        # Day-to-day operations
│   ├── monitoring-guide.md           # Monitoring & alerts
│   ├── disaster-recovery.md          # DR procedures
│   └── README.md                     # Deployment index
│
├── functional/                        # Functional Specifications
│   ├── agent-*.md                    # Individual agent specs
│   ├── feature-store-v2.md           # Feature store design
│   └── income-scorer-v6.md           # Scoring system
│
├── implementation/                    # Technical Specifications
│   └── (To be populated)
│
├── testing/                           # Testing Documentation
│   └── (To be populated)
│
├── diagrams/                          # System Diagrams
│   └── (Mermaid, SVG, PNG files)
│
├── architecture/                      # Architecture Documents
│   └── reference-architecture.md     # System architecture
│
└── archive/                           # Historical Versions
    ├── Documentation-V1.0/           # Old version
    └── files-old/                    # Old files folder

```

## 🚀 Quick Start

1. **New Users**: Start with `QUICKSTART.md`
2. **Deployment**: See `deployment/deployment-checklist.md`
3. **Architecture**: Read `architecture/reference-architecture.md`
4. **Agents**: Browse `functional/agent-*.md`

## 📋 Key Documents

### Getting Started
- [Quick Start Guide](QUICKSTART.md)
- [Integration Guide](INTEGRATION_GUIDE.md)
- [VS Code Setup](../VSCODE_SETUP_GUIDE.md)

### Architecture & Design
- [Design Summary](DESIGN-SUMMARY.md)
- [Reference Architecture](architecture/reference-architecture.md)
- [System Deployment](DEPLOYMENT.md)

### Operations
- [Deployment Checklist](deployment/deployment-checklist.md)
- [Operational Runbook](deployment/operational-runbook.md)
- [Monitoring Guide](deployment/monitoring-guide.md)
- [Disaster Recovery](deployment/disaster-recovery.md)

### Agents & Features
- [Agent 01: Market Data Sync](functional/agent-01-market-data-sync.md)
- [Agent 03: Income Scoring](functional/agent-03-income-scoring.md)
- [Agents 5-6-7-9 Summary](functional/agents-5-6-7-9-summary.md)
- [Feature Store V2](functional/feature-store-v2.md)
- [Income Scorer V6](functional/income-scorer-v6.md)

## 🔄 Updates

See [CHANGELOG.md](CHANGELOG.md) for version history and updates.

## 📝 Contributing

When adding documentation:
1. Place in appropriate subfolder
2. Update this README
3. Update DOCUMENTATION-MANIFEST.md
4. Add entry to CHANGELOG.md

## 🏗️ Migration Notes

This documentation structure was migrated from multiple sources:
- `docs/` - Primary documentation
- `Documentation V1.0/` - Archived version
- `files/` - Old files (archived)
- Root-level scattered files

All historical versions preserved in `archive/`.
