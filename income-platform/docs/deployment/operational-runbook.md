# Operational Runbook - Income Fortress Platform

**Version:** 1.0.0  
**Last Updated:** February 2, 2026  
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
docker-compose ps

# Expected: All services "Up (healthy)"

# 2. Check API health
curl https://api.incomefortress.com/health

# Expected: {"status":"healthy"}

# 3. Review overnight logs for errors
docker-compose logs --since 12h | grep -i error

# 4. Check Celery workers
docker-compose exec api celery -A app.celery_app inspect active

# Expected: All workers responding

# 5. Verify database connections
docker-compose exec api python -c "from app.database import db; print('OK' if db else 'FAIL')"

# 6. Check Redis
docker-compose exec redis redis-cli ping
# Expected: PONG

# 7. Review Prometheus alerts
curl -s http://localhost:9090/api/v1/alerts | jq '.data.alerts[] | select(.state=="firing")'

# Expected: [] (no firing alerts)
```

### Evening Checklist (5 PM EST)

```bash
# 1. Check backup completed
ls -lh /opt/income-platform/backups/database/ | tail -n 1

# Expected: Today's backup file

# 2. Review daily metrics
curl http://localhost:8000/metrics | grep http_requests_total

# 3. Check disk space
df -h

# Expected: <80% usage

# 4. Review circuit breaker triggers
docker-compose exec api python scripts/circuit_breaker_summary.py

# 5. Plan tomorrow's maintenance (if any)
```

---

## Common Tasks

### Start Services

```bash
# Start all services
cd /opt/income-platform
docker-compose up -d

# Verify startup
docker-compose ps
docker-compose logs -f --tail=20
```

**Expected Startup Time:** 30-60 seconds

### Stop Services

```bash
# Graceful stop (30 second timeout)
docker-compose stop

# Force stop (immediate)
docker-compose down
```

⚠️ **Warning:** Use `down` only for maintenance, not production stops.

### Restart Specific Service

```bash
# Restart API
docker-compose restart api

# Restart worker
docker-compose restart celery-worker-scoring

# Restart all workers
docker-compose restart celery-worker-scoring celery-worker-portfolio celery-worker-monitoring
```

### View Logs

```bash
# All services (live tail)
docker-compose logs -f

# Specific service
docker-compose logs -f api

# Last 100 lines
docker-compose logs --tail=100 api

# Since timestamp
docker-compose logs --since 2026-02-02T10:00:00 api

# Follow errors only
docker-compose logs -f api 2>&1 | grep -i error
```

### Execute Commands in Container

```bash
# Python shell
docker-compose exec api python

# Django/Alembic shell
docker-compose exec api python manage.py shell

# Run script
docker-compose exec api python scripts/create_tenant.py --tenant-id 002

# Bash shell
docker-compose exec api /bin/bash
```

### Check Service Health

```bash
# API health endpoint
curl https://api.incomefortress.com/health

# Detailed health
curl https://api.incomefortress.com/health/detailed

# Individual containers
docker-compose exec api curl localhost:8000/health
docker-compose exec n8n wget -qO- localhost:5678/healthz
docker-compose exec redis redis-cli ping

# Docker health status
docker inspect income-api | jq '.[0].State.Health.Status'
```

### Database Operations

```bash
# Connect to PostgreSQL
psql "$DATABASE_URL"

# Run query
psql "$DATABASE_URL" -c "SELECT COUNT(*) FROM platform_shared.securities;"

# List schemas
psql "$DATABASE_URL" -c "\dn"

# Check connections
psql "$DATABASE_URL" -c "SELECT count(*) FROM pg_stat_activity;"

# Backup database
./scripts/backup_database.sh

# Restore database
./scripts/restore_database.sh [backup_file]
```

### Celery Operations

```bash
# Check worker status
docker-compose exec api celery -A app.celery_app inspect active

# List scheduled tasks
docker-compose exec api celery -A app.celery_app inspect scheduled

# Purge queue (⚠️ CAREFUL)
docker-compose exec api celery -A app.celery_app purge

# Worker statistics
docker-compose exec api celery -A app.celery_app inspect stats

# Registered tasks
docker-compose exec api celery -A app.celery_app inspect registered
```

### Update Deployment

```bash
# Run update script
./scripts/deploy_update.sh

# Manual update process:
# 1. Backup database
./scripts/backup_database.sh

# 2. Pull latest code
git pull origin main

# 3. Rebuild images
docker-compose build

# 4. Run migrations
docker-compose run --rm api alembic upgrade head

# 5. Restart services (zero-downtime)
docker-compose up -d --no-deps --build api
sleep 10
docker-compose up -d --no-deps --build celery-worker-scoring celery-worker-portfolio celery-worker-monitoring

# 6. Verify
curl https://api.incomefortress.com/health
```

---

## Troubleshooting

### Issue: API Not Responding

**Symptoms:**
```bash
curl https://api.incomefortress.com/health
# Returns: Connection refused or timeout
```

**Diagnosis:**
```bash
# 1. Check container status
docker-compose ps api
# If not "Up (healthy)", proceed

# 2. Check logs
docker-compose logs --tail=100 api

# 3. Check port binding
netstat -tulpn | grep 8000

# 4. Check nginx
docker-compose ps nginx
docker-compose logs --tail=50 nginx
```

**Solutions:**

**Solution 1: Container crashed**
```bash
# Restart API
docker-compose restart api

# If fails to start, check logs for errors
docker-compose logs api
```

**Solution 2: Port conflict**
```bash
# Check what's using port 8000
lsof -i :8000

# Kill conflicting process or change port
```

**Solution 3: Out of memory**
```bash
# Check memory
free -h

# If low, restart services
docker-compose restart
```

**Solution 4: Configuration error**
```bash
# Verify .env file
grep -i "CHANGE_ME" .env
# Should return nothing

# Test configuration
docker-compose config
```

---

### Issue: Database Connection Fails

**Symptoms:**
```
psycopg2.OperationalError: could not connect to server
```

**Diagnosis:**
```bash
# 1. Test connection
psql "$DATABASE_URL"

# 2. Check database status (DigitalOcean dashboard)

# 3. Verify IP whitelist
# Go to: DigitalOcean > Databases > Trusted Sources

# 4. Check SSL mode
echo $DATABASE_URL | grep sslmode
# Must include: ?sslmode=require
```

**Solutions:**

**Solution 1: IP not whitelisted**
- Go to DigitalOcean dashboard
- Navigate to database > Settings > Trusted Sources
- Add droplet IP: `curl -s ifconfig.me`

**Solution 2: Connection pool exhausted**
```bash
# Check active connections
psql "$DATABASE_URL" -c "SELECT count(*) FROM pg_stat_activity;"

# If near max (20), restart API
docker-compose restart api
```

**Solution 3: Database maintenance**
- Check DigitalOcean dashboard for maintenance windows
- Wait for completion or contact support

---

### Issue: High Memory Usage

**Symptoms:**
```bash
free -h
# Shows: Mem: >90% used
docker stats
# Shows: High memory usage on containers
```

**Diagnosis:**
```bash
# 1. Check memory by container
docker stats --no-stream

# 2. Check for memory leaks
docker-compose logs api | grep -i "memory"

# 3. Check swap usage
free -h | grep Swap
```

**Solutions:**

**Solution 1: Restart high-memory containers**
```bash
docker-compose restart api celery-worker-scoring
```

**Solution 2: Reduce worker concurrency**
```bash
# Edit docker-compose.yml
# Change: --concurrency=2
# To: --concurrency=1

# Apply changes
docker-compose up -d --no-deps celery-worker-scoring
```

**Solution 3: Increase swap**
```bash
# Create 4GB swap (if 2GB exists)
sudo fallocate -l 4G /swapfile2
sudo chmod 600 /swapfile2
sudo mkswap /swapfile2
sudo swapon /swapfile2
```

**Solution 4: Clear Redis cache**
```bash
docker-compose exec redis redis-cli FLUSHDB
```

---

### Issue: Celery Tasks Not Processing

**Symptoms:**
```bash
# Tasks pile up in queue
docker-compose exec api celery -A app.celery_app inspect reserved
# Shows many reserved tasks
```

**Diagnosis:**
```bash
# 1. Check worker status
docker-compose exec api celery -A app.celery_app inspect active

# 2. Check worker logs
docker-compose logs --tail=100 celery-worker-scoring

# 3. Check Redis
docker-compose exec redis redis-cli ping
```

**Solutions:**

**Solution 1: Workers not running**
```bash
docker-compose ps | grep worker
# If not Up, restart
docker-compose restart celery-worker-scoring celery-worker-portfolio celery-worker-monitoring
```

**Solution 2: Workers stuck on long task**
```bash
# Check active tasks
docker-compose exec api celery -A app.celery_app inspect active

# Revoke stuck task (get task_id from above)
docker-compose exec api celery -A app.celery_app revoke [task_id] --terminate
```

**Solution 3: Redis connection issue**
```bash
# Check Redis connectivity
docker-compose exec api python -c "import redis; r=redis.from_url('$REDIS_URL'); print(r.ping())"

# Restart Redis
docker-compose restart redis
```

---

### Issue: SSL Certificate Expiring/Expired

**Symptoms:**
```
SSL certificate problem: certificate has expired
```

**Diagnosis:**
```bash
# Check certificate expiry
echo | openssl s_client -connect api.incomefortress.com:443 2>/dev/null | openssl x509 -noout -dates

# Output shows:
# notBefore=...
# notAfter=...  (check this date)
```

**Solutions:**

**Solution 1: Renew certificates**
```bash
# Manual renewal
docker-compose run --rm certbot renew

# Reload nginx
docker-compose exec nginx nginx -s reload
```

**Solution 2: Force renewal**
```bash
docker-compose run --rm certbot renew --force-renewal
docker-compose exec nginx nginx -s reload
```

**Solution 3: Re-run initialization**
```bash
./scripts/init_ssl.sh
```

---

### Issue: High CPU Usage

**Symptoms:**
```bash
top
# Shows high CPU usage on Docker processes
```

**Diagnosis:**
```bash
# 1. Check CPU by container
docker stats --no-stream

# 2. Check for infinite loops in logs
docker-compose logs api | grep -i "error\|exception"

# 3. Check Celery task count
docker-compose exec api celery -A app.celery_app inspect active
```

**Solutions:**

**Solution 1: Restart high-CPU containers**
```bash
docker-compose restart [container-name]
```

**Solution 2: Reduce concurrent tasks**
```bash
# Edit docker-compose.yml
# Reduce --concurrency=2 to --concurrency=1
docker-compose up -d
```

**Solution 3: Check for runaway tasks**
```bash
# Inspect active tasks
docker-compose exec api celery -A app.celery_app inspect active

# Revoke problematic tasks
docker-compose exec api celery -A app.celery_app revoke [task_id] --terminate
```

---

## Emergency Procedures

### Complete Service Failure

**Immediate Actions:**

1. **Assess Scope**
```bash
# Check all services
docker-compose ps

# Check system resources
free -h
df -h
top
```

2. **Check Recent Changes**
```bash
# Recent deployments
git log --oneline -10

# Recent configuration changes
ls -lt .env docker-compose.yml
```

3. **Attempt Restart**
```bash
# Full restart
docker-compose down
docker-compose up -d

# Monitor startup
docker-compose logs -f
```

4. **If Restart Fails → Rollback**
```bash
# Restore from backup
./scripts/restore_database.sh [last_known_good_backup]

# Checkout previous code version
git checkout [previous_commit]

# Rebuild and start
docker-compose build
docker-compose up -d
```

5. **Communicate**
- Update status page (if available)
- Notify users via email/Slack
- Document incident in incident log

---

### Database Corruption

**Immediate Actions:**

1. **Stop All Writes**
```bash
# Stop API and workers
docker-compose stop api celery-worker-scoring celery-worker-portfolio celery-worker-monitoring
```

2. **Assess Damage**
```bash
# Connect to database
psql "$DATABASE_URL"

# Check for corruption
SELECT * FROM pg_stat_database;

# Check table integrity
\dt
```

3. **Restore from Backup**
```bash
# Full restore procedure
./scripts/restore_database.sh [most_recent_backup]
```

4. **Verify Restoration**
```bash
# Check critical tables
psql "$DATABASE_URL" -c "SELECT COUNT(*) FROM platform_shared.securities;"
psql "$DATABASE_URL" -c "SELECT COUNT(*) FROM tenant_001.users;"
```

5. **Resume Services**
```bash
docker-compose start api celery-worker-scoring celery-worker-portfolio celery-worker-monitoring
```

---

### Security Incident

**Immediate Actions:**

1. **Isolate**
```bash
# Stop accepting traffic
docker-compose stop nginx

# Or block at firewall
ufw deny 80
ufw deny 443
```

2. **Assess**
```bash
# Check access logs
tail -n 1000 /var/log/nginx/access.log

# Check for unauthorized access
docker-compose logs api | grep -i "401\|403\|unauthorized"

# Check running processes
ps aux | grep -v grep
```

3. **Contain**
```bash
# Rotate secrets
# 1. Generate new secrets
openssl rand -hex 32

# 2. Update .env
nano .env

# 3. Restart services
docker-compose restart
```

4. **Investigate**
- Review all logs
- Check database for unauthorized changes
- Document findings

5. **Recover**
- Restore from clean backup if needed
- Implement additional security measures
- Update credentials

6. **Report**
- Document incident
- Notify affected users
- Report to appropriate authorities if required

---

## Monitoring & Alerts

### Key Metrics to Monitor

**API Metrics:**
- Request rate (req/sec)
- Response time (p50, p95, p99)
- Error rate (%)
- Active connections

**Celery Metrics:**
- Queue depth
- Task success/failure rate
- Task duration
- Worker availability

**System Metrics:**
- CPU usage (%)
- Memory usage (%)
- Disk usage (%)
- Network I/O

**Application Metrics:**
- Scoring requests/hour
- Feature extraction success rate
- Circuit breaker triggers
- Database connections

### Alert Thresholds

| Alert | Warning | Critical | Action |
|-------|---------|----------|--------|
| API Response Time | >500ms | >1s | Investigate slow queries |
| Error Rate | >1% | >5% | Check logs immediately |
| CPU Usage | >80% | >90% | Reduce load or scale |
| Memory Usage | >85% | >95% | Restart services |
| Disk Usage | >85% | >95% | Clean up logs/data |
| Queue Depth | >100 | >500 | Check workers |
| Database Connections | >15 | >18 | Check connection pool |

### Alert Response Procedures

**Critical Alert Response (15-minute SLA):**
1. Acknowledge alert
2. Assess impact
3. Follow troubleshooting guide
4. Implement fix
5. Monitor for resolution
6. Document in incident log

**Warning Alert Response (1-hour SLA):**
1. Review metrics
2. Identify trend
3. Plan preventive action
4. Schedule maintenance if needed

---

## Maintenance Windows

### Weekly Maintenance (Sunday 2 AM - 4 AM EST)

**Standard Tasks:**
```bash
# 1. Update system packages
sudo apt update && sudo apt upgrade -y

# 2. Docker cleanup
docker system prune -f

# 3. Log rotation
find /opt/income-platform/logs -name "*.log" -mtime +7 -delete

# 4. Database VACUUM
psql "$DATABASE_URL" -c "VACUUM ANALYZE;"

# 5. Redis SAVE
docker-compose exec redis redis-cli SAVE

# 6. Review backup integrity
ls -lh /opt/income-platform/backups/database/
```

### Monthly Maintenance (First Sunday 2 AM - 6 AM EST)

**Extended Tasks:**
```bash
# 1-5. Standard weekly tasks (above)

# 6. Full database backup verification
./scripts/test_restore.sh

# 7. Security updates
sudo unattended-upgrades

# 8. SSL certificate check
certbot renew --dry-run

# 9. Disk cleanup
sudo apt autoremove -y
sudo apt autoclean

# 10. Performance review
# Review Prometheus metrics from past month
# Identify trends and optimization opportunities
```

### Quarterly Maintenance (First Sunday of Quarter, 2 AM - 6 AM EST)

**Deep Maintenance:**
```bash
# 1-10. Monthly tasks (above)

# 11. Full system backup
tar -czf /backup/system_$(date +%Y%m%d).tar.gz /opt/income-platform

# 12. Disaster recovery test
# Test full restore procedure in staging environment

# 13. Security audit
# Review access logs, update firewall rules, rotate credentials

# 14. Dependency updates
pip list --outdated
# Plan dependency upgrade schedule
```

---

## Useful Commands Reference

### Docker

```bash
# View all containers (including stopped)
docker ps -a

# Remove stopped containers
docker container prune

# Remove unused images
docker image prune -a

# View disk usage
docker system df

# Full cleanup (⚠️ removes everything unused)
docker system prune -a --volumes
```

### PostgreSQL

```bash
# Export schema
pg_dump -s "$DATABASE_URL" > schema.sql

# Export data
pg_dump -a "$DATABASE_URL" > data.sql

# Restore
psql "$DATABASE_URL" < backup.sql

# List tables with size
psql "$DATABASE_URL" -c "\dt+"
```

### Redis

```bash
# Get info
docker-compose exec redis redis-cli INFO

# Monitor commands
docker-compose exec redis redis-cli MONITOR

# Get key count
docker-compose exec redis redis-cli DBSIZE

# Flush all (⚠️ CAREFUL)
docker-compose exec redis redis-cli FLUSHALL
```

### Nginx

```bash
# Test configuration
docker-compose exec nginx nginx -t

# Reload configuration
docker-compose exec nginx nginx -s reload

# View configuration
docker-compose exec nginx cat /etc/nginx/nginx.conf
```

---

## Contact Information

**On-Call Rotation:** [Insert schedule]  
**Escalation Path:** [Insert hierarchy]  
**Emergency Contact:** [Insert contact]

---

**Document Version:** 1.0.0  
**Last Updated:** February 2, 2026  
**Maintained By:** Alberto DBP  
**Review Frequency:** Monthly
