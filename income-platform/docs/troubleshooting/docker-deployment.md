# Docker & Deployment Issues

Troubleshooting Docker, image caching, and deployment-specific problems.

---

## Error: Old Code Running After Update

**Symptom:** Deployed new code but service still uses old version. Logs show old behavior.

**Root Cause:** Docker image cached from previous build. `docker compose up` reuses cached layers instead of rebuilding.

**Immediate Fix:**

Force full rebuild and remove cached images:
```bash
# Step 1: Stop all containers
docker compose down

# Step 2: Remove all local images (forces rebuild)
docker compose down --rmi local

# Step 3: Full rebuild with no cache
docker compose up -d --build
```

Or rebuild specific service:
```bash
docker compose build --no-cache market-data-service
docker compose up -d market-data-service
```

Verify new code running:
```bash
# Check image creation time (should be recent)
docker images market-data-service --format "{{.CreatedAt}}"

# Check logs for new behavior
docker compose logs market-data-service -f
```

**Prevention:**
- Use `docker compose build --no-cache` after code changes
- Tag images with version: `docker image tag market-data:latest market-data:v1.2.0`
- Use CI/CD to always rebuild on push
- Don't rely on `docker compose up` to rebuild; be explicit with `--build`

---

## Error: Untracked files block git pull on server

**Symptom:** SSH into server and `git pull` fails:
```
error: The following untracked working directory files would be overwritten by merge:
  path/to/file
Please move or remove these files before you merge.
```

**Root Cause:** Server has untracked files (temp logs, local config) that conflict with repo.

**Immediate Fix:**

1. See what files are blocking:
```bash
git status
```

2. Remove the blocking file:
```bash
git clean -f path/to/file
# Or for all untracked files:
git clean -f -d
```

3. Now pull succeeds:
```bash
git pull origin main
```

4. Restart services:
```bash
docker compose down --rmi local
docker compose up -d --build
```

**Prevention:**
- Add files to `.gitignore`:
```bash
*.log
.env.local
temp/
dist/
```

- Use `.gitignore` template:
```bash
# Logs
*.log
logs/

# Environment
.env.local
.env.*.local

# Cache
__pycache__/
.pytest_cache/
.mypy_cache/

# Build
dist/
build/
*.egg-info/
```

---

## Error: No space left on device

**Symptom:** Docker operations fail with:
```
No space left on device
failed to create new OS thread
```

**Root Cause:** Disk full from old images, logs, or unused containers.

**Immediate Fix:**

Clean up Docker:
```bash
# Remove unused images
docker image prune -a

# Remove unused containers
docker container prune -f

# Remove unused volumes
docker volume prune -f

# Check disk space
df -h

# Check Docker disk usage
docker system df
```

If still full, remove specific items:
```bash
# Remove specific image
docker rmi image-name

# Remove specific container
docker rm container-id

# Clear all build cache
docker builder prune -a
```

Then retry operation:
```bash
docker compose up -d --build
```

**Prevention:**
- Monitor disk space: `df -h` (keep >20% free)
- Clean up regularly: `docker system prune -a --volumes`
- Limit log size in docker-compose.yml:

```yaml
services:
  market-data-service:
    logging:
      options:
        max-size: "10m"
        max-file: "3"
```

---

## Error: docker-compose: command not found

**Symptom:**
```
docker-compose: command not found
```

**Root Cause:** Docker Compose v1 not installed, or v2 not in PATH.

**Immediate Fix:**

Use new syntax (v2 is built into Docker):
```bash
# Old (v1)
# docker-compose up

# New (v2)
docker compose up
```

If `docker compose` not available:
```bash
# Install Docker Compose v2
curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
chmod +x /usr/local/bin/docker-compose
docker-compose --version
```

**Prevention:**
- Use `docker compose` (v2) not `docker-compose`
- Update Docker to latest version

---

## Error: Service health check failing but container up

**Symptom:** `docker compose ps` shows:
```
market-data-service    Up (unhealthy)
```

**Root Cause:** Container is running but health check command is failing.

**Immediate Fix:**

1. Check what health check is running:
```bash
docker inspect <container-id> | jq '.[0].State.Health'
```

2. Run health check manually:
```bash
docker compose exec market-data-service python3 -c "
import urllib.request
urllib.request.urlopen('http://localhost:8001/health')
print('✅ Healthy')
"
```

3. Check the endpoint directly:
```bash
docker compose exec market-data-service curl -s http://localhost:8001/health | jq .
```

If it fails, check service logs:
```bash
docker compose logs market-data-service --tail 50
```

Common issues:
- Database connection failing (see database.md)
- Redis connection failing (see redis diagnostics below)
- Port not listening yet (increase `start_period`)

**Prevention:**
- Increase `start_period` for slow-starting services:

```yaml
healthcheck:
  start_period: 30s  # Wait 30s before first check
  interval: 10s
  timeout: 5s
  retries: 3
```

- Test health endpoint locally in dev
- Check dependencies are healthy before checking dependent services

---

## Error: Environment variables not reaching container

**Symptom:** Container logs show env var is empty:
```
DEBUG: DATABASE_URL=None
```

**Root Cause:** `.env` file not loaded, or variable not in docker-compose.yml environment section.

**Immediate Fix:**

1. Verify `.env` exists:
```bash
ls -la .env
cat .env | grep DATABASE_URL
```

2. Verify docker-compose references it:
```bash
docker compose config | grep "DATABASE_URL=" | head -5
```

3. Check container environment:
```bash
docker compose exec market-data-service env | grep DATABASE_URL
```

If empty, add to docker-compose.yml:
```yaml
environment:
  - DATABASE_URL=${DATABASE_URL}  # Interpolates from .env
```

4. Restart:
```bash
docker compose down
docker compose up -d
```

**Prevention:**
- `.env` must be in same directory as docker-compose.yml
- Variables in docker-compose.yml must use `${VAR_NAME}` syntax
- Test with `docker compose config` before deploying
- Never commit `.env` to git (add to `.gitignore`)

---

## Error: Port already in use

**Symptom:** Service fails to start:
```
Bind for 0.0.0.0:8001 failed: port is already allocated
```

**Root Cause:** Another container or process using the same port.

**Immediate Fix:**

Find what's using the port:
```bash
# macOS
lsof -i :8001

# Linux
netstat -tulpn | grep 8001
```

Stop the conflicting service:
```bash
# Kill by PID
kill -9 <PID>

# Or stop docker container
docker kill <container-id>

# Or change port mapping in docker-compose.yml
# Change "8001:8001" to "8010:8001"
```

Then restart:
```bash
docker compose up -d
```

**Prevention:**
- Use unique port numbers for each service (already done in docker-compose.yml)
- Stop services cleanly: `docker compose down` not `Ctrl+C`
- Check ports before deployment: `netstat -tulpn | grep LISTEN`

---

## Error: Dockerfile COPY order causes runtime error

**Symptom:** Container starts but import fails:
```
ModuleNotFoundError: No module named 'jwt'
```

Even though `RUN pip install PyJWT` is in Dockerfile.

**Root Cause:** Dockerfile copies requirements.txt to wrong location or wrong order. Later `COPY . .` overwrites it.

**Immediate Fix:**

Check Dockerfile structure in `/Volumes/CH-DataOne/AlbertoDBP/Agentic/income-platform/Dockerfile`:

```dockerfile
# Correct order (used by market-data-service):
COPY src/market-data-service/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

COPY . .  # This copies entire repo

# Then explicit install to ensure it's present:
RUN pip install --no-cache-dir PyJWT==2.8.0

# Wrong order (would fail):
# COPY . .              # Copies everything
# COPY requirements.txt # Overwrites with different file
```

If you see wrong order:
```bash
# Edit Dockerfile
# Move COPY requirements.txt BEFORE COPY .
# Then rebuild
docker compose build --no-cache market-data-service
```

**Prevention:**
- Always copy requirements.txt to `/tmp/` before `COPY . .`
- Pin all package versions
- Use explicit install steps for critical dependencies

---

## Error: Container restarts in loop

**Symptom:** Service keeps restarting:
```
docker compose ps
market-data-service    Restarting (1) X seconds ago
```

**Root Cause:** Startup error causing exit, then restart policy tries again.

**Immediate Fix:**

1. Check restart policy:
```bash
docker inspect <container-id> | jq '.[0].HostConfig.RestartPolicy'
```

2. View exit code and reason:
```bash
docker inspect <container-id> | jq '.[0].State | {ExitCode, Error}'
```

3. See startup logs:
```bash
docker compose logs market-data-service --tail 100
```

Fix the underlying issue (see service-startup.md, database.md, etc.)

4. Disable restart during debugging:
```yaml
restart: "no"  # Temporarily in docker-compose.yml
```

Then restart once fixed:
```bash
docker compose up -d
```

**Prevention:**
- Use `restart: unless-stopped` for production
- Monitor startup logs before considering service "up"
- Test locally before deploying

---

## Error: Build context too large

**Symptom:** Docker build times out:
```
Error response from daemon: build context too large
```

**Root Cause:** Docker sending too much context (venv, node_modules, large files).

**Immediate Fix:**

Add `.dockerignore` to repo root:
```bash
cat > .dockerignore << 'EOF'
venv/
.venv/
env/
node_modules/
.git/
.gitignore
*.pyc
__pycache__/
.pytest_cache/
.mypy_cache/
.env.local
*.log
*.tmp
dist/
build/
.eggs/
*.egg-info/
EOF
```

Then rebuild:
```bash
docker compose build --no-cache
```

**Prevention:**
- Use `.dockerignore` (same as `.gitignore`)
- Keep build context lean
- Don't copy entire repo if not needed

---

## Error: Image not found after tagging

**Symptom:**
```
docker: Error response from daemon: manifest not found
```

**Root Cause:** Image tagged locally but not pushed to registry.

**Immediate Fix:**

If using local images:
```bash
# List local images
docker images

# Use image name exactly as shown
docker run market-data-service:latest
```

If pushing to registry:
```bash
# Tag image
docker tag market-data-service:latest your-registry/market-data-service:v1.0.0

# Push to registry
docker push your-registry/market-data-service:v1.0.0

# Update docker-compose to use registry image
# image: your-registry/market-data-service:v1.0.0
```

**Prevention:**
- For prod, always push to registry (Docker Hub, ECR, etc.)
- Use explicit image URIs in docker-compose.yml
- Version images with git tags: `docker tag ... :v$(git describe --tags)`

---

## Redis Connectivity Issues

**Symptom:** Service logs show Redis connection failed.

**Immediate Fix:**

```bash
# Check if redis container running
docker compose ps | grep redis

# Start if needed
docker compose up -d redis

# Test connectivity
docker compose exec market-data-service nc -zv redis 6379

# Check redis is responsive
docker compose exec redis redis-cli ping
```

Expected output: `PONG`

---

## Debugging Checklist

- [ ] Image built recently? `docker images --format "{{.Repository}}\t{{.CreatedAt}}"`
- [ ] All containers running? `docker compose ps`
- [ ] Health checks passing? `docker compose ps` (status shows "Up" not "unhealthy")?
- [ ] Environment variables set? `docker compose exec <service> env`
- [ ] Logs showing errors? `docker compose logs <service>`
- [ ] Dependencies up? `docker compose ps` shows all services up?
- [ ] Ports available? `netstat -tulpn | grep LISTEN`
- [ ] No disk space issues? `df -h` shows >20% free?
- [ ] Network connectivity? `docker compose exec <service> nc -zv postgres 5432`

---

## See Also

- [Service Startup Failures](./service-startup.md) — Container exits with errors
- [Database Connection Errors](./database.md) — Database connectivity issues
- [Authentication Errors](./authentication.md) — JWT and auth issues
