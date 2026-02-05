# Deployment Checklist - ADDENDUM

**Version:** 1.1.0  
**Last Updated:** February 3, 2026  
**Purpose:** DigitalOcean-specific optimizations and Phase 1 clarifications

---

## Table of Contents

1. [Pre-configured Docker Droplet](#pre-configured-docker-droplet)
2. [Storage: Standard SSD vs NVMe](#storage-standard-ssd-vs-nvme)
3. [Managed Redis Setup](#managed-redis-setup)
4. [N8N Status - Phase 1](#n8n-status---phase-1)
5. [Circuit Breaker Monitoring Schedule](#circuit-breaker-monitoring-schedule)
6. [Updated Infrastructure Costs](#updated-infrastructure-costs)

---

## Pre-configured Docker Droplet

### **Use DigitalOcean's Docker Marketplace Image** ✅ RECOMMENDED

Instead of manually installing Docker (as described in main deployment-checklist.md), use DigitalOcean's pre-configured Docker droplet.

### **Benefits**

- ✅ Docker + Docker Compose pre-installed
- ✅ Optimized kernel parameters
- ✅ Security best practices applied
- ✅ Saves 15-20 minutes of setup time
- ✅ Maintained by DigitalOcean

### **How to Create**

**Step 1: Create Droplet (DigitalOcean Console)**

```
1. Click "Create" → "Droplets"
2. Choose Region: New York 3 (nyc3) [or closest to users]
3. Choose an Image:
   → Marketplace tab
   → Search: "Docker"
   → Select: "Docker on Ubuntu 24.04"
4. Choose Size:
   → Basic plan
   → CPU options: Regular (8GB / 4 vCPUs / 160GB SSD)
   → Price: $60/month
5. Choose Storage:
   → Standard SSD (see section below)
6. Choose Authentication:
   → SSH keys (upload your public key)
7. Finalize:
   → Hostname: income-fortress-prod
   → Enable backups: Optional ($12/mo)
   → Create Droplet
```

**Step 2: Verify Docker Installation**

```bash
# SSH to droplet
ssh root@<droplet-ip>

# Verify Docker is installed
docker --version
# Expected: Docker version 24.0.x or higher

# Verify Docker Compose is installed
docker compose version
# Expected: Docker Compose version v2.20.x or higher

# Check Docker is running
docker ps
# Expected: Empty list (no containers yet)
```

### **Changes to Main Deployment Checklist**

**SKIP these steps in deployment-checklist.md:**

```bash
# ❌ SKIP: Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# ❌ SKIP: Install Docker Compose
sudo apt install docker-compose-plugin -y
```

**KEEP everything else as-is:**
- ✅ Create deployer user
- ✅ Configure firewall
- ✅ Clone repository
- ✅ Configure .env
- ✅ All deployment steps

---

## Storage: Standard SSD vs NVMe

### **Recommendation: Use Standard SSD** ✅

**For Phase 1 (15 tenants, 150 symbols), Standard SSD is sufficient.**

### **Performance Comparison**

| Storage Type | IOPS | Throughput | Use Case | Additional Cost |
|-------------|------|------------|----------|-----------------|
| **Standard SSD** | 7,500 | 300 MB/s | Most applications | Base price |
| **NVMe SSD** | 240,000 | 2,000 MB/s | High-performance databases | +$80-120/mo |

### **Your Platform's I/O Profile (Phase 1)**

**Database Writes:**
```
Daily market data sync: 150 symbols × 1 update = 150 writes/day
User transactions: ~500 writes/day (15 tenants)
Background jobs: ~200 writes/day (proposals, DRIP, etc.)
---
Total: ~850 writes/day
Peak: ~50 writes/second (during market close sync)
```

**IOPS Requirement:**
- Peak: ~100-200 IOPS
- Standard SSD provides: 7,500 IOPS
- **Headroom: 37x current needs** ✅

### **When to Upgrade to NVMe**

Consider NVMe when you reach:
- [ ] 100+ tenants (10,000+ transactions/day)
- [ ] Real-time intraday data (1,000+ updates/minute)
- [ ] Database IOPS consistently >3,000
- [ ] Query latency p95 >100ms due to disk I/O

### **How to Monitor I/O Usage**

```bash
# Check disk I/O stats
iostat -x 1

# Look for:
# %util > 80% = disk bottleneck (consider NVMe)
# await > 10ms = high latency (consider NVMe)

# PostgreSQL query performance
docker compose exec api python manage.py dbshell
SELECT * FROM pg_stat_database WHERE datname='income_platform';
# Look for: blks_read (high = disk I/O heavy)
```

### **Migration Path (If Needed Later)**

```bash
# Upgrading to NVMe is easy:
1. Create snapshot of current droplet
2. Create new droplet with NVMe storage
3. Restore snapshot to new droplet
4. Update DNS to point to new droplet IP
5. Delete old droplet

# Downtime: ~30 minutes
# No data loss
```

### **Cost Savings**

**Standard SSD (Phase 1):**
- Droplet: $60/mo
- Total: $60/mo

**NVMe (if chosen):**
- Droplet: $140-180/mo
- Total: $140-180/mo

**Savings with Standard SSD: $80-120/mo** ✅

---

## Managed Redis Setup

### **Redis IS Available on DigitalOcean** ✅

Redis deployment instructions were missing from the main checklist. Here's how to set it up.

### **Option A: Managed Redis (Recommended)** ✅

**Benefits:**
- ✅ Automatic backups
- ✅ High availability (automatic failover)
- ✅ Automatic security updates
- ✅ Monitoring included
- ✅ Scales easily

**Cost:**
- Development: $15/mo (256MB RAM)
- Production: $25/mo (1GB RAM)

**Setup Instructions:**

```bash
# DigitalOcean Console:
1. Click "Create" → "Databases"
2. Choose Database Engine:
   → Redis
3. Choose Plan:
   → Basic (Development): $15/mo, 256MB RAM
   → Recommended for Phase 1 (15 tenants)
4. Choose Datacenter:
   → Same region as droplet (e.g., New York 3)
5. Configure:
   → Database name: income-fortress-redis
   → Enable TLS: Yes (required)
   → Enable eviction: Yes
   → Eviction policy: allkeys-lru
6. Create Database Cluster
```

**Connection Details:**

```bash
# After creation, get connection details from Console:
Host: redis-do-user-XXXXXX-0.db.ondigitalocean.com
Port: 25061
Username: default
Password: [auto-generated]
Connection URL: rediss://default:PASSWORD@HOST:PORT

# TLS is required (note: rediss:// not redis://)
```

**Add to .env:**

```bash
# Update your .env file:
REDIS_URL=rediss://default:YOUR_PASSWORD@redis-do-user-XXXXXX-0.db.ondigitalocean.com:25061?ssl_cert_reqs=required

# SSL is required for managed Redis
REDIS_SSL=true
```

**Verify Connection:**

```bash
# Test Redis connection
docker compose exec api python -c "
from django.core.cache import cache
cache.set('test', 'ok')
print(cache.get('test'))
"

# Expected output: ok
```

### **Option B: Self-hosted Redis in Docker**

**If you want to save $15/mo:**

Add to `docker-compose.yml`:

```yaml
services:
  redis:
    image: redis:7-alpine
    container_name: redis
    restart: unless-stopped
    ports:
      - "127.0.0.1:6379:6379"  # Only localhost
    volumes:
      - redis-data:/data
    command: >
      redis-server
      --appendonly yes
      --requirepass ${REDIS_PASSWORD}
      --maxmemory 512mb
      --maxmemory-policy allkeys-lru
    healthcheck:
      test: ["CMD", "redis-cli", "-a", "${REDIS_PASSWORD}", "ping"]
      interval: 30s
      timeout: 3s
      retries: 3
    networks:
      - income-fortress

volumes:
  redis-data:

networks:
  income-fortress:
    driver: bridge
```

Update `.env`:

```bash
REDIS_URL=redis://:YOUR_PASSWORD@redis:6379/0
REDIS_PASSWORD=your-secure-password-here
REDIS_SSL=false
```

**Self-hosted Pros:**
- ✅ Free (included in droplet resources)
- ✅ Same network (lower latency: <1ms vs ~5ms)
- ✅ Full control

**Self-hosted Cons:**
- ❌ No automatic backups (cache can be rebuilt but annoying)
- ❌ No high availability (single point of failure)
- ❌ You manage updates and security patches
- ❌ No built-in monitoring

### **Recommendation**

**Use Managed Redis ($15/mo)** for:
- ✅ Production deployments
- ✅ High availability requirements
- ✅ Professional monitoring

**Use Self-hosted Redis (free)** for:
- ✅ Development/staging environments
- ✅ Cost-sensitive deployments
- ✅ Single-server architecture acceptable

**Phase 1 Production: Managed Redis** ✅

---

## N8N Status - Phase 1

### **N8N is NOT Required for Phase 1** ⏸️

**Current Status:**
- ⏸️ N8N variables in `.env.example` - **Keep but ignore**
- ⏸️ N8N not installed - **Correct for Phase 1**
- ✅ All workflows use Celery - **Working as designed**

### **Why N8N is Deferred to Phase 2**

**Phase 1 Architecture:**
```
Workflow Orchestration: Celery + Celery Beat
├── Agent 1: Market Data Sync (Celery scheduled task)
├── Agent 3: Income Scoring (Celery task chain)
├── Agent 5: Portfolio Monitor (Celery periodic task)
├── Agent 6: Rebalancing (Celery task)
├── Agent 7: DRIP Execution (Celery task)
└── Agent 9: Tax Loss Harvesting (Celery task)

All workflows: Fully functional with Celery ✅
```

**N8N Would Add Value For (Phase 2+):**
```javascript
// Complex multi-step, multi-service workflows
// Example: User onboarding automation

Trigger: New user signup (webhook)
→ Create user in database
→ Call external KYC API (Plaid, Socure)
→ Wait for KYC approval (async)
→ Send welcome email (SendGrid)
→ Create sample portfolio
→ Trigger first income scoring run
→ Schedule onboarding call (Calendly)
→ Add to CRM (HubSpot)
→ Send Slack notification to ops team

// Visual workflow builder beneficial for:
// - Non-developers to modify workflows
// - Complex conditional logic
// - Multi-service integrations
// - Human-in-the-loop approvals
```

### **What to Do**

**During Phase 1 Deployment:**

1. **Keep N8N variables in `.env`:**
   ```bash
   # N8N (Phase 2 - not currently used)
   N8N_ENCRYPTION_KEY=your-random-key-here
   N8N_WEBHOOK_URL=https://n8n.incomefortress.com
   N8N_BASIC_AUTH_USER=admin
   N8N_BASIC_AUTH_PASSWORD=secure-password
   ```

2. **Do NOT install N8N:**
   - Skip any N8N Docker container setup
   - Skip N8N subdomain configuration
   - Skip N8N monitoring setup

3. **Celery handles all workflows:**
   - No action needed
   - System fully functional

### **When to Add N8N (Phase 2+)**

Consider N8N when you need:
- [ ] Visual workflow builder for non-developers
- [ ] Complex multi-service integrations
- [ ] Human-in-the-loop approval workflows
- [ ] Webhook-based automation
- [ ] Integration with 100+ external services (N8N has pre-built connectors)

### **N8N Installation (Future)**

When ready for N8N (Phase 2):

```yaml
# Add to docker-compose.yml:
services:
  n8n:
    image: n8nio/n8n:latest
    container_name: n8n
    restart: unless-stopped
    ports:
      - "5678:5678"
    environment:
      - N8N_ENCRYPTION_KEY=${N8N_ENCRYPTION_KEY}
      - N8N_BASIC_AUTH_ACTIVE=true
      - N8N_BASIC_AUTH_USER=${N8N_BASIC_AUTH_USER}
      - N8N_BASIC_AUTH_PASSWORD=${N8N_BASIC_AUTH_PASSWORD}
      - WEBHOOK_URL=${N8N_WEBHOOK_URL}
    volumes:
      - n8n-data:/home/node/.n8n
    networks:
      - income-fortress

volumes:
  n8n-data:
```

**No rush - add when you need it.** ✅

---

## Circuit Breaker Monitoring Schedule

### **Optimized Schedule: Market-Aware** ✅

**Original Design (Every 5 minutes):**
- ❌ Wasteful (390 checks/day during market hours)
- ❌ Unnecessary API calls
- ❌ Increased monitoring overhead

**New Schedule (Market-Aware):**
- ✅ At market open (9:30 AM EST)
- ✅ At market close (4:00 PM EST)
- ✅ On exchange availability check (weekdays only)
- **Total: 2-3 checks/day** (vs 390/day)

### **Implementation**

**Celery Beat Schedule Update:**

```python
# income_platform/celerybeat_schedule.py

from celery.schedules import crontab

CELERYBEAT_SCHEDULE = {
    # ... other tasks ...
    
    # Circuit Breaker Monitoring - Market Open
    'circuit-breaker-check-market-open': {
        'task': 'apps.monitoring.tasks.check_circuit_breakers',
        'schedule': crontab(
            hour=9,
            minute=30,
            day_of_week='1-5'  # Monday-Friday only
        ),
        'options': {
            'queue': 'monitoring',
            'priority': 9  # High priority
        }
    },
    
    # Circuit Breaker Monitoring - Market Close
    'circuit-breaker-check-market-close': {
        'task': 'apps.monitoring.tasks.check_circuit_breakers',
        'schedule': crontab(
            hour=16,
            minute=0,
            day_of_week='1-5'  # Monday-Friday only
        ),
        'options': {
            'queue': 'monitoring',
            'priority': 9  # High priority
        }
    },
    
    # Optional: Mid-day check (if desired)
    'circuit-breaker-check-midday': {
        'task': 'apps.monitoring.tasks.check_circuit_breakers',
        'schedule': crontab(
            hour=12,
            minute=0,
            day_of_week='1-5'  # Monday-Friday only
        ),
        'options': {
            'queue': 'monitoring',
            'priority': 5  # Medium priority
        },
        'enabled': False  # Disabled by default, enable if needed
    },
}
```

### **Circuit Breaker Check Task**

```python
# apps/monitoring/tasks.py

import logging
from datetime import datetime
from celery import shared_task
from apps.monitoring.models import CircuitBreakerStatus
from apps.alerts.tasks import send_critical_alert

logger = logging.getLogger(__name__)

@shared_task(name='apps.monitoring.tasks.check_circuit_breakers')
def check_circuit_breakers():
    """
    Check circuit breaker status for critical services.
    Runs at market open and close.
    """
    logger.info("Circuit breaker check started")
    
    checks = {
        'market_data_api': check_market_data_api(),
        'anthropic_api': check_anthropic_api(),
        'database': check_database_connection(),
        'redis': check_redis_connection(),
        'external_apis': check_external_apis(),
    }
    
    # Track results
    all_healthy = all(checks.values())
    timestamp = datetime.utcnow()
    
    # Store status
    CircuitBreakerStatus.objects.create(
        timestamp=timestamp,
        market_data_api_healthy=checks['market_data_api'],
        anthropic_api_healthy=checks['anthropic_api'],
        database_healthy=checks['database'],
        redis_healthy=checks['redis'],
        external_apis_healthy=checks['external_apis'],
        all_healthy=all_healthy
    )
    
    # Alert if unhealthy
    if not all_healthy:
        failed_services = [k for k, v in checks.items() if not v]
        send_critical_alert.delay(
            alert_type='circuit_breaker_open',
            message=f"Circuit breakers OPEN for: {', '.join(failed_services)}",
            severity='EMERGENCY'
        )
        logger.error(f"Circuit breakers OPEN: {failed_services}")
    else:
        logger.info("All circuit breakers CLOSED (healthy)")
    
    return {
        'timestamp': timestamp.isoformat(),
        'all_healthy': all_healthy,
        'checks': checks
    }

def check_market_data_api():
    """Check if Alpha Vantage API is responsive"""
    try:
        # Simple health check (quota-free endpoint)
        # Implementation details...
        return True
    except Exception as e:
        logger.error(f"Market data API check failed: {e}")
        return False

def check_anthropic_api():
    """Check if Anthropic API is responsive"""
    try:
        # Minimal API call to check availability
        # Implementation details...
        return True
    except Exception as e:
        logger.error(f"Anthropic API check failed: {e}")
        return False

# ... other check functions ...
```

### **Monitoring Dashboard Update**

**Prometheus Metrics:**

```python
# Circuit breaker status gauge
circuit_breaker_status = Gauge(
    'circuit_breaker_status',
    'Circuit breaker status (1=closed/healthy, 0=open/unhealthy)',
    ['service']
)

# Update after each check
circuit_breaker_status.labels(service='market_data_api').set(1 if healthy else 0)
circuit_breaker_status.labels(service='anthropic_api').set(1 if healthy else 0)
# ... etc
```

**Grafana Dashboard Panel:**

```json
{
  "title": "Circuit Breaker Status",
  "targets": [
    {
      "expr": "circuit_breaker_status",
      "legendFormat": "{{service}}"
    }
  ],
  "type": "stat",
  "options": {
    "graphMode": "none",
    "colorMode": "background",
    "thresholds": {
      "mode": "absolute",
      "steps": [
        {"value": 0, "color": "red"},    // Unhealthy
        {"value": 1, "color": "green"}   // Healthy
      ]
    }
  }
}
```

### **Alert Rule Update**

```yaml
# prometheus/alerts/circuit-breaker.yml

groups:
  - name: circuit_breaker
    interval: 1m
    rules:
      - alert: CircuitBreakerOpen
        expr: circuit_breaker_status == 0
        for: 1m
        labels:
          severity: emergency
          category: circuit_breaker
        annotations:
          summary: "Circuit breaker OPEN for {{ $labels.service }}"
          description: "{{ $labels.service }} is unhealthy. System may be degraded."
          runbook: "https://docs.incomefortress.com/runbook#circuit-breaker-open"
```

### **Benefits of Market-Aware Schedule**

**Cost Savings:**
```
Old: 390 checks/day × 365 days = 142,350 checks/year
New: 2 checks/day × 252 trading days = 504 checks/year

Reduction: 99.6% fewer checks ✅
```

**Operational Benefits:**
- ✅ Checks when it matters (market hours)
- ✅ No weekend/holiday checks (markets closed)
- ✅ Reduced alert fatigue
- ✅ Lower monitoring overhead
- ✅ Still catches critical issues at key times

**When Checks Run:**
```
Monday-Friday:
- 9:30 AM EST: Market opens (first check)
- 4:00 PM EST: Market closes (second check)

Weekends/Holidays:
- No checks (markets closed, no trading)
```

---

## Updated Infrastructure Costs

### **Phase 1 Cost Breakdown (15 Tenants)**

**DigitalOcean Infrastructure:**

| Service | Plan | Cost/Month |
|---------|------|------------|
| **Droplet** | 8GB RAM, 4 vCPUs, 160GB SSD (Standard) | $60 |
| **Managed PostgreSQL** | Basic, 1GB RAM, 10GB storage | $25 |
| **Managed Redis** | Basic, 256MB RAM | $15 |
| **Domain/DNS** | Included (or $12/year externally) | $1 |
| **Backups** (Optional) | Droplet snapshots | $12 |
| **Bandwidth** | 5TB included (sufficient) | $0 |
| **SSL Certificates** | Let's Encrypt (free) | $0 |
| **Total Infrastructure** | | **$101-113/mo** |

**External Services:**

| Service | Usage | Cost/Month |
|---------|-------|------------|
| **Anthropic API** | ~500K tokens/day (explanations) | $40-80 |
| **Alpha Vantage API** | Premium tier (150 symbols/day) | $50 |
| **Market Data APIs** | Dividend data, fundamentals | $0-50 |
| **Total External APIs** | | **$90-180/mo** |

**Total Monthly Cost:**

```
Infrastructure:        $101-113/mo
External APIs:         $90-180/mo
-----------------------------------
TOTAL:                 $191-293/mo

Per Tenant (15):       $12.73-19.53/mo
```

**Compared to Original Estimate:**

```
Original Estimate:     $149-239/mo
Actual (with changes): $191-293/mo

Difference:            +$42-54/mo (+28-23%)

Reason: Managed Redis added ($15/mo)
        More realistic API costs (+$27-39/mo)
```

**Still Profitable:**

```
Revenue (15 tenants @ $25/mo):     $375/mo
Costs:                             $191-293/mo
-----------------------------------
Gross Margin:                      $82-184/mo (22-49%)
```

### **Cost Optimization Options**

**If you need to reduce costs:**

1. **Use Self-hosted Redis:** Save $15/mo
   - Trade-off: No HA, manual backups

2. **Start with Free-tier APIs:** Save $40-50/mo
   - Alpha Vantage free tier (5 calls/min)
   - yfinance for most data
   - Trade-off: Rate limits, less reliable

3. **Smaller Droplet Initially:** Save $20/mo
   - 4GB RAM droplet: $40/mo (vs $60/mo)
   - Trade-off: Less headroom, may need upgrade

4. **Reduce Anthropic API Usage:** Save $20-40/mo
   - Use Claude only for complex explanations
   - Cache explanations aggressively
   - Trade-off: Less AI-powered features

**Recommended: Keep current configuration** ✅
- Managed services worth the cost
- Professional infrastructure
- Scales cleanly

---

## Quick Reference: What Changed

### **Use These Instead of Main Checklist:**

| Step | Main Checklist | This Addendum |
|------|----------------|---------------|
| **Droplet Creation** | Manual Ubuntu, install Docker | Use Docker Marketplace image |
| **Storage Type** | Not specified | Standard SSD (not NVMe) |
| **Redis Setup** | Missing instructions | Managed Redis ($15/mo) |
| **N8N Installation** | `.env` variables present | Skip installation (Phase 2) |
| **Circuit Breaker** | Every 5 minutes | 2x/day (market open/close) |
| **Total Cost** | $149-239/mo | $191-293/mo |

### **Deployment Checklist Updates**

**Step 1.1: Create Droplet**
- ✅ Use Docker Marketplace image
- ✅ Choose Standard SSD
- ❌ Skip manual Docker installation

**Step 1.3: Create Redis**
- ✅ Create Managed Redis cluster
- ✅ Copy connection string to `.env`

**Step 2.4: Configure N8N**
- ⏸️ Keep `.env` variables
- ❌ Skip N8N installation
- ✅ All workflows use Celery

**Step 3.5: Configure Monitoring**
- ✅ Set circuit breaker schedule to 2x/day
- ✅ Market-aware (weekdays only)

---

## Validation Checklist

After deployment, verify these addendum-specific items:

**Docker Pre-configuration:**
- [ ] `docker --version` shows v24.0+
- [ ] `docker compose version` shows v2.20+
- [ ] No manual Docker installation needed

**Storage Performance:**
- [ ] `iostat -x 1` shows %util <50%
- [ ] Database queries p95 <100ms
- [ ] Standard SSD sufficient

**Managed Redis:**
- [ ] Redis connection successful (TLS)
- [ ] Cache operations working
- [ ] High availability confirmed

**N8N Status:**
- [ ] N8N not installed (correct)
- [ ] Celery handling all workflows
- [ ] No N8N errors in logs

**Circuit Breaker Schedule:**
- [ ] Checks run at 9:30 AM EST
- [ ] Checks run at 4:00 PM EST
- [ ] No checks on weekends
- [ ] Alerts working for failures

---

## Support

**Questions about this addendum?**
- Refer to main deployment-checklist.md for detailed procedures
- This addendum provides DigitalOcean-specific optimizations
- Both documents should be used together

**Deployment Issues?**
- Check operational-runbook.md for troubleshooting
- See disaster-recovery.md for recovery procedures

---

**Addendum Version:** 1.1.0  
**Main Checklist Version:** 1.0.0  
**Last Updated:** February 3, 2026  
**Next Review:** After Phase 1 deployment completion
