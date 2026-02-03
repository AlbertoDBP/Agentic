# Disaster Recovery Guide - Income Fortress Platform

**Version:** 1.0.0  
**Last Updated:** February 2, 2026  
**Classification:** CRITICAL - Operations Team Only

---

## Table of Contents

1. [Overview](#overview)
2. [RTO/RPO Targets](#rtorpo-targets)
3. [Backup Strategy](#backup-strategy)
4. [Recovery Procedures](#recovery-procedures)
5. [Failover Scenarios](#failover-scenarios)
6. [Testing & Validation](#testing--validation)

---

## Overview

### Purpose

This document provides procedures for recovering the Income Fortress Platform from various disaster scenarios.

**Use this guide when:**
- Complete infrastructure failure
- Data corruption or loss
- Security breach requiring full rebuild
- Regional outage (DigitalOcean)
- Unrecoverable application errors

### Recovery Time Objectives (RTO)

| Scenario | Target RTO | Maximum Downtime |
|----------|-----------|------------------|
| Single container failure | 5 minutes | Automatic restart |
| Database corruption | 30 minutes | Manual intervention |
| Complete droplet failure | 1 hour | Full rebuild required |
| Regional outage | 4 hours | Multi-region failover |
| Data center disaster | 8 hours | Complete restoration |

### Recovery Point Objectives (RPO)

| Data Type | Target RPO | Data Loss Window |
|-----------|-----------|------------------|
| User data | 24 hours | Last daily backup |
| Transactions | 24 hours | Last daily backup |
| Configuration | 0 hours | Version controlled |
| System state | 24 hours | Last daily backup |

---

## Backup Strategy

### Automated Backups

#### Database Backups (Daily)

**Schedule:** 2:00 AM EST daily  
**Retention:** 30 days local + 90 days in Spaces  
**Location:** `/opt/income-platform/backups/database/` + DigitalOcean Spaces

**Automated via cron:**
```bash
# View cron schedule
crontab -l

# Expected entry:
0 2 * * * /opt/income-platform/scripts/backup_database.sh >> /var/log/backup.log 2>&1
```

**Backup Contents:**
- Complete PostgreSQL database dump
- All schemas (platform_shared + all tenant schemas)
- All tables, indexes, constraints
- No sensitive environment variables

**Verification:**
```bash
# List local backups
ls -lh /opt/income-platform/backups/database/

# List Spaces backups
s3cmd ls s3://income-platform-storage/backups/database/

# Test backup integrity
gzip -t /opt/income-platform/backups/database/income_platform_*.sql.gz
```

#### Configuration Backups

**What's backed up:**
- .env file (encrypted copy in secure location)
- docker-compose.yml
- nginx configuration
- SSL certificates (auto-renewed, not backed up)

**Backup method:**
```bash
# Manual configuration backup
tar -czf config-backup-$(date +%Y%m%d).tar.gz \
    .env \
    docker-compose.yml \
    nginx/ \
    prometheus/

# Upload to Spaces
s3cmd put config-backup-*.tar.gz s3://income-platform-storage/backups/config/
```

**Frequency:** Before each deployment or configuration change

#### Application State Backups

**Redis data:**
- Not backed up (cache only, can be rebuilt)
- RDB snapshots every 24 hours (local)

**n8n workflows:**
- Auto-saved to PostgreSQL (included in DB backup)
- Manual export option in n8n UI

### Manual Backup Procedures

#### On-Demand Database Backup

```bash
# Execute backup script
cd /opt/income-platform
./scripts/backup_database.sh

# Verify backup created
ls -lh backups/database/ | tail -1

# Verify upload to Spaces
s3cmd ls s3://income-platform-storage/backups/database/ | tail -1
```

**When to perform manual backup:**
- Before major deployments
- Before data migrations
- Before schema changes
- After significant configuration changes
- Before disaster recovery testing

#### Full System Backup

```bash
# Complete system snapshot (requires downtime)
# 1. Stop services
docker-compose down

# 2. Backup database
./scripts/backup_database.sh

# 3. Backup application files
tar -czf /backup/system-$(date +%Y%m%d).tar.gz \
    /opt/income-platform \
    --exclude='*/node_modules/*' \
    --exclude='*.log'

# 4. Upload to Spaces
s3cmd put /backup/system-*.tar.gz s3://income-platform-storage/backups/system/

# 5. Restart services
docker-compose up -d
```

**Downtime:** ~5-10 minutes  
**Frequency:** Monthly (first Sunday of month)

---

## Recovery Procedures

### Scenario 1: Single Container Failure

**Symptoms:**
- One container shows "Exited" status
- Health checks failing for specific service
- Logs show container crash

**Recovery Procedure:**

```bash
# 1. Identify failed container
docker-compose ps
# Look for: Exit (1) or Restarting

# 2. Check logs for error
docker-compose logs --tail=100 [container-name]

# 3. Attempt restart
docker-compose restart [container-name]

# 4. If restart fails, rebuild
docker-compose up -d --no-deps --build [container-name]

# 5. Verify recovery
docker-compose ps [container-name]
curl https://api.incomefortress.com/health
```

**RTO:** 5 minutes  
**Data Loss:** None  
**Downtime:** Minimal (other services continue)

---

### Scenario 2: Database Corruption

**Symptoms:**
- PostgreSQL errors in logs
- Connection pool exhausted
- Data integrity errors
- Cannot connect to database

**Recovery Procedure:**

```bash
# 1. Stop all writes immediately
docker-compose stop api celery-worker-scoring celery-worker-portfolio celery-worker-monitoring

# 2. Assess corruption
psql "$DATABASE_URL"
# Try querying critical tables
SELECT COUNT(*) FROM platform_shared.securities;
SELECT COUNT(*) FROM tenant_001.users;

# If queries fail, proceed with restore

# 3. Identify last good backup
ls -lht /opt/income-platform/backups/database/ | head -5

# 4. Restore database
./scripts/restore_database.sh [backup-filename]

# Script will:
# - Create pre-restore backup
# - Drop existing database
# - Restore from backup
# - Verify restoration

# 5. Verify data integrity
psql "$DATABASE_URL"
SELECT COUNT(*) FROM platform_shared.securities;
SELECT COUNT(*) FROM tenant_001.users;

# 6. Restart services
docker-compose start api celery-worker-scoring celery-worker-portfolio celery-worker-monitoring

# 7. Smoke test
curl https://api.incomefortress.com/health/detailed
```

**RTO:** 30 minutes  
**Data Loss:** Up to 24 hours (last backup)  
**Downtime:** 30 minutes

**Post-Recovery:**
- Review database logs to identify corruption cause
- Document incident
- Consider more frequent backups if needed

---

### Scenario 3: Complete Droplet Failure

**Symptoms:**
- Cannot SSH to droplet
- All services unreachable
- Droplet shows "off" in DigitalOcean console

**Recovery Procedure:**

```bash
# Option A: Restart existing droplet (if possible)
# 1. Via DigitalOcean console, power on droplet
# 2. Wait 2-3 minutes
# 3. SSH and verify services
ssh root@[DROPLET_IP]
docker-compose ps

# Option B: Create new droplet (if restart impossible)
# 1. Provision new 4GB droplet (follow deployment guide)
# 2. Install Docker and dependencies
# 3. Clone repository
cd /opt
git clone https://github.com/AlbertoDBP/Agentic.git
cd Agentic/income-platform

# 4. Restore configuration
# Download from Spaces or recreate .env
s3cmd get s3://income-platform-storage/backups/config/config-backup-*.tar.gz
tar -xzf config-backup-*.tar.gz

# 5. Update .env with new droplet IP if needed

# 6. Initialize SSL certificates
./scripts/init_ssl.sh

# 7. Restore database
# Database is managed service (not on droplet) - should still be accessible
# Update DB whitelist with new droplet IP
# Test connection:
psql "$DATABASE_URL"

# 8. Deploy application
docker-compose build
docker-compose up -d

# 9. Verify services
curl https://api.incomefortress.com/health
```

**RTO:** 1 hour  
**Data Loss:** None (managed database persists)  
**Downtime:** 1 hour

**Important Notes:**
- Managed PostgreSQL and Redis are separate - they survive droplet failure
- Only need to rebuild application layer
- Update DNS if IP changes
- Update database/Redis IP whitelists

---

### Scenario 4: Complete Data Loss

**Symptoms:**
- Database completely lost
- All backups corrupted
- Managed database service unrecoverable

**Recovery Procedure:**

```bash
# This is worst-case scenario - requires full rebuild

# 1. Provision new managed database
# Via DigitalOcean console

# 2. Update .env with new database credentials
nano .env
# Update: DB_HOST, DB_PORT, DB_PASSWORD, DATABASE_URL

# 3. Restore from oldest available backup
ls -lh /opt/income-platform/backups/database/
# Or download from Spaces
s3cmd get s3://income-platform-storage/backups/database/income_platform_*.sql.gz

# 4. Import backup to new database
gunzip income_platform_*.sql.gz
psql "$DATABASE_URL" < income_platform_*.sql

# 5. Run migrations to ensure schema current
docker-compose run --rm api alembic upgrade head

# 6. Verify data
psql "$DATABASE_URL"
\dt platform_shared.*
\dt tenant_001.*
SELECT COUNT(*) FROM platform_shared.securities;

# 7. Restart all services
docker-compose restart

# 8. Full smoke test
# - User login
# - Asset scoring
# - Portfolio loading
```

**RTO:** 2-4 hours  
**Data Loss:** Up to 24 hours (last backup)  
**Downtime:** 2-4 hours

**Post-Recovery:**
- Investigate cause of data loss
- Implement additional backup measures
- Consider point-in-time recovery (more expensive)

---

### Scenario 5: Security Breach

**Symptoms:**
- Unauthorized access detected
- Suspicious database queries
- API keys compromised
- Unknown processes running

**Immediate Actions:**

```bash
# 1. ISOLATE - Stop accepting traffic
docker-compose stop nginx
# Or at firewall level:
ufw deny 80
ufw deny 443

# 2. PRESERVE - Capture state for investigation
# Take memory dump (if forensics needed)
docker-compose logs > /tmp/incident-logs-$(date +%Y%m%d-%H%M%S).log

# Copy logs to secure location
scp /tmp/incident-logs-* [secure-location]

# 3. ASSESS - Check for compromise
# Review database for unauthorized changes
psql "$DATABASE_URL" -c "\
  SELECT * FROM platform_shared.audit_log \
  WHERE created_at > NOW() - INTERVAL '24 hours' \
  ORDER BY created_at DESC;"

# Check running processes
ps aux | grep -v grep

# Check system users
cat /etc/passwd

# 4. CONTAIN - If compromised
# Option A: Rebuild from scratch (recommended)
# Option B: Clean and patch

# Full Rebuild Procedure:
# a. Backup current state for investigation
./scripts/backup_database.sh

# b. Provision new droplet
# c. Deploy fresh installation
# d. Restore from pre-breach backup

# e. Rotate ALL secrets
# Generate new:
openssl rand -hex 32  # SECRET_KEY
openssl rand -hex 32  # JWT_SECRET_KEY
openssl rand -hex 32  # N8N_ENCRYPTION_KEY

# Rotate Anthropic API key
# Rotate database password
# Rotate Redis password
# Rotate Spaces keys

# f. Force logout all users (invalidate JWT tokens)
# Update JWT_SECRET_KEY in .env
docker-compose restart api

# g. Enable additional monitoring

# 5. VERIFY - Ensure no backdoors
# Full security scan
# Check crontabs: crontab -l
# Check startup scripts: ls /etc/rc*.d/
# Check Docker images: docker images
# Scan for rootkits: rkhunter --check

# 6. RECOVER - Restore service
# Re-enable firewall rules
ufw allow 80
ufw allow 443

docker-compose start nginx

# 7. MONITOR - Watch for re-compromise
# Increase log verbosity
# Watch for suspicious patterns
```

**RTO:** 4-8 hours (full rebuild)  
**Data Loss:** Varies (use pre-breach backup)  
**Downtime:** 4-8 hours

**Post-Incident:**
- Full forensic analysis
- Document attack vector
- Implement additional security measures
- Notify affected users (if data exposed)
- Report to authorities if required

---

### Scenario 6: Regional Outage (DigitalOcean NYC)

**Symptoms:**
- All NYC resources unavailable
- DigitalOcean status page shows outage
- Cannot access droplet, database, Redis

**Recovery Procedure:**

**Pre-Requisite:** Multi-region setup (Phase 3 enhancement)

```bash
# Current Setup: Single region (NYC3)
# No immediate failover capability

# Mitigation Strategy:
# 1. Wait for DigitalOcean to restore service
# 2. If extended (>4 hours), rebuild in different region

# Emergency Multi-Region Deployment:
# 1. Provision resources in SFO region
# - Droplet in SFO1
# - Managed PostgreSQL in SFO
# - Managed Redis in SFO
# - Spaces in SFO

# 2. Restore from latest Spaces backup
# (Spaces NYC3 should be accessible from SFO)
s3cmd get s3://income-platform-storage/backups/database/income_platform_latest.sql.gz

# 3. Deploy application in SFO

# 4. Update DNS to point to SFO droplet
# (5 minute TTL allows quick switchover)

# 5. Verify service restoration
```

**RTO:** 4 hours (manual rebuild in different region)  
**Data Loss:** Up to 24 hours  
**Downtime:** 4 hours

**Future Enhancement:**
- Phase 3: Implement multi-region active-active
- Real-time database replication
- Geographic load balancing

---

## Testing & Validation

### Quarterly DR Test Schedule

**Q1 (January):** Database restore test  
**Q2 (April):** Complete droplet rebuild test  
**Q3 (July):** Security breach simulation  
**Q4 (October):** Full disaster recovery drill

### Database Restore Test Procedure

```bash
# Perform in staging/test environment, not production

# 1. Create test database
createdb income_test

# 2. Restore latest backup
# Download from Spaces
s3cmd get s3://income-platform-storage/backups/database/income_platform_$(date +%Y%m%d)*.sql.gz

# Restore
gunzip income_platform_*.sql.gz
psql postgresql://user:pass@host:port/income_test < income_platform_*.sql

# 3. Verify data integrity
psql postgresql://user:pass@host:port/income_test

# Count records in critical tables
SELECT 
  'securities' as table_name, COUNT(*) FROM platform_shared.securities
UNION ALL
SELECT 
  'users', COUNT(*) FROM tenant_001.users
UNION ALL
SELECT
  'portfolios', COUNT(*) FROM tenant_001.portfolios;

# 4. Test application against test database
# Update test .env to point to income_test
DATABASE_URL=postgresql://user:pass@host:port/income_test

# Start application
docker-compose up -d

# Smoke test
curl http://localhost:8000/health/detailed

# 5. Document results
# - Restore time: _____ minutes
# - Data integrity: PASS/FAIL
# - Application functionality: PASS/FAIL

# 6. Cleanup
dropdb income_test
```

### DR Drill Checklist

- [ ] DR team assembled
- [ ] Roles assigned (incident commander, ops, comms)
- [ ] Scenario briefed
- [ ] Start time noted
- [ ] Recovery procedure executed
- [ ] RTO measured
- [ ] Data integrity verified
- [ ] Application functionality verified
- [ ] End time noted
- [ ] Lessons learned documented
- [ ] Runbook updated with findings

---

## Contact Information

### Emergency Contacts

**On-Call Rotation:**
- Primary: [Name] - [Phone] - [Email]
- Secondary: [Name] - [Phone] - [Email]
- Escalation: [Name] - [Phone] - [Email]

**Vendor Support:**
- DigitalOcean Support: https://cloud.digitalocean.com/support
- Anthropic Support: support@anthropic.com
- DNS Provider: [Contact info]

### Communication Channels

**During DR Event:**
- Primary: Slack #incidents
- Secondary: Email distribution list
- Conference bridge: [Number/Link]

**Status Updates:**
- Internal: Every 30 minutes
- External: As appropriate
- Post-incident: Within 24 hours

---

## Appendix: Recovery Scripts

### Quick Database Restore

```bash
#!/bin/bash
# quick-restore.sh

set -e

BACKUP_FILE=$1

if [ -z "$BACKUP_FILE" ]; then
    echo "Usage: $0 <backup-file>"
    exit 1
fi

echo "⚠️  WARNING: This will replace the production database!"
read -p "Type 'RESTORE' to confirm: " confirm

if [ "$confirm" != "RESTORE" ]; then
    echo "Cancelled"
    exit 0
fi

# Stop services
echo "Stopping services..."
docker-compose stop api celery-worker-scoring celery-worker-portfolio celery-worker-monitoring

# Restore
echo "Restoring database..."
./scripts/restore_database.sh "$BACKUP_FILE"

# Restart services
echo "Restarting services..."
docker-compose start api celery-worker-scoring celery-worker-portfolio celery-worker-monitoring

# Verify
echo "Verifying..."
sleep 5
curl https://api.incomefortress.com/health/detailed

echo "✅ Restore complete"
```

### Emergency Rollback

```bash
#!/bin/bash
# emergency-rollback.sh

set -e

echo "🚨 EMERGENCY ROLLBACK"
echo "This will:"
echo "  1. Stop all services"
echo "  2. Restore database from last backup"
echo "  3. Checkout previous code version"
echo "  4. Restart services"

read -p "Proceed? (yes/no): " confirm

if [ "$confirm" != "yes" ]; then
    exit 0
fi

# Stop services
docker-compose down

# Restore database
LATEST_BACKUP=$(ls -t backups/database/*.sql.gz | head -1)
./scripts/restore_database.sh "$LATEST_BACKUP"

# Rollback code
git log --oneline -10
read -p "Enter commit hash to rollback to: " commit
git checkout "$commit"

# Rebuild and restart
docker-compose build
docker-compose up -d

# Verify
sleep 10
curl https://api.incomefortress.com/health

echo "✅ Rollback complete"
echo "Commit: $commit"
echo "Database: $LATEST_BACKUP"
```

---

## Document History

| Version | Date | Changes | Author |
|---------|------|---------|--------|
| 1.0.0 | 2026-02-02 | Initial version | Alberto DBP |

---

**Document Classification:** CRITICAL  
**Distribution:** Operations Team Only  
**Review Frequency:** Quarterly  
**Next Review:** May 1, 2026

**Last Tested:** [Date of last DR drill]  
**Test Result:** [PASS/FAIL]  
**Test Notes:** [Link to test report]
