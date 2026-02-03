# Disaster Recovery Plan - Income Fortress Platform

**Version:** 1.0.0  
**Last Updated:** February 3, 2026  
**Audience:** DevOps, SRE, Engineering Leadership

---

## Table of Contents

1. [Overview](#overview)
2. [Recovery Objectives](#recovery-objectives)
3. [Disaster Scenarios](#disaster-scenarios)
4. [Backup Strategy](#backup-strategy)
5. [Recovery Procedures](#recovery-procedures)
6. [Testing & Validation](#testing--validation)
7. [Post-Recovery](#post-recovery)

---

## Overview

### Purpose

This document defines procedures for recovering the Income Fortress Platform from catastrophic failures, including:
- Complete system outages
- Data corruption or loss
- Infrastructure failures
- Security breaches
- Natural disasters affecting data centers

### Scope

**In Scope:**
- Application services (API, Celery workers)
- Database (PostgreSQL)
- Cache layer (Redis)
- File storage and configurations
- Infrastructure (Docker, Nginx)

**Out of Scope:**
- DigitalOcean platform failures (handled by vendor SLAs)
- Third-party API outages (Anthropic, market data)
- Client-side issues

### Roles & Responsibilities

**Incident Commander** (DevOps Lead)
- Declare disaster state
- Coordinate recovery efforts
- Communicate with stakeholders
- Make final decisions on recovery approach

**Technical Lead** (Senior Engineer)
- Execute technical recovery procedures
- Validate data integrity
- Restore services
- Document technical findings

**Database Administrator** (DBA)
- Database restoration
- Data validation
- Performance tuning post-recovery

**Communications Lead** (Product Manager)
- User communication
- Status page updates
- Stakeholder updates
- Post-mortem documentation

---

## Recovery Objectives

### Recovery Time Objective (RTO)

**Maximum acceptable downtime for each service:**

| Service | RTO Target | Maximum Acceptable |
|---------|------------|-------------------|
| API (Complete Outage) | 4 hours | 8 hours |
| Database (Primary Failure) | 1 hour | 2 hours |
| Cache (Redis Failure) | 30 minutes | 1 hour |
| Celery Workers | 1 hour | 2 hours |
| Background Jobs | 2 hours | 4 hours |

### Recovery Point Objective (RPO)

**Maximum acceptable data loss:**

| Data Type | RPO Target | Maximum Acceptable |
|-----------|------------|-------------------|
| User Data (Portfolios, Proposals) | 1 hour | 4 hours |
| Transaction History | 1 hour | 4 hours |
| Market Data (Cache) | 24 hours | 48 hours |
| System Logs | 24 hours | 72 hours |
| Configuration Changes | 0 (immediate backup) | 1 hour |

### Service Priority

**P0 - Critical (Restore First)**
- Database (PostgreSQL)
- API service
- Authentication system

**P1 - High (Restore Second)**
- Celery workers (scoring, execution)
- Redis cache
- Background job processing

**P2 - Medium (Restore Third)**
- Monitoring (Prometheus, Grafana)
- Logging infrastructure
- Non-essential background jobs

---

## Disaster Scenarios

### Scenario 1: Complete Infrastructure Failure

**Description:** DigitalOcean droplet completely unrecoverable (hardware failure, data center outage)

**Impact:**
- Total service outage
- All containers offline
- Need complete rebuild

**Recovery Time:** 4-6 hours (within RTO)

**Trigger Conditions:**
- Droplet status shows "destroyed" or "critical hardware failure"
- Unable to SSH or ping droplet for >30 minutes
- DigitalOcean support confirms hardware failure

**Recovery Procedure:** See [Complete Infrastructure Recovery](#complete-infrastructure-recovery)

### Scenario 2: Database Corruption or Failure

**Description:** PostgreSQL database corrupted, unavailable, or data integrity compromised

**Impact:**
- API returns 5xx errors
- Cannot read/write user data
- Transaction history at risk

**Recovery Time:** 1-2 hours (within RTO)

**Trigger Conditions:**
- Database connection failures
- Data integrity check failures
- Corrupted table errors in logs
- Managed database status shows "critical"

**Recovery Procedure:** See [Database Recovery](#database-recovery)

### Scenario 3: Data Corruption (Application Level)

**Description:** Application bug causes invalid data writes, logical corruption

**Impact:**
- Portfolio values incorrect
- Scores miscalculated
- Proposals invalid

**Recovery Time:** 2-4 hours (within RTO)

**Trigger Conditions:**
- User reports of incorrect data
- Data validation alerts firing
- Anomalous values in database

**Recovery Procedure:** See [Data Corruption Recovery](#data-corruption-recovery)

### Scenario 4: Security Breach

**Description:** Unauthorized access, data exfiltration, or malware infection

**Impact:**
- All user data potentially compromised
- System integrity unknown
- Legal/compliance implications

**Recovery Time:** Immediate isolation, 8-24 hours full recovery

**Trigger Conditions:**
- Unauthorized access alerts
- Suspicious database queries
- Data exfiltration detected
- Malware detected

**Recovery Procedure:** See [Security Breach Recovery](#security-breach-recovery)

### Scenario 5: Accidental Data Deletion

**Description:** Administrator error causes unintended data deletion

**Impact:**
- Specific tenant data lost
- User portfolios deleted
- Configuration lost

**Recovery Time:** 30 minutes - 2 hours

**Trigger Conditions:**
- User reports missing data
- Audit logs show deletion events
- Database row count significantly decreased

**Recovery Procedure:** See [Data Restoration from Backup](#data-restoration-from-backup)

---

## Backup Strategy

### Automated Backups

**Database Backups:**
- **Frequency:** Daily at 2:00 AM EST
- **Retention:** 7 days (rolling)
- **Location:** `/backups/postgresql/` on droplet + DigitalOcean Spaces (offsite)
- **Format:** PostgreSQL dump (`.sql`)
- **Verification:** Automated restore test on staging weekly

**Configuration Backups:**
- **Frequency:** On every change (automated via Git)
- **Retention:** Unlimited (Git history)
- **Location:** GitHub repository
- **Format:** Text files (`.env.example`, `docker-compose.yml`, etc.)

**Code Backups:**
- **Frequency:** Every commit
- **Retention:** Unlimited
- **Location:** GitHub repository
- **Format:** Git repository

### Manual Backups

**Pre-Deployment Backup:**
```bash
# Create tagged backup before deployment
./scripts/backup_database.sh --tag="pre-v1.1.0-deployment"

# Verify backup created
ls -lh backups/ | grep pre-v1.1.0
```

**Pre-Migration Backup:**
```bash
# Create backup before database migration
./scripts/backup_database.sh --tag="pre-migration-$(date +%Y%m%d)"

# Test restore on staging
./scripts/restore_database.sh backups/latest.sql --target=staging
```

### Backup Verification

**Weekly Restoration Test (Sundays 3:00 AM EST):**
```bash
#!/bin/bash
# scripts/test_backup_restore.sh

# 1. Get latest backup
LATEST_BACKUP=$(ls -t backups/*.sql | head -1)

# 2. Restore to staging database
pg_restore -d $STAGING_DATABASE_URL -c $LATEST_BACKUP

# 3. Run validation queries
psql $STAGING_DATABASE_URL -c "SELECT COUNT(*) FROM users;"
psql $STAGING_DATABASE_URL -c "SELECT COUNT(*) FROM portfolios;"

# 4. Log results
echo "Backup test: SUCCESS" >> /var/log/backup-tests.log

# 5. Clean up staging
psql $STAGING_DATABASE_URL -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"
```

### Offsite Backups

**DigitalOcean Spaces Configuration:**
```bash
# Install AWS CLI (compatible with DO Spaces)
pip install awscli

# Configure credentials
aws configure set aws_access_key_id $DO_SPACES_KEY
aws configure set aws_secret_access_key $DO_SPACES_SECRET
aws configure set default.region nyc3

# Upload backup
aws s3 cp backups/$(date +%Y%m%d).sql \
  s3://incomefortress-backups/postgresql/ \
  --endpoint-url=https://nyc3.digitaloceanspaces.com

# Verify upload
aws s3 ls s3://incomefortress-backups/postgresql/ \
  --endpoint-url=https://nyc3.digitaloceanspaces.com
```

**Backup Script (Automated):**
```bash
#!/bin/bash
# scripts/backup_database.sh

DATE=$(date +%Y%m%d-%H%M%S)
BACKUP_FILE="backups/income-platform-${DATE}.sql"

# Create local backup
pg_dump $DATABASE_URL > $BACKUP_FILE

# Compress backup
gzip $BACKUP_FILE

# Upload to Spaces
aws s3 cp ${BACKUP_FILE}.gz \
  s3://incomefortress-backups/postgresql/ \
  --endpoint-url=https://nyc3.digitaloceanspaces.com

# Clean up old local backups (keep 7 days)
find backups/ -name "*.sql.gz" -mtime +7 -delete

echo "Backup completed: $BACKUP_FILE"
```

---

## Recovery Procedures

### Complete Infrastructure Recovery

**Scenario:** Droplet completely destroyed, need to rebuild from scratch

**Prerequisites:**
- Access to GitHub repository
- Access to DigitalOcean console
- Latest database backup available
- Environment variables documented

**Estimated Time:** 4-6 hours

**Procedure:**

#### Phase 1: Infrastructure Provisioning (60 minutes)

```bash
# 1. Create new droplet (via DigitalOcean console)
# - Ubuntu 24.04 LTS
# - 8GB RAM, 4 vCPUs, 160GB SSD
# - Enable backups
# - Add SSH keys

# 2. Initial server setup
ssh root@<new-droplet-ip>

# Update system
apt update && apt upgrade -y

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh

# Install Docker Compose
apt install docker-compose-plugin -y

# Create deployer user
adduser deployer
usermod -aG docker deployer
usermod -aG sudo deployer

# Switch to deployer
su - deployer
```

#### Phase 2: Application Deployment (90 minutes)

```bash
# 1. Clone repository
git clone https://github.com/AlbertoDBP/Agentic.git
cd Agentic/income-platform

# 2. Checkout production tag
git checkout v1.0.0

# 3. Create .env file
cp .env.example .env
nano .env  # Fill in all values from documentation

# 4. Set permissions
chmod 600 .env

# 5. Verify managed services (DigitalOcean console)
# - PostgreSQL: Confirm connection string
# - Redis: Confirm connection string
# - Update .env with current connection strings
```

#### Phase 3: Database Restoration (60 minutes)

```bash
# 1. Download latest backup from Spaces
aws s3 cp s3://incomefortress-backups/postgresql/latest.sql.gz . \
  --endpoint-url=https://nyc3.digitaloceanspaces.com

# 2. Decompress backup
gunzip latest.sql.gz

# 3. Restore database
psql $DATABASE_URL < latest.sql

# 4. Verify restoration
psql $DATABASE_URL -c "SELECT COUNT(*) FROM users;"
psql $DATABASE_URL -c "SELECT COUNT(*) FROM portfolios;"

# 5. Run any pending migrations
docker compose run --rm api python manage.py migrate
```

#### Phase 4: Service Startup (30 minutes)

```bash
# 1. Build and start all services
docker compose up -d --build

# 2. Verify all services running
docker compose ps

# Expected: All services "Up (healthy)"

# 3. Check health endpoint
curl http://localhost:8000/health

# 4. Check logs for errors
docker compose logs --tail=100 | grep ERROR
```

#### Phase 5: SSL & DNS Configuration (60 minutes)

```bash
# 1. Install Certbot
apt install certbot python3-certbot-nginx

# 2. Update DNS (if IP changed)
# - Update A record: api.incomefortress.com → new-ip
# - Wait for propagation (5-30 minutes)

# 3. Obtain SSL certificate
certbot --nginx -d api.incomefortress.com

# 4. Test SSL
curl https://api.incomefortress.com/health

# 5. Verify auto-renewal
certbot renew --dry-run
```

#### Phase 6: Verification & Monitoring (60 minutes)

```bash
# 1. Run health checks
curl https://api.incomefortress.com/health/detailed

# 2. Test authentication
curl -X POST https://api.incomefortress.com/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"test"}'

# 3. Test scoring
curl -X POST https://api.incomefortress.com/api/v1/scores/VYM

# 4. Verify Celery workers
docker compose exec celery_default celery -A income_platform inspect active

# 5. Set up monitoring
# - Configure Prometheus scraping
# - Import Grafana dashboards
# - Test alert rules

# 6. Verify backups running
crontab -l | grep backup_database.sh
```

#### Phase 7: Go-Live (30 minutes)

```bash
# 1. Notify team
# - Post in Slack: "Disaster recovery complete, system online"

# 2. Monitor closely for 2 hours
# - Watch error rates
# - Check response times
# - Verify background jobs processing

# 3. Document recovery
# - Time to recovery
# - Issues encountered
# - Lessons learned

# 4. Update status page
# - Mark incident resolved
# - Post post-mortem (within 48 hours)
```

**Total Time:** 4-6 hours (within 8-hour RTO)

---

### Database Recovery

**Scenario:** Managed PostgreSQL failure or corruption

**Prerequisites:**
- Latest database backup
- Managed database status (check DigitalOcean)
- API stopped (to prevent writes during recovery)

**Estimated Time:** 1-2 hours

**Procedure:**

#### Option A: Managed Database Failover (30 minutes)

```bash
# 1. Check managed database status (DigitalOcean console)
# - If standby available, initiate failover

# 2. Update connection string (if IP changed)
# Edit .env: DATABASE_URL=new-connection-string

# 3. Restart API
docker compose restart api

# 4. Verify connectivity
docker compose exec api python -c "from django.db import connection; connection.ensure_connection()"
```

#### Option B: Restore from Backup (90 minutes)

```bash
# 1. Stop all services (prevent writes)
docker compose down

# 2. Download latest backup
aws s3 cp s3://incomefortress-backups/postgresql/latest.sql.gz . \
  --endpoint-url=https://nyc3.digitaloceanspaces.com

# 3. Drop existing database (if corrupted)
psql $DATABASE_URL -c "DROP DATABASE income_platform;"
psql $DATABASE_URL -c "CREATE DATABASE income_platform;"

# 4. Restore backup
gunzip latest.sql.gz
psql $DATABASE_URL < latest.sql

# 5. Verify data integrity
psql $DATABASE_URL -c "SELECT COUNT(*) FROM users;"
psql $DATABASE_URL -c "SELECT COUNT(*) FROM portfolios;"
psql $DATABASE_URL -c "SELECT COUNT(*) FROM proposals;"

# 6. Run VACUUM ANALYZE
psql $DATABASE_URL -c "VACUUM ANALYZE;"

# 7. Restart services
docker compose up -d

# 8. Verify application health
curl https://api.incomefortress.com/health
```

#### Option C: Point-in-Time Recovery (if available)

```bash
# 1. Check DigitalOcean managed database PITR settings
# - If enabled, restore to specific timestamp

# 2. Initiate PITR via DigitalOcean console
# - Select timestamp (before corruption)
# - Create new database cluster from PITR

# 3. Update connection string
# Edit .env: DATABASE_URL=pitr-cluster-connection

# 4. Restart services
docker compose restart

# 5. Verify data
# - Check critical tables
# - Verify timestamp of last transaction
```

---

### Data Corruption Recovery

**Scenario:** Logical data corruption (bad application logic, not database corruption)

**Prerequisites:**
- Identified scope of corruption
- Backup from before corruption occurred
- List of affected tenants/users

**Estimated Time:** 2-4 hours

**Procedure:**

```bash
# 1. Identify corruption scope
docker compose exec api python manage.py dbshell

# Find affected records
SELECT * FROM portfolios WHERE updated_at > '2026-02-03 10:00:00' 
  AND value < 0;  -- Example: negative values impossible

# 2. Enable maintenance mode
docker compose exec api python manage.py set_maintenance_mode on

# 3. Export current state (for forensics)
pg_dump $DATABASE_URL > corrupted-state-$(date +%Y%m%d).sql

# 4. Identify last good backup
ls -ltr backups/
# Find backup from before corruption time

# 5. Restore affected tables ONLY (selective restore)
# Extract specific tables from backup
pg_restore -t portfolios -t proposals backups/good-backup.sql | \
  psql $DATABASE_URL

# 6. Verify restoration
psql $DATABASE_URL -c "SELECT COUNT(*) FROM portfolios WHERE value < 0;"
# Expected: 0 rows

# 7. Re-run any jobs that may have been affected
docker compose exec celery_default celery -A income_platform purge
docker compose exec api python manage.py trigger_rebalancing_all

# 8. Disable maintenance mode
docker compose exec api python manage.py set_maintenance_mode off

# 9. Notify affected users
docker compose exec api python manage.py send_notification \
  --users=affected_user_ids \
  --message="Data restored from backup due to system error"
```

---

### Security Breach Recovery

**Scenario:** Confirmed unauthorized access or data breach

**Impact:** All systems potentially compromised

**Estimated Time:** 8-24 hours (immediate isolation, full recovery longer)

**Immediate Actions (0-15 minutes):**

```bash
# 1. ISOLATE SYSTEM IMMEDIATELY
# Block all traffic
sudo ufw deny from any to any port 80
sudo ufw deny from any to any port 443

# Stop all services
docker compose down

# 2. PRESERVE EVIDENCE
# Capture all logs
docker compose logs > breach-logs-$(date +%Y%m%d-%H%M%S).txt

# Capture system state
ps aux > breach-processes-$(date +%Y%m%d-%H%M%S).txt
netstat -tulpn > breach-network-$(date +%Y%m%d-%H%M%S).txt

# 3. NOTIFY SECURITY TEAM
# Email: security@incomefortress.com
# Escalate to CTO immediately
```

**Investigation Phase (15 minutes - 4 hours):**

```bash
# 1. Analyze breach scope
# - Review access logs
# - Identify compromised accounts
# - Check for data exfiltration

# 2. Identify entry point
grep -r "unauthorized" /var/log/
docker compose logs | grep -E "authentication.*failed|suspicious"

# 3. Document findings
# - Timeline of events
# - Systems affected
# - Data potentially compromised
```

**Recovery Phase (4-24 hours):**

```bash
# 1. Rotate ALL credentials
# - Database passwords
# - API keys (Anthropic, market data)
# - SSH keys
# - Application secrets
# - SSL certificates

# 2. Rebuild system from known-good state
# - Use infrastructure recovery procedure
# - Deploy from trusted Git tag (not latest)
# - Restore database from backup BEFORE breach time

# 3. Apply security patches
# - Update all dependencies
# - Apply OS security patches
# - Review and harden firewall rules

# 4. Enhanced monitoring
# - Enable detailed audit logging
# - Set up intrusion detection
# - Increase alert sensitivity

# 5. Gradual restoration
# - Start with single tenant (test account)
# - Verify no suspicious activity
# - Gradually add tenants back

# 6. User notification
# - Notify all users of breach
# - Force password resets
# - Provide security recommendations
```

**Post-Breach Actions:**

- [ ] Conduct security audit
- [ ] Engage third-party security firm (if needed)
- [ ] Review compliance requirements (GDPR, etc.)
- [ ] Update incident response plan
- [ ] Implement additional security controls
- [ ] Conduct team training on security best practices

---

### Data Restoration from Backup

**Scenario:** Accidental deletion, need to restore specific data

**Prerequisites:**
- Backup containing deleted data
- Timestamp of deletion
- List of affected records

**Estimated Time:** 30 minutes - 2 hours

**Procedure:**

```bash
# 1. Identify what was deleted
# Check audit logs
docker compose exec api python manage.py dbshell
SELECT * FROM audit_log WHERE action='DELETE' 
  AND timestamp > '2026-02-03 00:00:00';

# 2. Find appropriate backup
# Backup from before deletion time
ls -ltr backups/ | grep "2026-02-02"

# 3. Extract deleted data from backup
# Restore to temporary database
createdb temp_restore
psql temp_restore < backups/2026-02-02.sql

# 4. Export deleted records
psql temp_restore -c "
COPY (SELECT * FROM portfolios WHERE id IN (1,2,3)) 
TO '/tmp/deleted-portfolios.csv' CSV HEADER;
"

# 5. Import to production database
psql $DATABASE_URL -c "
COPY portfolios FROM '/tmp/deleted-portfolios.csv' CSV HEADER;
"

# 6. Verify restoration
psql $DATABASE_URL -c "SELECT * FROM portfolios WHERE id IN (1,2,3);"

# 7. Clean up
dropdb temp_restore
rm /tmp/deleted-portfolios.csv
```

---

## Testing & Validation

### Disaster Recovery Drills

**Quarterly DR Drill (Every 3 months):**

**Drill Objectives:**
- Validate backup restoration procedures
- Test team coordination
- Identify gaps in documentation
- Measure actual RTO/RPO

**Drill Procedure:**

```bash
# 1. Schedule drill (communicate to team 2 weeks in advance)
# 2. Prepare staging environment
# 3. Simulate disaster scenario (select one scenario)
# 4. Execute recovery procedure (timed)
# 5. Validate recovery success
# 6. Document results and lessons learned
# 7. Update DR plan based on findings
```

**Success Criteria:**
- [ ] Recovery completed within RTO
- [ ] No data loss beyond RPO
- [ ] All services functional after recovery
- [ ] Team followed procedures without major issues
- [ ] Documentation accurate and complete

### Monthly Backup Validation

**First Sunday of each month, 3:00 AM EST:**

```bash
#!/bin/bash
# scripts/monthly_backup_validation.sh

# 1. Restore latest backup to staging
LATEST_BACKUP=$(ls -t backups/*.sql.gz | head -1)
gunzip -c $LATEST_BACKUP | psql $STAGING_DATABASE_URL

# 2. Run data integrity checks
psql $STAGING_DATABASE_URL -c "
SELECT 
  'users' AS table_name, COUNT(*) AS count FROM users
UNION
SELECT 'portfolios', COUNT(*) FROM portfolios
UNION  
SELECT 'proposals', COUNT(*) FROM proposals;
"

# 3. Test application functionality
curl http://staging.incomefortress.com/health

# 4. Log validation results
echo "$(date): Backup validation SUCCESS" >> /var/log/backup-validation.log

# 5. Clean up staging
psql $STAGING_DATABASE_URL -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"
```

### Annual DR Audit

**Conducted by external auditor or senior leadership:**

**Audit Items:**
- [ ] DR plan documentation current and accurate
- [ ] Backup procedures functioning correctly
- [ ] Recovery procedures tested and validated
- [ ] RTO/RPO targets achievable
- [ ] Team trained on procedures
- [ ] Contacts and escalation paths current
- [ ] Compliance requirements met (GDPR, etc.)

---

## Post-Recovery

### Post-Recovery Checklist

**Immediate (0-2 hours after recovery):**
- [ ] Verify all services healthy
- [ ] Confirm no data loss (within RPO)
- [ ] Check error rates normal (<1%)
- [ ] Monitor resource utilization
- [ ] Notify team of recovery completion

**Short-term (2-24 hours after recovery):**
- [ ] Monitor for anomalies
- [ ] Review logs for issues
- [ ] Validate backup processes resumed
- [ ] Update status page
- [ ] Brief leadership on recovery

**Medium-term (24-72 hours after recovery):**
- [ ] Conduct post-mortem meeting
- [ ] Document timeline and actions
- [ ] Identify root cause
- [ ] Create action items to prevent recurrence
- [ ] Update DR plan if needed

### Post-Mortem Template

```markdown
# Incident Post-Mortem: [Incident Title]

**Date:** [Date of incident]  
**Duration:** [Start time] - [End time]  
**Severity:** [P0/P1/P2]

## Summary
[2-3 sentence summary of what happened]

## Timeline
- [Time]: [Event]
- [Time]: [Action taken]
- ...

## Impact
- Users affected: [Number/percentage]
- Downtime: [Duration]
- Data loss: [Amount, if any]
- Financial impact: [Estimate]

## Root Cause
[Detailed explanation of what caused the incident]

## Resolution
[How the incident was resolved]

## Lessons Learned
**What went well:**
- [Item]

**What didn't go well:**
- [Item]

**Where we got lucky:**
- [Item]

## Action Items
- [ ] [Action 1] - Owner: [Name] - Due: [Date]
- [ ] [Action 2] - Owner: [Name] - Due: [Date]

## Prevention
[How we'll prevent this from happening again]
```

---

## Contact Information

**Primary Contacts:**

**Incident Commander (DevOps Lead):**
- Name: Alberto D.
- Email: alberto@incomefortress.com
- Phone: [Redacted]
- Availability: 24/7 (on-call rotation)

**Technical Lead:**
- Name: [TBD]
- Email: [TBD]
- Phone: [TBD]

**Database Administrator:**
- Name: [TBD]
- Email: [TBD]
- Phone: [TBD]

**Communications Lead:**
- Name: [TBD]
- Email: [TBD]
- Phone: [TBD]

**Escalation:**
- CTO: [Contact info]
- CEO: [Contact info]

**External Contacts:**

**DigitalOcean Support:**
- Support Portal: https://cloud.digitalocean.com/support
- Phone: 1-888-890-6714
- Priority Support: Yes (Business tier)

**Anthropic Support:**
- Email: support@anthropic.com
- Portal: https://console.anthropic.com/support

**Security Incident Response:**
- Internal: security@incomefortress.com
- External (if needed): [Security firm contact]

---

## Appendix

### Quick Reference Commands

```bash
# Stop all services
docker compose down

# Backup database
./scripts/backup_database.sh

# Restore database
./scripts/restore_database.sh [backup-file]

# Download backup from Spaces
aws s3 cp s3://incomefortress-backups/postgresql/latest.sql.gz . \
  --endpoint-url=https://nyc3.digitaloceanspaces.com

# Enable maintenance mode
docker compose exec api python manage.py set_maintenance_mode on

# Disable maintenance mode
docker compose exec api python manage.py set_maintenance_mode off

# Health check
curl https://api.incomefortress.com/health
```

### Recovery Cheat Sheet

| Scenario | First Action | RTO | Recovery Procedure |
|----------|-------------|-----|-------------------|
| Complete outage | Provision new droplet | 4-6h | [Complete Infrastructure Recovery](#complete-infrastructure-recovery) |
| Database failure | Check managed DB status | 1-2h | [Database Recovery](#database-recovery) |
| Data corruption | Enable maintenance mode | 2-4h | [Data Corruption Recovery](#data-corruption-recovery) |
| Security breach | Isolate system | 8-24h | [Security Breach Recovery](#security-breach-recovery) |
| Accidental deletion | Identify affected data | 0.5-2h | [Data Restoration](#data-restoration-from-backup) |

---

**Disaster Recovery Plan Version:** 1.0.0  
**Last Updated:** February 3, 2026  
**Next Review:** May 1, 2026  
**Last DR Drill:** [Scheduled for March 2026]
