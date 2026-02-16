# Income Fortress Platform - Development Guide

## 🔄 Development Workflow

### **Golden Rule: Never Manual File Copying**

All changes flow through Git:
```
Local Mac → Git Commit → GitHub → Git Pull → Production
```

### **Three Environments**

1. **Local (Mac):** `/Volumes/CH-DataOne/AlbertoDBP/Agentic/income-platform`
2. **GitHub:** `https://github.com/AlbertoDBP/Agentic/tree/main/income-platform`
3. **Production:** `root@138.197.78.238:/opt/Agentic/income-platform`

---

## 🛠️ Daily Development

### **Start Work Session**
```bash
cd /Volumes/CH-DataOne/AlbertoDBP/Agentic/income-platform

# Check environment status
./scripts/dev-workflow.sh status

# Pull latest changes
./scripts/dev-workflow.sh dev
```

### **Make Changes**

1. Edit code in VS Code
2. Test locally
3. Document changes

### **Commit & Deploy**
```bash
# Option A: Use auto-updater (recommended)
./scripts/auto-update-docs.sh

# Option B: Manual Git workflow
git add .
git commit -m "feat: describe your changes"
git push origin main

# Deploy to production
./scripts/dev-workflow.sh deploy
```

---

## 📝 Documentation Standards

### **Every Code Change Requires:**

1. **Functional Specification** (if new feature)
   - Location: `documentation/functional/`
   - Format: `agent-XX-name.md` or `feature-name.md`

2. **Implementation Details**
   - Location: `documentation/implementation/`
   - Include: Technical design, testing plan

3. **CHANGELOG Entry**
   - What changed
   - Why it changed
   - Impact on users

4. **Tests**
   - Location: `tests/`
   - Must pass before deploy

---

## 🔧 VS Code Tasks

Press `Cmd+Shift+P` → "Tasks: Run Task"

- **Update Documentation** - Run auto-updater
- **Deploy to Production** - Full deployment
- **Test All Services Locally** - Docker Compose up
- **SSH to Production** - Quick SSH access
- **Full Deployment Pipeline** - Complete workflow

---

## 🐛 Debugging

### **Local Development:**

1. Press `F5` in VS Code
2. Select service to debug
3. Set breakpoints
4. Debug away!

### **Production Issues:**
```bash
# SSH to droplet
ssh root@138.197.78.238

# Check service logs
cd /opt/Agentic/income-platform
docker compose logs -f nav-erosion-service
docker compose logs -f market-data-service
docker compose logs -f income-scoring-service

# Check database
docker compose exec nav-erosion-service psql $DATABASE_URL
```

---

## 🧪 Testing
```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src --cov-report=html

# Run specific test
pytest tests/test_nav_erosion.py -v

# Run in VS Code
# Press F5 → Select "Run Tests"
```

---

## 📦 File Organization
```
income-platform/
├── .vscode/              # VS Code configuration
├── documentation/        # All documentation
│   ├── deployment/       # Deployment guides
│   ├── functional/       # Feature specifications
│   ├── implementation/   # Technical docs, migrations
│   └── testing/          # Test plans
├── scripts/              # Automation scripts
│   ├── auto-update-docs.sh
│   └── dev-workflow.sh
├── src/                  # Source code (TO BE CREATED)
│   ├── nav-erosion-service/
│   ├── market-data-service/
│   └── income-scoring-service/
├── tests/                # Tests (TO BE CREATED)
├── docker-compose.yml    # Production config
└── .env.example          # Environment template
```

---

## ⚠️ Common Pitfalls

### **❌ DON'T:**
- Copy files manually between Downloads and project
- Edit files directly on production
- Skip documentation updates
- Commit secrets (.env files)

### **✅ DO:**
- Use auto-update-docs.sh for file sync
- Always test locally first
- Document before coding
- Keep .env files out of Git

---

## 🚀 Deployment Checklist

Before deploying to production:

- [ ] All tests pass locally
- [ ] Documentation updated
- [ ] CHANGELOG.md updated
- [ ] Commit message is clear
- [ ] Pushed to GitHub
- [ ] Production environment checked

---

## 📞 Quick Commands
```bash
# Start development
./scripts/dev-workflow.sh dev

# Check sync status
./scripts/dev-workflow.sh status

# Deploy everything
./scripts/dev-workflow.sh deploy

# Update docs
./scripts/auto-update-docs.sh

# SSH to production
ssh root@138.197.78.238
```

---

## 🎯 Remember

**Git is your single source of truth.**  
**Never copy files manually.**  
**Document everything.**  
**Test before deploying.**
