# Deployment Checklist - Income Fortress Platform

**Version:** 1.0.0  
**Last Updated:** February 3, 2026  
**Environment:** Production  
**Deployment Type:** Initial Production Deployment

---

## Pre-Deployment Phase

### Infrastructure Verification

- [ ] **DigitalOcean Account Setup**
  - Account created and payment method verified
  - SSH keys configured and uploaded
  - Access tokens generated for API access
  
- [ ] **Droplet Configuration**
  - Droplet created: 8GB RAM, 4 vCPUs, 160GB SSD ($60/mo)
  - Ubuntu 24.04 LTS installed
  - Firewall configured (ports 80, 443, 22 only)
  - Root login disabled, sudo user created

- [ ] **Managed PostgreSQL**
  - Database cluster created ($25/mo plan minimum)
  - Connection pooling enabled (PgBouncer)
  - Automatic backups configured (daily, 7-day retention)
  - Connection string secured in environment variables

- [ ] **Managed Redis**
  - Redis cluster created ($15/mo plan minimum)
  - Eviction policy configured (allkeys-lru)
  - Maxmemory limit set appropriately
  - TLS encryption enabled

- [ ] **DNS Configuration**
  - Domain purchased/transferred (incomefortress.com)
  - A records pointing to droplet IP:
    - api.incomefortress.com → Droplet IP
    - n8n.incomefortress.com → Droplet IP (internal only)
  - SSL/TLS certificates obtained (Let's Encrypt)

### Security Hardening

- [ ] **SSL/TLS Setup**
  - Certificates obtained via Certbot
  - Auto-renewal configured (cron job)
  - A+ grade on SSL Labs test
  - HSTS enabled with 1-year max-age

- [ ] **Firewall Rules**
  - UFW enabled and configured
  - Only necessary ports open (80, 443, 22)
  - SSH rate limiting enabled
  - Fail2Ban installed and configured

- [ ] **Secret Management**
  - All secrets stored in `.env` file (not in repo)
  - `.env` file permissions set to 600
  - Backup of secrets stored securely (password manager)
  - API keys rotated before production

- [ ] **GDPR Compliance**
  - Privacy policy published
  - Data retention policies configured
  - User consent mechanisms implemented
  - Data export functionality available

### Code Preparation

- [ ] **Version Control**
  - All code committed to main branch
  - Git tag created for deployment (v1.0.0)
  - Release notes prepared
  - Deployment branch protected

- [ ] **Dependencies**
  - All Python packages listed in requirements.txt
  - Package versions pinned (no wildcards)
  - Security vulnerabilities checked (pip-audit)
  - Docker images built and tested locally

- [ ] **Configuration Files**
  - docker-compose.yml reviewed
  - nginx.conf validated
  - celery-config.py confirmed
  - Environment variables documented

### Pre-Deployment Testing

- [ ] **Local Testing Complete**
  - All unit tests passing (pytest)
  - Integration tests passing
  - Load tests performed (100 concurrent users)
  - Memory leak tests completed

- [ ] **Staging Environment**
  - Staging droplet deployed successfully
  - All services running on staging
  - End-to-end tests passing on staging
  - Performance benchmarks met on staging

### Data Migration

- [ ] **Database Schema**
  - All 97 tables created via migrations
  - Indexes created and optimized
  - Foreign key constraints validated
  - Initial seed data loaded (if applicable)

- [ ] **Data Migration Scripts**
  - Migration scripts tested on staging
  - Rollback scripts prepared
  - Data validation queries ready
  - Backup plan confirmed

### Third-Party Integrations

- [ ] **Anthropic API**
  - API key obtained (production tier)
  - Usage limits understood ($40-80/mo budget)
  - Rate limiting configured
  - Error handling tested

- [ ] **Market Data APIs**
  - Alpha Vantage API key configured
  - yfinance fallback configured
  - API quotas verified
  - Caching strategy confirmed

- [ ] **External APIs** (Dividend, etc.)
  - All API keys obtained
  - Authentication tested
  - Rate limits documented
  - Failover strategies defined

### Monitoring Setup

- [ ] **Prometheus**
  - Prometheus configured to scrape metrics
  - 15 alert rules configured
  - Retention period set (15 days)
  - Storage provisioned

- [ ] **Grafana Dashboards**
  - System dashboard created
  - Application dashboard created
  - Alert notifications configured (email/Slack)
  - Access credentials secured

- [ ] **Logging**
  - Centralized logging configured
  - Log rotation enabled (7-day retention)
  - Log levels appropriate (INFO in prod)
  - Sensitive data masked in logs

### Team Readiness

- [ ] **Documentation Review**
  - README.md reviewed by all team members
  - Operational runbook reviewed
  - Disaster recovery plan reviewed
  - Contact list updated

- [ ] **Permissions & Access**
  - All team members have necessary access
  - SSH keys distributed
  - Database credentials shared securely
  - On-call rotation established

- [ ] **Communication Plan**
  - Deployment announcement prepared
  - Status page ready (if applicable)
  - Rollback decision tree documented
  - Escalation path defined

---

## Deployment Phase

### Pre-Deployment Snapshot

- [ ] **Backups Created**
  - Database backup created
  - Code repository tagged
  - Configuration files backed up
  - Backup verification completed

### Service Deployment

- [ ] **1. Server Preparation**
  ```bash
  # SSH into droplet
  ssh deployer@<droplet-ip>
  
  # Update system
  sudo apt update && sudo apt upgrade -y
  
  # Install Docker
  curl -fsSL https://get.docker.com -o get-docker.sh
  sudo sh get-docker.sh
  
  # Install Docker Compose
  sudo apt install docker-compose-plugin -y
  
  # Verify installations
  docker --version
  docker compose version
  ```
  - [ ] System updated
  - [ ] Docker installed (v24.0+)
  - [ ] Docker Compose installed (v2.20+)
  - [ ] Deployer user added to docker group

- [ ] **2. Code Deployment**
  ```bash
  # Clone repository
  git clone https://github.com/AlbertoDBP/Agentic.git
  cd Agentic/income-platform
  
  # Checkout production tag
  git checkout v1.0.0
  
  # Verify tag
  git describe --tags
  ```
  - [ ] Repository cloned
  - [ ] Production tag checked out
  - [ ] Code integrity verified

- [ ] **3. Environment Configuration**
  ```bash
  # Copy .env template
  cp .env.example .env
  
  # Edit .env with production values
  nano .env
  
  # Verify .env file
  cat .env | grep -v "^#" | grep -v "^$"
  
  # Set permissions
  chmod 600 .env
  ```
  - [ ] .env file created
  - [ ] All required variables set
  - [ ] Sensitive values secured
  - [ ] File permissions correct (600)

- [ ] **4. Database Initialization**
  ```bash
  # Run migrations
  docker compose run --rm api python manage.py migrate
  
  # Create superuser
  docker compose run --rm api python manage.py createsuperuser
  
  # Verify schema
  docker compose run --rm api python manage.py showmigrations
  ```
  - [ ] All migrations applied
  - [ ] Superuser created
  - [ ] Schema validated

- [ ] **5. Service Startup**
  ```bash
  # Build and start all services
  docker compose up -d --build
  
  # Verify all services running
  docker compose ps
  
  # Check logs for errors
  docker compose logs -f --tail=100
  ```
  - [ ] All 8 containers started
  - [ ] No errors in startup logs
  - [ ] Services marked "healthy"

- [ ] **6. Nginx & SSL Configuration**
  ```bash
  # Obtain SSL certificates
  sudo certbot --nginx -d api.incomefortress.com
  
  # Test Nginx config
  sudo nginx -t
  
  # Reload Nginx
  sudo systemctl reload nginx
  
  # Verify SSL grade
  # Visit: https://www.ssllabs.com/ssltest/
  ```
  - [ ] SSL certificates obtained
  - [ ] Nginx config valid
  - [ ] A+ SSL grade achieved
  - [ ] Auto-renewal configured

### Health Checks

- [ ] **API Health**
  ```bash
  curl https://api.incomefortress.com/health
  # Expected: {"status": "healthy", "timestamp": "..."}
  
  curl https://api.incomefortress.com/health/detailed
  # Expected: All services "healthy"
  ```
  - [ ] API responding
  - [ ] All health checks passing

- [ ] **Database Connectivity**
  ```bash
  docker compose exec api python -c "from django.db import connection; connection.ensure_connection(); print('DB Connected')"
  ```
  - [ ] Database connection established
  - [ ] Query execution successful

- [ ] **Redis Connectivity**
  ```bash
  docker compose exec api python -c "from django.core.cache import cache; cache.set('test', 'ok'); print(cache.get('test'))"
  ```
  - [ ] Redis connection established
  - [ ] Cache operations working

- [ ] **Celery Workers**
  ```bash
  docker compose exec celery_default celery -A income_platform inspect active
  docker compose exec celery_scoring celery -A income_platform inspect active
  docker compose exec celery_beats celery -A income_platform inspect scheduled
  ```
  - [ ] Default worker active
  - [ ] Scoring worker active
  - [ ] Beat scheduler running
  - [ ] Scheduled tasks visible

### Functional Testing

- [ ] **API Endpoints**
  - [ ] POST /api/v1/auth/login (authentication works)
  - [ ] GET /api/v1/tenants (multi-tenancy works)
  - [ ] POST /api/v1/portfolios (portfolio creation works)
  - [ ] GET /api/v1/scores/ETF (income scoring works)
  - [ ] POST /api/v1/proposals (proposal workflow works)

- [ ] **Agent Workflows**
  - [ ] Agent 1: Market data sync successful
  - [ ] Agent 3: Income scoring calculation successful
  - [ ] Agent 9: Tax efficiency analysis successful
  - [ ] Agent 17: Rebalancing proposal generation successful

- [ ] **User Workflows**
  - [ ] User registration
  - [ ] User login
  - [ ] Portfolio creation
  - [ ] Proposal review/approval
  - [ ] DRIP execution

### Performance Validation

- [ ] **Response Times**
  ```bash
  # Test API response time
  time curl https://api.incomefortress.com/health
  # Expected: <500ms
  
  # Test scoring latency
  time curl -X POST https://api.incomefortress.com/api/v1/scores/VYM
  # Expected: <3s
  ```
  - [ ] API p95 latency <500ms
  - [ ] Scoring latency <3s
  - [ ] Database queries optimized

- [ ] **Resource Utilization**
  ```bash
  # Check container resources
  docker stats
  
  # Check system resources
  free -h
  df -h
  ```
  - [ ] Memory usage <80%
  - [ ] CPU usage <70% (idle)
  - [ ] Disk usage <60%

### Security Validation

- [ ] **SSL/TLS Grade**
  - [ ] A+ grade on SSL Labs
  - [ ] HSTS enabled
  - [ ] Perfect Forward Secrecy enabled

- [ ] **Vulnerability Scan**
  ```bash
  # Run security audit
  pip-audit
  
  # Check for exposed secrets
  trufflehog filesystem /path/to/repo
  ```
  - [ ] No critical vulnerabilities
  - [ ] No exposed secrets

- [ ] **Firewall Verification**
  ```bash
  sudo ufw status
  ```
  - [ ] Only 80, 443, 22 open
  - [ ] Rate limiting active

---

## Post-Deployment Phase

### Monitoring Activation

- [ ] **Prometheus Alerts**
  ```bash
  # Verify alert rules loaded
  curl http://localhost:9090/api/v1/rules
  
  # Test alert firing
  # (trigger a test alert)
  ```
  - [ ] 15 alert rules active
  - [ ] Alert notifications working
  - [ ] PagerDuty integration tested (if applicable)

- [ ] **Grafana Dashboards**
  - [ ] System dashboard displaying metrics
  - [ ] Application dashboard displaying metrics
  - [ ] Alert history visible
  - [ ] Team members have access

### Operational Readiness

- [ ] **Backup Verification**
  ```bash
  # Trigger manual backup
  ./scripts/backup_database.sh
  
  # Verify backup created
  ls -lh backups/
  
  # Test restore on staging
  ./scripts/restore_database.sh backups/latest.sql
  ```
  - [ ] Automated backups working
  - [ ] Manual backup successful
  - [ ] Restore tested on staging

- [ ] **Disaster Recovery Test**
  - [ ] RTO target confirmed (4 hours)
  - [ ] RPO target confirmed (1 hour)
  - [ ] Recovery procedures validated
  - [ ] Team trained on procedures

### User Acceptance

- [ ] **Beta User Testing**
  - [ ] 5 beta users onboarded
  - [ ] All user workflows tested by beta users
  - [ ] Feedback collected
  - [ ] Critical issues resolved

- [ ] **Performance Under Load**
  ```bash
  # Run load test (100 concurrent users)
  ab -n 1000 -c 100 https://api.incomefortress.com/health
  ```
  - [ ] System stable under load
  - [ ] Response times acceptable
  - [ ] No errors during load test

### Documentation Finalization

- [ ] **User Documentation**
  - [ ] User guide published
  - [ ] API documentation live (/docs endpoint)
  - [ ] FAQ created
  - [ ] Support contact information visible

- [ ] **Team Documentation**
  - [ ] Operational runbook finalized
  - [ ] On-call procedures documented
  - [ ] Escalation path defined
  - [ ] Team training completed

### Go-Live Preparation

- [ ] **Communication**
  - [ ] Internal team notified
  - [ ] Beta users notified (if expanding)
  - [ ] Status page updated
  - [ ] Support channels ready

- [ ] **Rollback Plan Ready**
  - [ ] Previous version tagged in Git
  - [ ] Database backup confirmed
  - [ ] Rollback procedure tested
  - [ ] Rollback decision criteria defined

---

## Go-Live Execution

### Final Checks (T-1 hour)

- [ ] **All systems green**
  ```bash
  curl https://api.incomefortress.com/health/detailed
  ```
  - [ ] All health checks passing
  - [ ] No errors in logs (last 1 hour)
  - [ ] Resource utilization normal

- [ ] **Team Readiness**
  - [ ] All team members online
  - [ ] Communication channels open
  - [ ] Monitoring dashboards open
  - [ ] On-call engineer identified

### Go-Live (T=0)

- [ ] **Enable Production Traffic**
  - [ ] DNS cutover completed (if applicable)
  - [ ] Load balancer updated (if applicable)
  - [ ] Traffic routing to production

- [ ] **Immediate Monitoring**
  - [ ] Watch logs in real-time
  - [ ] Monitor dashboards continuously
  - [ ] Track error rates
  - [ ] Verify first transactions

### Post-Go-Live Monitoring (First 4 Hours)

- [ ] **T+15 minutes**
  - [ ] Error rate <1%
  - [ ] Response times normal
  - [ ] No critical alerts

- [ ] **T+1 hour**
  - [ ] User transactions successful
  - [ ] Background jobs processing
  - [ ] Database performance stable

- [ ] **T+4 hours**
  - [ ] All systems stable
  - [ ] Performance within SLAs
  - [ ] No critical issues
  - [ ] Team can stand down to normal operations

---

## Rollback Procedures

### When to Rollback

**Immediate Rollback Triggers:**
- [ ] Error rate >5%
- [ ] Complete service outage >15 minutes
- [ ] Data corruption detected
- [ ] Security breach identified
- [ ] Critical functionality broken

### Rollback Steps

```bash
# 1. Stop all services
docker compose down

# 2. Restore database from last known good backup
./scripts/restore_database.sh backups/pre-deployment.sql

# 3. Checkout previous code version
git checkout v0.9.0

# 4. Rebuild and restart
docker compose build
docker compose up -d

# 5. Verify health
curl https://api.incomefortress.com/health
```

- [ ] Services stopped
- [ ] Database restored
- [ ] Previous version deployed
- [ ] Health checks passing
- [ ] Users notified of rollback

---

## Sign-Off

### Deployment Completion

**Deployment Completed By:** ___________________________  
**Date/Time:** ___________________________  
**Environment:** Production  
**Version Deployed:** v1.0.0

**Approvals:**

**Technical Lead:** ___________________________  
**Security Officer:** ___________________________  
**Operations Manager:** ___________________________

**Post-Deployment Notes:**

_________________________________________________________________
_________________________________________________________________
_________________________________________________________________

---

## Appendix: Quick Reference Commands

### Service Management
```bash
# View all containers
docker compose ps

# View logs
docker compose logs -f [service-name]

# Restart service
docker compose restart [service-name]

# Rebuild and restart
docker compose up -d --no-deps --build [service-name]
```

### Health Checks
```bash
# API health
curl https://api.incomefortress.com/health

# Detailed health
curl https://api.incomefortress.com/health/detailed

# Metrics
curl http://localhost:8000/metrics
```

### Database Operations
```bash
# Backup
./scripts/backup_database.sh

# Restore
./scripts/restore_database.sh [backup-file]

# Connect
psql "$DATABASE_URL"
```

### Monitoring
```bash
# Container stats
docker stats

# System resources
free -h
df -h

# Logs
tail -f logs/app.log
```

---

**Checklist Version:** 1.0.0  
**Last Updated:** February 3, 2026  
**Next Review:** After each major deployment
