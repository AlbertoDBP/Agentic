# DigitalOcean Deployment Guide - Income Fortress Platform

**Last Updated:** 2026-02-05  
**Estimated Time:** 2-4 hours  
**Cost:** ~$88/month (managed services) or ~$48/month (self-hosted)

---

## 🎯 DEPLOYMENT OVERVIEW

This guide deploys the **core 3 services**:
1. ✅ NAV Erosion Analysis Service
2. ✅ Market Data Sync Service (Agent 01)
3. ✅ Income Scoring Service (Agent 03)

**Infrastructure:**
- PostgreSQL (97 tables)
- Redis (caching layer)
- 3 Python/FastAPI services
- Nginx reverse proxy

---

## 📋 PREREQUISITES

### **1. DigitalOcean Account**
- [ ] Sign up at https://www.digitalocean.com
- [ ] Add payment method
- [ ] Generate API token (Settings → API → Generate New Token)

### **2. Local Requirements**
- [ ] Docker installed
- [ ] Docker Compose installed
- [ ] SSH key generated (`ssh-keygen -t ed25519`)
- [ ] Domain name (optional, can use IP initially)

### **3. API Keys**
- [ ] Market data provider key (Alpha Vantage, Polygon.io, or IEX Cloud)
- [ ] Sentry DSN (optional, for error tracking)

---

## 🚀 STEP-BY-STEP DEPLOYMENT

### **PHASE 1: Set Up DigitalOcean Infrastructure** (30 minutes)

#### **Option A: Managed Services (Recommended - $88/month)**

**1.1 Create Managed PostgreSQL Database**
```bash
# Via DigitalOcean Web Console:
1. Click "Create" → "Databases"
2. Choose PostgreSQL 15
3. Select plan: Basic ($15/month)
   - 1 vCPU, 1GB RAM, 10GB SSD
4. Choose region: NYC3 (or closest to you)
5. Name: income-fortress-postgres
6. Click "Create Database Cluster"
7. Wait 5-10 minutes for provisioning
8. Copy connection string
```

**1.2 Create Managed Valkey (Redis-Compatible)**
```bash
# Via DigitalOcean Web Console:
# NOTE: DigitalOcean now uses Valkey (Redis fork, 100% compatible)
1. Click "Create" → "Databases"
2. Choose Valkey 8 (formerly Redis)
3. Select plan: Basic ($15/month)
   - 1 vCPU, 1GB RAM
4. Choose same region as PostgreSQL
5. Name: income-fortress-valkey
6. Click "Create Database Cluster"
7. Copy connection string (format: valkey://... or redis://...)
```

**Compatibility Note:** Valkey is 100% compatible with Redis. Your existing Redis clients (redis-py, ioredis) work without changes.

**1.3 Create Droplet for Application Services**
```bash
# Via DigitalOcean Web Console:
1. Click "Create" → "Droplets"
2. Choose image: Docker on Ubuntu 24.04
3. Select plan: Basic
   - 4 vCPU, 8GB RAM ($48/month)
4. Choose same region
5. Add your SSH key
6. Hostname: income-fortress-app
7. Enable backups (+$4.80/month)
8. Click "Create Droplet"
9. Note the IP address
```

**Total Cost:** $48 + $15 + $15 + $5 (spaces) + $4.80 (backups) = **~$88/month**

---

#### **Option B: Self-Hosted (Budget - $48/month)**

**1.1 Create Single Droplet with Everything**
```bash
# Via DigitalOcean Web Console:
1. Click "Create" → "Droplets"
2. Choose image: Docker on Ubuntu 24.04
3. Select plan: General Purpose
   - 8 vCPU, 16GB RAM ($96/month)
   OR Basic: 4 vCPU, 8GB RAM ($48/month)
4. Add your SSH key
5. Hostname: income-fortress
6. Enable backups
7. Click "Create Droplet"
```

**Total Cost:** $48-$96/month (depending on size)

---

### **PHASE 2: Configure Droplet** (20 minutes)

**2.1 SSH into Droplet**
```bash
# Replace with your droplet IP
ssh root@your_droplet_ip

# Update system
apt update && apt upgrade -y

# Install required packages
apt install -y git curl wget htop nano ufw fail2ban

# Verify Docker is installed
docker --version
docker-compose --version
```

**2.2 Configure Firewall**
```bash
# Allow SSH, HTTP, HTTPS
ufw allow 22/tcp
ufw allow 80/tcp
ufw allow 443/tcp
ufw allow 8001:8003/tcp  # API services

# Enable firewall
ufw --force enable
ufw status
```

**2.3 Configure Fail2Ban (Security)**
```bash
# Enable fail2ban for SSH protection
systemctl enable fail2ban
systemctl start fail2ban
```

---

### **PHASE 3: Deploy Application** (30-60 minutes)

**3.1 Clone Repository**
```bash
cd /opt
git clone https://github.com/AlbertoDBP/Agentic.git
cd Agentic/income-platform
```

**3.2 Create Environment File**
```bash
# Copy example environment file
cp /path/to/.env.example .env

# Edit with your values
nano .env
```

**Fill in these CRITICAL values:**
```bash
# If using Managed Databases:
DATABASE_URL=postgresql://user:pass@host:25060/db?sslmode=require
REDIS_URL=rediss://default:pass@host:25061

# If using Docker Compose databases:
POSTGRES_PASSWORD=STRONG_PASSWORD_HERE
SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
JWT_SECRET=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")

# API Keys
MARKET_DATA_API_KEY=your_key_here
```

**3.3 Copy Production Docker Compose**
```bash
# Use the complete production docker-compose.yml
cp /path/to/docker-compose.production.yml docker-compose.yml
```

**3.4 Start Services**
```bash
# Pull images and build
docker-compose pull
docker-compose build

# Start in detached mode
docker-compose up -d

# Check logs
docker-compose logs -f
```

**3.5 Verify Services**
```bash
# Check all containers are running
docker-compose ps

# Test health endpoints
curl http://localhost:8001/health  # Market Data
curl http://localhost:8002/health  # Income Scoring  
curl http://localhost:8003/health  # NAV Erosion

# Check database connection
docker-compose exec postgres psql -U income_fortress_user -d income_fortress -c "SELECT version();"
```

---

### **PHASE 4: Database Migration** (10 minutes)

**4.1 Run Initial Migration**
```bash
# Copy SQL migration file
docker cp documentation/implementation/V2.0__nav_erosion_analysis.sql \
  income-fortress-postgres:/tmp/

# Execute migration
docker-compose exec postgres psql \
  -U income_fortress_user \
  -d income_fortress \
  -f /tmp/V2.0__nav_erosion_analysis.sql

# Verify tables created
docker-compose exec postgres psql \
  -U income_fortress_user \
  -d income_fortress \
  -c "\dt"
```

**Expected output:** Should see 97+ tables listed

---

### **PHASE 5: Configure Nginx** (20 minutes)

**5.1 Create Nginx Configuration**
```bash
mkdir -p nginx
nano nginx/nginx.conf
```

**Paste this configuration:**
```nginx
events {
    worker_connections 1024;
}

http {
    upstream market_data {
        server market-data-service:8001;
    }
    
    upstream income_scoring {
        server income-scoring-service:8002;
    }
    
    upstream nav_erosion {
        server nav-erosion-service:8003;
    }
    
    server {
        listen 80;
        server_name your_domain_or_ip;
        
        # Health check endpoint
        location /health {
            access_log off;
            return 200 "OK\n";
            add_header Content-Type text/plain;
        }
        
        # Market Data Service
        location /api/market-data/ {
            proxy_pass http://market_data/;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
        }
        
        # Income Scoring Service
        location /api/income-scoring/ {
            proxy_pass http://income_scoring/;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
        }
        
        # NAV Erosion Service
        location /api/nav-erosion/ {
            proxy_pass http://nav_erosion/;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
        }
    }
}
```

**5.2 Restart Nginx**
```bash
docker-compose restart nginx
```

**5.3 Test API Access**
```bash
# From your local machine
curl http://your_droplet_ip/api/nav-erosion/health
```

---

### **PHASE 6: SSL/HTTPS (Optional but Recommended)** (15 minutes)

**6.1 Install Certbot**
```bash
apt install -y certbot python3-certbot-nginx
```

**6.2 Get SSL Certificate**
```bash
# Replace with your domain
certbot --nginx -d your-domain.com -d www.your-domain.com

# Auto-renew
certbot renew --dry-run
```

---

## ✅ VERIFICATION CHECKLIST

Run these tests to verify deployment:

```bash
# 1. Check all containers
docker-compose ps
# ✅ All should show "Up" status

# 2. Check database
docker-compose exec postgres psql -U income_fortress_user -d income_fortress -c "\dt" | wc -l
# ✅ Should show 97+ tables

# 3. Test NAV Erosion API
curl -X POST http://localhost:8003/api/v1/analyze \
  -H "Content-Type: application/json" \
  -d '{"portfolio_value": 1000000, "withdrawal_rate": 0.04, "years": 30}'
# ✅ Should return simulation results

# 4. Check logs
docker-compose logs --tail=50 nav-erosion-service
# ✅ Should see no errors

# 5. Resource usage
docker stats --no-stream
# ✅ Verify memory/CPU within limits
```

---

## 📊 MONITORING

**Basic Monitoring Commands:**
```bash
# View all logs
docker-compose logs -f --tail=100

# Check resource usage
docker stats

# Database connections
docker-compose exec postgres psql -U income_fortress_user -d income_fortress \
  -c "SELECT count(*) FROM pg_stat_activity;"

# Redis stats
docker-compose exec redis redis-cli INFO stats
```

---

## 🔧 TROUBLESHOOTING

### **Issue: Services won't start**
```bash
# Check logs
docker-compose logs service-name

# Verify environment variables
docker-compose config

# Restart individual service
docker-compose restart service-name
```

### **Issue: Database connection failed**
```bash
# Test connection
docker-compose exec nav-erosion-service python -c \
  "import os; import psycopg2; print(psycopg2.connect(os.environ['DATABASE_URL']))"

# Check PostgreSQL is accessible
docker-compose exec postgres pg_isready
```

### **Issue: Out of memory**
```bash
# Check memory usage
free -h

# Reduce Monte Carlo simulations
# Edit .env: MONTE_CARLO_SIMULATIONS=5000

# Restart services
docker-compose restart
```

---

## 💰 COST OPTIMIZATION

**After 30 days, review:**
```bash
# Check actual resource usage
docker stats

# Downsize if underutilized:
# - 4 vCPU → 2 vCPU droplet ($24/month savings)
# - Use Standard SSD vs Premium SSD for databases
```

**Potential savings:**
- Self-host PostgreSQL: Save $15/month
- Self-host Redis: Save $15/month
- Smaller droplet: Save $24/month
- **Total savings potential: $54/month**

---

## 🎉 SUCCESS CRITERIA

✅ All 3 services running  
✅ Database migrated (97 tables)  
✅ API endpoints responding  
✅ Health checks passing  
✅ Nginx routing correctly  
✅ Logs showing no errors  
✅ Can run NAV erosion simulation  
✅ Market data syncing  
✅ Income scores calculating  

---

## 📝 NEXT STEPS

After successful deployment:

1. **Add remaining 19 agents** (Agents 2, 4, 10-24)
2. **Set up monitoring** (Prometheus + Grafana)
3. **Configure backups** (automated daily backups)
4. **Load testing** (ensure it handles expected traffic)
5. **Documentation** (API docs, runbooks)
6. **CI/CD pipeline** (automated deployments)

---

## 🆘 SUPPORT

If you encounter issues:
1. Check logs: `docker-compose logs`
2. Review error messages
3. Verify environment variables
4. Check DigitalOcean status page
5. Consult documentation in `/documentation/deployment/`

**Estimated Total Time:** 2-4 hours  
**Estimated Cost:** $48-$88/month
