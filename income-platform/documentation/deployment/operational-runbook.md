# Operational Runbook - Income Fortress Platform

**Version:** 1.0.0  
**Last Updated:** February 3, 2026  
**Audience:** DevOps, SRE, On-Call Engineers

---

## Table of Contents

1. [Daily Operations](#daily-operations)
2. [Common Tasks](#common-tasks)
3. [Troubleshooting](#troubleshooting)
4. [Emergency Procedures](#emergency-procedures)
5. [Monitoring & Alerts](#monitoring--alerts)
6. [Maintenance Windows](#maintenance-windows)

---

## Daily Operations

### Morning Checklist (9 AM EST)

```bash
# 1. Check all services are running
docker compose ps

# Expected: All services "Up (healthy)"

# 2. Check health endpoint
curl https://api.incomefortress.com/health/detailed

# Expected: {"status": "healthy", "services": {...}}

# 3. Check error rates (last 24 hours)
docker compose logs --since 24h | grep ERROR | wc -l

# Expected: <10 errors

# 4. Check database connections
docker compose exec api python -c "from django.db import connection; print(connection.queries)"

# Expected: Connection successful

# 5. Review Prometheus alerts
curl http://localhost:9090/api/v1/alerts

# Expected: No firing alerts
```

**Checklist:**
- [ ] All 8 containers healthy
- [ ] API responding correctly
- [ ] Error count acceptable (<10/day)
- [ ] Database connections stable
- [ ] No critical alerts firing

### Evening Checklist (6 PM EST)

```bash
# 1. Review daily metrics
curl http://localhost:8000/metrics | grep -E "(api_requests_total|scoring_duration_seconds)"

# 2. Check Celery queue lengths
docker compose exec celery_default celery -A income_platform inspect active_queues

# Expected: Queue lengths <100

# 3. Verify backups completed
ls -lh backups/ | tail -5

# Expected: Today's backup present

# 4. Check disk space
df -h

# Expected: <70% utilization

# 5. Review system logs
journalctl -u docker --since "4 hours ago" | grep -i error
```

**Checklist:**
- [ ] Request volume normal
- [ ] Celery queues not backing up
- [ ] Daily backup completed
- [ ] Disk space sufficient
- [ ] No system-level errors

---

## Common Tasks

### 1. Restarting a Service

**When:** Service is unresponsive or needs configuration reload

```bash
# Restart single service
docker compose restart api

# Restart with rebuild (if code/config changed)
docker compose up -d --no-deps --build api

# Verify service is healthy
docker compose ps api
curl https://api.incomefortress.com/health
```

**Expected Recovery Time:** 30-60 seconds

### 2. Scaling Celery Workers

**When:** Task queue growing, scoring taking too long

```bash
# Check current workers
docker compose exec celery_default celery -A income_platform inspect active

# Scale up workers (edit docker-compose.yml)
# Change: --concurrency=4 to --concurrency=8

# Apply changes
docker compose up -d --no-deps celery_default

# Verify new workers
docker compose logs -f celery_default
```

**Impact:** Increased CPU/memory usage, faster task processing

### 3. Database Backup

**When:** Before major changes, migrations, or on-demand

```bash
# Manual backup
./scripts/backup_database.sh

# Verify backup
ls -lh backups/
# Expected: New .sql file with current timestamp

# Test backup integrity
pg_restore --list backups/$(ls -t backups/ | head -1)
```

**Frequency:** 
- Automated: Daily at 2 AM EST
- Manual: Before migrations, major releases

### 4. Viewing Logs

**Real-time monitoring:**
```bash
# All services
docker compose logs -f

# Specific service
docker compose logs -f api

# Last 100 lines
docker compose logs --tail=100 api

# Filter by error level
docker compose logs api | grep ERROR

# Search for specific term
docker compose logs api | grep "scoring_agent"
```

**Log Locations:**
- Container logs: `docker compose logs`
- System logs: `/var/log/income-platform/`
- Nginx logs: `/var/log/nginx/`

### 5. Clearing Redis Cache

**When:** Stale data suspected, after configuration changes

```bash
# Connect to Redis
docker compose exec redis redis-cli

# Clear all caches
FLUSHALL

# Clear specific pattern
KEYS income:*
DEL income:scores:VYM

# Verify cache cleared
DBSIZE
```

**Impact:** Temporary performance degradation as cache rebuilds

### 6. Running Migrations

**When:** Database schema changes deployed

```bash
# Show pending migrations
docker compose exec api python manage.py showmigrations

# Run migrations
docker compose exec api python manage.py migrate

# Verify migrations applied
docker compose exec api python manage.py showmigrations | grep "\[X\]"
```

**Rollback if needed:**
```bash
# Rollback last migration
docker compose exec api python manage.py migrate <app_name> <previous_migration>
```

### 7. Adding a New Tenant

**When:** New client onboarding

```bash
# 1. Create tenant schema
docker compose exec api python manage.py create_tenant \
  --schema_name=tenant_new \
  --domain=tenant-new.incomefortress.com

# 2. Verify tenant created
docker compose exec api python -c "
from apps.tenants.models import Tenant
print(Tenant.objects.filter(schema_name='tenant_new').exists())
"

# 3. Run migrations for new schema
docker compose exec api python manage.py migrate_schemas --schema=tenant_new

# 4. Create superuser for tenant
docker compose exec api python manage.py tenant_command createsuperuser \
  --schema=tenant_new
```

### 8. Updating Environment Variables

**When:** API keys, secrets, or configuration changes

```bash
# 1. Edit .env file
nano .env

# 2. Verify changes
cat .env | grep <variable_name>

# 3. Restart affected services
docker compose restart api celery_default celery_scoring

# 4. Verify new values loaded
docker compose exec api printenv | grep <variable_name>
```

**Important:** Never commit `.env` to Git!

### 9. Certificate Renewal

**When:** SSL certificate expiring (automated, but manual if needed)

```bash
# Check certificate expiration
sudo certbot certificates

# Manual renewal
sudo certbot renew

# Verify renewal
sudo nginx -t
sudo systemctl reload nginx

# Test SSL grade
# Visit: https://www.ssllabs.com/ssltest/analyze.html?d=api.incomefortress.com
```

**Automated Renewal:** Runs daily via cron at 3 AM EST

---

## Troubleshooting

### Issue 1: API Not Responding (503 Error)

**Symptoms:**
- `curl https://api.incomefortress.com/health` returns 503
- Users cannot access platform
- Nginx shows "bad gateway" errors

**Diagnosis:**
```bash
# 1. Check if API container is running
docker compose ps api

# 2. Check API logs
docker compose logs --tail=100 api

# 3. Check resource usage
docker stats api
```

**Common Causes & Solutions:**

**Cause A: Container crashed**
```bash
# Restart API
docker compose restart api

# Check if it stays up
docker compose ps api
```

**Cause B: Out of memory**
```bash
# Check memory usage
docker stats api

# If >90%, increase memory limit in docker-compose.yml
# Then restart
docker compose up -d --no-deps api
```

**Cause C: Database connection lost**
```bash
# Test DB connection
docker compose exec api python -c "
from django.db import connection
connection.ensure_connection()
print('Connected')
"

# If fails, restart database (if managed by DigitalOcean, check their console)
# Then restart API
docker compose restart api
```

### Issue 2: Celery Tasks Not Processing

**Symptoms:**
- Task queue growing
- Scores not updating
- Background jobs stuck

**Diagnosis:**
```bash
# 1. Check Celery worker status
docker compose exec celery_default celery -A income_platform inspect active

# 2. Check queue lengths
docker compose exec celery_default celery -A income_platform inspect active_queues

# 3. Check worker logs
docker compose logs --tail=100 celery_default celery_scoring
```

**Common Causes & Solutions:**

**Cause A: Workers crashed**
```bash
# Restart workers
docker compose restart celery_default celery_scoring

# Verify they're processing
docker compose logs -f celery_default
```

**Cause B: Tasks blocking workers**
```bash
# Purge queue (WARNING: loses in-flight tasks)
docker compose exec celery_default celery -A income_platform purge

# Restart workers
docker compose restart celery_default celery_scoring
```

**Cause C: Database deadlock**
```bash
# Check for locks
docker compose exec api python manage.py dbshell
SELECT * FROM pg_locks WHERE NOT GRANTED;

# If deadlocks found, restart workers
docker compose restart celery_default celery_scoring
```

### Issue 3: Slow API Response Times

**Symptoms:**
- API latency >1s (normal <500ms)
- Users complaining of slowness
- Timeout errors

**Diagnosis:**
```bash
# 1. Check current latency
time curl https://api.incomefortress.com/health

# 2. Check database query performance
docker compose logs api | grep "slow query"

# 3. Check resource usage
docker stats
```

**Common Causes & Solutions:**

**Cause A: Slow database queries**
```bash
# Enable query logging (temporarily)
# Edit .env: DEBUG=True, DB_LOG_QUERIES=True

# Restart API
docker compose restart api

# Check logs for slow queries
docker compose logs api | grep "SLOW QUERY"

# Disable debug mode after investigation
# Edit .env: DEBUG=False
docker compose restart api
```

**Cause B: High CPU usage**
```bash
# Check CPU usage
docker stats

# If API >80%, scale horizontally (add more API containers)
# Or optimize code/queries

# If database >80%, upgrade database tier (DigitalOcean console)
```

**Cause C: Memory pressure**
```bash
# Check memory
free -h

# If <10% available, restart services to free memory
docker compose restart
```

### Issue 4: Scoring Agent Failures

**Symptoms:**
- Scores not calculating
- Errors in Agent 3 logs
- Missing feature data

**Diagnosis:**
```bash
# 1. Check scoring worker logs
docker compose logs celery_scoring | grep "Agent.*Error"

# 2. Check feature store
docker compose exec api python -c "
from apps.scoring.models import FeatureStore
print(FeatureStore.objects.filter(symbol='VYM').latest('updated_at'))
"

# 3. Check external API status
curl https://api.anthropic.com/v1/messages -H "x-api-key: $ANTHROPIC_API_KEY"
```

**Common Causes & Solutions:**

**Cause A: Missing feature data**
```bash
# Trigger manual feature extraction
docker compose exec api python manage.py extract_features --symbol=VYM

# Verify features stored
docker compose exec api python manage.py dbshell
SELECT COUNT(*) FROM feature_store WHERE symbol='VYM';
```

**Cause B: Anthropic API rate limit**
```bash
# Check rate limit headers in logs
docker compose logs celery_scoring | grep "rate.*limit"

# If rate limited, wait for reset (1 minute)
# Or reduce scoring frequency in celerybeat-schedule.py
```

**Cause C: Model version mismatch**
```bash
# Check current model version
docker compose exec api python -c "
from apps.scoring.income_scorer import IncomeScorerV6
print(IncomeScorerV6.__version__)
"

# If outdated, rebuild container
docker compose build celery_scoring
docker compose up -d --no-deps celery_scoring
```

### Issue 5: Disk Space Full

**Symptoms:**
- Docker commands failing
- Database writes failing
- Logs show "no space left"

**Diagnosis:**
```bash
# Check disk usage
df -h

# Check largest directories
du -sh /* | sort -rh | head -10

# Check Docker volumes
docker system df
```

**Solutions:**

```bash
# 1. Clear old logs
docker compose logs --tail=0 > /dev/null

# 2. Remove old Docker images
docker image prune -a

# 3. Remove old database backups (keep last 7 days)
find backups/ -name "*.sql" -mtime +7 -delete

# 4. Clear systemd journal
sudo journalctl --vacuum-size=500M

# 5. If still full, upgrade droplet storage (DigitalOcean console)
```

### Issue 6: SSL Certificate Expired

**Symptoms:**
- Browser shows "not secure"
- SSL Labs shows certificate expired
- Users cannot access platform

**Diagnosis:**
```bash
# Check certificate expiration
sudo certbot certificates
```

**Solution:**
```bash
# Renew certificate
sudo certbot renew --force-renewal

# Reload Nginx
sudo nginx -t
sudo systemctl reload nginx

# Verify renewal
curl https://api.incomefortress.com
# Should return 200, no SSL warnings
```

---

## Emergency Procedures

### EMERGENCY: Complete System Outage

**Severity:** P0 (Critical)  
**RTO:** 4 hours  
**RPO:** 1 hour

**Immediate Actions (First 15 minutes):**

1. **Assess Scope**
   ```bash
   # Check all services
   docker compose ps
   
   # Check system resources
   free -h
   df -h
   
   # Check network
   ping google.com
   ```

2. **Notify Team**
   - Slack #ops channel: "@here CRITICAL: Full outage"
   - Page on-call engineer
   - Update status page

3. **Attempt Quick Recovery**
   ```bash
   # Try restarting all services
   docker compose restart
   
   # Wait 2 minutes, check health
   curl https://api.incomefortress.com/health
   ```

**If Quick Recovery Fails (15-60 minutes):**

4. **Full System Restart**
   ```bash
   # Stop all services
   docker compose down
   
   # Check for stuck processes
   ps aux | grep docker
   
   # Restart Docker daemon
   sudo systemctl restart docker
   
   # Start services
   docker compose up -d
   
   # Monitor startup
   docker compose logs -f
   ```

5. **Check External Dependencies**
   ```bash
   # Test database connectivity
   psql "$DATABASE_URL" -c "SELECT 1"
   
   # Test Redis connectivity
   redis-cli -u "$REDIS_URL" PING
   
   # Test Anthropic API
   curl https://api.anthropic.com/v1/messages -H "x-api-key: $ANTHROPIC_API_KEY"
   ```

**If System Still Down (60+ minutes):**

6. **Disaster Recovery**
   - See [Disaster Recovery Plan](disaster-recovery.md)
   - Initiate failover to backup environment
   - Restore from last known good backup

### EMERGENCY: Data Corruption Detected

**Severity:** P0 (Critical)  
**RTO:** 2 hours  
**RPO:** 1 hour

**Immediate Actions:**

1. **Stop All Writes**
   ```bash
   # Put API in maintenance mode
   docker compose exec api python manage.py set_maintenance_mode on
   
   # Stop Celery workers
   docker compose stop celery_default celery_scoring
   ```

2. **Assess Corruption**
   ```bash
   # Check database integrity
   docker compose exec api python manage.py dbshell
   VACUUM ANALYZE;
   
   # Check for corrupted tables
   SELECT * FROM pg_stat_database WHERE datname='income_platform';
   ```

3. **Notify Leadership**
   - Escalate to CTO immediately
   - Document corruption scope
   - Prepare communication for users

4. **Restore from Backup**
   - See [Disaster Recovery: Database Restore](disaster-recovery.md#database-restore)
   - Use most recent uncorrupted backup
   - Validate data integrity after restore

### EMERGENCY: Security Breach

**Severity:** P0 (Critical)  
**RTO:** Immediate  
**RPO:** N/A

**Immediate Actions:**

1. **Isolate System**
   ```bash
   # Block all incoming traffic
   sudo ufw deny from any to any port 80
   sudo ufw deny from any to any port 443
   
   # Stop all services
   docker compose down
   ```

2. **Notify Security Team**
   - Email: security@incomefortress.com
   - Slack: @security-team
   - Phone: On-call security officer

3. **Preserve Evidence**
   ```bash
   # Capture logs
   docker compose logs > /tmp/breach-logs-$(date +%Y%m%d).txt
   
   # Capture system state
   docker compose ps > /tmp/breach-state-$(date +%Y%m%d).txt
   
   # Do NOT delete anything
   ```

4. **Rotate All Credentials**
   - Database passwords
   - API keys (Anthropic, market data)
   - SSH keys
   - SSL certificates
   - Application secrets

5. **Incident Response**
   - Follow company incident response plan
   - Document timeline
   - Coordinate with legal/PR teams

### EMERGENCY: Database Failure

**Severity:** P1 (High)  
**RTO:** 1 hour  
**RPO:** 1 hour

**Immediate Actions:**

1. **Verify Database Status**
   ```bash
   # Check managed database console (DigitalOcean)
   # Look for:
   # - Connection errors
   # - Disk full
   # - Memory exhaustion
   ```

2. **Attempt Failover**
   - If using managed DB with standby, initiate failover
   - Update connection string if needed
   - Restart API to pick up new connection

3. **If Failover Fails, Restore from Backup**
   ```bash
   # See Disaster Recovery Plan
   ./scripts/restore_database.sh backups/latest.sql
   ```

---

## Monitoring & Alerts

### Alert Levels

**P0 - Critical (Immediate Response Required)**
- Complete system outage
- Data corruption
- Security breach
- Database failure

**P1 - High (Response within 1 hour)**
- Service degradation (>5% error rate)
- API response time >1s (p95)
- Celery queue backing up (>500 tasks)
- Disk space >90%

**P2 - Medium (Response within 4 hours)**
- Memory usage >80%
- CPU usage >80% for >10 minutes
- Certificate expiring <7 days
- Backup failure

**P3 - Low (Response within 24 hours)**
- Minor configuration issues
- Non-critical warnings
- Informational alerts

### Alert Channels

**P0 Alerts:**
- PagerDuty (immediate page)
- Slack #ops-critical
- SMS to on-call engineer

**P1 Alerts:**
- Slack #ops
- Email to ops team

**P2/P3 Alerts:**
- Slack #ops-notifications
- Email digest (daily)

### Key Prometheus Alerts

See [Monitoring Guide](monitoring-guide.md) for complete alert definitions.

**Critical Alerts:**
1. `APIDown` - API unreachable for 5+ minutes
2. `HighErrorRate` - Error rate >5% for 10+ minutes
3. `DatabaseConnectionFailure` - DB connection pool exhausted
4. `DiskSpaceCritical` - Disk >90% full
5. `CeleryWorkersDown` - All workers offline

---

## Maintenance Windows

### Weekly Maintenance (Sundays 2-4 AM EST)

**Purpose:** Apply updates, optimize database, clear caches

**Procedure:**
```bash
# 1. Enable maintenance mode
docker compose exec api python manage.py set_maintenance_mode on

# 2. Backup database
./scripts/backup_database.sh

# 3. Apply system updates
sudo apt update && sudo apt upgrade -y

# 4. Optimize database
docker compose exec api python manage.py dbshell
VACUUM ANALYZE;
REINDEX DATABASE income_platform;

# 5. Clear old logs
docker compose logs --tail=0 > /dev/null

# 6. Restart services (apply updates)
docker compose restart

# 7. Verify health
curl https://api.incomefortress.com/health

# 8. Disable maintenance mode
docker compose exec api python manage.py set_maintenance_mode off
```

### Monthly Maintenance (First Sunday, 2-6 AM EST)

**Additional Tasks:**
- Full database backup verification (restore test on staging)
- SSL certificate rotation check
- Security patches application
- Dependency updates (Python packages)
- Docker image updates
- Log rotation and archival
- Performance tuning based on last month's metrics

### Quarterly Maintenance (First Sunday of Quarter, 2-8 AM EST)

**Additional Tasks:**
- Disaster recovery drill (full restore test)
- Security audit
- Capacity planning review
- Database schema optimization
- Infrastructure cost review
- Documentation updates

---

## Quick Reference

### Essential Commands

```bash
# Service status
docker compose ps

# Service logs
docker compose logs -f [service]

# Restart service
docker compose restart [service]

# Health check
curl https://api.incomefortress.com/health

# Database backup
./scripts/backup_database.sh

# Database restore
./scripts/restore_database.sh [backup-file]

# Celery status
docker compose exec celery_default celery -A income_platform inspect active

# Clear cache
docker compose exec redis redis-cli FLUSHALL

# Enable maintenance mode
docker compose exec api python manage.py set_maintenance_mode on

# Disable maintenance mode
docker compose exec api python manage.py set_maintenance_mode off
```

### Contact Information

**On-Call Engineer:** See PagerDuty rotation  
**DevOps Lead:** Alberto D. (alberto@incomefortress.com)  
**Database Admin:** TBD  
**Security Team:** security@incomefortress.com  

**Escalation Path:**
1. On-call engineer (immediate)
2. DevOps lead (within 30 minutes)
3. CTO (critical issues only)

---

**Runbook Version:** 1.0.0  
**Last Updated:** February 3, 2026  
**Next Review:** May 1, 2026
