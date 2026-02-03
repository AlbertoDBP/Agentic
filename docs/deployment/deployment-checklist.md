# Deployment Checklist - Income Fortress Platform

**Version:** 1.0.0  
**Last Updated:** February 2, 2026  
**Purpose:** Comprehensive verification checklist for production deployment

---

## Overview

This checklist ensures all critical components are properly configured before, during, and after deployment.

**Checklist Phases:**
1. Pre-Deployment (Infrastructure & Configuration)
2. Deployment (Execution)
3. Post-Deployment (Verification)
4. Go-Live (Production Readiness)
5. Post-Launch (Monitoring)

**Notation:**
- [ ] Pending
- [x] Complete
- [!] Failed/Blocked
- [~] In Progress

---

## PHASE 1: Pre-Deployment

### 1.1 Infrastructure Setup

#### DigitalOcean Resources
- [ ] Droplet created (4GB RAM, 2 vCPU, NYC region)
- [ ] Droplet IP noted: `___________________`
- [ ] SSH key uploaded to DigitalOcean
- [ ] SSH access verified: `ssh root@[IP]` works
- [ ] PostgreSQL managed database created (1GB RAM)
- [ ] PostgreSQL connection details saved
- [ ] PostgreSQL IP whitelist configured (droplet IP added)
- [ ] Redis managed instance created (1GB RAM)
- [ ] Redis connection details saved
- [ ] Redis IP whitelist configured
- [ ] Spaces bucket created: `income-platform-storage`
- [ ] Spaces CDN enabled
- [ ] Spaces access keys generated and saved

#### DNS Configuration
- [ ] Domain registered: `incomefortress.com`
- [ ] A record created: `api.incomefortress.com` → Droplet IP
- [ ] A record created: `n8n.incomefortress.com` → Droplet IP
- [ ] A record created: `app.incomefortress.com` → Droplet IP (future)
- [ ] DNS propagation verified (5-10 min wait)
  ```bash
  dig api.incomefortress.com +short
  # Returns: [droplet IP]
  ```

#### Server Setup
- [ ] System updated: `apt update && apt upgrade -y`
- [ ] Timezone set to EST: `timedatectl set-timezone America/New_York`
- [ ] UFW firewall configured
  - [ ] SSH allowed: `ufw allow 22/tcp`
  - [ ] HTTP allowed: `ufw allow 80/tcp`
  - [ ] HTTPS allowed: `ufw allow 443/tcp`
  - [ ] Firewall enabled: `ufw enable`
- [ ] Swap file created (2GB): `/swapfile`
- [ ] Swap verified: `free -h` shows swap

#### Software Installation
- [ ] Docker installed: `docker --version` shows 24.0+
- [ ] Docker service started and enabled
- [ ] Docker Compose installed: `docker-compose --version` shows 2.0+
- [ ] Git installed: `git --version`
- [ ] Repository cloned to `/opt/Agentic/income-platform`

---

### 1.2 Configuration

#### Environment Variables (.env)
- [ ] `.env` file created from `.env.production.example`
- [ ] No CHANGE_ME placeholders remain
  ```bash
  grep -i "CHANGE_ME" .env
  # Returns: nothing
  ```
- [ ] Database connection string configured:
  - [ ] DB_HOST correct
  - [ ] DB_PORT correct (25060)
  - [ ] DB_USER correct
  - [ ] DB_PASSWORD set
  - [ ] DB_NAME correct
  - [ ] DATABASE_URL includes `?sslmode=require`
- [ ] Redis connection configured:
  - [ ] REDIS_HOST correct
  - [ ] REDIS_PORT correct (25061)
  - [ ] REDIS_PASSWORD set
  - [ ] REDIS_URL uses `rediss://` (SSL)
- [ ] Secrets generated:
  - [ ] SECRET_KEY: `openssl rand -hex 32`
  - [ ] JWT_SECRET_KEY: `openssl rand -hex 32`
  - [ ] N8N_ENCRYPTION_KEY: `openssl rand -hex 32`
- [ ] API keys configured:
  - [ ] ANTHROPIC_API_KEY set
  - [ ] ALPHA_VANTAGE_API_KEY set (optional)
  - [ ] FINANCIAL_MODELING_PREP_API_KEY set (optional)
- [ ] Spaces configuration:
  - [ ] SPACES_REGION correct (nyc3)
  - [ ] SPACES_BUCKET correct
  - [ ] SPACES_ACCESS_KEY set
  - [ ] SPACES_SECRET_KEY set
- [ ] Domain configuration:
  - [ ] ALLOWED_ORIGINS correct
  - [ ] N8N_HOST correct
- [ ] n8n credentials:
  - [ ] N8N_USER set
  - [ ] N8N_PASSWORD set (strong password)
- [ ] Email configuration (optional):
  - [ ] SENDGRID_API_KEY set
  - [ ] FROM_EMAIL configured

#### Connection Tests
- [ ] PostgreSQL connection works:
  ```bash
  psql "$DATABASE_URL"
  # Successfully connects
  ```
- [ ] Redis connection works:
  ```bash
  redis-cli -u "$REDIS_URL" ping
  # Returns: PONG
  ```
- [ ] Spaces upload test works:
  ```bash
  s3cmd put test.txt s3://income-platform-storage/
  ```

---

### 1.3 Scripts & Permissions

#### Scripts Executable
- [ ] All scripts executable:
  ```bash
  chmod +x scripts/*.sh
  ls -l scripts/
  # Shows: -rwxr-xr-x
  ```
- [ ] Script inventory complete:
  - [ ] `deploy.sh` exists
  - [ ] `init_ssl.sh` exists
  - [ ] `deploy_update.sh` exists
  - [ ] `backup_database.sh` exists
  - [ ] `restore_database.sh` exists

---

## PHASE 2: Deployment

### 2.1 SSL Certificates

- [ ] SSL initialization started: `./scripts/init_ssl.sh`
- [ ] Dummy certificates created successfully
- [ ] nginx started successfully
- [ ] Let's Encrypt certificates obtained
- [ ] Certificates verified:
  ```bash
  ls -la certbot/conf/live/
  # Shows: api.incomefortress.com/, n8n.incomefortress.com/
  ```
- [ ] HTTPS redirect works:
  ```bash
  curl -I http://api.incomefortress.com
  # Returns: 301 redirect to https://
  ```
- [ ] SSL grade verified (optional):
  - Visit: https://www.ssllabs.com/ssltest/
  - Grade: A or better

---

### 2.2 Database Migration

- [ ] Redis started: `docker-compose up -d redis`
- [ ] Migration executed:
  ```bash
  docker-compose run --rm api alembic upgrade head
  ```
- [ ] Migration output shows success
- [ ] Schemas verified:
  ```bash
  psql "$DATABASE_URL" -c "\dn"
  # Shows: platform_shared
  ```
- [ ] Tables created in platform_shared:
  - [ ] securities
  - [ ] features_historical
  - [ ] stock_scores
  - [ ] analyst_consensus_cache
  - [ ] (verify others as needed)

---

### 2.3 Container Deployment

#### Build Phase
- [ ] Images built: `docker-compose build --parallel`
- [ ] Build completed without errors
- [ ] Images verified:
  ```bash
  docker images | grep income-platform
  # Shows: income-platform_api, etc.
  ```

#### Startup Sequence
- [ ] Core services started:
  - [ ] Redis: `docker-compose up -d redis`
  - [ ] Wait 5 seconds
  - [ ] API: `docker-compose up -d api`
  - [ ] n8n: `docker-compose up -d n8n`
  - [ ] Wait 10 seconds
  - [ ] Workers: `docker-compose up -d celery-worker-scoring celery-worker-portfolio celery-worker-monitoring`
  - [ ] Beat: `docker-compose up -d celery-beat`
  - [ ] Wait 5 seconds
  - [ ] Nginx: `docker-compose up -d nginx`

#### Container Status
- [ ] All containers running:
  ```bash
  docker-compose ps
  ```
  Expected state for each:
  - [ ] income-api: Up (healthy)
  - [ ] income-n8n: Up (healthy)
  - [ ] income-worker-scoring: Up
  - [ ] income-worker-portfolio: Up
  - [ ] income-worker-monitoring: Up
  - [ ] income-beat: Up
  - [ ] income-redis: Up (healthy)
  - [ ] income-nginx: Up (healthy)

---

### 2.4 Initial Tenant Creation

- [ ] Tenant created:
  ```bash
  docker-compose exec api python scripts/create_tenant.py \
    --tenant-id 001 \
    --name "Demo Tenant" \
    --email "admin@incomefortress.com"
  ```
- [ ] Tenant schema verified:
  ```bash
  psql "$DATABASE_URL" -c "\dn"
  # Shows: tenant_001
  ```
- [ ] Default preferences inserted:
  ```bash
  psql "$DATABASE_URL" -c "SELECT COUNT(*) FROM tenant_001.preferences;"
  # Returns: >0
  ```

---

## PHASE 3: Post-Deployment Verification

### 3.1 Health Checks

#### API Health
- [ ] Basic health check:
  ```bash
  curl https://api.incomefortress.com/health
  # Returns: {"status":"healthy"}
  ```
- [ ] Detailed health check:
  ```bash
  curl https://api.incomefortress.com/health/detailed
  # Returns: {"status":"healthy","checks":{"database":true,"redis":true,"celery":true}}
  ```
- [ ] Metrics endpoint accessible:
  ```bash
  curl http://localhost:8000/metrics
  # Returns: Prometheus metrics
  ```

#### n8n Web Interface
- [ ] n8n accessible: `https://n8n.incomefortress.com`
- [ ] Login works with N8N_USER / N8N_PASSWORD
- [ ] Dashboard loads successfully

#### Container Health
- [ ] All health checks passing:
  ```bash
  docker ps --format "table {{.Names}}\t{{.Status}}"
  # All show: Up X minutes (healthy)
  ```

---

### 3.2 Functional Testing

#### Authentication
- [ ] User registration works:
  ```bash
  curl -X POST https://api.incomefortress.com/auth/register \
    -H "Content-Type: application/json" \
    -d '{"email":"test@example.com","password":"Test123!","full_name":"Test User"}'
  # Returns: 201 Created
  ```
- [ ] User login works:
  ```bash
  curl -X POST https://api.incomefortress.com/auth/login \
    -H "Content-Type: application/json" \
    -d '{"email":"test@example.com","password":"Test123!"}'
  # Returns: {"access_token":"...","refresh_token":"..."}
  ```
- [ ] Token saved for further testing: `TOKEN="..."`

#### Asset Scoring
- [ ] Scoring endpoint works:
  ```bash
  curl https://api.incomefortress.com/stocks/ARCC/score \
    -H "Authorization: Bearer $TOKEN"
  # Returns: {"symbol":"ARCC","overall_score":75.2,...}
  ```
- [ ] Score components present in response
- [ ] Decision field populated

#### Celery Workers
- [ ] Workers responding:
  ```bash
  docker-compose exec api celery -A app.celery_app inspect stats
  # Returns: Statistics for all 3 workers
  ```
- [ ] Scheduled tasks configured:
  ```bash
  docker-compose exec api celery -A app.celery_app inspect scheduled
  # Returns: Scheduled tasks list
  ```

---

### 3.3 Performance Verification

#### Response Times
- [ ] API health check <100ms:
  ```bash
  time curl https://api.incomefortress.com/health
  # Shows: real 0m0.XXXs (where XXX < 100)
  ```
- [ ] Scoring request <3s:
  ```bash
  time curl https://api.incomefortress.com/stocks/ARCC/score -H "Authorization: Bearer $TOKEN"
  # Shows: real 0m2.XXXs (where XXX < 3)
  ```

#### Resource Usage
- [ ] CPU usage acceptable:
  ```bash
  top
  # Docker processes <80% CPU
  ```
- [ ] Memory usage acceptable:
  ```bash
  free -h
  # Used <80% of available
  ```
- [ ] Disk usage acceptable:
  ```bash
  df -h
  # Used <80% on all partitions
  ```

---

### 3.4 Monitoring & Logging

#### Prometheus Metrics
- [ ] Metrics collection working:
  ```bash
  curl http://localhost:8000/metrics | grep http_requests_total
  # Returns: Metric data
  ```
- [ ] No error metrics:
  ```bash
  curl http://localhost:8000/metrics | grep http_requests_total | grep '500'
  # Returns: 0 or low count
  ```

#### Logs
- [ ] Logs being written:
  ```bash
  ls -lh logs/
  # Shows: app.log, error.log
  ```
- [ ] No critical errors in logs:
  ```bash
  grep -i "critical\|fatal" logs/*.log
  # Returns: nothing or expected entries
  ```
- [ ] JSON log format verified:
  ```bash
  tail -n 1 logs/app.log | jq .
  # Parses successfully
  ```

---

### 3.5 Backup Verification

#### Manual Backup Test
- [ ] Backup script executed: `./scripts/backup_database.sh`
- [ ] Backup file created:
  ```bash
  ls -lh backups/database/
  # Shows: income_platform_YYYYMMDD_HHMMSS.sql.gz
  ```
- [ ] Backup uploaded to Spaces:
  ```bash
  s3cmd ls s3://income-platform-storage/backups/database/
  # Shows: backup file
  ```
- [ ] Backup integrity verified:
  ```bash
  gzip -t backups/database/income_platform_*.sql.gz
  # Returns: no errors
  ```

#### Automated Backup
- [ ] Cron job configured (optional for Phase 1):
  ```bash
  crontab -l | grep backup_database
  # Shows: 0 2 * * * /opt/income-platform/scripts/backup_database.sh
  ```

---

## PHASE 4: Go-Live Readiness

### 4.1 Security Review

#### SSL/TLS
- [ ] All domains use HTTPS
- [ ] HTTP redirects to HTTPS
- [ ] SSL grade A or better (ssllabs.com)
- [ ] HSTS header present:
  ```bash
  curl -I https://api.incomefortress.com | grep Strict-Transport
  # Shows: Strict-Transport-Security header
  ```

#### Firewall
- [ ] Only required ports open:
  ```bash
  ufw status
  # Shows: 22, 80, 443 allowed
  ```
- [ ] PostgreSQL not publicly accessible (only whitelisted IPs)
- [ ] Redis not publicly accessible (only whitelisted IPs)

#### Secrets
- [ ] No secrets in git:
  ```bash
  git log --all -S "sk-ant-api" --oneline
  # Returns: nothing
  ```
- [ ] .env file has proper permissions:
  ```bash
  ls -l .env
  # Shows: -rw------- (600)
  ```

#### Rate Limiting
- [ ] Rate limiting active:
  ```bash
  # Make 20 rapid requests
  for i in {1..20}; do curl https://api.incomefortress.com/health; done
  # Eventually returns: 429 Too Many Requests
  ```

---

### 4.2 Documentation Review

- [ ] README.md present and accurate
- [ ] Deployment guide reviewed
- [ ] Operational runbook reviewed
- [ ] Emergency procedures documented
- [ ] Contact information current

---

### 4.3 Runbook Verification

- [ ] Team has access to runbooks
- [ ] Common operations tested:
  - [ ] Start services
  - [ ] Stop services
  - [ ] Restart specific service
  - [ ] View logs
  - [ ] Execute commands in containers
- [ ] Emergency procedures reviewed with team
- [ ] On-call rotation established (if applicable)

---

### 4.4 Final Pre-Launch Checklist

#### Configuration
- [ ] All environment variables verified
- [ ] Correct production values (no test/dev values)
- [ ] DEBUG=false confirmed
- [ ] ENVIRONMENT=production confirmed

#### Monitoring
- [ ] Prometheus accessible
- [ ] Grafana configured (optional)
- [ ] Alerts configured
- [ ] On-call notifications working

#### Communication
- [ ] Team notified of go-live time
- [ ] Maintenance window communicated (if applicable)
- [ ] Rollback plan reviewed
- [ ] Incident response plan reviewed

---

## PHASE 5: Post-Launch Monitoring

### First Hour

- [ ] **T+5 min:** Health check
  ```bash
  curl https://api.incomefortress.com/health
  ```
- [ ] **T+5 min:** Check error rates
  ```bash
  docker-compose logs --since 5m | grep -i error
  ```
- [ ] **T+10 min:** Verify workers processing
  ```bash
  docker-compose exec api celery -A app.celery_app inspect active
  ```
- [ ] **T+15 min:** Check resource usage
  ```bash
  docker stats --no-stream
  ```
- [ ] **T+30 min:** Review metrics
  ```bash
  curl http://localhost:8000/metrics
  ```
- [ ] **T+60 min:** Full health check
  ```bash
  curl https://api.incomefortress.com/health/detailed
  ```

### First 24 Hours

- [ ] **Every 4 hours:** Review logs for errors
- [ ] **Every 6 hours:** Check backup completion
- [ ] **Every 12 hours:** Review resource usage
- [ ] **End of day:** Performance review
  - Average response time
  - Error rate
  - Resource utilization

### First Week

- [ ] **Daily:** Morning checklist (from operational runbook)
- [ ] **Daily:** Evening checklist
- [ ] **Day 3:** Review week-to-date metrics
- [ ] **Day 7:** First weekly maintenance
- [ ] **Day 7:** Post-launch retrospective

---

## Rollback Procedure

If critical issues arise, follow this rollback procedure:

### Quick Rollback (Service Issues)

1. **Stop current services**
   ```bash
   docker-compose down
   ```

2. **Checkout previous version**
   ```bash
   git log --oneline -10
   # Identify last known good commit
   git checkout [commit_hash]
   ```

3. **Rebuild and start**
   ```bash
   docker-compose build
   docker-compose up -d
   ```

4. **Verify**
   ```bash
   curl https://api.incomefortress.com/health
   ```

### Full Rollback (Database Issues)

1. **Stop all services**
   ```bash
   docker-compose down
   ```

2. **Restore database**
   ```bash
   ./scripts/restore_database.sh [pre_deployment_backup]
   ```

3. **Rollback code**
   ```bash
   git checkout [previous_commit]
   ```

4. **Rebuild and start**
   ```bash
   docker-compose build
   docker-compose up -d
   ```

5. **Verify restoration**
   ```bash
   psql "$DATABASE_URL" -c "SELECT COUNT(*) FROM platform_shared.securities;"
   curl https://api.incomefortress.com/health
   ```

---

## Sign-Off

### Pre-Deployment Sign-Off

- [ ] Infrastructure team: _________________ Date: _______
- [ ] Development team: _________________ Date: _______
- [ ] Security review: _________________ Date: _______

### Deployment Sign-Off

- [ ] Deployment executed by: _________________ Date: _______
- [ ] Verification completed by: _________________ Date: _______

### Go-Live Approval

- [ ] Technical lead: _________________ Date: _______
- [ ] Product owner: _________________ Date: _______

---

**Checklist Version:** 1.0.0  
**Last Updated:** February 2, 2026  
**Maintained By:** Alberto DBP
