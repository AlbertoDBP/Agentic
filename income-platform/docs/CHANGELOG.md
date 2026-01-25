# Changelog

All notable changes to the Tax-Efficient Income Investment Platform documentation will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Documentation update automation scripts
  - `update-documentation.sh` - Main orchestrator for doc updates
  - `validate-documentation.py` - Validation and consistency checks
  - Functional specification template

### Changed
- Enhanced workflow for design changes and development completion

---

## [1.0.0] - 2026-01-23

### Added
- Initial documentation package
- Reference architecture with hybrid orchestration (n8n + Prefect)
- Complete data model with 20+ tables (Mermaid ER diagram)
- System architecture diagram
- Functional specification for Agent 3 (Income Scoring)
- Security architecture with RLS policies
- Deployment architecture (Docker, Fly.io, Vercel)
- Master documentation index (docs/index.md)
- Professional README with quick start

### Documentation Structure
- `docs/architecture/` - System design and architecture
- `docs/functional/` - Component functional specifications
- `docs/implementation/` - Detailed implementation guides
- `docs/security/` - Security and compliance
- `docs/deployment/` - Deployment and infrastructure
- `docs/testing/` - Test matrices and strategies
- `docs/diagrams/` - Mermaid diagrams

### Technology Stack
- **Frontend**: Next.js 15, React 18, TypeScript, Tailwind CSS
- **Backend**: Python 3.11, FastAPI, XGBoost, scikit-learn
- **Orchestration**: n8n (integrations), Prefect (core workflows)
- **Data**: Supabase (Postgres 15 + pgvector + RLS)
- **Deployment**: Docker, Fly.io, Vercel, GitHub Actions

### Key Features Documented
- 11 AI Agents (3 ML-powered with XGBoost/GLM)
- Hybrid orchestration strategy
- Multi-tenant security with RLS
- Tax optimization across account types
- NAV erosion monitoring for covered call ETFs
- Income scoring with 50+ features
- Smart alert classification with user feedback loop

---

## Version History

### Versioning Scheme
- **Major (X.0.0)**: Breaking changes to documentation structure
- **Minor (0.X.0)**: New component specifications, significant additions
- **Patch (0.0.X)**: Updates to existing specs, fixes, clarifications

### Change Categories
- **Added**: New documentation, specifications, or features
- **Changed**: Updates to existing documentation
- **Deprecated**: Documentation marked for removal
- **Removed**: Documentation removed
- **Fixed**: Corrections to errors or broken links
- **Security**: Security-related documentation updates

---

## How to Update This Changelog

When making documentation changes:

1. **During Development**:
   ```bash
   # Use the automation script
   ./scripts/update-documentation.sh --design-change agent-03-income-scoring
   # Or manually edit this file
   ```

2. **Add Entry Under [Unreleased]**:
   - Place under appropriate category (Added, Changed, etc.)
   - Use format: `- **Component**: Description`
   - Include issue/PR references if applicable

3. **On Release**:
   - Move [Unreleased] entries to new version section
   - Update version number following semver
   - Add release date

### Example Entries

```markdown
### Added
- **Agent 4 (Entry Price)**: Functional and implementation specifications
- **Testing**: Comprehensive test matrix for ML agents

### Changed  
- **Agent 3 (Income Scoring)**: Updated feature list from 45 to 50+ features
- **Architecture**: Switched from single orchestrator to hybrid n8n + Prefect

### Fixed
- **Documentation**: Corrected broken links in index.md
- **Diagrams**: Fixed entity relationships in data model
```

---

## Links

- [Documentation Index](docs/index.md)
- [Contributing Guide](CONTRIBUTING.md)
- [GitHub Repository](https://github.com/AlbertoDBP/Agentic)
