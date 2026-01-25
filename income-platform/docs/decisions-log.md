# Architecture Decision Records (ADRs)

This document tracks significant architectural and design decisions for the Tax-Efficient Income Investment Platform.

## Format

Each decision record includes:
- **ADR Number**: Sequential identifier
- **Date**: When the decision was made
- **Status**: Proposed, Accepted, Deprecated, Superseded
- **Component**: Which part of the system is affected
- **Context**: The situation and problem
- **Decision**: What was decided
- **Consequences**: Positive, negative, and neutral impacts

---

## ADR-001: Hybrid Orchestration (n8n + Prefect)

**Date**: 2026-01-23  
**Status**: Accepted  
**Component**: Orchestration Layer

### Context

The platform requires workflow orchestration for:
- Daily data synchronization (scheduled jobs)
- Complex ML pipelines (feature engineering, scoring, training)
- Integration workflows (email parsing, webhooks, external APIs)
- User-triggered analysis (portfolio analysis, scenario planning)

Initial options considered:
1. **Single orchestrator** (n8n only or Prefect only)
2. **Hybrid approach** (n8n for integrations, Prefect for core workflows)
3. **Custom orchestration** (build our own)

### Decision

Adopt hybrid orchestration:
- **n8n**: Integration workflows (email → newsletter parsing, webhooks from frontend, simple scheduled tasks)
- **Prefect**: Core ML and data pipelines (daily scoring, batch processing, model training)
- Both call the same **FastAPI agent services** (DRY principle)

### Rationale

**n8n Strengths**:
- Visual workflow editor (non-technical users can modify)
- Built-in nodes for common integrations (Email, HTTP, Supabase)
- Rapid prototyping for new integrations
- Good for simple, linear workflows

**Prefect Strengths**:
- Python-native (natural for ML workflows)
- Excellent caching and retry logic
- Better for complex conditional logic
- Type-safe with Pydantic models
- Superior observability for long-running jobs

**Hybrid Benefits**:
- Use the right tool for each job
- n8n handles "edges of the system" (integrations, triggers)
- Prefect handles "core intelligence" (ML pipelines, complex orchestration)
- Both can evolve independently

### Consequences

**Positive**:
- ✅ Flexibility to use best tool for each workflow type
- ✅ n8n provides visual debugging for integration issues
- ✅ Prefect provides robust ML pipeline management
- ✅ Clear separation of concerns
- ✅ Can swap out either orchestrator without affecting the other

**Negative**:
- ❌ Two systems to deploy and monitor
- ❌ Two sets of credentials and configuration
- ❌ Slight operational complexity increase
- ❌ Team needs to learn both tools

**Neutral**:
- Both orchestrators call the same FastAPI services (consistent interfaces)
- Additional documentation needed to explain when to use which orchestrator
- Development workflow: n8n workflows as JSON exports, Prefect flows as Python code

### Alternatives Considered

**Alternative 1: n8n Only**
- Rejected because: Complex Python ML code awkward in n8n nodes
- Would require: Many custom n8n nodes wrapping Python code

**Alternative 2: Prefect Only**
- Rejected because: Email parsing and webhook handling harder in Python
- Would require: More code for simple integration tasks

**Alternative 3: Temporal**
- Rejected because: Steeper learning curve than Prefect
- Would require: More operational overhead

---

## ADR-002: Supabase for Data Layer (vs Self-Hosted Postgres)

**Date**: 2026-01-23  
**Status**: Accepted  
**Component**: Data Layer

### Context

Platform needs:
- Multi-tenant database with strict data isolation
- Vector search for newsletter semantic search (pgvector)
- User authentication and authorization
- Real-time updates for dashboard
- Easy deployment and scaling

Options:
1. **Supabase Cloud** (managed Postgres + Auth + Realtime + pgvector)
2. **Self-hosted Postgres** with custom auth and realtime
3. **Firebase** (NoSQL alternative)

### Decision

Use **Supabase Cloud** for all data, auth, and realtime needs.

### Rationale

**Supabase Advantages**:
- Built-in Row-Level Security (RLS) enforces multi-tenancy at database level
- pgvector extension for semantic search (newsletter embeddings)
- Supabase Auth handles JWT tokens, session management, MFA
- Supabase Realtime for WebSocket subscriptions (live dashboard updates)
- Generous free tier ($0 up to 500 MB, 50K auth users)
- Auto-scaling to paid tiers as needed
- Automatic backups and point-in-time recovery

**vs Self-Hosted Postgres**:
- Would require: Setting up pg_cron, pgvector, connection pooling, backups, auth
- Would save: ~$25/month on Supabase paid tier
- Trade-off: Engineering time >>> cost savings

### Consequences

**Positive**:
- ✅ Faster development (auth and RLS built-in)
- ✅ Excellent developer experience (Supabase Studio, auto-generated APIs)
- ✅ Production-ready from day 1 (backups, monitoring, scaling)
- ✅ RLS prevents accidental data leaks across tenants
- ✅ Free tier supports early development

**Negative**:
- ❌ Vendor lock-in (migrations to vanilla Postgres require work)
- ❌ Cost increases with scale ($25/month for 8 GB, more for heavy usage)
- ❌ Limited control over Postgres configuration
- ❌ Edge Functions limited vs full serverless platform

**Neutral**:
- Standard Postgres (easy to export and migrate if needed)
- Can always move to self-hosted Postgres + custom auth later
- Most features used (RLS, pgvector, Auth) are portable with effort

---

## ADR-003: XGBoost for Income Scoring (vs Neural Networks)

**Date**: 2026-01-23  
**Status**: Accepted  
**Component**: Agent 3 (Income Scoring)

### Context

Income Scoring agent (Agent 3) needs ML model to predict income quality and sustainability. Requirements:
- High accuracy (AUC ≥0.80 on test set)
- Explainability (users need to understand why a score is given)
- Fast inference (<500ms p95 latency)
- Easy to retrain and version

Model options:
1. **Gradient Boosted Trees** (XGBoost, LightGBM)
2. **Neural Networks** (MLPs, LSTMs)
3. **Linear Models** (Logistic Regression, ElasticNet)

### Decision

Use **XGBoost** for income scoring with SHAP values for explainability.

### Rationale

**XGBoost Strengths**:
- Excellent performance on tabular data (50+ features)
- Built-in feature importance
- SHAP values provide local explanations per prediction
- Fast inference (CPU-only, <50ms per ticker)
- Handles missing data gracefully
- Less prone to overfitting with proper hyperparameters
- Easy to serialize and version (.pkl files)

**vs Neural Networks**:
- NNs typically require more data (we have ~1000 tickers)
- NNs harder to explain (even with attention mechanisms)
- NNs require GPUs for fast training (XGBoost CPU is sufficient)
- NNs more complex to deploy and version

**vs Linear Models**:
- Linear models underfit on complex feature interactions
- XGBoost captures non-linear relationships better
- XGBoost still provides interpretability via SHAP

### Consequences

**Positive**:
- ✅ Transparent AI: SHAP values show exactly which features drove score
- ✅ Fast inference: CPU-only, <100ms per prediction
- ✅ Robust to missing data: Common in financial data
- ✅ Well-established: Widely used in finance (credit scoring, fraud detection)
- ✅ Easy to deploy: Single .pkl file, no GPU needed

**Negative**:
- ❌ Less effective on time-series patterns (use feature engineering instead)
- ❌ Requires careful hyperparameter tuning to avoid overfitting
- ❌ SHAP computation adds latency (optional, cached for popular tickers)

**Neutral**:
- Can experiment with LightGBM or CatBoost later (similar interfaces)
- If dataset grows significantly (10K+ tickers), might revisit neural networks
- Model versioning via S3 + model_registry table

---

## ADR-004: Next.js App Router (vs Pages Router)

**Date**: 2026-01-23  
**Status**: Accepted  
**Component**: Frontend (Web Interface)

### Context

Need to build responsive web interface for portfolio management. Next.js chosen as framework (React + SSR), but two routing approaches:
1. **App Router** (Next.js 13+ with Server Components)
2. **Pages Router** (traditional Next.js routing)

### Decision

Use **Next.js 15 App Router** with Server Components.

### Rationale

**App Router Advantages**:
- Server Components reduce JavaScript bundle size (dashboard loads faster)
- Improved data fetching (async Server Components fetch data directly)
- Better separation: Server Components for data, Client Components for interactivity
- Built-in layouts and templates (easier to share components across pages)
- Progressive enhancement (pages work with JavaScript disabled for core features)
- Future-proof (Pages Router in maintenance mode)

**Data Flow**:
- Server Components fetch from Supabase (no client-side API calls for initial data)
- Client Components use TanStack Query for mutations and real-time updates
- Optimistic UI updates for better UX

### Consequences

**Positive**:
- ✅ Faster initial page loads (less JavaScript to download)
- ✅ Better SEO (server-rendered content)
- ✅ Reduced API calls (Server Components fetch directly)
- ✅ Clearer boundaries (server vs client code)

**Negative**:
- ❌ Learning curve for team (new paradigm vs Pages Router)
- ❌ Some third-party libraries not yet compatible
- ❌ More complex mental model (when to use Server vs Client Components)

**Neutral**:
- Requires "use client" directive for interactive components
- Middleware for auth redirects works the same

---

## ADR-005: yFinance Primary, Alpaca Secondary (Cost Control)

**Date**: 2026-01-23  
**Status**: Accepted  
**Component**: Agent 1 (Market Data Sync)

### Context

Need market data (OHLCV, dividends, fundamentals) for 500+ tickers daily. Options:
1. **Free tier only**: yFinance (free, unlimited)
2. **Paid API primary**: Alpaca ($9/month for delayed data, $99/month for real-time)
3. **Hybrid**: yFinance primary, Alpaca for gaps/real-time needs

### Decision

Use **yFinance as primary** data source, **Alpaca as secondary** for:
- Real-time position tracking (for users with Alpaca accounts)
- Data validation (cross-check yFinance with Alpaca for accuracy)
- Fallback if yFinance rate-limited

### Rationale

**Cost Analysis** (100 users, 500 tickers):
- yFinance: $0/month (free, community-maintained)
- Alpaca free tier: $0/month (delayed data, 200 req/min)
- Alternative (paid APIs): $50-200/month

**yFinance Coverage**:
- Daily OHLCV: ✅ Excellent
- Dividends: ✅ Good (occasionally lags by 1-2 days)
- Fundamentals: ✅ Adequate (P/E, market cap, basic metrics)
- Options data: ✅ Available (for covered call ETF analysis)

**Limitations**:
- Not official API (unofficial library)
- No SLA or support
- Occasional rate limiting (mitigated with throttling)
- Data quality issues (rare, but possible)

### Consequences

**Positive**:
- ✅ Minimal API costs (~$0 vs $50+/month)
- ✅ Can serve 100+ users on free tier
- ✅ yFinance covers 95% of data needs
- ✅ Alpaca as validation/fallback reduces risk

**Negative**:
- ❌ No official support for yFinance (community-maintained)
- ❌ Potential rate limiting (mitigated with 1 req/sec throttle)
- ❌ Data quality not guaranteed (cross-check with Alpaca)

**Neutral**:
- Implement data quality checks (flag missing/stale data)
- Cache aggressively to reduce yFinance load
- If scale requires, upgrade to paid APIs (Polygon, Alpha Vantage)

---

## How to Add New ADRs

When making significant design decisions:

1. **Create New ADR**:
   ```bash
   # Use the automation script
   ./scripts/update-documentation.sh --design-change <component>
   # Select "yes" when prompted for ADR
   
   # Or manually:
   # Copy template from above
   # Increment ADR number
   # Fill in all sections
   ```

2. **Required Sections**:
   - Context: What problem are you solving?
   - Decision: What did you decide?
   - Rationale: Why this decision?
   - Consequences: Positive, negative, neutral impacts
   - Alternatives: What else was considered?

3. **When to Create ADR**:
   - Technology choice (framework, database, library)
   - Architecture pattern (orchestration, auth, deployment)
   - Data model changes (significant schema changes)
   - Security approach (authentication, authorization, encryption)
   - Performance trade-offs (caching strategy, scaling approach)

4. **When NOT to Create ADR**:
   - Minor implementation details
   - Temporary workarounds
   - Preference-based choices (code style, naming)

---

## ADR Status Definitions

- **Proposed**: Under discussion, not yet finalized
- **Accepted**: Decision made and being implemented
- **Deprecated**: Superseded by newer decision
- **Superseded**: Replaced by specific ADR (reference new ADR number)

---

**Last Updated**: 2026-01-23  
**Total ADRs**: 5  
**Active ADRs**: 5
