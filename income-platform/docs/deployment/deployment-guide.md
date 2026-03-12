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

## Next Steps

Continue with [Infrastructure Setup](#infrastructure-setup) for database and Redis configuration, environment setup, and deployment procedures.

For complete deployment instructions, refer to the original deployment-guide.md document.
