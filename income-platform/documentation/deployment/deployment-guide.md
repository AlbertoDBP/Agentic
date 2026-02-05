# Deployment Guide - Income Fortress Platform

**Version:** 1.0.0  
**Target Environment:** Production (DigitalOcean)  
**Last Updated:** February 2, 2026

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Infrastructure Setup](#infrastructure-setup)
3. [Environment Configuration](#environment-configuration)
4. [Initial Deployment](#initial-deployment)
5. [Post-Deployment Verification](#post-deployment-verification)
6. [Troubleshooting](#troubleshooting)

---

## Prerequisites

### Required Accounts
- [ ] DigitalOcean account with billing enabled
- [ ] Domain name registered (e.g., incomefortress.com)
- [ ] Anthropic API account with API key
- [ ] SendGrid account for email alerts (optional)
- [ ] GitHub account for code repository

### Required Tools (Local Machine)
```bash
# Verify installations
docker --version          # Docker 20.10+
docker-compose --version  # Docker Compose 2.0+
git --version            # Git 2.30+
ssh -V                   # OpenSSH 8.0+
```

### Required Knowledge
- Basic Linux command line
- Docker fundamentals
- DNS configuration
- SSH key management

---

## Infrastructure Setup

### Step 1: Create DigitalOcean Droplet

**1.1 Navigate to DigitalOcean Console**
- Go to: https://cloud.digitalocean.com
- Click "Create" → "Droplets"

**1.2 Select Configuration**
```
Region: New York (nyc1, nyc2, or nyc3)
Image: Ubuntu 22.04 LTS x64
Plan: Basic
CPU Options: Regular
Size: 4 GB RAM / 2 vCPUs / 80 GB SSD ($24/mo)
```

**1.3 Additional Options**
```
☑ Enable IPv6
☑ User data: (leave empty)
☑ Monitoring: Enable (free)
☐ Backups: Optional (+20% cost)
```

**1.4 Authentication**
- Upload your SSH public key (`~/.ssh/id_rsa.pub`)
- Or create new SSH key: `ssh-keygen -t rsa -b 4096 -C "your_email@example.com"`

**1.5 Finalize**
- Hostname: `income-platform-prod`
- Tags: `production`, `income-platform`
- Click "Create Droplet"

**1.6 Note Your Droplet IP**
```bash
# Example output
Droplet IP: 159.89.123.45
```

---

### Step 2: Create Managed PostgreSQL Database

**2.1 Navigate to Databases**
- Click "Create" → "Databases"

**2.2 Select Configuration**
```
Database Engine: PostgreSQL 15
Plan: Basic
Node: 1 GB RAM / 1 vCPU / 10 GB Disk ($15/mo)
Region: Same as droplet (nyc1/nyc2/nyc3)
```

**2.3 Configure**
```
Database Cluster Name: income-platform-db
Database Name: income_platform
```

**2.4 Trusted Sources**
- Add your droplet IP address
- Format: `159.89.123.45` (individual IP)

**2.5 Create Database**
- Click "Create Database Cluster"
- Wait 3-5 minutes for provisioning

**2.6 Save Connection Details**
```bash
# Example connection details
Host: db-postgresql-nyc1-12345.b.db.ondigitalocean.com
Port: 25060
User: doadmin
Password: [auto-generated - save this!]
Database: income_platform
SSL Mode: require
```

**2.7 Create Connection String**
```bash
DATABASE_URL="postgresql://doadmin:[PASSWORD]@db-postgresql-nyc1-12345.b.db.ondigitalocean.com:25060/income_platform?sslmode=require"
```

---

### Step 3: Create Managed Redis

**3.1 Navigate to Databases**
- Click "Create" → "Databases"

**3.2 Select Configuration**
```
Database Engine: Redis 7
Plan: Basic  
Node: 1 GB RAM / 1 vCPU ($15/mo)
Region: Same as droplet and PostgreSQL
```

**3.3 Configure**
```
Redis Cluster Name: income-platform-redis
Eviction Policy: allkeys-lru
```

**3.4 Trusted Sources**
- Add your droplet IP: `159.89.123.45`

**3.5 Create Redis**
- Click "Create Database Cluster"
- Wait 3-5 minutes

**3.6 Save Connection Details**
```bash
Host: db-redis-nyc1-67890.b.db.ondigitalocean.com
Port: 25061
Password: [auto-generated - save this!]
```

**3.7 Create Connection String**
```bash
REDIS_URL="rediss://default:[PASSWORD]@db-redis-nyc1-67890.b.db.ondigitalocean.com:25061"
```

---

### Step 4: Create DigitalOcean Spaces (Object Storage)

**4.1 Navigate to Spaces**
- Click "Create" → "Spaces"

**4.2 Select Configuration**
```
Region: Same as your droplet (nyc3)
Enable CDN: Yes (free)
```

**4.3 Configure**
```
Unique Name: income-platform-storage
Restrict File Listing: Yes (recommended)
```

**4.4 Create Space**
- Click "Create a Space"

**4.5 Generate Access Keys**
- Navigate to "API" → "Spaces access keys"
- Click "Generate New Key"
- Name: `income-platform-prod`
- Save both Access Key and Secret Key

**4.6 Note Configuration**
```bash
SPACES_REGION=nyc3
SPACES_BUCKET=income-platform-storage
SPACES_ENDPOINT=https://nyc3.digitaloceanspaces.com
SPACES_ACCESS_KEY=[saved from step 4.5]
SPACES_SECRET_KEY=[saved from step 4.5]
```

---

### Step 5: Configure DNS

**5.1 Add A Records**

In your domain registrar (e.g., Namecheap, GoDaddy):

```
Type: A
Name: api
Value: [your droplet IP]
TTL: 300

Type: A
Name: n8n
Value: [your droplet IP]
TTL: 300

Type: A  
Name: app (future frontend)
Value: [your droplet IP]
TTL: 300
```

**5.2 Verify DNS Propagation**
```bash
# Wait 5-10 minutes, then verify
dig api.incomefortress.com +short
# Should return: 159.89.123.45

dig n8n.incomefortress.com +short
# Should return: 159.89.123.45
```

---

## Environment Configuration

### Step 6: Connect to Droplet

**6.1 SSH into Droplet**
```bash
ssh root@159.89.123.45
```

**6.2 Update System**
```bash
apt update && apt upgrade -y
```

**6.3 Set Timezone**
```bash
timedatectl set-timezone America/New_York
timedatectl status
```

**6.4 Configure Firewall**
```bash
# Install UFW
apt install ufw -y

# Allow SSH (important - don't lock yourself out!)
ufw allow 22/tcp

# Allow HTTP and HTTPS
ufw allow 80/tcp
ufw allow 443/tcp

# Enable firewall
ufw enable

# Verify
ufw status
```

**6.5 Create Swap File (Recommended)**
```bash
# Create 2GB swap
fallocate -l 2G /swapfile
chmod 600 /swapfile
mkswap /swapfile
swapon /swapfile

# Make permanent
echo '/swapfile none swap sw 0 0' >> /etc/fstab

# Verify
free -h
```

---

### Step 7: Install Docker

**7.1 Install Docker**
```bash
# Install using convenience script
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh

# Verify installation
docker --version
# Expected: Docker version 24.0.x

# Start Docker service
systemctl start docker
systemctl enable docker
```

**7.2 Install Docker Compose**
```bash
# Install Docker Compose
apt install docker-compose -y

# Verify
docker-compose --version
# Expected: docker-compose version 2.x.x
```

**7.3 Test Docker**
```bash
docker run hello-world
# Should see: "Hello from Docker!"
```

---

### Step 8: Clone Repository

**8.1 Install Git** (if not already installed)
```bash
apt install git -y
```

**8.2 Clone Repository**
```bash
# Navigate to working directory
cd /opt

# Clone repository
git clone https://github.com/AlbertoDBP/Agentic.git
cd Agentic/income-platform

# Verify structure
ls -la
# Should see: docker-compose.yml, Dockerfile.api, etc.
```

---

### Step 9: Configure Environment Variables

**9.1 Create .env File**
```bash
# Copy example environment file
cp .env.production.example .env

# Edit with your values
nano .env
```

**9.2 Fill in Required Values**

```bash
# ════════════════════════════════════════════════════════════
# DEPLOYMENT INFO
# ════════════════════════════════════════════════════════════
VERSION=1.0.0
ENVIRONMENT=production
DEBUG=false

# ════════════════════════════════════════════════════════════
# DATABASE - From Step 2
# ════════════════════════════════════════════════════════════
DB_HOST=db-postgresql-nyc1-12345.b.db.ondigitalocean.com
DB_PORT=25060
DB_NAME=income_platform
DB_USER=doadmin
DB_PASSWORD=[your PostgreSQL password]
DATABASE_URL=postgresql://doadmin:[PASSWORD]@[HOST]:25060/income_platform?sslmode=require

# ════════════════════════════════════════════════════════════
# REDIS - From Step 3
# ════════════════════════════════════════════════════════════
REDIS_HOST=db-redis-nyc1-67890.b.db.ondigitalocean.com
REDIS_PORT=25061
REDIS_PASSWORD=[your Redis password]
REDIS_URL=rediss://default:[PASSWORD]@[HOST]:25061

# ════════════════════════════════════════════════════════════
# SECRETS - Generate New
# ════════════════════════════════════════════════════════════
# Generate with: openssl rand -hex 32
SECRET_KEY=[generate new]
JWT_SECRET_KEY=[generate new]
N8N_ENCRYPTION_KEY=[generate new]

# ════════════════════════════════════════════════════════════
# API KEYS
# ════════════════════════════════════════════════════════════
ANTHROPIC_API_KEY=sk-ant-api03-[your key]
ALPHA_VANTAGE_API_KEY=[optional]
FINANCIAL_MODELING_PREP_API_KEY=[optional]

# ════════════════════════════════════════════════════════════
# DIGITALOCEAN SPACES - From Step 4
# ════════════════════════════════════════════════════════════
SPACES_REGION=nyc3
SPACES_BUCKET=income-platform-storage
SPACES_ACCESS_KEY=[from step 4.5]
SPACES_SECRET_KEY=[from step 4.5]
SPACES_ENDPOINT=https://nyc3.digitaloceanspaces.com

# ════════════════════════════════════════════════════════════
# DOMAINS
# ════════════════════════════════════════════════════════════
ALLOWED_ORIGINS=https://incomefortress.com,https://app.incomefortress.com
N8N_HOST=n8n.incomefortress.com

# ════════════════════════════════════════════════════════════
# N8N AUTH
# ════════════════════════════════════════════════════════════
N8N_USER=admin
N8N_PASSWORD=[create strong password]

# ════════════════════════════════════════════════════════════
# EMAIL (Optional - SendGrid)
# ════════════════════════════════════════════════════════════
SENDGRID_API_KEY=[optional]
FROM_EMAIL=alerts@incomefortress.com
```

**9.3 Generate Secrets**
```bash
# Generate SECRET_KEY
openssl rand -hex 32

# Generate JWT_SECRET_KEY  
openssl rand -hex 32

# Generate N8N_ENCRYPTION_KEY
openssl rand -hex 32
```

**9.4 Verify .env File**
```bash
# Check for CHANGE_ME placeholders
grep -i "CHANGE_ME" .env

# Should return nothing
# If you see matches, replace them with actual values
```

---

## Initial Deployment

### Step 10: Initialize SSL Certificates

**10.1 Make Scripts Executable**
```bash
chmod +x scripts/*.sh
```

**10.2 Run SSL Initialization**
```bash
./scripts/init_ssl.sh
```

**Expected Output:**
```
→ Downloading recommended TLS parameters...
→ Creating dummy certificate for api.incomefortress.com...
→ Starting nginx...
→ Deleting dummy certificate...
→ Requesting Let's Encrypt certificates...
→ Reloading nginx...
✅ SSL certificates obtained successfully!
```

**10.3 Verify Certificates**
```bash
ls -la certbot/conf/live/
# Should see directories for each domain
```

---

### Step 11: Database Migrations

**11.1 Start Database Services**
```bash
# Start only Redis (for migrations)
docker-compose up -d redis

# Wait 5 seconds
sleep 5
```

**11.2 Run Migrations**
```bash
# Run migration container
docker-compose run --rm api alembic upgrade head
```

**Expected Output:**
```
INFO  [alembic.runtime.migration] Running upgrade -> 001_initial_schema
INFO  [alembic.runtime.migration] Running upgrade 001 -> 002_phase1_enhancements
```

**11.3 Verify Database**
```bash
# Connect to PostgreSQL (from your local machine)
psql "$DATABASE_URL"

# List schemas
\dn

# Should see:
# platform_shared
# (tenant schemas created on first tenant creation)

# Exit
\q
```

---

### Step 12: Deploy Application

**12.1 Build Docker Images**
```bash
docker-compose build --parallel
```

**Expected Output:**
```
Building api...
Building celery-worker-scoring...
Building celery-worker-portfolio...
Building celery-worker-monitoring...
[+] Building 120.5s (15/15) FINISHED
```

**12.2 Start Core Services**
```bash
# Start in order
docker-compose up -d redis
sleep 5

docker-compose up -d api n8n
sleep 10

docker-compose up -d celery-worker-scoring celery-worker-portfolio celery-worker-monitoring celery-beat
sleep 5

docker-compose up -d nginx
```

**12.3 Verify All Containers Running**
```bash
docker-compose ps
```

**Expected Output:**
```
NAME                          STATUS
income-api                    Up (healthy)
income-n8n                    Up (healthy)
income-worker-scoring         Up
income-worker-portfolio       Up
income-worker-monitoring      Up
income-beat                   Up
income-redis                  Up (healthy)
income-nginx                  Up (healthy)
```

---

### Step 13: Create Initial Tenant

**13.1 Create Tenant Schema**
```bash
docker-compose exec api python scripts/create_tenant.py \
    --tenant-id 001 \
    --name "Demo Tenant" \
    --email "admin@incomefortress.com"
```

**Expected Output:**
```
Creating tenant: 001
✓ Created schema: tenant_001
✓ Created tables
✓ Inserted default preferences
✓ Created admin user
Tenant 001 created successfully!
```

**13.2 Verify Tenant**
```bash
# Connect to database
psql "$DATABASE_URL"

# List schemas
\dn

# Should now see: tenant_001

# Check preferences
SELECT * FROM tenant_001.preferences LIMIT 5;

# Exit
\q
```

---

## Post-Deployment Verification

### Step 14: Health Checks

**14.1 API Health Check**
```bash
curl https://api.incomefortress.com/health
```

**Expected Response:**
```json
{
  "status": "healthy",
  "timestamp": 1738531200.123
}
```

**14.2 Detailed Health Check**
```bash
curl https://api.incomefortress.com/health/detailed
```

**Expected Response:**
```json
{
  "status": "healthy",
  "checks": {
    "database": true,
    "redis": true,
    "celery": true
  },
  "timestamp": 1738531200.123
}
```

**14.3 n8n Web Interface**
```bash
# Open in browser
https://n8n.incomefortress.com

# Login with credentials from .env:
# Username: [N8N_USER]
# Password: [N8N_PASSWORD]
```

**14.4 Check Logs**
```bash
# View API logs
docker-compose logs -f api --tail=50

# Should see:
# INFO: Started server process
# INFO: Uvicorn running on http://0.0.0.0:8000
```

---

### Step 15: Functional Testing

**15.1 Test Authentication**
```bash
# Register new user
curl -X POST https://api.incomefortress.com/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "password": "SecurePassword123!",
    "full_name": "Test User"
  }'
```

**Expected Response:**
```json
{
  "user_id": "uuid-here",
  "email": "test@example.com",
  "message": "User registered successfully"
}
```

**15.2 Test Login**
```bash
# Login
curl -X POST https://api.incomefortress.com/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "password": "SecurePassword123!"
  }'
```

**Expected Response:**
```json
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "refresh_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "token_type": "bearer"
}
```

**15.3 Test Asset Scoring**
```bash
# Get token from login response
TOKEN="your-access-token-here"

# Score an asset
curl https://api.incomefortress.com/stocks/ARCC/score \
  -H "Authorization: Bearer $TOKEN"
```

**Expected Response:**
```json
{
  "symbol": "ARCC",
  "asset_type": "bdc",
  "overall_score": 75.2,
  "decision": "accumulate",
  "component_scores": {
    "coverage": 82.5,
    "leverage": 71.3,
    "yield": 88.1
  }
}
```

---

### Step 16: Monitoring Setup

**16.1 Check Prometheus Metrics**
```bash
curl http://localhost:8000/metrics
```

**Expected Output:**
```
# HELP http_requests_total Total HTTP requests
# TYPE http_requests_total counter
http_requests_total{method="GET",endpoint="/health",status="200"} 45
...
```

**16.2 Verify Celery Workers**
```bash
docker-compose exec api celery -A app.celery_app inspect stats
```

**Expected Output:**
```json
{
  "worker-scoring@hostname": {
    "total": {
      "app.tasks.scoring.score_asset": 123
    }
  }
}
```

**16.3 Check Scheduled Tasks**
```bash
docker-compose exec api celery -A app.celery_app inspect scheduled
```

---

### Step 17: Backup Verification

**17.1 Run Manual Backup**
```bash
./scripts/backup_database.sh
```

**Expected Output:**
```
[INFO] Creating database backup...
[INFO] ✓ Backup created: income_platform_20260202_120000.sql.gz (12M)
[INFO] ✓ Backup uploaded to Spaces
[INFO] ✓ Old backups cleaned up
✅ Backup completed successfully
```

**17.2 Verify Backup Exists**
```bash
ls -lh backups/database/
# Should see: income_platform_YYYYMMDD_HHMMSS.sql.gz
```

**17.3 Verify Spaces Upload**
- Log into DigitalOcean Spaces console
- Navigate to: `income-platform-storage/backups/database/`
- Confirm backup file exists

---

## Troubleshooting

### Common Issues

#### Issue 1: SSL Certificate Fails

**Symptoms:**
```
Error: Failed to obtain certificate
```

**Solutions:**
```bash
# 1. Verify DNS is propagated
dig api.incomefortress.com +short
# Must return your droplet IP

# 2. Check port 80 is open
ufw status | grep 80

# 3. Verify nginx is running
docker-compose ps nginx

# 4. Try manual certbot
docker-compose run --rm certbot certonly \
  --webroot -w /var/www/certbot \
  -d api.incomefortress.com \
  --email your@email.com \
  --agree-tos --dry-run

# 5. If dry-run works, remove --dry-run and run again
```

---

#### Issue 2: Database Connection Fails

**Symptoms:**
```
psycopg2.OperationalError: could not connect to server
```

**Solutions:**
```bash
# 1. Verify PostgreSQL is accessible
psql "$DATABASE_URL"

# 2. Check if droplet IP is whitelisted
# Go to DigitalOcean > Databases > Trusted Sources
# Add: [your droplet IP]

# 3. Verify connection string
echo $DATABASE_URL
# Must include ?sslmode=require

# 4. Test from droplet
docker-compose exec api python -c "from app.database import db; print('Connected!' if db else 'Failed')"
```

---

#### Issue 3: Containers Not Starting

**Symptoms:**
```
Container exits immediately after start
```

**Solutions:**
```bash
# 1. Check logs
docker-compose logs api --tail=100

# 2. Verify .env file
grep -i "CHANGE_ME" .env
# Should return nothing

# 3. Check resource usage
free -h
df -h

# 4. Restart Docker
systemctl restart docker
docker-compose down
docker-compose up -d

# 5. Rebuild images
docker-compose build --no-cache
```

---

#### Issue 4: High Memory Usage

**Symptoms:**
```
OOMKilled, containers restarting
```

**Solutions:**
```bash
# 1. Check memory
free -h

# 2. Add/increase swap (if not done)
./scripts/setup_swap.sh

# 3. Reduce worker concurrency
# Edit docker-compose.yml:
# Change: --concurrency=2
# To: --concurrency=1

# 4. Restart services
docker-compose restart
```

---

### Getting Help

**Check Logs:**
```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f api --tail=100

# System logs
journalctl -u docker -f
```

**Contact Support:**
- Documentation: https://github.com/AlbertoDBP/Agentic/tree/main/income-platform/docs
- Issues: https://github.com/AlbertoDBP/Agentic/issues

---

## Next Steps After Deployment

1. ✅ Review [Operational Runbook](operational-runbook.md)
2. ✅ Set up monitoring alerts
3. ✅ Configure automated backups (cron)
4. ✅ Test disaster recovery procedure
5. ✅ Create additional tenants as needed
6. ✅ Import n8n workflows

---

**Deployment Guide Version:** 1.0.0  
**Last Updated:** February 2, 2026  
**Maintained By:** Alberto DBP
